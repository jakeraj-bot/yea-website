"""Admin overdue/outstanding numbers drop when parents pay tuition."""

from datetime import date
from decimal import Decimal

from django.test import TestCase

from portal.admin_reports import build_admin_report
from portal.admin_services import get_admin_alerts_live, get_admin_dashboard_live, get_member_families_live
from portal.agency_services import balances_report_rows
from portal.billing_services import post_charge, post_credit, post_payment
from portal.family_list import (
    child_balance,
    family_balance,
    live_family_child_rows,
    overdue_active_children_summary,
    prefetch_family_table_queryset,
    unit_balance_summary,
)
from portal.member_admin import set_child_active
from portal.models import PortalChild, PortalFamily, PortalPayment, PortalUnit
from portal.owed_weeks import families_with_balance, owed_weeks_report
from portal.parent_services import record_successful_payment
from portal.staff_services import build_dashboard_live
from portal.tests.test_care_program_filters import _make_app
from portal.tests.test_family_units import _make_application


class OverdueBalancesFollowPaymentsTests(TestCase):
    def setUp(self):
        self.unit = PortalUnit.objects.create(slug="school-18", name="School 18", is_active=True)
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
            is_active=True,
        )
        self.maya = PortalChild.objects.create(
            family=self.family,
            name="Maya Jacobs",
            school="School 18",
            is_active=True,
        )

    def _charge(self, child_name, amount, description="Weekly tuition"):
        return post_charge(
            self.family,
            child_name,
            "tuition",
            amount,
            date(2026, 9, 8),
            f"{description} — {child_name} (9/8/26–9/12/26)",
            notify=False,
        )

    def _outstanding(self):
        return build_admin_report("balances", {"owes": "yes"})

    def _row_by_child(self, report):
        return {row["child"]: row for row in report["rows"]}

    def test_named_payment_reduces_outstanding_by_tuition(self):
        self._charge("Jordan Jacobs", "80.00")
        report = self._outstanding()
        self.assertEqual(report["outstanding"], "80.00")
        self.assertEqual(self._row_by_child(report)["Jordan Jacobs"]["balance"], "80.00")

        post_payment(self.family, "Jordan Jacobs", "30.00", date(2026, 9, 9), "Cash")
        after = self._outstanding()
        self.assertEqual(after["outstanding"], "50.00")
        self.assertEqual(self._row_by_child(after)["Jordan Jacobs"]["balance"], "50.00")

    def test_stripe_fee_does_not_stay_on_outstanding(self):
        self._charge("Jordan Jacobs", "40.00")
        payment = PortalPayment.objects.create(
            family=self.family,
            amount=Decimal("40.00"),
            fee_amount=Decimal("1.46"),
            total_charged=Decimal("41.46"),
            payment_kind="balance",
            dropin_child="Jordan Jacobs",
            stripe_session_id="cs_overdue_fee",
            stripe_payment_intent_id="pi_overdue_fee",
        )
        record_successful_payment(payment, method_label="Visa ending 4242", child_name="Jordan Jacobs")

        after = self._outstanding()
        self.assertEqual(after["outstanding"], "0.00")
        self.assertEqual(after["rows"], [])
        self.assertEqual(family_balance(self.family), Decimal("0.00"))
        self.assertEqual(child_balance(self.jordan), Decimal("0.00"))

    def test_family_level_payment_covers_oldest_child_charge_first(self):
        self._charge("Jordan Jacobs", "35.00")
        self._charge("Maya Jacobs", "45.00")
        before = self._outstanding()
        self.assertEqual(before["outstanding"], "80.00")
        names = {row["child"] for row in before["rows"]}
        self.assertEqual(names, {"Jordan Jacobs", "Maya Jacobs"})
        self.assertEqual(self._row_by_child(before)["Jordan Jacobs"]["balance"], "35.00")
        self.assertEqual(self._row_by_child(before)["Maya Jacobs"]["balance"], "45.00")

        post_payment(self.family, "", "20.00", date(2026, 9, 9), "Check", "Family payment", "1001")
        after = self._outstanding()
        self.assertEqual(after["outstanding"], "60.00")
        by_child = self._row_by_child(after)
        self.assertEqual(set(by_child), {"Jordan Jacobs", "Maya Jacobs"})
        remaining = Decimal(by_child["Jordan Jacobs"]["balance"]) + Decimal(by_child["Maya Jacobs"]["balance"])
        self.assertEqual(remaining, Decimal("60.00"))
        # Same-day charges: FIFO by id pays Jordan (posted first) before Maya.
        self.assertEqual(by_child["Jordan Jacobs"]["balance"], "15.00")
        self.assertEqual(by_child["Maya Jacobs"]["balance"], "45.00")
        self.assertNotEqual(by_child["Jordan Jacobs"]["balance"], "60.00")
        self.assertNotEqual(by_child["Maya Jacobs"]["balance"], "60.00")

        post_payment(self.family, "", "60.00", date(2026, 9, 10), "Money order", "Family payoff", "555")
        paid = self._outstanding()
        self.assertEqual(paid["outstanding"], "0.00")
        self.assertEqual(paid["rows"], [])

    def test_zero_child_stays_off_outstanding_when_sibling_owes(self):
        self._charge("Jordan Jacobs", "35.00")
        self._charge("Maya Jacobs", "45.00")
        post_payment(self.family, "Jordan Jacobs", "35.00", date(2026, 9, 9), "Cash")
        report = self._outstanding()
        self.assertEqual([row["child"] for row in report["rows"]], ["Maya Jacobs"])
        self.assertEqual(report["rows"][0]["balance"], "45.00")
        self.assertEqual(report["outstanding"], "45.00")

    def test_dashboard_overdue_uses_ledger_not_stale_family_balance(self):
        self._charge("Jordan Jacobs", "50.00")
        self.family.refresh_from_db()
        self.assertEqual(self.family.balance, Decimal("50.00"))
        dashboard = get_admin_dashboard_live()
        self.assertEqual(dashboard["overdue_families"], 1)
        self.assertEqual(dashboard["overdue_amount"], "50.00")

        post_payment(self.family, "Jordan Jacobs", "50.00", date(2026, 9, 9), "Cash")
        self.family.balance = Decimal("50.00")
        self.family.save(update_fields=["balance"])

        dashboard = get_admin_dashboard_live()
        self.assertEqual(dashboard["overdue_families"], 0)
        self.assertEqual(dashboard["overdue_amount"], "0.00")
        alerts = get_admin_alerts_live()
        overdue_alerts = [row for row in alerts if "overdue" in row["text"].lower()]
        self.assertEqual(overdue_alerts, [])

        member_rows = get_member_families_live()
        jacobs = next(row for row in member_rows if row["slug"] == "jacobs")
        self.assertEqual(jacobs["balance"], "0.00")

    def test_family_list_balance_column_drops_after_payment(self):
        self._charge("Jordan Jacobs", "40.00")
        rows = live_family_child_rows(
            prefetch_family_table_queryset(PortalFamily.objects.filter(pk=self.family.pk))
        )
        jordan = next(row for row in rows if row["child_name"] == "Jordan Jacobs")
        self.assertEqual(jordan["child_balance"], "40.00")
        self.assertEqual(jordan["family_balance"], "40.00")

        post_payment(self.family, "", "15.00", date(2026, 9, 9), "Cash")
        rows = live_family_child_rows(
            prefetch_family_table_queryset(PortalFamily.objects.filter(pk=self.family.pk))
        )
        jordan = next(row for row in rows if row["child_name"] == "Jordan Jacobs")
        self.assertEqual(jordan["child_balance"], "25.00")
        self.assertEqual(jordan["family_balance"], "25.00")

    def test_owed_weeks_drops_paid_child_after_family_payment(self):
        self._charge("Jordan Jacobs", "35.00")
        self._charge("Maya Jacobs", "45.00")
        report = owed_weeks_report({}, admin=True)
        self.assertEqual({row["child"] for row in report["rows"]}, {"Jordan Jacobs", "Maya Jacobs"})
        self.assertEqual(report["outstanding"], "80.00")

        post_payment(self.family, "", "80.00", date(2026, 9, 9), "Cash")
        after = owed_weeks_report({}, admin=True)
        self.assertEqual(after["rows"], [])
        self.assertEqual(after["outstanding"], "0.00")
        self.assertEqual(families_with_balance(), [])

    def test_staff_outstanding_csv_and_dashboard_follow_ledger(self):
        self._charge("Jordan Jacobs", "25.00")
        staff_dashboard = build_dashboard_live(self.unit, None)
        texts = [alert["text"] for alert in staff_dashboard["alerts"]]
        self.assertTrue(any("1 family with balance due" in text for text in texts))
        self.assertTrue(any("Jacobs — $25.00 balance due" in text for text in texts))
        self.assertEqual(balances_report_rows(self.unit)[0]["balance"], "25.00")

        post_payment(self.family, "Jordan Jacobs", "25.00", date(2026, 9, 9), "Cash")
        self.family.balance = Decimal("25.00")
        self.family.save(update_fields=["balance"])

        staff_dashboard = build_dashboard_live(self.unit, None)
        texts = [alert["text"] for alert in staff_dashboard["alerts"]]
        self.assertFalse(any("balance due" in text.lower() for text in texts))
        self.assertEqual(balances_report_rows(self.unit), [])

    def test_overview_overdue_matches_sum_of_positive_child_balances_only(self):
        self._charge("Jordan Jacobs", "100.00")
        self._charge("Maya Jacobs", "50.00")
        post_payment(self.family, "Jordan Jacobs", "40.00", date(2026, 9, 9), "Cash")
        post_credit(self.family, "Jordan Jacobs", "20.00", date(2026, 9, 10), "Scholarship")
        post_payment(self.family, "Maya Jacobs", "80.00", date(2026, 9, 11), "Check", "Overpay", "2201")

        inactive = PortalChild.objects.create(
            family=self.family,
            name="Omar Inactive",
            school="School 18",
            is_active=False,
        )
        post_charge(
            self.family,
            inactive.name,
            "tuition",
            "99.00",
            date(2026, 9, 8),
            "Past due — Omar Inactive",
            notify=False,
        )

        pending_family = PortalFamily.objects.create(
            unit=self.unit,
            slug="pending-overdue",
            name="Pending Overdue",
            billing_type="Private pay",
            status="Active",
        )
        pending_child = PortalChild.objects.create(
            family=pending_family,
            name="Ada Pending",
            school="School 18",
            is_active=True,
        )
        _make_application(pending_family, status="under_review")
        pending_family.enrollment_applications.update(student_first_name="Ada", student_last_name="Pending")
        post_charge(
            pending_family,
            pending_child.name,
            "tuition",
            "88.00",
            date(2026, 9, 8),
            "Weekly tuition — Ada Pending",
            notify=False,
        )
        PortalPayment.objects.create(
            family=self.family,
            amount=Decimal("40.00"),
            fee_amount=Decimal("1.46"),
            total_charged=Decimal("41.46"),
            payment_kind="balance",
            dropin_child="Jordan Jacobs",
            status=PortalPayment.STATUS_PENDING,
            stripe_session_id="cs_waiting_card",
        )

        self.family.balance = Decimal("999.00")
        self.family.save(update_fields=["balance"])

        jordan_balance = child_balance(self.jordan)
        maya_balance = child_balance(self.maya)
        self.assertEqual(jordan_balance, Decimal("40.00"))
        self.assertEqual(maya_balance, Decimal("-30.00"))
        self.assertEqual(child_balance(inactive), Decimal("99.00"))
        self.assertEqual(family_balance(self.family), Decimal("109.00"))

        positive_only = sum(
            amount for amount in (jordan_balance, maya_balance) if amount > 0
        )
        self.assertEqual(positive_only, Decimal("40.00"))

        dashboard = get_admin_dashboard_live()
        self.assertNotIn("policy_completion_pct", dashboard)
        self.assertEqual(dashboard["overdue_families"], 1)
        self.assertEqual(dashboard["overdue_amount"], "40.00")
        self.assertNotEqual(dashboard["overdue_amount"], f"{self.family.balance:.2f}")
        self.assertNotEqual(dashboard["overdue_amount"], f"{family_balance(self.family):.2f}")

        count, total, owing = overdue_active_children_summary([self.family.pk, pending_family.pk])
        self.assertEqual(count, 1)
        self.assertEqual(total, Decimal("40.00"))
        self.assertEqual(owing[self.family.pk], Decimal("40.00"))
        self.assertNotIn(pending_family.pk, owing)


