from datetime import time

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from enrollment.models import EnrollmentApplication
from enrollment.validators import format_us_phone
from portal.care_program import before_care_roster_rows
from portal.live_services import family_profile_live
from portal.models import PortalChild, PortalFamily, PortalProgram, PortalStaffAccount, PortalUnit
from portal.phone_format import format_us_phone as portal_format_us_phone
from portal.report_sheets import signout_blank_context
from portal.staff_auth import PORTAL_AUTH_SESSION_KEY
from portal.staff_services import weekly_attendance_report_data
from portal.tests.test_care_program_filters import _make_app


class PhoneFormatTests(TestCase):
    def test_ten_digit_us_numbers(self):
        self.assertEqual(format_us_phone("2014565698"), "(201) 456-5698")
        self.assertEqual(format_us_phone("201-456-5698"), "(201) 456-5698")
        self.assertEqual(format_us_phone("201.456.5698"), "(201) 456-5698")
        self.assertEqual(format_us_phone("(201) 456-5698"), "(201) 456-5698")
        self.assertEqual(portal_format_us_phone("12015550100"), "(201) 555-0100")

    def test_odd_values_stay_readable(self):
        self.assertEqual(format_us_phone("+44 20 7946 0958"), "+44 20 7946 0958")
        self.assertEqual(format_us_phone("555-CALL"), "555-CALL")
        self.assertEqual(format_us_phone(""), "")
        self.assertEqual(format_us_phone("   "), "")
        self.assertEqual(format_us_phone("12345"), "12345")


