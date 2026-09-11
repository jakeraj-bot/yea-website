from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from portal.agency_services import save_agency_member
from portal.agency_weeks import (
    FOUR_CS_WEEKLY_POST_WEEKDAY,
    apply_week_includes,
    get_program_calendar,
    mark_agency_week_received,
    most_recent_thursday,
    next_thursday_after,
    next_thursday_on_or_after,
    next_biweekly_charge_date,
    parent_charge_periods,
    parent_period_for_biweekly_from_date,
    parent_period_for_weekly_thursday_post,
    period_parent_total,
    school_weeks_in_range,
    sync_contract_weeks,
    week_monday_covered_by_thursday,
    weekly_from_daily,
)
from portal.models import (
    PortalAgencyProfile,
    PortalChild,
    PortalFamily,
    PortalLedgerEntry,
    PortalProgramCalendar,
    PortalStaffAccount,
    PortalUnit,
)
from portal.billing_services import run_due_plan_charges, update_child_billing_plan
from portal.staff_auth import PORTAL_AUTH_SESSION_KEY


class SchoolWeekGenerationTests(TestCase):
    def test_september_2026_contract_lists_clipped_school_weeks(self):
        weeks = school_weeks_in_range(date(2026, 9, 1), date(2026, 9, 30))
        self.assertEqual(
            weeks,
            [
                (date(2026, 9, 1), date(2026, 9, 4)),
                (date(2026, 9, 7), date(2026, 9, 11)),
                (date(2026, 9, 14), date(2026, 9, 18)),
                (date(2026, 9, 21), date(2026, 9, 25)),
                (date(2026, 9, 28), date(2026, 9, 30)),
            ],
        )

    def test_weekend_start_jumps_to_next_monday(self):
        weeks = school_weeks_in_range(date(2026, 9, 5), date(2026, 9, 11))
        self.assertEqual(weeks, [(date(2026, 9, 7), date(2026, 9, 11))])


class WeeklyRateAndOverrideTests(TestCase):
    def setUp(self):
        self.unit = PortalUnit.objects.create(slug="school-18", name="School 18", is_active=True)
        self.family = PortalFamily.objects.create(
            unit=self.unit, slug="rivera", name="Rivera", billing_type="4Cs"
        )
        self.child = PortalChild.objects.create(family=self.family, name="Ada Rivera", is_active=True)

    def test_weekly_is_daily_times_five_unless_overridden(self):
        self.assertEqual(weekly_from_daily(Decimal("5.30")), Decimal("26.50"))
        profile = save_agency_member(
            self.unit,
            "rivera",
            "Ada Rivera",
            "Passaic County 4Cs",
            auth_start=date(2026, 9, 1),
            auth_end=date(2026, 9, 11),
            daily_agency_rate="22.00",
            daily_copay="5.30",
        )
        self.assertEqual(profile.weekly_agency_rate, Decimal("110.00"))
        self.assertEqual(profile.weekly_copay, Decimal("26.50"))
        self.assertFalse(profile.weekly_copay_overridden)
        weeks = list(profile.contract_weeks.order_by("week_start"))
        self.assertEqual(len(weeks), 2)
        self.assertEqual(weeks[0].parent_amount, Decimal("26.50"))
        self.assertEqual(weeks[0].agency_amount, Decimal("110.00"))

    def test_per_week_override_survives_rate_change_for_existing_weeks(self):
        profile = save_agency_member(
            self.unit,
            "rivera",
            "Ada Rivera",
            "Passaic County 4Cs",
            auth_start=date(2026, 9, 1),
            auth_end=date(2026, 9, 18),
            daily_copay="5.30",
            daily_agency_rate="22.00",
        )
        second = profile.contract_weeks.get(week_start=date(2026, 9, 7))
        second.parent_amount = Decimal("0.00")
        second.parent_overridden = True
        second.save()
        profile.weekly_copay = Decimal("30.00")
        profile.weekly_copay_overridden = True
        profile.save()
        sync_contract_weeks(profile)
        second.refresh_from_db()
        first = profile.contract_weeks.get(week_start=date(2026, 9, 1))
        self.assertEqual(second.parent_amount, Decimal("0.00"))
        self.assertTrue(second.parent_overridden)
        self.assertEqual(first.parent_amount, Decimal("30.00"))


