from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from portal.admin_reports import build_admin_report
from portal.billing_services import post_charge
from portal.models import (
    PortalChild,
    PortalFamily,
    PortalLedgerEntry,
    PortalParentAccount,
    PortalPayment,
    PortalStaffAccount,
    PortalUnit,
)
from portal.parent_services import get_receipts_live, payment_to_receipt_dict
from portal.staff_auth import PORTAL_AUTH_SESSION_KEY


class StaffPaymentDateTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.unit = PortalUnit.objects.create(slug="school-18", name="School 18", is_active=True)
        self.family = PortalFamily.objects.create(
            unit=self.unit,
            slug="jacobs",
            name="Jacobs",
            status="Active",
        )
        self.child = PortalChild.objects.create(family=self.family, name="Jordan Jacobs", is_active=True)
        self.admin = User.objects.create_user(username="staff:portaladmin", password="AdminPass123")
        PortalStaffAccount.objects.create(
            user=self.admin,
            unit=self.unit,
            display_name="Portal Admin",
            role="Portal admin",
            all_units_access=True,
            is_active=True,
        )
        self.parent_user = User.objects.create_user(
            username="parent:jacobs",
            password="ParentPass123",
            email="jacobs@example.com",
        )
        PortalParentAccount.objects.create(user=self.parent_user, family=self.family)

    def _login_admin(self):
        self.client.force_login(self.admin)
        session = self.client.session
        session[PORTAL_AUTH_SESSION_KEY] = "admin"
        session.save()

    def _login_parent(self):
        self.client.force_login(self.parent_user)
        session = self.client.session
        session[PORTAL_AUTH_SESSION_KEY] = "parent"
        session.save()

    def _owe(self, amount="50.00"):
        post_charge(
            self.family,
            "Jordan Jacobs",
            "tuition",
            amount,
            timezone.localdate(),
            "Weekly tuition",
            notify=False,
        )

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_record_payment_form_has_payment_date_defaulting_to_today(self):
        self._login_admin()
        billing = self.client.get(reverse("portal_admin_family_billing", kwargs={"family_slug": "jacobs"}))
        self.assertEqual(billing.status_code, 200)
        self.assertContains(billing, 'id="pay-date"')
        self.assertContains(billing, "Payment date")
        self.assertContains(billing, timezone.localdate().isoformat())
        self.assertContains(billing, "day the money was received")
        self.assertContains(billing, "Payment date is the day the money was received")
        self.assertNotContains(billing, 'id="card-pay-date"')
        html = billing.content.decode()
        card_start = html.find('id="card-payment-panel"')
        card_chunk = html[card_start : card_start + 1800]
        self.assertNotIn('name="date"', card_chunk)

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_recording_check_dated_yesterday_uses_that_date_on_ledger_and_outstanding(self):
        self._owe("50.00")
        yesterday = timezone.localdate() - timedelta(days=1)
        self._login_admin()
        response = self.client.post(
            reverse("portal_staff_billing_action", kwargs={"family_slug": "jacobs"}),
            {
                "portal_area": "admin",
                "action": "payment",
                "child_name": "Jordan Jacobs",
                "amount": "20.00",
                "method": "check",
                "check_number": "2201",
                "note": "Weekly tuition",
                "date": yesterday.isoformat(),
            },
        )
        self.assertEqual(response.status_code, 302)
        entry = PortalLedgerEntry.objects.get(family=self.family, entry_type="payment")
        self.assertEqual(entry.date, yesterday)
        self.assertEqual(entry.amount, Decimal("-20.00"))
        self.assertEqual(entry.reference_number, "2201")
        payment = PortalPayment.objects.get(family=self.family)
        self.assertEqual(timezone.localtime(payment.paid_at).date(), yesterday)
        self.family.refresh_from_db()
        self.assertEqual(self.family.balance, Decimal("30.00"))
        billing = self.client.get(reverse("portal_admin_family_billing", kwargs={"family_slug": "jacobs"}))
        self.assertContains(billing, yesterday.isoformat())
        receipts = get_receipts_live(self.family)
        self.assertEqual(receipts[0]["date"], yesterday.strftime("%b %d, %Y"))
        printed = payment_to_receipt_dict(payment, "private-pay")
        self.assertEqual(printed["date"], yesterday.isoformat())
        report = build_admin_report("payments", {})
        row = next(item for item in report["rows"] if item["family"] == "Jacobs")
        self.assertEqual(row["date"], yesterday.isoformat())
        outstanding = build_admin_report("balances", {})
        child_row = next(item for item in outstanding["rows"] if item["child"] == "Jordan Jacobs")
        self.assertEqual(child_row["balance"], "30.00")
        self.assertEqual(outstanding["outstanding"], "30.00")

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_blank_payment_date_defaults_to_today(self):
        self._owe("40.00")
        today = timezone.localdate()
        self._login_admin()
        response = self.client.post(
            reverse("portal_staff_billing_action", kwargs={"family_slug": "jacobs"}),
            {
                "portal_area": "admin",
                "action": "payment",
                "child_name": "Jordan Jacobs",
                "amount": "15.00",
                "method": "cash",
                "note": "Cash at desk",
            },
        )
        self.assertEqual(response.status_code, 302)
        entry = PortalLedgerEntry.objects.get(family=self.family, entry_type="payment")
        self.assertEqual(entry.date, today)
        payment = PortalPayment.objects.get(family=self.family)
        self.assertEqual(timezone.localtime(payment.paid_at).date(), today)
        self.family.refresh_from_db()
        self.assertEqual(self.family.balance, Decimal("25.00"))

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_parent_stripe_pay_page_has_no_backdate_field(self):
        self._login_parent()
        page = self.client.get(reverse("portal_parent_payment"))
        self.assertEqual(page.status_code, 200)
        self.assertNotContains(page, "Payment date")
        self.assertNotContains(page, 'id="pay-date"')

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_agency_copay_form_has_payment_date(self):
        self.client.force_login(self.admin)
        session = self.client.session
        session[PORTAL_AUTH_SESSION_KEY] = "staff"
        session.save()
        page = self.client.get(reverse("portal_staff_page", kwargs={"page": "agency"}))
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, 'id="copay-date"')
        self.assertContains(page, "Payment date")
        self.assertContains(page, timezone.localdate().isoformat())
