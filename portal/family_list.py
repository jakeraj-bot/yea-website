"""Helpers for staff/admin family tables — one row per child."""

from collections import defaultdict
from decimal import ROUND_DOWN, Decimal
from urllib.parse import urlencode

from .child_identity import child_name_in_collection
from .demo_data import FAMILIES_BILLING

DEFAULT_LIST_SORT = "child-asc"
LIST_NAV_SESSION_KEY = "yea_family_list_nav"

APPROVED_APPLICATION_STATUSES = frozenset({"approved", "enrolled"})
PENDING_REVIEW_STATUSES = frozenset({"under_review", "pending_documents"})
WAITLIST_APPLICATION_STATUS = "waitlist"

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


def _normalize_child_name(name):
    return (name or "").strip()


def _child_name_key(name):
    return _normalize_child_name(name).casefold()


def _as_decimal(value):
    if value in (None, ""):
        return Decimal("0")
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def household_ledger_totals(family_ids):
    """{family_id: Decimal} household net — every ledger amount, fees excluded.

    Family balance uses this total. It is not the sum of the child-balance column.
    """
    from django.db.models import Sum

    from .models import PortalLedgerEntry

    totals = {}
    ids = [pk for pk in family_ids if pk]
    if not ids:
        return totals
    for row in (
        PortalLedgerEntry.objects.filter(family_id__in=ids)
        .values("family_id")
        .annotate(total=Sum("amount"))
    ):
        totals[row["family_id"]] = row["total"] or Decimal("0")
    return totals


def household_balance_from_child_map(family_balances):
    """Sum of a per-child map. Prefer household_ledger_totals for family display."""
    if not family_balances:
        return Decimal("0")
    return sum(family_balances.values(), Decimal("0"))


def family_balance_from_names(family_balances, child_names):
    """Named children's balances after unallocated household payments are applied."""
    return sum((child_balance_from_map(family_balances, name) for name in child_names or []), Decimal("0"))


def _map_key_for_name(family_map, child_name):
    name = _normalize_child_name(child_name)
    if name in family_map:
        return name
    folded = _child_name_key(name)
    for key in family_map:
        if _child_name_key(key) == folded:
            return key
    return name


def _split_amount(amount, count):
    """Split cents across ``count`` people; the last share gets any leftover penny."""
    if count <= 0 or amount == 0:
        return []
    share = (amount / count).quantize(Decimal("0.01"), rounding=ROUND_DOWN)
    parts = [share] * (count - 1)
    parts.append(amount - share * (count - 1))
    return parts


def allocate_unlabeled_to_children(family_map, child_names):
    """Update child balances only: apply family-level payments to kids who still owe.

    Charge rows keep their child names. A payment with an empty child column is
    tuition only (Stripe fees stay in ``fee_amount``). Family balance is computed
    separately from the full household ledger.
    """
    if family_map is None:
        return family_map
    unlabeled = Decimal("0")
    for key in [item for item in family_map if not _normalize_child_name(item)]:
        unlabeled += family_map.pop(key) or Decimal("0")

    keys = []
    seen = set()
    for name in child_names or []:
        key = _map_key_for_name(family_map, name)
        folded = _child_name_key(key)
        if not folded or folded in seen:
            continue
        seen.add(folded)
        keys.append(key)
        family_map.setdefault(key, Decimal("0"))

    if not keys:
        if unlabeled:
            family_map[""] = unlabeled
        return family_map
    if unlabeled == 0:
        return family_map

    if unlabeled < 0:
        remaining = -unlabeled
        owing = [key for key in keys if family_map[key] > 0]
        total_owing = sum((family_map[key] for key in owing), Decimal("0"))
        if owing and remaining > 0:
            if remaining >= total_owing:
                for key in owing:
                    remaining -= family_map[key]
                    family_map[key] = Decimal("0")
            else:
                applied = Decimal("0")
                for index, key in enumerate(owing):
                    share = remaining - applied if index == len(owing) - 1 else (family_map[key] * remaining / total_owing).quantize(
                        Decimal("0.01"), rounding=ROUND_DOWN
                    )
                    family_map[key] -= share
                    applied += share
                remaining = Decimal("0")
        if remaining > 0:
            for key, share in zip(keys, _split_amount(-remaining, len(keys))):
                family_map[key] += share
    else:
        for key, share in zip(keys, _split_amount(unlabeled, len(keys))):
            family_map[key] += share
    return family_map


def child_balance_from_map(family_balances, child_name):
    if not family_balances:
        return Decimal("0")
    name = _normalize_child_name(child_name)
    if name in family_balances:
        return family_balances[name] or Decimal("0")
    folded = _child_name_key(name)
    for key, amount in family_balances.items():
        if _child_name_key(key) == folded:
            return amount or Decimal("0")
    return Decimal("0")


def child_balance_map(family):
    maps = child_balance_maps([family.pk] if family and family.pk else [])
    return maps.get(getattr(family, "pk", None), defaultdict(lambda: Decimal("0")))


