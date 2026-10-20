"""Settings → Email toggle stops automatic charge-posted mail; staff sends stay on."""

from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from portal.billing_services import (
    post_bulk_charges,
    post_charge,
    run_due_plan_charges,
    update_ledger_amount,
)
from portal.email_templates import send_late_payment_notices, send_updated_balance_email
from portal.member_admin import send_family_parent_email
from portal.models import (
    PortalChild,
    PortalFamily,
    PortalLedgerEntry,
    PortalOrgSetting,
    PortalParentAccount,
    PortalStaffAccount,
    PortalUnit,
)
from portal.owed_weeks import post_late_fees
from portal.payment_emails import (
    charge_posted_emails_enabled,
    set_charge_posted_emails_enabled,
)
from portal.staff_auth import PORTAL_AUTH_SESSION_KEY


def _parent_account(family, email):
    user = get_user_model().objects.create_user(
        username=f"parent:{family.slug}",
        password="ParentPass123",
        email=email,
    )
    return PortalParentAccount.objects.create(user=user, family=family)


class ChargePostedEmailToggleTests(TestCase):
    def setUp(self):
        self.unit = PortalUnit.objects.create(slug="school-18", name="School 18", is_active=True)
        self.family = PortalFamily.objects.create(
            unit=self.unit,
            slug="rivera",
            name="Rivera",
            status="Active",
        )
        self.child = PortalChild.objects.create(
            family=self.family, name="Ada Rivera", is_active=True
        )
        _parent_account(self.family, "parent@example.com")

    def _charge(self, *, notify=True, description="Weekly tuition — Ada Rivera"):
        return post_charge(
            self.family,
            self.child.name,
            "tuition",
            "40.00",
            date(2026, 9, 10),
            description,
            notify=notify,
        )

    def test_default_is_off(self):
        self.assertFalse(PortalOrgSetting.load().send_charge_posted_emails)
        self.assertFalse(charge_posted_emails_enabled())

    @patch("portal.email_templates.send_site_email", return_value=1)
    def test_posting_charge_does_not_email_when_toggle_is_off(self, send_email):
        self._charge()
        send_email.assert_not_called()
        self.assertTrue(
            PortalLedgerEntry.objects.filter(
                family=self.family, child_name="Ada Rivera", amount=Decimal("40.00")
            ).exists()
        )

    @patch("portal.email_templates.send_site_email", return_value=1)
    def test_posting_charge_emails_when_toggle_is_on(self, send_email):
        set_charge_posted_emails_enabled(True)
        self._charge()
        send_email.assert_called_once()
        message = send_email.call_args.kwargs["message"]
        self.assertIn("Ada Rivera", message)
        self.assertIn("40.00", message)

    @patch("portal.email_templates.send_site_email", return_value=1)
    def test_toggle_on_still_skips_inactive_child(self, send_email):
        set_charge_posted_emails_enabled(True)
        self.child.is_active = False
        self.child.save(update_fields=["is_active"])
        self._charge()
        send_email.assert_not_called()

    @patch("portal.email_templates.send_site_email", return_value=1)
    def test_bulk_post_today_does_not_email_when_toggle_is_off(self, send_email):
        posted = post_bulk_charges(
            [
                {
                    "family_slug": self.family.slug,
                    "child_name": self.child.name,
                    "charge_type": "tuition",
                    "amount": Decimal("40.00"),
                    "description": "Weekly tuition — Ada Rivera",
                }
            ],
            date(2026, 9, 10),
        )
        self.assertEqual(posted, 1)
        send_email.assert_not_called()

    @patch("portal.email_templates.send_site_email", return_value=1)
    def test_bulk_post_today_emails_when_toggle_is_on(self, send_email):
        set_charge_posted_emails_enabled(True)
        posted = post_bulk_charges(
            [
                {
                    "family_slug": self.family.slug,
                    "child_name": self.child.name,
                    "charge_type": "tuition",
                    "amount": Decimal("40.00"),
                    "description": "Weekly tuition — Ada Rivera",
                }
            ],
            date(2026, 9, 10),
        )
        self.assertEqual(posted, 1)
        send_email.assert_called_once()

    @patch("portal.email_templates.send_site_email", return_value=1)
    def test_weekly_plan_post_does_not_email_when_toggle_is_off(self, send_email):
        self.child.auto_charge = True
        self.child.billing_plan = "Weekly"
        self.child.billing_amount = Decimal("40.00")
        self.child.next_charge_date = date(2026, 9, 10)
        self.child.save(
            update_fields=["auto_charge", "billing_plan", "billing_amount", "next_charge_date"]
        )
        posted = run_due_plan_charges(today=date(2026, 9, 10), child=self.child)
        self.assertEqual(len(posted), 1)
        send_email.assert_not_called()

    @patch("portal.email_templates.send_site_email", return_value=1)
    def test_weekly_plan_post_emails_when_toggle_is_on(self, send_email):
        set_charge_posted_emails_enabled(True)
        self.child.auto_charge = True
        self.child.billing_plan = "Weekly"
        self.child.billing_amount = Decimal("40.00")
        self.child.next_charge_date = date(2026, 9, 10)
        self.child.save(
            update_fields=["auto_charge", "billing_plan", "billing_amount", "next_charge_date"]
        )
        posted = run_due_plan_charges(today=date(2026, 9, 10), child=self.child)
        self.assertEqual(len(posted), 1)
        send_email.assert_called_once()

    @patch("portal.email_templates.send_site_email", return_value=1)
    def test_late_fee_charge_does_not_email_when_toggle_is_off(self, send_email):
        posted = post_late_fees([self.child.pk], notify=True)
        self.assertEqual(len(posted), 1)
        send_email.assert_not_called()

    @patch("portal.member_admin.send_site_email", return_value=1)
    def test_staff_email_parent_still_sends_when_toggle_is_off(self, send_email):
        sent, total = send_family_parent_email(
            self.family, "Pickup", "Please pick up Ada at 4."
        )
        self.assertEqual((sent, total), (1, 1))
        send_email.assert_called_once()

    @patch("portal.email_templates.send_site_email", return_value=1)
    def test_send_updated_balance_still_sends_when_toggle_is_off(self, send_email):
        self._charge(notify=False)
        send_email.reset_mock()
        sent = send_updated_balance_email(self.family)
        self.assertEqual(sent, 1)
        send_email.assert_called_once()

    @patch("portal.email_templates.send_site_email", return_value=1)
    def test_billing_tab_edit_notify_still_sends_when_toggle_is_off(self, send_email):
        entry = self._charge(notify=False)
        send_email.reset_mock()
        update_ledger_amount(self.family, entry.pk, "20.00", notify=True)
        send_email.assert_called_once()
        self.assertIn("Your YEA balance was updated", send_email.call_args.kwargs["subject"])

    @patch("portal.member_admin.send_site_email", return_value=1)
    def test_friday_late_reminder_still_sends_when_toggle_is_off(self, send_email):
        self._charge(notify=False)
        sent, total = send_late_payment_notices()
        self.assertEqual((sent, total), (1, 1))
        send_email.assert_called_once()


class ChargePostedEmailSettingsPageTests(TestCase):
    def setUp(self):
        User = get_user_model()
        unit = PortalUnit.objects.create(slug="school-18", name="School 18", is_active=True)
        self.admin = User.objects.create_user(
            username="staff:portaladmin",
            password="AdminPass123",
            email="admin@yeanj.org",
        )
        PortalStaffAccount.objects.create(
            user=self.admin,
            unit=unit,
            display_name="Portal Admin",
            role="Portal admin",
            all_units_access=True,
            is_active=True,
        )
        self.client.force_login(self.admin)
        session = self.client.session
        session[PORTAL_AUTH_SESSION_KEY] = "admin"
        session.save()

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_fees_page_points_to_settings_toggle(self):
        page = self.client.get(reverse("portal_admin_page", kwargs={"page": "fees"}))
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, "Settings → Email")
        self.assertContains(page, "Keep this charge-notice template available")
        self.assertNotContains(page, "Send this email when a charge is posted")
