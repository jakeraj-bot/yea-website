"""Who still owes, which weeks those charges cover, and $15 late-fee posting."""

import csv
import re
from datetime import timedelta
from decimal import Decimal
from io import StringIO

from django.http import HttpResponse
from django.utils import timezone

from .family_list import (
    child_balance_from_map,
    child_balance_maps,
    household_ledger_totals,
)
from .member_admin import is_placeholder_unit
from .models import PortalChild, PortalFamily, PortalLateFeeSetting, PortalLedgerEntry
from .unit_visibility import children_for_unit, unit_label_for_child

MONEY = Decimal("0.01")
DEFAULT_LATE_FEE = Decimal("15.00")
CREDIT_TYPES = ("payment", "credit", "discount", "refund")
WEEK_IN_PARENS = re.compile(r"\(([^)]+)\)")
WEEK_OF = re.compile(r"week of\s+([^.,;]+)", re.I)
DATE_RANGE = re.compile(
    r"(\d{1,2}/\d{1,2}(?:/\d{2,4})?)\s*[–\-to]+\s*(\d{1,2}/\d{1,2}(?:/\d{2,4})?)",
    re.I,
)
ISO_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")


def _money(value):
    if value is None:
        return Decimal("0.00")
    if isinstance(value, Decimal):
        amount = value
    else:
        amount = Decimal(str(value))
    return amount.quantize(MONEY)


def get_late_fee_setting():
    row = PortalLateFeeSetting.objects.order_by("pk").first()
    if row:
        return row
    return PortalLateFeeSetting.objects.create(amount=DEFAULT_LATE_FEE, notify_on_charge_change=True)


def save_late_fee_amount(amount):
    from .billing_services import _parse_amount

    setting = get_late_fee_setting()
    setting.amount = _parse_amount(amount)
    setting.save(update_fields=["amount"])
    return setting


def late_fee_amount():
    return _money(get_late_fee_setting().amount or DEFAULT_LATE_FEE)


def notify_on_charge_change_enabled():
    return bool(get_late_fee_setting().notify_on_charge_change)


def monday_of(day):
    return day - timedelta(days=day.weekday())


def format_school_week(day):
    start = monday_of(day)
    end = start + timedelta(days=4)
    return f"{start.month}/{start.day}/{start.strftime('%y')}–{end.month}/{end.day}/{end.strftime('%y')}"


def week_label_from_charge(description, charge_date=None):
    """Pull a week from a charge description, else the school week of the charge date."""
    text = (description or "").strip()
    if text:
        for match in WEEK_IN_PARENS.finditer(text):
            inner = match.group(1).strip()
            if DATE_RANGE.search(inner) or WEEK_OF.search(inner) or "week" in inner.lower():
                return inner
            if ISO_DATE.search(inner) or re.search(r"\d{1,2}/\d{1,2}", inner):
                return inner
        week_of = WEEK_OF.search(text)
        if week_of:
            return week_of.group(0).strip()
        ranged = DATE_RANGE.search(text)
        if ranged:
            return ranged.group(0).strip()
    if charge_date:
        return format_school_week(charge_date)
    return ""


def charge_owe_for(entry):
    if entry is None:
        return "Account balance"
    label = (getattr(entry, "description", "") or "").strip()
    child = (getattr(entry, "child_name", "") or "").strip()
    week = week_label_from_charge(label, getattr(entry, "date", None))
    parts = [part for part in (label, child and f"Child: {child}", week and f"Week: {week}") if part]
    return " · ".join(parts) if parts else "Account balance"


def ledger_balance_context(family, child_name=""):
    """Same ledger math as the paid-family lists: charges minus tuition payments.

    Stripe processing fees live in ``fee_amount`` and do not inflate these totals.
    Unallocated (no child name) family payments are included in the family total.
    """
    maps = child_balance_maps([family.pk] if family and family.pk else [])
    family_map = maps.get(getattr(family, "pk", None), {})
    child_total = child_balance_from_map(family_map, child_name) if child_name else Decimal("0")
    family_total = household_ledger_totals([family.pk]).get(family.pk, Decimal("0")) if family and family.pk else Decimal("0")
    return {
        "child_balance": _money(child_total),
        "family_balance": _money(family_total),
        "child_balance_display": f"{_money(child_total):.2f}",
        "family_balance_display": f"{_money(family_total):.2f}",
    }


