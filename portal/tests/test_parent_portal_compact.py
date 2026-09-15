from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from portal.billing_services import post_charge, post_credit
from portal.demo_data import YEA_COMPANY, enrich_receipt_for_print
from django.utils import timezone
from portal.models import PortalChild, PortalFamily, PortalParentAccount, PortalPayment, PortalUnit
from portal.parent_i18n import COOKIE_NAME, YEA_ORG_NAME, YEA_PHONE
from portal.staff_auth import PORTAL_AUTH_SESSION_KEY


class ParentPortalCompactI18nTests(TestCase):
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
    def test_dashboard_is_compact_with_pay_now_and_no_before_care_paragraph(self):
        self._login_parent()
        page = self._dashboard()
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, "Pay now")
        self.assertContains(page, reverse("portal_parent_payment"))
        self.assertContains(page, "Add another child")
        self.assertNotContains(page, "Enrolling another child?")
        self.assertNotContains(page, "Already applied for after-school?")
        self.assertNotContains(page, "+ Before care")
        self.assertNotContains(page, "Billing and portal questions — Jakera Jacobs")
        self.assertNotContains(page, "Sample receipt preview")
        self.assertContains(page, "How to pay")
        self.assertContains(page, "parent-pay-howto.mp4")
        self.assertContains(page, "Cómo pagar")
        self.assertContains(page, reverse("portal_parent_page", kwargs={"page": "help"}))
        self.assertNotContains(page, "How to pay your balance")
        self.assertNotContains(page, "portal-pay-howto-steps")

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_billing_has_pay_now_at_top(self):
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
        billing = self.client.get(reverse("portal_parent_page", kwargs={"page": "billing"}))
        self.assertContains(billing, "Pay now")
        self.assertContains(billing, reverse("portal_parent_payment"))
        self.assertContains(billing, "$40.00")
        html = billing.content.decode()
        self.assertLess(html.find("Pay now"), html.find("Charges"))

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_help_page_has_categories_with_before_care_copy(self):
        self._login_parent()
        page = self.client.get(reverse("portal_parent_page", kwargs={"page": "help"}))
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, "Applications")
        self.assertContains(page, "Before care")
        self.assertContains(page, "After care")
        self.assertContains(page, "Billing")
        self.assertContains(page, "Payments")
        self.assertContains(page, "Profile")
        self.assertContains(page, "Already applied for after-school?")
        self.assertContains(page, "+ Before care")
        self.assertContains(page, "Contact us")

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_language_cookie_switches_parent_portal(self):
        self._login_parent()
        english = self._dashboard()
        self.assertContains(english, "Dashboard")
        self.assertContains(english, "Pay now")
        self.assertContains(english, 'name="lang" value="es"')
        switch = self.client.post(
            reverse("portal_parent_set_language"),
            {"lang": "es", "next": reverse("portal_parent_page", kwargs={"page": "dashboard"})},
        )
        self.assertEqual(switch.status_code, 302)
        self.assertEqual(switch.cookies[COOKIE_NAME].value, "es")
        spanish = self._dashboard()
        self.assertContains(spanish, "Pagar ahora")
        self.assertContains(spanish, "Inicio")
        self.assertContains(spanish, "Ayuda")
        self.assertNotContains(spanish, ">Dashboard<")
        billing = self.client.get(reverse("portal_parent_page", kwargs={"page": "billing"}))
        self.assertContains(billing, "Facturación y saldo")
        self.assertContains(billing, "Pagar ahora")
        help_page = self.client.get(reverse("portal_parent_page", kwargs={"page": "help"}))
        self.assertContains(help_page, "Ayuda")
        self.assertContains(help_page, "Solicitudes")
        receipts = self.client.get(reverse("portal_parent_page", kwargs={"page": "receipts"}))
        self.assertContains(receipts, "Recibos")
        self.client.post(
            reverse("portal_parent_set_language"),
            {"lang": "en", "next": reverse("portal_parent_page", kwargs={"page": "dashboard"})},
        )
        back = self._dashboard()
        self.assertContains(back, "Pay now")

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_language_cookie_on_request_without_post(self):
        self._login_parent()
        self.client.cookies[COOKIE_NAME] = "es"
        page = self._dashboard()
        self.assertContains(page, "Pagar ahora")

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_receipt_org_name_and_last_payment_only(self):
        self.assertEqual(YEA_COMPANY["name"], "Youth Education Academy")
        self.assertEqual(YEA_COMPANY["phone"], "609-357-8608")
        self.assertEqual(YEA_ORG_NAME, "Youth Education Academy")
        self.assertEqual(YEA_PHONE, "609-357-8608")
        payment = PortalPayment.objects.create(
            family=self.family,
            amount="40.00",
            total_charged="41.50",
            status=PortalPayment.STATUS_PAID,
            receipt_no="RCPT-260901-001",
            method_label="Visa ending 4242",
            paid_at=timezone.now(),
        )
        self._login_parent()
        page = self.client.get(reverse("portal_parent_page", kwargs={"page": "receipts"}))
        self.assertEqual(page.status_code, 200)
        self.assertNotContains(page, "Sample receipt preview")
        self.assertNotContains(page, "Youth Enrichment Academy")
        self.assertNotContains(page, "Jakera Jacobs")
        self.assertNotContains(page, "973-555-0100")
        self.assertContains(page, "Youth Education Academy")
        self.assertContains(page, "609-357-8608")
        self.assertContains(page, "Last payment")
        self.assertContains(page, payment.receipt_no)
        printed = enrich_receipt_for_print(
            {
                "reference": payment.receipt_no,
                "date": "2026-09-01",
                "amount": "40.00",
                "method": "Card — Visa ending 4242",
                "description": "Weekly tuition",
                "child": "Ada Rivera",
            },
            "private-pay",
            family=self.family,
        )
        self.assertEqual(printed["received_from"], "Youth Education Academy")
        self.assertEqual(printed["received_by"], "Youth Education Academy")
        self.assertEqual(printed["company_name"], "Youth Education Academy")
        self.assertEqual(printed["company_phone"], "609-357-8608")

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_header_balance_matches_household_ledger(self):
        post_charge(
            self.family,
            "Ada Rivera",
            "tuition",
            "40.00",
            date(2026, 9, 1),
            "Weekly tuition",
            notify=False,
        )
        post_credit(self.family, "Ada Rivera", "10.00", date(2026, 9, 2), "Payment")
        self._login_parent()
        page = self._dashboard()
        self.assertContains(page, "$30.00")
        self.assertContains(page, "Family balance")
        self.assertContains(page, "portal-header-balance")
        self.assertNotContains(page, "Running balance")

    def test_spanish_catalog_covers_english_keys(self):
        from portal.parent_i18n import _STRINGS

        missing = sorted(set(_STRINGS["en"]) - set(_STRINGS["es"]))
        self.assertEqual(missing, [])
