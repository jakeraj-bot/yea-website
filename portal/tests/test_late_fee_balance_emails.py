from datetime import date
from decimal import Decimal
from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse

from portal.billing_services import delete_ledger_entry, post_charge, post_payment, update_ledger_amount
from portal.email_templates import (
    get_email_template,
    late_notice_preview_rows,
    notify_charge_posted,
    send_late_payment_notices,
    send_updated_balance_email,
)
from portal.models import (
    PortalChild,
    PortalEmailTemplate,
    PortalFamily,
    PortalLedgerEntry,
    PortalParentAccount,
    PortalStaffAccount,
    PortalUnit,
)
from portal.owed_weeks import owed_weeks_report, post_late_fees, week_label_from_charge
from portal.staff_auth import PORTAL_AUTH_SESSION_KEY


class ChargeInvoiceEmailTests(TestCase):
    def setUp(self):
        self.unit = PortalUnit.objects.create(slug="school-18", name="School 18", is_active=True)
        self.family = PortalFamily.objects.create(
            unit=self.unit,
            slug="rivera",
            name="Rivera",
            program_label="After-School 2026–27",
        )
        self.child = PortalChild.objects.create(family=self.family, name="Ada Rivera", is_active=True)
        user = get_user_model().objects.create_user(
            username="parent:rivera",
            password="ParentPass123",
            email="parent@example.com",
        )
        PortalParentAccount.objects.create(user=user, family=self.family)

    @patch("portal.email_templates.send_site_email", return_value=1)
    def test_invoice_includes_balance_description_child_and_week(self, send_email):
        post_charge(
            self.family,
            "Ada Rivera",
            "tuition",
            "40.00",
            date(2026, 9, 8),
            "Weekly tuition — Ada Rivera (9/8/26–9/12/26)",
        )
        send_email.assert_called_once()
        message = send_email.call_args.kwargs["message"]
        self.assertIn("Weekly tuition — Ada Rivera (9/8/26–9/12/26)", message)
        self.assertIn("Ada Rivera", message)
        self.assertIn("9/8/26–9/12/26", message)
        self.assertIn("40.00", message)
        self.assertIn("Current balance for Ada Rivera: $40.00", message)
        self.assertIn("Family balance (what the household owes): $40.00", message)

    @patch("portal.email_templates.send_site_email", return_value=1)
    def test_invoice_family_balance_counts_unallocated_payment(self, send_email):
        post_charge(
            self.family,
            "Ada Rivera",
            "tuition",
            "40.00",
            date(2026, 9, 8),
            "Weekly tuition",
            notify=False,
        )
        post_payment(self.family, "", "10.00", date(2026, 9, 9), "Cash")
        notify_charge_posted(
            self.family,
            PortalLedgerEntry.objects.filter(family=self.family, entry_type="charge").first(),
        )
        message = send_email.call_args.kwargs["message"]
        self.assertIn("Family balance (what the household owes): $30.00", message)
        # Unlabeled household payments are shared onto children (same as All families).
        self.assertIn("Current balance for Ada Rivera: $30.00", message)


