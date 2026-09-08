from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from portal.admin_services import invite_admin_user, invite_staff_user
from portal.billing_services import post_charge
from portal.email_templates import (
    get_email_template,
    render_email,
    save_email_template,
    send_first_day_reminders,
)
from portal.models import (
    PortalEmailTemplate,
    PortalFamily,
    PortalParentAccount,
    PortalStaffAccount,
    PortalUnit,
)
from portal.staff_auth import PORTAL_AUTH_SESSION_KEY


class StaffWelcomeEmailTests(TestCase):
    def setUp(self):
        self.unit = PortalUnit.objects.create(slug="school-18", name="School 18", is_active=True)
        self.other = PortalUnit.objects.create(slug="school-26", name="School 26", is_active=True)

    @patch("portal.email_templates.send_site_email", return_value=1)
    def test_staff_invite_emails_username_password_and_staff_link(self, send_email):
        account, created, password, username = invite_staff_user(
            "Maya Staff",
            "maya@yeanj.org",
            "Unit staff",
            unit_slugs=["school-18", "school-26"],
            password="StaffPass123",
        )
        from portal.email_templates import send_staff_welcome_email

        sent = send_staff_welcome_email(account, username, password, "staff")
        self.assertTrue(created)
        self.assertEqual(sent, 1)
        self.assertEqual(set(account.accessible_units.values_list("slug", flat=True)), {"school-18", "school-26"})
        kwargs = send_email.call_args.kwargs
        self.assertEqual(kwargs["recipient_list"], ["maya@yeanj.org"])
        self.assertIn(username, kwargs["message"])
        self.assertIn("StaffPass123", kwargs["message"])
        self.assertIn("/portal/staff/login/", kwargs["message"])
        self.assertNotIn("/portal/admin/login/", kwargs["message"])
        self.assertNotIn("do not need a separate staff account", kwargs["message"])

    @patch("portal.email_templates.send_site_email", return_value=1)
    def test_admin_invite_emails_admin_portal_link(self, send_email):
        account, _created, password, username = invite_admin_user(
            "Jordan Admin",
            "jadmin",
            "jordan@yeanj.org",
            password="AdminPass123",
        )
        from portal.email_templates import send_staff_welcome_email

        send_staff_welcome_email(account, username, password, "admin")
        kwargs = send_email.call_args.kwargs
        self.assertEqual(kwargs["recipient_list"], ["jordan@yeanj.org"])
        self.assertIn("/portal/admin/login/", kwargs["message"])
        self.assertIn("jadmin", kwargs["message"])
        self.assertIn("AdminPass123", kwargs["message"])
        self.assertIn("do not need a separate staff account", kwargs["message"])
        self.assertIn("Staff portal", kwargs["message"])


class ChargeNoticeEmailTests(TestCase):
    def setUp(self):
        self.unit = PortalUnit.objects.create(slug="school-18", name="School 18", is_active=True)
        self.family = PortalFamily.objects.create(unit=self.unit, slug="rivera", name="Rivera")
        user = get_user_model().objects.create_user(
            username="parent:rivera",
            password="ParentPass123",
            email="parent@example.com",
        )
        PortalParentAccount.objects.create(user=user, family=self.family)

    @patch("portal.email_templates.send_site_email", return_value=1)
    def test_posting_charge_emails_parent_with_amount_and_description(self, send_email):
        entry = post_charge(
            self.family,
            "Ada Rivera",
            "membership",
            "20.00",
            date(2026, 9, 5),
            "Yearly membership fee",
        )
        self.assertEqual(entry.amount, Decimal("20.00"))
        send_email.assert_called_once()
        kwargs = send_email.call_args.kwargs
        self.assertEqual(kwargs["recipient_list"], ["parent@example.com"])
        self.assertIn("Yearly membership fee", kwargs["message"])
        self.assertIn("20.00", kwargs["message"])
        self.assertIn("Ada Rivera", kwargs["message"])
        self.assertIn("/portal/login/", kwargs["message"])

    @patch("portal.email_templates.send_site_email", return_value=1)
    def test_charge_template_can_be_edited(self, send_email):
        save_email_template(
            PortalEmailTemplate.KEY_CHARGE_NOTICE,
            "You were charged ${amount}",
            "Hi {family_name}, we posted {description} for ${amount}.",
            is_enabled=True,
        )
        post_charge(self.family, "Ada Rivera", "manual", "15.00", date(2026, 9, 5), "Late pickup")
        kwargs = send_email.call_args.kwargs
        self.assertEqual(kwargs["subject"], "You were charged $15.00")
        self.assertIn("Late pickup", kwargs["message"])
        self.assertIn("Rivera", kwargs["message"])

    @patch("portal.email_templates.send_site_email")
    def test_disabled_charge_template_does_not_send(self, send_email):
        save_email_template(
            PortalEmailTemplate.KEY_CHARGE_NOTICE,
            "Charge",
            "Body {amount}",
            is_enabled=False,
        )
        post_charge(self.family, "Ada Rivera", "manual", "10.00", date(2026, 9, 5), "Fee")
        send_email.assert_not_called()