def _program_for_child(child):
    if getattr(child, "is_drop_off", False):
        return "Drop-off program"
    return (child.family.program_label or "After-school program").strip() or "After-school program"


def _entries_oldest_first(family):
    return list(
        PortalLedgerEntry.objects.filter(family=family).order_by("date", "created_at", "pk")
    )


def _unpaid_charges(entries):
    charges = []
    credit = Decimal("0")
    for entry in entries:
        kind = entry.entry_type
        amount = _money(entry.amount)
        if kind == "charge" and amount > 0:
            charges.append(
                {
                    "id": entry.pk,
                    "date": entry.date,
                    "description": entry.description,
                    "week": week_label_from_charge(entry.description, entry.date),
                    "remaining": amount,
                }
            )
        elif kind in CREDIT_TYPES and amount < 0:
            credit += abs(amount)
        elif kind in CREDIT_TYPES and amount > 0:
            credit += amount
    for charge in charges:
        if credit <= 0:
            break
        applied = min(charge["remaining"], credit)
        charge["remaining"] -= applied
        credit -= applied
    return [row for row in charges if row["remaining"] > 0]


def _apply_unlabeled_credits(child_unpaid, unlabeled_credits):
    remaining = unlabeled_credits
    if remaining <= 0:
        return
    oldest = []
    for name, charges in child_unpaid.items():
        for charge in charges:
            oldest.append((charge["date"], charge["id"], name, charge))
    oldest.sort()
    for _date, _pk, _name, charge in oldest:
        if remaining <= 0:
            break
        applied = min(charge["remaining"], remaining)
        charge["remaining"] -= applied
        remaining -= applied
    for name in list(child_unpaid):
        child_unpaid[name] = [row for row in child_unpaid[name] if row["remaining"] > 0]


def _name_match(child_name, family_name, query):
    if not query:
        return True
    needle = query.lower()
    return needle in (child_name or "").lower() or needle in (family_name or "").lower()


