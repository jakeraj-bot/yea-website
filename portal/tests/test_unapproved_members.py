from datetime import date, time, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from enrollment.portal_integration import applications_for_admin, waitlist_for_admin
from portal.admin_reports import balance_report_rows, build_admin_report, inactive_children_report_rows
from portal.admin_services import get_admin_families_live
from portal.attendance_service import families_for_staff
from portal.member_report import member_information_rows
from portal.models import (
    PortalFamily,
    PortalLedgerEntry,
    PortalProgram,
    PortalStaffAccount,
    PortalUnit,
)
from portal.staff_auth import PORTAL_AUTH_SESSION_KEY
from portal.staff_services import emergency_contact_report_for_unit, weekly_attendance_report_data
from portal.tests.test_family_units import _make_application, _staff_login


def _child_names(rows, slug):
    return [row["child_name"] for row in rows if row.get("slug") == slug]


def _report_names(rows, key="child"):
    return [row.get(key) for row in rows]


class UnapprovedMembersHiddenTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.unit = PortalUnit.objects.create(
            slug="school-18",
            name="School 18",
            program_type="both",
            is_active=True,
        )
        self.program = PortalProgram.objects.create(
            unit=self.unit,
            name="After-School 2026–27",
            start_time=time(15, 0),
            end_time=time(18, 0),
            is_active=True,
        )
        self.admin = User.objects.create_user(username="staff:yeaadmin", password="AdminPass123")
        PortalStaffAccount.objects.create(
            user=self.admin,
            unit=self.unit,
            display_name="Portal Admin",
            role="Portal admin",
            all_units_access=True,
            is_active=True,
        )
        self.staff = User.objects.create_user(username="staff:unit18", password="StaffPass123")
        PortalStaffAccount.objects.create(
            user=self.staff,
            unit=self.unit,
            display_name="School 18 Staff",
            role="Unit director",
            is_active=True,
        )

    def _pending_family(self, slug, last, first="Nia", status="under_review", with_child=False):
        family = PortalFamily.objects.create(
            unit=self.unit,
            slug=slug,
            name=last,
            status="Pending enrollment",
        )
        app = _make_application(family, status=status)
        app.student_first_name = first
        app.student_last_name = last
        app.save(update_fields=["student_first_name", "student_last_name"])
        child = None
        if with_child:
            child = family.children.create(
                name=f"{first} {last}",
                school="School 18",
                unit=self.unit,
                is_active=True,
            )
        return family, app, child

    def _approved_child(self, family, first, last=None):
        last = last or family.name
        child = family.children.create(
            name=f"{first} {last}",
            school="School 18",
            unit=self.unit,
            is_active=True,
        )
        app = _make_application(family, status="approved")
        app.student_first_name = first
        app.student_last_name = last
        app.save(update_fields=["student_first_name", "student_last_name"])
        return child, app

    def test_pending_only_family_is_absent_from_family_list(self):
        family, app, _child = self._pending_family("pending-only", "Pendingonly")
        admin_rows = get_admin_families_live()
        staff_rows = families_for_staff(self.unit)
        self.assertEqual(_child_names(admin_rows, "pending-only"), [])
        self.assertEqual(_child_names(staff_rows, "pending-only"), [])
        self.assertNotIn("pending-only", {row["slug"] for row in admin_rows})
        self.assertNotIn("pending-only", {row["slug"] for row in staff_rows})
        self.assertTrue(any(item["child"] == "Nia Pendingonly" for item in applications_for_admin()))
        self.assertEqual(app.status, "under_review")
        self.assertFalse(family.children.exists())

    def test_pending_leftover_child_is_absent_from_family_list_and_reports(self):
        family, app, child = self._pending_family("leftover", "Leftover", with_child=True)
        PortalLedgerEntry.objects.create(
            family=family,
            child_name=child.name,
            date=date(2026, 9, 1),
            entry_type="charge",
            description="Pending leftover",
            amount=Decimal("40.00"),
        )
        today = timezone.localdate()
        monday = today - timedelta(days=today.weekday())

        self.assertEqual(_child_names(get_admin_families_live(), "leftover"), [])
        self.assertEqual(_child_names(families_for_staff(self.unit), "leftover"), [])

        weekly = weekly_attendance_report_data(self.unit, self.program, monday)
        self.assertNotIn(child.name, _report_names(weekly.get("weekly_rows") or []))

        outstanding = balance_report_rows({"status": "Active"})
        self.assertNotIn(child.name, _report_names(outstanding["rows"]))

        emergency = emergency_contact_report_for_unit(self.unit)
        self.assertNotIn(child.name, _report_names(emergency))

        enrollment = member_information_rows()
        self.assertNotIn(child.name, _report_names(enrollment))
        self.assertEqual(app.status, "under_review")

    def test_approved_plus_pending_sibling_shows_only_approved_child(self):
        family = PortalFamily.objects.create(unit=self.unit, slug="mixed", name="Mixed", status="Active")
        approved, _approved_app = self._approved_child(family, "Ada")
        pending = _make_application(family, status="under_review")
        pending.student_first_name = "Ben"
        pending.student_last_name = "Mixed"
        pending.save(update_fields=["student_first_name", "student_last_name"])
        family.children.create(name="Ben Mixed", school="School 18", unit=self.unit, is_active=True)

        names = _child_names(get_admin_families_live(), "mixed")
        self.assertEqual(names, ["Ada Mixed"])
        self.assertEqual(len([row for row in get_admin_families_live() if row["slug"] == "mixed"]), 1)
        self.assertTrue(any(item["child"] == "Ben Mixed" for item in applications_for_admin()))
        self.assertEqual(approved.name, "Ada Mixed")

        enrollment = {row["child"] for row in member_information_rows()}
        self.assertIn("Ada Mixed", enrollment)
        self.assertNotIn("Ben Mixed", enrollment)

    def test_same_child_approved_after_care_still_shows_while_before_care_pending(self):
        family = PortalFamily.objects.create(unit=self.unit, slug="dual", name="Dual", status="Active")
        child, after = self._approved_child(family, "Cora")
        before = _make_application(family, status="under_review")
        before.program = "before_care"
        before.student_first_name = "Cora"
        before.student_last_name = "Dual"
        before.save(update_fields=["program", "student_first_name", "student_last_name"])

        names = _child_names(get_admin_families_live(), "dual")
        self.assertEqual(names, ["Cora Dual"])
        self.assertEqual(len(names), 1)
        self.assertIn("Cora Dual", {row["child"] for row in member_information_rows()})
        self.assertTrue(any(item["child"] == "Cora Dual" for item in applications_for_admin()))
        self.assertEqual(after.status, "approved")
        self.assertEqual(before.status, "under_review")
        self.assertEqual(child.name, "Cora Dual")

    def test_waitlist_and_applications_queues_still_list_pending(self):
        _family, review, _child = self._pending_family("review-q", "Reviewq", status="under_review")
        wait_family, wait_app, _wait_child = self._pending_family(
            "wait-q", "Waitq", first="Pia", status="waitlist"
        )

        review_names = {item["child"] for item in applications_for_admin()}
        wait_names = {item["child"] for item in waitlist_for_admin()}
        self.assertIn("Nia Reviewq", review_names)
        self.assertNotIn("Pia Waitq", review_names)
        self.assertIn("Pia Waitq", wait_names)
        self.assertNotIn("review-q", {row["slug"] for row in get_admin_families_live()})
        self.assertNotIn("wait-q", {row["slug"] for row in get_admin_families_live()})
        self.assertEqual(review.status, "under_review")
        self.assertEqual(wait_app.status, "waitlist")
        self.assertEqual(wait_family.slug, "wait-q")

    def test_inactive_report_still_lists_approved_inactive_child(self):
        family = PortalFamily.objects.create(unit=self.unit, slug="inactive-ok", name="Inactiveok", status="Active")
        child, _app = self._approved_child(family, "Maya")
        child.is_active = False
        child.save(update_fields=["is_active"])
        pending_family, _pending, leftover = self._pending_family(
            "inactive-pending", "Inactivepending", first="Leo", with_child=True
        )
        leftover.is_active = False
        leftover.save(update_fields=["is_active"])

        report = inactive_children_report_rows()
        names = _report_names(report["rows"])
        self.assertIn("Maya Inactiveok", names)
        self.assertNotIn("Leo Inactivepending", names)
        admin_report = build_admin_report("inactive-children")
        admin_names = _report_names(admin_report["rows"])
        self.assertIn("Maya Inactiveok", admin_names)
        self.assertNotIn("Leo Inactivepending", admin_names)
        self.assertEqual(_child_names(get_admin_families_live(inactive=True), "inactive-ok"), ["Maya Inactiveok"])
        self.assertNotIn("inactive-pending", {row["slug"] for row in get_admin_families_live(inactive=True)})
        self.assertEqual(pending_family.slug, "inactive-pending")

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_admin_pages_hide_pending_only_and_keep_queues(self):
        self._pending_family("hidden-pending", "Hiddenpending")
        listed = PortalFamily.objects.create(unit=self.unit, slug="listed", name="Listed", status="Active")
        self._approved_child(listed, "Mia")

        _staff_login(self.client, self.admin, "admin")
        families = self.client.get(reverse("portal_admin_page", kwargs={"page": "families"}))
        self.assertEqual(families.status_code, 200)
        self.assertContains(families, "Mia Listed")
        self.assertNotContains(families, "Nia Hiddenpending")
        self.assertNotContains(families, "hidden-pending")

        apps = self.client.get(reverse("portal_admin_page", kwargs={"page": "applications"}))
        self.assertContains(apps, "Nia Hiddenpending")

        waitlist = self.client.get(reverse("portal_admin_page", kwargs={"page": "waitlist"}))
        self.assertEqual(waitlist.status_code, 200)

        enrollment = self.client.get(
            reverse("portal_admin_data_report", kwargs={"report_slug": "member-information"})
        )
        self.assertEqual(enrollment.status_code, 200)
        self.assertContains(enrollment, "Mia Listed")
        self.assertNotContains(enrollment, "Nia Hiddenpending")
