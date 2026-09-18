from datetime import date
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse

from enrollment.application_review import approve_application, parse_member_start_date
from enrollment.notifications import notify_parent_application_received
from portal.email_templates import (
    application_email_context,
    get_email_template,
    parent_pay_now_url,
    save_email_template,
    submitted_template_key,
)
from portal.models import PortalEmailTemplate, PortalFamily, PortalStaffAccount, PortalUnit
from portal.staff_auth import PORTAL_AUTH_SESSION_KEY
from portal.tests.test_family_units import _make_application


class ApplicationEmailTemplateTests(TestCase):
    def setUp(self):
        self.unit = PortalUnit.objects.create(
            slug="school-18",
            name="School 18",
            program_type="both",
            is_active=True,
        )
        self.family = PortalFamily.objects.create(unit=self.unit, slug="rivera", name="Rivera")
        self.regular = _make_application(self.family, status="under_review")
        self.waitlist = _make_application(self.family, status="waitlist")
        self.waitlist.program = "before_care"
        self.waitlist.student_first_name = "Nia"
        self.waitlist.save(update_fields=["program", "student_first_name"])

    def test_submit_picks_regular_vs_waitlist_template_keys(self):
        self.assertEqual(submitted_template_key(self.regular), PortalEmailTemplate.KEY_APPLICATION_SUBMITTED)
        self.assertEqual(
            submitted_template_key(self.waitlist),
            PortalEmailTemplate.KEY_APPLICATION_SUBMITTED_WAITLIST,
        )

    @patch("portal.email_templates.send_site_email", return_value=1)
    def test_regular_submit_uses_regular_template(self, send_email):
        notify_parent_application_received(self.regular)
        kwargs = send_email.call_args.kwargs
        self.assertIn("Thank you for submitting your enrollment application", kwargs["message"])
        self.assertIn("Ada Rivera", kwargs["message"])
        self.assertIn("Pat", kwargs["message"])
        self.assertNotIn("before care waitlist", kwargs["message"])

    @patch("portal.email_templates.send_site_email", return_value=1)
    def test_waitlist_submit_uses_waitlist_template(self, send_email):
        notify_parent_application_received(self.waitlist)
        kwargs = send_email.call_args.kwargs
        self.assertIn("before care waitlist", kwargs["message"])
        self.assertIn("Nia Rivera", kwargs["message"])

    @patch("portal.email_templates.send_site_email", return_value=1)
    def test_edited_submit_template_is_used(self, send_email):
        save_email_template(
            PortalEmailTemplate.KEY_APPLICATION_SUBMITTED,
            "Got it for {child_name}",
            "Hi {parent_name}, we have {child_name} for {program} at {unit}.",
            is_enabled=True,
        )
        notify_parent_application_received(self.regular)
        kwargs = send_email.call_args.kwargs
        self.assertEqual(kwargs["subject"], "Got it for Ada Rivera")
        self.assertIn("Hi Pat, we have Ada Rivera", kwargs["message"])
        self.assertIn("After-school program", kwargs["message"])

    @override_settings(SITE_URL="https://yeanj.org")
    def test_regular_approve_email_includes_start_date_and_pay_link(self):
        mail.outbox.clear()
        approve_application(self.regular, start_date=date(2026, 10, 6))
        self.assertEqual(len(mail.outbox), 1)
        body = mail.outbox[0].body
        self.assertIn("October 6, 2026", body)
        self.assertIn("can start on", body)
        self.assertIn("https://yeanj.org/portal/parent/payment/", body)
        self.assertIn("Payment is due before the program start", body)
        self.assertIn("1. Open Parent login", body)
        self.assertIn("Great news", body)
        self.regular.refresh_from_db()
        self.assertEqual(self.regular.member_start_date, date(2026, 10, 6))

    @override_settings(SITE_URL="https://yeanj.org")
    def test_waitlist_approve_uses_waitlist_template_and_start_date(self):
        save_email_template(
            PortalEmailTemplate.KEY_APPLICATION_APPROVED_WAITLIST,
            "Spot for {child_name} on {start_date}",
            "Hi {parent_name}, {child_name} starts {start_date} at {unit}. Pay: {payment_url}\n{payment_steps}",
            is_enabled=True,
        )
        mail.outbox.clear()
        approve_application(self.waitlist, start_date=date(2026, 9, 22))
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].subject, "Spot for Nia Rivera on September 22, 2026")
        body = mail.outbox[0].body
        self.assertIn("starts September 22, 2026", body)
        self.assertIn("https://yeanj.org/portal/parent/payment/", body)
        self.assertIn("1. Open Parent login", body)

    def test_parse_member_start_date_required(self):
        with self.assertRaisesMessage(ValueError, "Enter the member start date"):
            parse_member_start_date("", required=True)
        self.assertEqual(parse_member_start_date("2026-09-15"), date(2026, 9, 15))

    def test_context_has_requested_placeholders(self):
        self.regular.member_start_date = date(2026, 11, 2)
        ctx = application_email_context(self.regular)
        for key in (
            "parent_name",
            "child_name",
            "program",
            "unit",
            "start_date",
            "payment_url",
            "payment_steps",
        ):
            self.assertIn(key, ctx)
        self.assertEqual(ctx["start_date"], "November 2, 2026")
        self.assertTrue(ctx["payment_url"].endswith("/portal/parent/payment/"))
        self.assertIn("Pay with Stripe", ctx["payment_steps"])


