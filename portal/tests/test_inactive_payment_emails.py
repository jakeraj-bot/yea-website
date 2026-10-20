"""Automatic payment emails stop for inactive members; mixed families stay billed for active kids."""

from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings

from enrollment.application_review import approve_application
from portal.billing_services import post_charge, run_due_plan_charges, update_ledger_amount
from portal.email_templates import (
    send_first_day_reminders,
    send_late_payment_notices,
    send_updated_balance_email,
)
from portal.member_admin import send_family_parent_email, send_parent_password_reset_link
from portal.models import (
    PortalChild,
    PortalFamily,
    PortalLedgerEntry,
    PortalParentAccount,
    PortalUnit,
)
from portal.payment_emails import set_charge_posted_emails_enabled
from portal.tests.test_care_program_filters import _make_app
from portal.tests.test_family_units import _make_application


def _parent_account(family, email):
    user = get_user_model().objects.create_user(
        username=f"parent:{family.slug}",
        password="ParentPass123",
        email=email,
    )
    return PortalParentAccount.objects.create(user=user, family=family)


class InactivePaymentEmailTests(TestCase):
    def setUp(self):
        self.unit = PortalUnit.objects.create(slug="school-18", name="School 18", is_active=True)
        self.family = PortalFamily.objects.create(
            unit=self.unit,
            slug="jacobs",
            name="Jacobs",
            status="Active",
        )
        self.maya = PortalChild.objects.create(family=self.family, name="Maya Jacobs", is_active=True)
        self.jordan = PortalChild.objects.create(family=self.family, name="Jordan Jacobs", is_active=True)
        _parent_account(self.family, "pat@example.com")
        set_charge_posted_emails_enabled(True)

    def _charge(self, child, amount, description, notify=True):
        return post_charge(
            self.family,
            child.name,
            "tuition",
            amount,
            date(2026, 9, 8),
            description,
            notify=notify,
        )

    @patch("portal.email_templates.send_site_email", return_value=1)
    def test_inactive_child_charge_does_not_email_parent(self, send_email):
        self.maya.is_active = False
        self.maya.save(update_fields=["is_active"])
        self._charge(self.maya, "40.00", "Weekly tuition — Maya Jacobs")
        send_email.assert_not_called()
        self.assertTrue(
            PortalLedgerEntry.objects.filter(
                family=self.family, child_name="Maya Jacobs", amount=Decimal("40.00")
            ).exists()
        )

    @patch("portal.email_templates.send_site_email", return_value=1)
    def test_active_sibling_charge_still_emails(self, send_email):
        self.maya.is_active = False
        self.maya.save(update_fields=["is_active"])
        self._charge(self.maya, "50.00", "Weekly tuition — Maya Jacobs")
        send_email.assert_not_called()
        self._charge(self.jordan, "40.00", "Weekly tuition — Jordan Jacobs")
        send_email.assert_called_once()
        message = send_email.call_args.kwargs["message"]
        self.assertIn("Jordan Jacobs", message)
        self.assertNotIn("Maya Jacobs", message)
        self.assertIn("Family balance (what the household owes): $40.00", message)

    @patch("portal.email_templates.send_site_email", return_value=1)
    def test_editing_inactive_child_charge_does_not_email(self, send_email):
        self.maya.is_active = False
        self.maya.save(update_fields=["is_active"])
        entry = self._charge(self.maya, "50.00", "Weekly tuition — Maya Jacobs", notify=False)
        send_email.reset_mock()
        update_ledger_amount(self.family, entry.pk, "20.00", notify=True)
        send_email.assert_not_called()

    @patch("portal.member_admin.send_site_email", return_value=1)
    def test_late_notice_skips_inactive_only_balance_and_keeps_active_sibling(self, send_email):
        self.maya.is_active = False
        self.maya.save(update_fields=["is_active"])
        self._charge(self.maya, "50.00", "Weekly tuition — Maya Jacobs", notify=False)
        self._charge(self.jordan, "40.00", "Weekly tuition — Jordan Jacobs", notify=False)
        sent, total = send_late_payment_notices()
        self.assertEqual((sent, total), (1, 1))
        message = send_email.call_args.kwargs["message"]
        self.assertIn("40.00", message)
        self.assertIn("Jordan Jacobs", message)
        self.assertNotIn("Maya Jacobs", message)

    @patch("portal.member_admin.send_site_email", return_value=1)
    def test_late_notice_skips_family_when_only_inactive_child_owes(self, send_email):
        self.maya.is_active = False
        self.maya.save(update_fields=["is_active"])
        self.jordan.is_active = False
        self.jordan.save(update_fields=["is_active"])
        self._charge(self.maya, "50.00", "Weekly tuition — Maya Jacobs", notify=False)
        with self.assertRaises(ValueError):
            send_late_payment_notices()
        send_email.assert_not_called()

    @patch("portal.member_admin.send_site_email", return_value=1)
    def test_first_day_reminder_skips_all_inactive_family(self, send_email):
        self.maya.is_active = False
        self.maya.save(update_fields=["is_active"])
        self.jordan.is_active = False
        self.jordan.save(update_fields=["is_active"])
        with self.assertRaises(ValueError):
            send_first_day_reminders()
        send_email.assert_not_called()

    @patch("portal.member_admin.send_site_email", return_value=1)
    def test_first_day_reminder_still_sends_when_one_child_is_active(self, send_email):
        self.maya.is_active = False
        self.maya.save(update_fields=["is_active"])
        sent, total = send_first_day_reminders()
        self.assertEqual((sent, total), (1, 1))
        send_email.assert_called_once()

    @patch("portal.member_admin.send_site_email", return_value=1)
    def test_staff_email_parent_still_sends_for_inactive_child(self, send_email):
        self.maya.is_active = False
        self.maya.save(update_fields=["is_active"])
        self.jordan.is_active = False
        self.jordan.save(update_fields=["is_active"])
        sent, total = send_family_parent_email(self.family, "Pickup", "Please pick up Maya at 4.")
        self.assertEqual((sent, total), (1, 1))
        send_email.assert_called_once()

    @patch("portal.email_templates.send_site_email", return_value=1)
    def test_staff_send_updated_balance_still_sends_for_inactive(self, send_email):
        self.maya.is_active = False
        self.maya.save(update_fields=["is_active"])
        self._charge(self.maya, "35.00", "Weekly tuition — Maya Jacobs", notify=False)
        send_email.reset_mock()
        sent = send_updated_balance_email(self.family)
        self.assertEqual(sent, 1)
        send_email.assert_called_once()

    @patch("portal.member_admin.send_site_email", return_value=1)
    def test_password_reset_still_sends_when_children_are_inactive(self, send_email):
        self.maya.is_active = False
        self.maya.save(update_fields=["is_active"])
        send_parent_password_reset_link(self.family)
        send_email.assert_called_once()
        self.assertEqual(send_email.call_args.kwargs["subject"], "Create a new parent portal password")

    @override_settings(SITE_URL="https://yeanj.org")
    def test_approve_email_still_sends_when_sibling_is_inactive(self):
        self.maya.is_active = False
        self.maya.save(update_fields=["is_active"])
        app = _make_application(self.family, status="under_review")
        app.student_first_name = "Nia"
        app.student_last_name = "Jacobs"
        app.save(update_fields=["student_first_name", "student_last_name"])
        mail.outbox.clear()
        approve_application(app, start_date=date(2026, 10, 6))
        approval = [sent for sent in mail.outbox if "can start on" in (sent.body or "")]
        self.assertEqual(len(approval), 1)
        self.assertIn("Nia Jacobs", approval[0].body)

    def test_scheduled_plan_job_does_not_auto_charge_inactive_child(self):
        self.maya.is_active = False
        self.maya.auto_charge = True
        self.maya.billing_plan = "Weekly"
        self.maya.billing_amount = Decimal("40.00")
        self.maya.next_charge_date = date(2026, 9, 10)
        self.maya.save(
            update_fields=["is_active", "auto_charge", "billing_plan", "billing_amount", "next_charge_date"]
        )
        posted = run_due_plan_charges(today=date(2026, 9, 10), child=self.maya)
        self.assertEqual(posted, [])
        self.assertFalse(
            PortalLedgerEntry.objects.filter(family=self.family, child_name="Maya Jacobs").exists()
        )


