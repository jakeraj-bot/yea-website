from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from portal.billing_services import (
    first_plan_charge_date,
    post_credit,
    post_payment,
    update_child_billing_plan,
    update_ledger_description,
)
from portal.models import (
    PortalChild,
    PortalFamily,
    PortalLedgerEntry,
    PortalStaffAccount,
    PortalUnit,
)
from portal.staff_auth import PORTAL_AUTH_SESSION_KEY
from portal.tests.test_family_units import _make_application


class FamilyAccountHubTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.unit = PortalUnit.objects.create(slug="school-18", name="School 18", is_active=True)
        self.family = PortalFamily.objects.create(unit=self.unit, slug="jacobs", name="Jacobs")
        self.next_family = PortalFamily.objects.create(unit=self.unit, slug="martinez", name="Martinez")
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
        self.assertContains(response, "portal-family-tabs-colorful")
        for label in ("Profile", "Billing", "Plans", "4Cs", "Applications", "Policies", "Email parent", "Incidents", "Pickup", "Parent view"):
            self.assertContains(response, label)

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_admin_member_account_has_next_button_to_next_family(self):
        self._login(self.admin, "admin")
        profile = self.client.get(reverse("portal_admin_family_detail", kwargs={"family_slug": "jacobs"}))
        billing = self.client.get(reverse("portal_admin_family_billing", kwargs={"family_slug": "jacobs"}))
        self.assertEqual(profile.status_code, 200)
        self.assertEqual(billing.status_code, 200)
        next_url = reverse("portal_admin_family_detail", kwargs={"family_slug": "martinez"})
        next_billing = reverse("portal_admin_family_billing", kwargs={"family_slug": "martinez"})
        self.assertContains(profile, "portal-family-pager-next")
        self.assertContains(profile, next_url)
        self.assertContains(billing, "portal-family-pager-next")
        self.assertContains(billing, next_billing)

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_staff_member_account_has_next_button_to_next_family(self):
        self._login(self.staff, "staff")
        response = self.client.get(reverse("portal_staff_family_detail", kwargs={"family_slug": "jacobs"}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "portal-family-pager-next")
        self.assertContains(response, reverse("portal_staff_family_detail", kwargs={"family_slug": "martinez"}))

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
        self.assertContains(middle, "portal-family-neighbor-nav")
        self.assertContains(middle, "Next: Williams")
        self.assertContains(middle, reverse("portal_staff_family_detail", kwargs={"family_slug": "williams"}))
        self.assertContains(middle, "Previous: Chen")
        self.assertNotContains(middle, "Next: Lee")

        last = self.client.get(reverse("portal_staff_family_detail", kwargs={"family_slug": "williams"}))
        self.assertEqual(last.status_code, 200)
        self.assertContains(last, "Previous: Jacobs")
        self.assertNotContains(last, "Next:")

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_staff_billing_next_stays_on_billing_tab(self):
        self._login(self.staff, "staff")
        billing = self.client.get(reverse("portal_staff_family_billing", kwargs={"family_slug": "chen"}))
        self.assertEqual(billing.status_code, 200)
        next_billing = reverse("portal_staff_family_billing", kwargs={"family_slug": "jacobs"})
        self.assertContains(billing, f'href="{next_billing}')
        self.assertContains(billing, "Next: Jacobs")
        profile_url = reverse("portal_staff_family_detail", kwargs={"family_slug": "jacobs"})
        neighbor = billing.context["family_next"]
        self.assertEqual(neighbor["url"], next_billing)
        self.assertNotEqual(neighbor["url"], profile_url)

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_admin_next_preserves_id_and_stays_on_billing(self):
        self._login(self.admin, "admin")
        billing = self.client.get(
            reverse("portal_admin_family_billing", kwargs={"family_slug": "williams"}),
            {"id": self.williams.pk},
        )
        self.assertEqual(billing.status_code, 200)
        next_path = reverse("portal_admin_family_billing", kwargs={"family_slug": "lee"})
        self.assertContains(billing, "Next: Lee")
        self.assertContains(billing, f"{next_path}?id={self.lee.pk}")
        self.assertEqual(
            billing.context["family_next"]["url"],
            f"{next_path}?id={self.lee.pk}",
        )

        last = self.client.get(
            reverse("portal_admin_family_detail", kwargs={"family_slug": "lee"}),
            {"id": self.lee.pk},
        )
        self.assertEqual(last.status_code, 200)
        self.assertContains(last, "Previous: Williams")
        self.assertNotContains(last, "Next:")

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_admin_colliding_slugs_use_id_for_next(self):
        twin = PortalFamily.objects.create(unit=self.other_unit, slug="jacobs", name="Jacobs")
        _make_application(twin, location="school_26")
        self._login(self.admin, "admin")
        # School 18 Chen, Jacobs, Williams then School 26 Jacobs, Lee
        response = self.client.get(
            reverse("portal_admin_family_detail", kwargs={"family_slug": "williams"}),
            {"id": self.williams.pk},
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
        self.assertContains(response, "Next: Jacobs")
