"""Delete/edit offline payments, live overdue, unit totals, Account Balance report."""

from datetime import date
from decimal import Decimal
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from portal.admin_config import save_scholarship_fund
from portal.admin_reports import build_admin_report
from portal.admin_services import get_admin_dashboard_live
from portal.billing_services import (
    delete_ledger_entry,
    is_offline_staff_payment,
    post_charge,
    post_credit,
    post_payment,
    prepare_billing_for_staff,
    update_child_billing_plan,
    update_ledger_credit,
    update_offline_payment,
)
from portal.family_list import family_balance, unit_balance_summary
from portal.live_services import family_meta_live
from portal.models import (
    PortalChild,
    PortalFamily,
    PortalLedgerEntry,
    PortalPayment,
    PortalStaffAccount,
    PortalUnit,
)
from portal.parent_services import get_billing_live, record_successful_payment
from portal.staff_auth import PORTAL_AUTH_SESSION_KEY
from portal.tests.test_family_units import _make_application


class PaymentEditOverdueUnitBalanceTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.unit = PortalUnit.objects.create(slug="school-18", name="School 18", is_active=True)
        self.unit_26 = PortalUnit.objects.create(slug="school-26", name="School 26", is_active=True)
        self.family = PortalFamily.objects.create(
            unit=self.unit,
            slug="jacobs",
            name="Jacobs",
            billing_type="Private pay",
            status="Active",
            balance=Decimal("0.00"),
        )
        self.jordan = PortalChild.objects.create(
            family=self.family,
            name="Jordan Jacobs",
            school="School 18",
            billing_plan="Weekly",
            is_active=True,
        )
        self.admin = User.objects.create_user(username="staff:yeaadmin", password="AdminPass123")
        PortalStaffAccount.objects.create(
            user=self.admin,
            unit=self.unit,
            display_name="Jakera",
            role="Portal admin",
            all_units_access=True,
            is_active=True,
            can_add_charge=True,
            can_delete_charge=True,
        )
        self.front = User.objects.create_user(username="staff:frontdesk", password="StaffPass123")
        PortalStaffAccount.objects.create(
            user=self.front,
            unit=self.unit,
            display_name="Front Desk",
            role="Front desk",
            all_units_access=False,
            is_active=True,
            can_add_charge=True,
            can_delete_charge=False,
        )

    def _login(self, user, area="admin"):
        self.client.force_login(user)
        session = self.client.session
        session[PORTAL_AUTH_SESSION_KEY] = area
        session.save()

    def _charge(self, amount="50.00", child="Jordan Jacobs"):
        return post_charge(
            self.family,
            child,
            "tuition",
            amount,
            date(2026, 9, 8),
            f"Weekly tuition — {child} (9/8/26–9/12/26)",
            notify=False,
        )

    def test_delete_cash_check_money_order_recalcs_balance(self):
        self._charge("80.00")
        post_payment(self.family, "Jordan Jacobs", "30.00", date(2026, 9, 9), "Cash")
        self.assertEqual(family_balance(self.family), Decimal("50.00"))
        cash = PortalLedgerEntry.objects.get(family=self.family, entry_type="payment")
        self.assertTrue(is_offline_staff_payment(cash))
        delete_ledger_entry(self.family, cash.pk)
        self.assertEqual(family_balance(self.family), Decimal("80.00"))
        self.assertFalse(PortalPayment.objects.filter(family=self.family).exists())

        post_payment(self.family, "Jordan Jacobs", "20.00", date(2026, 9, 10), "Check", "Desk", "2201")
        post_payment(self.family, "Jordan Jacobs", "10.00", date(2026, 9, 11), "Money order", "MO", "555")
        self.assertEqual(family_balance(self.family), Decimal("50.00"))
        for entry in PortalLedgerEntry.objects.filter(family=self.family, entry_type="payment"):
            delete_ledger_entry(self.family, entry.pk)
        self.assertEqual(family_balance(self.family), Decimal("80.00"))
        self.assertEqual(PortalPayment.objects.filter(family=self.family).count(), 0)

    def test_cannot_delete_stripe_card_payment(self):
        self._charge("40.00")
        payment = PortalPayment.objects.create(
            family=self.family,
            amount=Decimal("40.00"),
            fee_amount=Decimal("1.46"),
            total_charged=Decimal("41.46"),
            payment_kind="balance",
            dropin_child="Jordan Jacobs",
            stripe_session_id="cs_no_delete",
            stripe_payment_intent_id="pi_no_delete",
        )
        record_successful_payment(payment, method_label="Visa ending 4242", child_name="Jordan Jacobs")
        entry = PortalLedgerEntry.objects.get(family=self.family, entry_type="payment")
        self.assertFalse(is_offline_staff_payment(entry))
        with self.assertRaises(ValueError):
            delete_ledger_entry(self.family, entry.pk)
        self.assertEqual(family_balance(self.family), Decimal("0.00"))
        self.assertTrue(PortalLedgerEntry.objects.filter(pk=entry.pk).exists())

    def test_edit_check_money_order_number_and_date(self):
        self._charge("25.00")
        post_payment(self.family, "Jordan Jacobs", "25.00", date(2026, 9, 9), "Check", "Weekly", "2201")
        entry = PortalLedgerEntry.objects.get(family=self.family, entry_type="payment")
        update_offline_payment(
            self.family,
            entry.pk,
            payment_date=date(2026, 9, 4),
            check_number="9901",
        )
        entry.refresh_from_db()
        self.assertEqual(entry.date, date(2026, 9, 4))
        self.assertEqual(entry.reference_number, "9901")
        receipt = PortalPayment.objects.get(family=self.family)
        self.assertEqual(receipt.reference_number, "9901")
        self.assertEqual(timezone.localtime(receipt.paid_at).date(), date(2026, 9, 4))

        post_payment(self.family, "Jordan Jacobs", "5.00", date(2026, 9, 12), "Money order", "Extra", "111")
        mo = PortalLedgerEntry.objects.filter(family=self.family, reference_number="111").first()
        update_offline_payment(
            self.family,
            mo.pk,
            payment_date=date(2026, 9, 1),
            money_order_number="8888",
        )
        mo.refresh_from_db()
        self.assertEqual(mo.reference_number, "8888")
        self.assertEqual(mo.date, date(2026, 9, 1))

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_front_desk_can_delete_offline_payment_not_charge(self):
        charge = self._charge("40.00")
        post_payment(self.family, "Jordan Jacobs", "15.00", date(2026, 9, 9), "Cash")
        payment = PortalLedgerEntry.objects.get(family=self.family, entry_type="payment")
        self._login(self.front, "staff")
        denied = self.client.post(
            reverse("portal_staff_billing_action", kwargs={"family_slug": "jacobs"}),
            {
                "portal_area": "staff",
                "family_id": str(self.family.pk),
                "action": "delete",
                "entry_id": str(charge.pk),
                "delete_reason": "Trying to delete a charge",
            },
            follow=True,
        )
        self.assertTrue(PortalLedgerEntry.objects.filter(pk=charge.pk).exists())
        self.assertContains(denied, "cannot delete")

        removed = self.client.post(
            reverse("portal_staff_billing_action", kwargs={"family_slug": "jacobs"}),
            {
                "portal_area": "staff",
                "family_id": str(self.family.pk),
                "action": "delete",
                "entry_id": str(payment.pk),
                "delete_reason": "Wrong cash amount entered",
            },
            follow=True,
        )
        self.assertEqual(removed.status_code, 200)
        self.assertFalse(PortalLedgerEntry.objects.filter(pk=payment.pk).exists())
        self.assertEqual(family_balance(self.family), Decimal("40.00"))

    def test_overview_overdue_updates_after_payment_delete_and_credit(self):
        self._charge("50.00")
        dashboard = get_admin_dashboard_live()
        self.assertEqual(dashboard["overdue_families"], 1)
        self.assertEqual(dashboard["overdue_amount"], "50.00")

        post_payment(self.family, "Jordan Jacobs", "20.00", date(2026, 9, 9), "Cash")
        dashboard = get_admin_dashboard_live()
        self.assertEqual(dashboard["overdue_amount"], "30.00")

        payment = PortalLedgerEntry.objects.get(family=self.family, entry_type="payment")
        delete_ledger_entry(self.family, payment.pk)
        dashboard = get_admin_dashboard_live()
        self.assertEqual(dashboard["overdue_amount"], "50.00")

        post_credit(self.family, "Jordan Jacobs", "50.00", date(2026, 9, 10), "Billing correction")
        dashboard = get_admin_dashboard_live()
        self.assertEqual(dashboard["overdue_families"], 0)
        self.assertEqual(dashboard["overdue_amount"], "0.00")

    def test_unapproved_application_not_in_overdue_or_report(self):
        pending = PortalFamily.objects.create(
            unit=self.unit,
            slug="pending-app",
            name="Pending",
            billing_type="Private pay",
            status="Active",
        )
        child = PortalChild.objects.create(
            family=pending,
            name="Ada Pending",
            school="School 18",
            is_active=True,
        )
        _make_application(pending, status="under_review")
        pending.enrollment_applications.update(student_first_name="Ada", student_last_name="Pending")
        post_charge(
            pending,
            child.name,
            "tuition",
            "75.00",
            date(2026, 9, 8),
            "Weekly tuition — Ada Pending",
            notify=False,
        )
        dashboard = get_admin_dashboard_live()
        self.assertEqual(dashboard["overdue_families"], 0)
        self.assertEqual(dashboard["overdue_amount"], "0.00")
        unit_rows = {row["slug"]: row for row in unit_balance_summary()}
        self.assertEqual(unit_rows["school-18"]["overdue"], "0.00")
        self.assertEqual(unit_rows["school-18"]["family_count"], 0)
        report = build_admin_report("balances", {})
        names = [row["child"] for row in report["rows"]]
        self.assertNotIn("Ada Pending", names)

    def test_unit_totals_count_child_unit_not_family_twice(self):
        other = PortalFamily.objects.create(
            unit=self.unit,
            slug="split",
            name="Split",
            billing_type="Private pay",
            status="Active",
        )
        at_18 = PortalChild.objects.create(
            family=other,
            name="Ava Split",
            unit=self.unit,
            is_active=True,
        )
        at_26 = PortalChild.objects.create(
            family=other,
            name="Ben Split",
            unit=self.unit_26,
            is_active=True,
        )
        post_charge(other, at_18.name, "tuition", "40.00", date(2026, 9, 8), "Tuition 18", notify=False)
        post_charge(other, at_26.name, "tuition", "25.00", date(2026, 9, 8), "Tuition 26", notify=False)
        self._charge("10.00")
        rows = {row["slug"]: row for row in unit_balance_summary()}
        self.assertEqual(rows["school-18"]["overdue"], "50.00")
        self.assertEqual(rows["school-18"]["family_count"], 2)
        self.assertEqual(rows["school-26"]["overdue"], "25.00")
        self.assertEqual(rows["school-26"]["family_count"], 1)
        dashboard = get_admin_dashboard_live()
        self.assertEqual(dashboard["unit_balances"][0]["overdue"], "50.00")

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_account_balance_report_structure_and_print_header(self):
        self._charge("35.00")
        post_payment(self.family, "Jordan Jacobs", "5.00", date(2026, 9, 9), "Cash")
        report = build_admin_report("balances", {})
        self.assertEqual(report["title"], "Account Balance")
        self.assertEqual(
            [label for _key, label in report["columns"]],
            ["#", "Child's Name", "Amount Owe", "Description", "Paid", "Notes"],
        )
        self.assertTrue(report["print_header"])
        jordan = next(row for row in report["rows"] if row["child"] == "Jordan Jacobs")
        self.assertEqual(jordan["amount_owe"], "30.00")
        self.assertIn("Weekly tuition — Jordan Jacobs (9/8/26–9/12/26)", jordan["description"])
        self.assertNotIn("Owe for account balance", jordan["description"])
        self.assertEqual(jordan["paid"], "")
        self.assertFalse(jordan["paid_checked"])
        self.assertEqual(jordan["paid_amount"], "5.00")
        self.assertIn("Weekly", jordan["notes"])
        self.assertNotIn("status", jordan)

        self._login(self.admin, "admin")
        page = self.client.get(reverse("portal_admin_data_report", kwargs={"report_slug": "balances"}))
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, "Account Balance")
        self.assertContains(page, "Amount Owe")
        self.assertNotContains(page, "Balance Report")
        self.assertContains(page, "yea-logo.png")
        self.assertContains(page, "Jordan Jacobs")
        self.assertContains(page, "Balances by unit")
        self.assertContains(page, ">Credits<")
        self.assertContains(page, "portal-print-title-row")
        self.assertEqual(page.content.decode().count("portal-print-title-row"), 1)
        self.assertEqual(page.content.decode().count("portal-medical-report-header"), 1)
        csv_response = self.client.get(
            reverse("portal_admin_data_report", kwargs={"report_slug": "balances"}),
            {"format": "csv"},
        )
        header = csv_response.content.decode().splitlines()[0]
        self.assertEqual(header, "#,Child's Name,Amount Owe,Description,Paid,Notes")
        staff = self.client
        self._login(self.admin, "staff")
        staff_page = staff.get(reverse("portal_staff_account_balance_report"))
        self.assertEqual(staff_page.status_code, 200)
        self.assertContains(staff_page, "Account Balance")

    def test_overpay_keeps_credit_and_delete_other_payment_leaves_it(self):
        self._charge("70.00")
        post_payment(self.family, "Jordan Jacobs", "10.00", date(2026, 9, 9), "Cash", "Small cash")
        post_payment(self.family, "Jordan Jacobs", "100.00", date(2026, 9, 10), "Cash", "Overpay cash")
        self.assertEqual(family_balance(self.family), Decimal("-40.00"))
        billing = get_billing_live(self.family)
        self.assertTrue(billing["has_credit"])
        self.assertEqual(billing["account_credit"], "40.00")
        self.assertEqual(billing["running_balance"], "-40.00")
        self.assertEqual(billing["balance_due"], "0.00")
        meta = family_meta_live("jacobs", family_id=self.family.pk)
        self.assertTrue(meta["has_credit"])
        self.assertEqual(meta["account_credit"], "40.00")

        small = PortalLedgerEntry.objects.get(family=self.family, description="Small cash")
        delete_ledger_entry(self.family, small.pk)
        self.assertEqual(family_balance(self.family), Decimal("-30.00"))
        billing = get_billing_live(self.family)
        self.assertTrue(billing["has_credit"])
        self.assertEqual(billing["account_credit"], "30.00")
        report = build_admin_report("balances", {})
        jordan = next(row for row in report["rows"] if row["child"] == "Jordan Jacobs")
        self.assertEqual(jordan["amount_owe"], "-30.00")
        self.assertEqual(jordan["description"], "Credit $30.00")
        unit_rows = {row["slug"]: row for row in unit_balance_summary()}
        self.assertTrue(unit_rows["school-18"]["has_credit"])
        self.assertEqual(unit_rows["school-18"]["account_credit"], "30.00")
        self.assertEqual(unit_rows["school-18"]["overdue"], "0.00")

        overpay = PortalLedgerEntry.objects.get(family=self.family, description="Overpay cash")
        delete_ledger_entry(self.family, overpay.pk)
        self.assertEqual(family_balance(self.family), Decimal("70.00"))
        billing = get_billing_live(self.family)
        self.assertFalse(billing["has_credit"])
        self.assertEqual(billing["running_balance"], "70.00")

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_billing_page_shows_credit_and_deletes_this_payment_copy(self):
        self._charge("70.00")
        post_payment(self.family, "Jordan Jacobs", "100.00", date(2026, 9, 10), "Cash")
        self._login(self.admin, "admin")
        page = self.client.get(reverse("portal_admin_family_billing", kwargs={"family_slug": "jacobs"}))
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, "Account credit")
        self.assertContains(page, "$30.00 credit")
        self.assertContains(page, "Delete this payment?")
        self.assertContains(page, "the account keeps that credit")
        self.assertNotContains(page, "The credit comes off the ledger")
        preview = prepare_billing_for_staff(self.family, {"can_delete_charge": True, "can_add_credit": True})
        self.assertTrue(preview["has_credit"])
        self.assertEqual(preview["account_credit"], "30.00")

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_edit_credit_description_date_and_amount(self):
        self._charge("70.00")
        post_credit(self.family, "Jordan Jacobs", "20.00", date(2026, 9, 11), "Goodwill")
        self.assertEqual(family_balance(self.family), Decimal("50.00"))
        entry = PortalLedgerEntry.objects.get(family=self.family, entry_type="credit")
        preview = prepare_billing_for_staff(self.family, {"can_delete_charge": True, "can_add_credit": True})
        credit_row = next(row for row in preview["ledger"] if row["type"] == "credit")
        self.assertTrue(credit_row["editable"])
        update_ledger_credit(
            self.family,
            entry.pk,
            description="Billing correction — extra week",
            entry_date=date(2026, 9, 4),
            amount="40.00",
        )
        entry.refresh_from_db()
        self.assertEqual(entry.description, "Billing correction — extra week")
        self.assertEqual(entry.date, date(2026, 9, 4))
        self.assertEqual(entry.amount, Decimal("-40.00"))
        self.assertEqual(family_balance(self.family), Decimal("30.00"))

        self._login(self.admin, "admin")
        response = self.client.post(
            reverse("portal_staff_billing_action", kwargs={"family_slug": "jacobs"}),
            {
                "portal_area": "admin",
                "action": "edit_description",
                "entry_id": str(entry.pk),
                "description": "Staff credit — September",
                "date": "2026-09-01",
                "amount": "15.00",
            },
        )
        self.assertEqual(response.status_code, 302)
        entry.refresh_from_db()
        self.assertEqual(entry.description, "Staff credit — September")
        self.assertEqual(entry.date, date(2026, 9, 1))
        self.assertEqual(entry.amount, Decimal("-15.00"))
        self.assertEqual(family_balance(self.family), Decimal("55.00"))
        billing = self.client.get(reverse("portal_admin_family_billing", kwargs={"family_slug": "jacobs"}))
        self.assertContains(billing, "Staff credit — September")

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_edit_scholarship_description_persists(self):
        today = timezone.localdate()
        fund = save_scholarship_fund({"name": "YEA General Scholarship", "description": "Need-based"})
        update_child_billing_plan(
            self.family,
            "Jordan Jacobs",
            "Weekly",
            "70.00",
            billing_type="Scholarship",
            scholarship_fund_id=fund.pk,
            scholarship_full_rate="70.00",
            scholarship_parent_amount="50.00",
            auto_charge=True,
            next_charge_date=today,
            charge_weekday=today.weekday(),
        )
        discount = PortalLedgerEntry.objects.get(family=self.family, entry_type="discount")
        preview = prepare_billing_for_staff(self.family, {"can_delete_charge": True})
        discount_row = next(row for row in preview["ledger"] if row["type"] == "discount")
        self.assertTrue(discount_row["editable"])
        self._login(self.admin, "admin")
        response = self.client.post(
            reverse("portal_staff_billing_action", kwargs={"family_slug": "jacobs"}),
            {
                "portal_area": "admin",
                "action": "edit_description",
                "entry_id": str(discount.pk),
                "description": "After care — YEA General Scholarship scholarship",
            },
        )
        self.assertEqual(response.status_code, 302)
        discount.refresh_from_db()
        self.assertEqual(discount.description, "After care — YEA General Scholarship scholarship")
        page = self.client.get(reverse("portal_admin_family_billing", kwargs={"family_slug": "jacobs"}))
        self.assertContains(page, "After care — YEA General Scholarship scholarship")
        self.assertEqual(family_balance(self.family), Decimal("50.00"))

    def test_account_balance_filters_unit_members_and_balance(self):
        at_26 = PortalChild.objects.create(
            family=self.family,
            name="Ben School26",
            unit=self.unit_26,
            billing_plan="Weekly",
            is_active=True,
        )
        inactive = PortalChild.objects.create(
            family=self.family,
            name="Omar Inactive",
            unit=self.unit,
            billing_plan="Weekly",
            is_active=False,
        )
        self._charge("100.00", "Jordan Jacobs")
        post_payment(self.family, "Jordan Jacobs", "40.00", date(2026, 9, 9), "Cash")
        post_credit(self.family, "Jordan Jacobs", "20.00", date(2026, 9, 10), "Scholarship")
        post_charge(self.family, at_26.name, "tuition", "50.00", date(2026, 9, 8), "Tuition 26", notify=False)
        post_payment(self.family, at_26.name, "80.00", date(2026, 9, 11), "Check", "Overpay", "9")
        post_charge(self.family, inactive.name, "tuition", "15.00", date(2026, 9, 8), "Past due inactive", notify=False)

        active = build_admin_report("balances", {"status": "Active"})
        active_names = {row["child"] for row in active["rows"]}
        self.assertEqual(active_names, {"Jordan Jacobs", "Ben School26"})
        by_child = {row["child"]: row for row in active["rows"]}
        self.assertEqual(by_child["Jordan Jacobs"]["amount_owe"], "10.00")
        self.assertEqual(by_child["Ben School26"]["amount_owe"], "0.00")
        self.assertNotIn("Credit $", by_child["Ben School26"]["description"])

        unit_18 = build_admin_report("balances", {"unit": "school-18", "status": "Active"})
        self.assertEqual([row["child"] for row in unit_18["rows"]], ["Jordan Jacobs"])

        unit_26 = build_admin_report("balances", {"unit": "school-26", "status": "Active"})
        self.assertEqual([row["child"] for row in unit_26["rows"]], ["Ben School26"])

        with_balance = build_admin_report("balances", {"status": "Active", "owes": "yes"})
        self.assertEqual([row["child"] for row in with_balance["rows"]], ["Jordan Jacobs"])
        self.assertEqual(with_balance["rows"][0]["amount_owe"], "10.00")

        without_balance = build_admin_report("balances", {"status": "Active", "owes": "no"})
        self.assertEqual([row["child"] for row in without_balance["rows"]], ["Ben School26"])

        credit = build_admin_report("balances", {"status": "Active", "owes": "credit"})
        self.assertEqual(credit["rows"], [])

        inactive_report = build_admin_report("balances", {"status": "Inactive"})
        self.assertEqual([row["child"] for row in inactive_report["rows"]], ["Omar Inactive"])

        all_members = build_admin_report("balances", {"status": ""})
        self.assertEqual(
            {row["child"] for row in all_members["rows"]},
            {"Jordan Jacobs", "Ben School26", "Omar Inactive"},
        )

        self._login(self.admin, "admin")
        page = self.client.get(
            reverse("portal_admin_data_report", kwargs={"report_slug": "balances"}),
            {"unit": "school-18", "status": "Active", "owes": "yes"},
        )
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, "id=\"account-balance-filters\"")
        self.assertContains(page, "id=\"account-balance-unit\"")
        self.assertContains(page, "id=\"account-balance-members\"")
        self.assertContains(page, "id=\"account-balance-owes\"")
        self.assertContains(page, "Jordan Jacobs")
        self.assertNotContains(page, "Ben School26")
        self.assertNotContains(page, "Omar Inactive")
        self.assertContains(page, "portal-cell-wrap")
        self.assertContains(page, "class=\"portal-row-num\"")
        self.assertContains(page, "class=\"portal-ab-col-row_num\"")
        self.assertContains(page, "class=\"portal-ab-col-description\"")
        self.assertContains(page, "<colgroup>")
        self.assertContains(page, "All units")
        self.assertContains(page, "With balance")
        css = (Path(__file__).resolve().parents[2] / "static" / "css" / "portal.css").read_text()
        self.assertEqual(css.count("{"), css.count("}"))
        self.assertIn(".portal-account-balance-print-table .portal-cell-wrap", css)
        self.assertIn("overflow-wrap: anywhere", css)
        self.assertIn("table-layout: fixed", css)
        ab_css = css.split(".portal-account-balance-print-table {", 1)[1]
        self.assertIn("col.portal-ab-col-row_num", ab_css)
        self.assertIn("width: 2.2rem", ab_css)
        self.assertIn("col.portal-ab-col-description", ab_css)
        self.assertIn("width: 40%", ab_css)
        self.assertNotIn("th:nth-child(1)", ab_css)
        self.assertNotIn("td:nth-child(1)", ab_css)
