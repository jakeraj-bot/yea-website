from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from portal.models import PortalFamily, PortalStaffAccount, PortalUnit
from portal.staff_auth import PORTAL_AUTH_SESSION_KEY
from portal.tests.test_family_units import _make_application


class FamilyAccountHubTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.unit = PortalUnit.objects.create(slug="school-18", name="School 18", is_active=True)
        self.family = PortalFamily.objects.create(unit=self.unit, slug="jacobs", name="Jacobs")
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

