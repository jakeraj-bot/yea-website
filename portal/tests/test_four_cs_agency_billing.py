from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from portal.agency_services import save_agency_member
from portal.agency_weeks import (
    mark_agency_week_received,
    parent_charge_periods,
    period_parent_total,
    school_weeks_in_range,
    sync_contract_weeks,
    weekly_from_daily,
)
from portal.billing_services import run_due_plan_charges
from portal.models import (
    PortalAgencyProfile,
    PortalChild,
    PortalFamily,
    PortalLedgerEntry,
    PortalStaffAccount,
    PortalUnit,
)
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

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_saving_agency_from_waiting_child_links_the_member(self):
        self._login(self.admin, "admin")
        response = self.client.post(
            reverse("portal_admin_agency_member_add") + f"?child_id={self.child.pk}",
            {
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
            },
        )
        self.assertEqual(response.status_code, 302)
        profile = PortalAgencyProfile.objects.get(child=self.child)
        self.assertEqual(profile.family_id, self.family.pk)
        self.assertEqual(profile.contract_weeks.count(), 5)
        self.assertEqual(profile.weekly_copay, Decimal("26.50"))
