from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from portal.agency_weeks import (
    automatic_charge_name,
    billable_week_count_for_month,
    cc_week_number_for_span,
    get_program_calendar,
    monday_owned_week_count,
    monthly_charge_details,
    numbered_weeks_for_month,
    save_program_week_override,
    sync_program_weeks,
)
from portal.billing_services import monthly_schedule_rows, update_child_billing_plan
from portal.models import (
    PortalChild,
    PortalFamily,
    PortalLedgerEntry,
    PortalStaffAccount,
    PortalUnit,
)
from portal.staff_auth import PORTAL_AUTH_SESSION_KEY


class ProgramWeekNumberingTests(TestCase):
    def setUp(self):
        calendar = get_program_calendar()
        calendar.program_start = date(2026, 9, 8)
        calendar.days_off = []
        calendar.half_days = []
        calendar.save()
        self.calendar = calendar
        self.weeks = sync_program_weeks(calendar)

    def test_start_sept_8_makes_short_first_week_cc_wk_1(self):
        first = self.weeks[0]
        self.assertEqual(first.week_number, 1)
        self.assertEqual(first.week_start, date(2026, 9, 8))
        self.assertEqual(first.week_end, date(2026, 9, 11))
        self.assertEqual(cc_week_number_for_span(date(2026, 9, 8), date(2026, 9, 11)), 1)

    def test_october_2026_is_five_friday_weeks_not_four_mondays(self):
        self.assertEqual(monday_owned_week_count(2026, 10), 4)
        self.assertEqual(billable_week_count_for_month(2026, 10), 5)
        october = numbered_weeks_for_month(2026, 10)
        numbers = [week.week_number for week in october]
        self.assertEqual(numbers, [4, 5, 6, 7, 8])
        self.assertEqual(october[0].week_start, date(2026, 9, 28))
        self.assertEqual(october[0].week_end, date(2026, 10, 2))
        self.assertEqual(
            [ (week.week_start, week.week_end) for week in october ],
            [
                (date(2026, 9, 28), date(2026, 10, 2)),
                (date(2026, 10, 5), date(2026, 10, 9)),
                (date(2026, 10, 12), date(2026, 10, 16)),
                (date(2026, 10, 19), date(2026, 10, 23)),
                (date(2026, 10, 26), date(2026, 10, 30)),
            ],
        )

    def test_staff_can_override_week_number_and_span(self):
        first = self.weeks[0]
        save_program_week_override(
            {
                "week_id": first.pk,
                "week_number": "1",
                "week_start": "2026-09-08",
                "week_end": "2026-09-10",
            }
        )
        first.refresh_from_db()
        self.assertEqual(first.week_end, date(2026, 9, 10))
        self.assertTrue(first.span_overridden)
        save_program_week_override(
            {
                "week_id": first.pk,
                "week_number": "9",
                "week_start": "2026-09-08",
                "week_end": "2026-09-10",
            }
        )
        first.refresh_from_db()
        self.assertEqual(first.week_number, 9)
        self.assertTrue(first.number_overridden)

    def test_charge_names_use_cc_week_labels(self):
        self.assertEqual(
            automatic_charge_name("Weekly", "tuition", week_numbers=[1]),
            "CC WK 1 - weekly charge",
        )
        self.assertEqual(
            automatic_charge_name("Weekly", "4cs_copay", week_numbers=[1]),
            "CC WK 1 - weekly 4Cs Copay",
        )
        self.assertEqual(
            automatic_charge_name("Monthly", "tuition", week_numbers=[4, 5, 6, 7, 8], month_date=date(2026, 10, 9)),
            "October monthly charge for Wk 4, 5, 6, 7, 8",
        )


class OctoberMonthlyFiveWeekChargeTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.unit = PortalUnit.objects.create(slug="school-18", name="School 18", is_active=True)
        self.family = PortalFamily.objects.create(
            unit=self.unit, slug="jacobs", name="Jacobs", billing_type="Private pay", status="Active"
        )
        self.child = PortalChild.objects.create(
            family=self.family, name="Jordan Jacobs", is_active=True, billing_plan="Weekly"
        )
        calendar = get_program_calendar()
        calendar.program_start = date(2026, 9, 8)
        calendar.days_off = []
        calendar.half_days = []
        calendar.save()
        sync_program_weeks(calendar)

    def test_october_preview_and_posted_charge_are_five_weeks(self):
        details = monthly_charge_details(Decimal("70.00"), date(2026, 10, 9))
        self.assertEqual(details["week_count"], 5)
        self.assertEqual(details["amount"], Decimal("350.00"))
        self.assertEqual(details["week_numbers"], [4, 5, 6, 7, 8])
        self.assertEqual(details["charge_name"], "October monthly charge for Wk 4, 5, 6, 7, 8")

        rows = monthly_schedule_rows(Decimal("70.00"), on_date=date(2026, 10, 9))
        october = next(row for row in rows if row["label"] == "October 2026")
        self.assertEqual(october["week_count"], 5)
        self.assertEqual(october["amount"], "350.00")
        self.assertEqual(october["week_numbers"], [4, 5, 6, 7, 8])
        self.assertEqual(october["charge_name"], "October monthly charge for Wk 4, 5, 6, 7, 8")

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
        self.assertEqual(charge.description, "October monthly charge for Wk 4, 5, 6, 7, 8")
        self.assertNotIn("4 weeks", charge.description)


class ProgramCalendarWeekUiTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.unit = PortalUnit.objects.create(slug="school-18", name="School 18", is_active=True)
        self.admin = User.objects.create_user(username="staff:yeaadmin", password="AdminPass123")
        PortalStaffAccount.objects.create(
            user=self.admin,
            unit=self.unit,
            display_name="Portal Admin",
            role="Portal admin",
            all_units_access=True,
            is_active=True,
        )

    def _login(self):
        self.client.force_login(self.admin)
        session = self.client.session
        session[PORTAL_AUTH_SESSION_KEY] = "admin"
        session.save()

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_calendar_shows_cc_week_numbers_after_start_date_save(self):
        self._login()
        response = self.client.post(
            reverse("portal_admin_program_calendar_save"),
            {
                "program_start": "2026-09-08",
                "days_off": "",
                "half_days": "",
                "month": "2026-09",
            },
        )
        self.assertEqual(response.status_code, 302)
        page = self.client.get(
            reverse("portal_admin_page", kwargs={"page": "program-calendar"}),
            {"month": "2026-09"},
        )
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, "CC WK 1")
        self.assertContains(page, "CC WK 2")
        self.assertContains(page, "id=\"program-week-calendar\"")
        self.assertContains(page, "id=\"program-week-table\"")
        self.assertContains(page, "Edit a week")


class WeeklyChargeNameTests(TestCase):
    def setUp(self):
        self.unit = PortalUnit.objects.create(slug="school-18", name="School 18", is_active=True)
        self.family = PortalFamily.objects.create(
            unit=self.unit, slug="jacobs", name="Jacobs", billing_type="Private pay", status="Active"
        )
        self.child = PortalChild.objects.create(
            family=self.family, name="Jordan Jacobs", is_active=True, billing_plan="Weekly"
        )
        calendar = get_program_calendar()
        calendar.program_start = date(2026, 9, 8)
        calendar.days_off = []
        calendar.save()
        sync_program_weeks(calendar)

    def test_weekly_private_pay_posts_cc_week_name(self):
        today = date(2026, 9, 10)
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
        charge = PortalLedgerEntry.objects.get(family=self.family, entry_type="charge")
        self.assertEqual(charge.amount, Decimal("70.00"))
        self.assertEqual(charge.description, "CC WK 1 - weekly charge")