def _active_child_names(family):
    if not family:
        return []
    cached = getattr(family, "_prefetched_objects_cache", None)
    if cached and "children" in cached:
        return [child.name for child in family.children.all() if getattr(child, "is_active", True)]
    if not getattr(family, "pk", None):
        return []
    return list(family.children.filter(is_active=True).values_list("name", flat=True))


def child_balance(child, balances=None):
    """Ledger balance for one child (tuition/charges minus payments; no Stripe fees)."""
    if child is None:
        return Decimal("0")
    family = getattr(child, "family", None)
    maps = balances if balances is not None else (child_balance_map(family) if family else {})
    return child_balance_from_map(maps, getattr(child, "name", "") or "")


def family_balance(family, balances=None, child_names=None):
    """Household ledger: charges minus tuition payments. Stripe fees excluded.

    Family-level payments (empty child column) are included here. This is not
    the sum of the child-balance column — child balances are updated separately.
    """
    if not family or not getattr(family, "pk", None):
        return Decimal("0")
    return household_ledger_totals([family.pk]).get(family.pk, Decimal("0"))


def household_balance(family):
    """Ledger total for one household. Same rules as family_balance()."""
    return family_balance(family)


def sync_family_balance_from_ledger(family):
    """Keep PortalFamily.balance equal to the household ledger (tuition only)."""
    if not family or not getattr(family, "pk", None):
        return Decimal("0")
    total = family_balance(family)
    if family.balance != total:
        family.balance = total
        family.save(update_fields=["balance"])
    return total


def child_balance_maps(family_ids):
    """One aggregated ledger query → {family_id: {child_name: Decimal}}.

    Amounts are the ledger ``amount`` (tuition / applied). Stripe processing
    fees live in ``fee_amount`` and are left out of the balance. Rows with no
    child name are then shared across the household's children.
    """
    from django.db.models import Sum

    from .models import PortalChild, PortalLedgerEntry

    maps = defaultdict(lambda: defaultdict(lambda: Decimal("0")))
    ids = [pk for pk in family_ids if pk]
    if not ids:
        return maps
    for row in (
        PortalLedgerEntry.objects.filter(family_id__in=ids)
        .values("family_id", "child_name")
        .annotate(total=Sum("amount"))
    ):
        name = _normalize_child_name(row["child_name"])
        family_map = maps[row["family_id"]]
        key = name
        folded = _child_name_key(name)
        for existing in family_map:
            if _child_name_key(existing) == folded:
                key = existing
                break
        family_map[key] += row["total"] or Decimal("0")

    child_names_by_family = defaultdict(list)
    for family_id, name in PortalChild.objects.filter(family_id__in=ids, is_active=True).values_list(
        "family_id", "name"
    ):
        child_names_by_family[family_id].append(name)
    for family_id, family_map in maps.items():
        allocate_unlabeled_to_children(family_map, child_names_by_family.get(family_id, []))
    return maps


def prefetch_family_table_queryset(qs):
    """Load children, applications, and login/application flags in a few queries."""
    from django.db.models import Exists, OuterRef, Prefetch

    from enrollment.models import EnrollmentApplication

    from .models import PortalChild, PortalParentAccount

    return (
        qs.select_related("unit", "parent_account__user")
        .prefetch_related(
            Prefetch(
                "children",
                queryset=PortalChild.objects.select_related("unit", "family", "family__unit").order_by("name"),
            ),
            Prefetch(
                "enrollment_applications",
                queryset=EnrollmentApplication.objects.order_by("-submitted_at"),
            ),
        )
        .annotate(
            list_has_application=Exists(EnrollmentApplication.objects.filter(portal_family_id=OuterRef("pk"))),
            list_has_parent_login=Exists(PortalParentAccount.objects.filter(family_id=OuterRef("pk"))),
        )
    )


def _active_prefetched_children(family):
    return [child for child in family.children.all() if child.is_active]


def application_child_name(app):
    return f"{app.student_first_name} {app.student_last_name}".strip()


def is_waitlist_only_household(apps, active_children=None):
    """True when this household is waitlist-only and should stay off All families.

    A household stays listed when any application is approved/enrolled, a sibling
    is still in review, or an enrolled child is not only on the waitlist.
    """
    apps = list(apps or [])
    if any(app.status in APPROVED_APPLICATION_STATUSES for app in apps):
        return False
    if any(app.status in PENDING_REVIEW_STATUSES for app in apps):
        return False
    waitlist_apps = [app for app in apps if app.status == WAITLIST_APPLICATION_STATUS]
    if not waitlist_apps:
        return False
    waitlist_names = [application_child_name(app) for app in waitlist_apps]
    for child in active_children or []:
        name = (getattr(child, "name", None) or "").strip()
        if name and not child_name_in_collection(name, waitlist_names):
            return False
    return True


