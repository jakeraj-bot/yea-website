from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from portal.admin_config import save_scholarship_fund
from portal.admin_reports import build_admin_report
from portal.billing_services import run_due_plan_charges, update_child_billing_plan
from portal.models import (
    PortalAgency,
    PortalAgencyProfile,
    PortalChild,
    PortalFamily,
    PortalLedgerEntry,
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
