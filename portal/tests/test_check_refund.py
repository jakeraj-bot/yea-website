from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from portal.billing_services import (
    get_org_ledger_live,
    post_charge,
    post_check_refund,
    post_payment,
    prepare_billing_for_staff,
)
from portal.family_list import household_balance
from portal.models import (
    PortalChild,
    PortalFamily,
    PortalLedgerEntry,
    PortalPayment,
    PortalStaffAccount,
    PortalUnit,
)
from portal.parent_services import get_billing_live
from portal.staff_auth import PORTAL_AUTH_SESSION_KEY, billing_permissions_for_staff
from portal.tests.test_family_units import _make_application


class CheckRefundTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.unit = PortalUnit.objects.create(slug="school-18", name="School 18", is_active=True)
        self.family = PortalFamily.objects.create(unit=self.unit, slug="jacobs", name="Jacobs")
        PortalChild.objects.create(family=self.family, name="Jordan Jacobs", is_active=True)
        _make_application(self.family)
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

    def _login(self, user, area):
        self.client.force_login(user)
        session = self.client.session
        session[PORTAL_AUTH_SESSION_KEY] = area
        session.save()

    def test_post_check_refund_requires_check_number(self):
        with self.assertRaises(ValueError):
            post_check_refund(self.family, "40.00", "")
        self.assertFalse(PortalLedgerEntry.objects.filter(family=self.family).exists())

    def test_post_check_refund_stores_number_not_description(self):
        post_charge(self.family, "Jordan Jacobs", "manual", "100.00", date(2026, 9, 8), "Tuition")
        post_payment(self.family, "Jordan Jacobs", "100.00", date(2026, 9, 9), "Cash", "Desk cash")
        post_check_refund(
            self.family,
            "40.00",
            "4521",
            date(2026, 9, 12),
            "Overpayment returned",
            "Jordan Jacobs",
        )
        entry = PortalLedgerEntry.objects.get(family=self.family, entry_type="refund")
        self.assertEqual(entry.amount, Decimal("40.00"))
        self.assertEqual(entry.reference_number, "4521")
        self.assertEqual(entry.description, "Overpayment returned")
        self.assertTrue(entry.is_manual)
        self.assertEqual(entry.child_name, "Jordan Jacobs")
        self.assertEqual(entry.date, date(2026, 9, 12))
        self.assertEqual(household_balance(self.family), Decimal("40.00"))
        self.assertFalse(PortalPayment.objects.filter(family=self.family, method_label="Check").exists())

        billing = prepare_billing_for_staff(
            self.family, billing_permissions_for_staff(None, portal_area="admin")
        )
        row = next(item for item in billing["ledger"] if item["type"] == "refund")
        self.assertEqual(row["description"], "Overpayment returned")
        self.assertEqual(row["reference_display"], "Check #4521")
        self.assertNotIn("4521", row["description"])

        parent = get_billing_live(self.family)
        parent_row = next(item for item in parent["ledger"] if item["type"] == "refund")
        self.assertEqual(parent_row["reference_display"], "Check #4521")
        self.assertNotIn("4521", parent_row["description"])

        org_row = next(
            item
            for item in get_org_ledger_live()
            if item["family_slug"] == "jacobs" and item["type"] == "refund"
        )
        self.assertEqual(org_row["reference_display"], "Check #4521")

    def test_default_reason_is_check_refund(self):
        post_check_refund(self.family, "10.00", "99")
        entry = PortalLedgerEntry.objects.get(family=self.family, entry_type="refund")
        self.assertEqual(entry.description, "Check refund")
        self.assertEqual(entry.reference_number, "99")

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_admin_can_post_check_refund_from_refund_page(self):
        self._login(self.admin, "admin")
        refund = self.client.get(reverse("portal_admin_family_refund", kwargs={"family_slug": "jacobs"}))
        self.assertEqual(refund.status_code, 200)
        self.assertContains(refund, "Check refund")
        self.assertContains(refund, 'name="action" value="check_refund"', html=False)
        self.assertContains(refund, "QuickBooks")
        self.assertContains(refund, "does not go through Stripe")
        self.assertEqual(refund.context["page_guide"]["key"], "family-refund")

        response = self.client.post(
            reverse("portal_staff_billing_action", kwargs={"family_slug": "jacobs"}),
            {
                "portal_area": "admin",
                "action": "check_refund",
                "child_name": "",
                "amount": "25.00",
                "date": "2026-09-15",
                "check_number": "8801",
                "reason": "Returned overpayment",
                "next": reverse("portal_admin_family_billing", kwargs={"family_slug": "jacobs"}),
            },
        )
        self.assertEqual(response.status_code, 302)
        entry = PortalLedgerEntry.objects.get(family=self.family, entry_type="refund")
        self.assertEqual(entry.reference_number, "8801")
        self.assertEqual(entry.description, "Returned overpayment")
        self.assertEqual(entry.amount, Decimal("25.00"))
        billing = self.client.get(reverse("portal_admin_family_billing", kwargs={"family_slug": "jacobs"}))
        self.assertContains(billing, "Returned overpayment")
        self.assertContains(billing, "Check #8801")
        self.assertNotContains(billing, "Check #8801 — Returned overpayment")

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_admin_check_refund_without_number_is_rejected(self):
        self._login(self.admin, "admin")
        response = self.client.post(
            reverse("portal_staff_billing_action", kwargs={"family_slug": "jacobs"}),
            {
                "portal_area": "admin",
                "action": "check_refund",
                "amount": "25.00",
                "reason": "Returned overpayment",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(PortalLedgerEntry.objects.filter(family=self.family).exists())

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_unit_staff_cannot_post_check_refund(self):
        self._login(self.staff, "staff")
        response = self.client.post(
            reverse("portal_staff_billing_action", kwargs={"family_slug": "jacobs"}),
            {
                "portal_area": "staff",
                "action": "check_refund",
                "amount": "25.00",
                "check_number": "8801",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(PortalLedgerEntry.objects.filter(family=self.family).exists())