class FirstDayReminderTests(TestCase):
    def setUp(self):
        self.unit = PortalUnit.objects.create(slug="school-18", name="School 18", is_active=True)
        self.family = PortalFamily.objects.create(unit=self.unit, slug="nguyen", name="Nguyen")
        user = get_user_model().objects.create_user(
            username="parent:nguyen",
            password="ParentPass123",
            email="nguyen@example.com",
        )
        PortalParentAccount.objects.create(user=user, family=self.family)

    def test_default_reminder_mentions_september_8_and_membership(self):
        subject, body = render_email(
            PortalEmailTemplate.KEY_FIRST_DAY_REMINDER,
            {"family_name": "Nguyen", "portal_url": "https://yeanj.org/portal/login/"},
        )
        self.assertIn("September 8", subject)
        self.assertIn("September 8", body)
        self.assertIn("$20", body)
        self.assertIn("first day", body.lower())

    @patch("portal.member_admin.send_site_email", return_value=1)
    def test_sends_to_all_parents(self, send_email):
        sent, total = send_first_day_reminders()
        self.assertEqual((sent, total), (1, 1))
        self.assertEqual(send_email.call_args.kwargs["recipient_list"], ["nguyen@example.com"])


class AdminAccountEmailViewTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.unit = PortalUnit.objects.create(slug="school-18", name="School 18", is_active=True)
        self.other = PortalUnit.objects.create(slug="school-26", name="School 26", is_active=True)
        self.admin = User.objects.create_user(username="staff:portaladmin", password="AdminPass123")
        PortalStaffAccount.objects.create(
            user=self.admin,
            unit=self.unit,
            display_name="Portal Admin",
            role="Portal admin",
            all_units_access=True,
            is_active=True,
        )
        self.client.force_login(self.admin)
        session = self.client.session
        session[PORTAL_AUTH_SESSION_KEY] = "admin"
        session.save()

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_staff_page_explains_process_and_unit_checkboxes(self):
        response = self.client.get(reverse("portal_admin_page", kwargs={"page": "staff"}) + "?add=1")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "How creating an account works")
        self.assertContains(response, "unit_slugs")
        self.assertContains(response, "School 18")
        self.assertContains(response, "School 26")
        self.assertContains(response, "Welcome email template")

    @override_settings(PORTAL_PREVIEW_MODE=False)
    @patch("portal.email_templates.send_site_email", return_value=1)
    def test_creating_staff_sends_welcome_email(self, send_email):
        response = self.client.post(
            reverse("portal_admin_staff_invite"),
            {
                "name": "Unit Lead",
                "email": "lead@yeanj.org",
                "role": "Unit director",
                "password": "StaffPass123",
                "unit_slugs": ["school-18", "school-26"],
            },
        )
        self.assertEqual(response.status_code, 302)
        send_email.assert_called_once()
        account = PortalStaffAccount.objects.get(user__email="lead@yeanj.org")
        self.assertEqual(set(account.accessible_units.values_list("slug", flat=True)), {"school-18", "school-26"})
        self.assertIn("lead@yeanj.org", send_email.call_args.kwargs["recipient_list"])

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_fees_page_has_charge_template_and_fits_content(self):
        response = self.client.get(reverse("portal_admin_page", kwargs={"page": "fees"}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Charge notice email")
        self.assertContains(response, "{amount}")
        self.assertContains(response, "portal-collapse.js")
        self.assertNotContains(response, "Server Error")

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_parent_emails_page_has_first_day_reminder(self):
        response = self.client.get(reverse("portal_admin_page", kwargs={"page": "parent-emails"}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "First-day payment reminder")
        self.assertContains(response, "September 8")
        self.assertContains(response, "$20")
        self.assertContains(response, "send_first_day_reminder")

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_can_save_charge_template(self):
        response = self.client.post(
            reverse("portal_admin_email_template_save"),
            {
                "template_key": PortalEmailTemplate.KEY_CHARGE_NOTICE,
                "subject": "New fee posted",
                "body": "You were charged ${amount} for {description}.",
                "is_enabled": "on",
                "next_page": "fees",
            },
        )
        self.assertEqual(response.status_code, 302)
        template = get_email_template(PortalEmailTemplate.KEY_CHARGE_NOTICE)
        self.assertEqual(template.subject, "New fee posted")

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_parent_billing_includes_collapse_script(self):
        family = PortalFamily.objects.create(unit=self.unit, slug="lee", name="Lee")
        parent = get_user_model().objects.create_user(
            username="parent:lee",
            password="ParentPass123",
            email="lee@example.com",
        )
        PortalParentAccount.objects.create(user=parent, family=family)
        self.client.logout()
        self.client.force_login(parent)
        session = self.client.session
        session[PORTAL_AUTH_SESSION_KEY] = "parent"
        session.save()
        response = self.client.get(reverse("portal_parent_page", kwargs={"page": "billing"}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "portal-collapse.js")
        self.assertContains(response, "portal.css?v=")
