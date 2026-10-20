from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from portal.models import PortalFamily, PortalParentAccount, PortalStaffAccount, PortalUnit
from portal.page_guides import guide_for
from portal.staff_auth import PORTAL_AUTH_SESSION_KEY


class PortalPageCopyMovedToHelpTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.unit = PortalUnit.objects.create(slug="school-18", name="School 18", is_active=True)
        self.family = PortalFamily.objects.create(unit=self.unit, slug="jacobs", name="Jacobs")
        self.admin_user = User.objects.create_user(username="admin:yeaadmin", password="AdminPass123")
        PortalStaffAccount.objects.create(
            user=self.admin_user,
            unit=self.unit,
            display_name="YEA Admin",
            role="Portal admin",
            all_units_access=True,
            is_active=True,
        )
        self.staff_user = User.objects.create_user(username="staff:unitstaff", password="StaffPass123")
        PortalStaffAccount.objects.create(
            user=self.staff_user,
            unit=self.unit,
            display_name="Unit Staff",
            role="Unit staff",
            all_units_access=False,
            is_active=True,
        )
        self.parent_user = User.objects.create_user(username="parent:jacobs", password="ParentPass123")
        PortalParentAccount.objects.create(user=self.parent_user, family=self.family)

    def _login(self, user, area):
        self.client.force_login(user)
        session = self.client.session
        session[PORTAL_AUTH_SESSION_KEY] = area
        session.save()

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_admin_dashboard_has_no_page_intro(self):
        self._login(self.admin_user, "admin")
        page = self.client.get(reverse("portal_admin_page", kwargs={"page": "dashboard"}))
        self.assertEqual(page.status_code, 200)
        self.assertNotContains(page, "Enrollment, billing, and staff at a glance.")
        self.assertNotContains(page, "Highest overdue first so you know which site to work down.")
        self.assertContains(page, "How to use this page")
        self.assertContains(page, "Balances by unit")
        admin_guide = guide_for("admin-dashboard")
        bodies = " ".join(step["body"] for step in admin_guide["steps"])
        self.assertIn("Balances by unit", bodies)

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_families_pages_drop_click_through_blurb(self):
        self._login(self.staff_user, "staff")
        staff = self.client.get(reverse("portal_staff_page", kwargs={"page": "families"}))
        self.assertEqual(staff.status_code, 200)
        self.assertNotContains(staff, "click through to profile")
        self.assertNotContains(staff, "accounts stay on file so they can come back")
        self.assertContains(staff, "How to use this page")
        self.assertContains(staff, "Inactive tab")

        self._login(self.admin_user, "admin")
        admin = self.client.get(reverse("portal_admin_page", kwargs={"page": "families"}))
        self.assertEqual(admin.status_code, 200)
        self.assertNotContains(admin, "listed A–Z by child name, then open billing or policies.")
        self.assertContains(admin, "How to use this page")

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_waitlist_and_weekly_attendance_drop_filter_essays(self):
        self._login(self.staff_user, "staff")
        waitlist = self.client.get(reverse("portal_staff_page", kwargs={"page": "waitlist"}))
        self.assertEqual(waitlist.status_code, 200)
        self.assertNotContains(waitlist, "families waiting for a before care spot")
        self.assertNotContains(waitlist, "All prints both")
        self.assertContains(waitlist, "How to use this page")

        weekly = self.client.get(reverse("portal_staff_weekly_attendance_report"))
        self.assertEqual(weekly.status_code, 200)
        self.assertNotContains(weekly, "All prints both")
        self.assertNotContains(
            weekly,
            "Check grades to keep those kids on this same Monday–Friday sheet.",
        )
        self.assertContains(weekly, "How to use this page")
        self.assertContains(weekly, "Pick a unit, then After-care, Before-care, or All")

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_parent_dashboard_and_billing_drop_intros(self):
        self._login(self.parent_user, "parent")
        dashboard = self.client.get(reverse("portal_parent_page", kwargs={"page": "dashboard"}))
        self.assertEqual(dashboard.status_code, 200)
        self.assertNotContains(dashboard, "parent-pay-howto.mp4")
        self.assertNotContains(dashboard, "Running balance, charges, and payments for your household.")
        self.assertContains(dashboard, reverse("portal_parent_page", kwargs={"page": "help"}))

        billing = self.client.get(reverse("portal_parent_page", kwargs={"page": "billing"}))
        self.assertEqual(billing.status_code, 200)
        self.assertNotContains(billing, "Running balance, charges, and payments for your household.")
        self.assertContains(billing, reverse("portal_parent_page", kwargs={"page": "help"}))

        help_page = self.client.get(reverse("portal_parent_page", kwargs={"page": "help"}))
        self.assertEqual(help_page.status_code, 200)
        self.assertContains(help_page, "parent-pay-howto.mp4")
        self.assertContains(help_page, "Tap Pay now")
        self.assertContains(help_page, "Account settings is for login")
        self.assertContains(help_page, "Pick a day and time we have a spot")