class PerApplicationInactivePaymentEmailTests(TestCase):
    def setUp(self):
        self.unit = PortalUnit.objects.create(slug="school-18", name="School 18", is_active=True)
        self.family = PortalFamily.objects.create(
            unit=self.unit,
            slug="cole",
            name="Cole",
            status="Active",
        )
        self.child = PortalChild.objects.create(family=self.family, name="Sam Cole", is_active=True)
        self.after_app = _make_app(self.family, self.child, program="after_school", status="approved")
        self.before_app = _make_app(self.family, self.child, program="before_care", status="approved")
        _parent_account(self.family, "cole@example.com")
        set_charge_posted_emails_enabled(True)

    @patch("portal.email_templates.send_site_email", return_value=1)
    def test_inactive_before_care_charge_does_not_email(self, send_email):
        self.before_app.is_active = False
        self.before_app.save(update_fields=["is_active"])
        post_charge(
            self.family,
            self.child.name,
            "tuition",
            "30.00",
            date(2026, 9, 8),
            "Before care — Weekly tuition — Sam Cole",
        )
        send_email.assert_not_called()

    @patch("portal.email_templates.send_site_email", return_value=1)
    def test_active_after_care_charge_still_emails(self, send_email):
        self.before_app.is_active = False
        self.before_app.save(update_fields=["is_active"])
        post_charge(
            self.family,
            self.child.name,
            "tuition",
            "70.00",
            date(2026, 9, 8),
            "After care — Weekly tuition — Sam Cole",
        )
        send_email.assert_called_once()
        self.assertIn("After care", send_email.call_args.kwargs["message"])
        self.assertIn("70.00", send_email.call_args.kwargs["message"])


