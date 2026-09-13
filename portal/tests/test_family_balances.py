"""Child and family balances follow the ledger on All families and Plans."""

from datetime import date
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from portal.admin_services import get_admin_families_live
from portal.attendance_service import families_for_staff
from portal.billing_services import (
    delete_ledger_entry,
    post_charge,
    post_credit,
    post_payment,
    prepare_billing_for_staff,
)
from portal.family_list import child_balance_map, household_balance, live_family_child_rows
from portal.models import PortalChild, PortalFamily, PortalLedgerEntry, PortalPayment, PortalUnit
from portal.parent_services import get_billing_live, record_successful_payment


class FamilyChildBalanceTests(TestCase):
    def setUp(self):
        self.unit = PortalUnit.objects.create(slug="school-18", name="School 18", is_active=True)
        self.family = PortalFamily.objects.create(
            unit=self.unit,
            slug="rivera",
            name="Rivera",
            primary_contact="Ada Rivera",
            balance=Decimal("0.00"),
            status="Active",
        )
        self.child = PortalChild.objects.create(
            family=self.family,
            name="Ada Rivera",
            school="School 18",
            is_active=True,
        )

    def _list_row(self):
        rows = families_for_staff(self.unit)
        return next(row for row in rows if row["slug"] == "rivera" and row["child_name"] == "Ada Rivera")

    def _plans(self):
        return get_billing_live(self.family)

    def test_charge_then_payment_updates_list_and_plans(self):
        post_charge(
            self.family,
            "Ada Rivera",
            "tuition",
            "40.00",
            date(2026, 9, 1),
            "Weekly tuition",
            notify=False,
        )
        self.family.refresh_from_db()
        row = self._list_row()
        plans = self._plans()
        child = next(item for item in plans["children"] if item["name"] == "Ada Rivera")
        self.assertEqual(row["child_balance"], "40.00")
        self.assertEqual(row["family_balance"], "40.00")
        self.assertEqual(child["balance"], "40.00")
        self.assertEqual(plans["running_balance"], "40.00")
        self.assertEqual(self.family.balance, Decimal("40.00"))

        post_payment(
            self.family,
            "Ada Rivera",
            "15.00",
            date(2026, 9, 2),
            "Cash",
            "In-person payment — Cash",
        )
        self.family.refresh_from_db()
        row = self._list_row()
        plans = self._plans()
        child = next(item for item in plans["children"] if item["name"] == "Ada Rivera")
        self.assertEqual(row["child_balance"], "25.00")
        self.assertEqual(row["family_balance"], "25.00")
        self.assertEqual(child["balance"], "25.00")
        self.assertEqual(plans["running_balance"], "25.00")
        self.assertEqual(self.family.balance, Decimal("25.00"))

    def test_check_and_money_order_payments_reduce_balances(self):
        post_charge(
            self.family,
            "Ada Rivera",
            "tuition",
            "50.00",
            date(2026, 9, 1),
            "Weekly tuition",
            notify=False,
        )
        post_payment(
            self.family,
            "Ada Rivera",
            "20.00",
            date(2026, 9, 3),
            "Check",
            "Check payment",
            "1001",
        )
        post_payment(
            self.family,
            "Ada Rivera",
            "10.00",
            date(2026, 9, 4),
            "Money order",
            "Money order payment",
            "555",
        )
        row = self._list_row()
        plans = self._plans()
        child = next(item for item in plans["children"] if item["name"] == "Ada Rivera")
        self.assertEqual(row["child_balance"], "20.00")
        self.assertEqual(row["family_balance"], "20.00")
        self.assertEqual(child["balance"], "20.00")
        self.assertEqual(plans["running_balance"], "20.00")

    def test_stripe_fee_does_not_inflate_balance(self):
        post_charge(
            self.family,
            "Ada Rivera",
            "tuition",
            "80.00",
            date(2026, 9, 1),
            "Weekly tuition",
            notify=False,
        )
        payment = PortalPayment.objects.create(
            family=self.family,
            amount=Decimal("80.00"),
            fee_amount=Decimal("2.62"),
            total_charged=Decimal("82.62"),
            payment_kind="balance",
            dropin_child="Ada Rivera",
            stripe_session_id="cs_balance_fee",
            stripe_payment_intent_id="pi_balance_fee",
        )
        record_successful_payment(payment, method_label="Visa ending 4242", child_name="Ada Rivera")
        self.family.refresh_from_db()
        row = self._list_row()
        plans = self._plans()
        child = next(item for item in plans["children"] if item["name"] == "Ada Rivera")
        self.assertEqual(row["child_balance"], "0.00")
        self.assertEqual(row["family_balance"], "0.00")
        self.assertEqual(child["balance"], "0.00")
        self.assertEqual(plans["running_balance"], "0.00")
        self.assertEqual(self.family.balance, Decimal("0.00"))
        entry = PortalLedgerEntry.objects.get(family=self.family, entry_type="payment")
        self.assertEqual(entry.amount, Decimal("-80.00"))
        self.assertEqual(entry.fee_amount, Decimal("2.62"))
        staff_billing = prepare_billing_for_staff(self.family, {"can_delete_charge": False})
        pay_row = next(item for item in staff_billing["ledger"] if item["type"] == "payment")
        self.assertEqual(pay_row["amount"], "82.62")
        self.assertEqual(pay_row["fee"], "2.62")
        self.assertEqual(pay_row["applied"], "80.00")

    def test_stale_cached_family_balance_does_not_override_ledger(self):
        PortalLedgerEntry.objects.create(
            family=self.family,
            child_name="Ada Rivera",
            date=date(2026, 9, 1),
            entry_type="charge",
            description="Weekly tuition",
            amount=Decimal("35.00"),
        )
        self.family.balance = Decimal("999.00")
        self.family.save(update_fields=["balance"])

        row = self._list_row()
        plans = self._plans()
        child = next(item for item in plans["children"] if item["name"] == "Ada Rivera")
        self.assertEqual(row["child_balance"], "35.00")
        self.assertEqual(row["family_balance"], "35.00")
        self.assertEqual(child["balance"], "35.00")
        self.assertEqual(plans["running_balance"], "35.00")

    def test_delete_charge_after_payment_follows_ledger(self):
        charge = post_charge(
            self.family,
            "Ada Rivera",
            "tuition",
            "40.00",
            date(2026, 9, 1),
            "Weekly tuition",
            notify=False,
        )
        post_payment(
            self.family,
            "Ada Rivera",
            "40.00",
            date(2026, 9, 2),
            "Cash",
            "Cash",
        )
        delete_ledger_entry(self.family, charge.pk)
        self.family.refresh_from_db()
        row = self._list_row()
        plans = self._plans()
        child = next(item for item in plans["children"] if item["name"] == "Ada Rivera")
        self.assertEqual(row["child_balance"], "-40.00")
        self.assertEqual(row["family_balance"], "-40.00")
        self.assertEqual(child["balance"], "-40.00")
        self.assertEqual(plans["running_balance"], "-40.00")
        self.assertEqual(self.family.balance, Decimal("-40.00"))

    def test_credit_reduces_child_and_family_balance(self):
        post_charge(
            self.family,
            "Ada Rivera",
            "tuition",
            "30.00",
            date(2026, 9, 1),
            "Weekly tuition",
            notify=False,
        )
        post_credit(self.family, "Ada Rivera", "5.00", date(2026, 9, 2), "Goodwill")
        row = self._list_row()
        plans = self._plans()
        child = next(item for item in plans["children"] if item["name"] == "Ada Rivera")
        self.assertEqual(row["child_balance"], "25.00")
        self.assertEqual(row["family_balance"], "25.00")
        self.assertEqual(child["balance"], "25.00")