class InactiveChildFortyDollarOverdueExclusionTests(TestCase):
    """Overview overdue must drop the inactive child's leftover, keep the sibling."""

    def setUp(self):
        self.unit = PortalUnit.objects.create(slug="school-18", name="School 18", is_active=True)
        self.family = PortalFamily.objects.create(
            unit=self.unit,
            slug="overdue-inactive",
            name="Overdueinactive",
            billing_type="Private pay",
            status="Active",
            balance=Decimal("0.00"),
        )
        self.active = PortalChild.objects.create(
            family=self.family,
            name="Ada Active",
            school="School 18",
            is_active=True,
        )
        self.inactive = PortalChild.objects.create(
            family=self.family,
            name="Ivy Inactive",
            school="School 18",
            is_active=True,
        )
        self._named_app(self.active, status="approved")
        self._named_app(self.inactive, status="approved")

    def _named_app(self, child, *, status="approved", program="after_school"):
        app = _make_app(self.family, child, program=program, status=status)
        return app

    def _charge(self, child, amount, description):
        return post_charge(
            self.family,
            child.name,
            "tuition",
            amount,
            date(2026, 9, 8),
            f"{description} — {child.name} (9/8/26–9/12/26)",
            notify=False,
        )

    def _snapshot(self):
        dashboard = get_admin_dashboard_live()
        count, total, owing = overdue_active_children_summary([self.family.pk])
        units = {row["slug"]: row for row in unit_balance_summary()}
        return dashboard, count, total, owing, units

    def test_inactive_child_forty_dollar_balance_excluded_from_overdue_active_sibling_twenty_five_still_counts(self):
        self._charge(self.active, "25.00", "Weekly tuition")
        self._charge(self.inactive, "40.00", "Weekly tuition")
        self.family.balance = Decimal("999.00")
        self.family.save(update_fields=["balance"])
        PortalPayment.objects.create(
            family=self.family,
            amount=Decimal("40.00"),
            fee_amount=Decimal("1.46"),
            total_charged=Decimal("41.46"),
            payment_kind="balance",
            dropin_child=self.inactive.name,
            status=PortalPayment.STATUS_PENDING,
            stripe_session_id="cs_inactive_unfinished",
        )

        before_dash, before_count, before_total, before_owing, before_units = self._snapshot()
        self.assertEqual(child_balance(self.active), Decimal("25.00"))
        self.assertEqual(child_balance(self.inactive), Decimal("40.00"))
        self.assertEqual(family_balance(self.family), Decimal("65.00"))
        self.assertEqual(before_dash["overdue_families"], 1)
        self.assertEqual(before_dash["overdue_amount"], "65.00")
        self.assertEqual(before_count, 1)
        self.assertEqual(before_total, Decimal("65.00"))
        self.assertEqual(before_owing[self.family.pk], Decimal("65.00"))
        self.assertEqual(before_units["school-18"]["overdue"], "65.00")
        self.assertEqual(before_units["school-18"]["family_count"], 1)
        self.assertNotEqual(before_dash["overdue_amount"], f"{self.family.balance:.2f}")

        set_child_active(self.inactive, False)
        self.inactive.refresh_from_db()
        self.assertFalse(self.inactive.is_active)
        self.family.balance = Decimal("999.00")
        self.family.save(update_fields=["balance"])

        after_dash, after_count, after_total, after_owing, after_units = self._snapshot()
        self.assertEqual(child_balance(self.inactive), Decimal("40.00"))
        self.assertEqual(family_balance(self.family), Decimal("65.00"))
        self.assertEqual(after_dash["overdue_families"], 1)
        self.assertEqual(after_dash["overdue_amount"], "25.00")
        self.assertEqual(after_count, 1)
        self.assertEqual(after_total, Decimal("25.00"))
        self.assertEqual(after_owing[self.family.pk], Decimal("25.00"))
        self.assertEqual(after_units["school-18"]["overdue"], "25.00")
        self.assertEqual(after_units["school-18"]["family_count"], 1)
        self.assertEqual(after_units["school-18"]["overdue"], after_dash["overdue_amount"])
        self.assertNotEqual(after_dash["overdue_amount"], "65.00")
        self.assertNotEqual(after_dash["overdue_amount"], "40.00")
        self.assertNotEqual(after_dash["overdue_amount"], f"{self.family.balance:.2f}")
        self.assertNotEqual(after_dash["overdue_amount"], f"{family_balance(self.family):.2f}")

        default_balance = build_admin_report("balances", {})
        default_names = [row["child"] for row in default_balance["rows"]]
        self.assertIn("Ada Active", default_names)
        self.assertNotIn("Ivy Inactive", default_names)
        self.assertEqual(default_balance["outstanding"], "25.00")
        outstanding = build_admin_report("balances", {"owes": "yes"})
        self.assertEqual([row["child"] for row in outstanding["rows"]], ["Ada Active"])
        self.assertEqual(outstanding["outstanding"], "25.00")

        inactive_report = build_admin_report("inactive-children", {})
        self.assertIn("Ivy Inactive", [row["child"] for row in inactive_report["rows"]])
        self.assertEqual(
            next(row for row in inactive_report["rows"] if row["child"] == "Ivy Inactive")["balance"],
            "40.00",
        )
        inactive_tab = live_family_child_rows(
            prefetch_family_table_queryset(PortalFamily.objects.filter(pk=self.family.pk)),
            inactive=True,
        )
        self.assertEqual([row["child_name"] for row in inactive_tab], ["Ivy Inactive"])

        member_rows = get_member_families_live()
        family_row = next(row for row in member_rows if row["slug"] == "overdue-inactive")
        self.assertEqual(family_row["balance"], "25.00")
        self.assertEqual(family_row["children"], ["Ada Active"])

        owing_helpers = families_with_balance()
        self.assertEqual(len(owing_helpers), 1)
        self.assertEqual(owing_helpers[0]["family"].pk, self.family.pk)
        self.assertEqual(owing_helpers[0]["balance"], Decimal("25.00"))

        owed = owed_weeks_report({}, admin=True)
        self.assertEqual([row["child"] for row in owed["rows"]], ["Ada Active"])
        self.assertEqual(owed["outstanding"], "25.00")

        staff_dash = build_dashboard_live(self.unit, None)
        texts = [alert["text"] for alert in staff_dash["alerts"]]
        self.assertTrue(any("1 family with balance due" in text for text in texts))
        self.assertTrue(any("Overdueinactive — $25.00 balance due" in text for text in texts))
        self.assertFalse(any("$65.00" in text for text in texts))
        self.assertEqual(balances_report_rows(self.unit)[0]["balance"], "25.00")

        alerts = get_admin_alerts_live()
        overdue_alerts = [row for row in alerts if "overdue" in row["text"].lower()]
        self.assertEqual(len(overdue_alerts), 1)
        self.assertIn("$25.00", overdue_alerts[0]["text"])
        self.assertNotIn("$65.00", overdue_alerts[0]["text"])

    def test_per_application_inactive_before_care_does_not_drop_after_care_overdue(self):
        before_app = self._named_app(self.active, program="before_care", status="approved")
        self._charge(self.active, "25.00", "After care")
        post_charge(
            self.family,
            self.active.name,
            "tuition",
            "15.00",
            date(2026, 9, 8),
            f"Before care — {self.active.name} (9/8/26–9/12/26)",
            notify=False,
        )
        before_app.is_active = False
        before_app.save(update_fields=["is_active"])
        self.active.refresh_from_db()
        self.assertTrue(self.active.is_active)

        dashboard = get_admin_dashboard_live()
        self.assertEqual(dashboard["overdue_amount"], "40.00")
        count, total, owing = overdue_active_children_summary([self.family.pk])
        self.assertEqual(total, Decimal("40.00"))
        self.assertEqual(owing[self.family.pk], Decimal("40.00"))

    def test_credit_is_not_overdue_after_sibling_is_made_inactive(self):
        post_credit(self.family, self.active.name, "12.00", date(2026, 9, 9), "Scholarship")
        self._charge(self.inactive, "40.00", "Weekly tuition")
        set_child_active(self.inactive, False)
        dashboard = get_admin_dashboard_live()
        self.assertEqual(dashboard["overdue_families"], 0)
        self.assertEqual(dashboard["overdue_amount"], "0.00")
        units = {row["slug"]: row for row in unit_balance_summary()}
        self.assertEqual(units["school-18"]["overdue"], "0.00")
        self.assertEqual(child_balance(self.active), Decimal("0.00"))
        self.assertEqual(child_balance(self.inactive), Decimal("28.00"))
        self.assertFalse(units["school-18"]["has_credit"])
