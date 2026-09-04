from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse

from portal.models import (
    PortalFamily,
    PortalParentAccount,
    PortalPayment,
    PortalProcessingFee,
    PortalUnit,
)
from portal.processing_fees import calculate_card_processing_fee, checkout_line_items
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
