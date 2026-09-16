from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from portal.admin_config import save_scholarship_fund
from portal.billing_services import (
    delete_child_billing_plan,
    first_plan_charge_date,
    next_plan_charge_date,
    post_credit,
    post_payment,
    run_due_plan_charges,
    staff_payment_note,
    update_child_billing_plan,
    update_ledger_description,
)
from portal.family_list import household_balance
from portal.models import (
    PortalAgency,
    PortalAgencyProfile,
    PortalChild,
    PortalChildBillingPlan,
    PortalFamily,
    PortalLedgerEntry,
    PortalPayment,
    PortalScholarshipAssignment,
    PortalStaffAccount,
    PortalUnit,
)
from portal.parent_services import get_billing_live, get_receipts_live, payment_to_receipt_dict
from portal.staff_auth import PORTAL_AUTH_SESSION_KEY
from portal.tests.test_family_units import _make_application


class FamilyAccountHubTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.unit = PortalUnit.objects.create(slug="school-18", name="School 18", is_active=True)
        self.family = PortalFamily.objects.create(unit=self.unit, slug="jacobs", name="Jacobs")
        self.next_family = PortalFamily.objects.create(unit=self.unit, slug="martinez", name="Martinez")
        PortalChild.objects.create(family=self.family, name="Jordan Jacobs", is_active=True)
        PortalChild.objects.create(family=self.next_family, name="Sofia Martinez", is_active=True)
        _make_application(self.family)
        self.family.enrollment_applications.update(primary_email="jakera@example.com")
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

    def _login(self, user, area):
        self.client.force_login(user)
        session = self.client.session
        session[PORTAL_AUTH_SESSION_KEY] = area
        session.save()

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_admin_family_account_has_staff_style_tabs(self):
        self._login(self.admin, "admin")
        response = self.client.get(reverse("portal_admin_family_detail", kwargs={"family_slug": "jacobs"}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Family account")
        self.assertContains(response, "Jordan Jacobs")
        self.assertContains(response, "portal-account-children")
        self.assertContains(response, "portal-family-tabs-colorful")
        for label in ("Profile", "Billing", "Plans", "4Cs", "Applications", "Policies", "Email parent", "Notes", "Incidents", "Pickup", "Attendance", "Parent view"):
            self.assertContains(response, label)
        self.assertContains(response, reverse("portal_admin_family_attendance", kwargs={"family_slug": "jacobs"}))
        self.assertContains(response, "Find a child or family")
        self.assertContains(response, reverse("portal_admin_family_search"))

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_admin_member_account_has_next_button_to_next_family(self):
        self._login(self.admin, "admin")
        profile = self.client.get(reverse("portal_admin_family_detail", kwargs={"family_slug": "jacobs"}))
        billing = self.client.get(reverse("portal_admin_family_billing", kwargs={"family_slug": "jacobs"}))
        self.assertEqual(profile.status_code, 200)
        self.assertEqual(billing.status_code, 200)
        # Child rows A–Z: Ada Jacobs (application), Jordan Jacobs, Sofia Martinez.
        # Opening Jacobs without a child lands on Ada; Next is the next child row.
        self.assertContains(profile, "portal-family-pager-next")
        self.assertNotContains(profile, "portal-family-neighbor-nav")
        self.assertContains(profile, "Next · Jordan Jacobs")
        self.assertContains(profile, "1 of 3")
        self.assertContains(billing, "portal-family-pager-next")
        self.assertContains(billing, reverse("portal_admin_family_billing", kwargs={"family_slug": "jacobs"}))
        jordan = self.client.get(
            reverse("portal_admin_family_detail", kwargs={"family_slug": "jacobs"}),
            {"id": self.family.pk, "child": "Jordan Jacobs"},
        )
        self.assertContains(jordan, reverse("portal_admin_family_detail", kwargs={"family_slug": "martinez"}))
        self.assertContains(jordan, "Next · Sofia Martinez")

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_staff_member_account_has_next_button_to_next_family(self):
        self._login(self.staff, "staff")
        response = self.client.get(reverse("portal_staff_family_detail", kwargs={"family_slug": "jacobs"}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "portal-family-pager-next")
        self.assertContains(response, "Next · Jordan Jacobs")
        jordan = self.client.get(
            reverse("portal_staff_family_detail", kwargs={"family_slug": "jacobs"}),
            {"child": "Jordan Jacobs"},
        )
        self.assertContains(jordan, reverse("portal_staff_family_detail", kwargs={"family_slug": "martinez"}))

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_admin_billing_has_refund_button_not_wide_table(self):
        self._login(self.admin, "admin")
        billing = self.client.get(reverse("portal_admin_family_billing", kwargs={"family_slug": "jacobs"}))
        refund = self.client.get(reverse("portal_admin_family_refund", kwargs={"family_slug": "jacobs"}))
        self.assertEqual(billing.status_code, 200)
        self.assertEqual(refund.status_code, 200)
        self.assertContains(billing, "Refund")
        self.assertContains(billing, reverse("portal_admin_family_refund", kwargs={"family_slug": "jacobs"}))
        self.assertNotContains(billing, "Already refunded")
        self.assertContains(refund, "Process refund")
        self.assertContains(refund, "portal-account-narrow")

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_unit_staff_cannot_open_admin_refund(self):
        self._login(self.staff, "staff")
        response = self.client.get(reverse("portal_admin_family_refund", kwargs={"family_slug": "jacobs"}))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/portal/admin/login/", response.url)

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_staff_family_profile_includes_new_tabs_and_collapse_script(self):
        self._login(self.staff, "staff")
        response = self.client.get(reverse("portal_staff_family_detail", kwargs={"family_slug": "jacobs"}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Plans")
        self.assertContains(response, "4Cs")
        self.assertContains(response, "Applications")
        self.assertContains(response, "Attendance")
        self.assertContains(response, "Notes")
        self.assertContains(response, reverse("portal_staff_family_notes", kwargs={"family_slug": "jacobs"}))
        self.assertContains(response, "Find a child or family")
        self.assertContains(response, reverse("portal_staff_family_search"))
        self.assertContains(response, reverse("portal_staff_family_attendance", kwargs={"family_slug": "jacobs"}))
        self.assertContains(response, "portal-collapse.js")
        self.assertContains(response, reverse("portal_staff_family_plans", kwargs={"family_slug": "jacobs"}))


class BillingPlanChargeTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.unit = PortalUnit.objects.create(slug="school-18", name="School 18", is_active=True)
        self.family = PortalFamily.objects.create(unit=self.unit, slug="jacobs", name="Jacobs", status="Active")
        self.child = PortalChild.objects.create(
            family=self.family,
            name="Jordan Jacobs",
            billing_plan="Weekly",
            billing_amount=Decimal("50.00"),
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

    def test_explicit_first_charge_date_is_honored(self):
        today = timezone.localdate()
        other_weekday = (today.weekday() + 1) % 7
        self.assertEqual(
            first_plan_charge_date(today, "Weekly", weekday=other_weekday),
            today,
        )

    def test_biweekly_repeats_fourteen_days_from_entered_date(self):
        start = timezone.localdate()
        other_weekday = (start.weekday() + 1) % 7
        self.assertEqual(
            next_plan_charge_date(start, "Bi-weekly", weekday=other_weekday),
            start + timedelta(days=14),
        )
        child, posted = update_child_billing_plan(
            self.family,
            "Jordan Jacobs",
            "Bi-weekly",
            "50.00",
            "Private pay",
            auto_charge=True,
            next_charge_date=start,
            charge_weekday=other_weekday,
        )
        self.assertEqual(len(posted), 1)
        entry = PortalLedgerEntry.objects.get(family=self.family, entry_type="charge")
        self.assertEqual(entry.date, start)
        child.refresh_from_db()
        self.assertEqual(child.next_charge_date, start + timedelta(days=14))

    def test_saving_plan_for_today_posts_charge_even_if_weekday_differs(self):
        today = timezone.localdate()
        other_weekday = (today.weekday() + 1) % 7
        child, posted = update_child_billing_plan(
            self.family,
            "Jordan Jacobs",
            "Weekly",
            "50.00",
            "Private pay",
            auto_charge=True,
            next_charge_date=today,
            charge_weekday=other_weekday,
        )
        self.assertEqual(len(posted), 1)
        entry = PortalLedgerEntry.objects.get(family=self.family, entry_type="charge")
        self.assertEqual(entry.amount, Decimal("50.00"))
        self.assertEqual(entry.date, today)
        self.assertIn("Jordan Jacobs", entry.description)
        child.refresh_from_db()
        self.assertEqual(child.last_auto_charge_date, today)
        self.assertGreater(child.next_charge_date, today)

    def test_future_first_charge_date_does_not_post(self):
        future = timezone.localdate() + timedelta(days=7)
        _child, posted = update_child_billing_plan(
            self.family,
            "Jordan Jacobs",
            "Weekly",
            "50.00",
            auto_charge=True,
            next_charge_date=future,
            charge_weekday=future.weekday(),
        )
        self.assertEqual(posted, [])
        self.assertFalse(PortalLedgerEntry.objects.filter(family=self.family).exists())

    def test_past_first_charge_date_is_ledger_date_not_today(self):
        today = date(2026, 9, 16)
        first_charge = date(2026, 9, 15)
        with patch("portal.billing_services.timezone.localdate", return_value=today):
            child, posted = update_child_billing_plan(
                self.family,
                "Jordan Jacobs",
                "Weekly",
                "50.00",
                "Private pay",
                auto_charge=True,
                next_charge_date=first_charge,
                charge_weekday=first_charge.weekday(),
            )
        self.assertEqual(len(posted), 1)
        entry = PortalLedgerEntry.objects.get(family=self.family, entry_type="charge")
        self.assertEqual(entry.date, first_charge)
        self.assertNotEqual(entry.date, today)
        child.refresh_from_db()
        self.assertEqual(child.last_auto_charge_date, first_charge)
        billing = get_billing_live(self.family)
        self.assertEqual(billing["ledger"][0]["date"], first_charge.isoformat())

    def test_future_first_charge_posts_that_date_when_due_not_today(self):
        today = date(2026, 9, 9)
        future = date(2026, 9, 16)
        with patch("portal.billing_services.timezone.localdate", return_value=today):
            child, posted = update_child_billing_plan(
                self.family,
                "Jordan Jacobs",
                "Weekly",
                "50.00",
                "Private pay",
                auto_charge=True,
                next_charge_date=future,
                charge_weekday=future.weekday(),
            )
        self.assertEqual(posted, [])
        child.refresh_from_db()
        self.assertEqual(child.next_charge_date, future)
        posted = run_due_plan_charges(today=future, child=child)
        self.assertEqual(len(posted), 1)
        entry = PortalLedgerEntry.objects.get(family=self.family, entry_type="charge")
        self.assertEqual(entry.date, future)
        self.assertNotEqual(entry.date, today)

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_admin_save_plan_keeps_chosen_first_charge_date_on_billing(self):
        self._login_admin()
        today = date(2026, 9, 16)
        first_charge = date(2026, 9, 15)
        with patch("portal.billing_services.timezone.localdate", return_value=today), patch(
            "portal.views_actions.timezone.localdate", return_value=today
        ):
            response = self.client.post(
                reverse("portal_staff_billing_action", kwargs={"family_slug": "jacobs"}),
                {
                    "portal_area": "admin",
                    "action": "update_plan",
                    "child_name": "Jordan Jacobs",
                    "billing_plan": "Weekly",
                    "billing_amount": "50.00",
                    "billing_type": "Private pay",
                    "auto_charge": "on",
                    "next_charge_date": first_charge.isoformat(),
                    "charge_weekday": str(first_charge.weekday()),
                    "next": reverse("portal_admin_family_plans", kwargs={"family_slug": "jacobs"}),
                },
            )
        self.assertEqual(response.status_code, 302)
        entry = PortalLedgerEntry.objects.get(family=self.family, entry_type="charge")
        self.assertEqual(entry.date, first_charge)
        billing = self.client.get(reverse("portal_admin_family_billing", kwargs={"family_slug": "jacobs"}))
        self.assertEqual(billing.status_code, 200)
        self.assertContains(billing, first_charge.isoformat())

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_admin_save_plan_for_today_shows_charge_on_billing(self):
        self._login_admin()
        today = timezone.localdate()
        other_weekday = (today.weekday() + 1) % 7
        response = self.client.post(
            reverse("portal_staff_billing_action", kwargs={"family_slug": "jacobs"}),
            {
                "portal_area": "admin",
                "action": "update_plan",
                "child_name": "Jordan Jacobs",
                "billing_plan": "Weekly",
                "billing_amount": "50.00",
                "billing_type": "Private pay",
                "auto_charge": "on",
                "next_charge_date": today.isoformat(),
                "charge_weekday": str(other_weekday),
                "next": reverse("portal_admin_family_plans", kwargs={"family_slug": "jacobs"}),
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn("/billing/", response.url)
        billing = self.client.get(reverse("portal_admin_family_billing", kwargs={"family_slug": "jacobs"}))
        self.assertEqual(billing.status_code, 200)
        self.assertContains(billing, "Weekly tuition")
        self.assertContains(billing, "50.00")
        self.assertContains(billing, "edit-ledger-desc")
        self.assertContains(billing, "edit_description")
        self.assertEqual(PortalLedgerEntry.objects.filter(family=self.family, entry_type="charge").count(), 1)

    def test_can_edit_system_charge_description(self):
        today = timezone.localdate()
        update_child_billing_plan(
            self.family,
            "Jordan Jacobs",
            "Weekly",
            "50.00",
            auto_charge=True,
            next_charge_date=today,
            charge_weekday=(today.weekday() + 1) % 7,
        )
        entry = PortalLedgerEntry.objects.get(family=self.family, entry_type="charge")
        update_ledger_description(self.family, entry.pk, "After-school week of Sep 4")
        entry.refresh_from_db()
        self.assertEqual(entry.description, "After-school week of Sep 4")
        self.assertEqual(entry.amount, Decimal("50.00"))

    def test_can_edit_payment_description(self):
        today = timezone.localdate()
        post_payment(self.family, "Jordan Jacobs", "20.00", today, "Cash", "In-person payment — Cash")
        entry = PortalLedgerEntry.objects.get(family=self.family, entry_type="payment")
        update_ledger_description(self.family, entry.pk, "Cash — week of Sep 4")
        entry.refresh_from_db()
        self.assertEqual(entry.description, "Cash — week of Sep 4")

    def test_cannot_edit_credit_description(self):
        today = timezone.localdate()
        post_credit(self.family, "Jordan Jacobs", "10.00", today, "Adjustment")
        entry = PortalLedgerEntry.objects.get(family=self.family, entry_type="credit")
        with self.assertRaises(ValueError):
            update_ledger_description(self.family, entry.pk, "Changed")

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_admin_can_save_edited_charge_description(self):
        self._login_admin()
        today = timezone.localdate()
        update_child_billing_plan(
            self.family,
            "Jordan Jacobs",
            "Weekly",
            "50.00",
            auto_charge=True,
            next_charge_date=today,
            charge_weekday=(today.weekday() + 1) % 7,
        )
        entry = PortalLedgerEntry.objects.get(family=self.family, entry_type="charge")
        response = self.client.post(
            reverse("portal_staff_billing_action", kwargs={"family_slug": "jacobs"}),
            {
                "portal_area": "admin",
                "action": "edit_description",
                "entry_id": str(entry.pk),
                "description": "Weekly tuition — after-school",
            },
        )
        self.assertEqual(response.status_code, 302)
        entry.refresh_from_db()
        self.assertEqual(entry.description, "Weekly tuition — after-school")
        billing = self.client.get(reverse("portal_admin_family_billing", kwargs={"family_slug": "jacobs"}))
        self.assertContains(billing, "Weekly tuition — after-school")

    def test_two_plans_post_separate_charges_and_keep_balance(self):
        today = timezone.localdate()
        weekday = (today.weekday() + 1) % 7
        update_child_billing_plan(
            self.family,
            "Jordan Jacobs",
            "Weekly",
            "40.00",
            "Private pay",
            auto_charge=True,
            next_charge_date=today,
            charge_weekday=weekday,
            description="After care",
        )
        update_child_billing_plan(
            self.family,
            "Jordan Jacobs",
            "Weekly",
            "25.00",
            "Private pay",
            auto_charge=True,
            next_charge_date=today,
            charge_weekday=weekday,
            description="Before care",
            create_new=True,
        )
        charges = list(
            PortalLedgerEntry.objects.filter(family=self.family, entry_type="charge").order_by("pk")
        )
        self.assertEqual(len(charges), 2)
        descriptions = [entry.description for entry in charges]
        self.assertTrue(any("After care" in item for item in descriptions))
        self.assertTrue(any("Before care" in item for item in descriptions))
        self.assertEqual(sum((entry.amount for entry in charges), Decimal("0")), Decimal("65.00"))
        self.family.refresh_from_db()
        billing = get_billing_live(self.family)
        child = next(item for item in billing["children"] if item["name"] == "Jordan Jacobs")
        self.assertEqual(child["balance"], "65.00")
        self.assertEqual(billing["running_balance"], "65.00")
        self.assertEqual(household_balance(self.family), Decimal("65.00"))
        self.assertEqual(self.family.balance, Decimal("65.00"))
        self.assertEqual(len(child["plans"]), 2)
        self.assertEqual(PortalChildBillingPlan.objects.filter(child=self.child).count(), 2)

    def test_can_remove_extra_plan_without_losing_first_plan(self):
        today = timezone.localdate()
        weekday = today.weekday()
        update_child_billing_plan(
            self.family,
            "Jordan Jacobs",
            "Weekly",
            "40.00",
            auto_charge=True,
            next_charge_date=today + timedelta(days=7),
            charge_weekday=weekday,
            description="After care",
        )
        update_child_billing_plan(
            self.family,
            "Jordan Jacobs",
            "Weekly",
            "25.00",
            auto_charge=True,
            next_charge_date=today + timedelta(days=7),
            charge_weekday=weekday,
            description="Before care",
            create_new=True,
        )
        extra = PortalChildBillingPlan.objects.get(child=self.child, description="Before care")
        delete_child_billing_plan(self.family, "Jordan Jacobs", extra.pk)
        remaining = list(PortalChildBillingPlan.objects.filter(child=self.child))
        self.assertEqual(len(remaining), 1)
        self.assertEqual(remaining[0].description, "After care")
        self.child.refresh_from_db()
        self.assertEqual(self.child.billing_amount, Decimal("40.00"))

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_admin_can_add_second_plan_from_plans_tab(self):
        self._login_admin()
        today = timezone.localdate()
        weekday = (today.weekday() + 1) % 7
        first = self.client.post(
            reverse("portal_staff_billing_action", kwargs={"family_slug": "jacobs"}),
            {
                "portal_area": "admin",
                "action": "update_plan",
                "child_name": "Jordan Jacobs",
                "billing_plan": "Weekly",
                "billing_amount": "40.00",
                "billing_type": "Private pay",
                "plan_description": "After care",
                "auto_charge": "on",
                "next_charge_date": today.isoformat(),
                "charge_weekday": str(weekday),
                "next": reverse("portal_admin_family_plans", kwargs={"family_slug": "jacobs"}),
            },
        )
        self.assertEqual(first.status_code, 302)
        second = self.client.post(
            reverse("portal_staff_billing_action", kwargs={"family_slug": "jacobs"}),
            {
                "portal_area": "admin",
                "action": "update_plan",
                "child_name": "Jordan Jacobs",
                "billing_plan": "Weekly",
                "billing_amount": "25.00",
                "billing_type": "Private pay",
                "plan_description": "Before care",
                "create_plan": "1",
                "auto_charge": "on",
                "next_charge_date": today.isoformat(),
                "charge_weekday": str(weekday),
                "next": reverse("portal_admin_family_plans", kwargs={"family_slug": "jacobs"}),
            },
        )
        self.assertEqual(second.status_code, 302)
        descriptions = list(
            PortalLedgerEntry.objects.filter(family=self.family, entry_type="charge").values_list(
                "description", flat=True
            )
        )
        self.assertEqual(len(descriptions), 2)
        self.assertTrue(any("After care" in item for item in descriptions))
        self.assertTrue(any("Before care" in item for item in descriptions))
        plans_page = self.client.get(reverse("portal_admin_family_plans", kwargs={"family_slug": "jacobs"}))
        self.assertContains(plans_page, "Before care")
        self.assertContains(plans_page, "After care")
        self.assertContains(plans_page, "Add another plan")
        billing = self.client.get(reverse("portal_admin_family_billing", kwargs={"family_slug": "jacobs"}))
        self.assertContains(billing, "Before care")
        self.assertContains(billing, "After care")


class RegularPlanScholarshipTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.unit = PortalUnit.objects.create(slug="school-18", name="School 18", is_active=True)
        self.family = PortalFamily.objects.create(
            unit=self.unit, slug="jacobs", name="Jacobs", billing_type="Private pay", status="Active"
        )
        self.child = PortalChild.objects.create(
            family=self.family, name="Jordan Jacobs", is_active=True, billing_plan="Weekly"
        )
        self.fund = save_scholarship_fund({"name": "YEA General Scholarship", "description": "Need-based"})
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

    def _assert_full_rate_and_discount(self, posted):
        self.assertEqual(len(posted), 1)
        self.child.refresh_from_db()
        self.family.refresh_from_db()
        assignment = PortalScholarshipAssignment.objects.get(child=self.child)
        self.assertEqual(assignment.fund, self.fund)
        self.assertEqual(assignment.full_rate, Decimal("70.00"))
        self.assertEqual(assignment.parent_amount, Decimal("50.00"))
        self.assertEqual(self.child.billing_amount, Decimal("70.00"))
        self.assertEqual(self.family.billing_type, "Private pay")
        types = list(PortalLedgerEntry.objects.filter(family=self.family).values_list("entry_type", "amount"))
        self.assertIn(("charge", Decimal("70.00")), types)
        self.assertIn(("discount", Decimal("-20.00")), types)
        discount = PortalLedgerEntry.objects.get(family=self.family, entry_type="discount")
        self.assertIn("YEA General Scholarship", discount.description)
        self.assertEqual(self.family.balance, Decimal("50.00"))

    def test_weekly_private_pay_plan_posts_full_rate_and_scholarship_discount(self):
        today = date(2026, 9, 9)
        with patch("portal.billing_services.timezone.localdate", return_value=today):
            _child, posted = update_child_billing_plan(
                self.family,
                "Jordan Jacobs",
                "Weekly",
                billing_type="Private pay",
                scholarship_fund_id=self.fund.pk,
                scholarship_full_rate="70.00",
                scholarship_parent_amount="50.00",
                auto_charge=True,
                next_charge_date=today,
                charge_weekday=today.weekday(),
            )
        self._assert_full_rate_and_discount(posted)

    def test_scholarship_charge_and_discount_share_chosen_first_charge_date(self):
        today = date(2026, 9, 16)
        first_charge = date(2026, 9, 15)
        with patch("portal.billing_services.timezone.localdate", return_value=today):
            _child, posted = update_child_billing_plan(
                self.family,
                "Jordan Jacobs",
                "Weekly",
                billing_type="Private pay",
                scholarship_fund_id=self.fund.pk,
                scholarship_full_rate="70.00",
                scholarship_parent_amount="50.00",
                auto_charge=True,
                next_charge_date=first_charge,
                charge_weekday=first_charge.weekday(),
            )
        self._assert_full_rate_and_discount(posted)
        charge = PortalLedgerEntry.objects.get(family=self.family, entry_type="charge")
        discount = PortalLedgerEntry.objects.get(family=self.family, entry_type="discount")
        self.assertEqual(charge.date, first_charge)
        self.assertEqual(discount.date, first_charge)
        self.assertNotEqual(charge.date, today)

    def test_biweekly_private_pay_plan_posts_reduced_family_amount(self):
        today = date(2026, 9, 9)
        with patch("portal.billing_services.timezone.localdate", return_value=today):
            _child, posted = update_child_billing_plan(
                self.family,
                "Jordan Jacobs",
                "Bi-weekly",
                billing_type="Private pay",
                scholarship_fund_id=self.fund.pk,
                scholarship_full_rate="70.00",
                scholarship_parent_amount="50.00",
                auto_charge=True,
                next_charge_date=today,
                charge_weekday=today.weekday(),
            )
        self._assert_full_rate_and_discount(posted)
        self.child.refresh_from_db()
        self.assertEqual(self.child.next_charge_date, today + timedelta(days=14))

    def test_monthly_private_pay_plan_posts_reduced_family_amount(self):
        today = date(2026, 9, 9)
        with patch("portal.billing_services.timezone.localdate", return_value=today):
            _child, posted = update_child_billing_plan(
                self.family,
                "Jordan Jacobs",
                "Monthly",
                amount="280.00",
                billing_type="Private pay",
                scholarship_fund_id=self.fund.pk,
                scholarship_full_rate="280.00",
                scholarship_parent_amount="200.00",
                auto_charge=True,
                next_charge_date=today,
                charge_month_day=today.day,
            )
        self.assertEqual(len(posted), 1)
        self.child.refresh_from_db()
        assignment = PortalScholarshipAssignment.objects.get(child=self.child)
        self.assertEqual(assignment.full_rate, Decimal("280.00"))
        self.assertEqual(assignment.parent_amount, Decimal("200.00"))
        self.assertEqual(self.child.billing_amount, Decimal("280.00"))
        types = list(PortalLedgerEntry.objects.filter(family=self.family).values_list("entry_type", "amount"))
        self.assertIn(("charge", Decimal("280.00")), types)
        self.assertIn(("discount", Decimal("-80.00")), types)
        self.family.refresh_from_db()
        self.assertEqual(self.family.balance, Decimal("200.00"))

    def test_monthly_scholarship_does_not_clear_existing_plan_amount(self):
        today = date(2026, 9, 9)
        with patch("portal.billing_services.timezone.localdate", return_value=today):
            update_child_billing_plan(
                self.family,
                "Jordan Jacobs",
                "Monthly",
                amount="280.00",
                billing_type="Private pay",
                auto_charge=True,
                next_charge_date=today,
                charge_month_day=today.day,
            )
        self.child.refresh_from_db()
        self.assertEqual(self.child.billing_amount, Decimal("280.00"))
        with patch("portal.billing_services.timezone.localdate", return_value=today):
            update_child_billing_plan(
                self.family,
                "Jordan Jacobs",
                "Monthly",
                amount="280.00",
                billing_type="Private pay",
                scholarship_fund_id=self.fund.pk,
                scholarship_full_rate="280.00",
                scholarship_parent_amount="200.00",
                auto_charge=True,
                next_charge_date=today,
                charge_month_day=today.day,
            )
        self.child.refresh_from_db()
        assignment = PortalScholarshipAssignment.objects.get(child=self.child)
        self.assertEqual(self.child.billing_amount, Decimal("280.00"))
        self.assertEqual(assignment.full_rate, Decimal("280.00"))
        self.assertEqual(assignment.parent_amount, Decimal("200.00"))

    def test_private_pay_scholarship_does_not_change_4cs_agency_weeks(self):
        four_cs_family = PortalFamily.objects.create(
            unit=self.unit, slug="rivera", name="Rivera", billing_type="4Cs", status="Active"
        )
        four_cs_child = PortalChild.objects.create(
            family=four_cs_family, name="Ada Rivera", is_active=True, billing_plan="Weekly"
        )
        agency = PortalAgency.objects.create(slug="passaic-4cs", name="Passaic County 4Cs", is_active=True)
        profile = PortalAgencyProfile.objects.create(
            unit=self.unit,
            family=four_cs_family,
            child=four_cs_child,
            agency=agency,
            weekly_agency_rate=Decimal("110.00"),
            weekly_copay=Decimal("26.50"),
            daily_agency_rate=Decimal("22.00"),
            daily_copay=Decimal("5.30"),
        )
        today = date(2026, 9, 9)
        with patch("portal.billing_services.timezone.localdate", return_value=today):
            update_child_billing_plan(
                self.family,
                "Jordan Jacobs",
                "Weekly",
                billing_type="Private pay",
                scholarship_fund_id=self.fund.pk,
                scholarship_full_rate="70.00",
                scholarship_parent_amount="50.00",
                auto_charge=True,
                next_charge_date=today,
                charge_weekday=today.weekday(),
            )
        profile.refresh_from_db()
        four_cs_family.refresh_from_db()
        self.assertEqual(profile.weekly_agency_rate, Decimal("110.00"))
        self.assertEqual(profile.weekly_copay, Decimal("26.50"))
        self.assertEqual(four_cs_family.billing_type, "4Cs")
        self.assertFalse(PortalLedgerEntry.objects.filter(family=four_cs_family).exists())
        self.assertEqual(self.family.billing_type, "Private pay")

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_plans_page_can_save_private_pay_scholarship_from_the_card(self):
        self._login_admin()
        plans = self.client.get(reverse("portal_admin_family_plans", kwargs={"family_slug": "jacobs"}))
        self.assertEqual(plans.status_code, 200)
        self.assertContains(plans, "Weekly rate ($)")
        self.assertContains(plans, 'name="billing_amount"')
        self.assertContains(plans, "Scholarship type")
        self.assertContains(plans, "Plan rate before scholarship")
        self.assertContains(plans, "Family pays after scholarship")
        self.assertContains(plans, "Add a scholarship on a regular plan")
        self.assertContains(plans, "Save plan")
        today = date(2026, 9, 9)
        weekday = today.weekday()
        with patch("portal.billing_services.timezone.localdate", return_value=today), patch(
            "portal.views_actions.timezone.localdate", return_value=today
        ):
            response = self.client.post(
                reverse("portal_staff_billing_action", kwargs={"family_slug": "jacobs"}),
                {
                    "portal_area": "admin",
                    "action": "update_plan",
                    "child_name": "Jordan Jacobs",
                    "billing_plan": "Weekly",
                    "billing_type": "Private pay",
                    "billing_amount": "70.00",
                    "auto_charge": "on",
                    "next_charge_date": today.isoformat(),
                    "charge_weekday": str(weekday),
                    "scholarship_fund_id": str(self.fund.pk),
                    "scholarship_full_rate": "70.00",
                    "scholarship_parent_amount": "50.00",
                    "next": reverse("portal_admin_family_plans", kwargs={"family_slug": "jacobs"}),
                },
            )
        self.assertEqual(response.status_code, 302)
        assignment = PortalScholarshipAssignment.objects.get(child=self.child)
        self.assertEqual(assignment.fund, self.fund)
        self.assertEqual(assignment.parent_amount, Decimal("50.00"))
        self.child.refresh_from_db()
        self.assertEqual(self.child.billing_amount, Decimal("70.00"))
        self.family.refresh_from_db()
        self.assertEqual(self.family.billing_type, "Private pay")
        self.assertEqual(self.family.balance, Decimal("50.00"))
        shown = self.client.get(reverse("portal_admin_family_plans", kwargs={"family_slug": "jacobs"}))
        self.assertContains(shown, "Amount")
        self.assertContains(shown, "70.00")
        self.assertContains(shown, "YEA General Scholarship")
        self.assertContains(shown, "Scholarship discount")
        self.assertContains(shown, "50.00")
        self.assertContains(shown, "Private pay")
        billing = self.client.get(reverse("portal_admin_family_billing", kwargs={"family_slug": "jacobs"}))
        self.assertContains(billing, "YEA General Scholarship")
        self.assertContains(billing, "70.00")

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_plans_page_keeps_monthly_amount_when_saving_scholarship(self):
        self.child.billing_plan = "Monthly"
        self.child.billing_amount = Decimal("280.00")
        self.child.save(update_fields=["billing_plan", "billing_amount"])
        self._login_admin()
        plans = self.client.get(reverse("portal_admin_family_plans", kwargs={"family_slug": "jacobs"}))
        self.assertContains(plans, "Monthly rate ($)")
        self.assertContains(plans, "280.00")
        self.assertContains(plans, 'name="billing_amount"')
        self.assertContains(plans, "Scholarship type")
        today = date(2026, 9, 9)
        with patch("portal.billing_services.timezone.localdate", return_value=today), patch(
            "portal.views_actions.timezone.localdate", return_value=today
        ):
            response = self.client.post(
                reverse("portal_staff_billing_action", kwargs={"family_slug": "jacobs"}),
                {
                    "portal_area": "admin",
                    "action": "update_plan",
                    "child_name": "Jordan Jacobs",
                    "billing_plan": "Monthly",
                    "billing_type": "Private pay",
                    "billing_amount": "280.00",
                    "auto_charge": "on",
                    "next_charge_date": today.isoformat(),
                    "charge_month_day": str(today.day),
                    "scholarship_fund_id": str(self.fund.pk),
                    "scholarship_full_rate": "280.00",
                    "scholarship_parent_amount": "200.00",
                    "next": reverse("portal_admin_family_plans", kwargs={"family_slug": "jacobs"}),
                },
            )
        self.assertEqual(response.status_code, 302)
        self.child.refresh_from_db()
        self.assertEqual(self.child.billing_amount, Decimal("280.00"))
        assignment = PortalScholarshipAssignment.objects.get(child=self.child)
        self.assertEqual(assignment.parent_amount, Decimal("200.00"))
        shown = self.client.get(reverse("portal_admin_family_plans", kwargs={"family_slug": "jacobs"}))
        self.assertContains(shown, "Amount")
        self.assertContains(shown, "280.00")
        self.assertContains(shown, "Monthly rate ($)")
        self.assertContains(shown, "YEA General Scholarship")
        self.assertContains(shown, "200.00")
        self.assertContains(shown, "Family pays")

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_plans_page_shows_amount_field_for_biweekly(self):
        self.child.billing_plan = "Bi-weekly"
        self.child.billing_amount = Decimal("140.00")
        self.child.save(update_fields=["billing_plan", "billing_amount"])
        self._login_admin()
        plans = self.client.get(reverse("portal_admin_family_plans", kwargs={"family_slug": "jacobs"}))
        self.assertContains(plans, "Bi-weekly rate ($)")
        self.assertContains(plans, "140.00")
        self.assertContains(plans, 'name="billing_amount"')
        self.assertContains(plans, "Scholarship type")


class MoneyOrderPaymentTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.unit = PortalUnit.objects.create(slug="school-18", name="School 18", is_active=True)
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

    def _login_admin(self):
        self.client.force_login(self.admin)
        session = self.client.session
        session[PORTAL_AUTH_SESSION_KEY] = "admin"
        session.save()

    def test_money_order_note_requires_number(self):
        with self.assertRaises(ValueError):
            staff_payment_note("money_order", "Weekly tuition")
        note, number = staff_payment_note("money_order", "Weekly tuition", money_order_number="1234567")
        self.assertEqual(note, "Weekly tuition")
        self.assertEqual(number, "1234567")
        note, number = staff_payment_note("money_order", "", money_order_number="1234567")
        self.assertEqual(note, "")
        self.assertEqual(number, "1234567")

    def test_check_and_cash_notes_still_work(self):
        note, number = staff_payment_note("check", "Weekly tuition", check_number="2201")
        self.assertEqual(note, "Weekly tuition")
        self.assertEqual(number, "2201")
        note, number = staff_payment_note("cash", "Weekly tuition")
        self.assertEqual(note, "Weekly tuition")
        self.assertEqual(number, "")

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_recording_money_order_stores_method_and_number(self):
        self._login_admin()
        response = self.client.post(
            reverse("portal_staff_billing_action", kwargs={"family_slug": "jacobs"}),
            {
                "portal_area": "admin",
                "action": "payment",
                "child_name": "Jordan Jacobs",
                "amount": "45.00",
                "method": "money_order",
                "money_order_number": "1234567",
                "note": "Weekly tuition",
            },
        )
        self.assertEqual(response.status_code, 302)
        entry = PortalLedgerEntry.objects.get(family=self.family, entry_type="payment")
        self.assertEqual(entry.reference_number, "1234567")
        self.assertEqual(entry.description, "Weekly tuition")
        self.assertEqual(entry.amount, Decimal("-45.00"))
        payment = PortalPayment.objects.get(family=self.family)
        self.assertEqual(payment.method_label, "Money order")
        self.assertEqual(payment.reference_number, "1234567")
        self.assertEqual(payment.status, PortalPayment.STATUS_PAID)
        billing = self.client.get(reverse("portal_admin_family_billing", kwargs={"family_slug": "jacobs"}))
        self.assertContains(billing, "Money order")
        self.assertContains(billing, "money_order_number")
        self.assertContains(billing, "Weekly tuition")
        self.assertContains(billing, "Money order #1234567")
        self.assertNotContains(billing, "Money order #1234567 — Weekly tuition")
        receipts = get_receipts_live(self.family)
        self.assertEqual(receipts[0]["method"], "Money order")
        self.assertEqual(receipts[0]["payment_reference"], "1234567")
        self.assertNotIn("1234567", receipts[0]["description"])
        printed = payment_to_receipt_dict(payment, "private-pay")
        self.assertEqual(printed["paid_through"], "Money order")
        self.assertEqual(printed["payment_reference"], "1234567")
        self.assertNotIn("1234567", printed["description"])

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_money_order_without_number_is_rejected(self):
        self._login_admin()
        response = self.client.post(
            reverse("portal_staff_billing_action", kwargs={"family_slug": "jacobs"}),
            {
                "portal_area": "admin",
                "action": "payment",
                "child_name": "Jordan Jacobs",
                "amount": "45.00",
                "method": "money_order",
                "note": "Weekly tuition",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(PortalLedgerEntry.objects.filter(family=self.family).exists())
        self.assertFalse(PortalPayment.objects.filter(family=self.family).exists())

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_cash_and_check_payments_still_record(self):
        self._login_admin()
        cash = self.client.post(
            reverse("portal_staff_billing_action", kwargs={"family_slug": "jacobs"}),
            {
                "portal_area": "admin",
                "action": "payment",
                "child_name": "Jordan Jacobs",
                "amount": "20.00",
                "method": "cash",
                "note": "Cash at desk",
            },
        )
        self.assertEqual(cash.status_code, 302)
        check = self.client.post(
            reverse("portal_staff_billing_action", kwargs={"family_slug": "jacobs"}),
            {
                "portal_area": "admin",
                "action": "payment",
                "child_name": "Jordan Jacobs",
                "amount": "25.00",
                "method": "check",
                "check_number": "2201",
                "note": "Weekly tuition",
            },
        )
        self.assertEqual(check.status_code, 302)
        descriptions = list(
            PortalLedgerEntry.objects.filter(family=self.family, entry_type="payment")
            .order_by("created_at")
            .values_list("description", "reference_number")
        )
        self.assertEqual(
            descriptions,
            [
                ("Cash at desk", ""),
                ("Weekly tuition", "2201"),
            ],
        )
        billing = self.client.get(reverse("portal_admin_family_billing", kwargs={"family_slug": "jacobs"}))
        self.assertContains(billing, "Cash at desk")
        self.assertContains(billing, "Weekly tuition")
        self.assertContains(billing, "Check #2201")
        self.assertNotContains(billing, "Check #2201 — Weekly tuition")


class FamilyNeighborNavTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.unit = PortalUnit.objects.create(slug="school-18", name="School 18", is_active=True)
        self.other_unit = PortalUnit.objects.create(slug="school-26", name="School 26", is_active=True)
        self.chen = PortalFamily.objects.create(unit=self.unit, slug="chen", name="Chen")
        self.jacobs = PortalFamily.objects.create(unit=self.unit, slug="jacobs", name="Jacobs")
        self.williams = PortalFamily.objects.create(unit=self.unit, slug="williams", name="Williams")
        self.lee = PortalFamily.objects.create(unit=self.other_unit, slug="lee", name="Lee")
        for family in (self.chen, self.jacobs, self.williams):
            _make_application(family)
        _make_application(self.lee, location="school_26")
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

    def _login(self, user, area):
        self.client.force_login(user)
        session = self.client.session
        session[PORTAL_AUTH_SESSION_KEY] = area
        session.save()

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_staff_profile_next_follows_name_order_and_hides_on_last(self):
        self._login(self.staff, "staff")
        middle = self.client.get(reverse("portal_staff_family_detail", kwargs={"family_slug": "jacobs"}))
        self.assertEqual(middle.status_code, 200)
        self.assertContains(middle, "portal-family-pager")
        self.assertNotContains(middle, "portal-family-neighbor-nav")
        self.assertContains(middle, "Next · Ada Williams")
        self.assertContains(middle, reverse("portal_staff_family_detail", kwargs={"family_slug": "williams"}))
        self.assertContains(middle, "portal-family-pager-prev")
        self.assertContains(middle, reverse("portal_staff_family_detail", kwargs={"family_slug": "chen"}))
        self.assertNotContains(middle, "Next · Ada Lee")

        last = self.client.get(reverse("portal_staff_family_detail", kwargs={"family_slug": "williams"}))
        self.assertEqual(last.status_code, 200)
        self.assertContains(last, "portal-family-pager-prev")
        self.assertContains(last, reverse("portal_staff_family_detail", kwargs={"family_slug": "jacobs"}))
        self.assertNotContains(last, "portal-family-pager-next")

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_staff_billing_next_stays_on_billing_tab(self):
        self._login(self.staff, "staff")
        billing = self.client.get(reverse("portal_staff_family_billing", kwargs={"family_slug": "chen"}))
        self.assertEqual(billing.status_code, 200)
        next_billing = reverse("portal_staff_family_billing", kwargs={"family_slug": "jacobs"})
        self.assertContains(billing, f'href="{next_billing}')
        self.assertContains(billing, "Next · Ada Jacobs")
        self.assertNotContains(billing, "portal-family-neighbor-nav")
        profile_url = reverse("portal_staff_family_detail", kwargs={"family_slug": "jacobs"})
        neighbor = billing.context["family_next"]
        self.assertTrue(neighbor["url"].startswith(next_billing))
        self.assertIn("Ada Jacobs", neighbor["url"] + neighbor["name"])
        self.assertNotEqual(neighbor["url"].split("?")[0], profile_url)

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_admin_next_preserves_id_and_stays_on_billing(self):
        self._login(self.admin, "admin")
        billing = self.client.get(
            reverse("portal_admin_family_billing", kwargs={"family_slug": "jacobs"}),
            {"id": self.jacobs.pk},
        )
        self.assertEqual(billing.status_code, 200)
        next_path = reverse("portal_admin_family_billing", kwargs={"family_slug": "lee"})
        self.assertContains(billing, "Next · Ada Lee")
        self.assertContains(billing, f"{next_path}?id={self.lee.pk}")
        self.assertNotContains(billing, "portal-family-neighbor-nav")
        next_url = billing.context["family_next"]["url"]
        self.assertTrue(next_url.startswith(f"{next_path}?"))
        self.assertIn(f"id={self.lee.pk}", next_url)

        last = self.client.get(
            reverse("portal_admin_family_detail", kwargs={"family_slug": "williams"}),
            {"id": self.williams.pk},
        )
        self.assertEqual(last.status_code, 200)
        self.assertContains(last, "portal-family-pager-prev")
        self.assertContains(last, reverse("portal_admin_family_detail", kwargs={"family_slug": "lee"}))
        self.assertNotContains(last, "portal-family-pager-next")

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_admin_colliding_slugs_use_id_for_next(self):
        twin = PortalFamily.objects.create(unit=self.other_unit, slug="jacobs", name="Jacobs")
        _make_application(twin, location="school_26")
        self._login(self.admin, "admin")
        # Child name A–Z: Ada Chen, Ada Jacobs (18), Ada Jacobs (26), Ada Lee, Ada Williams
        response = self.client.get(
            reverse("portal_admin_family_detail", kwargs={"family_slug": "jacobs"}),
            {"id": self.jacobs.pk},
        )
        self.assertEqual(response.status_code, 200)
        next_path = reverse("portal_admin_family_detail", kwargs={"family_slug": "jacobs"})
        self.assertContains(response, f"{next_path}?id={twin.pk}")
        self.assertEqual(response.context["family_next"]["id"], twin.pk)

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_admin_parent_view_next_stays_on_parent_view(self):
        self._login(self.admin, "admin")
        response = self.client.get(
            reverse("portal_admin_parent_preview", kwargs={"family_slug": "chen"}),
            {"id": self.chen.pk},
        )
        self.assertEqual(response.status_code, 200)
        next_path = reverse("portal_admin_parent_preview", kwargs={"family_slug": "jacobs"})
        self.assertContains(response, f"{next_path}?id={self.jacobs.pk}")
        self.assertContains(response, "Next: Ada Jacobs")


class FamilyListPagerFilterTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.school_18 = PortalUnit.objects.create(slug="school-18", name="School 18", is_active=True)
        self.school_26 = PortalUnit.objects.create(slug="school-26", name="School 26", is_active=True)
        self.admin = User.objects.create_user(username="staff:yeaadmin", password="AdminPass123")
        PortalStaffAccount.objects.create(
            user=self.admin,
            unit=self.school_18,
            display_name="Portal Admin",
            role="Portal admin",
            all_units_access=True,
            is_active=True,
        )
        self.staff = User.objects.create_user(username="staff:unit18", password="StaffPass123")
        PortalStaffAccount.objects.create(
            user=self.staff,
            unit=self.school_18,
            display_name="School 18 Staff",
            role="Unit director",
            all_units_access=False,
            is_active=True,
        )
        names_18 = [
            ("ava", "Ava Brooks"),
            ("ben", "Ben Carter"),
            ("cara", "Cara Diaz"),
            ("drew", "Drew Evans"),
        ]
        self.families_18 = []
        for slug, child_name in names_18:
            family = PortalFamily.objects.create(unit=self.school_18, slug=slug, name=child_name.split()[-1], status="Active")
            family.children.create(name=child_name, school="Paterson School 18", is_active=True)
            self.families_18.append(family)
        other = PortalFamily.objects.create(unit=self.school_26, slug="zoe", name="Foster", status="Active")
        other.children.create(name="Zoe Foster", school="Paterson School 26", is_active=True)
        self.other = other

    def _login(self, user, area):
        self.client.force_login(user)
        session = self.client.session
        session[PORTAL_AUTH_SESSION_KEY] = area
        session.save()

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_admin_filtered_unit_opens_third_child_as_three_of_n(self):
        self._login(self.admin, "admin")
        cara = self.families_18[2]
        cara_child = cara.children.get()
        response = self.client.get(
            reverse("portal_admin_family_detail", kwargs={"family_slug": "cara"}),
            {
                "id": cara.pk,
                "child_id": cara_child.pk,
                "child": "Cara Diaz",
                "unit": "school-18",
                "list": "1",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["family_nav_index"], 3)
        self.assertEqual(response.context["family_nav_count"], 4)
        self.assertContains(response, "3 of 4")
        nxt = response.context["family_next"]
        self.assertEqual(nxt["slug"], "drew")
        self.assertEqual(nxt["name"], "Drew Evans")
        self.assertIn("unit=school-18", nxt["url"])
        self.assertIn("list=1", nxt["url"])
        self.assertNotEqual(nxt["slug"], "zoe")

        next_page = self.client.get(nxt["url"])
        self.assertEqual(next_page.status_code, 200)
        self.assertEqual(next_page.context["family_nav_index"], 4)
        self.assertEqual(next_page.context["family_nav_count"], 4)
        self.assertContains(next_page, "4 of 4")
        self.assertIsNone(next_page.context["family_next"])
        self.assertNotIn("zoe", (next_page.context["family_prev"] or {}).get("slug", ""))

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_admin_search_filter_opens_third_child_as_three_of_n(self):
        self._login(self.admin, "admin")
        cara = self.families_18[2]
        cara_child = cara.children.get()
        response = self.client.get(
            reverse("portal_admin_family_detail", kwargs={"family_slug": "cara"}),
            {
                "id": cara.pk,
                "child_id": cara_child.pk,
                "child": "Cara Diaz",
                "q": "Diaz",
                "list": "1",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["family_nav_index"], 1)
        self.assertEqual(response.context["family_nav_count"], 1)
        self.assertContains(response, "1 of 1")
        self.assertContains(response, "portal-family-pager")
        self.assertIsNone(response.context["family_next"])
        self.assertIsNone(response.context["family_prev"])

        quill_rows = []
        for slug, child_name in (("quin-a", "Ada Quill"), ("quin-b", "Bea Quill"), ("quin-c", "Cy Quill")):
            family = PortalFamily.objects.create(
                unit=self.school_18, slug=slug, name="Quill", status="Active"
            )
            child = family.children.create(name=child_name, school="Paterson School 18", is_active=True)
            quill_rows.append((family, child))
        _middle_family, middle_child = quill_rows[1]
        searched = self.client.get(
            reverse("portal_admin_family_detail", kwargs={"family_slug": "quin-b"}),
            {
                "id": middle_child.family_id,
                "child_id": middle_child.pk,
                "child": "Bea Quill",
                "q": "Quill",
                "list": "1",
            },
        )
        self.assertEqual(searched.status_code, 200)
        self.assertEqual(searched.context["family_nav_count"], 3)
        self.assertEqual(searched.context["family_nav_index"], 2)
        self.assertContains(searched, "2 of 3")
        self.assertEqual(searched.context["family_prev"]["name"], "Ada Quill")
        self.assertEqual(searched.context["family_next"]["name"], "Cy Quill")
        self.assertIn("q=Quill", searched.context["family_next"]["url"])

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_admin_unfiltered_pager_includes_every_visible_child(self):
        self._login(self.admin, "admin")
        cara = self.families_18[2]
        response = self.client.get(
            reverse("portal_admin_family_detail", kwargs={"family_slug": "cara"}),
            {"id": cara.pk, "child": "Cara Diaz", "list": "1"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["family_nav_count"], 5)
        self.assertEqual(response.context["family_nav_index"], 3)
        self.assertEqual(response.context["family_next"]["name"], "Drew Evans")

        unfiltered = self.client.get(
            reverse("portal_admin_family_detail", kwargs={"family_slug": "cara"}),
            {"id": cara.pk, "child": "Cara Diaz"},
        )
        self.assertEqual(unfiltered.context["family_nav_count"], 5)

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_pager_walks_sibling_child_rows_in_same_family(self):
        family = PortalFamily.objects.create(unit=self.school_18, slug="twins", name="Twins", status="Active")
        older = family.children.create(name="Mia Twins", school="Paterson School 18", is_active=True)
        younger = family.children.create(name="Noah Twins", school="Paterson School 18", is_active=True)
        self._login(self.admin, "admin")
        response = self.client.get(
            reverse("portal_admin_family_detail", kwargs={"family_slug": "twins"}),
            {
                "id": family.pk,
                "child_id": older.pk,
                "child": "Mia Twins",
                "unit": "school-18",
                "list": "1",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["family_next"]["name"], "Noah Twins")
        self.assertEqual(response.context["family_next"]["slug"], "twins")
        self.assertIn(f"child_id={younger.pk}", response.context["family_next"]["url"])

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_staff_pager_stays_in_staff_unit(self):
        self._login(self.staff, "staff")
        session = self.client.session
        session["staff_unit_slug"] = "school-18"
        session.save()
        cara = self.families_18[2]
        response = self.client.get(
            reverse("portal_staff_family_detail", kwargs={"family_slug": "cara"}),
            {"child": "Cara Diaz", "list": "1"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["family_nav_index"], 3)
        self.assertEqual(response.context["family_nav_count"], 4)
        self.assertEqual(response.context["family_next"]["name"], "Drew Evans")
        self.assertNotEqual(response.context["family_next"]["slug"], "zoe")
