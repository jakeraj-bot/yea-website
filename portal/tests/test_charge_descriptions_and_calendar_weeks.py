from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from portal.agency_services import save_agency_member
from portal.agency_weeks import (
    automatic_charge_name,
    get_program_calendar,
    parent_charge_periods,
    parent_period_for_biweekly_from_date,
    sync_program_weeks,
)
from portal.billing_services import (
    rewrite_auto_charge_descriptions,
    update_child_billing_plan,
)
from portal.models import (
    PortalChild,
    PortalFamily,
    PortalLedgerEntry,
    PortalStaffAccount,
    PortalUnit,
)
from portal.staff_auth import PORTAL_AUTH_SESSION_KEY


def _start_program(start=date(2026, 9, 8)):
    calendar = get_program_calendar()
    calendar.program_start = start
    calendar.days_off = []
    calendar.half_days = []
    calendar.save()
    sync_program_weeks(calendar)
    return calendar


class AutomaticChargeDescriptionTemplateTests(TestCase):
    def setUp(self):
        _start_program()
        self.unit = PortalUnit.objects.create(slug="school-18", name="School 18", is_active=True)
        self.family = PortalFamily.objects.create(
            unit=self.unit, slug="jacobs", name="Jacobs", billing_type="Private pay", status="Active"
        )
        self.child = PortalChild.objects.create(
            family=self.family, name="Jordan Jacobs", is_active=True, billing_plan="Weekly"
        )

    def test_private_weekly_template(self):
        today = date(2026, 10, 8)
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
                description="After care",
            )
        charge = PortalLedgerEntry.objects.get(family=self.family, entry_type="charge")
        self.assertEqual(
            charge.description,
            "CC WK 5 - Weekly Charge - for (10/5/2026 - 10/9/2026)",
        )
        self.assertNotIn("After care", charge.description)

    def test_private_biweekly_includes_both_weeks_and_ranges(self):
        expected = (
            "CC WK 5 & 6 - Bi-Weekly Charge - for (10/5/2026 - 10/9/2026) "
            "and (10/12/2026 - 10/16/2026)"
        )
        self.assertEqual(
            automatic_charge_name(
                "Bi-weekly",
                "tuition",
                week_numbers=[5, 6],
                week_spans=[
                    (date(2026, 10, 5), date(2026, 10, 9)),
                    (date(2026, 10, 12), date(2026, 10, 16)),
                ],
            ),
            expected,
        )
        today = date(2026, 10, 8)
        with patch("portal.billing_services.timezone.localdate", return_value=today):
            update_child_billing_plan(
                self.family,
                "Jordan Jacobs",
                "Bi-weekly",
                amount="140.00",
                billing_type="Private pay",
                auto_charge=True,
                next_charge_date=today,
                charge_weekday=today.weekday(),
                description="After care",
            )
        charge = PortalLedgerEntry.objects.get(family=self.family, entry_type="charge")
        self.assertEqual(charge.description, expected)
        self.assertIn("CC WK 5 & 6", charge.description)
        self.assertIn("10/5/2026", charge.description)
        self.assertIn("10/12/2026", charge.description)
        self.assertNotIn("After care", charge.description)

    def test_private_monthly_template(self):
        expected = "October - Monthly Charge - for CC WK 4, 5, 6, 7, 8"
        today = date(2026, 10, 9)
        with patch("portal.billing_services.timezone.localdate", return_value=today):
            update_child_billing_plan(
                self.family,
                "Jordan Jacobs",
                "Monthly",
                amount="70.00",
                billing_type="Private pay",
                auto_charge=True,
                next_charge_date=today,
                charge_month_day=today.day,
                description="After care",
            )
        charge = PortalLedgerEntry.objects.get(family=self.family, entry_type="charge")
        self.assertEqual(charge.description, expected)
        self.assertEqual(charge.amount, Decimal("350.00"))
        self.assertNotIn("After care", charge.description)


