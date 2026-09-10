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
from portal.staff_services import daily_attendance_report_data, weekly_attendance_report_data


class AttendanceSheetFilterTests(TestCase):
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
        self.jordan = PortalChild.objects.create(
            family=family_18, name="Jordan Jacobs", grade="4th", school="Lincoln Elementary", is_active=True
        )
        self.maya = PortalChild.objects.create(
            family=family_18, name="Maya Jacobs", grade="2nd", school="Lincoln Elementary", is_active=True
        )
        self.nia = PortalChild.objects.create(
            family=family_26, name="Nia Lee", grade="4th", school="Riverside School", is_active=True
        )
        self.today = timezone.localdate()
        AttendanceRecord.objects.create(
            child=self.jordan,
            program=self.program_18,
            date=self.today,
            status=AttendanceRecord.STATUS_PRESENT,
        )
        AttendanceRecord.objects.create(
            child=self.maya,
            program=self.program_18,
            date=self.today,
            status=AttendanceRecord.STATUS_ABSENT,
        )
        AttendanceRecord.objects.create(
            child=self.nia,
            program=self.program_26,
            date=self.today,
            status=AttendanceRecord.STATUS_PRESENT,
        )
        User = get_user_model()
        self.staff_user = User.objects.create_user(username="staff:sheets", password="StaffPass123!")
        PortalStaffAccount.objects.create(
            user=self.staff_user,
            unit=self.school_18,
            display_name="Sheet Staff",
            role="Unit director",
            is_active=True,
        )
        self.admin_user = User.objects.create_user(username="staff:sheetadmin", password="AdminPass123")
        PortalStaffAccount.objects.create(
            user=self.admin_user,
            unit=self.school_18,
            display_name="Portal Admin",
            role="Portal admin",
            all_units_access=True,
            is_active=True,
        )
        self.multi_staff_user = User.objects.create_user(username="staff:sheetmulti", password="StaffPass123!")
        multi_account = PortalStaffAccount.objects.create(
            user=self.multi_staff_user,
            unit=self.school_18,
            display_name="Multi Unit Staff",
            role="Unit director",
            is_active=True,
        )
        multi_account.accessible_units.set([self.school_18, self.school_26])

    def _login(self, user, area):
        self.client.force_login(user)
        session = self.client.session
        session[PORTAL_AUTH_SESSION_KEY] = area
        session.save()

    def test_blank_weekly_and_daily_use_the_same_filtered_kids(self):
        weekly = weekly_attendance_report_data(
            self.school_18, self.program_18, self.today, filters={"grades": ["4th"]}
        )
        daily = daily_attendance_report_data(
            self.school_18, self.program_18, self.today, filters={"grades": ["4th"]}
        )
        self.assertEqual([row["child"] for row in weekly["weekly_rows"]], ["Jordan Jacobs"])
        self.assertEqual([row["child"] for row in daily["daily_rows"]], ["Jordan Jacobs"])
        self.assertEqual(weekly["listed_count"], 1)
        self.assertEqual(daily["listed_count"], 1)
        self.assertEqual(daily["present_count"], 1)
        self.assertEqual(weekly["week_days"][0]["listed_count"], 1)

        both = weekly_attendance_report_data(
            self.school_18, self.program_18, self.today, filters={"grades": ["2nd", "4th"]}
        )
        names = [row["child"] for row in both["weekly_rows"]]
        self.assertEqual(names, ["Jordan Jacobs", "Maya Jacobs"])

        admin_all = daily_attendance_report_data(None, None, self.today, admin=True)
        self.assertEqual(admin_all["listed_count"], 3)
        self.assertEqual(admin_all["present_count"], 2)

        admin_26 = daily_attendance_report_data(
            None, None, self.today, filters={"unit": "school-26"}, admin=True
        )
        self.assertEqual([row["child"] for row in admin_26["daily_rows"]], ["Nia Lee"])

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_blank_weekly_daily_and_daily_blank_pages_filter_and_keep_staff_scope(self):
        self._login(self.staff_user, "staff")
        blank_week = self.client.get(
            reverse("portal_staff_attendance_blank_weekly"),
            {"date": self.today.isoformat(), "grade": ["4th"]},
        )
        self.assertEqual(blank_week.status_code, 200)
        self.assertContains(blank_week, "Jordan Jacobs")
        self.assertNotContains(blank_week, "Maya Jacobs")
        self.assertNotContains(blank_week, "Nia Lee")
        self.assertContains(blank_week, "portal-day-kid-total")
        self.assertContains(blank_week, "listed")
        self.assertContains(blank_week, "How to print a blank weekly sheet")
        self.assertContains(blank_week, "counter(page)")
        self.assertContains(blank_week, "Printed")
        self.assertContains(blank_week, "portal-print-title-row")
        self.assertNotContains(blank_week, "<th>Unit</th>")

        daily = self.client.get(
            reverse("portal_staff_attendance_report"),
            {"date": self.today.isoformat(), "grade": ["2nd", "4th"]},
        )
        self.assertContains(daily, "Jordan Jacobs")
        self.assertContains(daily, "Maya Jacobs")
        self.assertNotContains(daily, "Nia Lee")
        self.assertContains(daily, "portal-blank-sheet-meta")
        self.assertContains(daily, "How to print daily attendance")
        html = daily.content.decode()
        self.assertNotIn(">Unit</th>", html)
        self.assertIn("portal-blank-line", html)

        daily_blank = self.client.get(
            reverse("portal_staff_attendance_blank_daily"),
            {"unit": "school-26", "date": self.today.isoformat()},
        )
        self.assertContains(daily_blank, "Jordan Jacobs")
        self.assertNotContains(daily_blank, "Nia Lee")
        self.assertIn('value="school-18" selected', daily_blank.content.decode())
        self.assertContains(daily_blank, "How to print a blank daily sheet")

        self._login(self.multi_staff_user, "staff")
        other = self.client.get(
            reverse("portal_staff_attendance_blank_weekly"),
            {"unit": "school-26", "date": self.today.isoformat()},
        )
        self.assertContains(other, "Nia Lee")
        self.assertNotContains(other, "Jordan Jacobs")

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_weekly_filled_matches_blank_layout_and_print_chrome(self):
        self._login(self.staff_user, "staff")
        page = self.client.get(
            reverse("portal_staff_weekly_attendance_report"),
            {"date": self.today.isoformat()},
        )
        html = page.content.decode()
        self.assertContains(page, "Jordan Jacobs")
        self.assertContains(page, "portal-blank-sheet-meta")
        self.assertNotIn("<th>Unit</th>", html)
        self.assertNotIn("<th>Grade</th>", html)
        self.assertIn("portal-blank-line--day", html)
        self.assertNotIn(">—<", html)
        self.assertContains(page, "portal-print-title-row")
        self.assertContains(page, "counter(page)")
        self.assertContains(page, "attendance-print")
        self.assertContains(page, "Printed")
        csv_page = self.client.get(
            reverse("portal_staff_weekly_attendance_report"),
            {"date": self.today.isoformat(), "format": "csv"},
        )
        body = csv_page.content.decode()
        self.assertNotIn("—", body.split("Maya Jacobs", 1)[-1].splitlines()[0])

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_admin_can_open_all_four_sheets_with_all_units(self):
        self._login(self.admin_user, "admin")
        weekly_blank = self.client.get(reverse("portal_admin_attendance_blank_weekly"))
        self.assertEqual(weekly_blank.status_code, 200)
        self.assertContains(weekly_blank, "All units")
        self.assertContains(weekly_blank, "Nia Lee")
        self.assertContains(weekly_blank, "Jordan Jacobs")

        daily = self.client.get(reverse("portal_admin_attendance_report"), {"unit": "school-26"})
        self.assertContains(daily, "Nia Lee")
        self.assertNotContains(daily, "Jordan Jacobs")
        self.assertContains(daily, "How to print daily attendance")

        daily_blank = self.client.get(reverse("portal_admin_attendance_blank_daily"))
        self.assertContains(daily_blank, "Nia Lee")
        self.assertContains(daily_blank, "portal-day-kid-total")
        self.assertContains(daily_blank, "counter(page)")
