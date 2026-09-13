from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from portal.activity_log import log_activity
from portal.billing_services import post_charge
from portal.models import (
    PortalActivityEvent,
    PortalChild,
    PortalFamily,
    PortalLedgerEntry,
    PortalStaffAccount,
    PortalUnit,
)
from portal.staff_auth import PORTAL_AUTH_SESSION_KEY


@override_settings(PORTAL_PREVIEW_MODE=False)
class ActivityLogUserFilterTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.unit = PortalUnit.objects.create(slug="school-18", name="School 18", is_active=True)
        self.admin = User.objects.create_user(username="staff:yeaadmin", password="AdminPass123")
        PortalStaffAccount.objects.create(
            user=self.admin,
            unit=self.unit,
            display_name="Jakera",
            role="Portal admin",
            all_units_access=True,
            is_active=True,
            can_delete_charge=True,
        )
        self.staff = User.objects.create_user(username="staff:unitone", password="StaffPass123")
        PortalStaffAccount.objects.create(
            user=self.staff,
            unit=self.unit,
            display_name="Unit Staff",
            role="Unit staff",
            is_active=True,
        )
        log_activity(
            user=self.admin,
            action=PortalActivityEvent.ACTION_LOGIN,
            action_label="Signed in",
            object_label="Admin portal",
        )
        log_activity(
            user=self.staff,
            action=PortalActivityEvent.ACTION_SAVE,
            action_label="Saved family",
            object_label="Rivera",
        )
        self.client.force_login(self.admin)
        session = self.client.session
        session[PORTAL_AUTH_SESSION_KEY] = "admin"
        session.save()

    def test_activity_page_asks_to_pick_a_person_first(self):
        response = self.client.get(reverse("portal_admin_page", kwargs={"page": "activity"}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Choose a person")
        self.assertContains(response, "Jakera")
        self.assertContains(response, "Unit Staff")
        self.assertContains(response, "Open activity")
        self.assertNotContains(response, "Saved family")

    def test_picking_a_user_lists_only_their_events(self):
        response = self.client.get(
            reverse("portal_admin_page", kwargs={"page": "activity"}),
            {"user": str(self.staff.pk)},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Unit Staff")
        self.assertContains(response, "Saved family")
        self.assertContains(response, "Rivera")
        self.assertNotContains(response, "Admin portal")
        self.assertNotContains(response, "Signed in")

    def test_activity_sections_are_collapse_ready(self):
        response = self.client.get(reverse("portal_admin_page", kwargs={"page": "activity"}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "portal-collapse.js")
        self.assertContains(response, "<h2>Choose a person</h2>")
        self.assertContains(response, 'class="card"')
        self.assertNotContains(response, "portal-collapse-skip")
        self.assertNotContains(response, "My activity")
        picked = self.client.get(
            reverse("portal_admin_page", kwargs={"page": "activity"}),
            {"user": str(self.staff.pk)},
        )
        self.assertContains(picked, "<h2>Unit Staff</h2>")
        self.assertNotContains(picked, "portal-collapse-skip")

    def test_staff_cannot_open_activity_urls(self):
        self.client.force_login(self.staff)
        session = self.client.session
        session[PORTAL_AUTH_SESSION_KEY] = "staff"
        session.save()
        staff_url = self.client.get(reverse("portal_staff_page", kwargs={"page": "activity"}))
        self.assertEqual(staff_url.status_code, 403)
        admin_url = self.client.get(reverse("portal_admin_page", kwargs={"page": "activity"}))
        self.assertIn(admin_url.status_code, {302, 403})
        self.assertNotEqual(admin_url.status_code, 200)
        dashboard = self.client.get(reverse("portal_staff_page", kwargs={"page": "dashboard"}))
        self.assertEqual(dashboard.status_code, 200)
        self.assertNotContains(dashboard, "My activity")
        self.assertNotContains(dashboard, "portal-nav-staff-activity")


@override_settings(PORTAL_PREVIEW_MODE=False)
class DeleteReasonActivityTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.unit = PortalUnit.objects.create(slug="school-18", name="School 18", is_active=True)
        self.family = PortalFamily.objects.create(unit=self.unit, slug="jacobs", name="Jacobs", status="Active")
        self.child = PortalChild.objects.create(family=self.family, name="Jordan Jacobs")
        self.admin = User.objects.create_user(username="staff:yeaadmin", password="AdminPass123")
        PortalStaffAccount.objects.create(
            user=self.admin,
            unit=self.unit,
            display_name="Jakera",
            role="Portal admin",
            all_units_access=True,
            is_active=True,
            can_delete_charge=True,
        )
        self.client.force_login(self.admin)
        session = self.client.session
        session[PORTAL_AUTH_SESSION_KEY] = "admin"
        session.save()

    def _post_charge(self):
        return post_charge(
            self.family,
            "Jordan Jacobs",
            "manual",
            "25.00",
            timezone.localdate(),
            "Test charge",
        )

    def test_delete_without_reason_is_blocked(self):
        entry = self._post_charge()
        response = self.client.post(
            reverse("portal_staff_billing_action", kwargs={"family_slug": "jacobs"}),
            {
                "portal_area": "admin",
                "family_id": str(self.family.pk),
                "action": "delete",
                "entry_id": str(entry.pk),
                "delete_reason": "   ",
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(PortalLedgerEntry.objects.filter(pk=entry.pk).exists())
        self.assertContains(response, "Enter a reason before deleting")
        self.assertFalse(
            PortalActivityEvent.objects.filter(action=PortalActivityEvent.ACTION_DELETE, actor=self.admin).exists()
        )

    def test_delete_with_reason_appears_on_that_users_log(self):
        entry = self._post_charge()
        response = self.client.post(
            reverse("portal_staff_billing_action", kwargs={"family_slug": "jacobs"}),
            {
                "portal_area": "admin",
                "family_id": str(self.family.pk),
                "action": "delete",
                "entry_id": str(entry.pk),
                "delete_reason": "Duplicate charge posted twice",
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(PortalLedgerEntry.objects.filter(pk=entry.pk).exists())
        event = PortalActivityEvent.objects.get(action=PortalActivityEvent.ACTION_DELETE, actor=self.admin)
        self.assertEqual(event.delete_reason, "Duplicate charge posted twice")
        page = self.client.get(
            reverse("portal_admin_page", kwargs={"page": "activity"}),
            {"user": str(self.admin.pk)},
        )
        self.assertContains(page, "Deleted charge")
        self.assertContains(page, "Duplicate charge posted twice")
        self.assertContains(page, "Why deleted")

    def test_date_range_hides_older_events(self):
        old = log_activity(
            user=self.admin,
            action=PortalActivityEvent.ACTION_LOGIN,
            action_label="Signed in",
            object_label="Old sign-in",
        )
        PortalActivityEvent.objects.filter(pk=old.pk).update(created_at=timezone.now() - timedelta(days=10))
        log_activity(
            user=self.admin,
            action=PortalActivityEvent.ACTION_SAVE,
            action_label="Saved family",
            object_label="Today save",
        )
        today = timezone.localdate().isoformat()
        page = self.client.get(
            reverse("portal_admin_page", kwargs={"page": "activity"}),
            {"user": str(self.admin.pk), "date_from": today, "date_to": today},
        )
        self.assertContains(page, "Today save")
        self.assertNotContains(page, "Old sign-in")

    def test_recording_a_payment_appears_on_that_users_log(self):
        response = self.client.post(
            reverse("portal_staff_billing_action", kwargs={"family_slug": "jacobs"}),
            {
                "portal_area": "admin",
                "family_id": str(self.family.pk),
                "action": "payment",
                "child_name": "Jordan Jacobs",
                "amount": "20.00",
                "method": "cash",
                "note": "Desk payment",
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        event = PortalActivityEvent.objects.get(action=PortalActivityEvent.ACTION_PAYMENT, actor=self.admin)
        self.assertEqual(event.action_label, "Recorded a payment")
        self.assertEqual(event.object_type, "family")
        self.assertEqual(event.object_label, "Jacobs")
        self.assertNotIn("4242", event.details)
        page = self.client.get(
            reverse("portal_admin_page", kwargs={"page": "activity"}),
            {"user": str(self.admin.pk)},
        )
        self.assertContains(page, "Recorded a payment")
        self.assertContains(page, "Jacobs")
