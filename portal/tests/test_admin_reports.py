from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from portal.admin_config import save_scholarship_fund
from portal.admin_reports import build_admin_report
from portal.billing_services import post_payment, run_due_plan_charges, update_child_billing_plan
from portal.models import (
    PortalAgency,
    PortalAgencyProfile,
    PortalChild,
    PortalFamily,
    PortalLedgerEntry,
    PortalPayment,
    PortalScholarshipAssignment,
    PortalScholarshipFund,
    PortalStaffAccount,
    PortalUnit,
)
from portal.staff_auth import PORTAL_AUTH_SESSION_KEY


class AdminReportsAndScholarshipTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.unit = PortalUnit.objects.create(slug="school-18", name="School 18", is_active=True)
        self.family = PortalFamily.objects.create(
            unit=self.unit,
            slug="jacobs",
            name="Jacobs",
            billing_type="Private pay",
            status="Active",
        )
        self.child = PortalChild.objects.create(
            family=self.family,
            name="Jordan Jacobs",
            school="School 18",
            billing_plan="Weekly",
            billing_amount=Decimal("50.00"),
            is_active=True,
        )
        self.no_plan = PortalFamily.objects.create(
            unit=self.unit,
            slug="rivera",
            name="Rivera",
            billing_type="Private pay",
            status="Active",
        )
        self.no_plan_child = PortalChild.objects.create(
            family=self.no_plan,
            name="Ada Rivera",
            school="School 26",
            billing_plan="",
            is_active=True,
        )
        self.agency = PortalAgency.objects.create(slug="passaic-4cs", name="Passaic County 4Cs", is_active=True)
        self.four_cs_family = PortalFamily.objects.create(
            unit=self.unit,
            slug="martinez",
            name="Martinez",
            billing_type="4Cs",
            status="Active",
        )
        self.four_cs_child = PortalChild.objects.create(
            family=self.four_cs_family,
            name="Sofia Martinez",
            school="School 18",
            billing_plan="Weekly copay",
            billing_amount=Decimal("25.00"),
            is_active=True,
        )
        PortalAgencyProfile.objects.create(
            unit=self.unit,
            family=self.four_cs_family,
            child=self.four_cs_child,
            agency=self.agency,
            auth_number="4CS-2026-1001",
            weekly_copay=Decimal("25.00"),
            weekly_agency_rate=Decimal("180.00"),
        )
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

    def test_billing_plan_report_filters_by_name_school_and_payment_type(self):
        all_plans = build_admin_report("plans", {})
        names = {row["child"] for row in all_plans["rows"]}
        self.assertIn("Jordan Jacobs", names)
        self.assertIn("Ada Rivera", names)
        by_school = build_admin_report("plans", {"school": "School 26"})
        self.assertEqual([row["child"] for row in by_school["rows"]], ["Ada Rivera"])
        by_type = build_admin_report("plans", {"billing": "4Cs"})
        self.assertEqual([row["child"] for row in by_type["rows"]], ["Sofia Martinez"])
        by_name = build_admin_report("plans", {"q": "jordan"})
        self.assertEqual([row["child"] for row in by_name["rows"]], ["Jordan Jacobs"])

    def test_missing_plan_report_lists_children_without_amount(self):
        report = build_admin_report("missing-plans", {})
        children = {row["child"] for row in report["rows"]}
        self.assertIn("Ada Rivera", children)
        self.assertNotIn("Jordan Jacobs", children)

    def test_four_cs_report_includes_agency_details(self):
        report = build_admin_report("four-cs", {})
        self.assertEqual(len(report["rows"]), 1)
        row = report["rows"][0]
        self.assertEqual(row["child"], "Sofia Martinez")
        self.assertEqual(row["agency"], "Passaic County 4Cs")
        self.assertEqual(row["auth_number"], "4CS-2026-1001")
        self.assertEqual(row["weekly_agency_rate"], "180.00")

    def test_ledger_and_balance_reports(self):
        PortalLedgerEntry.objects.create(
            family=self.family,
            child_name="Jordan Jacobs",
            date=timezone.localdate(),
            entry_type="charge",
            description="Weekly tuition — Jordan Jacobs",
            amount=Decimal("50.00"),
        )
        self.family.balance = Decimal("50.00")
        self.family.save(update_fields=["balance"])
        ledger = build_admin_report("ledger", {})
        self.assertEqual(len(ledger["rows"]), 1)
        self.assertIn("50.00", ledger["summary"])
        balances = build_admin_report("balances", {})
        jacobs = next(row for row in balances["rows"] if row["family"] == "Jacobs")
        self.assertEqual(jacobs["balance"], "50.00")

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_admin_reports_hub_and_csv_export(self):
        self._login_admin()
        hub = self.client.get(reverse("portal_admin_page", kwargs={"page": "reports"}))
        self.assertEqual(hub.status_code, 200)
        self.assertContains(hub, "Billing plans")
        self.assertContains(hub, "Missing billing plans")
        self.assertContains(hub, "4Cs members")
        self.assertContains(hub, "Member information")
        self.assertContains(hub, "portal-reports-grid")
        self.assertContains(hub, "portal-report-card")
        self.assertContains(hub, reverse("portal_admin_emergency_contact_report"))
        self.assertContains(hub, "Member information export")
        self.assertContains(hub, reverse("portal_admin_data_report", kwargs={"report_slug": "member-information"}))
        member_info = self.client.get(reverse("portal_admin_member_information_report"))
        self.assertEqual(member_info.status_code, 200)
        self.assertContains(member_info, "Jordan Jacobs")
        self.assertContains(hub, "Emergency contact list")
        contacts = self.client.get(reverse("portal_admin_emergency_contact_report"))
        self.assertEqual(contacts.status_code, 200)
        self.assertContains(contacts, "All units")
        self.assertContains(contacts, "Print / Save PDF")
        plans = self.client.get(reverse("portal_admin_data_report", kwargs={"report_slug": "plans"}))
        self.assertEqual(plans.status_code, 200)
        self.assertContains(plans, "Jordan Jacobs")
        csv_response = self.client.get(
            reverse("portal_admin_data_report", kwargs={"report_slug": "plans"}),
            {"format": "csv", "q": "jordan"},
        )
        self.assertEqual(csv_response.status_code, 200)
        self.assertIn("text/csv", csv_response["Content-Type"])
        self.assertIn(b"Jordan Jacobs", csv_response.content)
        four_cs = self.client.get(reverse("portal_admin_data_report", kwargs={"report_slug": "four-cs"}))
        self.assertContains(four_cs, "4CS-2026-1001")

    def test_can_add_scholarship_type_and_attach_to_weekly_plan(self):
        fund = save_scholarship_fund({"name": "YEA General Scholarship", "description": "Need-based"})
        child, posted = update_child_billing_plan(
            self.family,
            "Jordan Jacobs",
            "Weekly",
            billing_type="Scholarship",
            scholarship_fund_id=fund.pk,
            scholarship_full_rate="70.00",
            scholarship_parent_amount="50.00",
            auto_charge=True,
            next_charge_date=timezone.localdate(),
            charge_weekday=timezone.localdate().weekday(),
        )
        child.refresh_from_db()
        self.family.refresh_from_db()
        assignment = PortalScholarshipAssignment.objects.get(child=child)
        self.assertEqual(assignment.fund, fund)
        self.assertEqual(assignment.full_rate, Decimal("70.00"))
        self.assertEqual(assignment.parent_amount, Decimal("50.00"))
        self.assertEqual(child.billing_amount, Decimal("50.00"))
        self.assertEqual(self.family.billing_type, "Scholarship")
        self.assertEqual(len(posted), 1)
        types = list(PortalLedgerEntry.objects.filter(family=self.family).values_list("entry_type", "amount"))
        self.assertIn(("charge", Decimal("70.00")), types)
        self.assertIn(("discount", Decimal("-20.00")), types)
        self.assertEqual(self.family.balance, Decimal("50.00"))

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_admin_can_save_scholarship_type_and_plan(self):
        self._login_admin()
        response = self.client.post(
            reverse("portal_admin_scholarship_fund_save"),
            {"name": "Paterson Youth Fund", "description": "City partnership"},
        )
        self.assertEqual(response.status_code, 302)
        fund = PortalScholarshipFund.objects.get(name="Paterson Youth Fund")
        plans = self.client.get(reverse("portal_admin_family_plans", kwargs={"family_slug": "jacobs"}))
        self.assertContains(plans, "Paterson Youth Fund")
        self.assertContains(plans, "scholarship_fund_id")
        save = self.client.post(
            reverse("portal_staff_billing_action", kwargs={"family_slug": "jacobs"}),
            {
                "portal_area": "admin",
                "action": "update_plan",
                "child_name": "Jordan Jacobs",
                "billing_plan": "Weekly",
                "billing_type": "Scholarship",
                "scholarship_fund_id": str(fund.pk),
                "scholarship_full_rate": "70.00",
                "scholarship_parent_amount": "50.00",
                "next": reverse("portal_admin_family_plans", kwargs={"family_slug": "jacobs"}),
            },
        )
        self.assertEqual(save.status_code, 302)
        assignment = PortalScholarshipAssignment.objects.get(child=self.child)
        self.assertEqual(assignment.fund, fund)
        scholarships = self.client.get(reverse("portal_admin_data_report", kwargs={"report_slug": "scholarships"}))
        self.assertContains(scholarships, "Paterson Youth Fund")
        self.assertContains(scholarships, "Jordan Jacobs")

    def test_who_paid_what_report_lists_day_child_and_amount(self):
        self.family.primary_contact = "Jakera Jacobs"
        self.family.save(update_fields=["primary_contact"])
        today = timezone.localdate()
        post_payment(self.family, "Jordan Jacobs", "40.00", today, "Cash", "Cash — week of Sep 4")
        report = build_admin_report("payments", {})
        row = next(item for item in report["rows"] if item["child"] == "Jordan Jacobs")
        self.assertEqual(row["date"], today.isoformat())
        self.assertEqual(row["paid_by"], "Jakera Jacobs")
        self.assertEqual(row["amount"], "40.00")
        self.assertEqual(row["status"], "Paid")

    def test_stripe_settlement_report_marks_pending_card_and_excludes_in_person(self):
        today = timezone.now()
        pending = PortalPayment.objects.create(
            family=self.family,
            amount=Decimal("30.00"),
            method_label="Card",
            status=PortalPayment.STATUS_PENDING,
            stripe_session_id="cs_test_123",
            paid_at=today,
        )
        cash = PortalPayment.objects.create(
            family=self.four_cs_family,
            amount=Decimal("25.00"),
            method_label="Cash",
            status=PortalPayment.STATUS_PAID,
            paid_at=today,
        )
        report = build_admin_report("stripe-settlement", {})
        by_family = {row["family"]: row for row in report["rows"]}
        self.assertEqual(list(by_family), ["Jacobs"])
        self.assertEqual(by_family["Jacobs"]["status"], "Waiting for card")
        self.assertIn("Waiting for parent", by_family["Jacobs"]["bank_status"])
        pending.refresh_from_db()
        self.assertEqual(pending.stripe_bank_status, "waiting_for_card")
        self.assertNotIn("Martinez", by_family)
        self.assertEqual({row["family"] for row in report["waiting_for_card_rows"]}, {"Jacobs"})
        self.assertEqual(report["pending_rows"], [])
        self.assertEqual(report["waiting_to_receive_total"], "0.00")
        self.assertEqual(report["waiting_for_card_total"], "30.00")
        self.assertEqual(report["payout_groups"], [])
        self.assertEqual(report["layout"], "payout_sections")
        self.assertEqual(report["rows"][0]["section"], "Waiting for card")

    def test_stripe_settlement_groups_member_payments_under_payout(self):
        today = timezone.now()
        arrived = timezone.localdate()
        self.family.primary_contact = "Jakera Jacobs"
        self.family.save(update_fields=["primary_contact"])
        PortalPayment.objects.create(
            family=self.family,
            amount=Decimal("30.00"),
            method_label="Card",
            status=PortalPayment.STATUS_PENDING,
            stripe_session_id="cs_pending_group",
            paid_at=today,
        )
        PortalPayment.objects.create(
            family=self.no_plan,
            amount=Decimal("12.00"),
            method_label="Cash",
            status=PortalPayment.STATUS_PAID,
            paid_at=today,
        )
        PortalPayment.objects.create(
            family=self.family,
            amount=Decimal("40.00"),
            method_label="Card",
            status=PortalPayment.STATUS_PAID,
            stripe_session_id="cs_paid_a",
            stripe_payout_id="po_aaa",
            stripe_payout_descriptor="YEA SCHOOL 18",
            stripe_payout_amount=Decimal("95.00"),
            stripe_bank_status="in_bank",
            stripe_bank_date=arrived,
            paid_at=today,
        )
        PortalPayment.objects.create(
            family=self.four_cs_family,
            amount=Decimal("55.00"),
            method_label="Card",
            status=PortalPayment.STATUS_PAID,
            stripe_session_id="cs_paid_a2",
            stripe_payout_id="po_aaa",
            stripe_payout_descriptor="YEA SCHOOL 18",
            stripe_payout_amount=Decimal("95.00"),
            stripe_bank_status="in_bank",
            stripe_bank_date=arrived,
            paid_at=today,
        )
        PortalPayment.objects.create(
            family=self.family,
            amount=Decimal("20.00"),
            method_label="Card",
            status=PortalPayment.STATUS_PAID,
            stripe_session_id="cs_paid_b",
            stripe_payout_id="po_bbb",
            stripe_payout_descriptor="YEA MAIN",
            stripe_payout_amount=Decimal("20.00"),
            stripe_bank_status="in_bank",
            stripe_bank_date=arrived,
            paid_at=today,
        )
        report = build_admin_report("stripe-settlement", {})
        pending_families = {row["family"] for row in report["pending_rows"]}
        waiting_families = {row["family"] for row in report["waiting_for_card_rows"]}
        self.assertEqual(pending_families, set())
        self.assertEqual(waiting_families, {"Jacobs"})
        self.assertTrue(all(row["unit"] == "School 18" for row in report["waiting_for_card_rows"]))
        by_id = {group["payout_id"]: group for group in report["payout_groups"]}
        self.assertEqual(set(by_id), {"po_aaa", "po_bbb"})
        self.assertEqual({row["family"] for row in by_id["po_aaa"]["rows"]}, {"Jacobs", "Martinez"})
        self.assertEqual({row["family"] for row in by_id["po_bbb"]["rows"]}, {"Jacobs"})
        self.assertEqual(by_id["po_aaa"]["descriptor"], "YEA SCHOOL 18")
        self.assertEqual(by_id["po_aaa"]["amount"], "95.00")
        self.assertEqual(by_id["po_aaa"]["member_total"], "95.00")
        self.assertIn("Jakera Jacobs", {row["paid_by"] for row in by_id["po_aaa"]["rows"]})
        self.assertTrue(all(row["unit"] == "School 18" for row in report["rows"]))
        self.assertTrue(all(row["child"] for row in report["rows"]))

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_stripe_settlement_page_puts_unpaid_payments_first(self):
        today = timezone.now()
        arrived = timezone.localdate()
        PortalPayment.objects.create(
            family=self.family,
            amount=Decimal("40.00"),
            method_label="Card",
            status=PortalPayment.STATUS_PAID,
            stripe_session_id="cs_page_paid",
            stripe_payout_id="po_page_paid",
            stripe_payout_descriptor="YEA SCHOOL 18",
            stripe_payout_amount=Decimal("40.00"),
            stripe_bank_status="in_bank",
            stripe_bank_date=arrived,
            paid_at=today,
        )
        PortalPayment.objects.create(
            family=self.no_plan,
            amount=Decimal("12.00"),
            method_label="Card",
            status=PortalPayment.STATUS_PAID,
            stripe_session_id="cs_page_waiting",
            stripe_payment_intent_id="pi_page_waiting",
            stripe_charge_id="ch_page_waiting",
            stripe_bank_status="waiting_for_bank",
            paid_at=today,
        )
        self._login_admin()
        page = self.client.get(reverse("portal_admin_data_report", kwargs={"report_slug": "stripe-settlement"}))
        self.assertEqual(page.status_code, 200)
        html = page.content.decode()
        self.assertIn("Not paid out yet", html)
        self.assertIn("Waiting to receive $12.00", html)
        self.assertIn("Rivera", html)
        self.assertIn("Jacobs", html)
        self.assertIn("po_page_paid", html)
        self.assertIn("YEA SCHOOL 18", html)
        self.assertIn("portal-table--freeze-first", html)
        self.assertIn("data-table-hscroll", html)
        self.assertNotIn("Remaining payments", html)
        self.assertLess(html.find("Not paid out yet"), html.find("po_page_paid"))
        self.assertLess(html.find("Rivera"), html.find("po_page_paid"))
        csv_response = self.client.get(
            reverse("portal_admin_data_report", kwargs={"report_slug": "stripe-settlement"}),
            {"format": "csv"},
        )
        self.assertEqual(csv_response.status_code, 200)
        csv_text = csv_response.content.decode()
        self.assertIn("Section", csv_text.splitlines()[0])
        self.assertIn("Not paid out yet", csv_text)
        self.assertIn("po_page_paid", csv_text)

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_admin_can_open_payment_reports(self):
        self._login_admin()
        self.family.primary_contact = "Jakera Jacobs"
        self.family.save(update_fields=["primary_contact"])
        post_payment(self.family, "Jordan Jacobs", "15.00", timezone.localdate(), "Cash", "Cash")
        hub = self.client.get(reverse("portal_admin_page", kwargs={"page": "reports"}))
        self.assertContains(hub, "Who paid what")
        self.assertContains(hub, "Stripe &amp; bank payouts")
        payments = self.client.get(reverse("portal_admin_data_report", kwargs={"report_slug": "payments"}))
        self.assertContains(payments, "Jordan Jacobs")
        self.assertContains(payments, "Jakera Jacobs")
        settlement = self.client.get(reverse("portal_admin_data_report", kwargs={"report_slug": "stripe-settlement"}))
        self.assertEqual(settlement.status_code, 200)
        self.assertContains(settlement, "Bank / Stripe")

    def test_stripe_settlement_excludes_check_and_money_order(self):
        today = timezone.now()
        post_payment(self.family, "Jordan Jacobs", "18.00", timezone.localdate(), "Money order", "Money order #555", "555")
        post_payment(self.no_plan, "Ada Rivera", "22.00", timezone.localdate(), "Check", "Check #901", "901")
        PortalPayment.objects.create(
            family=self.four_cs_family,
            amount=Decimal("40.00"),
            method_label="Visa ending 4242",
            status=PortalPayment.STATUS_PAID,
            stripe_session_id="cs_only_stripe",
            stripe_payment_intent_id="pi_only_stripe",
            stripe_charge_id="ch_only_stripe",
            stripe_bank_status="waiting_for_bank",
            paid_at=today,
        )
        report = build_admin_report("stripe-settlement", {})
        methods = [row["method"] for row in report["rows"]]
        families = {row["family"] for row in report["rows"]}
        self.assertEqual(families, {"Martinez"})
        self.assertTrue(all("Money order" not in method and "Check" not in method for method in methods))
        self.assertEqual(report["waiting_to_receive_total"], "40.00")
        self.assertEqual(report["waiting_for_card_total"], "0.00")
        self.assertEqual(len(report["pending_rows"]), 1)
        self.assertEqual(report["pending_rows"][0]["amount"], "40.00")

    def test_stripe_settlement_hides_waiting_duplicate_of_paid_out_charge(self):
        """Same Stripe charge must not appear as Waiting for card and also in a payout."""
        today = timezone.now()
        arrived = timezone.localdate()
        PortalPayment.objects.create(
            family=self.family,
            amount=Decimal("40.00"),
            method_label="Visa ending 4242",
            status=PortalPayment.STATUS_PAID,
            stripe_session_id="cs_dup_paid",
            stripe_payment_intent_id="pi_same_purchase",
            stripe_charge_id="ch_same_purchase",
            stripe_payout_id="po_dup",
            stripe_payout_descriptor="YEA SCHOOL 18",
            stripe_payout_amount=Decimal("40.00"),
            stripe_bank_status="in_bank",
            stripe_bank_date=arrived,
            paid_at=today,
        )
        PortalPayment.objects.create(
            family=self.family,
            amount=Decimal("40.00"),
            method_label="Card",
            status=PortalPayment.STATUS_PENDING,
            stripe_session_id="cs_dup_pending",
            stripe_payment_intent_id="pi_same_purchase",
            stripe_charge_id="ch_same_purchase",
            paid_at=today,
        )
        # Same family, amount, and date — different Stripe charge — must still appear.
        PortalPayment.objects.create(
            family=self.family,
            amount=Decimal("40.00"),
            method_label="Card",
            status=PortalPayment.STATUS_PENDING,
            stripe_session_id="cs_other_checkout",
            stripe_payment_intent_id="pi_other_purchase",
            stripe_charge_id="ch_other_purchase",
            paid_at=today,
        )
        report = build_admin_report("stripe-settlement", {})
        waiting_intents = {row["stripe_payment_intent_id"] for row in report["waiting_for_card_rows"]}
        payout_intents = {
            row["stripe_payment_intent_id"]
            for group in report["payout_groups"]
            for row in group["rows"]
        }
        self.assertEqual(waiting_intents, {"pi_other_purchase"})
        self.assertEqual(payout_intents, {"pi_same_purchase"})
        self.assertNotIn("pi_same_purchase", waiting_intents)
        self.assertEqual(report["waiting_for_card_total"], "40.00")
        self.assertEqual(report["waiting_to_receive_total"], "0.00")
        statuses_for_same = [
            row["status"]
            for row in report["rows"]
            if row["stripe_payment_intent_id"] == "pi_same_purchase"
        ]
        self.assertEqual(statuses_for_same, ["Paid"])

    def test_stripe_settlement_does_not_relabel_paid_out_pending_as_waiting(self):
        from portal.stripe_services import refresh_payment_settlement

        today = timezone.now()
        leftover = PortalPayment.objects.create(
            family=self.family,
            amount=Decimal("22.00"),
            method_label="Card",
            status=PortalPayment.STATUS_PENDING,
            stripe_session_id="cs_contradict",
            stripe_payment_intent_id="pi_contradict",
            stripe_charge_id="ch_contradict",
            stripe_payout_id="po_keep",
            stripe_bank_status="in_bank",
            stripe_bank_date=timezone.localdate(),
            paid_at=today,
        )
        refresh_payment_settlement(leftover)
        leftover.refresh_from_db()
        self.assertEqual(leftover.stripe_bank_status, "in_bank")
        self.assertEqual(leftover.stripe_payout_id, "po_keep")
        report = build_admin_report("stripe-settlement", {})
        self.assertEqual(report["waiting_for_card_rows"], [])
        by_id = {group["payout_id"]: group for group in report["payout_groups"]}
        self.assertIn("po_keep", by_id)
        self.assertEqual(by_id["po_keep"]["rows"][0]["status"], "Paid")
