from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from types import SimpleNamespace

from portal.admin_reports import build_admin_report
from portal.billing_services import post_payment, prepare_billing_for_staff
from portal.models import (
    PortalFamily,
    PortalLedgerEntry,
    PortalParentAccount,
    PortalPayment,
    PortalProcessingFee,
    PortalUnit,
)
from portal.parent_services import record_successful_payment
from portal.processing_fees import (
    apply_stripe_session_totals,
    backfill_stripe_fee_totals,
    calculate_card_processing_fee,
    checkout_line_items,
    payment_charged_totals,
)
from portal.staff_auth import PORTAL_AUTH_SESSION_KEY


class ProcessingFeeCalculationTests(TestCase):
    def test_default_fee_is_two_point_nine_percent_plus_thirty_cents(self):
        totals = calculate_card_processing_fee("80.00")
        self.assertEqual(totals["subtotal"], "80.00")
        self.assertEqual(totals["fee"], "2.62")
        self.assertEqual(totals["total"], "82.62")

    def test_zero_amount_has_no_fee(self):
        totals = calculate_card_processing_fee("0")
        self.assertEqual(totals["fee"], "0.00")
        self.assertEqual(totals["total"], "0.00")

    def test_uses_admin_configured_processing_fee(self):
        PortalProcessingFee.objects.create(
            name="Card processing",
            percent=Decimal("3.00"),
            flat_amount=Decimal("0.50"),
            is_active=True,
        )
        totals = calculate_card_processing_fee("100.00")
        self.assertEqual(totals["fee"], "3.50")
        self.assertEqual(totals["total"], "103.50")

    def test_checkout_line_items_include_program_and_fee(self):
        unit = PortalUnit.objects.create(slug="school-18", name="School 18", is_active=True)
        family = PortalFamily.objects.create(unit=unit, slug="rivera", name="Rivera")
        payment = PortalPayment.objects.create(family=family, amount=Decimal("80.00"), payment_kind="balance")
        items = checkout_line_items(payment, "YEA family balance — Rivera", "Program balance payment ($80.00)")
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0]["price_data"]["unit_amount"], 8000)
        self.assertEqual(items[1]["price_data"]["unit_amount"], 262)
        self.assertEqual(items[1]["price_data"]["product_data"]["name"], "Card processing fee")
        payment.refresh_from_db()
        self.assertEqual(payment.fee_amount, Decimal("2.62"))
        self.assertEqual(payment.total_charged, Decimal("82.62"))


class ParentPaymentFeeDisplayTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.unit = PortalUnit.objects.create(slug="school-18", name="School 18", is_active=True)
        self.family = PortalFamily.objects.create(unit=self.unit, slug="rivera", name="Rivera", balance=Decimal("80.00"))
        self.parent = User.objects.create_user(username="parent:rivera", password="ParentPass123", email="r@example.com")
        PortalParentAccount.objects.create(user=self.parent, family=self.family)

    def _login_parent(self):
        self.client.force_login(self.parent)
        session = self.client.session
        session[PORTAL_AUTH_SESSION_KEY] = "parent"
        session.save()

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_payment_page_shows_processing_fee(self):
        self._login_parent()
        response = self.client.get(reverse("portal_parent_payment"), {"amount": "80.00"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Card processing fee")
        self.assertContains(response, "2.62")
        self.assertContains(response, "82.62")
        self.assertContains(response, 'data-fee-percent="2.90"')
        self.assertContains(response, 'data-fee-flat="0.30"')

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_review_page_shows_fee_in_total(self):
        self._login_parent()
        response = self.client.get(reverse("portal_parent_payment_preview"), {"amount": "80.00"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Card processing fee")
        self.assertContains(response, "$2.62")
        self.assertContains(response, "$82.62")


class StripeCheckoutFeeTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.unit = PortalUnit.objects.create(slug="school-18", name="School 18", is_active=True)
        self.family = PortalFamily.objects.create(unit=self.unit, slug="rivera", name="Rivera")
        self.parent = User.objects.create_user(username="parent:rivera", password="ParentPass123", email="r@example.com")
        self.account = PortalParentAccount.objects.create(user=self.parent, family=self.family)
        self.factory = RequestFactory()

    @override_settings(MEMBER_STRIPE_SECRET_KEY="sk_test_123", MEMBER_STRIPE_PUBLIC_KEY="pk_test_123")
    @patch("portal.stripe_services.member_stripe")
    def test_balance_checkout_charges_program_plus_fee(self, member_stripe):
        stripe = MagicMock()
        stripe.Customer.create.return_value = MagicMock(id="cus_123")
        stripe.checkout.Session.create.return_value = MagicMock(id="cs_123", url="https://stripe.test/pay")
        member_stripe.return_value = stripe

        payment = PortalPayment.objects.create(family=self.family, amount=Decimal("80.00"), payment_kind="balance")
        request = self.factory.post("/portal/parent/payment/checkout/")
        request.user = self.parent
        from portal.stripe_services import create_balance_checkout_session

        create_balance_checkout_session(request, payment)
        kwargs = stripe.checkout.Session.create.call_args.kwargs
        items = kwargs["line_items"]
        self.assertEqual(items[0]["price_data"]["unit_amount"], 8000)
        self.assertEqual(items[1]["price_data"]["unit_amount"], 262)
        payment.refresh_from_db()
        self.assertEqual(payment.total_charged, Decimal("82.62"))
        self.assertEqual(payment.stripe_session_id, "cs_123")


class StripeFeeLedgerAndReportTests(TestCase):
    def setUp(self):
        self.unit = PortalUnit.objects.create(slug="school-18", name="School 18", is_active=True)
        self.family = PortalFamily.objects.create(
            unit=self.unit,
            slug="rivera",
            name="Rivera",
            balance=Decimal("80.00"),
            primary_contact="Ada Rivera",
        )

    def test_ledger_shows_stripe_total_and_fee_without_double_count(self):
        payment = PortalPayment.objects.create(
            family=self.family,
            amount=Decimal("80.00"),
            fee_amount=Decimal("2.62"),
            total_charged=Decimal("82.62"),
            payment_kind="balance",
            stripe_session_id="cs_fee_1",
            stripe_payment_intent_id="pi_fee_1",
            stripe_charge_id="ch_fee_1",
        )
        record_successful_payment(payment, method_label="Visa ending 4242")
        self.family.refresh_from_db()
        self.assertEqual(self.family.balance, Decimal("0.00"))
        entry = PortalLedgerEntry.objects.get(family=self.family, entry_type="payment")
        self.assertEqual(entry.amount, Decimal("-80.00"))
        self.assertEqual(entry.fee_amount, Decimal("2.62"))
        billing = prepare_billing_for_staff(self.family, {"can_delete_charge": False})
        row = next(item for item in billing["ledger"] if item["type"] == "payment")
        self.assertEqual(row["amount"], "82.62")
        self.assertEqual(row["fee"], "2.62")
        self.assertEqual(row["applied"], "80.00")

    def test_session_amount_total_is_the_parent_charge(self):
        payment = PortalPayment.objects.create(
            family=self.family,
            amount=Decimal("80.00"),
            payment_kind="balance",
            stripe_session_id="cs_live_total",
        )
        apply_stripe_session_totals(payment, SimpleNamespace(amount_total=8262))
        payment.refresh_from_db()
        tuition, fee, charged = payment_charged_totals(payment)
        self.assertEqual(tuition, Decimal("80.00"))
        self.assertEqual(fee, Decimal("2.62"))
        self.assertEqual(charged, Decimal("82.62"))

    def test_payment_and_stripe_reports_use_charged_total(self):
        PortalPayment.objects.create(
            family=self.family,
            amount=Decimal("80.00"),
            fee_amount=Decimal("2.62"),
            total_charged=Decimal("82.62"),
            method_label="Visa ending 4242",
            status=PortalPayment.STATUS_PAID,
            stripe_session_id="cs_report_fee",
            stripe_payment_intent_id="pi_report_fee",
            stripe_charge_id="ch_report_fee",
            stripe_bank_status="waiting_for_bank",
            paid_at=timezone.now(),
        )
        payments = build_admin_report("payments", {})
        row = next(item for item in payments["rows"] if item["family"] == "Rivera")
        self.assertEqual(row["amount"], "82.62")
        self.assertEqual(row["fee"], "2.62")
        self.assertEqual(payments["summary"].split("·")[1].strip(), "$82.62 collected")
        settlement = build_admin_report("stripe-settlement", {})
        self.assertEqual(settlement["waiting_to_receive_total"], "82.62")
        self.assertEqual(settlement["pending_rows"][0]["amount"], "82.62")
        self.assertEqual(settlement["pending_rows"][0]["fee"], "2.62")

    def test_money_order_has_no_processing_fee(self):
        post_payment(self.family, "Ada Rivera", "18.00", timezone.localdate(), "Money order", "Money order #555", "555")
        payments = build_admin_report("payments", {})
        row = next(item for item in payments["rows"] if "Money order" in item["method"])
        self.assertEqual(row["amount"], "18.00")
        self.assertEqual(row["fee"], "")
        settlement = build_admin_report("stripe-settlement", {})
        self.assertTrue(all("Money order" not in (item["method"] or "") for item in settlement["rows"]))

    def test_historical_ledger_backfill_from_stored_stripe_totals(self):
        today = timezone.localdate()
        payment = PortalPayment.objects.create(
            family=self.family,
            amount=Decimal("80.00"),
            fee_amount=Decimal("2.62"),
            total_charged=Decimal("82.62"),
            method_label="Visa ending 4242",
            status=PortalPayment.STATUS_PAID,
            stripe_session_id="cs_hist",
            stripe_payment_intent_id="pi_hist",
            paid_at=timezone.now(),
            receipt_no="RCPT-HIST-001",
        )
        entry = PortalLedgerEntry.objects.create(
            family=self.family,
            date=today,
            entry_type="payment",
            description="Online payment — Visa ending 4242",
            amount=Decimal("-80.00"),
            reference_number="RCPT-HIST-001",
        )
        backfill_stripe_fee_totals([payment])
        entry.refresh_from_db()
        self.assertEqual(entry.fee_amount, Decimal("2.62"))
        ledger = build_admin_report("ledger", {})
        row = next(item for item in ledger["rows"] if item["family"] == "Rivera" and item["type"] == "payment")
        self.assertEqual(row["amount"], "-82.62")
        self.assertEqual(row["fee"], "2.62")
        self.assertIn("parents paid $82.62", ledger["summary"])
        self.assertIn("processing fees $2.62", ledger["summary"])