class UpdatedBalanceEmailTests(TestCase):
    def setUp(self):
        self.unit = PortalUnit.objects.create(slug="school-18", name="School 18", is_active=True)
        self.family = PortalFamily.objects.create(unit=self.unit, slug="lee", name="Lee")
        self.child = PortalChild.objects.create(family=self.family, name="Maya Lee", is_active=True)
        user = get_user_model().objects.create_user(
            username="parent:lee",
            password="ParentPass123",
            email="lee@example.com",
        )
        PortalParentAccount.objects.create(user=user, family=self.family)
        self.admin = get_user_model().objects.create_user(username="staff:portaladmin", password="AdminPass123")
        PortalStaffAccount.objects.create(
            user=self.admin,
            unit=self.unit,
            display_name="Portal Admin",
            role="Portal admin",
            all_units_access=True,
            is_active=True,
        )

    @patch("portal.email_templates.send_site_email", return_value=1)
    def test_reducing_charge_sends_updated_balance_email(self, send_email):
        entry = post_charge(
            self.family,
            "Maya Lee",
            "tuition",
            "50.00",
            date(2026, 9, 8),
            "Weekly tuition — Maya Lee (week of Sep 8)",
            notify=False,
        )
        send_email.reset_mock()
        update_ledger_amount(self.family, entry.pk, "20.00", notify=True)
        send_email.assert_called_once()
        kwargs = send_email.call_args.kwargs
        self.assertEqual(kwargs["subject"], "Your YEA balance was updated")
        self.assertIn("20.00", kwargs["message"])
        self.assertIn("50.00", kwargs["message"])
        self.assertIn("Maya Lee", kwargs["message"])
        self.assertIn("Family balance (what the household owes): $20.00", kwargs["message"])

    @patch("portal.email_templates.send_site_email", return_value=1)
    def test_voiding_charge_sends_updated_balance_email(self, send_email):
        entry = post_charge(
            self.family,
            "Maya Lee",
            "tuition",
            "50.00",
            date(2026, 9, 8),
            "Weekly tuition",
            notify=False,
        )
        send_email.reset_mock()
        delete_ledger_entry(self.family, entry.pk, notify=True)
        send_email.assert_called_once()
        self.assertIn("Your YEA balance was updated", send_email.call_args.kwargs["subject"])
        self.assertIn("Family balance (what the household owes): $0.00", send_email.call_args.kwargs["message"])

    @patch("portal.email_templates.send_site_email", return_value=1)
    def test_manual_send_updated_balance_email(self, send_email):
        post_charge(self.family, "Maya Lee", "tuition", "35.00", date(2026, 9, 8), "Weekly tuition", notify=False)
        send_email.reset_mock()
        sent = send_updated_balance_email(self.family)
        self.assertEqual(sent, 1)
        self.assertIn("Your YEA balance was updated", send_email.call_args.kwargs["subject"])
        self.assertIn("35.00", send_email.call_args.kwargs["message"])

    @override_settings(PORTAL_PREVIEW_MODE=False)
    @patch("portal.email_templates.send_site_email", return_value=1)
    def test_billing_tab_manual_send_button(self, send_email):
        post_charge(self.family, "Maya Lee", "tuition", "35.00", date(2026, 9, 8), "Weekly tuition", notify=False)
        self.client.force_login(self.admin)
        session = self.client.session
        session[PORTAL_AUTH_SESSION_KEY] = "admin"
        session.save()
        send_email.reset_mock()
        response = self.client.post(
            reverse("portal_staff_billing_action", kwargs={"family_slug": "lee"}),
            {"portal_area": "admin", "family_id": str(self.family.pk), "action": "send_balance_email"},
        )
        self.assertEqual(response.status_code, 302)
        send_email.assert_called_once()


