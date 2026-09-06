from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings
from django.urls import reverse


def _stripe_event(event_type, session=None):
    """Looks like stripe 15 Event: attributes only, no .get()."""
    return SimpleNamespace(
        type=event_type,
        data=SimpleNamespace(object=session or SimpleNamespace()),
    )


class StripeWebhookTests(TestCase):
    @override_settings(MEMBER_STRIPE_SECRET_KEY="sk_test_123", MEMBER_STRIPE_PUBLIC_KEY="pk_test_123")
    @patch("portal.stripe_services.confirm_checkout_payment")
    @patch("portal.stripe_services.member_stripe")
    def test_stripe_event_object_without_get_returns_200(self, member_stripe, confirm):
        stripe = MagicMock()
        stripe.Webhook.construct_event.return_value = _stripe_event(
            "checkout.session.completed",
            SimpleNamespace(id="cs_live_123", payment_status="paid"),
        )
        member_stripe.return_value = stripe
        with override_settings(MEMBER_STRIPE_WEBHOOK_SECRET="whsec_test"):
            response = self.client.post(
                reverse("portal_member_stripe_webhook"),
                data=b'{"id":"evt_1"}',
                content_type="application/json",
                HTTP_STRIPE_SIGNATURE="t=1,v1=abc",
            )
        self.assertEqual(response.status_code, 200)
        confirm.assert_called_once_with("cs_live_123")

    @override_settings(
        MEMBER_STRIPE_SECRET_KEY="sk_test_123",
        MEMBER_STRIPE_PUBLIC_KEY="pk_test_123",
        MEMBER_STRIPE_WEBHOOK_SECRET="whsec_test",
    )
    @patch("portal.stripe_services.member_stripe")
    def test_other_event_types_return_200(self, member_stripe):
        stripe = MagicMock()
        stripe.Webhook.construct_event.return_value = _stripe_event("payout.paid")
        member_stripe.return_value = stripe
        response = self.client.post(
            reverse("portal_member_stripe_webhook"),
            data=b"{}",
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE="t=1,v1=abc",
        )
        self.assertEqual(response.status_code, 200)

    @override_settings(
        MEMBER_STRIPE_SECRET_KEY="sk_test_123",
        MEMBER_STRIPE_PUBLIC_KEY="pk_test_123",
        MEMBER_STRIPE_WEBHOOK_SECRET="whsec_test",
    )
    @patch("portal.stripe_services.member_stripe")
    def test_bad_signature_returns_400(self, member_stripe):
        stripe = MagicMock()
        stripe.Webhook.construct_event.side_effect = ValueError("bad signature")
        member_stripe.return_value = stripe
        response = self.client.post(
            reverse("portal_member_stripe_webhook"),
            data=b"{}",
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE="t=1,v1=bad",
        )
        self.assertEqual(response.status_code, 400)

    @override_settings(
        MEMBER_STRIPE_SECRET_KEY="sk_test_123",
        MEMBER_STRIPE_PUBLIC_KEY="pk_test_123",
        MEMBER_STRIPE_WEBHOOK_SECRET="whsec_test",
    )
    @patch("portal.stripe_services.confirm_checkout_payment", side_effect=RuntimeError("boom"))
    @patch("portal.stripe_services.member_stripe")
    def test_confirm_failure_still_returns_200(self, member_stripe, _confirm):
        stripe = MagicMock()
        stripe.Webhook.construct_event.return_value = _stripe_event(
            "checkout.session.completed",
            SimpleNamespace(id="cs_live_err", payment_status="paid"),
        )
        member_stripe.return_value = stripe
        response = self.client.post(
            reverse("portal_member_stripe_webhook"),
            data=b"{}",
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE="t=1,v1=abc",
        )
        self.assertEqual(response.status_code, 200)