class FourCsPlanCalculationTests(TestCase):
    def setUp(self):
        self.unit = PortalUnit.objects.create(slug="school-18", name="School 18", is_active=True)
        self.family = PortalFamily.objects.create(
            unit=self.unit, slug="rivera", name="Rivera", billing_type="4Cs", status="Active"
        )
        self.child = PortalChild.objects.create(
            family=self.family, name="Ada Rivera", is_active=True, billing_plan="Bi-weekly"
        )
        self.profile = save_agency_member(
            self.unit,
            "rivera",
            "Ada Rivera",
            "Passaic County 4Cs",
            auth_start=date(2026, 9, 1),
            auth_end=date(2026, 9, 25),
            daily_copay="5.30",
            daily_agency_rate="22.00",
        )

    def test_biweekly_sums_parent_weeks_only(self):
        zero_week = self.profile.contract_weeks.get(week_start=date(2026, 9, 21))
        zero_week.parent_amount = Decimal("0.00")
        zero_week.parent_overridden = True
        zero_week.save()
        periods = parent_charge_periods(self.profile, "Bi-weekly")
        self.assertEqual(len(periods), 2)
        self.assertEqual(periods[0]["amount"], Decimal("53.00"))
        self.assertEqual(periods[1]["amount"], Decimal("26.50"))
        self.assertEqual(period_parent_total(periods[0]["weeks"]), Decimal("53.00"))
        for week in self.profile.contract_weeks.all():
            self.assertEqual(week.agency_amount, Decimal("110.00"))

    def test_parent_charges_do_not_include_agency_amounts(self):
        self.child.auto_charge = True
        self.child.billing_plan = "Bi-weekly"
        self.child.next_charge_date = date(2026, 9, 1)
        self.child.billing_amount = Decimal("53.00")
        self.child.save()
        posted = run_due_plan_charges(today=date(2026, 9, 9), child=self.child)
        self.assertTrue(posted)
        entries = list(PortalLedgerEntry.objects.filter(family=self.family, entry_type="charge"))
        self.assertTrue(entries)
        for entry in entries:
            self.assertLessEqual(entry.amount, Decimal("53.00"))
            self.assertNotIn("agency", entry.description.lower())
        total = sum(entry.amount for entry in entries)
        self.assertEqual(total, Decimal("53.00"))
        self.assertFalse(
            PortalLedgerEntry.objects.filter(family=self.family, amount=Decimal("110.00")).exists()
        )