class FourCsChargeDescriptionTemplateTests(TestCase):
    def setUp(self):
        _start_program()
        self.unit = PortalUnit.objects.create(slug="school-18", name="School 18", is_active=True)
        self.family = PortalFamily.objects.create(
            unit=self.unit, slug="rivera", name="Rivera", billing_type="4Cs", status="Active"
        )
        self.child = PortalChild.objects.create(
            family=self.family, name="Ada Rivera", is_active=True, billing_plan="Weekly"
        )
        self.profile = save_agency_member(
            self.unit,
            "rivera",
            "Ada Rivera",
            "Passaic County 4Cs",
            auth_start=date(2026, 9, 1),
            auth_end=date(2026, 10, 30),
            daily_copay="5.30",
            daily_agency_rate="22.00",
        )

    def test_4cs_weekly_template(self):
        self.assertEqual(
            automatic_charge_name(
                "Weekly",
                "4cs_copay",
                week_numbers=[5],
                week_spans=[(date(2026, 10, 5), date(2026, 10, 9))],
            ),
            "CC WK 5 - 4Cs Copay Weekly Charge - for (10/5/2026 - 10/9/2026)",
        )

    def test_4cs_biweekly_posts_both_weeks(self):
        expected = (
            "CC WK 5 & 6 - 4Cs Copay Bi-Weekly Charge - for (10/5/2026 - 10/9/2026) "
            "and (10/12/2026 - 10/16/2026)"
        )
        period = parent_period_for_biweekly_from_date(self.profile, "Bi-weekly", date(2026, 10, 5))
        self.assertEqual(period["week_numbers"], [5, 6])
        self.assertEqual(len(period["week_spans"]), 2)
        self.assertEqual(period["label"], expected)
        today = date(2026, 10, 8)
        with patch("portal.billing_services.timezone.localdate", return_value=today):
            _child, posted = update_child_billing_plan(
                self.family,
                "Ada Rivera",
                "Bi-weekly",
                billing_type="4Cs",
                auto_charge=True,
                next_charge_date=today,
                description="After care",
            )
        self.assertEqual(len(posted), 1)
        charge = PortalLedgerEntry.objects.get(family=self.family, entry_type="charge")
        self.assertEqual(charge.description, expected)
        self.assertIn(" and (", charge.description)
        self.assertNotIn("After care", charge.description)
        self.assertEqual(charge.amount, Decimal("53.00"))

    def test_4cs_monthly_template(self):
        expected = "October - 4Cs Copay Monthly Charge - for CC WK 4, 5, 6, 7, 8"
        self.assertEqual(
            automatic_charge_name(
                "Monthly",
                "4cs_copay",
                week_numbers=[4, 5, 6, 7, 8],
                month_date=date(2026, 10, 9),
            ),
            expected,
        )
        periods = parent_charge_periods(self.profile, "Monthly")
        october = next(period for period in periods if period["label"].startswith("October"))
        self.assertEqual(october["label"], expected)
        self.assertEqual(october["week_numbers"], [4, 5, 6, 7, 8])

    def test_4cs_agency_uses_same_week_structure(self):
        self.assertEqual(
            automatic_charge_name(
                "Weekly",
                "4cs_agency",
                week_numbers=[5],
                week_spans=[(date(2026, 10, 5), date(2026, 10, 9))],
            ),
            "CC WK 5 - 4Cs Agency Weekly Charge - for (10/5/2026 - 10/9/2026)",
        )
        self.assertEqual(
            automatic_charge_name(
                "Bi-weekly",
                "4cs_agency",
                week_numbers=[5, 6],
                week_spans=[
                    (date(2026, 10, 5), date(2026, 10, 9)),
                    (date(2026, 10, 12), date(2026, 10, 16)),
                ],
            ),
            "CC WK 5 & 6 - 4Cs Agency Bi-Weekly Charge - for (10/5/2026 - 10/9/2026) "
            "and (10/12/2026 - 10/16/2026)",
        )
        self.assertEqual(
            automatic_charge_name(
                "Monthly",
                "4cs_agency",
                week_numbers=[4, 5, 6, 7, 8],
                month_date=date(2026, 10, 9),
            ),
            "October - 4Cs Agency Monthly Charge - for CC WK 4, 5, 6, 7, 8",
        )


