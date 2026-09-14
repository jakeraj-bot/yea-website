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
    def test_dashboard_shows_english_and_spanish_payment_steps(self):
        self._login_parent()
        page = self._dashboard()
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, "How to pay your balance")
        self.assertContains(page, "Cómo pagar su saldo")
        self.assertContains(page, 'data-lang-set="en"')
        self.assertContains(page, 'data-lang-set="es"')
        self.assertContains(page, "yea_parent_lang")
        self.assertContains(page, "Billing &amp; balance")
        self.assertContains(page, "Pay balance")
        self.assertContains(page, "Pay ahead")
        self.assertContains(page, "Balance by child")
        self.assertContains(page, "Charges &amp; payments")
        self.assertContains(page, "Continue to review")
        self.assertContains(page, "Pay … with Stripe")
        self.assertContains(page, "Payment received")
        self.assertContains(page, "check or money order at the site")
        self.assertContains(page, "cheque o giro postal")
        self.assertContains(page, "en el sitio")
        self.assertContains(page, reverse("portal_parent_page", kwargs={"page": "billing"}))
        self.assertNotContains(page, "How to use this page")
        self.assertNotContains(page, "How to start the day")
        self.assertNotContains(page, "Pick a child")
        self.assertNotContains(page, "Mail a check")

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_payment_walkthrough_is_collapsed_by_default(self):
        self._login_parent()
        page = self._dashboard()
        self.assertContains(page, 'id="parent-pay-howto"')
        self.assertContains(page, "portal-collapse")
        self.assertContains(page, "is-collapsed")
        self.assertContains(page, "portal-collapse-toggle")
        self.assertContains(page, "portal-collapse-body")
        self.assertContains(page, 'aria-expanded="false"')
        self.assertContains(page, "yea-portal-collapse")
        self.assertContains(page, 'data-collapse-key="how to pay your balance"')
        self.assertContains(page, 'data-lang-title="en"')
        self.assertContains(page, 'data-lang-title="es"')
        self.assertContains(page, "Contact us")

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_dashboard_header_shows_family_balance_and_keeps_bottom_stat(self):
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
        self.assertContains(page, "Running balance")
        self.assertContains(page, "$40.00", count=2)
        billing = self.client.get(reverse("portal_parent_page", kwargs={"page": "billing"}))
        self.assertContains(billing, "Family running balance")
        self.assertContains(billing, "$40.00")
        self.assertNotContains(billing, "portal-dash-hero-balance")

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_dashboard_header_shows_zero_and_credit_clearly(self):
        self._login_parent()
        zero_page = self._dashboard()
        self.assertContains(zero_page, "$0.00", count=2)
        self.assertContains(zero_page, "portal-dash-hero-balance is-zero")
        self.assertNotContains(zero_page, "$0.00 credit")
        self.assertNotContains(zero_page, "portal-dash-hero-balance is-credit")

        post_credit(self.family, "Ada Rivera", "25.00", date(2026, 9, 2), "Overpayment")
        credit_page = self._dashboard()
        self.assertContains(credit_page, "Family balance")
        self.assertContains(credit_page, "$25.00 credit")
        self.assertContains(credit_page, "portal-dash-hero-balance is-credit")
        self.assertContains(credit_page, "Running balance")
        self.assertContains(credit_page, "$-25.00")
        billing = self.client.get(reverse("portal_parent_page", kwargs={"page": "billing"}))
        self.assertContains(billing, "$25.00 credit")
        self.assertContains(billing, "Account credit")
