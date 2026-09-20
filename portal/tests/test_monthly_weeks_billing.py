from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from portal.admin_config import save_scholarship_fund
from portal.agency_weeks import (
    billable_week_count_for_month,
    friday_of_program_week,
    get_program_calendar,
    group_program_weeks_by_month,
    monthly_charge_for_date,
)
from portal.billing_services import (
    monthly_schedule_rows,
    run_due_plan_charges,
    update_child_billing_plan,
)
from portal.models import (
    PortalChild,
    PortalFamily,
    PortalLedgerEntry,
    PortalScholarshipAssignment,
    PortalStaffAccount,
    PortalUnit,
)
from portal.staff_auth import PORTAL_AUTH_SESSION_KEY


class MonthlyWeeksBillingTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.unit = PortalUnit.objects.create(slug="school-18", name="School 18", is_active=True)
        self.family = PortalFamily.objects.create(
            unit=self.unit, slug="jacobs", name="Jacobs", billing_type="Private pay", status="Active"
        )
        self.child = PortalChild.objects.create(
            family=self.family, name="Jordan Jacobs", is_active=True, billing_plan="Weekly"
        )
        self.fund = save_scholarship_fund({"name": "YEA General Scholarship", "description": "Need-based"})
        self.admin = User.objects.create_user(username="staff:portaladmin", password="AdminPass123")
        PortalStaffAccount.objects.create(
            user=self.admin,
            unit=self.unit,
            display_name="Portal Admin",
            role="Portal admin",
            all_units_access=True,
            is_active=True,
        )
        calendar = get_program_calendar()
        calendar.program_start = date(2026, 9, 1)
        calendar.days_off = []
        calendar.half_days = []
        calendar.save()

    def _login_admin(self):
        self.client.force_login(self.admin)
        session = self.client.session
        session[PORTAL_AUTH_SESSION_KEY] = "admin"
        session.save()

    def test_september_2026_has_four_billable_weeks(self):
        self.assertEqual(billable_week_count_for_month(2026, 9), 4)
        self.assertEqual(billable_week_count_for_month(2026, 10), 5)

    def test_four_week_month_charges_four_times_weekly(self):
        today = date(2026, 9, 9)
        with patch("portal.billing_services.timezone.localdate", return_value=today):
            _child, posted = update_child_billing_plan(
                self.family,
                "Jordan Jacobs",
                "Monthly",
                amount="70.00",
                billing_type="Private pay",
                auto_charge=True,
                next_charge_date=today,
                charge_month_day=today.day,
            )
        self.assertEqual(len(posted), 1)
        charge = PortalLedgerEntry.objects.get(family=self.family, entry_type="charge")
        self.assertEqual(charge.amount, Decimal("280.00"))
        self.assertEqual(charge.date, today)
        self.assertIn("September 2026", charge.description)
        self.assertIn("4 weeks", charge.description)
        self.child.refresh_from_db()
        self.assertEqual(self.child.weekly_rate, Decimal("70.00"))
        self.assertEqual(self.child.next_charge_date, date(2026, 10, 9))

    def test_five_week_month_charges_five_times_weekly(self):
        today = date(2026, 10, 9)
        with patch("portal.billing_services.timezone.localdate", return_value=today):
            _child, posted = update_child_billing_plan(
                self.family,
                "Jordan Jacobs",
                "Monthly",
                amount="70.00",
                billing_type="Private pay",
                auto_charge=True,
                next_charge_date=today,
                charge_month_day=today.day,
            )
        self.assertEqual(len(posted), 1)
        charge = PortalLedgerEntry.objects.get(family=self.family, entry_type="charge")
        self.assertEqual(charge.amount, Decimal("350.00"))
        self.assertEqual(charge.date, today)
        self.assertIn("October 2026", charge.description)
        self.assertIn("5 weeks", charge.description)

    def test_scholarship_reduces_family_pays_on_each_month(self):
        rows = monthly_schedule_rows(
            Decimal("70.00"),
            scholarship=type(
                "S",
                (),
                {"full_rate": Decimal("70.00"), "parent_amount": Decimal("50.00")},
            )(),
            on_date=date(2026, 9, 9),
        )
        by_label = {row["label"]: row for row in rows}
        self.assertEqual(by_label["September 2026"]["week_count"], 4)
        self.assertEqual(by_label["September 2026"]["amount"], "280.00")
        self.assertEqual(by_label["September 2026"]["family_pays"], "200.00")
        self.assertTrue(by_label["September 2026"]["has_scholarship"])
        self.assertEqual(by_label["October 2026"]["week_count"], 5)
        self.assertEqual(by_label["October 2026"]["amount"], "350.00")
        self.assertEqual(by_label["October 2026"]["family_pays"], "250.00")
        self.assertIn("9/28/26–10/2/26", by_label["October 2026"]["week_labels"])

    def test_closed_week_is_not_billed(self):
        calendar = get_program_calendar()
        calendar.days_off = [
            "2026-10-05",
            "2026-10-06",
            "2026-10-07",
            "2026-10-08",
            "2026-10-09",
        ]
        calendar.save()
        self.assertEqual(billable_week_count_for_month(2026, 10), 4)
        amount, count = monthly_charge_for_date(Decimal("70.00"), date(2026, 10, 9))
        self.assertEqual(count, 4)
        self.assertEqual(amount, Decimal("280.00"))

    def test_week_of_sep_28_to_oct_2_is_october_week_1(self):
        span = (date(2026, 9, 28), date(2026, 10, 2))
        self.assertEqual(friday_of_program_week(*span), date(2026, 10, 2))
        groups = group_program_weeks_by_month()
        september = groups.get((2026, 9), [])
        october = groups.get((2026, 10), [])
        self.assertNotIn(span, september)
        self.assertEqual(october[0], span)
        self.assertEqual(len(september), 4)
        self.assertEqual(len(october), 5)

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_plans_card_lists_months_and_amounts(self):
        self.child.billing_plan = "Monthly"
        self.child.billing_amount = Decimal("70.00")
        self.child.weekly_rate = Decimal("70.00")
        self.child.save(update_fields=["billing_plan", "billing_amount", "weekly_rate"])
        self._login_admin()
        page = self.client.get(reverse("portal_admin_family_plans", kwargs={"family_slug": "jacobs"}))
        self.assertContains(page, "Weekly rate ($)")
        self.assertContains(page, "Amount due each month")
        self.assertContains(page, "September 2026")
        self.assertContains(page, "October 2026")
        self.assertContains(page, "5 × $70.00 = $350.00")
        self.assertContains(page, "4 × $70.00 = $280.00")
        self.assertContains(page, "month of its Friday")
        self.assertContains(page, "9/28/26–10/2/26")
        self.assertContains(page, "first week of October")

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_plans_card_lists_scholarship_family_pays(self):
        self.child.billing_plan = "Monthly"
        self.child.billing_amount = Decimal("70.00")
        self.child.weekly_rate = Decimal("70.00")
        self.child.save(update_fields=["billing_plan", "billing_amount", "weekly_rate"])
        PortalScholarshipAssignment.objects.create(
            child=self.child,
            fund=self.fund,
            full_rate=Decimal("70.00"),
            parent_amount=Decimal("50.00"),
            status="Active",
        )
        self._login_admin()
        page = self.client.get(reverse("portal_admin_family_plans", kwargs={"family_slug": "jacobs"}))
        self.assertContains(page, "Family pays")
        self.assertContains(page, "$250.00")
        self.assertContains(page, "$200.00")
        self.assertContains(page, "5 × $70.00 = $350.00")
        self.assertContains(page, "4 × $70.00 = $280.00")

    def test_weekly_and_biweekly_still_post_flat_amount(self):
        today = date(2026, 9, 9)
        with patch("portal.billing_services.timezone.localdate", return_value=today):
            update_child_billing_plan(
                self.family,
                "Jordan Jacobs",
                "Weekly",
                amount="70.00",
                billing_type="Private pay",
                auto_charge=True,
                next_charge_date=today,
                charge_weekday=today.weekday(),
            )
        weekly_charge = PortalLedgerEntry.objects.get(family=self.family, entry_type="charge")
        self.assertEqual(weekly_charge.amount, Decimal("70.00"))
        PortalLedgerEntry.objects.filter(family=self.family).delete()
        self.family.balance = Decimal("0")
        self.family.save(update_fields=["balance"])
        self.child.last_auto_charge_date = None
        self.child.next_charge_date = None
        self.child.save(update_fields=["last_auto_charge_date", "next_charge_date"])
        sibling = PortalChild.objects.create(
            family=self.family, name="Casey Jacobs", is_active=True, billing_plan="Weekly"
        )
        with patch("portal.billing_services.timezone.localdate", return_value=today):
            update_child_billing_plan(
                self.family,
                sibling.name,
                "Bi-weekly",
                amount="140.00",
                billing_type="Private pay",
                auto_charge=True,
                next_charge_date=today,
                charge_weekday=today.weekday(),
            )
        biweekly_charge = PortalLedgerEntry.objects.get(family=self.family, entry_type="charge")
        self.assertEqual(biweekly_charge.amount, Decimal("140.00"))

    def test_later_month_uses_that_month_amount_not_stale_flat(self):
        september = date(2026, 9, 9)
        with patch("portal.billing_services.timezone.localdate", return_value=september):
            update_child_billing_plan(
                self.family,
                "Jordan Jacobs",
                "Monthly",
                amount="70.00",
                billing_type="Private pay",
                auto_charge=True,
                next_charge_date=september,
                charge_month_day=september.day,
            )
        self.assertEqual(
            PortalLedgerEntry.objects.get(family=self.family, entry_type="charge").amount,
            Decimal("280.00"),
        )
        october = date(2026, 10, 9)
        with patch("portal.billing_services.timezone.localdate", return_value=october):
            posted = run_due_plan_charges(today=october, child=self.child)
        self.assertEqual(len(posted), 1)
        amounts = list(
            PortalLedgerEntry.objects.filter(family=self.family, entry_type="charge")
            .order_by("date")
            .values_list("amount", flat=True)
        )
        self.assertEqual(amounts, [Decimal("280.00"), Decimal("350.00")])
