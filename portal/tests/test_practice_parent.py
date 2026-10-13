from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from enrollment.models import EmergencyContact
from portal.models import (
    PortalChild,
    PortalFamily,
    PortalLedgerEntry,
    PortalOrgSetting,
    PortalPayment,
    PortalStaffAccount,
    PortalUnit,
)
from portal.practice_parent import (
    PRACTICE_CHILD_NAME,
    PRACTICE_FAMILY_SLUG,
    PRACTICE_PASSWORD,
    PRACTICE_USERNAME,
    ensure_practice_parent_account,
    is_practice_family,
)
from portal.staff_auth import PORTAL_AUTH_SESSION_KEY


@override_settings(PORTAL_PREVIEW_MODE=False, ALLOW_PORTAL_PRACTICE=True)
class PracticeParentPortalTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.unit = PortalUnit.objects.create(slug="school-18", name="School 18", is_active=True)
        self.live_family = PortalFamily.objects.create(
            unit=self.unit,
            slug="rivera",
            name="Rivera",
            primary_contact="Ada Rivera",
            status="Active",
            balance=Decimal("40.00"),
        )
        PortalChild.objects.create(
            family=self.live_family,
            name="Jordan Rivera",
            grade="4th",
            is_active=True,
            unit=self.unit,
        )
        self.admin = User.objects.create_user(username="staff:portaladmin", password="AdminPass123")
        PortalStaffAccount.objects.create(
            user=self.admin,
            unit=self.unit,
            display_name="Portal Admin",
            role="Portal admin",
            all_units_access=True,
            is_active=True,
        )

    def _login_admin(self):
        self.client.force_login(self.admin)
        session = self.client.session
        session[PORTAL_AUTH_SESSION_KEY] = "admin"
        session.save()

    def test_practice_family_is_isolated_from_live_household(self):
        account = ensure_practice_parent_account()
        self.assertTrue(is_practice_family(account.family))
        self.assertEqual(account.family.slug, PRACTICE_FAMILY_SLUG)
        self.assertNotEqual(account.family.pk, self.live_family.pk)
        self.assertTrue(account.family.children.filter(name=PRACTICE_CHILD_NAME).exists())
        self.assertGreater(account.family.balance, 0)

    def test_admin_open_signs_into_practice_parent_with_banner_and_pay_now(self):
        self._login_admin()
        response = self.client.post(reverse("portal_admin_practice_parent_open"), follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Practice parent — test payments only, not a real family.")
        self.assertContains(response, "Practice family")
        self.assertContains(response, "Pay now")
        self.assertContains(response, reverse("portal_parent_payment"))
        self.assertNotContains(response, "portal-preview-action")
        self.assertContains(response, 'name="lang" value="es"')
        self.assertContains(response, reverse("portal_parent_page", kwargs={"page": "help"}))
        self.assertEqual(self.client.session[PORTAL_AUTH_SESSION_KEY], "parent")

    def test_parent_view_still_does_not_charge(self):
        self._login_admin()
        preview = self.client.get(
            reverse("portal_admin_parent_preview", kwargs={"family_slug": "rivera"}),
            {"id": self.live_family.pk},
        )
        self.assertEqual(preview.status_code, 200)
        self.assertContains(preview, "portal-preview-action")
        self.assertContains(preview, "this does not charge a card")
        self.assertNotContains(preview, reverse("portal_parent_payment"))

    def test_sample_parent_portal_stays_read_only(self):
        self._login_admin()
        sample = self.client.get(reverse("portal_admin_parent_preview_sample"))
        self.assertEqual(sample.status_code, 200)
        self.assertContains(sample, "Sample parent portal")
        self.assertContains(sample, "portal-preview-action")
        self.assertNotContains(sample, reverse("portal_parent_payment"))

    def test_practice_pay_now_records_test_receipt_without_live_stripe(self):
        self._login_admin()
        self.client.post(reverse("portal_admin_practice_parent_open"))
        pay = self.client.get(reverse("portal_parent_payment"))
        self.assertEqual(pay.status_code, 200)
        self.assertContains(pay, "Practice family")
        checkout = self.client.post(
            reverse("portal_parent_payment_checkout"),
            {"amount": "85.00"},
            follow=True,
        )
        self.assertEqual(checkout.status_code, 200)
        self.assertContains(checkout, "Youth Education Academy")
        family = PortalFamily.objects.get(slug=PRACTICE_FAMILY_SLUG)
        self.assertTrue(PortalPayment.objects.filter(family=family, status="paid").exists())
        self.assertFalse(PortalPayment.objects.filter(family=self.live_family).exists())
        self.assertEqual(self.live_family.balance, Decimal("40.00"))

    @override_settings(MEMBER_STRIPE_SECRET_KEY="sk_live_not_for_practice", MEMBER_STRIPE_PUBLIC_KEY="pk_live_not_for_practice")
    def test_practice_never_uses_live_stripe_keys(self):
        self._login_admin()
        self.client.post(reverse("portal_admin_practice_parent_open"))
        with patch("portal.stripe_services.create_balance_checkout_session") as create_session:
            response = self.client.post(
                reverse("portal_parent_payment_checkout"),
                {"amount": "85.00"},
                follow=True,
            )
        create_session.assert_not_called()
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Youth Education Academy")

    @override_settings(MEMBER_STRIPE_SECRET_KEY="sk_test_practice", MEMBER_STRIPE_PUBLIC_KEY="pk_test_practice")
    def test_practice_uses_stripe_test_checkout_when_keys_are_test(self):
        self._login_admin()
        self.client.post(reverse("portal_admin_practice_parent_open"))

        class FakeSession:
            url = "https://checkout.stripe.com/c/pay/cs_test_practice"

        with patch("portal.stripe_services.create_balance_checkout_session", return_value=FakeSession()) as create_session:
            response = self.client.post(reverse("portal_parent_payment_checkout"), {"amount": "85.00"})
        create_session.assert_called_once()
        self.assertIn(response.status_code, (302, 303))
        self.assertEqual(response.url, FakeSession.url)

    def test_practice_parent_can_add_emergency_contact(self):
        self._login_admin()
        self.client.post(reverse("portal_admin_practice_parent_open"))
        page = self.client.get(reverse("portal_parent_page", kwargs={"page": "emergency-contacts"}))
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, PRACTICE_CHILD_NAME)
        child = PortalFamily.objects.get(slug=PRACTICE_FAMILY_SLUG).children.get(name=PRACTICE_CHILD_NAME)
        added = self.client.post(
            reverse("portal_parent_emergency_contact_add"),
            {
                "child_id": child.pk,
                "first_name": "Riley",
                "last_name": "Friend",
                "phone": "555-0190",
                "relationship": "Friend",
                "authorized_pickup": "on",
            },
            follow=True,
        )
        self.assertEqual(added.status_code, 200)
        self.assertContains(added, "Riley Friend")
        self.assertTrue(EmergencyContact.objects.filter(first_name="Riley", last_name="Friend").exists())
        self.assertFalse(
            EmergencyContact.objects.filter(
                application__portal_family=self.live_family,
                first_name="Riley",
            ).exists()
        )

    def test_spanish_toggle_on_practice_portal(self):
        self._login_admin()
        self.client.post(reverse("portal_admin_practice_parent_open"))
        switched = self.client.post(
            reverse("portal_parent_set_language"),
            {"lang": "es", "next": reverse("portal_parent_page", kwargs={"page": "dashboard"})},
            follow=True,
        )
        self.assertEqual(switched.status_code, 200)
        self.assertContains(switched, "Padre de práctica")
        self.assertContains(switched, "Pagar ahora")

    def test_back_to_admin_restores_admin_session(self):
        self._login_admin()
        self.client.post(reverse("portal_admin_practice_parent_open"))
        back = self.client.post(reverse("portal_admin_practice_parent_end"), follow=True)
        self.assertEqual(back.status_code, 200)
        self.assertEqual(self.client.session[PORTAL_AUTH_SESSION_KEY], "admin")
        self.assertContains(back, "Organization admin")

    def test_practice_hidden_on_production_unless_enabled(self):
        PortalOrgSetting.load()
        with override_settings(
            ALLOW_PORTAL_PRACTICE=False,
            ALLOW_PORTAL_DEMO_SEED=False,
            DEBUG=False,
            STAGING_SITE=False,
        ):
            self._login_admin()
            dashboard = self.client.get(reverse("portal_admin_page", kwargs={"page": "dashboard"}))
            self.assertNotContains(dashboard, "Open practice parent")
            blocked = self.client.post(reverse("portal_admin_practice_parent_open"))
            self.assertEqual(blocked.status_code, 302)
            self.assertIn("/portal/admin/", blocked.url)

    def test_direct_login_works_with_seed_password(self):
        ensure_practice_parent_account()
        logged_in = self.client.post(
            reverse("portal_parent_login"),
            {"username": PRACTICE_USERNAME, "password": PRACTICE_PASSWORD},
            follow=True,
        )
        self.assertEqual(logged_in.status_code, 200)
        self.assertContains(logged_in, "Practice parent — test payments only, not a real family.")

    def test_practice_family_does_not_appear_on_all_families(self):
        ensure_practice_parent_account()
        self._login_admin()
        families = self.client.get(reverse("portal_admin_page", kwargs={"page": "families"}))
        self.assertEqual(families.status_code, 200)
        self.assertNotContains(families, "Practice family")
        self.assertContains(families, "Rivera")

    def test_unit_staff_cannot_open_practice_parent(self):
        User = get_user_model()
        staff = User.objects.create_user(username="staff:unitstaff", password="StaffPass123")
        PortalStaffAccount.objects.create(
            user=staff,
            unit=self.unit,
            display_name="Unit Staff",
            role="Unit director",
            all_units_access=False,
            is_active=True,
        )
        self.client.force_login(staff)
        session = self.client.session
        session[PORTAL_AUTH_SESSION_KEY] = "staff"
        session.save()
        response = self.client.post(reverse("portal_admin_practice_parent_open"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/portal/admin/login/", response.url)
        self.assertFalse(PortalLedgerEntry.objects.filter(family=self.live_family).exists())
