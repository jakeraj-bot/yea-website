from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from portal.admin_config import save_scholarship_fund
from portal.admin_reports import build_admin_report, set_account_balance_paid
from portal.billing_services import (
    post_charge,
    post_credit,
    post_payment,
    prepare_billing_for_staff,
    update_child_billing_plan,
)
from portal.family_list import child_balance, family_balance
from portal.models import (
    PortalAgency,
    PortalAgencyLedgerEntry,
    PortalAgencyProfile,
    PortalChild,
    PortalFamily,
    PortalLedgerEntry,
    PortalStaffAccount,
    PortalUnit,
)
from portal.parent_services import get_billing_live
from portal.staff_auth import PORTAL_AUTH_SESSION_KEY
from portal.tests.test_family_units import _make_application


class AccountBalanceMatchesBillingTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.unit = PortalUnit.objects.create(slug="school-18", name="School 18", is_active=True)
        self.family = PortalFamily.objects.create(
            unit=self.unit,
            slug="jacobs",
            name="Jacobs",
            billing_type="Private pay",
            status="Active",
        )
        self.child = PortalChild.objects.create(
            family=self.family,
            name="Jordan Jacobs",
            school="School 18",
            billing_plan="Weekly",
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
            can_add_charge=True,
            can_delete_charge=True,
            can_add_credit=True,
        )

    def _login(self):
        self.client.force_login(self.admin)
        session = self.client.session
        session[PORTAL_AUTH_SESSION_KEY] = "admin"
        session.save()

    def _report_row(self, child_name, filters=None):
        report = build_admin_report("balances", filters or {"status": "Active"})
        return next(row for row in report["rows"] if row["child"] == child_name)

    def _child_live(self, family, child_name):
        billing = get_billing_live(family)
        child = next(item for item in billing["children"] if item["name"] == child_name)
        return child, billing

    def test_two_plan_scholarship_matches_billing_amount_and_open_descriptions(self):
        today = timezone.localdate()
        weekday = (today.weekday() + 1) % 7
        fund = save_scholarship_fund({"name": "YEA General Scholarship", "description": "Need-based"})
        update_child_billing_plan(
            self.family,
            "Jordan Jacobs",
            "Weekly",
            "40.00",
            billing_type="Scholarship",
            scholarship_fund_id=fund.pk,
            scholarship_full_rate="40.00",
            scholarship_parent_amount="25.00",
            auto_charge=True,
            next_charge_date=today,
            charge_weekday=weekday,
            description="After care",
        )
        update_child_billing_plan(
            self.family,
            "Jordan Jacobs",
            "Weekly",
            "20.00",
            "Private pay",
            auto_charge=True,
            next_charge_date=today,
            charge_weekday=weekday,
            description="Before care",
            create_new=True,
        )
        child_live, billing = self._child_live(self.family, "Jordan Jacobs")
        row = self._report_row("Jordan Jacobs")
        self.assertEqual(row["amount_owe"], child_live["balance"])
        self.assertEqual(row["amount_owe"], billing["running_balance"])
        self.assertEqual(row["amount_owe"], f"{child_balance(self.child):.2f}")
        charges = list(
            PortalLedgerEntry.objects.filter(family=self.family, entry_type="charge").values_list(
                "description", flat=True
            )
        )
        self.assertGreaterEqual(len(charges), 2)
        for description in charges:
            self.assertIn(description, row["description"])
        self.assertNotIn("Owe for account balance", row["description"])
        self.assertNotIn("Credit $", row["description"])
        self.assertTrue(any("After care" in item for item in charges))
        self.assertTrue(any("Before care" in item for item in charges))

    def test_overpay_credit_matches_billing_and_description(self):
        post_charge(
            self.family,
            "Jordan Jacobs",
            "tuition",
            "70.00",
            date(2026, 9, 8),
            "CC WK 2 - weekly charge — After care",
            notify=False,
        )
        post_payment(self.family, "Jordan Jacobs", "100.00", date(2026, 9, 10), "Cash")
        child_live, billing = self._child_live(self.family, "Jordan Jacobs")
        self.assertTrue(child_live["has_credit"])
        self.assertTrue(billing["has_credit"])
        self.assertEqual(child_live["account_credit"], "30.00")
        row = self._report_row("Jordan Jacobs")
        self.assertEqual(row["amount_owe"], child_live["balance"])
        self.assertEqual(row["amount_owe"], billing["running_balance"])
        self.assertEqual(row["amount_owe"], "-30.00")
        self.assertEqual(row["description"], "Credit $30.00")

    def test_four_cs_copay_matches_billing_not_agency_rate(self):
        family = PortalFamily.objects.create(
            unit=self.unit,
            slug="martinez",
            name="Martinez",
            billing_type="4Cs",
            status="Active",
        )
        child = PortalChild.objects.create(
            family=family,
            name="Sofia Martinez",
            school="School 18",
            billing_plan="Weekly copay",
            billing_amount=Decimal("25.00"),
            is_active=True,
        )
        agency = PortalAgency.objects.create(slug="passaic-4cs", name="Passaic County 4Cs", is_active=True)
        profile = PortalAgencyProfile.objects.create(
            unit=self.unit,
            family=family,
            child=child,
            agency=agency,
            auth_number="4CS-2026-1001",
            weekly_copay=Decimal("25.00"),
            weekly_agency_rate=Decimal("180.00"),
        )
        copay_desc = "CC WK 3 - weekly 4Cs Copay"
        post_charge(
            family,
            child.name,
            "4cs_copay",
            "25.00",
            date(2026, 9, 10),
            copay_desc,
            notify=False,
        )
        PortalAgencyLedgerEntry.objects.create(
            profile=profile,
            date=date(2026, 9, 10),
            entry_type="charge",
            description="CC WK 3 - weekly 4Cs agency",
            amount=Decimal("180.00"),
        )
        child_live, billing = self._child_live(family, child.name)
        row = self._report_row(child.name)
        self.assertEqual(child_live["balance"], "25.00")
        self.assertEqual(row["amount_owe"], "25.00")
        self.assertEqual(row["amount_owe"], child_live["balance"])
        self.assertEqual(row["description"], copay_desc)
        self.assertNotIn("agency", row["description"].lower())
        self.assertNotEqual(row["amount_owe"], "180.00")
        self.assertNotEqual(row["amount_owe"], "205.00")

    def test_membership_and_unlabeled_family_payment_descriptions(self):
        post_charge(
            self.family,
            "Jordan Jacobs",
            "tuition",
            "40.00",
            date(2026, 9, 8),
            "CC WK 1 - weekly charge",
            notify=False,
        )
        PortalLedgerEntry.objects.create(
            family=self.family,
            child_name="Jordan Jacobs",
            date=date(2026, 9, 1),
            entry_type="membership",
            description="Membership fee ($20.00) — Jordan Jacobs",
            amount=Decimal("20.00"),
            is_manual=True,
        )
        child_live, _billing = self._child_live(self.family, "Jordan Jacobs")
        row = self._report_row("Jordan Jacobs")
        self.assertEqual(row["amount_owe"], "60.00")
        self.assertEqual(row["amount_owe"], child_live["balance"])
        self.assertIn("CC WK 1 - weekly charge", row["description"])
        self.assertIn("Membership fee ($20.00) — Jordan Jacobs", row["description"])

        PortalLedgerEntry.objects.create(
            family=self.family,
            child_name="",
            date=date(2026, 9, 11),
            entry_type="payment",
            description="Family cash",
            amount=Decimal("-20.00"),
            is_manual=True,
        )
        child_live, _billing = self._child_live(self.family, "Jordan Jacobs")
        row = self._report_row("Jordan Jacobs")
        self.assertEqual(row["amount_owe"], child_live["balance"])
        self.assertEqual(row["amount_owe"], "40.00")
        self.assertIn("CC WK 1 - weekly charge", row["description"])
        self.assertNotIn("Membership fee ($20.00) — Jordan Jacobs", row["description"])

    def test_stripe_fee_does_not_inflate_amount_owe(self):
        post_charge(
            self.family,
            "Jordan Jacobs",
            "tuition",
            "50.00",
            date(2026, 9, 8),
            "CC WK 4 - weekly charge",
            notify=False,
        )
        PortalLedgerEntry.objects.create(
            family=self.family,
            child_name="Jordan Jacobs",
            date=date(2026, 9, 9),
            entry_type="payment",
            description="Online payment",
            amount=Decimal("-20.00"),
            fee_amount=Decimal("0.88"),
        )
        child_live, billing = self._child_live(self.family, "Jordan Jacobs")
        row = self._report_row("Jordan Jacobs")
        self.assertEqual(row["amount_owe"], "30.00")
        self.assertEqual(row["amount_owe"], child_live["balance"])
        self.assertEqual(family_balance(self.family), Decimal("30.00"))
        self.assertNotEqual(row["amount_owe"], "30.88")
        self.assertIn("CC WK 4 - weekly charge", row["description"])
        staff = prepare_billing_for_staff(self.family, {"can_delete_charge": True})
        newest = staff["ledger"][0]
        self.assertEqual(newest["running_balance"], billing["running_balance"])

    def test_paid_checkbox_does_not_change_amount_or_description(self):
        post_charge(
            self.family,
            "Jordan Jacobs",
            "tuition",
            "35.00",
            date(2026, 9, 8),
            "CC WK 5 - weekly charge",
            notify=False,
        )
        before = self._report_row("Jordan Jacobs")
        set_account_balance_paid(self.child, True, updated_by="Portal Admin")
        after = self._report_row("Jordan Jacobs")
        self.assertTrue(after["paid_checked"])
        self.assertEqual(after["amount_owe"], before["amount_owe"])
        self.assertEqual(after["description"], before["description"])
        self.assertEqual(after["description"], "CC WK 5 - weekly charge")

    def test_unapproved_child_stays_off_report(self):
        pending = PortalFamily.objects.create(
            unit=self.unit,
            slug="pending-app",
            name="Pending",
            billing_type="Private pay",
            status="Active",
        )
        child = PortalChild.objects.create(
            family=pending,
            name="Ada Pending",
            school="School 18",
            is_active=True,
        )
        _make_application(pending, status="under_review")
        pending.enrollment_applications.update(student_first_name="Ada", student_last_name="Pending")
        post_charge(
            pending,
            child.name,
            "tuition",
            "75.00",
            date(2026, 9, 8),
            "Weekly tuition — Ada Pending",
            notify=False,
        )
        names = [row["child"] for row in build_admin_report("balances", {"status": "Active"})["rows"]]
        self.assertNotIn("Ada Pending", names)

    def test_paid_in_full_description_is_blank(self):
        post_charge(
            self.family,
            "Jordan Jacobs",
            "tuition",
            "40.00",
            date(2026, 9, 8),
            "CC WK 6 - weekly charge",
            notify=False,
        )
        post_payment(self.family, "Jordan Jacobs", "40.00", date(2026, 9, 9), "Cash")
        child_live, billing = self._child_live(self.family, "Jordan Jacobs")
        row = self._report_row("Jordan Jacobs")
        self.assertEqual(child_live["balance"], "0.00")
        self.assertEqual(row["amount_owe"], "0.00")
        self.assertEqual(row["amount_owe"], billing["running_balance"])
        self.assertEqual(row["description"], "")

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_billing_ledger_running_balance_and_actions_under_description(self):
        post_charge(
            self.family,
            "Jordan Jacobs",
            "tuition",
            "70.00",
            date(2026, 9, 8),
            "CC WK 2 - weekly charge — After care",
            notify=False,
        )
        post_credit(self.family, "Jordan Jacobs", "20.00", date(2026, 9, 11), "Goodwill")
        post_payment(self.family, "Jordan Jacobs", "10.00", date(2026, 9, 12), "Cash")
        preview = prepare_billing_for_staff(
            self.family, {"can_delete_charge": True, "can_add_credit": True}
        )
        self.assertEqual(preview["running_balance"], "40.00")
        newest = preview["ledger"][0]
        self.assertEqual(newest["running_balance"], "40.00")
        chrono = list(reversed(preview["ledger"]))
        self.assertEqual(chrono[0]["running_balance"], "70.00")
        self.assertEqual(chrono[1]["running_balance"], "50.00")
        self.assertEqual(chrono[2]["running_balance"], "40.00")

        self._login()
        page = self.client.get(reverse("portal_admin_family_billing", kwargs={"family_slug": "jacobs"}))
        self.assertEqual(page.status_code, 200)
        html = page.content.decode()
        self.assertIn("Running balance", html)
        self.assertIn("portal-ledger-col-running", html)
        self.assertIn("portal-billing-ledger-actions", html)
        self.assertIn("edit-ledger-desc", html)
        self.assertIn(">Delete<", html)
        self.assertNotIn("<th></th>", html)
        self.assertNotIn("Check # / Money order #", html)
        self.assertIn("portal-billing-ledger", html)
        date_idx = html.find("portal-ledger-col-date")
        fee_idx = html.find("portal-ledger-col-fee")
        running_idx = html.find("portal-ledger-col-running")
        actions_idx = html.find("portal-billing-ledger-actions")
        desc_idx = html.find("portal-ledger-desc-cell")
        self.assertLess(date_idx, fee_idx)
        self.assertLess(fee_idx, running_idx)
        self.assertLess(desc_idx, actions_idx)
        self.assertLess(actions_idx, html.find("portal-ledger-col-amount", desc_idx))

        report_page = self.client.get(reverse("portal_admin_data_report", kwargs={"report_slug": "balances"}))
        self.assertEqual(report_page.status_code, 200)
        self.assertContains(report_page, "Jordan Jacobs")
        self.assertContains(report_page, "40.00")
        self.assertContains(report_page, "CC WK 2 - weekly charge — After care")
        self.assertContains(report_page, "portal-paid-box")
