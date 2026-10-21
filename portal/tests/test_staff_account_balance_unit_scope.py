"""Staff Account Balance lists only PortalStaffAccount assigned units."""

from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from portal.admin_reports import build_admin_report
from portal.billing_services import post_charge
from portal.models import (
    PortalChild,
    PortalFamily,
    PortalStaffAccount,
    PortalUnit,
)
from portal.staff_auth import (
    PORTAL_AUTH_SESSION_KEY,
    staff_account_balance_unit_scope,
    staff_assigned_units,
)
from portal.tests.test_family_units import _make_application, _staff_login


class StaffAccountBalanceUnitScopeTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.school_18 = PortalUnit.objects.create(slug="school-18", name="School 18", is_active=True)
        self.school_26 = PortalUnit.objects.create(slug="school-26", name="School 26", is_active=True)

        self.family_18 = PortalFamily.objects.create(
            unit=self.school_18,
            slug="jacobs",
            name="Jacobs",
            billing_type="Private pay",
            status="Active",
        )
        self.jordan = PortalChild.objects.create(
            family=self.family_18,
            name="Jordan Jacobs",
            unit=self.school_18,
            billing_plan="Weekly",
            is_active=True,
        )
        post_charge(
            self.family_18,
            self.jordan.name,
            "tuition",
            "40.00",
            date(2026, 9, 8),
            "Weekly tuition — Jordan Jacobs (9/8/26–9/12/26)",
            notify=False,
        )

        self.family_26 = PortalFamily.objects.create(
            unit=self.school_26,
            slug="lee",
            name="Lee",
            billing_type="Private pay",
            status="Active",
        )
        self.nia = PortalChild.objects.create(
            family=self.family_26,
            name="Nia Lee",
            unit=self.school_26,
            billing_plan="Weekly",
            is_active=True,
        )
        post_charge(
            self.family_26,
            self.nia.name,
            "tuition",
            "55.00",
            date(2026, 9, 8),
            "Weekly tuition — Nia Lee (9/8/26–9/12/26)",
            notify=False,
        )

        self.mixed = PortalFamily.objects.create(
            unit=self.school_18,
            slug="rivera",
            name="Rivera",
            billing_type="Private pay",
            status="Active",
        )
        self.child_a = PortalChild.objects.create(
            family=self.mixed,
            name="Child A Rivera",
            unit=self.school_18,
            billing_plan="Weekly",
            is_active=True,
        )
        self.child_b = PortalChild.objects.create(
            family=self.mixed,
            name="Child B Rivera",
            unit=self.school_26,
            billing_plan="Weekly",
            is_active=True,
        )
        post_charge(
            self.mixed,
            self.child_a.name,
            "tuition",
            "35.00",
            date(2026, 9, 8),
            "School 18 tuition",
            notify=False,
        )
        post_charge(
            self.mixed,
            self.child_b.name,
            "tuition",
            "45.00",
            date(2026, 9, 8),
            "School 26 tuition",
            notify=False,
        )

        practice = PortalFamily.objects.create(
            unit=self.school_18,
            slug="practice",
            name="Practice",
            status="Active",
        )
        PortalChild.objects.create(
            family=practice,
            name="Practice Kid",
            unit=self.school_18,
            is_active=True,
        )

        pending = PortalFamily.objects.create(
            unit=self.school_18,
            slug="pending",
            name="Pending",
            status="Pending enrollment",
        )
        app = _make_application(pending, status="under_review")
        app.student_first_name = "Ada"
        app.student_last_name = "Pending"
        app.save(update_fields=["student_first_name", "student_last_name"])
        PortalChild.objects.create(
            family=pending,
            name="Ada Pending",
            unit=self.school_18,
            is_active=True,
        )

        self.inactive = PortalChild.objects.create(
            family=self.family_18,
            name="Omar Inactive",
            unit=self.school_18,
            billing_plan="Weekly",
            is_active=False,
        )
        post_charge(
            self.family_18,
            self.inactive.name,
            "tuition",
            "15.00",
            date(2026, 9, 8),
            "Past due inactive",
            notify=False,
        )

        self.staff18 = User.objects.create_user(username="staff:staff18", password="StaffPass123!")
        self.staff18_account = PortalStaffAccount.objects.create(
            user=self.staff18,
            unit=self.school_18,
            display_name="School 18 Staff",
            role="Unit director",
            is_active=True,
        )
        self.staff26 = User.objects.create_user(username="staff:staff26", password="StaffPass123!")
        PortalStaffAccount.objects.create(
            user=self.staff26,
            unit=self.school_26,
            display_name="School 26 Staff",
            role="Front desk staff",
            is_active=True,
        )
        self.pd = User.objects.create_user(username="staff:pd18", password="StaffPass123!")
        PortalStaffAccount.objects.create(
            user=self.pd,
            unit=self.school_18,
            display_name="Program Director 18",
            role="Program director",
            is_active=True,
            can_see_billing=True,
        )
        self.multi = User.objects.create_user(username="staff:multi", password="StaffPass123!")
        multi_account = PortalStaffAccount.objects.create(
            user=self.multi,
            unit=self.school_18,
            display_name="Multi Unit Staff",
            role="Unit director",
            is_active=True,
        )
        multi_account.accessible_units.set([self.school_18, self.school_26])
        self.admin = User.objects.create_user(username="staff:yeaadmin", password="AdminPass123")
        PortalStaffAccount.objects.create(
            user=self.admin,
            unit=self.school_18,
            display_name="Portal Admin",
            role="Portal admin",
            all_units_access=True,
            is_active=True,
        )

    def _staff_page(self, user, params=None, *, session_unit=None):
        _staff_login(self.client, user, "staff")
        if session_unit:
            session = self.client.session
            session["staff_unit_slug"] = session_unit
            session.save()
        return self.client.get(reverse("portal_staff_account_balance_report"), params or {})

    def _admin_page(self, params=None):
        _staff_login(self.client, self.admin, "admin")
        return self.client.get(
            reverse("portal_admin_data_report", kwargs={"report_slug": "balances"}),
            params or {},
        )

    def test_assigned_units_do_not_expand_for_program_director(self):
        self.assertEqual(
            [unit.slug for unit in staff_assigned_units(self.staff18_account)],
            ["school-18"],
        )
        units, selected = staff_account_balance_unit_scope(self.staff18_account, "school-26")
        self.assertEqual([unit.slug for unit in units], ["school-18"])
        self.assertEqual(selected, "school-18")

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_staff18_account_balance_is_school_18_only(self):
        page = self._staff_page(self.staff18)
        self.assertEqual(page.status_code, 200)
        html = page.content.decode()
        self.assertIn("Jordan Jacobs", html)
        self.assertIn("Child A Rivera", html)
        self.assertNotIn("Nia Lee", html)
        self.assertNotIn("Child B Rivera", html)
        self.assertNotIn("Practice Kid", html)
        self.assertNotIn("Ada Pending", html)
        self.assertNotIn("Omar Inactive", html)
        self.assertNotIn("School 26", html)
        names = [row["child"] for row in page.context["report"]["rows"]]
        self.assertEqual(names, ["Child A Rivera", "Jordan Jacobs"])
        self.assertEqual(
            next(row for row in page.context["report"]["rows"] if row["child"] == "Child A Rivera")["amount_owe"],
            "35.00",
        )
        unit_names = [row["unit"] for row in page.context["report"]["unit_balances"]]
        self.assertEqual(unit_names, ["School 18"])
        self.assertNotIn("unit", page.context["report"]["filters"])

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_staff26_account_balance_is_school_26_only(self):
        page = self._staff_page(self.staff26)
        self.assertEqual(page.status_code, 200)
        html = page.content.decode()
        self.assertIn("Nia Lee", html)
        self.assertIn("Child B Rivera", html)
        self.assertNotIn("Jordan Jacobs", html)
        self.assertNotIn("Child A Rivera", html)
        self.assertNotIn("School 18", html)
        names = [row["child"] for row in page.context["report"]["rows"]]
        self.assertEqual(names, ["Child B Rivera", "Nia Lee"])
        self.assertEqual(
            next(row for row in page.context["report"]["rows"] if row["child"] == "Child B Rivera")["amount_owe"],
            "45.00",
        )
        self.assertEqual(
            [row["unit"] for row in page.context["report"]["unit_balances"]],
            ["School 26"],
        )

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_admin_account_balance_shows_both_units(self):
        page = self._admin_page()
        self.assertEqual(page.status_code, 200)
        html = page.content.decode()
        self.assertIn("Jordan Jacobs", html)
        self.assertIn("Nia Lee", html)
        self.assertIn("Child A Rivera", html)
        self.assertIn("Child B Rivera", html)
        self.assertIn("School 18", html)
        self.assertIn("School 26", html)
        self.assertNotIn("Practice Kid", html)
        self.assertNotIn("Ada Pending", html)
        names = {row["child"] for row in page.context["report"]["rows"]}
        self.assertEqual(names, {"Jordan Jacobs", "Nia Lee", "Child A Rivera", "Child B Rivera"})
        unit_names = {row["unit"] for row in page.context["report"]["unit_balances"]}
        self.assertEqual(unit_names, {"School 18", "School 26"})

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_staff18_cannot_tamper_unit_query_or_session(self):
        tamper = self._staff_page(
            self.staff18,
            {"unit": "school-26"},
            session_unit="school-26",
        )
        self.assertEqual(tamper.status_code, 200)
        html = tamper.content.decode()
        self.assertIn("Jordan Jacobs", html)
        self.assertNotIn("Nia Lee", html)
        self.assertNotIn("Child B Rivera", html)
        self.assertNotIn("School 26", html)
        self.assertEqual(tamper.context["filters"]["unit"], "school-18")
        self.assertNotIn('value="school-26"', html)

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_program_director_stays_on_assigned_unit(self):
        page = self._staff_page(self.pd, {"unit": "school-26"}, session_unit="school-26")
        self.assertEqual(page.status_code, 200)
        names = [row["child"] for row in page.context["report"]["rows"]]
        self.assertEqual(names, ["Child A Rivera", "Jordan Jacobs"])
        self.assertEqual(
            [row["unit"] for row in page.context["report"]["unit_balances"]],
            ["School 18"],
        )

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_multi_unit_staff_sees_only_assigned_units(self):
        page = self._staff_page(self.multi)
        self.assertEqual(page.status_code, 200)
        names = {row["child"] for row in page.context["report"]["rows"]}
        self.assertEqual(names, {"Jordan Jacobs", "Nia Lee", "Child A Rivera", "Child B Rivera"})
        self.assertIn("unit", page.context["report"]["filters"])
        self.assertEqual(
            {slug for slug, _name in page.context["report"]["units"]},
            {"school-18", "school-26"},
        )

        only_26 = self._staff_page(self.multi, {"unit": "school-26"})
        self.assertEqual(
            [row["child"] for row in only_26.context["report"]["rows"]],
            ["Child B Rivera", "Nia Lee"],
        )
        self.assertEqual(only_26.context["filters"]["unit"], "school-26")

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_staff_cannot_open_admin_balances_url(self):
        _staff_login(self.client, self.staff18, "staff")
        response = self.client.get(
            reverse("portal_admin_data_report", kwargs={"report_slug": "balances"}),
            {"unit": "school-26"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn("/portal/admin/login/", response.url)

    def test_admin_builder_without_scope_still_lists_both_units(self):
        report = build_admin_report("balances", {"status": "Active"})
        names = {row["child"] for row in report["rows"]}
        self.assertEqual(names, {"Jordan Jacobs", "Nia Lee", "Child A Rivera", "Child B Rivera"})
        self.assertEqual({row["unit"] for row in report["unit_balances"]}, {"School 18", "School 26"})
        scoped = build_admin_report(
            "balances",
            {"status": "Active", "allowed_unit_slugs": ["school-18"]},
        )
        self.assertEqual([row["child"] for row in scoped["rows"]], ["Child A Rivera", "Jordan Jacobs"])
        self.assertEqual([row["unit"] for row in scoped["unit_balances"]], ["School 18"])
