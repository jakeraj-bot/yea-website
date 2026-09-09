from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from enrollment.models import EnrollmentApplication
from portal.admin_reports import build_admin_report
from portal.member_report import (
    PROGRAM_AFTER_CARE,
    PROGRAM_BEFORE_CARE,
    PROGRAM_DROP_IN,
    WAITING,
    filter_member_information_rows,
    member_information_rows,
)
from portal.models import (
    PortalAgency,
    PortalAgencyProfile,
    PortalChild,
    PortalFamily,
    PortalStaffAccount,
    PortalUnit,
)
from portal.staff_auth import PORTAL_AUTH_SESSION_KEY


def _application(family, child, *, program="after_school", location="school_18", status="approved"):
    first, _, last = child.name.partition(" ")
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
        student_last_name=last or family.name,
        student_gender="female",
        student_dob=date(2016, 1, 1),
        student_language="english",
        student_ethnicity="unknown",
        student_race="unknown",
        student_grade="4",
        student_school=child.school or "Lincoln Elementary",
        health_statement="good_health",
        membership_fee_agreed="no",
        payment_method="4cs" if family.billing_type == "4Cs" else "private_pay",
        payment_plan="weekly",
        payment_plan_signature="Pat",
        payment_plan_signed_date=date(2026, 8, 1),
        status=status,
        portal_family=family,
    )


class MemberInformationReportTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.school_18 = PortalUnit.objects.create(slug="school-18", name="School 18", is_active=True)
        self.school_26 = PortalUnit.objects.create(slug="school-26", name="School 26", is_active=True)

        self.private_family = PortalFamily.objects.create(
            unit=self.school_18,
            slug="jacobs",
            name="Jacobs",
            primary_contact="Pat Jacobs",
            billing_type="Private pay",
            status="Active",
            program_label="After-school program",
        )
        self.private_child = PortalChild.objects.create(
            family=self.private_family,
            unit=self.school_18,
            name="Jordan Jacobs",
            grade="4th",
            school="Lincoln Elementary",
            billing_plan="Weekly",
            is_active=True,
        )
        _application(self.private_family, self.private_child, program="after_school")

        self.drop_family = PortalFamily.objects.create(
            unit=self.school_18,
            slug="chen",
            name="Chen",
            primary_contact="Wei Chen",
            billing_type="Private pay",
            status="Active",
            program_label="Drop-off program",
        )
        self.drop_child = PortalChild.objects.create(
            family=self.drop_family,
            unit=self.school_18,
            name="Ethan Chen",
            grade="5th",
            school="Lincoln Elementary",
            billing_plan="Monthly",
            is_active=True,
            is_drop_off=True,
        )
        _application(self.drop_family, self.drop_child, program="drop_off")

        self.before_family = PortalFamily.objects.create(
            unit=self.school_18,
            slug="lee",
            name="Lee",
            primary_contact="Sam Lee",
            billing_type="Private pay",
            status="Active",
            program_label="Before care",
        )
        self.before_child = PortalChild.objects.create(
            family=self.before_family,
            unit=self.school_18,
            name="Mina Lee",
            grade="1st",
            school="Riverside School",
            billing_plan="Weekly",
            is_active=True,
        )
        _application(self.before_family, self.before_child, program="before_care", status="waitlist")

        self.agency = PortalAgency.objects.create(slug="passaic-4cs", name="Passaic County 4Cs", is_active=True)
        self.four_cs_family = PortalFamily.objects.create(
            unit=self.school_18,
            slug="martinez",
            name="Martinez",
            primary_contact="Rosa Martinez",
            billing_type="4Cs",
            status="Active",
            program_label="After-school program",
        )
        self.four_cs_child = PortalChild.objects.create(
            family=self.four_cs_family,
            unit=self.school_18,
            name="Sofia Martinez",
            grade="2nd",
            school="Lincoln Elementary",
            billing_plan="Weekly",
            is_active=True,
        )
        _application(self.four_cs_family, self.four_cs_child, program="after_school")
        PortalAgencyProfile.objects.create(
            unit=self.school_18,
            family=self.four_cs_family,
            child=self.four_cs_child,
            agency=self.agency,
            auth_number="4CS-2026-1001",
            daily_agency_rate=Decimal("36.00"),
            weekly_agency_rate=Decimal("180.00"),
            daily_copay=Decimal("5.00"),
            weekly_copay=Decimal("25.00"),
        )

        self.waiting_family = PortalFamily.objects.create(
            unit=self.school_18,
            slug="nguyen",
            name="Nguyen",
            primary_contact="Lan Nguyen",
            billing_type="4Cs",
            status="Active",
        )
        self.waiting_child = PortalChild.objects.create(
            family=self.waiting_family,
            unit=self.school_18,
            name="An Nguyen",
            grade="3rd",
            school="Riverside School",
            billing_plan="Weekly",
            is_active=True,
        )

        self.other_family = PortalFamily.objects.create(
            unit=self.school_26,
            slug="williams",
            name="Williams",
            primary_contact="Chris Williams",
            billing_type="Private pay",
            status="Active",
        )
        self.other_child = PortalChild.objects.create(
            family=self.other_family,
            unit=self.school_26,
            name="Aiden Williams",
            grade="3rd",
            school="School 26",
            billing_plan="Bi-Weekly",
            is_active=True,
        )

        self.staff_user = User.objects.create_user(username="staff:reports", password="StaffPass123!")
        PortalStaffAccount.objects.create(
            user=self.staff_user,
            unit=self.school_18,
            display_name="Report Staff",
            role="Unit director",
            is_active=True,
        )
        self.admin_user = User.objects.create_user(username="staff:portaladmin", password="AdminPass123")
        PortalStaffAccount.objects.create(
            user=self.admin_user,
            unit=self.school_18,
            display_name="Portal Admin",
            role="Portal admin",
            all_units_access=True,
            is_active=True,
        )

    def _login_staff(self):
        self.client.force_login(self.staff_user)
        session = self.client.session
        session[PORTAL_AUTH_SESSION_KEY] = "staff"
        session.save()

    def _login_admin(self):
        self.client.force_login(self.admin_user)
        session = self.client.session
        session[PORTAL_AUTH_SESSION_KEY] = "admin"
        session.save()

    def test_rows_include_requested_columns_and_4cs_waiting(self):
        rows = {row["child"]: row for row in member_information_rows(unit=self.school_18)}
        self.assertIn("Jordan Jacobs", rows)
        self.assertNotIn("Aiden Williams", rows)
        jordan = rows["Jordan Jacobs"]
        for key in (
            "child",
            "family",
            "status",
            "unit",
            "school",
            "grade",
            "program",
            "billing",
            "plan",
            "four_cs",
            "four_cs_daily",
            "four_cs_copay",
            "four_cs_agency",
            "four_cs_agency_created",
            "contact",
        ):
            self.assertIn(key, jordan)
        self.assertEqual(jordan["school"], "Lincoln Elementary")
        self.assertEqual(jordan["grade"], "4th")
        self.assertEqual(jordan["billing"], "Private pay")
        self.assertEqual(jordan["four_cs"], "No")
        self.assertIn(PROGRAM_AFTER_CARE, jordan["program_types"])
        self.assertIn(PROGRAM_DROP_IN, rows["Ethan Chen"]["program_types"])
        self.assertIn(PROGRAM_BEFORE_CARE, rows["Mina Lee"]["program_types"])
        sofia = rows["Sofia Martinez"]
        self.assertEqual(sofia["four_cs"], "Yes")
        self.assertEqual(sofia["four_cs_agency"], "Passaic County 4Cs")
        self.assertIn("36.00", sofia["four_cs_daily"])
        self.assertIn("5.00", sofia["four_cs_copay"])
        self.assertNotEqual(sofia["four_cs_agency_created"], WAITING)
        waiting = rows["An Nguyen"]
        self.assertEqual(waiting["four_cs"], "Yes")
        self.assertEqual(waiting["four_cs_agency"], WAITING)
        self.assertEqual(waiting["four_cs_daily"], WAITING)
        self.assertEqual(waiting["agency_status_key"], "waiting")

    def test_each_column_filter(self):
        rows = member_information_rows(unit=self.school_18)
        names = lambda filtered: {row["child"] for row in filtered}
        self.assertEqual(names(filter_member_information_rows(rows, {"school": "Riverside School"})), {"Mina Lee", "An Nguyen"})
        self.assertEqual(names(filter_member_information_rows(rows, {"grade": "4th"})), {"Jordan Jacobs"})
        self.assertEqual(names(filter_member_information_rows(rows, {"program": PROGRAM_DROP_IN})), {"Ethan Chen"})
        self.assertEqual(names(filter_member_information_rows(rows, {"program": PROGRAM_BEFORE_CARE})), {"Mina Lee"})
        after_care = names(filter_member_information_rows(rows, {"program": PROGRAM_AFTER_CARE}))
        self.assertIn("Jordan Jacobs", after_care)
        self.assertIn("Sofia Martinez", after_care)
        self.assertNotIn("Ethan Chen", after_care)
        self.assertNotIn("Mina Lee", after_care)
        self.assertEqual(names(filter_member_information_rows(rows, {"billing": "4Cs"})), {"Sofia Martinez", "An Nguyen"})
        self.assertEqual(names(filter_member_information_rows(rows, {"plan": "Monthly"})), {"Ethan Chen"})
        self.assertEqual(names(filter_member_information_rows(rows, {"four_cs": "yes"})), {"Sofia Martinez", "An Nguyen"})
        self.assertNotIn("Sofia Martinez", names(filter_member_information_rows(rows, {"four_cs": "no"})))
        self.assertEqual(names(filter_member_information_rows(rows, {"agency_status": "waiting"})), {"An Nguyen"})
        self.assertEqual(names(filter_member_information_rows(rows, {"agency_status": "yes"})), {"Sofia Martinez"})
        self.assertEqual(names(filter_member_information_rows(rows, {"q": "jordan"})), {"Jordan Jacobs"})
        self.assertEqual(names(filter_member_information_rows(rows, {"status": "Active"})), names(rows))

    def test_unit_filter_scopes_admin_rows(self):
        all_rows = member_information_rows(unit=None)
        names = {row["child"] for row in all_rows}
        self.assertIn("Jordan Jacobs", names)
        self.assertIn("Aiden Williams", names)
        only_26 = filter_member_information_rows(all_rows, {"unit": "school-26"})
        self.assertEqual({row["child"] for row in only_26}, {"Aiden Williams"})

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_staff_and_admin_pages_return_ok_with_columns_and_guide(self):
        self._login_staff()
        staff = self.client.get(reverse("portal_staff_member_information_report"))
        self.assertEqual(staff.status_code, 200)
        self.assertContains(staff, "Jordan Jacobs")
        self.assertContains(staff, "Member information")
        self.assertContains(staff, "Program type")
        self.assertContains(staff, "4Cs daily")
        self.assertContains(staff, "How to print member information")
        self.assertNotContains(staff, "Aiden Williams")
        hub = self.client.get(reverse("portal_staff_page", kwargs={"page": "reports"}))
        self.assertContains(hub, reverse("portal_staff_member_information_report"))

        filtered = self.client.get(
            reverse("portal_staff_member_information_report"),
            {"school": "Lincoln Elementary", "four_cs": "yes"},
        )
        self.assertContains(filtered, "Sofia Martinez")
        self.assertNotContains(filtered, "Jordan Jacobs")

        self._login_admin()
        admin = self.client.get(reverse("portal_admin_member_information_report"))
        self.assertEqual(admin.status_code, 200)
        self.assertContains(admin, "Jordan Jacobs")
        self.assertContains(admin, "Aiden Williams")
        self.assertContains(admin, "How to print member information")
        admin_hub = self.client.get(reverse("portal_admin_page", kwargs={"page": "reports"}))
        self.assertContains(admin_hub, reverse("portal_admin_member_information_report"))
        self.assertContains(admin_hub, reverse("portal_admin_data_report", kwargs={"report_slug": "member-information"}))
        unit_filtered = self.client.get(
            reverse("portal_admin_member_information_report"),
            {"unit": "school-26"},
        )
        self.assertContains(unit_filtered, "Aiden Williams")
        self.assertNotContains(unit_filtered, "Jordan Jacobs")

        data = self.client.get(reverse("portal_admin_data_report", kwargs={"report_slug": "member-information"}))
        self.assertEqual(data.status_code, 200)
        self.assertContains(data, "Jordan Jacobs")
        self.assertContains(data, "Member information")
        self.assertContains(data, "Download CSV")
        csv_response = self.client.get(
            reverse("portal_admin_member_information_report"),
            {"format": "csv", "q": "sofia"},
        )
        self.assertEqual(csv_response.status_code, 200)
        self.assertIn("text/csv", csv_response["Content-Type"])
        self.assertIn(b"Sofia Martinez", csv_response.content)
        self.assertNotIn(b"Jordan Jacobs", csv_response.content)

    def test_four_cs_data_report_includes_waiting_and_daily_columns(self):
        report = build_admin_report("four-cs", {})
        children = {row["child"]: row for row in report["rows"]}
        self.assertIn("Sofia Martinez", children)
        self.assertIn("An Nguyen", children)
        self.assertEqual(children["An Nguyen"]["agency"], WAITING)
        self.assertIn("36.00", children["Sofia Martinez"]["daily_agency"])
        self.assertIn("agency_created", children["Sofia Martinez"])
        waiting_only = build_admin_report("four-cs", {"agency_status": "waiting"})
        self.assertEqual([row["child"] for row in waiting_only["rows"]], ["An Nguyen"])