class MultiChildFamilyBalanceTests(TestCase):
    def setUp(self):
        self.unit = PortalUnit.objects.create(slug="school-18", name="School 18", is_active=True)
        self.family = PortalFamily.objects.create(
            unit=self.unit,
            slug="jacobs",
            name="Jacobs",
            primary_contact="Pat Jacobs",
            balance=Decimal("0.00"),
            status="Active",
        )
        self.jordan = PortalChild.objects.create(
            family=self.family, name="Jordan Jacobs", school="School 18", is_active=True
        )
        self.maya = PortalChild.objects.create(
            family=self.family, name="Maya Jacobs", school="School 18", is_active=True
        )

    def test_family_balance_is_ledger_sum_of_both_children(self):
        post_charge(
            self.family,
            "Jordan Jacobs",
            "tuition",
            "35.00",
            date(2026, 9, 1),
            "Jordan tuition",
            notify=False,
        )
        post_charge(
            self.family,
            "Maya Jacobs",
            "tuition",
            "45.00",
            date(2026, 9, 1),
            "Maya tuition",
            notify=False,
        )
        post_payment(
            self.family,
            "Jordan Jacobs",
            "10.00",
            date(2026, 9, 2),
            "Cash",
            "Cash",
        )

        rows = [row for row in get_admin_families_live() if row["slug"] == "jacobs"]
        self.assertEqual(len(rows), 2)
        by_child = {row["child_name"]: row for row in rows}
        self.assertEqual(by_child["Jordan Jacobs"]["child_balance"], "25.00")
        self.assertEqual(by_child["Maya Jacobs"]["child_balance"], "45.00")
        self.assertEqual(by_child["Jordan Jacobs"]["family_balance"], "70.00")
        self.assertEqual(by_child["Maya Jacobs"]["family_balance"], "70.00")

        plans = get_billing_live(self.family)
        plan_by_child = {child["name"]: child for child in plans["children"]}
        self.assertEqual(plan_by_child["Jordan Jacobs"]["balance"], "25.00")
        self.assertEqual(plan_by_child["Maya Jacobs"]["balance"], "45.00")
        self.assertEqual(plans["running_balance"], "70.00")
        self.assertEqual(household_balance(self.family), Decimal("70.00"))
        self.assertEqual(
            sum(child_balance_map(self.family).values(), Decimal("0")),
            Decimal("70.00"),
        )

    def test_whitespace_child_names_still_batch_together(self):
        PortalLedgerEntry.objects.create(
            family=self.family,
            child_name="Jordan Jacobs",
            date=date(2026, 9, 1),
            entry_type="charge",
            description="Tuition",
            amount=Decimal("20.00"),
        )
        PortalLedgerEntry.objects.create(
            family=self.family,
            child_name="Jordan Jacobs ",
            date=date(2026, 9, 2),
            entry_type="charge",
            description="Late fee",
            amount=Decimal("5.00"),
        )
        balances = child_balance_map(self.family)
        self.assertEqual(balances["Jordan Jacobs"], Decimal("25.00"))
        rows = live_family_child_rows([self.family])
        jordan = next(row for row in rows if row["child_name"] == "Jordan Jacobs")
        self.assertEqual(jordan["child_balance"], "25.00")
        self.assertEqual(jordan["family_balance"], "25.00")
