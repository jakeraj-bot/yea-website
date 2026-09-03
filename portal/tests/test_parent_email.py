from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from portal.member_admin import parent_email_for_family, send_family_parent_email
from portal.models import PortalFamily, PortalParentAccount, PortalStaffAccount, PortalUnit
from portal.staff_auth import PORTAL_AUTH_SESSION_KEY
from portal.tests.test_family_units import _make_application


class ParentEmailLookupTests(TestCase):
    def setUp(self):
        self.unit = PortalUnit.objects.create(slug="school-18", name="School 18", is_active=True)
        self.family = PortalFamily.objects.create(unit=self.unit, slug="rivera", name="Rivera")

    def test_uses_parent_account_email_first(self):
        user = get_user_model().objects.create_user(
            username="parent:rivera",
            password="Pass12345",
            email="login@example.com",
        )
        PortalParentAccount.objects.create(user=user, family=self.family)
        _make_application(self.family)
        self.family.enrollment_applications.update(primary_email="application@example.com")
        self.assertEqual(parent_email_for_family(self.family), "login@example.com")

    def test_falls_back_to_application_email(self):
        _make_application(self.family)
        self.family.enrollment_applications.update(primary_email="application@example.com")
        self.assertEqual(parent_email_for_family(self.family), "application@example.com")


class SendFamilyParentEmailTests(TestCase):
    def setUp(self):
        self.unit = PortalUnit.objects.create(slug="school-18", name="School 18", is_active=True)
        self.family = PortalFamily.objects.create(unit=self.unit, slug="nguyen", name="Nguyen")
        _make_application(self.family)
        self.family.enrollment_applications.update(primary_email="parent@example.com")

    @patch("portal.member_admin.send_site_email", return_value=1)
    def test_sends_to_resolved_parent_email(self, send_email):
        sent, total = send_family_parent_email(self.family, "Balance reminder", "Please pay this week.")
        self.assertEqual((sent, total), (1, 1))
        send_email.assert_called_once()
        kwargs = send_email.call_args.kwargs
        self.assertEqual(kwargs["recipient_list"], ["parent@example.com"])
        self.assertEqual(kwargs["subject"], "Balance reminder")

    def test_requires_parent_email(self):
        family = PortalFamily.objects.create(unit=self.unit, slug="empty", name="Empty")
        with self.assertRaises(ValueError):
            send_family_parent_email(family, "Hello", "Body")


class FamilyEmailViewTests(TestCase):
    def setUp(self):
        self.unit = PortalUnit.objects.create(slug="school-18", name="School 18", is_active=True)
        self.other = PortalUnit.objects.create(slug="school-26", name="School 26", is_active=True)
        self.family = PortalFamily.objects.create(unit=self.unit, slug="jacobs", name="Jacobs")
        _make_application(self.family)
        self.family.enrollment_applications.update(primary_email="jakera@example.com")
        user = get_user_model().objects.create_user(
            username="staff:tester",
            password="StaffPass123!",
            email="staff@yeanj.org",
        )
        PortalStaffAccount.objects.create(
            user=user,
            unit=self.unit,
            display_name="Tester",
            role="Unit director",
            is_active=True,
        )
        self.client.force_login(user)
        session = self.client.session
        session[PORTAL_AUTH_SESSION_KEY] = "staff"
        session.save()

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_profile_and_email_pages_show_compose_form(self):
        profile = self.client.get(reverse("portal_staff_family_detail", kwargs={"family_slug": "jacobs"}))
        email_page = self.client.get(reverse("portal_staff_family_email", kwargs={"family_slug": "jacobs"}))
        self.assertEqual(profile.status_code, 200)
        self.assertEqual(email_page.status_code, 200)
        self.assertContains(profile, "Email parent")
        self.assertContains(profile, "jakera@example.com")
        self.assertContains(email_page, 'name="subject"')
        self.assertContains(email_page, "jakera@example.com")

    @override_settings(PORTAL_PREVIEW_MODE=False)
    @patch("portal.member_admin.send_site_email", return_value=1)
    def test_staff_can_send_email_from_profile(self, send_email):
        response = self.client.post(
            reverse("portal_staff_family_email_send", kwargs={"family_slug": "jacobs"}),
            {
                "subject": "Pickup change",
                "body": "Please pick up at 5.",
                "next": "/portal/staff/family/jacobs/",
            },
        )
        self.assertEqual(response.status_code, 302)
        send_email.assert_called_once()
        self.assertEqual(send_email.call_args.kwargs["recipient_list"], ["jakera@example.com"])
        self.assertEqual(send_email.call_args.kwargs["reply_to"], ["staff@yeanj.org"])

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_staff_cannot_email_family_in_another_unit(self):
        other_family = PortalFamily.objects.create(unit=self.other, slug="williams", name="Williams")
        _make_application(other_family, location="school_26")
        other_family.enrollment_applications.update(primary_email="other@example.com")
        response = self.client.post(
            reverse("portal_staff_family_email_send", kwargs={"family_slug": "williams"}),
            {"subject": "Hello", "body": "No"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn("/portal/staff/families/", response.url)