class WeeklyFourCsThursdayPostTests(TestCase):
    def setUp(self):
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
            auth_end=date(2026, 9, 25),
            daily_copay="5.30",
            daily_agency_rate="22.00",
        )
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

    def _login_admin(self):
        self.client.force_login(self.admin)
        session = self.client.session
        session[PORTAL_AUTH_SESSION_KEY] = "admin"
        session.save()

    def test_thursday_covers_the_following_school_week(self):
        self.assertEqual(FOUR_CS_WEEKLY_POST_WEEKDAY, 3)
        self.assertEqual(most_recent_thursday(date(2026, 9, 10)), date(2026, 9, 10))
        self.assertEqual(most_recent_thursday(date(2026, 9, 11)), date(2026, 9, 10))
        self.assertEqual(most_recent_thursday(date(2026, 9, 9)), date(2026, 9, 3))
        self.assertEqual(week_monday_covered_by_thursday(date(2026, 9, 10)), date(2026, 9, 14))
        self.assertEqual(week_monday_covered_by_thursday(date(2026, 9, 3)), date(2026, 9, 7))
        self.assertEqual(next_thursday_on_or_after(date(2026, 9, 10)), date(2026, 9, 10))
        self.assertEqual(next_thursday_on_or_after(date(2026, 9, 8)), date(2026, 9, 10))
        self.assertEqual(next_thursday_after(date(2026, 9, 10)), date(2026, 9, 17))

    def test_weekly_period_for_thursday_is_next_week_not_older_weeks(self):
        period = parent_period_for_weekly_thursday_post(self.profile, "Weekly", date(2026, 9, 10))
        self.assertEqual(period["start"], date(2026, 9, 14))
        self.assertEqual(period["end"], date(2026, 9, 18))
        self.assertEqual(period["amount"], Decimal("26.50"))

    def test_post_today_creates_ledger_charge_dated_today(self):
        today = date(2026, 9, 9)  # Wednesday — last Thursday covers week of Sept 7
        with patch("portal.billing_services.timezone.localdate", return_value=today):
            child, posted = update_child_billing_plan(
                self.family,
                "Ada Rivera",
                "Weekly",
                billing_type="4Cs",
                auto_charge=True,
                next_charge_date=today,
            )
        self.assertEqual(len(posted), 1)
        entry = PortalLedgerEntry.objects.get(family=self.family, entry_type="charge")
        self.assertEqual(entry.date, today)
        self.assertEqual(entry.amount, Decimal("26.50"))
        self.assertIn("9/7/26", entry.description)
        self.assertNotIn("agency", entry.description.lower())
        child.refresh_from_db()
        self.assertEqual(child.charge_weekday, FOUR_CS_WEEKLY_POST_WEEKDAY)
        self.assertEqual(child.next_charge_date, date(2026, 9, 10))
        self.assertFalse(
            PortalLedgerEntry.objects.filter(family=self.family, amount=Decimal("110.00")).exists()
        )

    def test_post_today_on_thursday_covers_next_week_and_appears_today(self):
        today = date(2026, 9, 10)  # Thursday
        with patch("portal.billing_services.timezone.localdate", return_value=today):
            child, posted = update_child_billing_plan(
                self.family,
                "Ada Rivera",
                "Weekly",
                billing_type="4Cs",
                auto_charge=True,
                next_charge_date=today,
            )
        self.assertEqual(len(posted), 1)
        entry = PortalLedgerEntry.objects.get(family=self.family, entry_type="charge")
        self.assertEqual(entry.date, today)
        self.assertEqual(entry.amount, Decimal("26.50"))
        self.assertIn("9/14/26", entry.description)
        child.refresh_from_db()
        self.assertEqual(child.next_charge_date, date(2026, 9, 17))

    def test_weekly_automatic_posts_on_thursday_for_next_week(self):
        thursday = date(2026, 9, 10)
        self.child.auto_charge = True
        self.child.billing_plan = "Weekly"
        self.child.charge_weekday = FOUR_CS_WEEKLY_POST_WEEKDAY
        self.child.next_charge_date = thursday
        self.child.billing_amount = Decimal("26.50")
        self.child.save()
        posted = run_due_plan_charges(today=thursday, child=self.child)
        self.assertTrue(posted)
        entry = PortalLedgerEntry.objects.get(family=self.family, entry_type="charge")
        self.assertEqual(entry.date, thursday)
        self.assertIn("9/14/26", entry.description)
        self.assertEqual(entry.amount, Decimal("26.50"))
        self.child.refresh_from_db()
        self.assertEqual(self.child.next_charge_date, date(2026, 9, 17))
        later = run_due_plan_charges(today=date(2026, 9, 14), child=self.child)
        self.assertEqual(later, [])
        self.assertEqual(PortalLedgerEntry.objects.filter(family=self.family, entry_type="charge").count(), 1)
        posted_again = run_due_plan_charges(today=date(2026, 9, 17), child=self.child)
        self.assertTrue(posted_again)
        self.assertEqual(PortalLedgerEntry.objects.filter(family=self.family, entry_type="charge").count(), 2)
        second = (
            PortalLedgerEntry.objects.filter(family=self.family, entry_type="charge")
            .order_by("date", "pk")
            .last()
        )
        self.assertEqual(second.date, date(2026, 9, 17))
        self.assertIn("9/21/26", second.description)

    def test_saving_weekly_plan_without_post_today_waits_until_thursday(self):
        monday = date(2026, 9, 7)
        with patch("portal.billing_services.timezone.localdate", return_value=monday):
            child, posted = update_child_billing_plan(
                self.family,
                "Ada Rivera",
                "Weekly",
                billing_type="4Cs",
                auto_charge=True,
            )
        self.assertEqual(posted, [])
        self.assertFalse(PortalLedgerEntry.objects.filter(family=self.family).exists())
        child.refresh_from_db()
        self.assertEqual(child.next_charge_date, date(2026, 9, 10))
        self.assertEqual(child.charge_weekday, FOUR_CS_WEEKLY_POST_WEEKDAY)

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_plans_form_post_today_writes_charge_now(self):
        self._login_admin()
        today = date(2026, 9, 11)  # Friday — last Thursday covers week of Sept 14
        with patch("portal.billing_services.timezone.localdate", return_value=today), patch(
            "portal.views_actions.timezone.localdate", return_value=today
        ):
            plans = self.client.get(reverse("portal_admin_family_plans", kwargs={"family_slug": "rivera"}))
            self.assertEqual(plans.status_code, 200)
            self.assertContains(plans, "Post today")
            self.assertContains(plans, "Thursday")
            response = self.client.post(
                reverse("portal_staff_billing_action", kwargs={"family_slug": "rivera"}),
                {
                    "portal_area": "admin",
                    "action": "update_4cs_plan",
                    "child_name": "Ada Rivera",
                    "billing_plan": "Weekly",
                    "auto_charge": "on",
                    "post_today": "on",
                    "next": reverse("portal_admin_family_billing", kwargs={"family_slug": "rivera"}),
                },
            )
        self.assertEqual(response.status_code, 302)
        entry = PortalLedgerEntry.objects.get(family=self.family, entry_type="charge")
        self.assertEqual(entry.date, today)
        self.assertEqual(entry.amount, Decimal("26.50"))
        self.assertIn("9/14/26", entry.description)
        billing = self.client.get(reverse("portal_admin_family_billing", kwargs={"family_slug": "rivera"}))
        self.assertEqual(billing.status_code, 200)
        self.assertContains(billing, "26.50")
        self.assertContains(billing, "9/14/26")


