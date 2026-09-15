from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from portal.billing_services import post_charge, post_credit
from portal.models import PortalChild, PortalFamily, PortalParentAccount, PortalUnit
from portal.staff_auth import PORTAL_AUTH_SESSION_KEY


class ParentPaymentWalkthroughTests(TestCase):
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
        self.parent_user = User.objects.create_user(username="parent:rivera", password="ParentPass123")
        PortalParentAccount.objects.create(user=self.parent_user, family=self.family)

    def _login_parent(self):
        self.client.force_login(self.parent_user)
        session = self.client.session
        session[PORTAL_AUTH_SESSION_KEY] = "parent"
        session.save()

    def _dashboard(self):
        return self.client.get(reverse("portal_parent_page", kwargs={"page": "dashboard"}))

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_dashboard_shows_pay_video_in_english_and_spanish(self):
        self._login_parent()
        page = self._dashboard()
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, "How to pay")
        self.assertContains(page, "Cómo pagar")
        self.assertContains(page, "yea_parent_lang")
        self.assertContains(page, "parent-pay-howto.mp4")
        self.assertContains(page, "Pay now")
        self.assertContains(page, "Pay with Stripe")
        self.assertContains(page, "Pagar con Stripe")
        self.assertContains(page, reverse("portal_parent_page", kwargs={"page": "help"}))
        self.assertNotContains(page, "How to use this page")
        self.assertNotContains(page, "How to start the day")
        self.assertNotContains(page, "Mail a check")
        self.assertNotContains(page, "portal-pay-howto-steps")

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_payment_walkthrough_is_a_compact_video_card(self):
        self._login_parent()
        page = self._dashboard()
        self.assertContains(page, 'id="parent-pay-howto"')
        self.assertContains(page, "portal-pay-howto-video")
        self.assertContains(page, "portal-pay-howto-caption")
        self.assertContains(page, reverse("portal_parent_page", kwargs={"page": "help"}))

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_dashboard_header_shows_family_balance_and_pay_now(self):
        post_charge(
            self.family,
            "Ada Rivera",
            "tuition",
            "40.00",
            date(2026, 9, 1),
            "Weekly tuition",
            notify=False,
        )
        self._login_parent()
        page = self._dashboard()
        self.assertContains(page, "portal-dash-hero-balance is-due")
        self.assertContains(page, "Family balance")
        self.assertContains(page, "Pay now")
        self.assertContains(page, "$40.00")
        billing = self.client.get(reverse("portal_parent_page", kwargs={"page": "billing"}))
        self.assertContains(billing, "Family running balance")
        self.assertContains(billing, "$40.00")
        self.assertContains(billing, "Pay now")

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_dashboard_header_shows_zero_and_credit_clearly(self):
        self._login_parent()
        zero_page = self._dashboard()
        self.assertContains(zero_page, "$0.00")
        self.assertContains(zero_page, "portal-dash-hero-balance is-zero")
        self.assertNotContains(zero_page, "$0.00 credit")
        self.assertNotContains(zero_page, "portal-dash-hero-balance is-credit")

        post_credit(self.family, "Ada Rivera", "25.00", date(2026, 9, 2), "Overpayment")
        credit_page = self._dashboard()
        self.assertContains(credit_page, "Family balance")
        self.assertContains(credit_page, "$25.00 credit")
        self.assertContains(credit_page, "portal-dash-hero-balance is-credit")
        billing = self.client.get(reverse("portal_parent_page", kwargs={"page": "billing"}))
        self.assertContains(billing, "$25.00 credit")
        self.assertContains(billing, "Account credit")
