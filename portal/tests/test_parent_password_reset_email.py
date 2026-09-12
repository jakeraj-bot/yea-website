from datetime import datetime, timedelta
from unittest.mock import patch
from urllib.parse import urlparse

from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from portal.member_admin import (
    send_parent_password_reset_link,
    staff_flash_from_password_reset,
)
from portal.models import (
    PortalFamily,
    PortalParentAccount,
    PortalParentEmail,
    PortalProfileChangeRequest,
    PortalStaffAccount,
    PortalUnit,
)
from portal.staff_auth import PORTAL_AUTH_SESSION_KEY


def _capture_send(**kwargs):
    _capture_send.calls.append(kwargs)
    return 1


_capture_send.calls = []


class ParentPasswordResetEmailTests(TestCase):
    def setUp(self):
        User = get_user_model()
        _capture_send.calls = []
        self.unit = PortalUnit.objects.create(slug="school-18", name="School 18", is_active=True)
        self.family = PortalFamily.objects.create(
            unit=self.unit,
            slug="orengo",
            name="Orengo",
            primary_contact="Alize Parent",
            status="Active",
        )
        self.parent_user = User.objects.create_user(
            username="parent:orengo",
            password="ParentPass123",
            email="alize@example.com",
            first_name="Alize",
            last_name="Parent",
        )
        PortalParentAccount.objects.create(user=self.parent_user, family=self.family)
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

    def _reset_url_from_message(self, message):
        for line in message.splitlines():
            line = line.strip()
            if "/login/password-reset/confirm/" in line:
                return line
        self.fail("Email did not include a create-password link.")

    def _complete_reset(self, reset_url, new_password):
        response = self.client.get(reset_url)
        self.assertEqual(response.status_code, 302)
        confirm_url = response["Location"]
        response = self.client.post(
            confirm_url,
            {"new_password1": new_password, "new_password2": new_password},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("portal_parent_password_reset_complete"))
        return confirm_url

    @patch("portal.member_admin.send_site_email", side_effect=_capture_send)
    def test_send_queues_email_with_token_link_and_keeps_hash(self, _send):
        old_hash = self.parent_user.password
        result = send_parent_password_reset_link(self.family, actor="yeaadmin")
        self.assertEqual(result["mode"], "email_link")
        self.assertEqual(result["email"], "alize@example.com")
        self.assertEqual(result["expires_hours"], 72)
        self.assertEqual(len(_capture_send.calls), 1)
        sent = _capture_send.calls[0]
        self.assertEqual(sent["recipient_list"], ["alize@example.com"])
        self.assertIn("Create a new parent portal password", sent["subject"])
        self.assertIn("/portal/login/password-reset/confirm/", sent["message"])
        self.assertIn("expires in 72 hours", sent["message"])
        self.assertIn("/portal/login/", sent["message"])
        self.assertNotIn("ParentPass123", sent["message"])
        self.assertNotIn(old_hash, sent["message"])
        self.assertNotIn("pbkdf2_", sent["message"])
        self.parent_user.refresh_from_db()
        self.assertEqual(self.parent_user.password, old_hash)
        self.assertTrue(self.parent_user.password.startswith("pbkdf2_"))
        self.assertTrue(self.parent_user.check_password("ParentPass123"))
        ledger = PortalParentEmail.objects.get(family=self.family)
        self.assertEqual(ledger.subject, sent["subject"])
        self.assertIn("create-password link sent to parent", ledger.body)
        self.assertNotIn("/login/password-reset/confirm/", ledger.body)
        token = result["reset_url"].rstrip("/").rsplit("/", 1)[-1]
        self.assertNotIn(token, ledger.body)
        audit = PortalProfileChangeRequest.objects.get(account__family=self.family)
        self.assertEqual(audit.changes, {"parent_password_reset": True, "reset_email_sent": True})
        flash = staff_flash_from_password_reset(result)
        self.assertEqual(flash["mode"], "email_link")
        self.assertFalse(flash.get("password"))
        self.assertNotIn("reset_url", flash)

    @patch("portal.member_admin.send_site_email", side_effect=_capture_send)
    def test_token_sets_new_hashed_password_and_allows_parent_login(self, _send):
        result = send_parent_password_reset_link(self.family, actor="yeaadmin")
        reset_url = self._reset_url_from_message(_capture_send.calls[0]["message"])
        parsed = urlparse(reset_url)
        self.assertTrue(parsed.path.startswith("/portal/login/password-reset/confirm/"))
        self._complete_reset(reset_url, "ParentNewPass456!")
        self.parent_user.refresh_from_db()
        self.assertTrue(self.parent_user.check_password("ParentNewPass456!"))
        self.assertFalse(self.parent_user.check_password("ParentPass123"))
        self.assertNotEqual(self.parent_user.password, "ParentNewPass456!")
        self.assertTrue(self.parent_user.password.startswith("pbkdf2_"))
        login_ok = self.client.post(
            reverse("portal_parent_login"),
            {"username": "orengo", "password": "ParentNewPass456!"},
        )
        self.assertEqual(login_ok.status_code, 302)
        self.assertTrue(authenticate(username="parent:orengo", password="ParentNewPass456!"))
        self.assertIsNone(authenticate(username="parent:orengo", password="ParentPass123"))
        self.assertEqual(result["username"], "orengo")

    @patch("portal.member_admin.send_site_email", side_effect=_capture_send)
    def test_used_token_shows_clear_error(self, _send):
        send_parent_password_reset_link(self.family)
        reset_url = self._reset_url_from_message(_capture_send.calls[0]["message"])
        self._complete_reset(reset_url, "ParentNewPass456!")
        reused = self.client.get(reset_url)
        self.assertEqual(reused.status_code, 200)
        self.assertContains(reused, "This link is not valid")
        self.assertContains(reused, "expired or was already used")
        self.assertNotContains(reused, "Create password")

    @patch("portal.member_admin.send_site_email", side_effect=_capture_send)
    def test_expired_token_shows_clear_error(self, _send):
        send_parent_password_reset_link(self.family)
        reset_url = self._reset_url_from_message(_capture_send.calls[0]["message"])
        future = datetime.now() + timedelta(hours=73)
        with patch.object(PasswordResetTokenGenerator, "_now", return_value=future):
            response = self.client.get(reset_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "This link is not valid")
        self.assertContains(response, "expired or was already used")
        self.parent_user.refresh_from_db()
        self.assertTrue(self.parent_user.check_password("ParentPass123"))

    def test_garbage_token_shows_clear_error(self):
        uid = urlsafe_base64_encode(force_bytes(self.parent_user.pk))
        url = reverse(
            "portal_parent_password_reset_confirm",
            kwargs={"uidb64": uid, "token": "invalid-token"},
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "This link is not valid")

    def test_requires_parent_email(self):
        self.parent_user.email = ""
        self.parent_user.save(update_fields=["email"])
        with self.assertRaises(ValueError) as ctx:
            send_parent_password_reset_link(self.family)
        self.assertIn("parent email", str(ctx.exception).lower())

    @override_settings(PORTAL_PREVIEW_MODE=False)
    @patch("portal.member_admin.send_site_email", side_effect=_capture_send)
    def test_admin_reset_sends_email_and_does_not_show_old_password(self, _send):
        self._login_admin()
        response = self.client.post(
            reverse("portal_admin_family_parent_password", kwargs={"family_slug": "orengo"}),
            {"action": "send_link"},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Create-password email sent")
        self.assertContains(response, "alize@example.com")
        self.assertContains(response, "You cannot see the old password")
        self.assertContains(response, "expires in 72 hours")
        self.assertNotContains(response, "ParentPass123")
        self.assertNotContains(response, self.parent_user.password)
        self.assertNotContains(response, "/login/password-reset/confirm/")
        self.assertEqual(len(_capture_send.calls), 1)
        self.assertIn("/login/password-reset/confirm/", _capture_send.calls[0]["message"])
        self.parent_user.refresh_from_db()
        self.assertTrue(self.parent_user.check_password("ParentPass123"))
        self.assertTrue(self.parent_user.password.startswith("pbkdf2_"))