class BiweeklyFourCsStartDateTests(TestCase):
    def setUp(self):
        self.unit = PortalUnit.objects.create(slug="school-18", name="School 18", is_active=True)
        self.family = PortalFamily.objects.create(
            unit=self.unit, slug="rivera", name="Rivera", billing_type="4Cs", status="Active"
        )
        self.child = PortalChild.objects.create(
            family=self.family, name="Ada Rivera", is_active=True, billing_plan="Bi-weekly"
        )
        self.profile = save_agency_member(
            self.unit,
            "rivera",
            "Ada Rivera",
            "Passaic County 4Cs",
            auth_start=date(2026, 9, 1),
            auth_end=date(2026, 9, 25),
            daily_copay="5.30",
            daily_agency_rate="22.00",
        )
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

    def _login_admin(self):
        self.client.force_login(self.admin)
        session = self.client.session
        session[PORTAL_AUTH_SESSION_KEY] = "admin"
        session.save()

    def test_biweekly_window_starts_on_entered_date_not_contract(self):
        self.assertEqual(next_biweekly_charge_date(date(2026, 9, 14)), date(2026, 9, 28))
        period = parent_period_for_biweekly_from_date(self.profile, "Bi-weekly", date(2026, 9, 14))
        self.assertEqual(period["start"], date(2026, 9, 14))
        self.assertEqual(period["end"], date(2026, 9, 25))
        self.assertEqual(period["amount"], Decimal("53.00"))
        self.assertNotEqual(period["start"], date(2026, 9, 1))

    def test_entered_start_skips_earlier_contract_weeks(self):
        start = date(2026, 9, 14)
        with patch("portal.billing_services.timezone.localdate", return_value=start):
            child, posted = update_child_billing_plan(
                self.family,
                "Ada Rivera",
                "Bi-weekly",
                billing_type="4Cs",
                auto_charge=True,
                next_charge_date=start,
            )
        self.assertEqual(len(posted), 1)
        entry = PortalLedgerEntry.objects.get(family=self.family, entry_type="charge")
        self.assertEqual(entry.date, start)
        self.assertEqual(entry.amount, Decimal("53.00"))
        self.assertIn("9/14/26", entry.description)
        self.assertNotIn("9/1/26", entry.description)
        self.assertFalse(
            PortalLedgerEntry.objects.filter(family=self.family, amount=Decimal("110.00")).exists()
        )
        child.refresh_from_db()
        self.assertEqual(child.next_charge_date, date(2026, 9, 28))
        first_week = self.profile.contract_weeks.get(week_start=date(2026, 9, 1))
        first_week.refresh_from_db()
        self.assertFalse(first_week.parent_posted)

    def test_future_entered_date_does_not_post(self):
        today = date(2026, 9, 11)
        start = date(2026, 9, 21)
        with patch("portal.billing_services.timezone.localdate", return_value=today):
            child, posted = update_child_billing_plan(
                self.family,
                "Ada Rivera",
                "Bi-weekly",
                billing_type="4Cs",
                auto_charge=True,
                next_charge_date=start,
            )
        self.assertEqual(posted, [])
        self.assertFalse(PortalLedgerEntry.objects.filter(family=self.family).exists())
        child.refresh_from_db()
        self.assertEqual(child.next_charge_date, start)

    def test_biweekly_repeats_every_two_weeks_from_entered_date(self):
        start = date(2026, 9, 14)
        self.child.auto_charge = True
        self.child.billing_plan = "Bi-weekly"
        self.child.next_charge_date = start
        self.child.billing_amount = Decimal("53.00")
        self.child.save()
        posted = run_due_plan_charges(today=start, child=self.child)
        self.assertTrue(posted)
        self.child.refresh_from_db()
        self.assertEqual(self.child.next_charge_date, date(2026, 9, 28))
        later = run_due_plan_charges(today=date(2026, 9, 21), child=self.child)
        self.assertEqual(later, [])
        self.assertEqual(PortalLedgerEntry.objects.filter(family=self.family, entry_type="charge").count(), 1)

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_plans_form_uses_typed_biweekly_start_date(self):
        self._login_admin()
        today = date(2026, 9, 11)
        start = date(2026, 9, 14)
        with patch("portal.billing_services.timezone.localdate", return_value=today), patch(
            "portal.views_actions.timezone.localdate", return_value=today
        ):
            plans = self.client.get(reverse("portal_admin_family_plans", kwargs={"family_slug": "rivera"}))
            self.assertContains(plans, "First charge date")
            self.assertContains(plans, "every two weeks")
            response = self.client.post(
                reverse("portal_staff_billing_action", kwargs={"family_slug": "rivera"}),
                {
                    "portal_area": "admin",
                    "action": "update_4cs_plan",
                    "child_name": "Ada Rivera",
                    "billing_plan": "Bi-weekly",
                    "auto_charge": "on",
                    "next_charge_date": start.isoformat(),
                    "next": reverse("portal_admin_family_plans", kwargs={"family_slug": "rivera"}),
                },
            )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(PortalLedgerEntry.objects.filter(family=self.family).exists())
        self.child.refresh_from_db()
        self.assertEqual(self.child.next_charge_date, start)
        self.assertEqual(self.child.billing_plan, "Bi-weekly")


