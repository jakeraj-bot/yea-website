from datetime import time

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
from portal.staff_services import weekly_attendance_report_data


class WeeklyAttendanceGradeFilterTests(TestCase):
    def setUp(self):
        self.school_18 = PortalUnit.objects.create(slug="school-18", name="School 18", is_active=True)
        self.school_26 = PortalUnit.objects.create(slug="school-26", name="School 26", is_active=True)
        self.program_18 = PortalProgram.objects.create(
            unit=self.school_18,
            name="After-School 2026–27",
            start_time=time(15, 0),
            end_time=time(18, 0),
            is_active=True,
        )
        self.program_26 = PortalProgram.objects.create(
            unit=self.school_26,
            name="After-School 26",
            start_time=time(15, 0),
            end_time=time(18, 0),
            is_active=True,
        )
        family_18 = PortalFamily.objects.create(unit=self.school_18, slug="jacobs", name="Jacobs")
        family_26 = PortalFamily.objects.create(unit=self.school_26, slug="lee", name="Lee")
        self.fourth = PortalChild.objects.create(
            family=family_18,
            name="Jordan Jacobs",
            grade="4th",
            school="Lincoln Elementary",
            is_active=True,
        )
        self.second = PortalChild.objects.create(
            family=family_18,
            name="Maya Jacobs",
            grade="2nd",
            school="Lincoln Elementary",
            is_active=True,
        )
        self.other = PortalChild.objects.create(
            family=family_26,
            name="Nia Lee",
            grade="4th",
            school="Riverside School",
            is_active=True,
        )
        today = timezone.localdate()
        self.today = today
        AttendanceRecord.objects.create(
            child=self.fourth,
            program=self.program_18,
            date=today,
            status=AttendanceRecord.STATUS_PRESENT,
        )
        AttendanceRecord.objects.create(
            child=self.second,
            program=self.program_18,
            date=today,
            status=AttendanceRecord.STATUS_ABSENT,
        )
        AttendanceRecord.objects.create(
            child=self.other,
            program=self.program_26,
            date=today,
            status=AttendanceRecord.STATUS_PRESENT,
        )
        User = get_user_model()
        self.staff_user = User.objects.create_user(username="staff:weekly", password="StaffPass123!")
        PortalStaffAccount.objects.create(
            user=self.staff_user,
            unit=self.school_18,
            display_name="Weekly Staff",
            role="Unit director",
            is_active=True,
        )
        self.admin_user = User.objects.create_user(username="staff:yeaadmin", password="AdminPass123")
        PortalStaffAccount.objects.create(
            user=self.admin_user,
            unit=self.school_18,
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

    def test_no_grade_filter_includes_every_unit_child(self):
        payload = weekly_attendance_report_data(self.school_18, self.program_18, self.today)
        names = [row["child"] for row in payload["weekly_rows"]]
        self.assertEqual(names, ["Jordan Jacobs", "Maya Jacobs"])
        self.assertNotIn("Nia Lee", names)
        self.assertEqual(len(payload["week_days"]), 5)
        self.assertEqual(payload["selected_grades"], [])

    def test_one_grade_keeps_only_those_kids(self):
        payload = weekly_attendance_report_data(
            self.school_18,
            self.program_18,
            self.today,
            filters={"grades": ["4th"]},
        )
        self.assertEqual([row["child"] for row in payload["weekly_rows"]], ["Jordan Jacobs"])
        self.assertEqual(payload["selected_grades"], ["4th"])

    def test_multiple_grades_stay_on_one_sheet(self):
        payload = weekly_attendance_report_data(
            self.school_18,
            self.program_18,
            self.today,
            filters={"grades": ["2nd", "4th"]},
        )
        names = [row["child"] for row in payload["weekly_rows"]]
        self.assertEqual(names, ["Jordan Jacobs", "Maya Jacobs"])
        grades = [row["grade"] for row in payload["weekly_rows"]]
        self.assertEqual(set(grades), {"2nd", "4th"})
        self.assertNotIn("grade_groups", payload)

    def test_staff_unit_scoping_includes_child_at_this_site(self):
        split_family = PortalFamily.objects.create(unit=self.school_26, slug="brooks", name="Brooks")
        visiting = PortalChild.objects.create(
            family=split_family,
            unit=self.school_18,
            name="Miles Brooks",
            grade="3rd",
            school="Lincoln Elementary",
            is_active=True,
        )
        AttendanceRecord.objects.create(
            child=visiting,
            program=self.program_18,
            date=self.today,
            status=AttendanceRecord.STATUS_PRESENT,
        )
        staff = weekly_attendance_report_data(self.school_18, self.program_18, self.today)
        names = {row["child"] for row in staff["weekly_rows"]}
        self.assertEqual(names, {"Jordan Jacobs", "Maya Jacobs", "Miles Brooks"})
        self.assertNotIn("Nia Lee", names)

        other_unit_child = PortalChild.objects.create(
            family=split_family,
            unit=self.school_26,
            name="Nora Brooks",
            grade="1st",
            school="Riverside School",
            is_active=True,
        )
        AttendanceRecord.objects.create(
            child=other_unit_child,
            program=self.program_26,
            date=self.today,
            status=AttendanceRecord.STATUS_PRESENT,
        )
        staff_again = weekly_attendance_report_data(self.school_18, self.program_18, self.today)
        self.assertNotIn("Nora Brooks", {row["child"] for row in staff_again["weekly_rows"]})
        other = weekly_attendance_report_data(self.school_26, self.program_26, self.today)
        self.assertIn("Nora Brooks", {row["child"] for row in other["weekly_rows"]})
        self.assertIn("Nia Lee", {row["child"] for row in other["weekly_rows"]})
        self.assertNotIn("Jordan Jacobs", {row["child"] for row in other["weekly_rows"]})

        admin_all = weekly_attendance_report_data(None, None, self.today, admin=True)
        admin_names = {row["child"] for row in admin_all["weekly_rows"]}
        self.assertIn("Miles Brooks", admin_names)
        self.assertIn("Jordan Jacobs", admin_names)
        self.assertIn("Nia Lee", admin_names)

        admin_26 = weekly_attendance_report_data(
            None, None, self.today, filters={"unit": "school-26"}, admin=True
        )
        self.assertEqual({row["child"] for row in admin_26["weekly_rows"]}, {"Nia Lee", "Nora Brooks"})

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_staff_page_filters_grades_together_and_keeps_howto(self):
        self._login(self.staff_user, "staff")
        page = self.client.get(
            reverse("portal_staff_weekly_attendance_report"),
            {"date": self.today.isoformat(), "grade": ["2nd", "4th"]},
        )
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, "Weekly attendance summary")
        self.assertContains(page, "How to print weekly attendance")
        self.assertContains(page, "How to use this page")
        self.assertContains(page, "Jordan Jacobs")
        self.assertContains(page, "Maya Jacobs")
        self.assertNotContains(page, "Nia Lee")
        self.assertContains(page, 'name="grade"')
        self.assertContains(page, 'type="checkbox"')
        self.assertNotContains(page, "portal-attendance-grade-heading")
        self.assertContains(page, "landscape")
        html = page.content.decode()
        self.assertLess(html.find("Jordan Jacobs"), html.find("Maya Jacobs") if "Maya Jacobs" in html else 0)
        self.assertEqual(html.count("<table"), 1)

        one_grade = self.client.get(
            reverse("portal_staff_weekly_attendance_report"),
            {"date": self.today.isoformat(), "grade": "4th"},
        )
        self.assertContains(one_grade, "Jordan Jacobs")
        self.assertNotContains(one_grade, "Maya Jacobs")

        all_grades = self.client.get(reverse("portal_staff_weekly_attendance_report"), {"date": self.today.isoformat()})
        self.assertContains(all_grades, "Jordan Jacobs")
        self.assertContains(all_grades, "Maya Jacobs")

        csv_page = self.client.get(
            reverse("portal_staff_weekly_attendance_report"),
            {"date": self.today.isoformat(), "grade": "4th", "format": "csv"},
        )
        self.assertEqual(csv_page.status_code, 200)
        self.assertIn("text/csv", csv_page["Content-Type"])
        self.assertIn("Jordan Jacobs", csv_page.content.decode())
        self.assertNotIn("Maya Jacobs", csv_page.content.decode())

        old = self.client.get(reverse("portal_staff_attendance_grade_report"), {"grade": "4th"})
        self.assertEqual(old.status_code, 302)
        self.assertIn(reverse("portal_staff_weekly_attendance_report"), old["Location"])

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_admin_page_has_unit_filter_and_replaces_grade_report(self):
        self._login(self.admin_user, "admin")
        hub = self.client.get(reverse("portal_admin_page", kwargs={"page": "reports"}))
        self.assertContains(hub, reverse("portal_admin_weekly_attendance_report"))
        self.assertNotContains(hub, "Attendance by grade")

        admin = self.client.get(
            reverse("portal_admin_weekly_attendance_report"),
            {"unit": "school-26", "date": self.today.isoformat()},
        )
        self.assertEqual(admin.status_code, 200)
        self.assertContains(admin, "Nia Lee")
        self.assertNotContains(admin, "Jordan Jacobs")
        self.assertContains(admin, "All units")
        self.assertContains(admin, "How to print weekly attendance")
        self.assertContains(admin, 'name="grade"')
        self.assertContains(admin, "landscape")

        csv_page = self.client.get(
            reverse("portal_admin_weekly_attendance_report"),
            {"unit": "school-26", "format": "csv"},
        )
        self.assertEqual(csv_page.status_code, 200)
        self.assertIn("text/csv", csv_page["Content-Type"])
        self.assertIn("Nia Lee", csv_page.content.decode())
        self.assertNotIn("Jordan Jacobs", csv_page.content.decode())

        old = self.client.get(reverse("portal_admin_attendance_grade_report"), {"unit": "school-26"})
        self.assertEqual(old.status_code, 302)
        self.assertIn(reverse("portal_admin_weekly_attendance_report"), old["Location"])
