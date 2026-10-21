"""Unit Balance is money still owed; leftover named credits stay on that family."""

from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from portal.admin_reports import build_admin_report
from portal.admin_services import get_admin_dashboard_live
from portal.billing_services import post_charge, post_credit, post_payment, prepare_billing_for_staff
from portal.family_list import child_balance, family_balance, unit_balance_summary
from portal.member_admin import set_child_active
from portal.models import PortalChild, PortalFamily, PortalStaffAccount, PortalUnit
from portal.parent_services import get_billing_live
from portal.staff_auth import PORTAL_AUTH_SESSION_KEY


class AccountBalanceUnitCreditsTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.school_18 = PortalUnit.objects.create(slug="school-18", name="School 18", is_active=True)
        self.school_26 = PortalUnit.objects.create(slug="school-26", name="School 26", is_active=True)
        self.admin = User.objects.create_user(username="staff:yeaadmin", password="AdminPass123")
        PortalStaffAccount.objects.create(
            user=self.admin,
            unit=self.school_18,
            display_name="Portal Admin",
            role="Portal admin",
            all_units_access=True,
            is_active=True,
            can_add_charge=True,
            can_add_credit=True,
        )

    def _family(self, slug, name, unit):
        return PortalFamily.objects.create(
            unit=unit,
            slug=slug,
            name=name,
            billing_type="Private pay",
            status="Active",
        )

    def _child(self, family, name, unit):
        return PortalChild.objects.create(
            family=family,
            name=name,
            unit=unit,
            school=unit.name,
            is_active=True,
        )

    def _charge(self, family, child, amount, description="Weekly tuition"):
        return post_charge(
            family,
            child.name,
            "tuition",
            amount,
            date(2026, 9, 8),
            f"{description} — {child.name}",
            notify=False,
        )

    def _credit(self, family, child, amount, description="Scholarship"):
        return post_credit(family, child.name, amount, date(2026, 9, 9), f"{description} — {child.name}")

    def _units(self):
        return {row["slug"]: row for row in unit_balance_summary()}

    def test_school_26_balance_does_not_net_eighty_dollar_credit(self):
        owing_family = self._family("owing-26", "Owing26", self.school_26)
        credit_family = self._family("credit-26", "Credit26", self.school_26)
        owing = self._child(owing_family, "Omar Owing", self.school_26)
        credited = self._child(credit_family, "Cara Credit", self.school_26)
        self._charge(owing_family, owing, "2560.00")
        self._credit(credit_family, credited, "80.00")

        units = self._units()
        school = units["school-26"]
        self.assertEqual(school["balance"], "2560.00")
        self.assertEqual(school["credits"], "80.00")
        self.assertEqual(school["overdue"], "2560.00")
        self.assertEqual(school["account_credit"], "80.00")
        self.assertTrue(school["has_credit"])
        self.assertEqual(school["family_count"], 1)
        self.assertNotEqual(school["balance"], "2480.00")
        self.assertEqual(child_balance(credited), Decimal("-80.00"))
        report = build_admin_report("balances", {"status": "Active"})
        cara = next(row for row in report["rows"] if row["child"] == "Cara Credit")
        self.assertEqual(cara["amount_owe"], "-80.00")
        self.assertIn("Credit $80.00", cara["description"])

    def test_school_18_balance_keeps_positive_sum_and_lists_credits(self):
        owing_family = self._family("owing-18", "Owing18", self.school_18)
        alan_family = self._family("solano", "Solano", self.school_18)
        extra_credit_family = self._family("credit-18", "Credit18", self.school_18)
        owing = self._child(owing_family, "Owen Owing", self.school_18)
        alan = self._child(alan_family, "Alan Michael Solano", self.school_18)
        extra = self._child(extra_credit_family, "Nina Credit", self.school_18)
        self._charge(owing_family, owing, "6280.10")
        self._credit(alan_family, alan, "19.90")
        self._credit(extra_credit_family, extra, "218.65")

        units = self._units()
        school = units["school-18"]
        self.assertEqual(school["balance"], "6280.10")
        self.assertEqual(school["credits"], "238.55")
        self.assertEqual(school["overdue"], "6280.10")
        self.assertEqual(school["family_count"], 1)
        self.assertNotEqual(school["balance"], "6041.55")
        self.assertEqual(child_balance(alan), Decimal("-19.90"))
        dashboard = get_admin_dashboard_live()
        overview = {row["slug"]: row for row in dashboard["unit_balances"]}
        self.assertEqual(overview["school-18"]["balance"], "6280.10")
        self.assertEqual(overview["school-18"]["credits"], "238.55")
        self.assertEqual(overview["school-18"]["overdue"], "6280.10")

    def test_named_credit_pays_sibling_then_keeps_leftover_on_family(self):
        family = self._family("siblings", "Siblings", self.school_18)
        other = self._family("other-18", "Other18", self.school_18)
        ada = self._child(family, "Ada Sibling", self.school_18)
        ben = self._child(family, "Ben Sibling", self.school_18)
        outsider = self._child(other, "Omar Other", self.school_18)
        self._charge(family, ada, "50.00")
        self._credit(family, ben, "20.00")
        self._charge(other, outsider, "80.00")

        self.assertEqual(child_balance(ben), Decimal("0.00"))
        self.assertEqual(child_balance(ada), Decimal("30.00"))
        self.assertEqual(child_balance(outsider), Decimal("80.00"))
        self.assertEqual(family_balance(family), Decimal("30.00"))
        billing = get_billing_live(family)
        by_name = {row["name"]: row for row in billing["children"]}
        self.assertEqual(by_name["Ada Sibling"]["balance"], "30.00")
        self.assertEqual(by_name["Ben Sibling"]["balance"], "0.00")
        self.assertFalse(by_name["Ben Sibling"]["has_credit"])
        staff = prepare_billing_for_staff(family, {"can_add_credit": True})
        staff_by_name = {row["name"]: row for row in staff["children"]}
        self.assertEqual(staff_by_name["Ada Sibling"]["balance"], "30.00")
        self.assertEqual(staff_by_name["Ben Sibling"]["balance"], "0.00")
        report = build_admin_report("balances", {"status": "Active"})
        ada_row = next(row for row in report["rows"] if row["child"] == "Ada Sibling")
        ben_row = next(row for row in report["rows"] if row["child"] == "Ben Sibling")
        omar_row = next(row for row in report["rows"] if row["child"] == "Omar Other")
        self.assertEqual(ada_row["amount_owe"], "30.00")
        self.assertEqual(ben_row["amount_owe"], "0.00")
        self.assertEqual(omar_row["amount_owe"], "80.00")
        units = self._units()
        self.assertEqual(units["school-18"]["balance"], "110.00")
        self.assertEqual(units["school-18"]["credits"], "0.00")
        self.assertEqual(units["school-18"]["overdue"], "110.00")
        self.assertEqual(units["school-18"]["family_count"], 2)

        self._credit(family, ben, "40.00")
        self.assertEqual(child_balance(ada), Decimal("0.00"))
        self.assertEqual(child_balance(ben), Decimal("-10.00"))
        self.assertEqual(child_balance(outsider), Decimal("80.00"))
        units = self._units()
        self.assertEqual(units["school-18"]["balance"], "80.00")
        self.assertEqual(units["school-18"]["credits"], "10.00")
        self.assertEqual(units["school-18"]["overdue"], "80.00")
        self.assertEqual(units["school-18"]["family_count"], 1)

    def test_credit_only_family_is_not_families_with_a_balance(self):
        family = self._family("credit-only", "CreditOnly", self.school_18)
        child = self._child(family, "Ivy Creditonly", self.school_18)
        self._credit(family, child, "25.00")
        units = self._units()
        self.assertEqual(units["school-18"]["balance"], "0.00")
        self.assertEqual(units["school-18"]["overdue"], "0.00")
        self.assertEqual(units["school-18"]["credits"], "25.00")
        self.assertEqual(units["school-18"]["family_count"], 0)

    def test_inactive_child_stays_off_unit_balance_and_credits(self):
        family = self._family("mixed-active", "Mixed", self.school_18)
        active = self._child(family, "Ada Active", self.school_18)
        inactive = self._child(family, "Ivy Inactive", self.school_18)
        self._charge(family, active, "25.00")
        self._charge(family, inactive, "40.00")
        self._credit(family, inactive, "15.00")
        set_child_active(inactive, False)
        inactive.refresh_from_db()
        self.assertFalse(inactive.is_active)
        self.assertEqual(child_balance(inactive), Decimal("25.00"))
        units = self._units()
        self.assertEqual(units["school-18"]["balance"], "25.00")
        self.assertEqual(units["school-18"]["overdue"], "25.00")
        self.assertEqual(units["school-18"]["credits"], "0.00")
        self.assertEqual(units["school-18"]["family_count"], 1)

    def test_unlabeled_family_money_can_still_apply_across_household(self):
        family = self._family("unlabeled", "Unlabeled", self.school_18)
        ada = self._child(family, "Ada Unlabeled", self.school_18)
        ben = self._child(family, "Ben Unlabeled", self.school_18)
        self._charge(family, ada, "40.00")
        self._charge(family, ben, "60.00")
        post_payment(family, "", "40.00", date(2026, 9, 10), "Cash")
        self.assertEqual(child_balance(ada), Decimal("0.00"))
        self.assertEqual(child_balance(ben), Decimal("60.00"))
        units = self._units()
        self.assertEqual(units["school-18"]["balance"], "60.00")
        self.assertEqual(units["school-18"]["credits"], "0.00")

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_account_balance_and_overview_show_credits_column(self):
        owing_family = self._family("page-owing", "PageOwing", self.school_18)
        credit_family = self._family("page-credits", "PageCredits", self.school_18)
        owing = self._child(owing_family, "Owen Page", self.school_18)
        credited = self._child(credit_family, "Cara Page", self.school_18)
        self._charge(owing_family, owing, "90.00")
        self._credit(credit_family, credited, "15.00")
        self.client.force_login(self.admin)
        session = self.client.session
        session[PORTAL_AUTH_SESSION_KEY] = "admin"
        session.save()
        report_page = self.client.get(reverse("portal_admin_data_report", kwargs={"report_slug": "balances"}))
        self.assertEqual(report_page.status_code, 200)
        html = report_page.content.decode()
        self.assertIn("Balances by unit", html)
        self.assertIn(">Credits<", html)
        self.assertIn("id=\"unit-balance-table\"", html)
        self.assertIn("$90.00", html)
        self.assertIn("$15.00", html)
        self.assertNotIn("$75.00", html)
        dashboard = self.client.get(reverse("portal_admin_page", kwargs={"page": "dashboard"}))
        self.assertEqual(dashboard.status_code, 200)
        dash_html = dashboard.content.decode()
        self.assertIn("id=\"overview-unit-balances\"", dash_html)
        self.assertIn(">Credits<", dash_html)
        self.assertIn("$90.00", dash_html)
        self.assertIn("$15.00", dash_html)
