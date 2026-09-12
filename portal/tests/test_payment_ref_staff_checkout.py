from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from portal.admin_reports import build_admin_report
from portal.billing_services import post_payment, prepare_billing_for_staff
from portal.models import (
    PortalActivityEvent,
    PortalChild,
    PortalFamily,
    PortalLedgerEntry,
    PortalParentAccount,
    PortalPayment,
    PortalStaffAccount,
    PortalUnit,
)
from portal.payment_refs import display_payment_reference, reject_raw_card_fields
from portal.staff_auth import PORTAL_AUTH_SESSION_KEY, billing_permissions_for_staff


class PaymentReferenceDisplayTests(TestCase):
    def test_new_check_number_stays_out_of_description(self):
        display = display_payment_reference("Weekly tuition", "2201", "Check")
        self.assertEqual(display["description"], "Weekly tuition")
        self.assertEqual(display["reference_display"], "Check #2201")

    def test_old_mashed_check_description_is_split(self):
        display = display_payment_reference("Check #2201 — Weekly tuition", "2201")
        self.assertEqual(display["description"], "Weekly tuition")
        self.assertEqual(display["reference_display"], "Check #2201")

    def test_old_mashed_money_order_without_stored_ref(self):
        display = display_payment_reference("Money order #555")
        self.assertEqual(display["description"], "In-person payment — Money order")
        self.assertEqual(display["reference_display"], "Money order #555")

    def test_real_note_with_check_word_is_not_stripped(self):
        display = display_payment_reference("Please check backpack for forms")
        self.assertEqual(display["description"], "Please check backpack for forms")
        self.assertEqual(display["reference_display"], "")

    def test_stripe_receipt_number_is_not_a_check(self):
        display = display_payment_reference("Online payment — Card", "RCPT-260912-001", "Card")
        self.assertEqual(display["description"], "Online payment — Card")
        self.assertEqual(display["reference_display"], "")


class LedgerAndReportReferenceTests(TestCase):
    def setUp(self):
        self.unit = PortalUnit.objects.create(slug="school-18", name="School 18", is_active=True)
        self.family = PortalFamily.objects.create(
            unit=self.unit,
            slug="jacobs",
            name="Jacobs",
            primary_contact="Jakera Jacobs",
            status="Active",
        )
        PortalChild.objects.create(family=self.family, name="Jordan Jacobs", is_active=True)

    def test_prepare_billing_shows_number_beside_not_in_description(self):
        post_payment(
            self.family,
            "Jordan Jacobs",
            "25.00",
            timezone.localdate(),
            "Check",
            "Weekly tuition",
            "2201",
        )
        billing = prepare_billing_for_staff(self.family, billing_permissions_for_staff(None, portal_area="admin"))
        row = next(item for item in billing["ledger"] if item["type"] == "payment")
        self.assertEqual(row["description"], "Weekly tuition")
        self.assertEqual(row["reference_display"], "Check #2201")
        self.assertNotIn("Check #2201", row["description"])

    def test_old_ledger_row_splits_mashed_description(self):
        PortalLedgerEntry.objects.create(
            family=self.family,
            child_name="Jordan Jacobs",
            date=timezone.localdate(),
            entry_type="payment",
            description="Check #901 — Desk payment",
            amount=Decimal("-22.00"),
            is_manual=True,
        )
        billing = prepare_billing_for_staff(self.family, billing_permissions_for_staff(None, portal_area="admin"))
        row = next(item for item in billing["ledger"] if item["type"] == "payment")
        self.assertEqual(row["description"], "Desk payment")
        self.assertEqual(row["reference_display"], "Check #901")

    def test_who_paid_what_puts_number_in_own_column(self):
        post_payment(
            self.family,
            "Jordan Jacobs",
            "18.00",
            timezone.localdate(),
            "Money order",
            "Weekly tuition",
            "555",
        )
        report = build_admin_report("payments", {})
        row = next(item for item in report["rows"] if item["family"] == "Jacobs")
        self.assertEqual(row["method"], "Money order")
        self.assertEqual(row["reference_display"], "Money order #555")
        self.assertNotIn("555", row.get("description", ""))
        column_keys = [key for key, _label in report["columns"]]
        self.assertIn("reference_display", column_keys)


class StaffCardCheckoutTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.unit = PortalUnit.objects.create(slug="school-18", name="School 18", is_active=True)
        self.other_unit = PortalUnit.objects.create(slug="school-26", name="School 26", is_active=True)
        self.family = PortalFamily.objects.create(unit=self.unit, slug="jacobs", name="Jacobs", status="Active")
        PortalChild.objects.create(family=self.family, name="Jordan Jacobs", is_active=True)
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
        self.parent = User.objects.create_user(
            username="parent:jacobs",
            password="ParentPass123",
            email="jakera@example.com",
        )
        PortalParentAccount.objects.create(user=self.parent, family=self.family)
        self.factory = RequestFactory()

    def _login(self, user, area):
        self.client.force_login(user)
        session = self.client.session
        session[PORTAL_AUTH_SESSION_KEY] = area
        session.save()

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_billing_page_has_checkout_not_raw_card_fields(self):
        self._login(self.admin, "admin")
        billing = self.client.get(reverse("portal_admin_family_billing", kwargs={"family_slug": "jacobs"}))
        self.assertContains(billing, "Take a card payment")
        self.assertContains(billing, "card_checkout")
        self.assertContains(billing, "Open Stripe Checkout")
        self.assertNotContains(billing, 'name="card_number"')
        self.assertNotContains(billing, 'name="cvc"')
        self.assertNotContains(billing, 'name="cvv"')
        self.assertNotContains(billing, "Card (staff entry)")

    def test_reject_raw_card_fields(self):
        with self.assertRaises(ValueError):
            reject_raw_card_fields({"card_number": "4242424242424242", "cvc": "123"})

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_posting_raw_card_number_is_rejected(self):
        self._login(self.admin, "admin")
        response = self.client.post(
            reverse("portal_staff_billing_action", kwargs={"family_slug": "jacobs"}),
            {
                "portal_area": "admin",
                "action": "card_checkout",
                "child_name": "Jordan Jacobs",
                "amount": "40.00",
                "note": "Weekly tuition",
                "card_number": "4242424242424242",
                "cvc": "123",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(PortalPayment.objects.filter(family=self.family).exists())

    @override_settings(
        PORTAL_PREVIEW_MODE=False,
        MEMBER_STRIPE_SECRET_KEY="sk_test_123",
        MEMBER_STRIPE_PUBLIC_KEY="pk_test_123",
    )
    @patch("portal.stripe_services.member_stripe")
    def test_staff_checkout_creates_stripe_session(self, member_stripe):
        stripe = MagicMock()
        stripe.Customer.create.return_value = MagicMock(id="cus_staff")
        stripe.checkout.Session.create.return_value = MagicMock(
            id="cs_staff_123",
            url="https://stripe.test/pay-staff",
        )
        member_stripe.return_value = stripe
        self._login(self.staff, "staff")
        response = self.client.post(
            reverse("portal_staff_billing_action", kwargs={"family_slug": "jacobs"}),
            {
                "portal_area": "staff",
                "action": "card_checkout",
                "child_name": "Jordan Jacobs",
                "amount": "40.00",
                "note": "Weekly tuition",
            },
        )
        self.assertEqual(response.status_code, 303)
        self.assertEqual(response["Location"], "https://stripe.test/pay-staff")
        payment = PortalPayment.objects.get(family=self.family)
        self.assertEqual(payment.status, PortalPayment.STATUS_PENDING)
        self.assertEqual(payment.stripe_session_id, "cs_staff_123")
        self.assertEqual(payment.amount, Decimal("40.00"))
        self.assertEqual(payment.dropin_child, "Jordan Jacobs")
        kwargs = stripe.checkout.Session.create.call_args.kwargs
        self.assertEqual(kwargs["metadata"]["initiated_by"], "staff")
        self.assertEqual(kwargs["metadata"]["staff_note"], "Weekly tuition")
        self.assertNotIn("card_number", kwargs)
        event = PortalActivityEvent.objects.get(action=PortalActivityEvent.ACTION_PAYMENT, actor=self.staff)
        self.assertEqual(event.action_label, "Started a card payment")
        self.assertEqual(event.object_label, "Jacobs")
        self.assertNotIn("4242", event.details)
        self.assertNotIn("card_number", event.details)

    @override_settings(
        PORTAL_PREVIEW_MODE=False,
        MEMBER_STRIPE_SECRET_KEY="sk_test_123",
        MEMBER_STRIPE_PUBLIC_KEY="pk_test_123",
    )
    @patch("portal.stripe_services.member_stripe")
    def test_admin_checkout_confirm_posts_ledger_like_parent(self, member_stripe):
        from portal.processing_fees import apply_fee_to_payment

        payment = PortalPayment.objects.create(
            family=self.family,
            amount=Decimal("40.00"),
            payment_kind="balance",
            dropin_child="Jordan Jacobs",
            method_label="Card",
            status=PortalPayment.STATUS_PENDING,
            stripe_session_id="cs_staff_paid",
        )
        apply_fee_to_payment(payment)
        stripe = MagicMock()
        stripe.checkout.Session.retrieve.return_value = SimpleNamespace(
            id="cs_staff_paid",
            payment_status="paid",
            amount_total=None,
            payment_intent="pi_staff_paid",
            metadata={"portal_payment_id": str(payment.pk), "staff_note": "Weekly tuition", "child_name": "Jordan Jacobs"},
        )
        member_stripe.return_value = stripe
        from portal.stripe_services import confirm_checkout_payment

        confirmed = confirm_checkout_payment("cs_staff_paid")
        self.assertIsNotNone(confirmed)
        confirmed.refresh_from_db()
        self.assertEqual(confirmed.status, PortalPayment.STATUS_PAID)
        entry = PortalLedgerEntry.objects.get(family=self.family, entry_type="payment")
        self.assertEqual(entry.description, "Weekly tuition")
        self.assertEqual(entry.child_name, "Jordan Jacobs")
        self.assertEqual(entry.amount, Decimal("-40.00"))
        self.assertTrue((entry.fee_amount or Decimal("0")) > 0)
        self.assertTrue(entry.reference_number.startswith("RCPT-"))

    @override_settings(
        PORTAL_PREVIEW_MODE=False,
        MEMBER_STRIPE_SECRET_KEY="sk_test_123",
        MEMBER_STRIPE_PUBLIC_KEY="pk_test_123",
    )
    @patch("portal.stripe_services.member_stripe")
    def test_returning_from_checkout_logs_recorded_card_payment(self, member_stripe):
        from portal.processing_fees import apply_fee_to_payment

        payment = PortalPayment.objects.create(
            family=self.family,
            amount=Decimal("40.00"),
            payment_kind="balance",
            dropin_child="Jordan Jacobs",
            method_label="Card",
            status=PortalPayment.STATUS_PENDING,
            stripe_session_id="cs_staff_return",
        )
        apply_fee_to_payment(payment)
        stripe = MagicMock()
        stripe.checkout.Session.retrieve.return_value = SimpleNamespace(
            id="cs_staff_return",
            payment_status="paid",
            amount_total=None,
            payment_intent="pi_staff_return",
            metadata={
                "portal_payment_id": str(payment.pk),
                "staff_note": "Weekly tuition",
                "child_name": "Jordan Jacobs",
            },
        )
        member_stripe.return_value = stripe
        self._login(self.admin, "admin")
        response = self.client.get(
            reverse("portal_admin_family_billing", kwargs={"family_slug": "jacobs"}),
            {"session_id": "cs_staff_return"},
        )
        self.assertEqual(response.status_code, 200)
        payment.refresh_from_db()
        self.assertEqual(payment.status, PortalPayment.STATUS_PAID)
        event = PortalActivityEvent.objects.get(action=PortalActivityEvent.ACTION_PAYMENT, actor=self.admin)
        self.assertEqual(event.action_label, "Recorded a card payment")
        self.assertEqual(event.object_label, "Jacobs")
        self.assertNotIn("4242", event.details)
        self.assertNotIn("card_number", event.details)
