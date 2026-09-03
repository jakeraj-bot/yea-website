from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from portal.models import PortalFamily, PortalParentAccount, PortalStaffAccount, PortalSupportViewSession, PortalUnit
from portal.staff_auth import PORTAL_AUTH_SESSION_KEY
from portal.support_view import mask_parent_account_cards
from portal.tests.test_family_units import _make_application


class ParentSupportViewTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.unit = PortalUnit.objects.create(slug="school-18", name="School 18", is_active=True)
        self.family = PortalFamily.objects.create(unit=self.unit, slug="rivera", name="Rivera")
        _make_application(self.family)
        self.admin = User.objects.create_user(username="staff:portaladmin", password="AdminPass123")
        PortalStaffAccount.objects.create(
            user=self.admin,
            unit=self.unit,
            display_name="Portal Admin",
            role="Portal admin",
            all_units_access=True,
            is_active=True,
        )
        self.staff = User.objects.create_user(username="staff:unitstaff", password="StaffPass123")
        PortalStaffAccount.objects.create(
            user=self.staff,
            unit=self.unit,
            display_name="Unit Staff",
            role="Unit director",
            all_units_access=False,
            is_active=True,
        )
        self.parent_user = User.objects.create_user(
            username="parent:rivera",
            password="ParentPass123",
            email="rivera@example.com",
        )
        self.parent_account = PortalParentAccount.objects.create(user=self.parent_user, family=self.family)

    def _login(self, user, area, client=None):
        client = client or self.client
        client.force_login(user)
        session = client.session
        session[PORTAL_AUTH_SESSION_KEY] = area
        session.save()

    def test_mask_parent_account_cards_hides_numbers_and_password(self):
        masked = mask_parent_account_cards(
            {
                "password_preview": "SecretPass!",
                "stripe_customer_id": "cus_123",
                "payment_methods": [
                    {
                        "label": "Visa ending 4242",
                        "last4": "4242",
                        "expires": "08/2028",
                        "brand": "Visa",
                        "stripe_id": "pm_123",
                    }
                ],
            }
        )
        self.assertEqual(masked["password_preview"], "")
        self.assertEqual(masked["stripe_customer_id"], "")
        self.assertEqual(masked["payment_methods"][0]["label"], "Visa on file · ••••")
        self.assertEqual(masked["payment_methods"][0]["last4"], "••••")
        self.assertEqual(masked["payment_methods"][0]["expires"], "••/••")
        self.assertEqual(masked["payment_methods"][0]["stripe_id"], "")

    def test_mask_billing_hides_ending_last4(self):
        from portal.support_view import mask_billing_card_mentions, mask_receipt_card_mentions

        billing = mask_billing_card_mentions(
            {"ledger": [{"description": "Autopay — card ending 4242", "amount": "-80.00"}]}
        )
        self.assertEqual(billing["ledger"][0]["description"], "Autopay — card ending ••••")
        receipts = mask_receipt_card_mentions([{"method": "Visa ending 4242", "description": "Paid"}])
        self.assertEqual(receipts[0]["method"], "Visa ending ••••")

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_admin_can_open_parent_view_without_parent_login(self):
        self.parent_account.delete()
        self._login(self.admin, "admin")
        response = self.client.get(
            reverse("portal_admin_parent_preview", kwargs={"family_slug": "rivera"}),
            {"id": self.family.pk},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Support view")
        self.assertContains(response, "Rivera")
        self.assertContains(response, "Card numbers are hidden")
        self.assertTrue(
            PortalSupportViewSession.objects.filter(family=self.family, ended_at__isnull=True).exists()
        )

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_admin_parent_view_masks_cards(self):
        self._login(self.admin, "admin")
        with self.settings(PORTAL_PREVIEW_MODE=False):
            from unittest.mock import patch

            with patch(
                "portal.parent_services.get_account_live",
                return_value={
                    "login_email": "rivera@example.com",
                    "username": "rivera",
                    "password_preview": "SecretPass!",
                    "payment_methods": [
                        {
                            "label": "Visa ending 4242",
                            "last4": "4242",
                            "expires": "08/2028",
                            "brand": "Visa",
                        }
                    ],
                },
            ):
                response = self.client.get(
                    reverse("portal_admin_parent_preview_page", kwargs={"family_slug": "rivera", "page": "account"}),
                    {"id": self.family.pk},
                )
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Visa ending 4242")
        self.assertNotContains(response, "SecretPass!")
        self.assertContains(response, "Visa on file · ••••")
        self.assertNotContains(response, "+ Add payment method")
        self.assertNotContains(response, 'id="toggle-password-display"')

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_admin_billing_preview_masks_ledger_last4(self):
        self._login(self.admin, "admin")
        from unittest.mock import patch

        with patch(
            "portal.parent_services.build_parent_preview_live",
            return_value={
                "key": "rivera",
                "label": "Private pay",
                "family_name": "Rivera",
                "billing": {
                    "payment_type": "Private pay",
                    "running_balance": "10.00",
                    "balance_due": "10.00",
                    "has_credit": False,
                    "account_credit": "0.00",
                    "children": [],
                    "ledger": [{"date": "2026-09-05", "child": "Ada", "type": "payment", "description": "Autopay — card ending 4242", "amount": "-10.00"}],
                },
                "profile": {},
                "dashboard": {"balance": "10.00"},
            },
        ):
            response = self.client.get(
                reverse("portal_admin_parent_preview_page", kwargs={"family_slug": "rivera", "page": "billing"}),
                {"id": self.family.pk},
            )
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "ending 4242")
        self.assertContains(response, "ending ••••")
        self.assertContains(response, "Pay and add-card actions are hidden")

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_sample_parent_portal_does_not_need_parent_account(self):
        self._login(self.admin, "admin")
        response = self.client.get(reverse("portal_admin_parent_preview_sample"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Sample parent portal")
        self.assertFalse(PortalSupportViewSession.objects.exists())
        missing = self.client.get(
            reverse("portal_admin_parent_preview_sample_page", kwargs={"page": "not-a-page"})
        )
        self.assertEqual(missing.status_code, 404)

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_unit_staff_cannot_open_admin_parent_view(self):
        self._login(self.staff, "staff")
        response = self.client.get(
            reverse("portal_admin_parent_preview", kwargs={"family_slug": "rivera"}),
            {"id": self.family.pk},
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn("/portal/admin/login/", response.url)

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_parent_sees_notice_while_admin_view_is_open(self):
        self._login(self.admin, "admin")
        self.client.get(
            reverse("portal_admin_parent_preview", kwargs={"family_slug": "rivera"}),
            {"id": self.family.pk},
        )
        parent_client = self.client_class()
        self._login(self.parent_user, "parent", parent_client)
        response = parent_client.get(reverse("portal_parent_page", kwargs={"page": "dashboard"}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "A YEA admin is viewing your portal")
        self.assertNotContains(response, "Support view")

        self.client.post(
            reverse("portal_admin_parent_preview_end", kwargs={"family_slug": "rivera"}),
            {"family_id": self.family.pk},
        )
        session = PortalSupportViewSession.objects.get(family=self.family)
        self.assertIsNotNone(session.ended_at)
        after = parent_client.get(reverse("portal_parent_page", kwargs={"page": "dashboard"}))
        self.assertNotContains(after, "A YEA admin is viewing your portal")
