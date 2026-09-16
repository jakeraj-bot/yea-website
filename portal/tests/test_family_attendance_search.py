from datetime import date, time

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from portal.attendance_calendar import (
    attendance_children_for_account,
    child_attendance_month,
    parse_calendar_month,
    pick_attendance_child,
    shift_month,
)
from portal.models import (
    AttendanceRecord,
    PortalChild,
    PortalFamily,
    PortalProgram,
    PortalStaffAccount,
    PortalUnit,
)
from portal.staff_auth import PORTAL_AUTH_SESSION_KEY


class ChildAttendanceCalendarTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.school_18 = PortalUnit.objects.create(slug="school-18", name="School 18", is_active=True)
        self.school_26 = PortalUnit.objects.create(slug="school-26", name="School 26", is_active=True)
        self.program_18 = PortalProgram.objects.create(
            unit=self.school_18,
            name="After-School 18",
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
        self.family = PortalFamily.objects.create(unit=self.school_18, slug="rivera", name="Rivera")
        self.child_a = PortalChild.objects.create(
            family=self.family, name="Child A Rivera", unit=self.school_18, is_active=True
        )
        self.child_b = PortalChild.objects.create(
            family=self.family, name="Child B Rivera", unit=self.school_26, is_active=True
        )
        self.other = PortalFamily.objects.create(unit=self.school_18, slug="martinez", name="Martinez")
        self.sofia = PortalChild.objects.create(
            family=self.other, name="Sofia Martinez", unit=self.school_18, is_active=True
        )
        self.present_day = date(2026, 9, 8)
        self.absent_day = date(2026, 9, 9)
        AttendanceRecord.objects.create(
            child=self.child_a,
            program=self.program_18,
            date=self.present_day,
            status=AttendanceRecord.STATUS_PRESENT,
            check_in_time=time(15, 12),
            check_out_time=time(17, 40),
            method="Staff",
            note="Late bus",
        )
        AttendanceRecord.objects.create(
            child=self.child_a,
            program=self.program_18,
            date=self.absent_day,
            status=AttendanceRecord.STATUS_ABSENT,
            note="Sick",
        )
        AttendanceRecord.objects.create(
            child=self.child_b,
            program=self.program_26,
            date=self.present_day,
            status=AttendanceRecord.STATUS_PRESENT,
            check_in_time=time(15, 5),
            method="Staff",
        )
        self.admin = User.objects.create_user(username="staff:yeaadmin", password="AdminPass123")
        PortalStaffAccount.objects.create(
            user=self.admin,
            unit=self.school_18,
            display_name="Portal Admin",
            role="Portal admin",
            all_units_access=True,
            is_active=True,
        )
        self.staff = User.objects.create_user(username="staff:unit18", password="StaffPass123")
        PortalStaffAccount.objects.create(
            user=self.staff,
            unit=self.school_18,
            display_name="School 18 Staff",
            role="Unit director",
            all_units_access=False,
            is_active=True,
        )

    def _login(self, user, area):
        self.client.force_login(user)
        session = self.client.session
        session[PORTAL_AUTH_SESSION_KEY] = area
        if area == "staff":
            session["staff_unit_slug"] = "school-18"
        session.save()

    def test_month_helper_marks_present_absent_and_leaves_other_days_unmarked(self):
        calendar = child_attendance_month(self.child_a, date(2026, 9, 1))
        self.assertEqual(calendar["month_value"], "2026-09")
        self.assertIn("September", calendar["month_label"])
        by_iso = {day["iso"]: day for week in calendar["weeks"] for day in week if day["in_month"]}
        self.assertEqual(by_iso["2026-09-08"]["mark"], "present")
        self.assertEqual(by_iso["2026-09-09"]["mark"], "absent")
        self.assertEqual(by_iso["2026-09-10"]["mark"], "unmarked")
        self.assertFalse(by_iso["2026-09-10"]["has_record"])
        self.assertEqual(parse_calendar_month("2026-08"), date(2026, 8, 1))
        self.assertEqual(shift_month(date(2026, 9, 1), -1), date(2026, 8, 1))

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_admin_attendance_tab_shows_month_and_present_absent(self):
        self._login(self.admin, "admin")
        page = self.client.get(
            reverse("portal_admin_family_attendance", kwargs={"family_slug": "rivera"}),
            {"id": self.family.pk, "child_id": self.child_a.pk, "child": "Child A Rivera", "month": "2026-09"},
        )
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, "Attendance")
        self.assertContains(page, "September 2026")
        self.assertContains(page, "Previous month")
        self.assertContains(page, "Next month")
        self.assertContains(page, "Child A Rivera")
        self.assertContains(page, "is-present")
        self.assertContains(page, "is-absent")
        self.assertContains(page, "is-unmarked")
        self.assertContains(page, "Present")
        self.assertContains(page, "Absent")
        self.assertContains(page, "Not marked")
        self.assertContains(page, "day=2026-09-08")
        self.assertNotContains(page, "Child B Rivera — Attendance")
        sibling = self.client.get(
            reverse("portal_admin_family_attendance", kwargs={"family_slug": "rivera"}),
            {"id": self.family.pk, "child_id": self.child_b.pk, "child": "Child B Rivera", "month": "2026-09"},
        )
        self.assertEqual(sibling.status_code, 200)
        self.assertContains(sibling, "Child B Rivera — Attendance")
        self.assertContains(sibling, "is-present")

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_admin_day_click_shows_review_attendance_details(self):
        self._login(self.admin, "admin")
        page = self.client.get(
            reverse("portal_admin_family_attendance", kwargs={"family_slug": "rivera"}),
            {
                "id": self.family.pk,
                "child_id": self.child_a.pk,
                "child": "Child A Rivera",
                "month": "2026-09",
                "day": "2026-09-08",
            },
        )
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, "attendance-day-detail")
        self.assertContains(page, "3:12 PM")
        self.assertContains(page, "5:40 PM")
        self.assertContains(page, "Staff")
        self.assertContains(page, "Late bus")
        unmarked = self.client.get(
            reverse("portal_admin_family_attendance", kwargs={"family_slug": "rivera"}),
            {
                "id": self.family.pk,
                "child_id": self.child_a.pk,
                "month": "2026-09",
                "day": "2026-09-10",
            },
        )
        self.assertContains(unmarked, "Not marked — no attendance is saved for this day.")

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_month_prev_next_stay_on_this_child(self):
        self._login(self.admin, "admin")
        page = self.client.get(
            reverse("portal_admin_family_attendance", kwargs={"family_slug": "rivera"}),
            {"id": self.family.pk, "child_id": self.child_a.pk, "month": "2026-09"},
        )
        self.assertContains(page, "month=2026-08")
        self.assertContains(page, "month=2026-10")
        august = self.client.get(
            reverse("portal_admin_family_attendance", kwargs={"family_slug": "rivera"}),
            {"id": self.family.pk, "child_id": self.child_a.pk, "month": "2026-08"},
        )
        self.assertEqual(august.status_code, 200)
        self.assertContains(august, "August 2026")
        self.assertNotContains(august, "3:12 PM")

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_staff_attendance_is_scoped_to_unit_child(self):
        self._login(self.staff, "staff")
        own = self.client.get(
            reverse("portal_staff_family_attendance", kwargs={"family_slug": "rivera"}),
            {"child_id": self.child_a.pk, "child": "Child A Rivera", "month": "2026-09"},
        )
        self.assertEqual(own.status_code, 200)
        self.assertContains(own, "Child A Rivera")
        self.assertContains(own, "is-present")
        self.assertNotContains(own, "portal-attendance-child-switcher")
        self.assertNotContains(own, "Child B Rivera")
        other = self.client.get(
            reverse("portal_staff_family_attendance", kwargs={"family_slug": "rivera"}),
            {"child_id": self.child_b.pk, "child": "Child B Rivera", "month": "2026-09"},
        )
        self.assertEqual(other.status_code, 404)
        default = self.client.get(
            reverse("portal_staff_family_attendance", kwargs={"family_slug": "rivera"}),
            {"month": "2026-09"},
        )
        self.assertEqual(default.status_code, 200)
        self.assertContains(default, "Child A Rivera")
        self.assertNotContains(default, "Child B Rivera — Attendance")

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_admin_search_from_family_page_opens_another_child(self):
        self._login(self.admin, "admin")
        profile = self.client.get(
            reverse("portal_admin_family_detail", kwargs={"family_slug": "rivera"}),
            {"id": self.family.pk, "child_id": self.child_a.pk},
        )
        self.assertContains(profile, reverse("portal_admin_family_search"))
        self.assertContains(profile, "portal-family-pager")
        search = self.client.get(reverse("portal_admin_family_search"), {"q": "Sofia", "format": "json"})
        self.assertEqual(search.status_code, 200)
        payload = search.json()
        self.assertEqual(len(payload["results"]), 1)
        self.assertEqual(payload["results"][0]["child_name"], "Sofia Martinez")
        opened = self.client.get(payload["results"][0]["url"])
        self.assertEqual(opened.status_code, 200)
        self.assertContains(opened, "Sofia Martinez")
        self.assertContains(opened, "Family account")
        redirecting = self.client.get(reverse("portal_admin_family_search"), {"q": "Sofia"})
        self.assertEqual(redirecting.status_code, 302)
        self.assertIn("/family/martinez/", redirecting.url)

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_staff_search_stays_in_unit(self):
        self._login(self.staff, "staff")
        hidden = self.client.get(reverse("portal_staff_family_search"), {"q": "Child B", "format": "json"})
        self.assertEqual(hidden.status_code, 200)
        self.assertEqual(hidden.json()["results"], [])
        visible = self.client.get(reverse("portal_staff_family_search"), {"q": "Sofia", "format": "json"})
        self.assertEqual(len(visible.json()["results"]), 1)
        self.assertEqual(visible.json()["results"][0]["child_name"], "Sofia Martinez")
        opened = self.client.get(visible.json()["results"][0]["url"])
        self.assertEqual(opened.status_code, 200)
        self.assertContains(opened, "Sofia Martinez")
        self.assertContains(opened, reverse("portal_staff_family_attendance", kwargs={"family_slug": "martinez"}))

    def test_switcher_includes_inactive_with_history_and_skips_empty_inactive(self):
        family = PortalFamily.objects.create(unit=self.school_18, slug="patel", name="Patel")
        ami = PortalChild.objects.create(
            family=family, name="Ami Patel", unit=self.school_18, is_active=True
        )
        ravi = PortalChild.objects.create(
            family=family, name="Ravi Patel", unit=self.school_18, is_active=False
        )
        ghost = PortalChild.objects.create(
            family=family, name="Ghost Patel", unit=self.school_18, is_active=False
        )
        AttendanceRecord.objects.create(
            child=ravi,
            program=self.program_18,
            date=self.present_day,
            status=AttendanceRecord.STATUS_PRESENT,
        )
        names = [child.name for child in attendance_children_for_account(family, self.school_18)]
        self.assertEqual(names, ["Ami Patel", "Ravi Patel"])
        self.assertNotIn("Ghost Patel", names)
        opened = attendance_children_for_account(
            family, self.school_18, include_child_id=ghost.pk
        )
        self.assertEqual([child.name for child in opened], ["Ami Patel", "Ghost Patel", "Ravi Patel"])
        self.assertEqual(pick_attendance_child(opened).name, "Ami Patel")
        self.assertEqual(pick_attendance_child(opened, child_id=ghost.pk).name, "Ghost Patel")

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_admin_two_child_account_switches_calendars_with_child_id(self):
        self._login(self.admin, "admin")
        page = self.client.get(
            reverse("portal_admin_family_attendance", kwargs={"family_slug": "rivera"}),
            {"id": self.family.pk, "child_id": self.child_a.pk, "month": "2026-09"},
        )
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, "portal-attendance-child-switcher")
        self.assertContains(page, "Child A Rivera")
        self.assertContains(page, "Child B Rivera")
        self.assertContains(page, f"child_id={self.child_b.pk}")
        self.assertContains(page, "Child A Rivera — Attendance")
        self.assertNotContains(page, "Child B Rivera — Attendance")
        switched = self.client.get(
            reverse("portal_admin_family_attendance", kwargs={"family_slug": "rivera"}),
            {
                "id": self.family.pk,
                "child_id": self.child_b.pk,
                "child": "Child B Rivera",
                "month": "2026-09",
            },
        )
        self.assertEqual(switched.status_code, 200)
        self.assertContains(switched, "Child B Rivera — Attendance")
        self.assertNotContains(switched, "Child A Rivera — Attendance")
        self.assertContains(switched, 'aria-current="page"')
        self.assertContains(switched, f"child_id={self.child_a.pk}")

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_staff_same_unit_siblings_switch_calendars(self):
        family = PortalFamily.objects.create(unit=self.school_18, slug="nguyen", name="Nguyen")
        ami = PortalChild.objects.create(
            family=family, name="Ami Nguyen", unit=self.school_18, is_active=True
        )
        ravi = PortalChild.objects.create(
            family=family, name="Ravi Nguyen", unit=self.school_18, is_active=True
        )
        AttendanceRecord.objects.create(
            child=ami,
            program=self.program_18,
            date=self.present_day,
            status=AttendanceRecord.STATUS_PRESENT,
        )
        AttendanceRecord.objects.create(
            child=ravi,
            program=self.program_18,
            date=self.absent_day,
            status=AttendanceRecord.STATUS_ABSENT,
        )
        self._login(self.staff, "staff")
        page = self.client.get(
            reverse("portal_staff_family_attendance", kwargs={"family_slug": "nguyen"}),
            {"child_id": ami.pk, "month": "2026-09"},
        )
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, "portal-attendance-child-switcher")
        self.assertContains(page, "Ami Nguyen")
        self.assertContains(page, "Ravi Nguyen")
        self.assertContains(page, f"child_id={ravi.pk}")
        self.assertContains(page, "Ami Nguyen — Attendance")
        self.assertContains(page, "is-present")
        self.assertNotContains(page, "Ravi Nguyen — Attendance")
        switched = self.client.get(
            reverse("portal_staff_family_attendance", kwargs={"family_slug": "nguyen"}),
            {"child_id": ravi.pk, "child": "Ravi Nguyen", "month": "2026-09"},
        )
        self.assertEqual(switched.status_code, 200)
        self.assertContains(switched, "Ravi Nguyen — Attendance")
        self.assertNotContains(switched, "Ami Nguyen — Attendance")
        self.assertContains(switched, "is-absent")
        default = self.client.get(
            reverse("portal_staff_family_attendance", kwargs={"family_slug": "nguyen"}),
            {"month": "2026-09"},
        )
        self.assertContains(default, "Ami Nguyen — Attendance")
        opened = self.client.get(
            reverse("portal_staff_family_attendance", kwargs={"family_slug": "nguyen"}),
            {"child_id": ravi.pk, "month": "2026-09"},
        )
        self.assertContains(opened, "Ravi Nguyen — Attendance")

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_single_child_family_has_no_switcher_tabs(self):
        self._login(self.admin, "admin")
        page = self.client.get(
            reverse("portal_admin_family_attendance", kwargs={"family_slug": "martinez"}),
            {"id": self.other.pk, "child_id": self.sofia.pk, "month": "2026-09"},
        )
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, "Sofia Martinez — Attendance")
        self.assertNotContains(page, "portal-attendance-child-switcher")

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_inactive_sibling_with_history_is_labeled_on_switcher(self):
        family = PortalFamily.objects.create(unit=self.school_18, slug="cole", name="Cole")
        active = PortalChild.objects.create(
            family=family, name="Casey Cole", unit=self.school_18, is_active=True
        )
        inactive = PortalChild.objects.create(
            family=family, name="Ivy Cole", unit=self.school_18, is_active=False
        )
        PortalChild.objects.create(
            family=family, name="Quiet Cole", unit=self.school_18, is_active=False
        )
        AttendanceRecord.objects.create(
            child=inactive,
            program=self.program_18,
            date=self.present_day,
            status=AttendanceRecord.STATUS_PRESENT,
        )
        self._login(self.admin, "admin")
        page = self.client.get(
            reverse("portal_admin_family_attendance", kwargs={"family_slug": "cole"}),
            {"id": family.pk, "child_id": active.pk, "month": "2026-09"},
        )
        self.assertContains(page, "portal-attendance-child-switcher")
        self.assertContains(page, "Casey Cole")
        self.assertContains(page, "Ivy Cole")
        self.assertContains(page, "Inactive")
        switcher = page.content.decode().split("portal-attendance-child-switcher", 1)[1].split(
            "portal-child-calendar-card", 1
        )[0]
        self.assertIn("Ivy Cole", switcher)
        self.assertNotIn("Quiet Cole", switcher)
        history = self.client.get(
            reverse("portal_admin_family_attendance", kwargs={"family_slug": "cole"}),
            {"id": family.pk, "child_id": inactive.pk, "month": "2026-09"},
        )
        self.assertContains(history, "Ivy Cole — Attendance")
        self.assertContains(history, "is-present")