class ApplicationInactiveAttendanceTests(TestCase):
    def setUp(self):
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
        )
        self.both = PortalChild.objects.create(
            family=self.family, name="Sam Jacobs", grade="3rd", school="Lincoln Elementary", is_active=True
        )
        self.after_only = PortalChild.objects.create(
            family=self.family, name="Jordan Jacobs", grade="4th", school="Lincoln Elementary", is_active=True
        )
        self.before_only = PortalChild.objects.create(
            family=self.family, name="Maya Jacobs", grade="2nd", school="Lincoln Elementary", is_active=True
        )
        self.after_app = _make_app(self.family, self.after_only, program="after_school", status="approved")
        self.before_app = _make_app(self.family, self.before_only, program="before_care", status="approved")
        self.both_after = _make_app(self.family, self.both, program="after_school", status="approved")
        self.both_before = _make_app(self.family, self.both, program="before_care", status="enrolled")
        for app in (self.after_app, self.before_app, self.both_after, self.both_before):
            app.primary_phone = "2014565698"
            app.primary_email_address = "pat@example.com"
            app.save(update_fields=["primary_phone", "primary_email_address"])
        self.today = timezone.localdate()
        User = get_user_model()
        self.staff_user = User.objects.create_user(username="staff:appinactive", password="StaffPass123!")
        PortalStaffAccount.objects.create(
            user=self.staff_user,
            unit=self.unit,
            display_name="Care Staff",
            role="Unit director",
            is_active=True,
        )
        self.admin_user = User.objects.create_user(username="staff:appinactiveadmin", password="AdminPass123")
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

    def test_application_is_active_defaults_true(self):
        self.assertTrue(self.both_before.is_active)
        self.assertTrue(EnrollmentApplication.objects.get(pk=self.both_after.pk).is_active)

    def test_inactivate_before_care_only_hides_from_before_sheets(self):
        self.both_before.is_active = False
        self.both_before.save(update_fields=["is_active"])
        self.both.refresh_from_db()
        self.assertTrue(self.both.is_active)

        after = weekly_attendance_report_data(
            self.unit, self.program, self.today, filters={"care": "after"}
        )
        before = weekly_attendance_report_data(
            self.unit, self.program, self.today, filters={"care": "before"}
        )
        all_kids = weekly_attendance_report_data(self.unit, self.program, self.today)
        self.assertIn("Sam Jacobs", self._names(after))
        self.assertNotIn("Sam Jacobs", self._names(before))
        self.assertIn("Sam Jacobs", self._names(all_kids))
        self.assertIn("Maya Jacobs", self._names(before))

        roster = [row["child"] for row in before_care_roster_rows(unit=self.unit)]
        self.assertEqual(roster, ["Maya Jacobs"])
        self.assertNotIn("Sam Jacobs", roster)

        signout_before = signout_blank_context(
            self.today, live=True, unit=self.unit, program_obj=self.program, care="before"
        )
        signout_after = signout_blank_context(
            self.today, live=True, unit=self.unit, program_obj=self.program, care="after"
        )
        self.assertNotIn("Sam Jacobs", [row["child"] for row in signout_before["enrolled_rows"]])
        self.assertIn("Sam Jacobs", [row["child"] for row in signout_after["enrolled_rows"]])

    def test_inactivate_after_care_only_hides_from_after_sheets(self):
        self.both_after.is_active = False
        self.both_after.save(update_fields=["is_active"])

        after = weekly_attendance_report_data(
            self.unit, self.program, self.today, filters={"care": "after"}
        )
        before = weekly_attendance_report_data(
            self.unit, self.program, self.today, filters={"care": "before"}
        )
        self.assertNotIn("Sam Jacobs", self._names(after))
        self.assertIn("Sam Jacobs", self._names(before))
        roster = [row["child"] for row in before_care_roster_rows(unit=self.unit)]
        self.assertIn("Sam Jacobs", roster)

    def test_both_programs_inactive_hides_from_all_filters(self):
        self.both_after.is_active = False
        self.both_after.save(update_fields=["is_active"])
        self.both_before.is_active = False
        self.both_before.save(update_fields=["is_active"])

        for care in ("", "after", "before"):
            payload = weekly_attendance_report_data(
                self.unit, self.program, self.today, filters={"care": care} if care else None
            )
            self.assertNotIn("Sam Jacobs", self._names(payload), care or "all")

        self.assertNotIn("Sam Jacobs", [row["child"] for row in before_care_roster_rows(unit=self.unit)])

    def test_inactive_before_only_child_does_not_fall_through_to_after_care(self):
        self.before_app.is_active = False
        self.before_app.save(update_fields=["is_active"])

        after = weekly_attendance_report_data(
            self.unit, self.program, self.today, filters={"care": "after"}
        )
        before = weekly_attendance_report_data(
            self.unit, self.program, self.today, filters={"care": "before"}
        )
        all_kids = weekly_attendance_report_data(self.unit, self.program, self.today)
        self.assertNotIn("Maya Jacobs", self._names(after))
        self.assertNotIn("Maya Jacobs", self._names(before))
        self.assertNotIn("Maya Jacobs", self._names(all_kids))
        self.assertIn("Jordan Jacobs", self._names(all_kids))

    def test_child_level_inactive_still_hides_everywhere(self):
        self.both.is_active = False
        self.both.save(update_fields=["is_active"])
        for care in ("", "after", "before"):
            payload = weekly_attendance_report_data(
                self.unit, self.program, self.today, filters={"care": care} if care else None
            )
            self.assertNotIn("Sam Jacobs", self._names(payload))
        self.assertNotIn("Sam Jacobs", [row["child"] for row in before_care_roster_rows(unit=self.unit)])

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_staff_can_toggle_one_application_from_profile(self):
        self._login(self.staff_user, "staff")
        profile = self.client.get(reverse("portal_staff_family_detail", kwargs={"family_slug": "jacobs"}))
        self.assertEqual(profile.status_code, 200)
        self.assertContains(profile, "Make this before-care application inactive")
        self.assertContains(profile, "Make this after-care application inactive")
        self.assertContains(profile, "Whole child")

        url = reverse("portal_staff_application_status", kwargs={"app_slug": str(self.both_before.reference)})
        response = self.client.post(
            url,
            {
                "active": "0",
                "next": reverse("portal_staff_family_detail", kwargs={"family_slug": "jacobs"}),
            },
        )
        self.assertEqual(response.status_code, 302)
        self.both_before.refresh_from_db()
        self.both.refresh_from_db()
        self.assertFalse(self.both_before.is_active)
        self.assertTrue(self.both.is_active)
        self.assertTrue(EnrollmentApplication.objects.get(pk=self.both_after.pk).is_active)

        weekly_before = self.client.get(
            reverse("portal_staff_weekly_attendance_report"),
            {"date": self.today.isoformat(), "care": "before"},
        )
        self.assertNotContains(weekly_before, "Sam Jacobs")
        self.assertContains(weekly_before, "Maya Jacobs")
        weekly_after = self.client.get(
            reverse("portal_staff_weekly_attendance_report"),
            {"date": self.today.isoformat(), "care": "after"},
        )
        self.assertContains(weekly_after, "Sam Jacobs")

        restore = self.client.post(
            url,
            {
                "active": "1",
                "next": reverse("portal_staff_family_detail", kwargs={"family_slug": "jacobs"}),
            },
        )
        self.assertEqual(restore.status_code, 302)
        self.both_before.refresh_from_db()
        self.assertTrue(self.both_before.is_active)

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_weekly_parent_contact_checkbox_and_phone_format(self):
        self._login(self.staff_user, "staff")
        default = self.client.get(
            reverse("portal_staff_weekly_attendance_report"), {"date": self.today.isoformat()}
        )
        self.assertContains(default, 'name="parent_contact"')
        self.assertContains(default, "Show primary parent contact")
        self.assertNotContains(default, "(201) 456-5698")
        self.assertNotContains(default, "pat@example.com")

        shown = self.client.get(
            reverse("portal_staff_weekly_attendance_report"),
            {"date": self.today.isoformat(), "parent_contact": "1"},
        )
        self.assertContains(shown, "(201) 456-5698")
        self.assertContains(shown, "Pat Jacobs")
        self.assertContains(shown, "pat@example.com")
        self.assertContains(shown, 'name="parent_contact"')
        self.assertContains(shown, "checked")

        payload = weekly_attendance_report_data(
            self.unit, self.program, self.today, filters={"parent_contact": "1"}
        )
        jordan = next(row for row in payload["weekly_rows"] if row["child"] == "Jordan Jacobs")
        self.assertEqual(jordan["parent_phone"], "(201) 456-5698")
        self.assertEqual(jordan["parent_email"], "pat@example.com")
        self.assertTrue(payload["show_parent_contact"])

        csv_page = self.client.get(
            reverse("portal_staff_weekly_attendance_report"),
            {"date": self.today.isoformat(), "parent_contact": "1", "format": "csv"},
        )
        body = csv_page.content.decode()
        self.assertIn("Parent phone", body)
        self.assertIn("(201) 456-5698", body)

    def test_family_profile_lists_each_application(self):
        profile = family_profile_live("jacobs", unit=self.unit, family_id=self.family.pk)
        sam = next(child for child in profile["children"] if child["name"] == "Sam Jacobs")
        labels = {app["program_short"] for app in sam["applications"]}
        self.assertEqual(labels, {"after-care", "before-care"})
        self.assertTrue(all(app["is_active"] for app in sam["applications"]))
        self.assertEqual(profile["primary"]["phone"], "(201) 456-5698")
