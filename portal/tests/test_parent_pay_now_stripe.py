from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock, patch
from urllib.parse import parse_qs, urlparse

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from portal.billing_services import post_charge, post_credit
from portal.email_templates import parent_portal_url
from portal.models import (
    PortalChild,
    PortalFamily,
    PortalParentAccount,
    PortalPayment,
    PortalStaffAccount,
    PortalUnit,
)
from portal.staff_auth import PORTAL_AUTH_SESSION_KEY


class ParentPayNowStripeTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.unit = PortalUnit.objects.create(slug="school-18", name="School 18", is_active=True)
        self.family = PortalFamily.objects.create(unit=self.unit, slug="rivera", name="Rivera")
        self.child = PortalChild.objects.create(
            family=self.family,
            name="Ada Rivera",
            school="School 18",
            is_active=True,
        )
        self.parent_user = User.objects.create_user(
            username="parent:rivera",
            password="ParentPass123",
            email="rivera@example.com",
        )
        self.account = PortalParentAccount.objects.create(user=self.parent_user, family=self.family)
        self.admin = User.objects.create_user(username="staff:portaladmin", password="AdminPass123")
        PortalStaffAccount.objects.create(
            user=self.admin,
            unit=self.unit,
            display_name="Portal Admin",
            role="Portal admin",
            all_units_access=True,
            is_active=True,
        )

    def _login_parent(self, client=None):
        client = client or self.client
        client.force_login(self.parent_user)
        session = client.session
        session[PORTAL_AUTH_SESSION_KEY] = "parent"
        session.save()
        return client

    def _login_admin(self):
        self.client.force_login(self.admin)
        session = self.client.session
        session[PORTAL_AUTH_SESSION_KEY] = "admin"
        session.save()

    def _owe(self, amount="40.00"):
        post_charge(
            self.family,
            "Ada Rivera",
            "tuition",
            amount,
            date(2026, 9, 1),
            "Weekly tuition",
            notify=False,
        )

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_real_parent_pay_now_opens_payment_view(self):
        self._owe()
        self._login_parent()
        dashboard = self.client.get(reverse("portal_parent_page", kwargs={"page": "dashboard"}))
        self.assertEqual(dashboard.status_code, 200)
        self.assertContains(dashboard, reverse("portal_parent_payment"))
        self.assertContains(dashboard, "Pay now")
        self.assertNotContains(dashboard, "portal-preview-action")

        billing = self.client.get(reverse("portal_parent_page", kwargs={"page": "billing"}))
        self.assertContains(billing, reverse("portal_parent_payment"))
        self.assertContains(billing, "Pay now")

        payment = self.client.get(reverse("portal_parent_payment"))
        self.assertEqual(payment.status_code, 200)
        self.assertContains(payment, "Pay full balance")
        self.assertContains(payment, "Continue to review")
        self.assertNotContains(payment, 'name="amount" required')

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_zero_balance_pay_now_offers_pay_ahead(self):
        self._login_parent()
        payment = self.client.get(reverse("portal_parent_payment"))
        self.assertEqual(payment.status_code, 200)
        self.assertContains(payment, "Pay ahead")
        self.assertContains(payment, "Enter an amount to pay ahead")
        self.assertContains(payment, "Continue to review")

        preview = self.client.get(reverse("portal_parent_payment_preview"))
        self.assertEqual(preview.status_code, 302)
        self.assertEqual(preview.url, reverse("portal_parent_payment"))

        preview_ok = self.client.get(reverse("portal_parent_payment_preview"), {"amount": "25.00"})
        self.assertEqual(preview_ok.status_code, 200)
        self.assertContains(preview_ok, "$25.00")

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_pay_now_link_requires_parent_login(self):
        response = self.client.get(reverse("portal_parent_payment"))
        self.assertEqual(response.status_code, 302)
        parsed = urlparse(response.url)
        self.assertEqual(parsed.path, "/portal/login/")
        self.assertEqual(parse_qs(parsed.query).get("next"), ["/portal/parent/payment/"])

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_email_pay_link_goes_to_payment_page(self):
        self.assertTrue(parent_portal_url().endswith("/portal/parent/payment/"))
        with patch("portal.email_templates.send_site_email", return_value=1) as send_email:
            post_charge(
                self.family,
                "Ada Rivera",
                "tuition",
                "40.00",
                date(2026, 9, 8),
                "Weekly tuition",
            )
        message = send_email.call_args.kwargs["message"]
        self.assertIn("/portal/parent/payment/", message)
        self.assertNotIn("/portal/login/", message)
        self.assertIn("Pay now", message)

    @override_settings(PORTAL_PREVIEW_MODE=False, SITE_URL="https://yeanj.org")
    def test_email_pay_link_lands_on_payment_after_login(self):
        payment = reverse("portal_parent_payment")
        logged_out = self.client.get(payment)
        self.assertEqual(logged_out.status_code, 302)
        parsed = urlparse(logged_out.url)
        self.assertEqual(parsed.path, "/portal/login/")
        self.assertEqual(parse_qs(parsed.query).get("next"), [payment])

        signed_in = self.client.post(
            reverse("portal_parent_login"),
            {"username": "rivera", "password": "ParentPass123", "next": payment},
        )
        self.assertEqual(signed_in.status_code, 302)
        self.assertEqual(signed_in.url, payment)

        page = self.client.get(signed_in.url)
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, "Continue to review")

    @override_settings(PORTAL_PREVIEW_MODE=False, SITE_URL="https://yeanj.org")
    def test_absolute_site_url_next_still_opens_payment(self):
        signed_in = self.client.post(
            reverse("portal_parent_login"),
            {
                "username": "rivera",
                "password": "ParentPass123",
                "next": "https://yeanj.org/portal/parent/payment/",
            },
        )
        self.assertEqual(signed_in.status_code, 302)
        self.assertEqual(signed_in.url, reverse("portal_parent_payment"))

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_admin_parent_view_pay_now_does_not_create_checkout(self):
        self._owe()
        self._login_admin()
        preview = self.client.get(
            reverse("portal_admin_parent_preview", kwargs={"family_slug": "rivera"}),
            {"id": self.family.pk},
        )
        self.assertEqual(preview.status_code, 200)
        self.assertContains(preview, "Pay now")
        self.assertContains(preview, "portal-preview-action")
        self.assertContains(preview, "this does not charge a card")
        self.assertNotContains(preview, reverse("portal_parent_payment"))

        checkout = self.client.post(
            reverse("portal_parent_payment_checkout"),
            {"amount": "40.00"},
        )
        self.assertEqual(checkout.status_code, 302)
        self.assertIn("/portal/login/", checkout.url)
        self.assertFalse(PortalPayment.objects.filter(family=self.family).exists())

    @override_settings(
        PORTAL_PREVIEW_MODE=True,
        MEMBER_STRIPE_SECRET_KEY="sk_test_123",
        MEMBER_STRIPE_PUBLIC_KEY="pk_test_123",
    )
    @patch("portal.stripe_services.member_stripe")
    def test_preview_mode_checkout_does_not_create_stripe_session(self, member_stripe):
        response = self.client.post(reverse("portal_parent_payment_checkout"), {"amount": "40.00"})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("portal_parent_payment_complete"))
        member_stripe.assert_not_called()
        self.assertFalse(PortalPayment.objects.exists())

    @override_settings(
        PORTAL_PREVIEW_MODE=False,
        MEMBER_STRIPE_SECRET_KEY="sk_test_123",
        MEMBER_STRIPE_PUBLIC_KEY="pk_test_123",
    )
    def test_owing_family_review_shows_pay_with_stripe(self):
        self._owe()
        self._login_parent()
        payment = self.client.get(reverse("portal_parent_payment"))
        self.assertContains(payment, "Secure card checkout")
        self.assertNotContains(payment, "Card number")
        review = self.client.get(reverse("portal_parent_payment_preview"), {"amount": "40.00"})
        self.assertEqual(review.status_code, 200)
        self.assertContains(review, "Pay $")
        self.assertContains(review, "with Stripe")
        self.assertContains(review, reverse("portal_parent_payment_checkout"))

    @override_settings(
        PORTAL_PREVIEW_MODE=False,
        MEMBER_STRIPE_SECRET_KEY="sk_test_123",
        MEMBER_STRIPE_PUBLIC_KEY="pk_test_123",
    )
    @patch("portal.stripe_services.member_stripe")
    def test_owing_family_starts_stripe_checkout_session(self, member_stripe):
        self._owe()
        self._login_parent()
        stripe = MagicMock()
        stripe.Customer.create.return_value = MagicMock(id="cus_live")
        stripe.checkout.Session.create.return_value = MagicMock(
            id="cs_live_123",
            url="https://checkout.stripe.com/c/pay/cs_test_paynow",
        )
        member_stripe.return_value = stripe

        response = self.client.post(reverse("portal_parent_payment_checkout"), {"amount": "40.00"})
        self.assertEqual(response.status_code, 303)
        self.assertEqual(response["Location"], "https://checkout.stripe.com/c/pay/cs_test_paynow")
        payment = PortalPayment.objects.get(family=self.family)
        self.assertEqual(payment.status, PortalPayment.STATUS_PENDING)
        self.assertEqual(payment.stripe_session_id, "cs_live_123")
        self.assertEqual(payment.amount, Decimal("40.00"))
        kwargs = stripe.checkout.Session.create.call_args.kwargs
        self.assertEqual(kwargs["customer"], "cus_live")
        self.assertIn("{CHECKOUT_SESSION_ID}", kwargs["success_url"])

    @override_settings(
        PORTAL_PREVIEW_MODE=False,
        MEMBER_STRIPE_SECRET_KEY="sk_test_123",
        MEMBER_STRIPE_PUBLIC_KEY="pk_test_123",
    )
    @patch("portal.stripe_services.member_stripe")
    def test_stale_customer_and_blank_email_still_start_checkout(self, member_stripe):
        self.parent_user.email = ""
        self.parent_user.save(update_fields=["email"])
        self.account.stripe_customer_id = "cus_deleted"
        self.account.save(update_fields=["stripe_customer_id"])
        self._login_parent()

        stripe = MagicMock()
        stripe.Customer.retrieve.side_effect = Exception("No such customer: 'cus_deleted'")
        stripe.Customer.create.return_value = MagicMock(id="cus_new")
        stripe.checkout.Session.create.return_value = MagicMock(
            id="cs_recovered",
            url="https://checkout.stripe.com/c/pay/cs_recovered",
        )
        member_stripe.return_value = stripe

        response = self.client.post(reverse("portal_parent_payment_checkout"), {"amount": "25.00"})
        self.assertEqual(response.status_code, 303)
        self.assertEqual(response["Location"], "https://checkout.stripe.com/c/pay/cs_recovered")
        create_kwargs = stripe.Customer.create.call_args.kwargs
        self.assertNotIn("email", create_kwargs)
        self.account.refresh_from_db()
        self.assertEqual(self.account.stripe_customer_id, "cus_new")

    @override_settings(
        PORTAL_PREVIEW_MODE=False,
        MEMBER_STRIPE_SECRET_KEY="sk_test_123",
        MEMBER_STRIPE_PUBLIC_KEY="pk_test_123",
    )
    @patch("portal.stripe_services.member_stripe")
    def test_checkout_error_keeps_amount_and_shows_message(self, member_stripe):
        self._login_parent()
        stripe = MagicMock()
        stripe.Customer.create.return_value = MagicMock(id="cus_live")
        stripe.checkout.Session.create.side_effect = Exception("api_error")
        member_stripe.return_value = stripe

        response = self.client.post(reverse("portal_parent_payment_checkout"), {"amount": "25.00"})
        self.assertEqual(response.status_code, 302)
        self.assertIn("amount=25.00", response.url)
        self.assertFalse(PortalPayment.objects.filter(family=self.family).exists())
        follow = self.client.get(response.url)
        self.assertEqual(follow.status_code, 200)
        self.assertContains(follow, "could not start Stripe checkout")

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_credit_balance_still_shows_pay_now(self):
        post_credit(self.family, "Ada Rivera", "25.00", date(2026, 9, 2), "Overpayment")
        self._login_parent()
        dashboard = self.client.get(reverse("portal_parent_page", kwargs={"page": "dashboard"}))
        self.assertContains(dashboard, "Pay now")
        self.assertContains(dashboard, reverse("portal_parent_payment"))
        payment = self.client.get(reverse("portal_parent_payment"))
        self.assertContains(payment, "Pay ahead")
        self.assertContains(payment, "$25.00 credit")
