from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse

from portal.models import PortalFamily, PortalParentAccount, PortalStaffAccount, PortalUnit
from portal.staff_auth import PORTAL_AUTH_SESSION_KEY
from portal.views import PARENT_CONTACT_EMAIL


class ParentContactUsTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.unit = PortalUnit.objects.create(slug="school-18", name="School 18", is_active=True)
        self.family = PortalFamily.objects.create(
            unit=self.unit,
            slug="rivera",
            name="Rivera",
            primary_contact="Ada Rivera",
            status="Active",
        )
        self.parent_user = User.objects.create_user(
            username="parent:rivera",
            password="ParentPass123",
            email="ada.rivera@example.com",
            first_name="Ada",
            last_name="Rivera",
        )
        PortalParentAccount.objects.create(user=self.parent_user, family=self.family)
        self.staff_user = User.objects.create_user(username="staff:unitstaff", password="StaffPass123")
        PortalStaffAccount.objects.create(
            user=self.staff_user,
            unit=self.unit,
            display_name="Unit Staff",
            role="Unit staff",
            is_active=True,
        )
        self.admin_user = User.objects.create_user(username="staff:yeaadmin", password="AdminPass123")
        PortalStaffAccount.objects.create(
            user=self.admin_user,
            unit=self.unit,
            display_name="YEA Admin",
            role="Portal admin",
            all_units_access=True,
            is_active=True,
        )

    def _login(self, user, area):
        self.client.force_login(user)
        session = self.client.session
        session[PORTAL_AUTH_SESSION_KEY] = area
        session.save()

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_parent_sees_contact_us_in_nav_and_page(self):
        self._login(self.parent_user, "parent")
        dashboard = self.client.get(reverse("portal_parent_page", kwargs={"page": "dashboard"}))
        self.assertEqual(dashboard.status_code, 200)
        self.assertContains(dashboard, "Contact us")
        self.assertContains(dashboard, reverse("portal_parent_page", kwargs={"page": "contact-us"}))
        page = self.client.get(reverse("portal_parent_page", kwargs={"page": "contact-us"}))
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, "Billing and portal questions — Jakera Jacobs")
        self.assertContains(page, "Jakeraj@yeanj.org")
        self.assertContains(page, "862-866-4744")
        self.assertContains(page, "Text: 9:00am–7:00pm")
        self.assertContains(page, "Phone: 4:00pm–7:00pm")
        self.assertContains(page, "Programming questions — Janice Gomez")
        self.assertContains(page, "janiceg@yeanj.org")
        self.assertContains(page, "609-357-8608")
        self.assertContains(page, "This form emails")
        self.assertContains(page, reverse("portal_parent_contact"))
        self.assertContains(page, "Ada Rivera")
        self.assertContains(page, "ada.rivera@example.com")

    @override_settings(PORTAL_PREVIEW_MODE=False)
    @patch("core.email_service.send_site_email", return_value=1)
    def test_parent_form_emails_jakera(self, mock_send):
        self._login(self.parent_user, "parent")
        response = self.client.post(
            reverse("portal_parent_contact"),
            {
                "name": "Ada Rivera",
                "email": "ada.rivera@example.com",
                "topic": "billing",
                "message": "I have a question about my balance.",
                "company": "",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn("sent=1", response["Location"])
        mock_send.assert_called_once()
        kwargs = mock_send.call_args.kwargs
        self.assertEqual(kwargs["recipient_list"], [PARENT_CONTACT_EMAIL])
        self.assertEqual(kwargs["reply_to"], ["ada.rivera@example.com"])
        self.assertIn("Billing and portal questions", kwargs["subject"])
        self.assertIn("Rivera", kwargs["message"])
        self.assertIn("I have a question about my balance.", kwargs["message"])
        confirm = self.client.get(response["Location"])
        self.assertContains(confirm, "Your message was sent to Jakera Jacobs")

    @override_settings(
        PORTAL_PREVIEW_MODE=False,
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    )
    @patch("core.email_service.email_is_configured", return_value=True)
    def test_parent_form_uses_email_backend(self, _configured):
        self._login(self.parent_user, "parent")
        response = self.client.post(
            reverse("portal_parent_contact"),
            {
                "name": "Ada Rivera",
                "email": "ada.rivera@example.com",
                "topic": "programming",
                "message": "What time does after-school start?",
                "company": "",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(len(mail.outbox), 1)
        sent = mail.outbox[0]
        self.assertEqual(sent.to, [PARENT_CONTACT_EMAIL])
        self.assertEqual(sent.reply_to, ["ada.rivera@example.com"])
        self.assertIn("Programming questions", sent.subject)
        self.assertIn("What time does after-school start?", sent.body)

    @override_settings(PORTAL_PREVIEW_MODE=False)
    @patch("core.email_service.send_site_email", return_value=1)
    def test_honeypot_is_silently_ignored(self, mock_send):
        self._login(self.parent_user, "parent")
        response = self.client.post(
            reverse("portal_parent_contact"),
            {
                "name": "Ada Rivera",
                "email": "ada.rivera@example.com",
                "topic": "general",
                "message": "Spam attempt",
                "company": "Acme SEO",
            },
        )
        self.assertEqual(response.status_code, 302)
        mock_send.assert_not_called()

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_staff_and_admin_menus_do_not_show_contact_us(self):
        self._login(self.staff_user, "staff")
        staff = self.client.get(reverse("portal_staff_page", kwargs={"page": "dashboard"}))
        self.assertEqual(staff.status_code, 200)
        self.assertNotContains(staff, "Contact us")
        self.assertNotContains(staff, reverse("portal_parent_page", kwargs={"page": "contact-us"}))

        self._login(self.admin_user, "admin")
        admin = self.client.get(reverse("portal_admin_page", kwargs={"page": "dashboard"}))
        self.assertEqual(admin.status_code, 200)
        self.assertNotContains(admin, "Contact us")
        self.assertNotContains(admin, reverse("portal_parent_page", kwargs={"page": "contact-us"}))