class Oct15ChargeDescriptionRewriteTests(TestCase):
    def setUp(self):
        _start_program()
        self.unit = PortalUnit.objects.create(slug="school-18", name="School 18", is_active=True)
        self.family = PortalFamily.objects.create(
            unit=self.unit, slug="jacobs", name="Jacobs", billing_type="Private pay", status="Active"
        )
        self.child = PortalChild.objects.create(
            family=self.family, name="Jordan Jacobs", is_active=True, billing_plan="Bi-weekly"
        )

    def test_rewrites_oct15_auto_charges_only(self):
        auto = PortalLedgerEntry.objects.create(
            family=self.family,
            child_name="Jordan Jacobs",
            date=date(2026, 10, 15),
            entry_type="charge",
            description="CC WK 6 - bi-weekly charge — After care",
            amount=Decimal("140.00"),
            is_manual=False,
        )
        payment = PortalLedgerEntry.objects.create(
            family=self.family,
            child_name="Jordan Jacobs",
            date=date(2026, 10, 15),
            entry_type="payment",
            description="Cash payment",
            amount=Decimal("-50.00"),
            is_manual=True,
        )
        older = PortalLedgerEntry.objects.create(
            family=self.family,
            child_name="Jordan Jacobs",
            date=date(2026, 10, 8),
            entry_type="charge",
            description="CC WK 5 - weekly charge",
            amount=Decimal("70.00"),
            is_manual=False,
        )
        membership = PortalLedgerEntry.objects.create(
            family=self.family,
            child_name="Jordan Jacobs",
            date=date(2026, 10, 15),
            entry_type="charge",
            description="Membership fee ($20.00) — Jordan Jacobs",
            amount=Decimal("20.00"),
            is_manual=False,
        )
        updated = rewrite_auto_charge_descriptions(on_date=date(2026, 10, 15))
        self.assertEqual(len(updated), 1)
        auto.refresh_from_db()
        payment.refresh_from_db()
        older.refresh_from_db()
        membership.refresh_from_db()
        self.assertEqual(auto.amount, Decimal("140.00"))
        self.assertEqual(
            auto.description,
            "CC WK 6 & 7 - Bi-Weekly Charge - for (10/12/2026 - 10/16/2026) "
            "and (10/19/2026 - 10/23/2026)",
        )
        self.assertEqual(payment.description, "Cash payment")
        self.assertEqual(older.description, "CC WK 5 - weekly charge")
        self.assertEqual(membership.description, "Membership fee ($20.00) — Jordan Jacobs")


class CalendarWeekNumberUiTests(TestCase):
    def setUp(self):
        _start_program()
        User = get_user_model()
        self.unit = PortalUnit.objects.create(slug="school-18", name="School 18", is_active=True)
        self.family = PortalFamily.objects.create(unit=self.unit, slug="rivera", name="Rivera")
        self.child = PortalChild.objects.create(
            family=self.family, name="Ada Rivera", unit=self.unit, is_active=True
        )
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
    def test_attendance_calendar_html_has_cc_wk_side_column(self):
        self._login()
        page = self.client.get(
            reverse("portal_admin_family_attendance", kwargs={"family_slug": "rivera"}),
            {"id": self.family.pk, "child_id": self.child.pk, "month": "2026-10"},
        )
        self.assertEqual(page.status_code, 200)
        html = page.content.decode()
        self.assertIn("CC WK", html)
        self.assertIn('class="portal-program-week-cc"', html)
        self.assertIn(">Week</th>", html)

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_activity_calendar_html_has_cc_wk_side_column(self):
        self._login()
        page = self.client.get(reverse("portal_admin_activity_calendar"), {"month": "2026-10"})
        self.assertEqual(page.status_code, 200)
        html = page.content.decode()
        self.assertIn("CC WK", html)
        self.assertIn('class="portal-program-week-cc"', html)
        self.assertIn(">Week</th>", html)

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_program_calendar_week_label_is_side_column_not_under_days(self):
        self._login()
        page = self.client.get(
            reverse("portal_admin_page", kwargs={"page": "program-calendar"}),
            {"month": "2026-10"},
        )
        self.assertEqual(page.status_code, 200)
        html = page.content.decode()
        self.assertIn("CC WK 5", html)
        self.assertIn('class="portal-program-week-cc"', html)
        self.assertNotIn("portal-program-week-tag", html)
        self.assertIn('id="program-week-calendar"', html)
