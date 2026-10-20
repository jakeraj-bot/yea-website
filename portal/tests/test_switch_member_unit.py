from datetime import date, time
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from portal.admin_reports import billing_plan_rows
from portal.admin_services import get_admin_families_live
from portal.attendance_service import build_roster, families_for_staff
from portal.member_admin import switch_child_unit
from portal.models import (
    AttendanceRecord,
    PortalActivityEvent,
    PortalChild,
    PortalFamily,
    PortalLedgerEntry,
    PortalProgram,
    PortalStaffAccount,
    PortalUnit,
)
from portal.staff_auth import can_switch_member_unit
from portal.staff_services import get_program_roster
from portal.tests.test_family_units import _make_application, _staff_login
from portal.unit_visibility import families_qs_for_unit, family_visible_to_unit


def _named_application(family, child, *, location="school_18", status="approved"):
    parts = child.name.split(None, 1)
    app = _make_application(family, location=location, status=status)
    app.student_first_name = parts[0]
    app.student_last_name = parts[1] if len(parts) > 1 else family.name
    app.student_school = child.school or "Lincoln Elementary"
    app.save(update_fields=["student_first_name", "student_last_name", "student_school"])
    return app


@override_settings(PORTAL_PREVIEW_MODE=False)
class SwitchMemberUnitTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.school_18 = PortalUnit.objects.create(
            slug="school-18", name="School 18", program_type="after_school", is_active=True
        )
        self.school_26 = PortalUnit.objects.create(
            slug="school-26", name="School 26", program_type="after_school", is_active=True
        )
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
        self.family = PortalFamily.objects.create(
            unit=self.school_18,
            slug="chen",
            name="Chen",
            primary_contact="Pat Chen",
            status="Active",
        )
        self.child = PortalChild.objects.create(
            family=self.family,
            name="Ada Chen",
            school="Lincoln Elementary",
            is_active=True,
            unit=self.school_18,
        )
        self.app = _named_application(self.family, self.child, location="school_18")
        PortalLedgerEntry.objects.create(
            family=self.family,
            child_name=self.child.name,
            date="2026-09-01",
            entry_type="charge",
            description="Weekly tuition",
            amount=Decimal("35.00"),
        )
        AttendanceRecord.objects.create(
            child=self.child,
            program=self.program_18,
            date=date(2026, 9, 8),
            status=AttendanceRecord.STATUS_PRESENT,
        )
        self.admin = User.objects.create_user(username="staff:portaladmin", password="AdminPass123")
        self.admin_account = PortalStaffAccount.objects.create(
            user=self.admin,
            unit=self.school_18,
            display_name="Portal Admin",
            role="Portal admin",
            all_units_access=True,
            is_active=True,
        )
        self.pd = User.objects.create_user(username="staff:pduser", password="StaffPass123")
        self.pd_account = PortalStaffAccount.objects.create(
            user=self.pd,
            unit=self.school_18,
            display_name="Program Director",
            role="Program director",
            can_approve_applications=True,
            is_active=True,
        )
        self.desk = User.objects.create_user(username="staff:frontdesk", password="StaffPass123")
        self.desk_account = PortalStaffAccount.objects.create(
            user=self.desk,
            unit=self.school_18,
            display_name="Front Desk",
            role="Front desk staff",
            can_approve_applications=True,
            is_active=True,
        )
        self.unit_staff = User.objects.create_user(username="staff:unitstaff", password="StaffPass123")
        self.unit_staff_account = PortalStaffAccount.objects.create(
            user=self.unit_staff,
            unit=self.school_18,
            display_name="Unit Staff",
            role="Unit staff",
            is_active=True,
        )

    def _child_names(self, rows):
        return [row["child_name"] for row in rows if row.get("slug") == self.family.slug]

    def test_permission_helper_matches_enrollment_edit(self):
        self.assertTrue(can_switch_member_unit(self.admin_account, "admin"))
        self.assertTrue(can_switch_member_unit(self.admin_account, "staff"))
        self.assertTrue(can_switch_member_unit(self.pd_account, "staff"))
        self.assertFalse(can_switch_member_unit(self.desk_account, "staff"))
        self.assertFalse(can_switch_member_unit(self.unit_staff_account, "staff"))

    def test_switch_only_child_moves_unit_application_and_family(self):
        child_count = PortalChild.objects.count()
        family_count = PortalFamily.objects.count()
        result = switch_child_unit(self.child, self.school_26)

        self.assertTrue(result["changed"])
        self.assertTrue(result["family_moved"])
        self.assertEqual(PortalChild.objects.count(), child_count)
        self.assertEqual(PortalFamily.objects.count(), family_count)
        self.child.refresh_from_db()
        self.family.refresh_from_db()
        self.app.refresh_from_db()
        self.assertEqual(self.child.pk, result["child"].pk)
        self.assertEqual(self.child.unit_id, self.school_26.pk)
        self.assertEqual(self.family.unit_id, self.school_26.pk)
        self.assertEqual(self.app.program_location, "school_26")
        self.assertEqual(self.child.school, "Lincoln Elementary")
        self.assertEqual(AttendanceRecord.objects.filter(child=self.child, program=self.program_18).count(), 1)
        self.assertTrue(
            PortalLedgerEntry.objects.filter(family=self.family, child_name=self.child.name).exists()
        )

        self.assertEqual(self._child_names(families_for_staff(self.school_26)), ["Ada Chen"])
        self.assertEqual(self._child_names(families_for_staff(self.school_18)), [])
        self.assertTrue(family_visible_to_unit(self.family, self.school_26))
        self.assertFalse(family_visible_to_unit(self.family, self.school_18))
        self.assertIn(self.family, families_qs_for_unit(self.school_26))
        self.assertNotIn(self.family, families_qs_for_unit(self.school_18))

        roster_26 = build_roster(self.school_26, self.program_26, date(2026, 9, 15))
        roster_18 = build_roster(self.school_18, self.program_18, date(2026, 9, 15))
        self.assertEqual({row["child"] for row in roster_26}, {"Ada Chen"})
        self.assertNotIn("Ada Chen", {row["child"] for row in roster_18})
        self.assertEqual({row["child"] for row in get_program_roster(self.school_26)}, {"Ada Chen"})
        self.assertNotIn("Ada Chen", {row["child"] for row in get_program_roster(self.school_18)})

        admin_rows = [row for row in get_admin_families_live() if row["slug"] == "chen"]
        self.assertEqual({row["child_name"] for row in admin_rows}, {"Ada Chen"})
        self.assertEqual(admin_rows[0]["unit"], "School 26")
        plan_26 = billing_plan_rows({"unit": "school-26"})
        plan_18 = billing_plan_rows({"unit": "school-18"})
        self.assertIn("Ada Chen", {row["child"] for row in plan_26["rows"]})
        self.assertNotIn("Ada Chen", {row["child"] for row in plan_18["rows"]})

    def test_mixed_siblings_keep_family_visible_to_both_units(self):
        sibling = PortalChild.objects.create(
            family=self.family,
            name="Ben Chen",
            school="Lincoln Elementary",
            is_active=True,
            unit=self.school_18,
        )
        _named_application(self.family, sibling, location="school_18")
        result = switch_child_unit(self.child, self.school_26)

        self.assertTrue(result["changed"])
        self.assertFalse(result["family_moved"])
        self.family.refresh_from_db()
        self.child.refresh_from_db()
        sibling.refresh_from_db()
        self.assertEqual(self.family.unit_id, self.school_18.pk)
        self.assertEqual(self.child.unit_id, self.school_26.pk)
        self.assertEqual(sibling.unit_id, self.school_18.pk)
        self.assertEqual(PortalChild.objects.filter(family=self.family).count(), 2)
        self.assertTrue(family_visible_to_unit(self.family, self.school_18))
        self.assertTrue(family_visible_to_unit(self.family, self.school_26))
        self.assertEqual(self._child_names(families_for_staff(self.school_18)), ["Ben Chen"])
        self.assertEqual(self._child_names(families_for_staff(self.school_26)), ["Ada Chen"])
        self.assertNotIn("Ada Chen", self._child_names(families_for_staff(self.school_18)))
        self.assertNotIn("Ben Chen", self._child_names(families_for_staff(self.school_26)))

    def test_admin_post_switches_unit_and_logs_activity(self):
        _staff_login(self.client, self.admin, "admin")
        child_count = PortalChild.objects.count()
        url = reverse("portal_admin_family_child_unit", kwargs={"family_slug": "chen"})
        response = self.client.post(
            url,
            {
                "family_id": self.family.pk,
                "child_id": self.child.pk,
                "unit_slug": "school-26",
                "next": reverse("portal_admin_family_detail", kwargs={"family_slug": "chen"}),
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(PortalChild.objects.count(), child_count)
        self.child.refresh_from_db()
        self.family.refresh_from_db()
        self.app.refresh_from_db()
        self.assertEqual(self.child.unit_id, self.school_26.pk)
        self.assertEqual(self.family.unit_id, self.school_26.pk)
        self.assertEqual(self.app.program_location, "school_26")
        event = PortalActivityEvent.objects.get(action_label="Changed child unit", object_label="Ada Chen")
        self.assertIn("School 18", event.details)
        self.assertIn("School 26", event.details)

        page = self.client.get(reverse("portal_admin_family_detail", kwargs={"family_slug": "chen"}))
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, "Program site")
        self.assertContains(page, 'name="unit_slug"')
        self.assertContains(page, reverse("portal_admin_family_child_unit", kwargs={"family_slug": "chen"}))
        self.assertContains(page, 'value="school-26"')
        self.assertContains(page, "Ada Chen now attends School 26")

    def test_program_director_can_post_from_staff_portal(self):
        _staff_login(self.client, self.pd, "staff")
        session = self.client.session
        session["staff_unit_slug"] = "school-18"
        session.save()
        url = reverse("portal_staff_family_child_unit", kwargs={"family_slug": "chen"})
        response = self.client.post(
            url,
            {
                "family_id": self.family.pk,
                "child_id": self.child.pk,
                "unit_slug": "school-26",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.child.refresh_from_db()
        self.assertEqual(self.child.unit_id, self.school_26.pk)

    def test_front_desk_cannot_switch_unit(self):
        _staff_login(self.client, self.desk, "staff")
        session = self.client.session
        session["staff_unit_slug"] = "school-18"
        session.save()
        page = self.client.get(reverse("portal_staff_family_detail", kwargs={"family_slug": "chen"}))
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, "Program status")
        self.assertNotContains(page, reverse("portal_staff_family_child_unit", kwargs={"family_slug": "chen"}))
        response = self.client.post(
            reverse("portal_staff_family_child_unit", kwargs={"family_slug": "chen"}),
            {
                "family_id": self.family.pk,
                "child_id": self.child.pk,
                "unit_slug": "school-26",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.child.refresh_from_db()
        self.assertEqual(self.child.unit_id, self.school_18.pk)

    def test_profile_shows_unit_switch_control_for_admin(self):
        _staff_login(self.client, self.admin, "admin")
        page = self.client.get(reverse("portal_admin_family_detail", kwargs={"family_slug": "chen"}))
        self.assertEqual(page.status_code, 200)
        html = page.content.decode()
        self.assertIn('name="unit_slug"', html)
        self.assertIn('value="school-18"', html)
        self.assertIn('value="school-26"', html)
        self.assertIn("portal-child-unit-form", html)
        self.assertIn("stay on this family account", html)
