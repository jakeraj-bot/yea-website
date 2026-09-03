"""Helpers for staff/admin family tables — one row per child."""

from collections import defaultdict
from decimal import Decimal

from .demo_data import FAMILIES_BILLING

DEMO_CHILD_SCHOOLS = {
    "Jordan Jacobs": "Paterson School 18",
    "Maya Jacobs": "Paterson School 18",
    "Sofia Martinez": "Paterson School 18",
    "Aiden Williams": "Paterson School 26",
    "Olivia Williams": "Paterson School 26",
    "Ethan Chen": "Paterson School 18",
    "Amari Johnson": "Paterson School 18",
    "Layla Thompson": "Paterson School 26",
    "Nia Patel": "Paterson School 18",
    "Marcus Lee": "Paterson School 26",
}


def child_balance_map(family):
    from .models import PortalLedgerEntry

    balances = defaultdict(lambda: Decimal("0"))
    for entry in PortalLedgerEntry.objects.filter(family=family):
        name = (entry.child_name or "").strip()
        balances[name] += entry.amount
    return balances


def expand_family_record(base_row, children_specs, family_balance):
    """Turn one family dict into one table row per child."""
    family_balance = format(Decimal(str(family_balance)), ".2f")
    if not children_specs:
        return [
            {
                **base_row,
                "child_name": "—",
                "child_id": None,
                "application_id": None,
                "school": "—",
                "child_balance": "0.00",
                "family_balance": family_balance,
                "balance": family_balance,
                "is_first_child": True,
            }
        ]

    rows = []
    for index, child in enumerate(children_specs):
        child_balance = child.get("balance", "0.00")
        if not isinstance(child_balance, str):
            child_balance = format(Decimal(str(child_balance)), ".2f")
        rows.append(
            {
                **base_row,
                "child_name": child["name"],
                "child_id": child.get("child_id"),
                "application_id": child.get("application_id"),
                "school": child.get("school") or "—",
                "child_balance": child_balance,
                "family_balance": family_balance,
                "balance": family_balance,
                "is_first_child": index == 0,
            }
        )
    return rows


def expand_demo_families(families):
    rows = []
    for family in families:
        slug = family["slug"]
        billing = FAMILIES_BILLING.get(slug, {})
        child_balance_lookup = {child["name"]: child["balance"] for child in billing.get("children", [])}
        children_specs = [
            {
                "name": name,
                "school": DEMO_CHILD_SCHOOLS.get(name, "—"),
                "balance": child_balance_lookup.get(name, "0.00"),
            }
            for name in family.get("children", [])
        ]
        base = {key: value for key, value in family.items() if key != "children"}
        rows.extend(expand_family_record(base, children_specs, family["balance"]))
    return rows