class LatePaymentTemplateTests(TestCase):
    def setUp(self):
        self.unit = PortalUnit.objects.create(slug="school-18", name="School 18", is_active=True)
        self.family = PortalFamily.objects.create(
            unit=self.unit,
            slug="nguyen",
            name="Nguyen",
            status="Active",
        )
        PortalChild.objects.create(family=self.family, name="Kim Nguyen", is_active=True)
        user = get_user_model().objects.create_user(
            username="parent:nguyen",
            password="ParentPass123",
            email="nguyen@example.com",
        )
        PortalParentAccount.objects.create(user=user, family=self.family)
        self.paid = PortalFamily.objects.create(unit=self.unit, slug="paid", name="Paid", status="Active")
        PortalChild.objects.create(family=self.paid, name="Pat Paid", is_active=True)
        paid_user = get_user_model().objects.create_user(
            username="parent:paid",
            password="ParentPass123",
            email="paid@example.com",
        )
        PortalParentAccount.objects.create(user=paid_user, family=self.paid)
        self.admin = get_user_model().objects.create_user(username="staff:portaladmin", password="AdminPass123")
        PortalStaffAccount.objects.create(
            user=self.admin,
            unit=self.unit,
            display_name="Portal Admin",
            role="Portal admin",
            all_units_access=True,
            is_active=True,
        )

    def test_preview_only_lists_families_with_a_balance(self):
        post_charge(self.family, "Kim Nguyen", "tuition", "40.00", date(2026, 9, 8), "Weekly tuition", notify=False)
        rows = late_notice_preview_rows()
        emails = [row["email"] for row in rows]
        self.assertEqual(emails, ["nguyen@example.com"])
        self.assertEqual(rows[0]["balance"], "40.00")

    @patch("portal.member_admin.send_site_email", return_value=1)
    def test_late_template_send_only_to_families_with_balance(self, send_email):
        post_charge(self.family, "Kim Nguyen", "tuition", "40.00", date(2026, 9, 8), "Weekly tuition", notify=False)
        sent, total = send_late_payment_notices()
        self.assertEqual((sent, total), (1, 1))
        kwargs = send_email.call_args.kwargs
        self.assertEqual(kwargs["recipient_list"], ["nguyen@example.com"])
        self.assertIn("due Friday", kwargs["message"])
        self.assertIn("$15.00", kwargs["message"])
        self.assertIn("Tuesday", kwargs["message"])
        self.assertIn("40.00", kwargs["message"])

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_parent_emails_page_has_late_template_and_send_now(self):
        self.client.force_login(self.admin)
        session = self.client.session
        session[PORTAL_AUTH_SESSION_KEY] = "admin"
        session.save()
        response = self.client.get(reverse("portal_admin_page", kwargs={"page": "parent-emails"}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Friday late-payment reminder")
        self.assertContains(response, "send_late_payment_notices")
        self.assertContains(response, "Send late-payment email now")
        self.assertContains(response, "Updated balance email")

    @patch("portal.management.commands.send_late_payment_notices.send_late_payment_notices", return_value=(1, 1))
    def test_management_command_skips_non_friday_without_force(self, send_notices):
        out = StringIO()
        with patch("portal.management.commands.send_late_payment_notices.timezone") as tz:
            tz.localdate.return_value = date(2026, 9, 10)  # Thursday
            call_command("send_late_payment_notices", stdout=out)
        send_notices.assert_not_called()
        self.assertIn("Friday", out.getvalue())

    @patch("portal.management.commands.send_late_payment_notices.send_late_payment_notices", return_value=(1, 1))
    def test_management_command_force_sends(self, send_notices):
        call_command("send_late_payment_notices", force=True, stdout=StringIO())
        send_notices.assert_called_once()


class OwedWeeksReportAndLateFeeTests(TestCase):
    def setUp(self):
        self.unit = PortalUnit.objects.create(slug="school-18", name="School 18", is_active=True)
        self.other = PortalUnit.objects.create(slug="school-26", name="School 26", is_active=True)
        self.family = PortalFamily.objects.create(
            unit=self.unit,
            slug="jacobs",
            name="Jacobs",
            status="Active",
            program_label="After-School 2026–27",
        )
        self.jordan = PortalChild.objects.create(family=self.family, name="Jordan Jacobs", is_active=True)
        self.maya = PortalChild.objects.create(family=self.family, name="Maya Jacobs", is_active=True)
        self.other_family = PortalFamily.objects.create(
            unit=self.other,
            slug="chen",
            name="Chen",
            status="Active",
            program_label="Before-care",
        )
        self.ethan = PortalChild.objects.create(family=self.other_family, name="Ethan Chen", is_active=True)
        post_charge(
            self.family,
            "Jordan Jacobs",
            "tuition",
            "35.00",
            date(2026, 9, 8),
            "Weekly tuition — Jordan Jacobs (9/8/26–9/12/26)",
            notify=False,
        )
        post_charge(
            self.family,
            "Maya Jacobs",
            "tuition",
            "60.00",
            date(2026, 9, 15),
            "Weekly tuition — Maya Jacobs (9/15/26–9/19/26)",
            notify=False,
        )
        post_charge(
            self.other_family,
            "Ethan Chen",
            "tuition",
            "25.00",
            date(2026, 9, 8),
            "Weekly copay — Ethan Chen (9/8/26–9/12/26)",
            notify=False,
        )
        self.admin = get_user_model().objects.create_user(username="staff:portaladmin", password="AdminPass123")
        PortalStaffAccount.objects.create(
            user=self.admin,
            unit=self.unit,
            display_name="Portal Admin",
            role="Portal admin",
            all_units_access=True,
            is_active=True,
        )
        self.staff = get_user_model().objects.create_user(username="staff:unit", password="StaffPass123")
        PortalStaffAccount.objects.create(
            user=self.staff,
            unit=self.unit,
            display_name="Unit Staff",
            role="Unit director",
            is_active=True,
        )

    def test_week_label_from_charge_description(self):
        self.assertEqual(
            week_label_from_charge("Weekly tuition — Ada (9/8/26–9/12/26)", date(2026, 9, 8)),
            "9/8/26–9/12/26",
        )
        self.assertEqual(
            week_label_from_charge("Weekly tuition", date(2026, 9, 10)),
            "9/7/26–9/11/26",
        )

    def test_report_lists_owed_weeks(self):
        report = owed_weeks_report({}, admin=True)
        by_child = {row["child"]: row for row in report["rows"]}
        self.assertIn("Jordan Jacobs", by_child)
        self.assertIn("9/8/26–9/12/26", by_child["Jordan Jacobs"]["weeks_display"])
        self.assertEqual(by_child["Jordan Jacobs"]["child_balance"], "35.00")
        self.assertIn("9/15/26–9/19/26", by_child["Maya Jacobs"]["weeks_display"])
        self.assertEqual(by_child["Maya Jacobs"]["child_balance"], "60.00")

    def test_report_filters_by_name_program_and_unit(self):
        by_name = owed_weeks_report({"q": "jordan"}, admin=True)
        self.assertEqual([row["child"] for row in by_name["rows"]], ["Jordan Jacobs"])
        by_program = owed_weeks_report({"program": "Before-care"}, admin=True)
        self.assertEqual([row["child"] for row in by_program["rows"]], ["Ethan Chen"])
        by_unit = owed_weeks_report({"unit": "school-18"}, admin=True)
        self.assertEqual({row["child"] for row in by_unit["rows"]}, {"Jordan Jacobs", "Maya Jacobs"})

    def test_staff_report_is_unit_scoped(self):
        report = owed_weeks_report({}, unit=self.unit, admin=False)
        self.assertEqual({row["child"] for row in report["rows"]}, {"Jordan Jacobs", "Maya Jacobs"})
        self.assertNotIn("Ethan Chen", {row["child"] for row in report["rows"]})

    def test_bulk_late_fee_only_on_selected_children(self):
        posted = post_late_fees([self.jordan.pk], notify=False)
        self.assertEqual(len(posted), 1)
        jordan_late = PortalLedgerEntry.objects.filter(
            family=self.family,
            child_name="Jordan Jacobs",
            description="Late fee",
        )
        maya_late = PortalLedgerEntry.objects.filter(
            family=self.family,
            child_name="Maya Jacobs",
            description="Late fee",
        )
        self.assertEqual(jordan_late.count(), 1)
        self.assertEqual(jordan_late.first().amount, Decimal("15.00"))
        self.assertEqual(maya_late.count(), 0)

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_admin_report_page_and_csv(self):
        self.client.force_login(self.admin)
        session = self.client.session
        session[PORTAL_AUTH_SESSION_KEY] = "admin"
        session.save()
        response = self.client.get(reverse("portal_admin_owed_weeks_report"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Jordan Jacobs")
        self.assertContains(response, "9/8/26–9/12/26")
        self.assertContains(response, "Charge $15.00 late fee on selected")
        csv_response = self.client.get(reverse("portal_admin_owed_weeks_report") + "?format=csv")
        self.assertEqual(csv_response.status_code, 200)
        self.assertIn("Jordan Jacobs", csv_response.content.decode())

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_staff_report_hides_other_unit(self):
        self.client.force_login(self.staff)
        session = self.client.session
        session[PORTAL_AUTH_SESSION_KEY] = "staff"
        session.save()
        response = self.client.get(reverse("portal_staff_owed_weeks_report"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Jordan Jacobs")
        self.assertNotContains(response, "Ethan Chen")

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_bulk_late_fee_post_only_selected(self):
        self.client.force_login(self.admin)
        session = self.client.session
        session[PORTAL_AUTH_SESSION_KEY] = "admin"
        session.save()
        response = self.client.post(
            reverse("portal_admin_owed_weeks_late_fee"),
            {"portal_area": "admin", "child_ids": [str(self.maya.pk)]},
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            PortalLedgerEntry.objects.filter(
                family=self.family, child_name="Maya Jacobs", description="Late fee", amount=Decimal("15.00")
            ).exists()
        )
        self.assertFalse(
            PortalLedgerEntry.objects.filter(family=self.family, child_name="Jordan Jacobs", description="Late fee").exists()
        )

    def test_default_late_template_exists(self):
        template = get_email_template(PortalEmailTemplate.KEY_LATE_PAYMENT)
        self.assertTrue(template.is_enabled)
        self.assertIn("Friday", template.body)
        self.assertIn("Tuesday", template.body)
