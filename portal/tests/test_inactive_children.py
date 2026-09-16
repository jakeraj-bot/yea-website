from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from portal.admin_reports import build_admin_report
from portal.admin_services import get_admin_families_live
from portal.attendance_service import families_for_staff
from portal.billing_services import post_charge
from portal.enrollment_counts import unit_enrollment_count
from portal.family_list import phone_digits, query_matches_phones, row_matches_list_nav
from portal.models import (
    PortalChild,
    PortalFamily,
    PortalLedgerEntry,
    PortalParentAccount,
    PortalStaffAccount,
    PortalUnit,
)
from portal.parent_services import build_parent_preview_live, get_tax_eligibility_live
from portal.staff_auth import PORTAL_AUTH_SESSION_KEY
from portal.staff_services import get_program_roster
from portal.tests.test_family_units import _make_application, _staff_login


class InactiveChildrenAndPhoneSearchTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.unit = PortalUnit.objects.create(slug="school-18", name="School 18", is_active=True)
        self.other = PortalUnit.objects.create(slug="school-26", name="School 26", is_active=True)
        self.family = PortalFamily.objects.create(
            unit=self.unit,
            slug="jacobs",
            name="Jacobs",
            primary_contact="Pat Jacobs",
            status="Active",
        )
        self.jordan = PortalChild.objects.create(
            family=self.family, name="Jordan Jacobs", school="School 18", is_active=True
        )
        self.maya = PortalChild.objects.create(
            family=self.family, name="Maya Jacobs", school="School 18", is_active=True
        )
        app = _make_application(self.family)
        app.primary_phone = "(201) 456-5698"
        app.primary_phone_type = "cell"
        app.secondary_first_name = "Sam"
        app.secondary_last_name = "Jacobs"
        app.secondary_phone = "201-555-0100"
        app.secondary_phone_type = "home"
        app.student_first_name = "Jordan"
        app.student_last_name = "Jacobs"
        app.status = "approved"
        app.save()
        self.admin = User.objects.create_user(username="staff:portaladmin", password="AdminPass123")
        PortalStaffAccount.objects.create(
            user=self.admin,
            unit=self.unit,
            display_name="Portal Admin",
            role="Portal admin",
            all_units_access=True,
            is_active=True,
        )
        self.staff = User.objects.create_user(username="staff:unitstaff", password="StaffPass123")
        PortalStaffAccount.objects.create(
            user=self.staff,
            unit=self.unit,
            display_name="Unit Staff",
            role="Unit director",
            all_units_access=False,
            is_active=True,
        )
        self.parent_user = User.objects.create_user(
            username="parent:jacobs",
            password="ParentPass123",
            email="pat@example.com",
        )
        self.parent_account = PortalParentAccount.objects.create(user=self.parent_user, family=self.family)

    def _child_names(self, rows, slug):
        return [row["child_name"] for row in rows if row.get("slug") == slug]

    def test_phone_digits_normalize_punctuation(self):
        self.assertEqual(phone_digits("(201) 456-5698"), "2014565698")
        self.assertTrue(query_matches_phones("(201) 456-5698", "2014565698"))
        self.assertTrue(query_matches_phones("2014565698", "2014565698 2015550100"))

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_make_inactive_moves_child_to_inactive_tab_and_keeps_sibling(self):
        _staff_login(self.client, self.admin, "admin")
        url = reverse("portal_admin_family_child_status", kwargs={"family_slug": "jacobs"})
        response = self.client.post(
            url,
            {
                "family_id": self.family.pk,
                "child_id": self.maya.pk,
                "active": "0",
                "next": reverse("portal_admin_page", kwargs={"page": "families"}) + "?tab=inactive",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.maya.refresh_from_db()
        self.assertFalse(self.maya.is_active)
        self.family.refresh_from_db()
        self.assertEqual(self.family.status, "Active")
        self.assertTrue(PortalParentAccount.objects.filter(family=self.family).exists())

        active = get_admin_families_live()
        inactive = get_admin_families_live(inactive=True)
        self.assertEqual(self._child_names(active, "jacobs"), ["Jordan Jacobs"])
        self.assertEqual(self._child_names(inactive, "jacobs"), ["Maya Jacobs"])

        page = self.client.get(reverse("portal_admin_page", kwargs={"page": "families"}))
        self.assertContains(page, ">Active</a>")
        self.assertContains(page, ">Inactive</a>")
        self.assertContains(page, "Jordan Jacobs")
        self.assertNotContains(page, 'data-child-name="maya jacobs"')
        self.assertContains(page, "Family, child, or phone")
        self.assertContains(page, "How to use the families list")

        inactive_page = self.client.get(
            reverse("portal_admin_page", kwargs={"page": "families"}),
            {"tab": "inactive"},
        )
        self.assertContains(inactive_page, "Maya Jacobs")
        self.assertContains(inactive_page, "Make active")
        self.assertNotContains(inactive_page, "Jordan Jacobs")

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_reactivate_from_inactive_tab(self):
        self.maya.is_active = False
        self.maya.save(update_fields=["is_active"])
        _staff_login(self.client, self.admin, "admin")
        response = self.client.post(
            reverse("portal_admin_family_child_status", kwargs={"family_slug": "jacobs"}),
            {
                "family_id": self.family.pk,
                "child_id": self.maya.pk,
                "active": "1",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.maya.refresh_from_db()
        self.assertTrue(self.maya.is_active)
        self.assertEqual(self._child_names(get_admin_families_live(inactive=True), "jacobs"), [])
        self.assertIn("Maya Jacobs", self._child_names(get_admin_families_live(), "jacobs"))

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_waitlist_only_child_stays_off_inactive_tab(self):
        wait_family = PortalFamily.objects.create(unit=self.unit, slug="wait-only", name="Waitonly")
        child = PortalChild.objects.create(family=wait_family, name="Ada Waitonly", is_active=False)
        app = _make_application(wait_family, status="waitlist")
        app.student_first_name = "Ada"
        app.student_last_name = "Waitonly"
        app.save(update_fields=["student_first_name", "student_last_name"])
        self.assertEqual(child.name, "Ada Waitonly")
        self.assertNotIn("wait-only", {row["slug"] for row in get_admin_families_live()})
        self.assertNotIn("wait-only", {row["slug"] for row in get_admin_families_live(inactive=True)})

    def test_phone_search_matches_parent_and_secondary_phones(self):
        rows = get_admin_families_live()
        jordan = next(row for row in rows if row["child_name"] == "Jordan Jacobs")
        self.assertTrue(row_matches_list_nav(jordan, {"q": "(201) 456-5698"}))
        self.assertTrue(row_matches_list_nav(jordan, {"q": "2014565698"}))
        self.assertTrue(row_matches_list_nav(jordan, {"q": "201-555-0100"}))
        self.assertFalse(row_matches_list_nav(jordan, {"q": "9995550000"}))

        self.maya.is_active = False
        self.maya.save(update_fields=["is_active"])
        inactive = get_admin_families_live(inactive=True)
        maya = next(row for row in inactive if row["child_name"] == "Maya Jacobs")
        self.assertTrue(row_matches_list_nav(maya, {"q": "2014565698"}))

    def test_inactive_child_drops_from_enrollment_and_attendance_roster(self):
        self.maya.is_active = False
        self.maya.save(update_fields=["is_active"])
        self.assertEqual(unit_enrollment_count(self.unit), 1)
        roster = {row["child"] for row in get_program_roster(self.unit)}
        self.assertIn("Jordan Jacobs", roster)
        self.assertNotIn("Maya Jacobs", roster)

    def test_staff_only_sees_their_unit_inactive_child(self):
        other_family = PortalFamily.objects.create(unit=self.other, slug="chen", name="Chen")
        other_child = PortalChild.objects.create(
            family=other_family, name="Mia Chen", unit=self.other, is_active=False
        )
        self.maya.is_active = False
        self.maya.save(update_fields=["is_active"])
        names = [row["child_name"] for row in families_for_staff(self.unit, inactive=True)]
        self.assertIn("Maya Jacobs", names)
        self.assertNotIn("Mia Chen", names)
        self.assertEqual(other_child.unit_id, self.other.pk)

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_parent_still_gets_pay_now_and_tax_when_children_are_inactive(self):
        post_charge(
            self.family,
            "Maya Jacobs",
            "tuition",
            "40.00",
            date(2026, 9, 1),
            "Weekly tuition",
            notify=False,
        )
        self.jordan.is_active = False
        self.jordan.save(update_fields=["is_active"])
        self.maya.is_active = False
        self.maya.save(update_fields=["is_active"])

        preview = build_parent_preview_live(self.family, self.parent_account)
        self.assertEqual(preview["dashboard"]["application_status"], "Inactive")
        self.assertEqual(preview["dashboard"]["balance"], "40.00")
        self.assertTrue(any(child["name"] == "Maya Jacobs" for child in preview["billing"]["children"]))

        tax = get_tax_eligibility_live(self.family)
        self.assertEqual(tax["balance"], "40.00")
        self.assertFalse(tax["eligible"])

        self.client.force_login(self.parent_user)
        session = self.client.session
        session[PORTAL_AUTH_SESSION_KEY] = "parent"
        session.save()
        dashboard = self.client.get(reverse("portal_parent_page", kwargs={"page": "dashboard"}))
        self.assertEqual(dashboard.status_code, 200)
        self.assertContains(dashboard, "Pay now")
        self.assertContains(dashboard, "$40.00")
        self.assertContains(dashboard, "Inactive")
        billing = self.client.get(reverse("portal_parent_page", kwargs={"page": "billing"}))
        self.assertContains(billing, "Pay now")
        tax_page = self.client.get(reverse("portal_parent_page", kwargs={"page": "tax-statements"}))
        self.assertEqual(tax_page.status_code, 200)
        self.assertContains(tax_page, "Tax")

    def test_outstanding_inactive_status_finds_inactive_child_who_owes(self):
        PortalLedgerEntry.objects.create(
            family=self.family,
            child_name="Maya Jacobs",
            date=timezone.localdate(),
            entry_type="charge",
            description="Past due — Maya Jacobs",
            amount=Decimal("25.00"),
        )
        self.maya.is_active = False
        self.maya.save(update_fields=["is_active"])
        default_report = build_admin_report("balances", {})
        self.assertNotIn("Maya Jacobs", [row["child"] for row in default_report["rows"]])
        inactive_report = build_admin_report("balances", {"status": "Inactive"})
        self.assertEqual([row["child"] for row in inactive_report["rows"]], ["Maya Jacobs"])
        all_report = build_admin_report("balances", {"status": ""})
        self.assertIn("Maya Jacobs", [row["child"] for row in all_report["rows"]])

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_family_account_shows_make_inactive(self):
        _staff_login(self.client, self.admin, "admin")
        page = self.client.get(reverse("portal_admin_family_detail", kwargs={"family_slug": "jacobs"}))
        self.assertContains(page, "Children in program")
        self.assertContains(page, "Make inactive")
        self.assertContains(page, "Jordan Jacobs")
