from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from django.utils import timezone

from portal.admin_config import save_scholarship_fund
from portal.agency_weeks import billable_week_count_for_month
from portal.four_cs_report import (
    child_is_4cs_member,
    filter_four_cs_payout_rows,
    four_cs_payout_report_bundle,
    four_cs_payout_rows,
    four_cs_payout_totals,
)
from portal.models import (
    PortalAgency,
    PortalAgencyProfile,
    PortalChild,
    PortalChildBillingPlan,
    PortalFamily,
    PortalScholarshipAssignment,
    PortalStaffAccount,
    PortalUnit,
)
from portal.staff_auth import PORTAL_AUTH_SESSION_KEY


class FourCsPayoutReportTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.school_18 = PortalUnit.objects.create(slug="school-18", name="School 18", is_active=True)
        self.school_26 = PortalUnit.objects.create(slug="school-26", name="School 26", is_active=True)
        self.agency = PortalAgency.objects.create(
            slug="passaic-4cs",
            name="Passaic County 4Cs",
            remittance_schedule="Monthly (1st business day)",
            is_active=True,
        )
        self.fund = save_scholarship_fund({"name": "YEA General Scholarship", "description": "Need-based"})

        self.weekly_family = PortalFamily.objects.create(
            unit=self.school_18,
            slug="martinez",
            name="Martinez",
            billing_type="4Cs",
            status="Active",
        )
        self.weekly_child = PortalChild.objects.create(
            family=self.weekly_family,
            name="Sofia Martinez",
            school="Lincoln Elementary",
            grade="2nd",
            billing_plan="Weekly copay",
            billing_amount=Decimal("25.00"),
            is_active=True,
        )
        PortalAgencyProfile.objects.create(
            unit=self.school_18,
            family=self.weekly_family,
            child=self.weekly_child,
            agency=self.agency,
            auth_number="4CS-WEEKLY",
            daily_copay=Decimal("5.00"),
            weekly_copay=Decimal("25.00"),
            daily_agency_rate=Decimal("36.00"),
            weekly_agency_rate=Decimal("180.00"),
        )

        self.biweekly_family = PortalFamily.objects.create(
            unit=self.school_18,
            slug="brooks",
            name="Brooks",
            billing_type="4Cs",
            status="Active",
        )
        self.biweekly_child = PortalChild.objects.create(
            family=self.biweekly_family,
            name="Miles Brooks",
            school="Lincoln Elementary",
            grade="4th",
            billing_plan="Bi-weekly",
            billing_amount=Decimal("50.00"),
            is_active=True,
        )
        PortalAgencyProfile.objects.create(
            unit=self.school_18,
            family=self.biweekly_family,
            child=self.biweekly_child,
            agency=self.agency,
            auth_number="4CS-BIWEEKLY",
            weekly_copay=Decimal("25.00"),
            weekly_agency_rate=Decimal("180.00"),
        )

        self.monthly_family = PortalFamily.objects.create(
            unit=self.school_26,
            slug="chen",
            name="Chen",
            billing_type="4Cs",
            status="Active",
        )
        self.monthly_child = PortalChild.objects.create(
            family=self.monthly_family,
            name="Ethan Chen",
            school="School 26",
            grade="5th",
            billing_plan="Monthly",
            billing_amount=Decimal("80.00"),
            is_active=True,
        )
        PortalAgencyProfile.objects.create(
            unit=self.school_26,
            family=self.monthly_family,
            child=self.monthly_child,
            agency=self.agency,
            auth_number="4CS-MONTHLY",
            weekly_copay=Decimal("20.00"),
            weekly_agency_rate=Decimal("95.00"),
        )

        self.scholarship_family = PortalFamily.objects.create(
            unit=self.school_18,
            slug="rivera",
            name="Rivera",
            billing_type="4Cs",
            status="Active",
        )
        self.scholarship_child = PortalChild.objects.create(
            family=self.scholarship_family,
            name="Ada Rivera",
            school="Lincoln Elementary",
            grade="1st",
            billing_plan="Weekly copay",
            billing_amount=Decimal("25.00"),
            is_active=True,
        )
        PortalAgencyProfile.objects.create(
            unit=self.school_18,
            family=self.scholarship_family,
            child=self.scholarship_child,
            agency=self.agency,
            auth_number="4CS-SCHOLAR",
            weekly_copay=Decimal("25.00"),
            weekly_agency_rate=Decimal("180.00"),
        )
        PortalScholarshipAssignment.objects.create(
            child=self.scholarship_child,
            fund=self.fund,
            full_rate=Decimal("25.00"),
            parent_amount=Decimal("10.00"),
            status="Active",
        )

        self.waitlist_family = PortalFamily.objects.create(
            unit=self.school_18,
            slug="waitlist",
            name="Waitlist",
            billing_type="4Cs",
            status="Waitlist",
        )
        self.waitlist_child = PortalChild.objects.create(
            family=self.waitlist_family,
            name="Nia Waitlist",
            school="Lincoln Elementary",
            grade="K",
            billing_plan="Weekly copay",
            is_active=True,
        )
        PortalAgencyProfile.objects.create(
            unit=self.school_18,
            family=self.waitlist_family,
            child=self.waitlist_child,
            agency=self.agency,
            weekly_copay=Decimal("25.00"),
            weekly_agency_rate=Decimal("180.00"),
        )

        self.private_family = PortalFamily.objects.create(
            unit=self.school_18,
            slug="jacobs",
            name="Jacobs",
            billing_type="Private pay",
            status="Active",
        )
        self.private_child = PortalChild.objects.create(
            family=self.private_family,
            name="Jordan Jacobs",
            school="Lincoln Elementary",
            grade="4th",
            billing_plan="Weekly",
            billing_amount=Decimal("70.00"),
            is_active=True,
        )

        self.admin = User.objects.create_user(username="staff:yeaadmin", password="AdminPass123")
        PortalStaffAccount.objects.create(
            user=self.admin,
            unit=self.school_18,
            display_name="Portal Admin",
            role="Portal admin",
            all_units_access=True,
            is_active=True,
        )
        self.staff = User.objects.create_user(username="staff:reports", password="StaffPass123!")
        PortalStaffAccount.objects.create(
            user=self.staff,
            unit=self.school_18,
            display_name="Report Staff",
            role="Unit director",
            is_active=True,
        )

    def _login(self, user, area):
        self.client.force_login(user)
        session = self.client.session
        session[PORTAL_AUTH_SESSION_KEY] = area
        session.save()

    def _all_rows(self):
        return four_cs_payout_rows(admin=True)

    def test_member_count_excludes_private_pay_and_defaults_to_active(self):
        rows = self._all_rows()
        names = {row["child"] for row in rows}
        self.assertIn("Sofia Martinez", names)
        self.assertIn("Miles Brooks", names)
        self.assertIn("Ethan Chen", names)
        self.assertIn("Ada Rivera", names)
        self.assertIn("Nia Waitlist", names)
        self.assertNotIn("Jordan Jacobs", names)
        self.assertFalse(child_is_4cs_member(self.private_child))

        bundle = four_cs_payout_report_bundle({}, admin=True)
        filtered_names = {row["child"] for row in bundle["report_rows"]}
        self.assertEqual(bundle["totals"]["member_count"], 4)
        self.assertNotIn("Nia Waitlist", filtered_names)
        self.assertNotIn("Jordan Jacobs", filtered_names)

    def test_copay_totals_by_cadence(self):
        rows = filter_four_cs_payout_rows(self._all_rows(), {"status": "Active"})
        totals = four_cs_payout_totals(rows)
        # Weekly: Sofia 25 + Ada 10 (after scholarship)
        self.assertEqual(totals["copay_weekly_plans_amount"], Decimal("35.00"))
        self.assertEqual(totals["weekly_count"], 2)
        # Bi-weekly: Miles 25 * 2
        self.assertEqual(totals["copay_biweekly_plans_amount"], Decimal("50.00"))
        self.assertEqual(totals["biweekly_count"], 1)
        today = timezone.localdate()
        month_weeks = billable_week_count_for_month(today.year, today.month) or 4
        self.assertEqual(totals["copay_monthly_plans_amount"], Decimal("20.00") * month_weeks)
        self.assertEqual(totals["monthly_count"], 1)

    def test_agency_totals_not_reduced_by_scholarship(self):
        rows = filter_four_cs_payout_rows(self._all_rows(), {"status": "Active"})
        by_name = {row["child"]: row for row in rows}
        self.assertEqual(by_name["Ada Rivera"]["weekly_copay_amount"], Decimal("10.00"))
        self.assertEqual(by_name["Ada Rivera"]["copay_cycle_amount"], Decimal("10.00"))
        self.assertEqual(by_name["Ada Rivera"]["copay_before_amount"], Decimal("25.00"))
        self.assertEqual(by_name["Ada Rivera"]["weekly_agency_amount"], Decimal("180.00"))
        self.assertEqual(by_name["Sofia Martinez"]["weekly_agency_amount"], Decimal("180.00"))

        totals = four_cs_payout_totals(rows)
        # Weekly agency: Sofia 180 + Ada 180
        self.assertEqual(totals["agency_weekly_plans_amount"], Decimal("360.00"))
        # Bi-weekly agency: Miles 180 * 2
        self.assertEqual(totals["agency_biweekly_plans_amount"], Decimal("360.00"))
        # Monthly agency: Ethan 95 * 4
        self.assertEqual(totals["agency_monthly_plans_amount"], Decimal("380.00"))
        # Weekly agency for all members
        self.assertEqual(totals["weekly_agency_all_amount"], Decimal("180.00") + Decimal("180.00") + Decimal("180.00") + Decimal("95.00"))

    def test_weekly_normalized_copay_for_all_members(self):
        rows = filter_four_cs_payout_rows(self._all_rows(), {"status": "Active"})
        by_name = {row["child"]: row for row in rows}
        self.assertEqual(by_name["Sofia Martinez"]["weekly_copay_amount"], Decimal("25.00"))
        self.assertEqual(by_name["Miles Brooks"]["weekly_copay_amount"], Decimal("25.00"))
        self.assertEqual(by_name["Ethan Chen"]["weekly_copay_amount"], Decimal("20.00"))
        self.assertEqual(by_name["Ada Rivera"]["weekly_copay_amount"], Decimal("10.00"))
        totals = four_cs_payout_totals(rows)
        self.assertEqual(totals["weekly_copay_all_amount"], Decimal("80.00"))

    def test_filters_change_rows_and_totals(self):
        rows = self._all_rows()
        weekly = filter_four_cs_payout_rows(rows, {"status": "Active", "copay_cadence": "weekly"})
        self.assertEqual({row["child"] for row in weekly}, {"Sofia Martinez", "Ada Rivera"})
        self.assertEqual(four_cs_payout_totals(weekly)["copay_weekly_plans_amount"], Decimal("35.00"))

        named = filter_four_cs_payout_rows(rows, {"status": "Active", "q": "miles"})
        self.assertEqual([row["child"] for row in named], ["Miles Brooks"])

        unit_26 = filter_four_cs_payout_rows(rows, {"status": "Active", "unit": "school-26"})
        self.assertEqual([row["child"] for row in unit_26], ["Ethan Chen"])

        scholarship_yes = filter_four_cs_payout_rows(rows, {"status": "Active", "scholarship": "yes"})
        self.assertEqual([row["child"] for row in scholarship_yes], ["Ada Rivera"])
        scholarship_no = filter_four_cs_payout_rows(rows, {"status": "Active", "scholarship": "no"})
        self.assertNotIn("Ada Rivera", {row["child"] for row in scholarship_no})

        waitlist = filter_four_cs_payout_rows(rows, {"status": "Waitlist"})
        self.assertEqual([row["child"] for row in waitlist], ["Nia Waitlist"])

        school = filter_four_cs_payout_rows(rows, {"status": "Active", "school": "School 26"})
        self.assertEqual([row["child"] for row in school], ["Ethan Chen"])

        grade = filter_four_cs_payout_rows(rows, {"status": "Active", "grade": "4th"})
        self.assertEqual([row["child"] for row in grade], ["Miles Brooks"])

    def test_extra_private_plan_does_not_change_4cs_cadence(self):
        PortalChildBillingPlan.objects.create(
            child=self.biweekly_child,
            description="Before-care private",
            billing_plan="Weekly",
            billing_kind="private",
            billing_amount=Decimal("40.00"),
            sort_order=1,
        )
        PortalChildBillingPlan.objects.create(
            child=self.biweekly_child,
            description="After-care copay",
            billing_plan="Bi-weekly",
            billing_kind="4cs",
            billing_amount=Decimal("50.00"),
            sort_order=2,
        )
        row = next(item for item in self._all_rows() if item["child"] == "Miles Brooks")
        self.assertEqual(row["copay_cadence"], "biweekly")
        self.assertEqual(row["copay_cycle_amount"], Decimal("50.00"))

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_admin_page_shows_cards_rows_totals_and_howto(self):
        self._login(self.admin, "admin")
        hub = self.client.get(reverse("portal_admin_page", kwargs={"page": "reports"}))
        self.assertContains(hub, "4Cs expected amounts")
        self.assertContains(hub, reverse("portal_admin_four_cs_payout_report"))

        page = self.client.get(reverse("portal_admin_four_cs_payout_report"))
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, "How to use this page")
        self.assertContains(page, "Sofia Martinez")
        self.assertContains(page, "Miles Brooks")
        self.assertContains(page, "Ethan Chen")
        self.assertContains(page, "Ada Rivera")
        self.assertNotContains(page, "Nia Waitlist")
        self.assertNotContains(page, "Jordan Jacobs")
        self.assertContains(page, 'id="four-cs-member-count">4</span>')
        self.assertContains(page, "$80.00")
        self.assertContains(page, "Copay I should collect")
        self.assertContains(page, "Weekly copay for all 4Cs members")
        self.assertContains(page, reverse("portal_admin_family_billing", kwargs={"family_slug": "martinez"}))

        weekly = self.client.get(reverse("portal_admin_four_cs_payout_report"), {"copay_cadence": "weekly"})
        self.assertContains(weekly, "Sofia Martinez")
        self.assertContains(weekly, "Ada Rivera")
        self.assertNotContains(weekly, "Miles Brooks")
        self.assertNotContains(weekly, "Ethan Chen")

        csv_response = self.client.get(reverse("portal_admin_four_cs_payout_report"), {"format": "csv"})
        self.assertEqual(csv_response.status_code, 200)
        self.assertIn("text/csv", csv_response["Content-Type"])
        self.assertIn(b"Sofia Martinez", csv_response.content)
        self.assertIn(b"Total (4 members)", csv_response.content)

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_staff_page_is_unit_scoped_and_on_reports_hub(self):
        self._login(self.staff, "staff")
        hub = self.client.get(reverse("portal_staff_page", kwargs={"page": "reports"}))
        self.assertContains(hub, "4Cs expected amounts")
        self.assertContains(hub, reverse("portal_staff_four_cs_payout_report"))

        page = self.client.get(reverse("portal_staff_four_cs_payout_report"))
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, "Sofia Martinez")
        self.assertContains(page, "Miles Brooks")
        self.assertNotContains(page, "Ethan Chen")
        self.assertContains(page, reverse("portal_staff_family_billing", kwargs={"family_slug": "martinez"}))