class InactivePaymentEmailOutboxTests(TestCase):
    """Locmem outbox counts for charge + reminder jobs."""

    def setUp(self):
        self.unit = PortalUnit.objects.create(slug="school-18", name="School 18", is_active=True)
        self.family = PortalFamily.objects.create(
            unit=self.unit, slug="outbox", name="Outbox", status="Active"
        )
        self.inactive = PortalChild.objects.create(family=self.family, name="Ivy Outbox", is_active=False)
        self.active = PortalChild.objects.create(family=self.family, name="Ada Outbox", is_active=True)
        _parent_account(self.family, "outbox@example.com")
        set_charge_posted_emails_enabled(True)

    def test_outbox_counts_skip_inactive_keep_active(self):
        mail.outbox.clear()
        post_charge(
            self.family,
            "Ivy Outbox",
            "tuition",
            "50.00",
            date(2026, 9, 8),
            "Weekly tuition — Ivy Outbox",
        )
        inactive_charge_count = len(mail.outbox)
        post_charge(
            self.family,
            "Ada Outbox",
            "tuition",
            "40.00",
            date(2026, 9, 8),
            "Weekly tuition — Ada Outbox",
        )
        after_active_charge = len(mail.outbox)
        send_late_payment_notices()
        after_late = len(mail.outbox)
        send_family_parent_email(self.family, "Manual note", "Staff chose to send this.")
        after_staff = len(mail.outbox)
        self.assertEqual(inactive_charge_count, 0)
        self.assertEqual(after_active_charge, 1)
        self.assertEqual(after_late, 2)
        self.assertEqual(after_staff, 3)
        self.assertIn("Ada Outbox", mail.outbox[0].body)
        self.assertNotIn("Ivy Outbox", mail.outbox[1].body)
        self.assertIn("Staff chose to send this.", mail.outbox[2].body)
