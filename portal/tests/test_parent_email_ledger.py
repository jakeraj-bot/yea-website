from pathlib import Path
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.mail import EmailMessage
from django.test import TestCase, override_settings
from django.urls import reverse

from core.email_service import send_site_email
from portal.models import PortalFamily, PortalParentEmail, PortalStaffAccount, PortalUnit
from portal.parent_email_log import collect_email_attachments
from portal.staff_auth import PORTAL_AUTH_SESSION_KEY
from portal.tests.test_family_units import _make_application

REPO_JS = Path(__file__).resolve().parents[2] / "static" / "js" / "portal-parent-email.js"


def _login(client, user, area):
    client.force_login(user)
    session = client.session
    session[PORTAL_AUTH_SESSION_KEY] = area
    session.save()


class AttachmentValidationTests(TestCase):
    def test_accepts_pdf_and_image(self):
        files = [
            SimpleUploadedFile("notice.pdf", b"%PDF-1.4 demo", content_type="application/pdf"),
            SimpleUploadedFile("photo.jpg", b"\xff\xd8\xff", content_type="image/jpeg"),
        ]
        payloads = collect_email_attachments(files)
        self.assertEqual([item[0] for item in payloads], ["notice.pdf", "photo.jpg"])
        self.assertEqual(payloads[0][1], b"%PDF-1.4 demo")

    def test_rejects_exe(self):
        bad = SimpleUploadedFile("virus.exe", b"MZ", content_type="application/octet-stream")
        with self.assertRaises(ValueError):
            collect_email_attachments([bad])


class SendSiteEmailAttachmentTests(TestCase):
    @patch("core.email_service.email_is_configured", return_value=True)
    def test_attaches_files_to_outgoing_message(self, _configured):
        with patch.object(EmailMessage, "send", return_value=1) as send, patch.object(
            EmailMessage, "attach"
        ) as attach:
            sent = send_site_email(
                "Forms",
                "Please sign.",
                ["parent@example.com"],
                attachments=[("notice.pdf", b"%PDF-1.4", "application/pdf")],
            )
        self.assertEqual(sent, 1)
        send.assert_called_once()
        attach.assert_called_once_with("notice.pdf", b"%PDF-1.4", "application/pdf")


class ParentEmailLedgerTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.unit = PortalUnit.objects.create(slug="school-18", name="School 18", is_active=True)
        self.other = PortalUnit.objects.create(slug="school-26", name="School 26", is_active=True)
        self.family = PortalFamily.objects.create(unit=self.unit, slug="jacobs", name="Jacobs")
        _make_application(self.family)
        self.family.enrollment_applications.update(primary_email="jakera@example.com")
        self.other_family = PortalFamily.objects.create(unit=self.other, slug="williams", name="Williams")
        _make_application(self.other_family, location="school_26")
        self.other_family.enrollment_applications.update(primary_email="other@example.com")

        self.staff = User.objects.create_user(
            username="staff:tester",
            password="StaffPass123!",
            email="staff@yeanj.org",
            first_name="Unit",
            last_name="Director",
        )
        PortalStaffAccount.objects.create(
            user=self.staff,
            unit=self.unit,
            display_name="Unit Director",
            role="Unit director",
            is_active=True,
        )
        self.admin = User.objects.create_user(
            username="staff:portaladmin",
            password="AdminPass123",
            email="admin@yeanj.org",
            first_name="Portal",
            last_name="Admin",
        )
        PortalStaffAccount.objects.create(
            user=self.admin,
            unit=self.unit,
            display_name="Portal Admin",
            role="Portal admin",
            all_units_access=True,
            is_active=True,
        )

    @override_settings(PORTAL_PREVIEW_MODE=False)
    @patch("portal.member_admin.send_site_email", return_value=1)
    def test_staff_send_attaches_files_and_writes_ledger(self, send_email):
        _login(self.client, self.staff, "staff")
        pdf = SimpleUploadedFile("pickup.pdf", b"%PDF-1.4 pickup", content_type="application/pdf")
        photo = SimpleUploadedFile("map.png", b"\x89PNG", content_type="image/png")
        response = self.client.post(
            reverse("portal_staff_family_email_send", kwargs={"family_slug": "jacobs"}),
            {
                "subject": "Pickup change",
                "body": "Please pick up at 5.",
                "next": "/portal/staff/family/jacobs/email/",
                "attachments": [pdf, photo],
            },
        )
        self.assertEqual(response.status_code, 302)
        send_email.assert_called_once()
        attachments = send_email.call_args.kwargs["attachments"]
        self.assertEqual([item[0] for item in attachments], ["pickup.pdf", "map.png"])
        row = PortalParentEmail.objects.get()
        self.assertEqual(row.subject, "Pickup change")
        self.assertEqual(row.body, "Please pick up at 5.")
        self.assertEqual(row.recipients, ["jakera@example.com"])
        self.assertEqual(row.sender_name, "Unit Director")
        self.assertEqual(row.unit, self.unit)
        self.assertEqual(row.family, self.family)
        self.assertEqual(row.attachment_names, ["pickup.pdf", "map.png"])
        self.assertEqual(row.files.count(), 2)

    @override_settings(PORTAL_PREVIEW_MODE=False)
    @patch("portal.member_admin.send_site_email", return_value=1)
    def test_ledger_lists_sent_mail_and_expand_box_has_body(self, send_email):
        _login(self.client, self.staff, "staff")
        self.client.post(
            reverse("portal_staff_family_email_send", kwargs={"family_slug": "jacobs"}),
            {"subject": "Field trip form", "body": "Please sign the permission slip."},
        )
        page = self.client.get(reverse("portal_staff_family_email", kwargs={"family_slug": "jacobs"}))
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, "Emails sent")
        self.assertContains(page, "Field trip form")
        self.assertContains(page, "jakera@example.com")
        self.assertContains(page, "Please sign the permission slip.")
        self.assertContains(page, 'data-email-ledger-item')
        self.assertContains(page, 'data-email-ledger-detail')
        self.assertContains(page, 'hidden')
        self.assertContains(page, "Open full email ledger")
        self.assertContains(page, "How to email a parent")
        js = REPO_JS.read_text()
        self.assertIn("data-email-ledger-toggle", js)
        self.assertIn("aria-expanded", js)

        full = self.client.get(reverse("portal_staff_page", kwargs={"page": "emails-sent"}))
        self.assertEqual(full.status_code, 200)
        self.assertContains(full, "Field trip form")
        self.assertContains(full, "Please sign the permission slip.")
        self.assertContains(full, "How to use the email ledger")

    @override_settings(PORTAL_PREVIEW_MODE=False)
    @patch("portal.member_admin.send_site_email", return_value=1)
    def test_staff_does_not_see_other_unit_mail_admin_does(self, send_email):
        _login(self.client, self.staff, "staff")
        self.client.post(
            reverse("portal_staff_family_email_send", kwargs={"family_slug": "jacobs"}),
            {"subject": "School 18 note", "body": "Unit 18 only."},
        )
        _login(self.client, self.admin, "admin")
        self.client.post(
            reverse("portal_admin_family_email_send", kwargs={"family_slug": "williams"}),
            {"subject": "School 26 note", "body": "Other unit message."},
        )

        _login(self.client, self.staff, "staff")
        staff_ledger = self.client.get(reverse("portal_staff_page", kwargs={"page": "emails-sent"}))
        self.assertContains(staff_ledger, "School 18 note")
        self.assertNotContains(staff_ledger, "School 26 note")
        self.assertNotContains(staff_ledger, "Other unit message.")

        blocked = self.client.get(reverse("portal_staff_family_email", kwargs={"family_slug": "williams"}))
        self.assertEqual(blocked.status_code, 404)

        _login(self.client, self.admin, "admin")
        admin_ledger = self.client.get(reverse("portal_admin_page", kwargs={"page": "emails-sent"}))
        self.assertContains(admin_ledger, "School 18 note")
        self.assertContains(admin_ledger, "School 26 note")
        self.assertContains(admin_ledger, "Other unit message.")

        parent_emails = self.client.get(reverse("portal_admin_page", kwargs={"page": "parent-emails"}))
        self.assertContains(parent_emails, 'name="attachments"')
        self.assertContains(parent_emails, "Emails sent")
        self.assertContains(parent_emails, "How to email parents")

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_unauthenticated_ledger_redirects(self):
        staff_page = self.client.get(reverse("portal_staff_page", kwargs={"page": "emails-sent"}))
        admin_page = self.client.get(reverse("portal_admin_page", kwargs={"page": "emails-sent"}))
        self.assertEqual(staff_page.status_code, 302)
        self.assertIn("/portal/staff/login/", staff_page.url)
        self.assertEqual(admin_page.status_code, 302)
        self.assertIn("/portal/admin/login/", admin_page.url)

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_compose_shows_upload_control(self):
        _login(self.client, self.staff, "staff")
        page = self.client.get(reverse("portal_staff_family_email", kwargs={"family_slug": "jacobs"}))
        self.assertContains(page, ">Upload<")
        self.assertContains(page, 'name="attachments"')
        self.assertContains(page, "enctype=\"multipart/form-data\"")
        self.assertContains(page, "portal-parent-email.js")