class AgencyReceivedCheckboxTests(TestCase):
    def setUp(self):
        self.unit = PortalUnit.objects.create(slug="school-18", name="School 18", is_active=True)
        self.family = PortalFamily.objects.create(
            unit=self.unit, slug="rivera", name="Rivera", billing_type="4Cs"
        )
        self.child = PortalChild.objects.create(family=self.family, name="Ada Rivera", is_active=True)
        self.profile = save_agency_member(
            self.unit,
            "rivera",
            "Ada Rivera",
            "Passaic County 4Cs",
            auth_start=date(2026, 9, 1),
            auth_end=date(2026, 9, 4),
            daily_agency_rate="22.00",
            daily_copay="5.30",
        )

    def test_received_checkbox_stays_off_parent_ledger(self):
        week = self.profile.contract_weeks.get()
        before_parent = PortalLedgerEntry.objects.filter(family=self.family).count()
        mark_agency_week_received(week, received=True)
        week.refresh_from_db()
        self.profile.refresh_from_db()
        self.assertTrue(week.received)
        self.assertEqual(PortalLedgerEntry.objects.filter(family=self.family).count(), before_parent)
        self.assertTrue(self.profile.ledger_entries.filter(entry_type="payment").exists())


class WaitingAuthorizationAddAgencyTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.unit = PortalUnit.objects.create(slug="school-18", name="School 18", is_active=True)
        self.family = PortalFamily.objects.create(
            unit=self.unit, slug="rivera", name="Rivera", billing_type="4Cs"
        )
        self.child = PortalChild.objects.create(family=self.family, name="Ada Rivera", is_active=True)
        self.admin = User.objects.create_user(username="staff:yeaadmin", password="AdminPass123")
        PortalStaffAccount.objects.create(
            user=self.admin,
            unit=self.unit,
            display_name="Portal Admin",
            role="Portal admin",
            all_units_access=True,
            is_active=True,
        )
        self.staff = User.objects.create_user(username="staff:unitstaff", password="StaffPass123")
        PortalStaffAccount.objects.create(
            user=self.staff,
            unit=self.unit,
            display_name="Unit Staff",
            role="Unit director",
            all_units_access=False,
            is_active=True,
        )

    def _login(self, user, area):
        self.client.force_login(user)
        session = self.client.session
        session[PORTAL_AUTH_SESSION_KEY] = area
        session.save()

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_waiting_list_add_agency_prefills_child(self):
        self._login(self.admin, "admin")
        dashboard = self.client.get(reverse("portal_admin_page", kwargs={"page": "dashboard"}))
        self.assertEqual(dashboard.status_code, 200)
        add_url = reverse("portal_admin_agency_member_add")
        self.assertContains(dashboard, "Add agency")
        self.assertContains(dashboard, f"{add_url}?child_id={self.child.pk}")
        agencies = self.client.get(reverse("portal_admin_page", kwargs={"page": "agencies"}))
        self.assertEqual(agencies.status_code, 200)
        self.assertContains(agencies, "Add agency")
        self.assertContains(agencies, f"{add_url}?child_id={self.child.pk}")
        form = self.client.get(f"{add_url}?child_id={self.child.pk}")
        self.assertEqual(form.status_code, 200)
        self.assertContains(form, "Ada Rivera")
        self.assertContains(form, "Rivera")
        self.assertContains(form, "What the agency pays YEA")
        self.assertContains(form, "What the parent pays YEA")

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_staff_waiting_list_has_add_agency_button(self):
        self._login(self.staff, "staff")
        page = self.client.get(reverse("portal_staff_page", kwargs={"page": "agency"}))
        self.assertEqual(page.status_code, 200)
        add_url = reverse("portal_staff_agency_member_add")
        self.assertContains(page, "Add agency")
        self.assertContains(page, f"{add_url}?child_id={self.child.pk}")

    def _agency_save_payload(self, **overrides):
        payload = {
            "child_id": str(self.child.pk),
            "family_slug": "rivera",
            "child_name": "Ada Rivera",
            "agency_name": "Passaic County 4Cs",
            "auth_start": "2026-09-01",
            "auth_end": "2026-09-30",
            "daily_agency_rate": "22.00",
            "weekly_agency_rate": "110.00",
            "daily_copay": "5.30",
            "weekly_copay": "26.50",
            "week_start": ["2026-09-01", "2026-09-07", "2026-09-14", "2026-09-21", "2026-09-28"],
            "week_end": ["2026-09-04", "2026-09-11", "2026-09-18", "2026-09-25", "2026-09-30"],
            "week_agency": ["110.00", "110.00", "90.00", "110.00", "110.00"],
            "week_parent": ["26.50", "26.50", "0.00", "26.50", "26.50"],
        }
        payload.update(overrides)
        return payload

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_saving_agency_from_waiting_child_links_the_member(self):
        self._login(self.admin, "admin")
        response = self.client.post(
            reverse("portal_admin_agency_member_add") + f"?child_id={self.child.pk}",
            self._agency_save_payload(),
        )
        self.assertNotEqual(response.status_code, 500)
        self.assertEqual(response.status_code, 302)
        family_agency = reverse("portal_admin_family_agency", kwargs={"family_slug": "rivera"})
        self.assertIn(family_agency, response["Location"])
        profile = PortalAgencyProfile.objects.get(child=self.child)
        self.assertEqual(profile.family_id, self.family.pk)
        self.assertEqual(profile.contract_weeks.count(), 5)
        self.assertEqual(profile.weekly_copay, Decimal("26.50"))
        self.assertEqual(profile.weekly_agency_rate, Decimal("110.00"))
        self.assertEqual(
            profile.contract_weeks.get(week_start=date(2026, 9, 14)).agency_amount,
            Decimal("90.00"),
        )
        self.assertEqual(
            profile.contract_weeks.get(week_start=date(2026, 9, 14)).parent_amount,
            Decimal("0.00"),
        )
        follow = self.client.get(response["Location"])
        self.assertEqual(follow.status_code, 200)
        self.assertContains(follow, "Ada Rivera")
        self.assertContains(follow, "9/14/26")
        self.assertContains(follow, "$90.00")

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_staff_saving_agency_redirects_with_weeks(self):
        self._login(self.staff, "staff")
        response = self.client.post(
            reverse("portal_staff_agency_member_add"),
            self._agency_save_payload(),
        )
        self.assertNotEqual(response.status_code, 500)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response["Location"],
            reverse("portal_staff_family_agency", kwargs={"family_slug": "rivera"}),
        )
        profile = PortalAgencyProfile.objects.get(child=self.child)
        self.assertEqual(profile.contract_weeks.count(), 5)
        follow = self.client.get(response["Location"])
        self.assertEqual(follow.status_code, 200)
        self.assertContains(follow, "Agency expected weeks")
        self.assertContains(follow, "$110.00")

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_editing_agency_keeps_posted_weeks(self):
        self._login(self.admin, "admin")
        add = self.client.post(
            reverse("portal_admin_agency_member_add"),
            self._agency_save_payload(),
        )
        self.assertEqual(add.status_code, 302)
        profile = PortalAgencyProfile.objects.get(child=self.child)
        edit = self.client.post(
            reverse("portal_admin_agency_member_edit", kwargs={"profile_id": profile.pk}),
            self._agency_save_payload(
                daily_agency_rate="22.00",
                weekly_agency_rate="110.00",
                week_agency=["110.00", "75.00", "90.00", "110.00", "110.00"],
                week_parent=["26.50", "10.00", "0.00", "26.50", "26.50"],
            ),
        )
        self.assertNotEqual(edit.status_code, 500)
        self.assertEqual(edit.status_code, 302)
        profile.refresh_from_db()
        self.assertEqual(
            profile.contract_weeks.get(week_start=date(2026, 9, 7)).agency_amount,
            Decimal("75.00"),
        )
        self.assertEqual(
            profile.contract_weeks.get(week_start=date(2026, 9, 7)).parent_amount,
            Decimal("10.00"),
        )
        self.assertEqual(profile.contract_weeks.count(), 5)


