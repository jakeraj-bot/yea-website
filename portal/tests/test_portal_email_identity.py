from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse

from core.email_service import (
    formatted_portal_from,
    portal_bcc_email,
    portal_sending_email,
    send_site_email,
    staff_from_display_name,
    staff_reply_to_email,
)
from portal.email_templates import notify_charge_posted
from portal.forms import PortalPasswordResetForm
from portal.member_admin import (
    parse_compose_cc,
    send_family_parent_email,
    send_parent_password_reset_link,
)
from portal.models import (
    PortalFamily,
    PortalLedgerEntry,
    PortalOrgSetting,
    PortalParentAccount,
    PortalStaffAccount,
    PortalUnit,
)
from portal.staff_auth import PORTAL_AUTH_SESSION_KEY
from portal.tests.test_family_units import _make_application


def _login(client, user, area):
    client.force_login(user)
    session = client.session
    session[PORTAL_AUTH_SESSION_KEY] = area
    session.save()


class PortalEmailIdentityHelperTests(TestCase):
    def setUp(self):
        PortalOrgSetting.load()

    def test_defaults_to_server_from_address(self):
        with self.settings(DEFAULT_FROM_EMAIL="jakeraj@yeanj.org"):
            self.assertEqual(portal_sending_email(), "jakeraj@yeanj.org")
            self.assertEqual(portal_bcc_email(), "jakeraj@yeanj.org")
            self.assertIn("jakeraj@yeanj.org", formatted_portal_from())
            self.assertIn("Youth Education Academy", formatted_portal_from())

    def test_settings_override_from_and_bcc(self):
        setting = PortalOrgSetting.load()
        setting.portal_sending_email = "portal@yeanj.org"
        setting.portal_bcc_email = "copies@yeanj.org"
        setting.save()
        self.assertEqual(portal_sending_email(), "portal@yeanj.org")
        self.assertEqual(portal_bcc_email(), "copies@yeanj.org")
        setting.portal_bcc_email = ""
        setting.save()
        self.assertEqual(portal_bcc_email(), "portal@yeanj.org")

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        DEFAULT_FROM_EMAIL="jakeraj@yeanj.org",
    )
    @patch("core.email_service.email_is_configured", return_value=True)
    def test_system_mail_uses_settings_from_and_bcc(self, _configured):
        setting = PortalOrgSetting.load()
        setting.portal_sending_email = "portal@yeanj.org"
        setting.portal_bcc_email = "copies@yeanj.org"
        setting.save()
        sent_count = send_site_email("Invoice", "Please pay.", ["parent@example.com"])
        self.assertEqual(sent_count, 1)
        sent = mail.outbox[0]
        self.assertEqual(sent.to, ["parent@example.com"])
        self.assertIn("portal@yeanj.org", sent.from_email)
        self.assertIn("Youth Education Academy", sent.from_email)
        self.assertEqual(sent.bcc, ["copies@yeanj.org"])
        self.assertFalse(sent.reply_to)

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        DEFAULT_FROM_EMAIL="jakeraj@yeanj.org",
    )
    @patch("core.email_service.email_is_configured", return_value=True)
    def test_staff_send_sets_reply_to_and_via_from_name(self, _configured):
        unit = PortalUnit.objects.create(slug="school-18", name="School 18", is_active=True)
        user = get_user_model().objects.create_user(
            username="staff:assistant",
            password="StaffPass123!",
            email="assistant@yeanj.org",
        )
        PortalStaffAccount.objects.create(
            user=user,
            unit=unit,
            display_name="Pat Assistant",
            role="Unit staff",
            is_active=True,
        )
        self.assertEqual(staff_reply_to_email(user), "assistant@yeanj.org")
        self.assertEqual(staff_from_display_name(user), "Pat Assistant via Youth Education Academy")
        send_site_email(
            "Pickup change",
            "Please pick up at 5.",
            ["parent@example.com"],
            sender=user,
        )
        sent = mail.outbox[0]
        self.assertEqual(sent.reply_to, ["assistant@yeanj.org"])
        self.assertIn("Pat Assistant via Youth Education Academy", sent.from_email)
        self.assertIn("jakeraj@yeanj.org", sent.from_email)
        self.assertEqual(sent.bcc, ["jakeraj@yeanj.org"])


class StaffComposeCcTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.unit = PortalUnit.objects.create(slug="school-18", name="School 18", is_active=True)
        self.family = PortalFamily.objects.create(unit=self.unit, slug="jacobs", name="Jacobs")
        _make_application(self.family)
        self.family.enrollment_applications.update(primary_email="parent@example.com")
        self.staff = User.objects.create_user(
            username="staff:tester",
            password="StaffPass123!",
            email="staff@yeanj.org",
        )
        PortalStaffAccount.objects.create(
            user=self.staff,
            unit=self.unit,
            display_name="Tester",
            role="Unit director",
            is_active=True,
        )
        self.assistant = User.objects.create_user(
            username="staff:assistant",
            password="StaffPass123!",
            email="assistant@yeanj.org",
        )
        PortalStaffAccount.objects.create(
            user=self.assistant,
            unit=self.unit,
            display_name="Pat Assistant",
            role="Unit staff",
            is_active=True,
        )
        self.admin = User.objects.create_user(
            username="staff:portaladmin",
            password="AdminPass123",
            email="admin@yeanj.org",
        )
        PortalStaffAccount.objects.create(
            user=self.admin,
            unit=self.unit,
            display_name="Portal Admin",
            role="Portal admin",
            all_units_access=True,
            is_active=True,
        )
        _login(self.client, self.staff, "staff")

    def test_parse_compose_cc_includes_checked_staff_and_typed_address(self):
        factory = RequestFactory()
        request = factory.post(
            "/",
            {
                "cc_staff": ["assistant@yeanj.org", "admin@yeanj.org"],
                "cc_extra": "partner@yeanj.org",
            },
        )
        self.assertEqual(
            parse_compose_cc(request.POST),
            ["assistant@yeanj.org", "admin@yeanj.org", "partner@yeanj.org"],
        )

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_email_pages_show_cc_staff_and_reply_note(self):
        email_page = self.client.get(reverse("portal_staff_family_email", kwargs={"family_slug": "jacobs"}))
        self.assertEqual(email_page.status_code, 200)
        self.assertContains(email_page, "CC staff")
        self.assertContains(email_page, "assistant@yeanj.org")
        self.assertContains(email_page, "Pat Assistant")
        self.assertContains(email_page, 'name="cc_extra"')
        self.assertContains(email_page, "Parents reply to")
        self.assertContains(email_page, "name@email.com")

    @override_settings(PORTAL_PREVIEW_MODE=False)
    @patch("portal.member_admin.send_site_email", return_value=1)
    def test_staff_send_passes_reply_to_and_cc(self, send_email):
        response = self.client.post(
            reverse("portal_staff_family_email_send", kwargs={"family_slug": "jacobs"}),
            {
                "subject": "Pickup change",
                "body": "Please pick up at 5.",
                "cc_staff": ["assistant@yeanj.org"],
                "cc_extra": "partner@yeanj.org",
                "next": "/portal/staff/family/jacobs/email/",
            },
        )
        self.assertEqual(response.status_code, 302)
        send_email.assert_called_once()
        kwargs = send_email.call_args.kwargs
        self.assertEqual(kwargs["recipient_list"], ["parent@example.com"])
        self.assertEqual(kwargs["reply_to"], ["staff@yeanj.org"])
        self.assertEqual(kwargs["cc"], ["assistant@yeanj.org", "partner@yeanj.org"])
        self.assertEqual(kwargs["sender"], self.staff)

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_admin_email_parents_page_has_cc_and_identity_note(self):
        _login(self.client, self.admin, "admin")
        page = self.client.get(reverse("portal_admin_page", kwargs={"page": "parent-emails"}))
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, "CC staff")
        self.assertContains(page, "Pat Assistant")
        self.assertContains(page, "Parents reply to")
        self.assertContains(page, "email-settings")

    @override_settings(PORTAL_PREVIEW_MODE=False)
    @patch("portal.member_admin.send_site_email", return_value=1)
    def test_bulk_send_includes_staff_cc(self, send_email):
        _login(self.client, self.admin, "admin")
        response = self.client.post(
            reverse("portal_admin_member_ops"),
            {
                "action": "send_parent_emails",
                "subject": "Snow day",
                "body": "Program is closed.",
                "emails": ["parent@example.com"],
                "cc_staff": ["assistant@yeanj.org"],
            },
        )
        self.assertEqual(response.status_code, 302)
        kwargs = send_email.call_args.kwargs
        self.assertEqual(kwargs["cc"], ["assistant@yeanj.org"])
        self.assertEqual(kwargs["reply_to"], ["admin@yeanj.org"])
        self.assertEqual(kwargs["sender"], self.admin)


class EmailSettingsViewTests(TestCase):
    def setUp(self):
        User = get_user_model()
        unit = PortalUnit.objects.create(slug="school-18", name="School 18", is_active=True)
        self.admin = User.objects.create_user(
            username="staff:portaladmin",
            password="AdminPass123",
            email="admin@yeanj.org",
        )
        PortalStaffAccount.objects.create(
            user=self.admin,
            unit=unit,
            display_name="Portal Admin",
            role="Portal admin",
            all_units_access=True,
            is_active=True,
        )
        _login(self.client, self.admin, "admin")

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_settings_page_shows_labels_and_saves(self):
        page = self.client.get(reverse("portal_admin_page", kwargs={"page": "email-settings"}))
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, "Portal sending email")
        self.assertContains(page, "Always BCC this address on mail to parents")
        self.assertContains(page, "How outgoing mail works")
        self.assertContains(page, "Settings")
        response = self.client.post(
            reverse("portal_admin_email_settings_save"),
            {
                "portal_sending_email": "portal@yeanj.org",
                "portal_bcc_email": "copies@yeanj.org",
            },
        )
        self.assertEqual(response.status_code, 302)
        setting = PortalOrgSetting.load()
        self.assertEqual(setting.portal_sending_email, "portal@yeanj.org")
        self.assertEqual(setting.portal_bcc_email, "copies@yeanj.org")
        saved = self.client.get(reverse("portal_admin_page", kwargs={"page": "email-settings"}))
        self.assertContains(saved, "portal@yeanj.org")
        self.assertContains(saved, "copies@yeanj.org")


class SystemAndResetEmailIdentityTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.unit = PortalUnit.objects.create(slug="school-18", name="School 18", is_active=True)
        self.family = PortalFamily.objects.create(unit=self.unit, slug="orengo", name="Orengo")
        self.parent_user = User.objects.create_user(
            username="parent:orengo",
            password="ParentPass123",
            email="alize@example.com",
        )
        PortalParentAccount.objects.create(user=self.parent_user, family=self.family)
        setting = PortalOrgSetting.load()
        setting.portal_sending_email = "portal@yeanj.org"
        setting.portal_bcc_email = "copies@yeanj.org"
        setting.save()

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        DEFAULT_FROM_EMAIL="jakeraj@yeanj.org",
    )
    @patch("core.email_service.email_is_configured", return_value=True)
    def test_charge_notice_uses_settings_from_and_bcc(self, _configured):
        entry = PortalLedgerEntry.objects.create(
            family=self.family,
            child_name="Alize",
            date=date(2026, 9, 8),
            entry_type="charge",
            description="Weekly tuition",
            amount=Decimal("110.00"),
        )
        notify_charge_posted(self.family, entry)
        self.assertEqual(len(mail.outbox), 1)
        sent = mail.outbox[0]
        self.assertEqual(sent.to, ["alize@example.com"])
        self.assertIn("portal@yeanj.org", sent.from_email)
        self.assertEqual(sent.bcc, ["copies@yeanj.org"])
        self.assertFalse(sent.reply_to)

    @patch("portal.member_admin.send_site_email", return_value=1)
    def test_parent_reset_email_still_sends(self, send_email):
        result = send_parent_password_reset_link(self.family)
        self.assertEqual(result["email"], "alize@example.com")
        send_email.assert_called_once()
        kwargs = send_email.call_args.kwargs
        self.assertEqual(kwargs["recipient_list"], ["alize@example.com"])
        self.assertIn("/login/password-reset/confirm/", kwargs["message"])

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        SITE_URL="https://yeanj.org",
    )
    def test_forgot_password_form_uses_portal_from_and_bcc(self):
        form = PortalPasswordResetForm(data={"email": "alize@example.com"}, portal_type="parent")
        self.assertTrue(form.is_valid())
        form.save(
            domain_override="yeanj.org",
            use_https=True,
            subject_template_name="portal/password_reset/email_subject.txt",
            email_template_name="portal/password_reset/email_body.txt",
            extra_email_context={
                "portal_label": "parent portal",
                "reset_confirm_url_name": "portal_parent_password_reset_confirm",
                "login_url_name": "portal_parent_login",
            },
        )
        self.assertEqual(len(mail.outbox), 1)
        sent = mail.outbox[0]
        self.assertEqual(sent.to, ["alize@example.com"])
        self.assertIn("portal@yeanj.org", sent.from_email)
        self.assertEqual(sent.bcc, ["copies@yeanj.org"])
        self.assertIn("password", sent.subject.lower())


class FamilySendUsesStaffIdentityTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.unit = PortalUnit.objects.create(slug="school-18", name="School 18", is_active=True)
        self.family = PortalFamily.objects.create(unit=self.unit, slug="nguyen", name="Nguyen")
        _make_application(self.family)
        self.family.enrollment_applications.update(primary_email="parent@example.com")
        self.staff = User.objects.create_user(
            username="staff:tester",
            password="StaffPass123!",
            email="staff@yeanj.org",
        )
        PortalStaffAccount.objects.create(
            user=self.staff,
            unit=self.unit,
            display_name="Tester",
            role="Unit director",
            is_active=True,
        )

    @patch("portal.member_admin.send_site_email", return_value=1)
    def test_send_family_parent_email_passes_staff_sender(self, send_email):
        send_family_parent_email(
            self.family,
            "Hello",
            "Body",
            sender=self.staff,
            cc=["assistant@yeanj.org"],
        )
        kwargs = send_email.call_args.kwargs
        self.assertEqual(kwargs["sender"], self.staff)
        self.assertEqual(kwargs["cc"], ["assistant@yeanj.org"])
        self.assertTrue(kwargs["copy_to_portal"])
