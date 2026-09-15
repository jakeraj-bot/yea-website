from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse

from portal.models import (
    PortalChild,
    PortalFamily,
    PortalParentAccount,
    PortalProfileChangeRequest,
    PortalStaffAccount,
    PortalUnit,
)
from portal.staff_auth import PORTAL_AUTH_SESSION_KEY
from portal.tests.test_family_units import _make_application


@override_settings(
    PORTAL_PREVIEW_MODE=False,
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
)
class ParentProfilePendingReviewTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.school_18 = PortalUnit.objects.create(
            slug="school-18",
            name="School 18",
            program_type="after_school",
            is_active=True,
        )
        self.school_26 = PortalUnit.objects.create(
            slug="school-26",
            name="School 26",
            program_type="after_school",
            is_active=True,
        )
        self.family = PortalFamily.objects.create(
            unit=self.school_18,
            slug="rivera",
            name="Rivera",
            primary_contact="Pat Rivera",
            status="Active",
        )
        self.child = PortalChild.objects.create(
            family=self.family,
            unit=self.school_18,
            name="Ada Rivera",
            grade="3",
            is_active=True,
        )
        self.app = _make_application(self.family, status="approved")
        self.app.student_first_name = "Ada"
        self.app.student_last_name = "Rivera"
        self.app.primary_first_name = "Pat"
        self.app.primary_last_name = "Rivera"
        self.app.primary_phone = "555-0100"
        self.app.home_address = "1 Main St"
        self.app.save()

        self.parent_user = User.objects.create_user(
            username="parent:rivera",
            password="ParentPass123",
            email="pat@example.com",
            first_name="Pat",
            last_name="Rivera",
        )
        self.parent_account = PortalParentAccount.objects.create(user=self.parent_user, family=self.family)

        self.admin_user = User.objects.create_user(username="staff:yeaadmin", password="AdminPass123")
        PortalStaffAccount.objects.create(
            user=self.admin_user,
            unit=self.school_18,
            display_name="Portal Admin",
            role="Portal admin",
            all_units_access=True,
            is_active=True,
        )
        self.staff_18 = User.objects.create_user(username="staff:unit18", password="StaffPass123!")
        PortalStaffAccount.objects.create(
            user=self.staff_18,
            unit=self.school_18,
            display_name="School 18 Staff",
            role="Unit director",
            is_active=True,
        )
        self.staff_26 = User.objects.create_user(username="staff:unit26", password="StaffPass123!")
        PortalStaffAccount.objects.create(
            user=self.staff_26,
            unit=self.school_26,
            display_name="School 26 Staff",
            role="Unit director",
            is_active=True,
        )

    def _login(self, user, area, unit_slug=None):
        self.client.force_login(user)
        session = self.client.session
        session[PORTAL_AUTH_SESSION_KEY] = area
        if area == "staff":
            session["staff_unit_slug"] = unit_slug or "school-18"
        session.save()

    def _submit_parent_change(self, **overrides):
        self._login(self.parent_user, "parent")
        payload = {
            "home_address": "1 Main St",
            "primary_name": "Pat Rivera",
            "primary_phone": "555-0100",
            "primary_email": "pat@example.com",
            "primary_relationship": "Mother",
        }
        payload.update(overrides)
        return self.client.post(reverse("portal_parent_profile_save"), payload, follow=True)

    @patch("core.email_service.email_is_configured", return_value=True)
    def test_parent_submit_appears_on_admin_and_staff_pending_reviews(self, _configured):
        response = self._submit_parent_change(home_address="99 Oak Ave", primary_phone="555-0199")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Changes pending staff review")
        self.assertContains(response, "99 Oak Ave")
        self.assertContains(response, "Pending review")

        change = PortalProfileChangeRequest.objects.get(account=self.parent_account)
        self.assertEqual(change.status, PortalProfileChangeRequest.STATUS_PENDING)
        self.assertEqual(change.changes["home_address"]["to"], "99 Oak Ave")
        self.assertEqual(change.changes["primary_phone"]["to"], "555-0199")
        self.assertTrue(mail.outbox)
        self.assertIn("Profile change to review", mail.outbox[0].subject)
        self.assertIn("99 Oak Ave", mail.outbox[0].body)

        self._login(self.admin_user, "admin")
        admin_list = self.client.get(reverse("portal_admin_page", kwargs={"page": "pending-reviews"}))
        self.assertEqual(admin_list.status_code, 200)
        self.assertContains(admin_list, "Pending reviews")
        self.assertContains(admin_list, "Rivera")
        self.assertContains(admin_list, "99 Oak Ave")
        self.assertContains(admin_list, "Approve")
        self.assertContains(admin_list, "How to use this page")
        apps = self.client.get(reverse("portal_admin_page", kwargs={"page": "applications"}))
        self.assertContains(apps, "Pending reviews")

        dashboard = self.client.get(reverse("portal_admin_page", kwargs={"page": "dashboard"}))
        self.assertContains(dashboard, "parent profile change")
        self.assertContains(dashboard, reverse("portal_admin_page", kwargs={"page": "pending-reviews"}))

        family = self.client.get(reverse("portal_admin_family_detail", kwargs={"family_slug": "rivera"}))
        self.assertContains(family, "Pending profile reviews")
        self.assertContains(family, "99 Oak Ave")

        self._login(self.staff_18, "staff", "school-18")
        staff_list = self.client.get(reverse("portal_staff_page", kwargs={"page": "pending-reviews"}))
        self.assertEqual(staff_list.status_code, 200)
        self.assertContains(staff_list, "Rivera")
        self.assertContains(staff_list, "99 Oak Ave")
        today = self.client.get(reverse("portal_staff_page", kwargs={"page": "dashboard"}))
        self.assertContains(today, "parent profile change")

        self._login(self.staff_26, "staff", "school-26")
        other_unit = self.client.get(reverse("portal_staff_page", kwargs={"page": "pending-reviews"}))
        self.assertNotContains(other_unit, "99 Oak Ave")
        self.assertContains(other_unit, "No parent profile changes waiting for review")

    def test_admin_approve_applies_and_clears_parent_pending(self):
        self._submit_parent_change(home_address="99 Oak Ave", primary_phone="555-0199")
        change = PortalProfileChangeRequest.objects.get(account=self.parent_account)

        self._login(self.admin_user, "admin")
        approve = self.client.post(
            reverse("portal_admin_profile_change"),
            {"change_id": change.pk, "action": "approve"},
            follow=True,
        )
        self.assertEqual(approve.status_code, 200)
        self.assertContains(approve, "Profile change approved")

        change.refresh_from_db()
        self.app.refresh_from_db()
        self.family.refresh_from_db()
        self.assertEqual(change.status, PortalProfileChangeRequest.STATUS_APPROVED)
        self.assertEqual(self.app.home_address, "99 Oak Ave")
        self.assertEqual(self.app.primary_phone, "555-0199")

        self._login(self.parent_user, "parent")
        profile = self.client.get(reverse("portal_parent_page", kwargs={"page": "profile"}))
        self.assertContains(profile, "99 Oak Ave")
        self.assertIn('id="pending-review-banner" hidden', profile.content.decode())
        self.assertFalse(
            PortalProfileChangeRequest.objects.filter(
                account=self.parent_account,
                status=PortalProfileChangeRequest.STATUS_PENDING,
            ).exists()
        )
        self._login(self.admin_user, "admin")
        admin_list = self.client.get(reverse("portal_admin_page", kwargs={"page": "pending-reviews"}))
        self.assertContains(admin_list, "No parent profile changes waiting for review")

    def test_staff_can_approve_for_their_unit(self):
        self._submit_parent_change(home_address="12 Pine St")
        change = PortalProfileChangeRequest.objects.get(account=self.parent_account)
        self._login(self.staff_18, "staff", "school-18")
        response = self.client.post(
            reverse("portal_staff_profile_change"),
            {"change_id": change.pk, "action": "approve"},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        change.refresh_from_db()
        self.app.refresh_from_db()
        self.assertEqual(change.status, PortalProfileChangeRequest.STATUS_APPROVED)
        self.assertEqual(self.app.home_address, "12 Pine St")

    def test_staff_cannot_approve_another_unit_change(self):
        self._submit_parent_change(home_address="12 Pine St")
        change = PortalProfileChangeRequest.objects.get(account=self.parent_account)
        self._login(self.staff_26, "staff", "school-26")
        response = self.client.post(
            reverse("portal_staff_profile_change"),
            {"change_id": change.pk, "action": "approve"},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "not for this unit")
        change.refresh_from_db()
        self.assertEqual(change.status, PortalProfileChangeRequest.STATUS_PENDING)

    def test_live_parent_profile_can_open_edit_form(self):
        self._login(self.parent_user, "parent")
        page = self.client.get(reverse("portal_parent_page", kwargs={"page": "profile"}))
        self.assertContains(page, "Edit profile")
        self.assertContains(page, 'name="home_address"')
        self.assertContains(page, 'name="secondary_name"')
        self.assertContains(page, reverse("portal_parent_profile_save"))
        self.assertContains(page, "toggle-edit-profile")
        html = page.content.decode()
        self.assertNotIn("if (liveProfile) return;", html)
