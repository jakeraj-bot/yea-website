from datetime import time

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from portal.attendance_grade_report import attendance_grade_report_bundle
from portal.models import (
    AttendanceRecord,
    PortalChild,
    PortalFamily,
    PortalProgram,
    PortalStaffAccount,
    PortalUnit,
)
from portal.staff_auth import PORTAL_AUTH_SESSION_KEY


class AttendanceGradeReportTests(TestCase):
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
        self.staff_user = User.objects.create_user(username="staff:grade", password="StaffPass123!")
        PortalStaffAccount.objects.create(
            user=self.staff_user,
            unit=self.school_18,
            display_name="Grade Staff",
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

    def test_filters_by_grade_status_and_unit(self):
        staff = attendance_grade_report_bundle({"date": self.today.isoformat()}, unit=self.school_18, admin=False)
        names = {row["child"] for row in staff["report_rows"]}
        self.assertEqual(names, {"Jordan Jacobs", "Maya Jacobs"})
        self.assertNotIn("Nia Lee", names)
        grades = [group["grade"] for group in staff["grade_groups"]]
        self.assertEqual(grades, ["2nd", "4th"])

        fourth = attendance_grade_report_bundle(
            {"date": self.today.isoformat(), "grade": "4th"},
            unit=self.school_18,
            admin=False,
        )
        self.assertEqual([row["child"] for row in fourth["report_rows"]], ["Jordan Jacobs"])

        present = attendance_grade_report_bundle(
            {"date": self.today.isoformat(), "status": "Present"},
            unit=self.school_18,
            admin=False,
        )
        self.assertEqual([row["child"] for row in present["report_rows"]], ["Jordan Jacobs"])

        admin = attendance_grade_report_bundle({"date": self.today.isoformat(), "unit": "school-26"}, admin=True)
        self.assertEqual([row["child"] for row in admin["report_rows"]], ["Nia Lee"])

        searched = attendance_grade_report_bundle(
            {"date": self.today.isoformat(), "q": "maya"},
            unit=self.school_18,
            admin=False,
        )
        self.assertEqual([row["child"] for row in searched["report_rows"]], ["Maya Jacobs"])

        week = attendance_grade_report_bundle(
            {"date": self.today.isoformat(), "range": "week"},
            unit=self.school_18,
            admin=False,
        )
        self.assertEqual(week["range_mode"], "week")
        self.assertEqual(len(week["week_days"]), 5)
        jordan = next(row for row in week["report_rows"] if row["child"] == "Jordan Jacobs")
        self.assertEqual(len(jordan["days"]), 5)

        split_family = PortalFamily.objects.create(unit=self.school_18, slug="brooks", name="Brooks")
        other_unit_child = PortalChild.objects.create(
            family=split_family,
            unit=self.school_26,
            name="Miles Brooks",
            grade="3rd",
            school="Riverside School",
            is_active=True,
        )
        AttendanceRecord.objects.create(
            child=other_unit_child,
            program=self.program_26,
            date=self.today,
            status=AttendanceRecord.STATUS_PRESENT,
        )
        staff_split = attendance_grade_report_bundle({"date": self.today.isoformat()}, unit=self.school_18, admin=False)
        self.assertNotIn("Miles Brooks", {row["child"] for row in staff_split["report_rows"]})
        other_unit = attendance_grade_report_bundle({"date": self.today.isoformat()}, unit=self.school_26, admin=False)
        self.assertIn("Miles Brooks", {row["child"] for row in other_unit["report_rows"]})
        admin_all = attendance_grade_report_bundle({"date": self.today.isoformat()}, admin=True)
        self.assertIn("Miles Brooks", {row["child"] for row in admin_all["report_rows"]})
        self.assertIn("Jordan Jacobs", {row["child"] for row in admin_all["report_rows"]})

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_staff_and_admin_pages_render(self):
        self._login(self.staff_user, "staff")
        staff = self.client.get(
            reverse("portal_staff_attendance_grade_report"),
            {"date": self.today.isoformat(), "grade": "4th"},
        )
        self.assertEqual(staff.status_code, 200)
        self.assertContains(staff, "Attendance by grade")
        self.assertContains(staff, "How to print attendance by grade")
        self.assertContains(staff, "Jordan Jacobs")
        self.assertNotContains(staff, "Maya Jacobs")
        self.assertNotContains(staff, "Nia Lee")
        self.assertContains(staff, "landscape")
        self.assertContains(staff, "portal-attendance-grade-sheet portal-collapse-skip")

        self._login(self.admin_user, "admin")
        hub = self.client.get(reverse("portal_admin_page", kwargs={"page": "reports"}))
        self.assertContains(hub, reverse("portal_admin_attendance_grade_report"))
        admin = self.client.get(reverse("portal_admin_attendance_grade_report"), {"unit": "school-26"})
        self.assertEqual(admin.status_code, 200)
        self.assertContains(admin, "Nia Lee")
        self.assertNotContains(admin, "Jordan Jacobs")
        self.assertContains(admin, "All units")
        self.assertContains(admin, "portal-collapse-skip")
        self.assertContains(admin, "landscape")

        csv_page = self.client.get(
            reverse("portal_admin_attendance_grade_report"),
            {"unit": "school-26", "format": "csv"},
        )
        self.assertEqual(csv_page.status_code, 200)
        self.assertIn("text/csv", csv_page["Content-Type"])
        self.assertIn("Nia Lee", csv_page.content.decode())
        self.assertNotIn("Jordan Jacobs", csv_page.content.decode())