class ProgramCalendarFourCsTests(TestCase):
    def setUp(self):
        self.unit = PortalUnit.objects.create(slug="school-18", name="School 18", is_active=True)
        self.family = PortalFamily.objects.create(
            unit=self.unit, slug="rivera", name="Rivera", billing_type="4Cs", status="Active"
        )
        self.child = PortalChild.objects.create(
            family=self.family, name="Ada Rivera", is_active=True, billing_plan="Bi-weekly"
        )
        calendar = get_program_calendar()
        calendar.program_start = date(2026, 9, 8)
        calendar.days_off = ["2026-11-26"]
        calendar.half_days = ["2026-11-25"]
        calendar.save()
        self.profile = save_agency_member(
            self.unit,
            "rivera",
            "Ada Rivera",
            "Passaic County 4Cs",
            auth_start=date(2026, 9, 1),
            auth_end=date(2026, 9, 25),
            daily_copay="5.30",
            daily_agency_rate="22.00",
        )
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

    def _login_admin(self):
        self.client.force_login(self.admin)
        session = self.client.session
        session[PORTAL_AUTH_SESSION_KEY] = "admin"
        session.save()

    def test_parent_biweekly_is_sept_8_to_18_agency_keeps_sept_1(self):
        first = self.profile.contract_weeks.get(week_start=date(2026, 9, 1))
        self.assertTrue(first.agency_included)
        self.assertFalse(first.parent_included)
        period = parent_period_for_biweekly_from_date(self.profile, "Bi-weekly", date(2026, 9, 1))
        self.assertEqual(period["start"], date(2026, 9, 8))
        self.assertEqual(period["end"], date(2026, 9, 18))
        self.assertEqual(period["amount"], Decimal("53.00"))
        self.assertEqual(period["label"], "9/8/26–9/18/26")
        periods = parent_charge_periods(self.profile, "Bi-weekly")
        self.assertEqual(periods[0]["start"], date(2026, 9, 8))
        self.assertEqual(periods[0]["end"], date(2026, 9, 18))
        starts = [week.week_start for week in self.profile.contract_weeks.order_by("week_start")]
        self.assertIn(date(2026, 9, 1), starts)

    def test_full_days_off_skip_parent_week(self):
        calendar = get_program_calendar()
        calendar.days_off = [
            "2026-09-08",
            "2026-09-09",
            "2026-09-10",
            "2026-09-11",
        ]
        calendar.save()
        sync_contract_weeks(self.profile)
        week = self.profile.contract_weeks.get(week_start=date(2026, 9, 7))
        self.assertFalse(week.parent_included)
        self.assertTrue(week.agency_included)
        period = parent_period_for_biweekly_from_date(self.profile, "Bi-weekly", date(2026, 9, 1))
        self.assertEqual(period["start"], date(2026, 9, 14))

    def test_unchecking_parent_week_controls_what_posts(self):
        apply_week_includes(
            self.profile,
            parent_starts=[date(2026, 9, 14), date(2026, 9, 21)],
            agency_starts=[week.week_start for week in self.profile.contract_weeks.all()],
        )
        period = parent_period_for_biweekly_from_date(self.profile, "Bi-weekly", date(2026, 9, 1))
        self.assertEqual(period["start"], date(2026, 9, 14))
        self.assertEqual(period["end"], date(2026, 9, 25))
        self.child.auto_charge = True
        self.child.billing_plan = "Bi-weekly"
        self.child.next_charge_date = date(2026, 9, 1)
        self.child.save()
        posted = run_due_plan_charges(today=date(2026, 9, 9), child=self.child)
        self.assertTrue(posted)
        entry = PortalLedgerEntry.objects.get(family=self.family, entry_type="charge")
        self.assertIn("9/14/26", entry.description)
        self.assertNotIn("9/8/26", entry.description)
        skipped = self.profile.contract_weeks.get(week_start=date(2026, 9, 7))
        skipped.refresh_from_db()
        self.assertFalse(skipped.parent_posted)

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_settings_page_persists_program_start_and_days(self):
        self._login_admin()
        page = self.client.get(reverse("portal_admin_page", kwargs={"page": "program-calendar"}))
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, "Program start date")
        self.assertContains(page, "Days off")
        self.assertContains(page, "Half days")
        self.assertContains(page, "4Cs still pays")
        response = self.client.post(
            reverse("portal_admin_program_calendar_save"),
            {
                "program_start": "2026-09-08",
                "days_off": "11/26/2026\n12/24/2026",
                "half_days": "11/25/2026",
            },
        )
        self.assertEqual(response.status_code, 302)
        calendar = PortalProgramCalendar.objects.order_by("pk").first()
        self.assertEqual(calendar.program_start, date(2026, 9, 8))
        self.assertEqual(calendar.days_off, ["2026-11-26", "2026-12-24"])
        self.assertEqual(calendar.half_days, ["2026-11-25"])
        again = self.client.get(reverse("portal_admin_page", kwargs={"page": "program-calendar"}))
        self.assertContains(again, "2026-09-08")
        self.assertContains(again, "11/26/2026")
        self.assertContains(again, "11/25/2026")

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_plans_form_can_change_which_weeks_post(self):
        self._login_admin()
        plans = self.client.get(reverse("portal_admin_family_plans", kwargs={"family_slug": "rivera"}))
        self.assertEqual(plans.status_code, 200)
        self.assertContains(plans, "Weeks to post")
        self.assertContains(plans, "Charge parent")
        self.assertContains(plans, "Agency pays")
        today = date(2026, 9, 9)
        with patch("portal.billing_services.timezone.localdate", return_value=today), patch(
            "portal.views_actions.timezone.localdate", return_value=today
        ):
            response = self.client.post(
                reverse("portal_staff_billing_action", kwargs={"family_slug": "rivera"}),
                {
                    "portal_area": "admin",
                    "action": "update_4cs_plan",
                    "child_name": "Ada Rivera",
                    "billing_plan": "Bi-weekly",
                    "auto_charge": "on",
                    "post_today": "on",
                    "four_cs_weeks_posted": "1",
                    "parent_week_include": ["2026-09-14", "2026-09-21"],
                    "agency_week_include": [
                        "2026-09-01",
                        "2026-09-07",
                        "2026-09-14",
                        "2026-09-21",
                    ],
                    "next": reverse("portal_admin_family_plans", kwargs={"family_slug": "rivera"}),
                },
            )
        self.assertEqual(response.status_code, 302)
        week_sept_8 = self.profile.contract_weeks.get(week_start=date(2026, 9, 7))
        week_sept_8.refresh_from_db()
        self.assertFalse(week_sept_8.parent_included)
        self.assertFalse(week_sept_8.parent_posted)
        entry = PortalLedgerEntry.objects.get(family=self.family, entry_type="charge")
        self.assertIn("9/14/26", entry.description)
        self.assertNotIn("9/8/26", entry.description)
