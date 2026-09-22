from datetime import date, time

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from enrollment.models import EnrollmentApplication
from portal.care_program import before_care_roster_rows
from portal.models import PortalChild, PortalFamily, PortalProgram, PortalStaffAccount, PortalUnit
from portal.report_sheets import signout_blank_context
from portal.staff_auth import PORTAL_AUTH_SESSION_KEY
from portal.staff_services import weekly_attendance_report_data


def _make_app(family, child, *, program="after_school", status="approved"):
    first, _, last = child.name.partition(" ")
    return EnrollmentApplication.objects.create(
        program=program,
        program_location="school_18",
        family_name=family.name,
        primary_email=f"{family.slug}@example.com",
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
        primary_email_address=f"{family.slug}@example.com",
        primary_authorized_pickup="yes",
        student_first_name=first,
        student_last_name=last or family.name,
        student_gender="female",
        student_dob=date(2016, 1, 1),
        student_language="english",
        student_ethnicity="unknown",
        student_race="unknown",
        student_grade="3",
        student_school=child.school or "Lincoln Elementary",
        health_statement="good_health",
        membership_fee_agreed="no",
        payment_method="private_pay",
        payment_plan="weekly",
        payment_plan_signature="Pat",
        payment_plan_signed_date=date(2026, 8, 1),
        status=status,
        portal_family=family,
    )


