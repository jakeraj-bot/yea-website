from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from portal.models import PortalFamily, PortalParentAccount, PortalUnit
from portal.staff_auth import PORTAL_AUTH_SESSION_KEY


class ParentPaymentWalkthroughTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.unit = PortalUnit.objects.create(slug="school-18", name="School 18", is_active=True)
        self.family = PortalFamily.objects.create(unit=self.unit, slug="rivera", name="Rivera")
        self.parent_user = User.objects.create_user(username="parent:rivera", password="ParentPass123")
        PortalParentAccount.objects.create(user=self.parent_user, family=self.family)

    def _login_parent(self):
        self.client.force_login(self.parent_user)
        session = self.client.session
        session[PORTAL_AUTH_SESSION_KEY] = "parent"
        session.save()

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_dashboard_shows_english_and_spanish_payment_steps(self):
        self._login_parent()
        page = self.client.get(reverse("portal_parent_page", kwargs={"page": "dashboard"}))
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
