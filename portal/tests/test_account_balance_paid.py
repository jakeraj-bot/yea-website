from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from portal.admin_reports import build_admin_report, set_account_balance_paid
from portal.billing_services import post_charge, post_payment
from portal.models import (
    PortalAccountBalancePaidMark,
    PortalChild,
    PortalFamily,
    PortalLedgerEntry,
    PortalStaffAccount,
    PortalUnit,
)
from portal.staff_auth import PORTAL_AUTH_SESSION_KEY


class AccountBalancePaidCheckboxTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.unit = PortalUnit.objects.create(slug="school-18", name="School 18", is_active=True)
        self.family = PortalFamily.objects.create(
            unit=self.unit,
            slug="jacobs",
            name="Jacobs",
            billing_type="Private pay",
            status="Active",
            primary_contact="Jakera Jacobs",
        )
        self.child = PortalChild.objects.create(
            family=self.family, name="Jordan Jacobs", is_active=True, billing_plan="Weekly"
        )
        post_charge(
            self.family,
            "Jordan Jacobs",
            "tuition",
            Decimal("35.00"),
            date(2026, 9, 9),
            "CC WK 1 - weekly charge",
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

    def _login(self, area="admin"):
        self.client.force_login(self.admin)
        session = self.client.session
        session[PORTAL_AUTH_SESSION_KEY] = area
        session.save()

    def _row(self):
        report = build_admin_report("balances", {"status": "Active"})
        return next(row for row in report["rows"] if row["child"] == "Jordan Jacobs")

    def test_paid_starts_unchecked_and_keeps_ledger_amount(self):
        row = self._row()
        self.assertFalse(row["paid_checked"])
        self.assertEqual(row["paid"], "")
        self.assertEqual(row["amount_owe"], "35.00")
        self.assertEqual(row["child_id"], self.child.pk)

    def test_checking_paid_persists_and_does_not_delete_ledger(self):
        set_account_balance_paid(self.child, True, updated_by="Portal Admin")
        row = self._row()
        self.assertTrue(row["paid_checked"])
        self.assertEqual(row["paid"], "Yes")
        self.assertEqual(row["amount_owe"], "35.00")
        self.assertEqual(
            PortalLedgerEntry.objects.filter(family=self.family, entry_type="charge").count(),
            1,
        )
        self.assertFalse(PortalLedgerEntry.objects.filter(family=self.family, entry_type="payment").exists())
        mark = PortalAccountBalancePaidMark.objects.get(child=self.child)
        self.assertTrue(mark.is_paid)
        set_account_balance_paid(self.child, False, updated_by="Portal Admin")
        row = self._row()
        self.assertFalse(row["paid_checked"])
        self.assertEqual(row["amount_owe"], "35.00")

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_staff_checkbox_posts_and_prints_checked(self):
        self._login("admin")
        page = self.client.get(reverse("portal_admin_data_report", kwargs={"report_slug": "balances"}))
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, "portal-paid-box")
        self.assertContains(page, "portal-paid-print")
        self.assertContains(page, f'name="child_id" value="{self.child.pk}"')
        response = self.client.post(
            reverse("portal_account_balance_paid"),
            {
                "child_id": str(self.child.pk),
                "is_paid": "1",
                "next": reverse("portal_admin_data_report", kwargs={"report_slug": "balances"}),
            },
        )
        self.assertEqual(response.status_code, 302)
        self.child.refresh_from_db()
        self.assertTrue(PortalAccountBalancePaidMark.objects.get(child=self.child).is_paid)
        again = self.client.get(reverse("portal_admin_data_report", kwargs={"report_slug": "balances"}))
        self.assertContains(again, "portal-paid-box is-checked")
        self.assertContains(again, "portal-paid-print is-checked")
        csv_response = self.client.get(
            reverse("portal_admin_data_report", kwargs={"report_slug": "balances"}),
            {"format": "csv"},
        )
        self.assertIn("Yes", csv_response.content.decode())
        post_payment(self.family, "Jordan Jacobs", "35.00", date(2026, 9, 10), "Cash")
        self.assertEqual(
            PortalLedgerEntry.objects.filter(family=self.family, entry_type="payment").count(),
            1,
        )
        self.assertTrue(PortalAccountBalancePaidMark.objects.get(child=self.child).is_paid)
