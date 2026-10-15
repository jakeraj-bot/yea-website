"""Household payments cover the oldest unpaid charges first, not a sibling split."""

from datetime import date
from decimal import Decimal

from django.test import TestCase

from portal.admin_reports import build_admin_report
from portal.billing_services import post_charge, post_payment, prepare_billing_for_staff
from portal.family_list import (
    child_balance,
    family_balance,
    fifo_allocate_family_entries,
)
from portal.models import PortalChild, PortalFamily, PortalLedgerEntry, PortalUnit
from portal.owed_weeks import unpaid_charges_by_child, unpaid_charges_for_child
from portal.parent_services import get_billing_live


class FifoPaymentOldestChargesTests(TestCase):
    """Julie/Marvin Bisono-style: $20 membership on 9/8 must not survive a later family payment."""

    def setUp(self):
        self.unit = PortalUnit.objects.create(slug="school-18", name="School 18", is_active=True)
        self.family = PortalFamily.objects.create(
            unit=self.unit,
            slug="bisono",
            name="Bisono",
            billing_type="Private pay",
            status="Active",
        )
        self.marvin = PortalChild.objects.create(
            family=self.family,
            name="Marvin Bisono",
            school="School 18",
            is_active=True,
        )
        self.julie = PortalChild.objects.create(
            family=self.family,
            name="Julie Bisono",
            school="School 18",
            is_active=True,
        )

    def _report_row(self, child_name):
        report = build_admin_report("balances", {"status": "Active"})
        return next(row for row in report["rows"] if row["child"] == child_name)

    def _child_live(self, child_name):
        billing = get_billing_live(self.family)
        child = next(item for item in billing["children"] if item["name"] == child_name)
        return child, billing

    def _post_bisono_ledger(self):
        """Marvin $20 membership 9/8; Julie later charges; mom pays $165 on 9/28."""
        PortalLedgerEntry.objects.create(
            family=self.family,
            child_name="Marvin Bisono",
            date=date(2026, 9, 8),
            entry_type="membership",
            description="Membership fee ($20.00) — Marvin Bisono",
            amount=Decimal("20.00"),
            is_manual=True,
        )
        post_charge(
            self.family,
            "Julie Bisono",
            "tuition",
            "70.00",
            date(2026, 9, 10),
            "CC WK 2 - weekly charge — Julie Bisono",
            notify=False,
        )
        post_charge(
            self.family,
            "Julie Bisono",
            "tuition",
            "70.00",
            date(2026, 9, 17),
            "CC WK 3 - weekly charge — Julie Bisono",
            notify=False,
        )
        post_charge(
            self.family,
            "Julie Bisono",
            "tuition",
            "92.80",
            date(2026, 9, 24),
            "CC WK 4 - weekly charge — Julie Bisono",
            notify=False,
        )
        PortalLedgerEntry.objects.create(
            family=self.family,
            child_name="",
            date=date(2026, 9, 28),
            entry_type="payment",
            description="Family payment 9/28",
            amount=Decimal("-165.00"),
            is_manual=True,
        )

    def test_family_payment_zeros_older_membership_and_leaves_sibling_remainder(self):
        self._post_bisono_ledger()
        # $20 + $70 + $70 + $92.80 = $252.80 charged; $165 paid → $87.80 leftover.
        self.assertEqual(family_balance(self.family), Decimal("87.80"))
        self.assertEqual(child_balance(self.marvin), Decimal("0.00"))
        self.assertEqual(child_balance(self.julie), Decimal("87.80"))

        marvin_live, billing = self._child_live("Marvin Bisono")
        julie_live, _ = self._child_live("Julie Bisono")
        self.assertEqual(marvin_live["balance"], "0.00")
        self.assertEqual(julie_live["balance"], "87.80")
        self.assertEqual(billing["running_balance"], "87.80")

        marvin_row = self._report_row("Marvin Bisono")
        julie_row = self._report_row("Julie Bisono")
        self.assertEqual(marvin_row["amount_owe"], "0.00")
        self.assertEqual(marvin_row["amount_owe"], marvin_live["balance"])
        self.assertEqual(marvin_row["description"], "")
        self.assertNotIn("Membership", marvin_row["description"])
        self.assertEqual(julie_row["amount_owe"], "87.80")
        self.assertEqual(julie_row["amount_owe"], julie_live["balance"])
        self.assertEqual(julie_row["amount_owe"], billing["running_balance"])
        self.assertIn("CC WK 4 - weekly charge — Julie Bisono", julie_row["description"])
        self.assertNotIn("Membership fee ($20.00) — Marvin Bisono", julie_row["description"])

        entries = list(PortalLedgerEntry.objects.filter(family=self.family).order_by("date", "pk"))
        self.assertEqual(unpaid_charges_for_child(entries, "Marvin Bisono"), [])
        julie_unpaid = unpaid_charges_for_child(entries, "Julie Bisono")
        self.assertTrue(julie_unpaid)
        self.assertEqual(sum((row["remaining"] for row in julie_unpaid), Decimal("0")), Decimal("87.80"))

    def test_does_not_split_membership_after_older_charges_are_covered(self):
        self._post_bisono_ledger()
        # Proportional leftover would leave Marvin ~$6.95 still owing membership.
        self.assertNotEqual(child_balance(self.marvin), Decimal("6.95"))
        self.assertEqual(child_balance(self.marvin), Decimal("0.00"))
        marvin_row = self._report_row("Marvin Bisono")
        self.assertEqual(marvin_row["amount_owe"], "0.00")
        self.assertEqual(marvin_row["description"], "")

    def test_older_julie_charges_are_paid_before_later_julie_but_marvin_membership_still_clears(self):
        post_charge(
            self.family,
            "Julie Bisono",
            "tuition",
            "40.00",
            date(2026, 9, 1),
            "CC WK 1 - weekly charge — Julie Bisono",
            notify=False,
        )
        PortalLedgerEntry.objects.create(
            family=self.family,
            child_name="Marvin Bisono",
            date=date(2026, 9, 8),
            entry_type="membership",
            description="Membership fee ($20.00) — Marvin Bisono",
            amount=Decimal("20.00"),
            is_manual=True,
        )
        post_charge(
            self.family,
            "Julie Bisono",
            "tuition",
            "192.80",
            date(2026, 9, 15),
            "CC WK 3 - weekly charge — Julie Bisono",
            notify=False,
        )
        post_payment(self.family, "", "165.00", date(2026, 9, 28), "Cash", "Mom paid 9/28")

        # $40 (Julie 9/1) + $20 (Marvin 9/8) + $105 of Julie 9/15 = $165.
        self.assertEqual(child_balance(self.marvin), Decimal("0.00"))
        self.assertEqual(child_balance(self.julie), Decimal("87.80"))
        self.assertEqual(family_balance(self.family), Decimal("87.80"))
        marvin_row = self._report_row("Marvin Bisono")
        julie_row = self._report_row("Julie Bisono")
        self.assertEqual(marvin_row["amount_owe"], "0.00")
        self.assertEqual(marvin_row["description"], "")
        self.assertEqual(julie_row["amount_owe"], "87.80")
        self.assertIn("CC WK 3 - weekly charge — Julie Bisono", julie_row["description"])
        self.assertNotIn("CC WK 1 - weekly charge — Julie Bisono", julie_row["description"])

    def test_named_payment_stays_on_that_child(self):
        post_charge(
            self.family,
            "Marvin Bisono",
            "tuition",
            "20.00",
            date(2026, 9, 8),
            "Membership fee ($20.00) — Marvin Bisono",
            notify=False,
        )
        post_charge(
            self.family,
            "Julie Bisono",
            "tuition",
            "80.00",
            date(2026, 9, 10),
            "CC WK 2 - weekly charge — Julie Bisono",
            notify=False,
        )
        post_payment(self.family, "Julie Bisono", "80.00", date(2026, 9, 28), "Cash")
        self.assertEqual(child_balance(self.marvin), Decimal("20.00"))
        self.assertEqual(child_balance(self.julie), Decimal("0.00"))
        self.assertEqual(family_balance(self.family), Decimal("20.00"))

    def test_account_balance_matches_billing_per_child_after_fifo(self):
        self._post_bisono_ledger()
        staff = prepare_billing_for_staff(self.family, {"can_delete_charge": True})
        marvin_live, billing = self._child_live("Marvin Bisono")
        julie_live, _ = self._child_live("Julie Bisono")
        marvin_row = self._report_row("Marvin Bisono")
        julie_row = self._report_row("Julie Bisono")
        self.assertEqual(marvin_row["amount_owe"], marvin_live["balance"])
        self.assertEqual(julie_row["amount_owe"], julie_live["balance"])
        self.assertEqual(staff["running_balance"], billing["running_balance"])
        self.assertEqual(staff["running_balance"], "87.80")
        self.assertEqual(staff["ledger"][0]["running_balance"], "87.80")

    def test_fifo_allocate_covers_oldest_charge_id_on_same_date(self):
        first = PortalLedgerEntry.objects.create(
            family=self.family,
            child_name="Marvin Bisono",
            date=date(2026, 9, 8),
            entry_type="charge",
            description="Older Marvin line",
            amount=Decimal("20.00"),
        )
        second = PortalLedgerEntry.objects.create(
            family=self.family,
            child_name="Julie Bisono",
            date=date(2026, 9, 8),
            entry_type="charge",
            description="Same-day Julie line",
            amount=Decimal("40.00"),
        )
        PortalLedgerEntry.objects.create(
            family=self.family,
            child_name="",
            date=date(2026, 9, 9),
            entry_type="payment",
            description="Family $20",
            amount=Decimal("-20.00"),
        )
        entries = list(PortalLedgerEntry.objects.filter(family=self.family))
        state = fifo_allocate_family_entries(entries, ["Marvin Bisono", "Julie Bisono"])
        self.assertEqual(state["balances"]["Marvin Bisono"], Decimal("0.00"))
        self.assertEqual(state["balances"]["Julie Bisono"], Decimal("40.00"))
        unpaid = unpaid_charges_by_child(entries)
        self.assertEqual(unpaid.get("marvin bisono", []), [])
        self.assertEqual(unpaid["julie bisono"][0]["id"], second.pk)
        self.assertEqual(unpaid["julie bisono"][0]["remaining"], Decimal("40.00"))
        self.assertLess(first.pk, second.pk)
