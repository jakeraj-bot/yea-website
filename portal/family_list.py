"""Helpers for staff/admin family tables — one row per child."""

from collections import defaultdict
from decimal import Decimal
from urllib.parse import urlencode

from .demo_data import FAMILIES_BILLING

DEFAULT_LIST_SORT = "child-asc"
LIST_NAV_SESSION_KEY = "yea_family_list_nav"

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


def _name_sort_key(value):
    return (value or "").casefold()


def sort_family_child_rows(rows):
    """Child name A–Z (case-insensitive). First child in each household keeps the action row."""
    sorted_rows = sorted(
        rows,
        key=lambda row: (
            _name_sort_key(row.get("child_name")),
            _name_sort_key(row.get("name")),
            row.get("slug") or "",
            row.get("id") or 0,
        ),
    )
    seen = set()
    for row in sorted_rows:
        family_id = row.get("id")
        if family_id is not None:
            key = ("id", family_id)
        else:
            key = ("slug", row.get("unit"), row.get("slug"))
        row["is_first_child"] = key not in seen
        seen.add(key)
    return sorted_rows


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

    ordered_children = sorted(children_specs, key=lambda child: _name_sort_key(child.get("name")))
    rows = []
    for index, child in enumerate(ordered_children):
        child_balance = child.get("balance", "0.00")
        if not isinstance(child_balance, str):
            child_balance = format(Decimal(str(child_balance)), ".2f")
        row = {
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
        if child.get("unit"):
            row["unit"] = child["unit"]
        if child.get("unit_slug"):
            row["unit_slug"] = child["unit_slug"]
        rows.append(row)
    return rows


def expand_demo_families(families):
    rows = []
    for family in sorted(families, key=lambda item: _name_sort_key(item.get("name"))):
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
    return sort_family_child_rows(rows)


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


def _row_text(*values):
    return " ".join(str(value or "") for value in values).casefold()


def _row_balance(row, *keys):
    for key in keys:
        raw = row.get(key)
        if raw in (None, ""):
            continue
        try:
            return float(str(raw).replace("$", "").replace(",", ""))
        except (TypeError, ValueError):
            continue
    return 0.0


def parse_family_list_nav(query):
    """Read Families-table filters from a QueryDict or mapping."""
    get = query.get
    return {
        "q": (get("q") or "").strip(),
        "unit": (get("unit") or "all").strip() or "all",
        "ff": (get("ff") or get("filter") or "all").strip() or "all",
        "sort": (get("sort") or DEFAULT_LIST_SORT).strip() or DEFAULT_LIST_SORT,
        "school": (get("school") or "").strip(),
        "child_id": (get("child_id") or "").strip(),
        "child": (get("child") or "").strip(),
        "from_list": get("list") == "1",
    }


def family_list_nav_filters(nav):
    return {
        "q": (nav.get("q") or "").strip(),
        "unit": (nav.get("unit") or "all") or "all",
        "ff": (nav.get("ff") or "all") or "all",
        "sort": (nav.get("sort") or DEFAULT_LIST_SORT) or DEFAULT_LIST_SORT,
        "school": (nav.get("school") or "").strip(),
    }


def has_active_list_filters(nav):
    return bool(
        (nav.get("q") or "").strip()
        or (nav.get("school") or "").strip()
        or (nav.get("unit") or "all") not in ("", "all")
        or (nav.get("ff") or "all") not in ("", "all")
        or (nav.get("sort") or DEFAULT_LIST_SORT) not in ("", DEFAULT_LIST_SORT)
    )


def resolve_family_list_nav(request, area):
    """Query-string list context, with session backup while moving between account pages."""
    nav = parse_family_list_nav(request.GET)
    session_key = f"{LIST_NAV_SESSION_KEY}_{area}"
    referer = request.META.get("HTTP_REFERER") or ""
    from_family_page = "/family/" in referer or "parent-preview" in referer

    if nav["from_list"] or has_active_list_filters(nav):
        request.session[session_key] = family_list_nav_filters(nav)
        return nav

    saved = request.session.get(session_key)
    if saved and from_family_page:
        return {
            **parse_family_list_nav({}),
            **saved,
            "child_id": nav["child_id"],
            "child": nav["child"],
            "from_list": True,
        }

    if session_key in request.session and not from_family_page:
        del request.session[session_key]
    return nav


def row_matches_list_nav(row, nav):
    """Same matching rules as static/js/staff-families-table.js."""
    nav = nav or {}
    unit = nav.get("unit") or "all"
    if unit and unit != "all":
        unit_slug = str(row.get("unit_slug") or "")
        unit_name = str(row.get("unit") or "").casefold()
        if unit_slug != unit and unit.casefold() not in unit_name:
            return False

    school = (nav.get("school") or "").strip()
    if school:
        if school.casefold() not in str(row.get("school") or "").casefold():
            return False

    query = (nav.get("q") or "").strip().casefold()
    if query:
        haystack = _row_text(
            row.get("unit"),
            row.get("name"),
            row.get("primary_contact"),
            row.get("child_name"),
            row.get("school"),
            row.get("program"),
            row.get("billing_type"),
            row.get("status"),
        )
        if query not in haystack:
            return False

    status = str(row.get("status") or "").casefold()
    billing = str(row.get("billing_type") or "").casefold()
    balance = _row_balance(row, "family_balance", "balance")
    ff = nav.get("ff") or "all"
    if ff == "active":
        return "active" in status and "pending" not in status
    if ff == "pending-enrollment":
        return "pending enrollment" in status
    if ff == "past-due":
        return balance > 0
    if ff == "4cs":
        return "4cs" in billing
    if ff == "private-pay":
        return "private" in billing
    if ff == "pending-membership":
        return "pending membership" in status
    if ff == "no-application":
        return not row.get("has_application")
    if ff == "no-login":
        return not row.get("has_parent_login")
    if ff == "suspended":
        return "suspended" in status
    return True


def sort_family_list_rows(rows, sort=None):
    """Match the Families table sort control. Default is child name A–Z."""
    rows = list(rows)
    sort = sort or DEFAULT_LIST_SORT

    def name_key(value):
        return (value or "").casefold()

    if sort == "child-desc":
        rows.sort(key=lambda row: name_key(row.get("name")))
        rows.sort(key=lambda row: name_key(row.get("child_name")), reverse=True)
    elif sort == "name-asc":
        rows.sort(key=lambda row: name_key(row.get("child_name")))
        rows.sort(key=lambda row: name_key(row.get("name")))
    elif sort == "name-desc":
        rows.sort(key=lambda row: name_key(row.get("child_name")))
        rows.sort(key=lambda row: name_key(row.get("name")), reverse=True)
    elif sort == "unit-asc":
        rows.sort(key=lambda row: (name_key(row.get("child_name")), name_key(row.get("name"))))
        rows.sort(key=lambda row: name_key(row.get("unit")))
    elif sort == "unit-desc":
        rows.sort(key=lambda row: (name_key(row.get("child_name")), name_key(row.get("name"))))
        rows.sort(key=lambda row: name_key(row.get("unit")), reverse=True)
    elif sort == "balance-desc":
        rows.sort(key=lambda row: (name_key(row.get("child_name")), name_key(row.get("name"))))
        rows.sort(key=lambda row: _row_balance(row, "family_balance", "balance"), reverse=True)
    elif sort == "balance-asc":
        rows.sort(key=lambda row: (name_key(row.get("child_name")), name_key(row.get("name"))))
        rows.sort(key=lambda row: _row_balance(row, "family_balance", "balance"))
    elif sort == "child-balance-desc":
        rows.sort(key=lambda row: (name_key(row.get("child_name")), name_key(row.get("name"))))
        rows.sort(key=lambda row: _row_balance(row, "child_balance"), reverse=True)
    elif sort == "child-balance-asc":
        rows.sort(key=lambda row: (name_key(row.get("child_name")), name_key(row.get("name"))))
        rows.sort(key=lambda row: _row_balance(row, "child_balance"))
    elif sort == "contact-asc":
        rows.sort(key=lambda row: (name_key(row.get("child_name")), name_key(row.get("name"))))
        rows.sort(key=lambda row: name_key(row.get("primary_contact")))
    else:
        rows.sort(
            key=lambda row: (
                name_key(row.get("child_name")),
                name_key(row.get("name")),
                row.get("slug") or "",
                row.get("id") or 0,
            )
        )
    return rows


def apply_family_list_nav(rows, nav):
    """Filter and sort child rows the same way the Families table does."""
    nav = nav or {}
    matched = [row for row in rows if row_matches_list_nav(row, nav)]
    return sort_family_list_rows(matched, nav.get("sort") or DEFAULT_LIST_SORT)


def _family_row_match(row, *, slug, family_id=None):
    family_id_text = str(family_id) if family_id not in (None, "") else ""
    if family_id_text and row.get("id") is not None and str(row.get("id")) == family_id_text:
        return True
    if family_id_text:
        return False
    return row.get("slug") == slug


def find_child_row_index(rows, *, slug, family_id=None, child_id=None, child_name=None):
    """Position of the opened child row in the (already filtered) list."""
    child_id_text = str(child_id) if child_id not in (None, "") else ""
    child_name_folded = (child_name or "").strip().casefold()

    if child_id_text:
        for index, row in enumerate(rows):
            if row.get("child_id") is not None and str(row.get("child_id")) == child_id_text:
                return index
    if child_name_folded:
        for index, row in enumerate(rows):
            if _family_row_match(row, slug=slug, family_id=family_id) and (
                row.get("child_name") or ""
            ).strip().casefold() == child_name_folded:
                return index
        for index, row in enumerate(rows):
            if (row.get("child_name") or "").strip().casefold() == child_name_folded:
                return index
    for index, row in enumerate(rows):
        if _family_row_match(row, slug=slug, family_id=family_id):
            return index
    if slug:
        for index, row in enumerate(rows):
            if row.get("slug") == slug:
                return index
    return None


def adjacent_child_rows(rows, *, slug, family_id=None, child_id=None, child_name=None):
    """Return (previous row, next row, 1-based index, count) for a child row."""
    index = find_child_row_index(
        rows,
        slug=slug,
        family_id=family_id,
        child_id=child_id,
        child_name=child_name,
    )
    if index is None:
        return None, None, 0, len(rows)
    previous = rows[index - 1] if index > 0 else None
    nxt = rows[index + 1] if index < len(rows) - 1 else None
    return previous, nxt, index + 1, len(rows)


def child_row_nav_name(row):
    child = (row.get("child_name") or "").strip()
    if child and child != "—":
        return child
    return row.get("name") or row.get("family_name") or row.get("slug")


def family_list_querystring(nav, *, family_id=None, child_id=None, child_name=None, include_list_flag=True):
    """Query string that keeps Families-table filters on the account pager."""
    items = []
    if family_id not in (None, ""):
        items.append(("id", str(family_id)))
    if child_id not in (None, ""):
        items.append(("child_id", str(child_id)))
    child_label = (child_name or "").strip()
    if child_label and child_label != "—":
        items.append(("child", child_label))
    if nav:
        query = (nav.get("q") or "").strip()
        if query:
            items.append(("q", query))
        school = (nav.get("school") or "").strip()
        if school:
            items.append(("school", school))
        unit = nav.get("unit") or "all"
        if unit not in ("", "all"):
            items.append(("unit", unit))
        ff = nav.get("ff") or "all"
        if ff not in ("", "all"):
            items.append(("ff", ff))
        sort = nav.get("sort") or DEFAULT_LIST_SORT
        if sort not in ("", DEFAULT_LIST_SORT):
            items.append(("sort", sort))
        if include_list_flag and (nav.get("from_list") or has_active_list_filters(nav)):
            items.append(("list", "1"))
    return urlencode(items)
