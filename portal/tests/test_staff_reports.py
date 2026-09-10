from datetime import time, timedelta
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from portal.models import (
    AttendanceRecord,
    PortalChild,
    PortalFamily,
    PortalProgram,
    PortalStaffAccount,
    PortalUnit,
)
from portal.staff_auth import PORTAL_AUTH_SESSION_KEY
from portal.staff_services import get_member_summaries_for_unit, weekly_attendance_report_data


class StaffReportsTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.unit = PortalUnit.objects.create(slug="school-18", name="School 18", is_active=True)
        self.program = PortalProgram.objects.create(
            unit=self.unit,
            name="After-School 2026–27",
            start_time=time(15, 0),
            end_time=time(18, 0),
            is_active=True,
        )
        self.family = PortalFamily.objects.create(
            unit=self.unit,
            slug="jacobs",
            name="Jacobs",
            primary_contact="Pat Jacobs",
            billing_type="Private pay",
            status="Active",
            program_label="After-School 2026–27",
        )
        self.child = PortalChild.objects.create(
            family=self.family,
            name="Jordan Jacobs",
            grade="4th",
            school="Lincoln Elementary",
            is_active=True,
        )
        self.user = User.objects.create_user(username="staff:reports", password="StaffPass123!")
        PortalStaffAccount.objects.create(
            user=self.user,
            unit=self.unit,
            display_name="Report Staff",
            role="Unit director",
            is_active=True,
        )
        self.client.force_login(self.user)
        session = self.client.session
        session[PORTAL_AUTH_SESSION_KEY] = "staff"
        session.save()
        today = timezone.localdate()
        self.monday = today - timedelta(days=today.weekday())
        AttendanceRecord.objects.create(
            child=self.child,
            program=self.program,
            date=self.monday,
            status=AttendanceRecord.STATUS_PRESENT,
        )

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_weekly_attendance_report_renders_live_weekday_headers(self):
        response = self.client.get(reverse("portal_staff_weekly_attendance_report"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Jordan Jacobs")
        self.assertContains(response, "Weekly attendance summary")
        monday_label = self.monday.strftime("%a")
        monday_short = self.monday.strftime("%b %d")
        self.assertContains(response, monday_label)
        self.assertContains(response, monday_short)
        self.assertContains(response, "✓")
        week_days = response.context["week_days"]
        self.assertEqual(len(week_days), 5)
        self.assertEqual(week_days[0]["label"], monday_label)
        self.assertEqual(week_days[0]["date_short"], monday_short)
        self.assertNotIn("strftime", response.content.decode())

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_weekly_attendance_data_marks_present_days(self):
        payload = weekly_attendance_report_data(self.unit, self.program, self.monday)
        self.assertEqual(payload["weekly_rows"][0]["child"], "Jordan Jacobs")
        self.assertEqual(payload["weekly_rows"][0]["days"][0], True)
        self.assertEqual(payload["weekly_rows"][0]["total"], 1)
        self.assertEqual(len(payload["week_days"]), 5)
        self.assertIn(" – ", payload["week_range_display"])

    @override_settings(PORTAL_PREVIEW_MODE=True)
    def test_weekly_attendance_report_preview_mode_still_renders(self):
        response = self.client.get(reverse("portal_staff_weekly_attendance_report"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Weekly attendance summary")

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_staff_report_pages_return_ok(self):
        urls = [
            reverse("portal_staff_page", kwargs={"page": "reports"}),
            reverse("portal_staff_attendance_report"),
            reverse("portal_staff_weekly_attendance_report"),
            reverse("portal_staff_attendance_blank_daily"),
            reverse("portal_staff_attendance_blank_weekly"),
            reverse("portal_staff_signout_blank"),
            reverse("portal_staff_medical_report"),
            reverse("portal_staff_school_bus_report"),
            reverse("portal_staff_pickup_report"),
            reverse("portal_staff_member_information_report"),
            reverse("portal_staff_attendance_grade_report"),
            reverse("portal_staff_emergency_contact_report"),
            reverse("portal_staff_program_roster", kwargs={"program_slug": "after-school-2026-27"}),
            reverse("portal_staff_balances_export"),
            reverse("portal_staff_agency_copay_export"),
            reverse("portal_staff_page", kwargs={"page": "drop-off-pickup"}),
            reverse("portal_staff_page", kwargs={"page": "member-policies"}),
            reverse("portal_staff_member_policies_print"),
            reverse("portal_staff_application_print", kwargs={"app_slug": "jordan-jacobs"}),
            reverse("apply"),
        ]
        for url in urls:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200, url)

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_pickup_report_lists_enrolled_children(self):
        response = self.client.get(reverse("portal_staff_pickup_report"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Jordan Jacobs")
        self.assertContains(response, "Pat Jacobs")

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_member_policy_summaries_match_staff_template(self):
        summaries = get_member_summaries_for_unit(self.unit)
        self.assertEqual(summaries[0]["family_name"], "Jacobs")
        self.assertIsInstance(summaries[0]["children"], list)
        response = self.client.get(reverse("portal_staff_page", kwargs={"page": "member-policies"}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Jacobs")

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_csv_exports_are_downloadable(self):
        balances = self.client.get(reverse("portal_staff_balances_export"))
        copay = self.client.get(reverse("portal_staff_agency_copay_export"))
        self.assertEqual(balances.status_code, 200)
        self.assertEqual(copay.status_code, 200)
        self.assertEqual(balances["Content-Type"], "text/csv")
        self.assertEqual(copay["Content-Type"], "text/csv")
        self.assertIn("Family", balances.content.decode())
        self.assertIn("Child", copay.content.decode())


def _enrollment_application(family, *, first, last, location="school_18", program="after_school"):
    from datetime import date

    from enrollment.models import EnrollmentApplication

    return EnrollmentApplication.objects.create(
        program=program,
        program_location=location,
        family_name=family.name,
        primary_email="parent@example.com",
        home_address="1 Main St",
        primary_first_name="Pat",
        primary_last_name=family.name,
        primary_gender="female",
        primary_language="english",
        primary_relationship="mother",
        primary_phone="555-0100",
        primary_phone_type="cell",
        primary_text_subscription="yes",
        primary_email_subscription="yes",
        primary_email_address="parent@example.com",
        primary_authorized_pickup="yes",
        student_first_name=first,
        student_last_name=last,
        student_gender="female",
        student_dob=date(2016, 1, 1),
        student_language="english",
        student_ethnicity="unknown",
        student_race="unknown",
        student_grade="4",
        student_school="Lincoln Elementary",
        health_statement="good_health",
        membership_fee_agreed="no",
        payment_method="private_pay",
        payment_plan="weekly",
        payment_plan_signature="Pat",
        payment_plan_signed_date=date(2026, 8, 1),
        status="enrolled",
        portal_family=family,
    )


class StaffEmergencyContactReportTests(TestCase):
    def setUp(self):
        from enrollment.models import EmergencyContact

        User = get_user_model()
        self.school_18 = PortalUnit.objects.create(slug="school-18", name="School 18", is_active=True)
        self.school_26 = PortalUnit.objects.create(slug="school-26", name="School 26", is_active=True)
        self.family = PortalFamily.objects.create(
            unit=self.school_18,
            slug="jacobs",
            name="Jacobs",
            primary_contact="Pat Jacobs",
            status="Active",
            program_label="After-School 2026–27",
        )
        self.jordan = PortalChild.objects.create(
            family=self.family,
            name="Jordan Jacobs",
            grade="4th",
            school="Lincoln Elementary",
            is_active=True,
            unit=self.school_18,
        )
        self.maya = PortalChild.objects.create(
            family=self.family,
            name="Maya Jacobs",
            grade="1st",
            school="Lincoln Elementary",
            is_active=True,
            unit=self.school_18,
        )
        other_family = PortalFamily.objects.create(
            unit=self.school_26,
            slug="rivera",
            name="Rivera",
            primary_contact="Pat Rivera",
            status="Active",
        )
        self.other_child = PortalChild.objects.create(
            family=other_family,
            name="Ada Rivera",
            grade="3rd",
            school="School 26",
            is_active=True,
            unit=self.school_26,
        )
        jordan_app = _enrollment_application(self.family, first="Jordan", last="Jacobs")
        EmergencyContact.objects.create(
            application=jordan_app,
            order=1,
            first_name="Rosa",
            last_name="Jacobs",
            phone="555-0199",
            relationship="Grandmother",
            authorized_pickup=True,
        )
        EmergencyContact.objects.create(
            application=jordan_app,
            order=2,
            first_name="Mike",
            last_name="Jacobs",
            phone="555-0188",
            relationship="Uncle",
            authorized_pickup=False,
        )
        other_app = _enrollment_application(
            other_family, first="Ada", last="Rivera", location="school_26"
        )
        EmergencyContact.objects.create(
            application=other_app,
            order=1,
            first_name="Luis",
            last_name="Rivera",
            phone="555-0260",
            relationship="Father",
            authorized_pickup=True,
        )
        self.staff = User.objects.create_user(username="staff:econtacts", password="StaffPass123!")
        PortalStaffAccount.objects.create(
            user=self.staff,
            unit=self.school_18,
            display_name="Report Staff",
            role="Unit director",
            is_active=True,
        )
        self.client.force_login(self.staff)
        session = self.client.session
        session[PORTAL_AUTH_SESSION_KEY] = "staff"
        session.save()

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_print_page_returns_ok_and_lists_unit_contacts(self):
        response = self.client.get(reverse("portal_staff_emergency_contact_report"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Emergency contact list")
        self.assertContains(response, "Jordan Jacobs")
        self.assertContains(response, "Rosa Jacobs")
        self.assertContains(response, "Print / Save PDF")
        self.assertContains(response, "How to print emergency contacts")
        self.assertNotContains(response, "Ada Rivera")
        self.assertNotContains(response, "Luis Rivera")

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_staff_only_see_their_unit_children(self):
        from portal.staff_services import emergency_contact_report_for_unit

        names_18 = {row["child"] for row in emergency_contact_report_for_unit(self.school_18)}
        names_26 = {row["child"] for row in emergency_contact_report_for_unit(self.school_26)}
        self.assertEqual(names_18, {"Jordan Jacobs", "Maya Jacobs"})
        self.assertEqual(names_26, {"Ada Rivera"})
        self.assertNotIn("Ada Rivera", names_18)
        self.assertNotIn("Jordan Jacobs", names_26)

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_filters_reduce_rows(self):
        from portal.pickup_services import filter_emergency_contact_rows
        from portal.staff_services import emergency_contact_report_for_unit

        rows = emergency_contact_report_for_unit(self.school_18)
        self.assertGreater(len(rows), 1)
        by_child = filter_emergency_contact_rows(rows, {"child": "Jordan Jacobs"})
        self.assertEqual({row["child"] for row in by_child}, {"Jordan Jacobs"})
        self.assertEqual(len(by_child), 2)
        by_contact = filter_emergency_contact_rows(rows, {"q": "rosa"})
        self.assertEqual([row["contact_name"] for row in by_contact], ["Rosa Jacobs"])
        authorized = filter_emergency_contact_rows(rows, {"authorized": "yes"})
        self.assertEqual([row["contact_name"] for row in authorized], ["Rosa Jacobs"])
        by_school = filter_emergency_contact_rows(rows, {"school": "Lincoln Elementary"})
        self.assertTrue(by_school)
        page = self.client.get(
            reverse("portal_staff_emergency_contact_report"),
            {"child": "Jordan Jacobs", "authorized": "yes"},
        )
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, "Rosa Jacobs")
        self.assertNotContains(page, "Mike Jacobs")
        visible = {row["child"] for row in page.context["report_rows"]}
        self.assertEqual(visible, {"Jordan Jacobs"})
        self.assertEqual([row["contact_name"] for row in page.context["report_rows"]], ["Rosa Jacobs"])

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_missing_contacts_filter(self):
        from portal.pickup_services import filter_emergency_contact_rows
        from portal.staff_services import emergency_contact_report_for_unit

        rows = emergency_contact_report_for_unit(self.school_18)
        missing = filter_emergency_contact_rows(rows, {"missing": "on"})
        self.assertEqual([row["child"] for row in missing], ["Maya Jacobs"])
        self.assertFalse(missing[0]["has_contact"])
        page = self.client.get(
            reverse("portal_staff_emergency_contact_report"),
            {"missing": "on"},
        )
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, "Maya Jacobs")
        self.assertContains(page, "None on file")
        self.assertNotContains(page, "Rosa Jacobs")

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_reports_hub_links_to_emergency_contacts(self):
        hub = self.client.get(reverse("portal_staff_page", kwargs={"page": "reports"}))
        self.assertEqual(hub.status_code, 200)
        self.assertContains(hub, "Emergency contact list")
        self.assertContains(hub, reverse("portal_staff_emergency_contact_report"))
        self.assertContains(hub, "portal-reports-grid")
        self.assertContains(hub, "portal-report-card")
        self.assertContains(hub, "Member information")
        self.assertContains(hub, reverse("portal_staff_member_information_report"))
        self.assertContains(hub, "Attendance by grade")
        self.assertContains(hub, reverse("portal_staff_attendance_grade_report"))


class ReportsHubGridCssTests(TestCase):
    def test_portal_css_keeps_a_multi_column_reports_grid(self):
        css = Path("static/css/portal.css").read_text()
        start = css.index(".portal-reports-grid {")
        card = css.index(".portal-report-card {", start)
        grid = css[start:card]
        self.assertIn("display: grid", grid)
        self.assertIn("repeat(2, minmax(0, 1fr))", grid)
        self.assertIn("repeat(3, minmax(0, 1fr))", grid)
        self.assertIn("repeat(4, minmax(0, 1fr))", grid)
        member_table = css[css.index(".portal-member-info-table th") : css.index(".portal-report-missing-row")]
        self.assertIn("padding: 0.35rem 0.45rem;", member_table)
        self.assertIn("}", member_table)
        self.assertNotIn("padding: 0.35rem 0.45rem;\n.portal-report-filters", member_table)
