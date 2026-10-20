from datetime import date, time

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from enrollment.models import EnrollmentApplication
from portal.attendance_calendar import child_attendance_month
from portal.care_program import record_attendance_session
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


def _make_app(family, child, *, program="after_school", status="approved", is_active=True):
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
        is_active=is_active,
        portal_family=family,
    )


class BeforeAfterAttendanceTests(TestCase):
    def setUp(self):
        self.unit = PortalUnit.objects.create(slug="school-18", name="School 18", is_active=True)
        self.program = PortalProgram.objects.create(
            unit=self.unit,
            name="After-School 2026–27",
            start_time=time(15, 0),
            end_time=time(18, 0),
            is_active=True,
        )
        self.family = PortalFamily.objects.create(unit=self.unit, slug="jacobs", name="Jacobs")
        self.both = PortalChild.objects.create(
            family=self.family,
            name="Sam Jacobs",
            grade="3rd",
            school="Lincoln Elementary",
            is_active=True,
        )
        self.after_only = PortalChild.objects.create(
            family=self.family,
            name="Jordan Jacobs",
            grade="4th",
            school="Lincoln Elementary",
            is_active=True,
        )
        self.before_only = PortalChild.objects.create(
            family=self.family,
            name="Maya Jacobs",
            grade="2nd",
            school="Lincoln Elementary",
            is_active=True,
        )
        _make_app(self.family, self.both, program="after_school", status="approved")
        _make_app(self.family, self.both, program="before_care", status="enrolled")
        _make_app(self.family, self.after_only, program="after_school", status="approved")
        _make_app(self.family, self.before_only, program="before_care", status="approved")
        self.today = timezone.localdate()
        User = get_user_model()
        self.staff_user = User.objects.create_user(username="staff:sessions", password="StaffPass123!")
        PortalStaffAccount.objects.create(
            user=self.staff_user,
            unit=self.unit,
            display_name="Session Staff",
            role="Unit director",
            is_active=True,
        )

    def _login(self):
        self.client.force_login(self.staff_user)
        session = self.client.session
        session[PORTAL_AUTH_SESSION_KEY] = "staff"
        session.save()

    def _mark(self, child, care, present=True, day=None):
        return self.client.post(
            reverse("portal_staff_attendance_mark"),
            {
                "child_id": str(child.pk),
                "date": (day or self.today).isoformat(),
                "care": care,
                "present": "1" if present else "0",
                "next": reverse("portal_staff_weekly_attendance_report"),
            },
        )

    def _session_rows(self, child, day=None):
        return list(AttendanceRecord.objects.filter(child=child, date=day or self.today).order_by("care"))

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_before_care_check_does_not_set_after_care_present(self):
        self._login()
        response = self._mark(self.both, "before", present=True)
        self.assertEqual(response.status_code, 302)
        rows = self._session_rows(self.both)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].care, AttendanceRecord.CARE_BEFORE)
        self.assertEqual(rows[0].status, AttendanceRecord.STATUS_PRESENT)
        self.assertEqual(record_attendance_session(rows[0]), "before")

        after_sheet = weekly_attendance_report_data(
            self.unit, self.program, self.today, filters={"care": "after"}
        )
        before_sheet = weekly_attendance_report_data(
            self.unit, self.program, self.today, filters={"care": "before"}
        )
        after_row = next(row for row in after_sheet["weekly_rows"] if row["child"] == "Sam Jacobs")
        before_row = next(row for row in before_sheet["weekly_rows"] if row["child"] == "Sam Jacobs")
        idx = min(self.today.weekday(), 4)
        self.assertFalse(after_row["days"][idx])
        self.assertTrue(before_row["days"][idx])

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_after_care_check_does_not_set_before_care_present(self):
        self._login()
        response = self._mark(self.both, "after", present=True)
        self.assertEqual(response.status_code, 302)
        rows = self._session_rows(self.both)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].care, AttendanceRecord.CARE_AFTER)
        self.assertEqual(rows[0].status, AttendanceRecord.STATUS_PRESENT)

        after_sheet = weekly_attendance_report_data(
            self.unit, self.program, self.today, filters={"care": "after"}
        )
        before_sheet = weekly_attendance_report_data(
            self.unit, self.program, self.today, filters={"care": "before"}
        )
        after_row = next(row for row in after_sheet["weekly_rows"] if row["child"] == "Sam Jacobs")
        before_row = next(row for row in before_sheet["weekly_rows"] if row["child"] == "Sam Jacobs")
        idx = min(self.today.weekday(), 4)
        self.assertTrue(after_row["days"][idx])
        self.assertFalse(before_row["days"][idx])

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_all_filter_maps_to_after_care(self):
        self._login()
        self._mark(self.both, "", present=True)
        rows = self._session_rows(self.both)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].care, AttendanceRecord.CARE_AFTER)
        all_sheet = weekly_attendance_report_data(self.unit, self.program, self.today)
        before_sheet = weekly_attendance_report_data(
            self.unit, self.program, self.today, filters={"care": "before"}
        )
        idx = min(self.today.weekday(), 4)
        all_row = next(row for row in all_sheet["weekly_rows"] if row["child"] == "Sam Jacobs")
        before_row = next(row for row in before_sheet["weekly_rows"] if row["child"] == "Sam Jacobs")
        self.assertTrue(all_row["days"][idx])
        self.assertFalse(before_row["days"][idx])

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_morning_only_calendar_shows_b_not_a(self):
        self._login()
        self._mark(self.both, "before", present=True)
        month_start = date(self.today.year, self.today.month, 1)
        calendar = child_attendance_month(self.both, month_start)
        by_iso = {day["iso"]: day for week in calendar["weeks"] for day in week["days"] if day["in_month"]}
        day = by_iso[self.today.isoformat()]
        self.assertTrue(day["sessions"]["before"]["present"])
        self.assertFalse(day["sessions"]["after"]["present"])
        self.assertEqual(day["mark"], "present")

        page = self.client.get(
            reverse("portal_staff_family_attendance", kwargs={"family_slug": "jacobs"}),
            {"child_id": self.both.pk, "month": month_start.strftime("%Y-%m"), "day": self.today.isoformat()},
        )
        self.assertContains(page, "portal-child-calendar-session")
        self.assertContains(page, "Before-care")
        html = page.content.decode()
        self.assertIn(">B</span>", html)
        self.assertIn(">A</span>", html)
        self.assertIn("is-present", html)
        self.assertIn("is-unmarked", html)

    def test_legacy_attendance_counts_as_after_care(self):
        AttendanceRecord.objects.create(
            child=self.both,
            program=self.program,
            date=self.today,
            status=AttendanceRecord.STATUS_PRESENT,
            care="",
        )
        record = AttendanceRecord.objects.get(child=self.both, date=self.today)
        self.assertEqual(record.care, "")
        self.assertEqual(record_attendance_session(record), "after")

        after_sheet = weekly_attendance_report_data(
            self.unit, self.program, self.today, filters={"care": "after"}
        )
        before_sheet = weekly_attendance_report_data(
            self.unit, self.program, self.today, filters={"care": "before"}
        )
        all_sheet = weekly_attendance_report_data(self.unit, self.program, self.today)
        idx = min(self.today.weekday(), 4)
        after_row = next(row for row in after_sheet["weekly_rows"] if row["child"] == "Sam Jacobs")
        before_row = next(row for row in before_sheet["weekly_rows"] if row["child"] == "Sam Jacobs")
        all_row = next(row for row in all_sheet["weekly_rows"] if row["child"] == "Sam Jacobs")
        self.assertTrue(after_row["days"][idx])
        self.assertTrue(all_row["days"][idx])
        self.assertFalse(before_row["days"][idx])

        month_start = date(self.today.year, self.today.month, 1)
        calendar = child_attendance_month(self.both, month_start)
        by_iso = {day["iso"]: day for week in calendar["weeks"] for day in week["days"] if day["in_month"]}
        day = by_iso[self.today.isoformat()]
        self.assertFalse(day["sessions"]["before"]["present"])
        self.assertTrue(day["sessions"]["after"]["present"])

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_weekly_sheet_html_has_one_checkbox_per_day(self):
        self._login()
        page = self.client.get(
            reverse("portal_staff_weekly_attendance_report"),
            {"date": self.today.isoformat(), "care": "before"},
        )
        self.assertEqual(page.status_code, 200)
        html = page.content.decode()
        self.assertContains(page, "Maya Jacobs")
        self.assertContains(page, "Sam Jacobs")
        self.assertNotContains(page, "Jordan Jacobs")
        self.assertIn("portal-attendance-day-check", html)
        self.assertNotIn("portal-attendance-day-check-before", html)
        self.assertNotIn("name=\"present_before\"", html)
        listed = [row for row in weekly_attendance_report_data(
            self.unit, self.program, self.today, filters={"care": "before"}
        )["weekly_rows"]]
        self.assertEqual(html.count("portal-attendance-day-check"), len(listed) * 5)
        self.assertEqual(html.count("<table"), 1)
        for row_html in html.split("portal-blank-sheet-row"):
            self.assertLessEqual(row_html.count("portal-attendance-day-check"), 5)

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_inactive_before_care_cannot_save_morning_mark(self):
        before_app = EnrollmentApplication.objects.get(
            portal_family=self.family,
            program="before_care",
            student_first_name="Sam",
            student_last_name="Jacobs",
        )
        before_app.is_active = False
        before_app.save(update_fields=["is_active"])
        self._login()
        self._mark(self.both, "before", present=True)
        self.assertFalse(AttendanceRecord.objects.filter(child=self.both, date=self.today).exists())

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_after_only_child_cannot_save_before_care_mark(self):
        self._login()
        self._mark(self.after_only, "before", present=True)
        self.assertFalse(AttendanceRecord.objects.filter(child=self.after_only, date=self.today).exists())
        self._mark(self.after_only, "after", present=True)
        row = AttendanceRecord.objects.get(child=self.after_only, date=self.today)
        self.assertEqual(row.care, AttendanceRecord.CARE_AFTER)

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_weekly_csv_labels_session(self):
        self._login()
        AttendanceRecord.objects.create(
            child=self.both,
            program=self.program,
            date=self.today,
            status=AttendanceRecord.STATUS_PRESENT,
            care=AttendanceRecord.CARE_BEFORE,
        )
        AttendanceRecord.objects.create(
            child=self.after_only,
            program=self.program,
            date=self.today,
            status=AttendanceRecord.STATUS_PRESENT,
            care=AttendanceRecord.CARE_AFTER,
        )
        before_csv = self.client.get(
            reverse("portal_staff_weekly_attendance_report"),
            {"date": self.today.isoformat(), "care": "before", "format": "csv"},
        )
        body = before_csv.content.decode()
        self.assertIn("Before-care", body)
        self.assertIn("Sam Jacobs", body)
        sam_before = next(line for line in body.splitlines() if line.startswith("Sam Jacobs,"))
        self.assertIn("Before-care", sam_before)
        after_csv = self.client.get(
            reverse("portal_staff_weekly_attendance_report"),
            {"date": self.today.isoformat(), "care": "after", "format": "csv"},
        )
        after_body = after_csv.content.decode()
        self.assertIn("After-care", after_body)
        sam_after = next(line for line in after_body.splitlines() if line.startswith("Sam Jacobs,"))
        self.assertNotIn("Before-care", sam_after)
        jordan_after = next(line for line in after_body.splitlines() if line.startswith("Jordan Jacobs,"))
        self.assertIn("After-care", jordan_after)