def owed_weeks_report(filters=None, *, unit=None, admin=False):
    """Families/children with an outstanding balance and the weeks those charges cover."""
    filters = filters or {}
    query = (filters.get("q") or "").strip()
    program = (filters.get("program") or "").strip()
    unit_slug = (filters.get("unit") or "").strip()
    if admin:
        children = (
            PortalChild.objects.filter(is_active=True)
            .select_related("family", "family__unit", "unit")
            .order_by("family__name", "name")
        )
        if unit_slug:
            from .unit_visibility import child_unit_slug_q

            children = children.filter(child_unit_slug_q(unit_slug))
    else:
        children = children_for_unit(unit, active_only=True).order_by("family__name", "name")

    children = list(children)
    family_ids = []
    seen_families = set()
    visible = []
    for child in children:
        family = child.family
        if is_placeholder_unit(family.unit):
            continue
        if not _name_match(child.name, family.name, query):
            continue
        child_program = _program_for_child(child)
        if program and program.lower() not in child_program.lower():
            continue
        visible.append((child, child_program))
        if family.pk not in seen_families:
            seen_families.add(family.pk)
            family_ids.append(family.pk)

    maps = child_balance_maps(family_ids)
    family_totals = household_ledger_totals(family_ids)
    family_entries = {}
    for family_id in family_ids:
        family_entries[family_id] = _entries_oldest_first(
            next(child.family for child, _prog in visible if child.family_id == family_id)
        )

    rows = []
    programs = set()
    outstanding = Decimal("0")
    for child, child_program in visible:
        family = child.family
        family_map = maps.get(family.pk, {})
        child_total = child_balance_from_map(family_map, child.name)
        if child_total <= 0:
            continue
        family_total = family_totals.get(family.pk, Decimal("0"))
        entries = family_entries.get(family.pk, [])
        named = [row for row in entries if (row.child_name or "").strip().lower() == child.name.strip().lower()]
        unpaid = _unpaid_charges(named)
        weeks = []
        seen_weeks = set()
        for charge in unpaid:
            label = charge["week"] or format_school_week(charge["date"])
            if label not in seen_weeks:
                seen_weeks.add(label)
                weeks.append(label)
        unit_name, child_unit_slug = unit_label_for_child(child)
        programs.add(child_program)
        outstanding += child_total
        rows.append(
            {
                "child_id": child.pk,
                "child": child.name,
                "family": family.name,
                "family_slug": family.slug,
                "family_id": family.pk,
                "unit": unit_name or family.unit.name,
                "unit_slug": child_unit_slug or family.unit.slug,
                "program": child_program,
                "weeks": weeks,
                "weeks_display": ", ".join(weeks) if weeks else "Balance (no week on charges)",
                "child_balance": f"{_money(child_total):.2f}",
                "family_balance": f"{_money(family_total):.2f}",
                "child_balance_amount": _money(child_total),
            }
        )

    # Apply unlabeled household payments so weeks match the family total.
    by_family = {}
    for row in rows:
        by_family.setdefault(row["family_id"], []).append(row)
    for family_id, family_rows in by_family.items():
        entries = family_entries.get(family_id, [])
        unlabeled_credit = sum(
            (
                abs(_money(row.amount))
                for row in entries
                if not (row.child_name or "").strip() and row.entry_type in CREDIT_TYPES and _money(row.amount) < 0
            ),
            Decimal("0"),
        )
        if unlabeled_credit <= 0:
            continue
        unpaid_map = {}
        for row in family_rows:
            child_name = row["child"]
            named = [
                entry
                for entry in entries
                if (entry.child_name or "").strip().lower() == child_name.strip().lower()
            ]
            unpaid_map[child_name] = _unpaid_charges(named)
        _apply_unlabeled_credits(unpaid_map, unlabeled_credit)
        for row in family_rows:
            charges = unpaid_map.get(row["child"], [])
            weeks = []
            seen = set()
            for charge in charges:
                label = charge["week"] or format_school_week(charge["date"])
                if label not in seen:
                    seen.add(label)
                    weeks.append(label)
            row["weeks"] = weeks
            row["weeks_display"] = ", ".join(weeks) if weeks else "Balance (no week on charges)"

    units = []
    if admin:
        from .admin_reports import unit_options

        units = unit_options()

    return {
        "rows": rows,
        "programs": sorted(programs),
        "units": units,
        "summary": f"{len(rows)} children with a balance · ${outstanding:.2f} outstanding",
        "late_fee_amount": f"{late_fee_amount():.2f}",
        "outstanding": f"{_money(outstanding):.2f}",
    }


def families_with_balance(*, unit=None):
    """Active families whose household ledger is over $0."""
    families = PortalFamily.objects.select_related("unit").prefetch_related("children").filter(status="Active")
    if unit:
        family_ids = set(children_for_unit(unit, active_only=True).values_list("family_id", flat=True))
        families = families.filter(pk__in=family_ids)
    families = [family for family in families if not is_placeholder_unit(family.unit)]
    totals = household_ledger_totals([family.pk for family in families])
    rows = []
    for family in families:
        total = totals.get(family.pk, Decimal("0"))
        if total <= 0:
            continue
        rows.append({"family": family, "balance": _money(total)})
    return rows


def post_late_fees(selections, *, notify=True):
    """Post today's late-fee charge on the chosen children only.

    ``selections`` is a list of ``child_id`` values.
    """
    from .billing_services import post_charge

    amount = late_fee_amount()
    today = timezone.localdate()
    posted = []
    seen = set()
    for raw in selections or []:
        try:
            child_id = int(raw)
        except (TypeError, ValueError):
            continue
        if child_id in seen:
            continue
        seen.add(child_id)
        child = PortalChild.objects.select_related("family").filter(pk=child_id, is_active=True).first()
        if not child:
            continue
        entry = post_charge(
            child.family,
            child.name,
            "late_fee",
            amount,
            today,
            "Late fee",
            is_manual=True,
            notify=notify,
        )
        posted.append(entry)
    return posted


def owed_weeks_csv_response(report):
    buffer = StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["Child", "Family", "Unit", "Program", "Weeks owed", "Child balance", "Family balance"])
    for row in report["rows"]:
        writer.writerow(
            [
                row["child"],
                row["family"],
                row["unit"],
                row["program"],
                row["weeks_display"],
                row["child_balance"],
                row["family_balance"],
            ]
        )
    response = HttpResponse(buffer.getvalue(), content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="owed-by-week.csv"'
    return response
