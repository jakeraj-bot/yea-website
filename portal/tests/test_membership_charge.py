from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from enrollment.add_program import create_after_school_from_application
from enrollment.application_review import approve_application
from portal.billing_services import prepare_billing_for_staff, update_ledger_amount, update_ledger_description
from portal.family_list import family_balance
from portal.models import PortalFamily, PortalLedgerEntry, PortalStaffAccount, PortalUnit
from portal.staff_auth import PORTAL_AUTH_SESSION_KEY
from portal.tests.test_family_units import _make_application


class MembershipChargeOnApproveTests(TestCase):
    def setUp(self):
        self.unit = PortalUnit.objects.create(
            slug="school-18",
            name="School 18",
            program_type="both",
            is_active=True,
        )
        self.family = PortalFamily.objects.create(unit=self.unit, slug="rivera", name="Rivera")
        User = get_user_model()
        self.admin = User.objects.create_user(username="staff:yeaadmin", password="AdminPass123")
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

    def _pending_app(self, *, membership="yes", first="Ada", last="Rivera", status="under_review"):
        app = _make_application(self.family, status=status)
        app.student_first_name = first
        app.student_last_name = last
        app.membership_fee_agreed = membership
        app.save()
        return app

    def test_approve_posts_default_membership_fee_dated_today(self):
        app = self._pending_app()
        approve_application(app)
        fees = list(PortalLedgerEntry.objects.filter(family=self.family, entry_type="membership"))
        self.assertEqual(len(fees), 1)
        self.assertEqual(fees[0].amount, Decimal("20.00"))
        self.assertEqual(fees[0].date, timezone.localdate())
        self.assertEqual(fees[0].child_name, "Ada Rivera")
        self.assertIn("20.00", fees[0].description)
        self.assertEqual(family_balance(self.family), Decimal("20.00"))

    def test_approve_posts_edited_membership_amount_on_ledger(self):
        app = self._pending_app()
        approve_application(
            app,
            membership_amount=Decimal("15.00"),
            membership_description="Membership fee ($15.00) — Ada Rivera",
        )
        fee = PortalLedgerEntry.objects.get(family=self.family, entry_type="membership")
        self.assertEqual(fee.amount, Decimal("15.00"))
        self.assertEqual(fee.date, timezone.localdate())
        self.assertEqual(fee.description, "Membership fee ($15.00) — Ada Rivera")
        self.assertEqual(family_balance(self.family), Decimal("15.00"))

    def test_approve_with_zero_waives_membership(self):
        app = self._pending_app()
        approve_application(app, membership_amount=Decimal("0.00"))
        self.assertFalse(PortalLedgerEntry.objects.filter(family=self.family, entry_type="membership").exists())
        self.assertEqual(family_balance(self.family), Decimal("0.00"))

    def test_waitlist_add_on_does_not_double_charge_after_edited_amount(self):
        before = self._pending_app(status="waitlist")
        before.program = "before_care"
        before.membership_fee_agreed = "yes"
        before.save(update_fields=["program", "membership_fee_agreed"])
        after = create_after_school_from_application(before)
        after.membership_fee_agreed = "yes"
        after.save(update_fields=["membership_fee_agreed"])
        approve_application(after, membership_amount=Decimal("12.50"))
        approve_application(before, membership_amount=Decimal("20.00"))
        fees = PortalLedgerEntry.objects.filter(family=self.family, entry_type="membership")
        self.assertEqual(fees.count(), 1)
        self.assertEqual(fees.get().amount, Decimal("12.50"))
        self.assertEqual(fees.get().date, timezone.localdate())

    def test_can_edit_posted_membership_amount_and_description(self):
        app = self._pending_app()
        approve_application(app, membership_amount=Decimal("20.00"))
        entry = PortalLedgerEntry.objects.get(family=self.family, entry_type="membership")
        update_ledger_amount(self.family, entry.pk, "8.00", notify=False)
        update_ledger_description(self.family, entry.pk, "Membership waived in part — Ada Rivera")
        entry.refresh_from_db()
        self.assertEqual(entry.amount, Decimal("8.00"))
        self.assertEqual(entry.description, "Membership waived in part — Ada Rivera")
        self.assertEqual(family_balance(self.family), Decimal("8.00"))

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_approve_screen_shows_editable_membership_amount(self):
        app = self._pending_app()
        self._login_admin()
        page = self.client.get(
            reverse("portal_admin_application_detail", kwargs={"app_slug": str(app.reference)})
        )
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, "Membership amount")
        self.assertContains(page, 'name="membership_amount"')
        self.assertContains(page, 'name="member_start_date"')
        self.assertContains(page, "Member start date")
        self.assertContains(page, 'value="20.00"')
        self.assertContains(page, "Type 0 to waive")
        self.assertContains(page, "Change the membership amount before you approve")

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_admin_approve_posts_edited_amount_with_today(self):
        app = self._pending_app()
        self._login_admin()
        response = self.client.post(
            reverse("portal_admin_application_review", kwargs={"app_slug": str(app.reference)}),
            {
                "action": "approve",
                "membership_amount": "7.25",
                "membership_description": "Membership fee ($7.25) — Ada Rivera",
                "member_start_date": "2026-09-15",
            },
        )
        self.assertEqual(response.status_code, 302)
        fee = PortalLedgerEntry.objects.get(family=self.family, entry_type="membership")
        self.assertEqual(fee.amount, Decimal("7.25"))
        self.assertEqual(fee.date, timezone.localdate())
        self.assertEqual(fee.description, "Membership fee ($7.25) — Ada Rivera")
        app.refresh_from_db()
        self.assertEqual(app.member_start_date.isoformat(), "2026-09-15")
        billing = self.client.get(reverse("portal_admin_family_billing", kwargs={"family_slug": "rivera"}))
        self.assertContains(billing, "7.25")
        self.assertContains(billing, "Membership fee ($7.25) — Ada Rivera")
        self.assertContains(billing, 'name="amount"')
        ledger = prepare_billing_for_staff(self.family, {"can_delete_charge": True})
        membership_rows = [row for row in ledger["ledger"] if row["type"] == "membership"]
        self.assertEqual(len(membership_rows), 1)
        self.assertTrue(membership_rows[0]["editable"])

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_admin_can_edit_membership_amount_on_family_billing(self):
        app = self._pending_app()
        approve_application(app, membership_amount=Decimal("20.00"))
        entry = PortalLedgerEntry.objects.get(family=self.family, entry_type="membership")
        self._login_admin()
        response = self.client.post(
            reverse("portal_staff_billing_action", kwargs={"family_slug": "rivera"}),
            {
                "portal_area": "admin",
                "action": "edit_description",
                "entry_id": str(entry.pk),
                "description": "Membership fee ($5.00) — Ada Rivera",
                "amount": "5.00",
                "notify_balance": "",
            },
        )
        self.assertEqual(response.status_code, 302)
        entry.refresh_from_db()
        self.assertEqual(entry.amount, Decimal("5.00"))
        self.assertEqual(entry.description, "Membership fee ($5.00) — Ada Rivera")
        self.assertEqual(family_balance(self.family), Decimal("5.00"))
