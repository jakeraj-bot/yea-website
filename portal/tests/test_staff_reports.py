from datetime import time, timedelta

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