class CareProgramFilterTests(TestCase):
    def setUp(self):
        self.unit = PortalUnit.objects.create(slug="school-18", name="School 18", is_active=True)
        self.other = PortalUnit.objects.create(slug="school-26", name="School 26", is_active=True)
        self.program = PortalProgram.objects.create(
            unit=self.unit,
            name="After-School 2026–27",
            start_time=time(15, 0),
            end_time=time(18, 0),
            is_active=True,
        )
        PortalProgram.objects.create(
            unit=self.other,
            name="After-School 26",
            start_time=time(15, 0),
            end_time=time(18, 0),
            is_active=True,
        )
        family = PortalFamily.objects.create(unit=self.unit, slug="jacobs", name="Jacobs")
        other_family = PortalFamily.objects.create(unit=self.other, slug="lee", name="Lee")
        self.after_only = PortalChild.objects.create(
            family=family, name="Jordan Jacobs", grade="4th", school="Lincoln Elementary", is_active=True
        )
        self.before_only = PortalChild.objects.create(
            family=family, name="Maya Jacobs", grade="2nd", school="Lincoln Elementary", is_active=True
        )
        self.both = PortalChild.objects.create(
            family=family, name="Sam Jacobs", grade="3rd", school="Lincoln Elementary", is_active=True
        )
        self.waitlist_before = PortalChild.objects.create(
            family=family, name="Riley Jacobs", grade="1st", school="Lincoln Elementary", is_active=True
        )
        self.inactive_before = PortalChild.objects.create(
            family=family, name="Quinn Jacobs", grade="5th", school="Lincoln Elementary", is_active=False
        )
        self.other_before = PortalChild.objects.create(
            family=other_family, name="Nia Lee", grade="4th", school="Riverside School", is_active=True
        )
        _make_app(family, self.after_only, program="after_school", status="approved")
        _make_app(family, self.before_only, program="before_care", status="approved")
        _make_app(family, self.both, program="after_school", status="approved")
        _make_app(family, self.both, program="before_care", status="enrolled")
        _make_app(family, self.waitlist_before, program="before_care", status="waitlist")
        _make_app(family, self.inactive_before, program="before_care", status="approved")
        _make_app(other_family, self.other_before, program="before_care", status="approved")
        self.today = timezone.localdate()
        User = get_user_model()
        self.staff_user = User.objects.create_user(username="staff:care", password="StaffPass123!")
        PortalStaffAccount.objects.create(
            user=self.staff_user,
            unit=self.unit,
            display_name="Care Staff",
            role="Unit director",
            is_active=True,
        )
        self.admin_user = User.objects.create_user(username="staff:careadmin", password="AdminPass123")
        PortalStaffAccount.objects.create(
            user=self.admin_user,
            unit=self.unit,
            display_name="Portal Admin",
            role="Portal admin",
            all_units_access=True,
            is_active=True,
        )

    def _login(self, user, area):
        self.client.force_login(user)
        session = self.client.session
        session[PORTAL_AUTH_SESSION_KEY] = area
        session.save()

    def _names(self, payload):
        return [row["child"] for row in payload["weekly_rows"]]

    def test_before_care_roster_lists_approved_before_care_only(self):
        names = [row["child"] for row in before_care_roster_rows(unit=self.unit)]
        self.assertEqual(names, ["Maya Jacobs", "Sam Jacobs"])
        self.assertNotIn("Jordan Jacobs", names)
        self.assertNotIn("Riley Jacobs", names)
        self.assertNotIn("Quinn Jacobs", names)
        self.assertNotIn("Nia Lee", names)

        admin_names = [row["child"] for row in before_care_roster_rows(admin=True)]
        self.assertEqual(admin_names, ["Maya Jacobs", "Nia Lee", "Sam Jacobs"])

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_before_care_report_page_and_hub(self):
        self._login(self.staff_user, "staff")
        hub = self.client.get(reverse("portal_staff_page", kwargs={"page": "reports"}))
        self.assertContains(hub, reverse("portal_staff_before_care_report"))
        self.assertContains(hub, "Before care")

        page = self.client.get(reverse("portal_staff_before_care_report"))
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, "Maya Jacobs")
        self.assertContains(page, "Sam Jacobs")
        self.assertNotContains(page, "Jordan Jacobs")
        self.assertNotContains(page, "Riley Jacobs")
        self.assertNotContains(page, "Quinn Jacobs")
        self.assertNotContains(page, "Nia Lee")
        self.assertContains(page, reverse("portal_staff_family_detail", kwargs={"family_slug": "jacobs"}))
        self.assertContains(page, "How to see before-care kids")

        csv_page = self.client.get(reverse("portal_staff_before_care_report"), {"format": "csv"})
        body = csv_page.content.decode()
        self.assertIn("Maya Jacobs", body)
        self.assertNotIn("Jordan Jacobs", body)

        self._login(self.admin_user, "admin")
        admin_hub = self.client.get(reverse("portal_admin_page", kwargs={"page": "reports"}))
        self.assertContains(admin_hub, reverse("portal_admin_before_care_report"))
        admin = self.client.get(reverse("portal_admin_before_care_report"))
        self.assertContains(admin, "Nia Lee")
        self.assertContains(admin, "Maya Jacobs")
        one_unit = self.client.get(reverse("portal_admin_before_care_report"), {"unit": "school-26"})
        self.assertContains(one_unit, "Nia Lee")
        self.assertNotContains(one_unit, "Maya Jacobs")

    def test_weekly_sheet_after_excludes_before_only(self):
        after = weekly_attendance_report_data(
            self.unit, self.program, self.today, filters={"care": "after"}
        )
        names = self._names(after)
        self.assertIn("Jordan Jacobs", names)
        self.assertIn("Sam Jacobs", names)
        self.assertIn("Riley Jacobs", names)
        self.assertNotIn("Maya Jacobs", names)
        self.assertNotIn("Quinn Jacobs", names)
        self.assertNotIn("Nia Lee", names)

    def test_weekly_sheet_before_excludes_after_only(self):
        before = weekly_attendance_report_data(
            self.unit, self.program, self.today, filters={"care": "before"}
        )
        names = self._names(before)
        self.assertEqual(names, ["Maya Jacobs", "Sam Jacobs"])
        self.assertNotIn("Jordan Jacobs", names)
        self.assertNotIn("Riley Jacobs", names)

    def test_weekly_sheet_all_includes_both(self):
        all_kids = weekly_attendance_report_data(self.unit, self.program, self.today)
        names = self._names(all_kids)
        self.assertEqual(names, ["Jordan Jacobs", "Maya Jacobs", "Riley Jacobs", "Sam Jacobs"])
        self.assertEqual(all_kids["care_label"], "All")

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_weekly_page_filter_changes_printed_names(self):
        self._login(self.staff_user, "staff")
        default = self.client.get(
            reverse("portal_staff_weekly_attendance_report"), {"date": self.today.isoformat()}
        )
        self.assertContains(default, "Jordan Jacobs")
        self.assertContains(default, "Maya Jacobs")
        self.assertContains(default, 'name="care"')
        self.assertContains(default, "After-care")
        self.assertContains(default, "Before-care")
        self.assertContains(default, "Choose After-care, Before-care, or All")

        after = self.client.get(
            reverse("portal_staff_weekly_attendance_report"),
            {"date": self.today.isoformat(), "care": "after"},
        )
        self.assertContains(after, "Jordan Jacobs")
        self.assertNotContains(after, "Maya Jacobs")
        self.assertContains(after, "Sam Jacobs")

        before = self.client.get(
            reverse("portal_staff_weekly_attendance_report"),
            {"date": self.today.isoformat(), "care": "before"},
        )
        self.assertContains(before, "Maya Jacobs")
        self.assertNotContains(before, "Jordan Jacobs")
        self.assertContains(before, "Sam Jacobs")

        blank = self.client.get(
            reverse("portal_staff_attendance_blank_weekly"),
            {"date": self.today.isoformat(), "care": "before"},
        )
        self.assertContains(blank, "Maya Jacobs")
        self.assertNotContains(blank, "Jordan Jacobs")

    def test_signout_sheet_same_care_filter(self):
        all_rows = signout_blank_context(self.today, live=True, unit=self.unit, program_obj=self.program)
        all_names = [row["child"] for row in all_rows["enrolled_rows"]]
        self.assertEqual(all_names, ["Jordan Jacobs", "Maya Jacobs", "Riley Jacobs", "Sam Jacobs"])

        after = signout_blank_context(
            self.today, live=True, unit=self.unit, program_obj=self.program, care="after"
        )
        after_names = [row["child"] for row in after["enrolled_rows"]]
        self.assertIn("Jordan Jacobs", after_names)
        self.assertNotIn("Maya Jacobs", after_names)
        self.assertIn("Sam Jacobs", after_names)

        before = signout_blank_context(
            self.today, live=True, unit=self.unit, program_obj=self.program, care="before"
        )
        before_names = [row["child"] for row in before["enrolled_rows"]]
        self.assertEqual(before_names, ["Maya Jacobs", "Sam Jacobs"])

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_signout_page_filter_changes_printed_names(self):
        self._login(self.staff_user, "staff")
        default = self.client.get(reverse("portal_staff_signout_blank"))
        self.assertContains(default, "Jordan Jacobs")
        self.assertContains(default, "Maya Jacobs")
        self.assertContains(default, 'name="care"')
        self.assertContains(default, "Choose After-care, Before-care, or All")

        after = self.client.get(reverse("portal_staff_signout_blank"), {"care": "after"})
        self.assertContains(after, "Jordan Jacobs")
        self.assertNotContains(after, "Maya Jacobs")

        before = self.client.get(reverse("portal_staff_signout_blank"), {"care": "before"})
        self.assertContains(before, "Maya Jacobs")
        self.assertNotContains(before, "Jordan Jacobs")
        self.assertContains(before, "Sam Jacobs")
        self.assertNotContains(before, "Nia Lee")