class ApplicationEmailAdminViewTests(TestCase):
    def setUp(self):
        self.unit = PortalUnit.objects.create(slug="school-18", name="School 18", is_active=True)
        self.family = PortalFamily.objects.create(unit=self.unit, slug="lee", name="Lee")
        User = get_user_model()
        self.admin = User.objects.create_user(username="staff:yeaadmin", password="AdminPass123")
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
    def test_can_save_application_approved_template(self):
        response = self.client.post(
            reverse("portal_admin_email_template_save"),
            {
                "template_key": PortalEmailTemplate.KEY_APPLICATION_APPROVED,
                "subject": "Approved — {child_name} starts {start_date}",
                "body": "Start {start_date}. Pay {payment_url}\n{payment_steps}",
                "is_enabled": "on",
                "next_page": "parent-emails",
            },
        )
        self.assertEqual(response.status_code, 302)
        template = get_email_template(PortalEmailTemplate.KEY_APPLICATION_APPROVED)
        self.assertEqual(template.subject, "Approved — {child_name} starts {start_date}")

    @override_settings(PORTAL_PREVIEW_MODE=False, SITE_URL="https://yeanj.org")
    def test_approve_without_start_date_is_rejected(self):
        app = _make_application(self.family, status="under_review")
        response = self.client.post(
            reverse("portal_admin_application_review", kwargs={"app_slug": str(app.reference)}),
            {"action": "approve", "membership_amount": "20.00"},
        )
        self.assertEqual(response.status_code, 302)
        app.refresh_from_db()
        self.assertEqual(app.status, "under_review")
        self.assertEqual(len(mail.outbox), 0)

    @override_settings(PORTAL_PREVIEW_MODE=False, SITE_URL="https://yeanj.org")
    def test_approve_posts_start_date_into_email(self):
        app = _make_application(self.family, status="under_review")
        mail.outbox.clear()
        response = self.client.post(
            reverse("portal_admin_application_review", kwargs={"app_slug": str(app.reference)}),
            {
                "action": "approve",
                "membership_amount": "0",
                "member_start_date": "2026-09-29",
            },
        )
        self.assertEqual(response.status_code, 302)
        app.refresh_from_db()
        self.assertEqual(app.status, "approved")
        self.assertEqual(app.member_start_date, date(2026, 9, 29))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("September 29, 2026", mail.outbox[0].body)
        self.assertIn("https://yeanj.org/portal/parent/payment/", mail.outbox[0].body)
        self.assertIn("Payment is due before the program start", mail.outbox[0].body)

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_waitlist_list_approve_has_start_date_field(self):
        app = _make_application(self.family, status="waitlist")
        app.program = "before_care"
        app.save(update_fields=["program"])
        page = self.client.get(reverse("portal_admin_page", kwargs={"page": "waitlist"}))
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, 'name="member_start_date"')
        self.assertContains(page, "Start date")