def _units_by_slug():
    from .models import PortalUnit

    return {unit.slug: unit for unit in PortalUnit.objects.filter(is_active=True)}


def _unit_for_enrollment_key(key, units_by_slug):
    from enrollment.locations import LEGACY_LOCATION_TO_UNIT_SLUG

    if not key:
        return None
    slug = key.replace("_", "-")
    if slug in units_by_slug:
        return units_by_slug[slug]
    legacy = LEGACY_LOCATION_TO_UNIT_SLUG.get(key)
    return units_by_slug.get(legacy) if legacy else None


def _location_label(key, units_by_slug):
    unit = _unit_for_enrollment_key(key, units_by_slug)
    if unit:
        return f"{unit.name} — {unit.city}" if unit.city else unit.name
    return (key or "").replace("_", " ").title() if key else ""


def live_family_child_rows(families, *, staff_unit=None, include_parent_login=False):
    """Build Families-table child rows without N+1 queries or per-request data repair."""
    from enrollment.portal_integration import family_display_label, family_name_duplicate_keys

    from .unit_visibility import application_belongs_to_unit, child_belongs_to_unit, unit_label_for_child

    families = list(families)
    family_ids = [family.pk for family in families]
    balances = child_balance_maps(family_ids)
    household_totals = household_ledger_totals(family_ids)
    duplicate_keys = family_name_duplicate_keys()
    units_by_slug = _units_by_slug()
    rows = []
    for family in families:
        family_balances = balances.get(family.pk, {})
        household_children = _active_prefetched_children(family)
        apps = list(family.enrollment_applications.all())
        if is_waitlist_only_household(apps, household_children):
            continue
        active_children = [
            child
            for child in household_children
            if not staff_unit or child_belongs_to_unit(child, staff_unit)
        ]
        children_specs = []
        listed_names = []
        for child in active_children:
            unit_name, unit_slug = unit_label_for_child(child)
            children_specs.append(
                {
                    "name": child.name,
                    "child_id": child.pk,
                    "school": child.school or "—",
                    "balance": child_balance_from_map(family_balances, child.name),
                    "unit": unit_name or (family.unit.name if family.unit_id else ""),
                    "unit_slug": unit_slug or (family.unit.slug if family.unit_id else ""),
                }
            )
            listed_names.append(child.name)
        for app in apps:
            child_name = application_child_name(app)
            if app.status in {"declined", "enrolled", WAITLIST_APPLICATION_STATUS}:
                continue
            if child_name_in_collection(child_name, listed_names):
                continue
            if staff_unit and not application_belongs_to_unit(app, staff_unit):
                continue
            app_unit = _unit_for_enrollment_key(app.program_location, units_by_slug)
            children_specs.append(
                {
                    "name": child_name,
                    "application_id": app.pk,
                    "school": app.student_school or "—",
                    "balance": child_balance_from_map(family_balances, child_name),
                    "unit": (app_unit.name if app_unit else "")
                    or _location_label(app.program_location, units_by_slug)
                    or (family.unit.name if family.unit_id else ""),
                    "unit_slug": (app_unit.slug if app_unit else "") or (family.unit.slug if family.unit_id else ""),
                }
            )
            listed_names.append(child_name)
        if staff_unit and not children_specs:
            continue
        has_application = getattr(family, "list_has_application", None)
        if has_application is None:
            has_application = bool(family.enrollment_applications.all())
        base_row = {
            "id": family.pk,
            "slug": family.slug,
            "name": family_display_label(family, duplicate_keys=duplicate_keys),
            "primary_contact": family.primary_contact or "—",
            "program": family.program_label or "—",
            "billing_type": family.billing_type or "Private pay",
            "status": "Suspended" if family.is_suspended else family.status,
            "has_application": bool(has_application),
        }
        if family.unit_id:
            base_row["unit"] = family.unit.name
            base_row["unit_slug"] = family.unit.slug
        if include_parent_login:
            has_login = getattr(family, "list_has_parent_login", None)
            if has_login is None:
                from .models import PortalParentAccount

                try:
                    has_login = bool(family.parent_account)
                except PortalParentAccount.DoesNotExist:
                    has_login = False
            base_row["has_parent_login"] = bool(has_login)
            base_row["is_suspended"] = family.is_suspended
        household_total = household_totals.get(family.pk, Decimal("0"))
        rows.extend(expand_family_record(base_row, children_specs, household_total))
    return sort_family_child_rows(rows)


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
        family_total = sum((_as_decimal(spec.get("balance")) for spec in children_specs), Decimal("0"))
        if not children_specs:
            family_total = _as_decimal(family.get("balance"))
        rows.extend(expand_family_record(base, children_specs, family_total))
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


def family_account_search_rows(rows, query, *, limit=25):
    """Children matching All families search (`q`), already unit-scoped in `rows`."""
    query = (query or "").strip()
    if not query:
        return []
    matched = apply_family_list_nav(rows, {"q": query})
    return matched[:limit]


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
