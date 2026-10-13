"""Admin overdue/outstanding numbers drop when parents pay tuition."""

from datetime import date
from decimal import Decimal

from django.test import TestCase

from portal.admin_reports import build_admin_report
from portal.admin_services import get_admin_alerts_live, get_admin_dashboard_live, get_member_families_live
from portal.agency_services import balances_report_rows
from portal.billing_services import post_charge, post_payment
from portal.family_list import child_balance, family_balance, live_family_child_rows, prefetch_family_table_queryset
from portal.models import PortalChild, PortalFamily, PortalPayment, PortalUnit
from portal.owed_weeks import families_with_balance, owed_weeks_report
from portal.parent_services import record_successful_payment
from portal.staff_services import build_dashboard_live


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
        return build_admin_report("balances", {})

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

    def test_family_level_payment_reduces_each_child_overdue_row(self):
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
        self.assertLess(Decimal(by_child["Jordan Jacobs"]["balance"]), Decimal("35.00"))
        self.assertLess(Decimal(by_child["Maya Jacobs"]["balance"]), Decimal("45.00"))
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
