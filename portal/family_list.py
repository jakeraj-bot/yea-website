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


def demo_family_list_rows(area):
    """Same demo rows as the staff/admin Families tables."""
    from .demo_data import ADMIN_MEMBER_FAMILIES, FAMILIES

    if area == "admin":
        families = [
            {
                **row,
                "unit": row.get("unit", "School 18"),
                "unit_slug": row.get("unit_slug", "school-18"),
                "program": row.get("program", "After-School 2026–27"),
                "has_application": row.get("has_application", True),
                "has_parent_login": row.get("has_parent_login", True),
            }
            for row in ADMIN_MEMBER_FAMILIES
        ]
        return expand_demo_families(families)
    return expand_demo_families(FAMILIES)


def child_names_label(names):
    unique = []
    seen = set()
    for name in names or []:
        label = (name.get("name") if isinstance(name, dict) else name) or ""
        label = str(label).strip()
        if not label or label == "—":
            continue
        key = label.lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(label)
    return unique, " · ".join(unique)


def account_child_context(profile=None, family_meta=None, billing=None):
    """Child names for family-account headings so staff can see whose account it is."""
    names = []
    if family_meta and family_meta.get("children"):
        names = family_meta["children"]
    elif profile and profile.get("children"):
        names = profile["children"]
    elif billing and billing.get("children"):
        names = billing["children"]
    unique, label = child_names_label(names)
    family_name = (
        (profile or {}).get("family_name")
        or (family_meta or {}).get("name")
        or (billing or {}).get("family_name")
        or ""
    )
    return {
        "account_child_names": unique,
        "account_child_label": label,
        "account_heading_name": label or family_name,
        "account_family_name": family_name,
    }


def unique_households_from_rows(rows):
    """One household per family, in Families table order (first child row wins)."""
    households = []
    seen = {}
    for row in rows:
        family_id = row.get("id")
        if family_id is not None:
            key = ("id", family_id)
        else:
            key = ("slug", row.get("unit"), row.get("slug"))
        family_name = row.get("name") or row.get("family_name") or row.get("slug")
        if key not in seen:
            household = {
                "id": family_id,
                "slug": row["slug"],
                "family_name": family_name,
                "children": [],
                "name": family_name,
            }
            seen[key] = household
            households.append(household)
        child = (row.get("child_name") or "").strip()
        if child and child != "—" and child not in seen[key]["children"]:
            seen[key]["children"].append(child)
    for household in households:
        if household["children"]:
            household["name"] = " · ".join(household["children"])
    return households


def adjacent_households(households, *, slug, family_id=None):
    """Return (previous, next) household dicts for the current family."""
    index = None
    if family_id not in (None, ""):
        family_id_text = str(family_id)
        for i, household in enumerate(households):
            if household.get("id") is not None and str(household["id"]) == family_id_text:
                index = i
                break
    if index is None:
        for i, household in enumerate(households):
            if household.get("slug") == slug:
                index = i
                break
    if index is None:
        return None, None
    previous = households[index - 1] if index > 0 else None
    nxt = households[index + 1] if index < len(households) - 1 else None
    return previous, nxt
