from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from portal.billing_services import post_charge
from portal.models import (
    PortalChild,
    PortalFamily,
    PortalParentAccount,
    PortalPayment,
    PortalStaffAccount,
    PortalUnit,
)
from portal.parent_i18n import COOKIE_NAME
from portal.staff_auth import PORTAL_AUTH_SESSION_KEY


class ParentPwaTests(TestCase):
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
        self.admin = User.objects.create_user(username="staff:portaladmin", password="AdminPass123")
        PortalStaffAccount.objects.create(
            user=self.admin,
            unit=self.unit,
            display_name="Portal Admin",
            role="Portal admin",
            all_units_access=True,
            is_active=True,
        )

    def _login_parent(self):
        self.client.force_login(self.parent_user)
        session = self.client.session
        session[PORTAL_AUTH_SESSION_KEY] = "parent"
        session.save()

    def _login_admin(self):
        self.client.force_login(self.admin)
        session = self.client.session
        session[PORTAL_AUTH_SESSION_KEY] = "admin"
        session.save()

    def test_manifest_names_yea_parent_portal(self):
        response = self.client.get(reverse("portal_parent_manifest"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("application/manifest+json", response["Content-Type"])
        data = response.json()
        self.assertEqual(data["name"], "YEA Parent Portal")
        self.assertEqual(data["short_name"], "YEA Parent")
        self.assertEqual(data["display"], "standalone")
        self.assertEqual(data["start_url"], reverse("portal_parent_page", kwargs={"page": "dashboard"}))
        self.assertEqual(data["scope"], "/portal/")
        srcs = [icon["src"] for icon in data["icons"]]
        self.assertTrue(any("yea-parent-192.png" in src for src in srcs))
        self.assertTrue(any("yea-parent-512.png" in src for src in srcs))
        self.assertTrue(any(icon.get("purpose") == "maskable" for icon in data["icons"]))

    def test_service_worker_handles_fetch(self):
        response = self.client.get(reverse("portal_parent_sw"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("javascript", response["Content-Type"])
        self.assertEqual(response["Service-Worker-Allowed"], "/portal/")
        self.assertContains(response, 'addEventListener("fetch"')
        self.assertContains(response, "Capacitor")

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_parent_pages_have_pwa_tags_phone_nav_and_a2hs(self):
        self._login_parent()
        dashboard = self.client.get(reverse("portal_parent_page", kwargs={"page": "dashboard"}))
        self.assertEqual(dashboard.status_code, 200)
        self.assertContains(dashboard, "YEA Parent Portal")
        self.assertContains(dashboard, 'name="apple-mobile-web-app-capable"')
        self.assertContains(dashboard, reverse("portal_parent_manifest"))
        self.assertContains(dashboard, "yea-parent-180.png")
        self.assertContains(dashboard, "portal-parent-phone-nav")
        self.assertContains(dashboard, "yea-a2hs")
        self.assertContains(dashboard, "Add YEA Parent Portal to your Home Screen")
        self.assertContains(dashboard, "tap the Share button")
        self.assertContains(dashboard, "Add to Home screen")
        self.assertContains(dashboard, reverse("portal_parent_payment"))
        self.assertContains(dashboard, "portal-phone-secondary")
        html = dashboard.content.decode()
        self.assertIn('href="' + reverse("portal_parent_page", kwargs={"page": "receipts"}), html)
        self.assertIn(
            'href="' + reverse("portal_parent_page", kwargs={"page": "emergency-contacts"}),
            html,
        )
        self.assertIn('href="' + reverse("portal_parent_page", kwargs={"page": "help"}), html)
        self.assertContains(dashboard, "More")
        pay = self.client.get(reverse("portal_parent_payment"))
        self.assertContains(pay, "portal-parent-fat-btn")
        receipts = self.client.get(reverse("portal_parent_page", kwargs={"page": "receipts"}))
        self.assertContains(receipts, "portal-parent-phone-nav")
        self.assertContains(receipts, "Receipts")
        contacts = self.client.get(reverse("portal_parent_page", kwargs={"page": "emergency-contacts"}))
        self.assertContains(contacts, "portal-parent-fat-btn")
        help_page = self.client.get(reverse("portal_parent_page", kwargs={"page": "help"}))
        self.assertContains(help_page, "portal-help-cats")
        account = self.client.get(reverse("portal_parent_page", kwargs={"page": "account"}))
        self.assertContains(account, "App Store wrap later")
        self.assertContains(account, "$99/year")

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_spanish_a2hs_and_tabs(self):
        self._login_parent()
        self.client.cookies[COOKIE_NAME] = "es"
        dashboard = self.client.get(reverse("portal_parent_page", kwargs={"page": "dashboard"}))
        self.assertContains(dashboard, "Agregue YEA Parent Portal a la pantalla de inicio")
        self.assertContains(dashboard, "Agregar a pantalla de inicio")
        self.assertContains(dashboard, "Pagar")
        self.assertContains(dashboard, "Recibos")
        self.assertContains(dashboard, "Contactos")
        self.assertContains(dashboard, "Ayuda")
        self.assertContains(dashboard, "Más")
        self.assertContains(dashboard, "Ahora no")
        account = self.client.get(reverse("portal_parent_page", kwargs={"page": "account"}))
        self.assertContains(account, "$99")
        self.assertNotContains(account, "App Store wrap later")

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_login_and_admin_ready_for_home_screen_app(self):
        login = self.client.get(reverse("portal_parent_login"))
        self.assertEqual(login.status_code, 200)
        self.assertContains(login, "YEA Parent Portal")
        self.assertContains(login, reverse("portal_parent_manifest"))
        self.assertContains(login, "yea-a2hs")
        self._login_admin()
        admin = self.client.get(reverse("portal_admin_page", kwargs={"page": "dashboard"}))
        self.assertContains(admin, "App Store wrap later")
        self.assertContains(admin, "$99/year")

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_pay_now_still_uses_stripe_checkout_path(self):
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
        dashboard = self.client.get(reverse("portal_parent_page", kwargs={"page": "dashboard"}))
        self.assertContains(dashboard, reverse("portal_parent_payment"))
        self.assertNotContains(dashboard, "portal-preview-action")
        payment = self.client.get(reverse("portal_parent_payment"))
        self.assertEqual(payment.status_code, 200)
        self.assertContains(payment, reverse("portal_parent_payment_preview"))
        self.assertContains(payment, "$40.00")

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_receipts_phone_cards_when_history_exists(self):
        PortalPayment.objects.create(
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
        self.assertContains(page, "portal-receipt-cards")
        self.assertContains(page, "RCPT-260901-001")
        self.assertContains(page, "portal-parent-fat-btn")
