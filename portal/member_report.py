"""Filterable member information / enrollment roster for staff and admin."""

from datetime import date, timedelta
from decimal import Decimal

from django.utils import timezone

from enrollment.models import EnrollmentApplication

from .member_admin import is_placeholder_unit
from .models import PortalAgencyProfile, PortalChild, PortalUnit
from .unit_visibility import children_for_unit, unit_label_for_child

PROGRAM_AFTER_CARE = "After-Care"
PROGRAM_BEFORE_CARE = "Before-Care"
PROGRAM_DROP_IN = "Drop-in"
PROGRAM_SUMMER = "Summer camp"

PROGRAM_TYPE_ORDER = (PROGRAM_AFTER_CARE, PROGRAM_BEFORE_CARE, PROGRAM_DROP_IN, PROGRAM_SUMMER)

APP_PROGRAM_TO_TYPE = {
    "after_school": PROGRAM_AFTER_CARE,
    "before_care": PROGRAM_BEFORE_CARE,
    "drop_off": PROGRAM_DROP_IN,
    "summer_camp": PROGRAM_SUMMER,
}

WAITING = "waiting"
BLANK = "—"

FILTER_KEYS = (
    "q",
    "school",
    "grade",
    "unit",
    "program",
    "billing",
    "plan",
    "four_cs",
    "agency_status",
    "status",
)

PRINT_COLUMNS = [
    ("child", "Child"),
    ("family", "Family"),
    ("status", "Status"),
    ("unit", "Unit"),
    ("school", "School"),
    ("grade", "Grade"),
    ("program", "Program type"),
    ("billing", "Billing type"),
    ("plan", "Payment plan"),
    ("four_cs", "4Cs member"),
    ("four_cs_daily", "4Cs daily"),
    ("four_cs_copay", "4Cs copay"),
    ("four_cs_agency", "4Cs agency"),
    ("four_cs_agency_created", "Agency created"),
    ("contact", "Contact"),
]


def _money(value):
    if value is None:
        return BLANK
    amount = Decimal(value).quantize(Decimal("0.01"))
    if amount == 0:
        return BLANK
    return f"{amount:.2f}"


def _is_4cs_billing(billing_type):
    text = (billing_type or "").strip().lower().replace("'", "")
    return "4c" in text or text in {"four cs", "fourcs"}


def _match_apps_for_child(child, family_apps):
    name = (child.name or "").strip()
    parts = name.split()
    first = parts[0] if parts else ""
    last = " ".join(parts[1:]) if len(parts) > 1 else ""
    matched = []
    for app in family_apps:
        if first and (app.student_first_name or "").strip().lower() != first.lower():
            continue
        if last and (app.student_last_name or "").strip().lower() != last.lower():
            continue
        matched.append(app)
    return matched


def program_types_for_child(child, apps=None):
    """Canonical program labels: After-Care, Before-Care, Drop-in (plus Summer camp if present)."""
    seen = []

    def add(label):
        if label and label not in seen:
            seen.append(label)

    if getattr(child, "is_drop_off", False):
        add(PROGRAM_DROP_IN)
    for app in apps or []:
        add(APP_PROGRAM_TO_TYPE.get(app.program) or "")
    label = (getattr(child.family, "program_label", None) or "").lower()
    if "drop" in label:
        add(PROGRAM_DROP_IN)
    if "before" in label:
        add(PROGRAM_BEFORE_CARE)
    if "after" in label:
        add(PROGRAM_AFTER_CARE)
    if not seen:
        add(PROGRAM_AFTER_CARE)
    return [name for name in PROGRAM_TYPE_ORDER if name in seen] or seen


def _weekdays_in_range(start, end):
    if not start or not end or end < start:
        return 0
    days = 0
    cursor = start
    while cursor <= end:
        if cursor.weekday() < 5:
            days += 1
        cursor += timedelta(days=1)
    return days


def current_contract_week(profile, on_date=None):
    on_date = on_date or timezone.localdate()
    weeks = list(getattr(profile, "contract_weeks", []).all()) if profile else []
    if not weeks:
        return None
    for week in weeks:
        if week.week_start <= on_date <= week.week_end:
            return week
    upcoming = [week for week in weeks if week.week_start > on_date]
    if upcoming:
        return min(upcoming, key=lambda week: week.week_start)
    past = [week for week in weeks if week.week_end < on_date]
    if past:
        return max(past, key=lambda week: week.week_end)
    return None


def four_cs_snapshot(child, profile=None, on_date=None):
    """Live 4Cs daily/copay/agency fields. Waiting when billed as 4Cs but no agency yet."""
    billing = (child.family.billing_type or "").strip() or "Private pay"
    is_member = _is_4cs_billing(billing) or bool(profile)
    if not is_member:
        return {
            "four_cs": "No",
            "four_cs_yes": False,
            "four_cs_daily": BLANK,
            "four_cs_copay": BLANK,
            "four_cs_agency": BLANK,
            "four_cs_agency_created": BLANK,
            "agency_status_key": "no",
        }
    if not profile:
        return {
            "four_cs": "Yes",
            "four_cs_yes": True,
            "four_cs_daily": WAITING,
            "four_cs_copay": WAITING,
            "four_cs_agency": WAITING,
            "four_cs_agency_created": WAITING,
            "agency_status_key": "waiting",
        }

    agency_name = profile.agency.name if profile.agency_id else ""
    created = ""
    if profile.created_at:
        created = profile.created_at.date().isoformat()
    waiting_agency = not profile.agency_id
    week = current_contract_week(profile, on_date=on_date)

    daily = profile.daily_agency_rate or Decimal("0")
    if daily <= 0 and week and week.agency_amount:
        days = _weekdays_in_range(week.week_start, week.week_end) or 5
        daily = (week.agency_amount or Decimal("0")) / days
    if daily <= 0 and profile.weekly_agency_rate:
        daily = (profile.weekly_agency_rate or Decimal("0")) / Decimal("5")

    copay = profile.daily_copay or Decimal("0")
    copay_label = _money(copay)
    if copay_label == BLANK:
        weekly_copay = profile.weekly_copay or Decimal("0")
        if week and week.parent_amount:
            weekly_copay = week.parent_amount
        copay_label = _money(weekly_copay)
        if copay_label != BLANK:
            copay_label = f"{copay_label} / week"
    else:
        copay_label = f"{copay_label} / day"

    daily_label = _money(daily)
    if daily_label != BLANK:
        daily_label = f"{daily_label} / day"
    elif waiting_agency:
        daily_label = WAITING
        copay_label = WAITING if copay_label == BLANK else copay_label

    return {
        "four_cs": "Yes",
        "four_cs_yes": True,
        "four_cs_daily": daily_label,
        "four_cs_copay": copay_label if copay_label != BLANK else (WAITING if waiting_agency else BLANK),
        "four_cs_agency": agency_name or WAITING,
        "four_cs_agency_created": created or WAITING,
        "agency_status_key": "waiting" if waiting_agency else "yes",
    }


def _family_status(family):
    if family.is_suspended:
        return "Suspended"
    return (family.status or "Active").strip() or "Active"


def member_information_rows(*, unit=None):
    """One row per active child. Pass unit to scope to that site (staff)."""
    if unit:
        children = children_for_unit(unit, active_only=True)
    else:
        children = PortalChild.objects.filter(is_active=True).select_related("family", "family__unit", "unit")
    children = children.order_by("family__name", "name")
    child_list = list(children)
    if not child_list:
        return []

    profiles = {
        profile.child_id: profile
        for profile in PortalAgencyProfile.objects.filter(child_id__in=[child.pk for child in child_list])
        .select_related("agency")
        .prefetch_related("contract_weeks")
    }
    family_ids = {child.family_id for child in child_list}
    apps_by_family = {}
    for app in EnrollmentApplication.objects.filter(portal_family_id__in=family_ids).exclude(status="declined"):
        apps_by_family.setdefault(app.portal_family_id, []).append(app)

    today = timezone.localdate()
    rows = []
    for child in child_list:
        family = child.family
        child_unit = child.unit or family.unit
        if is_placeholder_unit(child_unit or family.unit):
            continue
        unit_name, unit_slug = unit_label_for_child(child)
        apps = _match_apps_for_child(child, apps_by_family.get(family.pk, []))
        types = program_types_for_child(child, apps)
        school = (child.school or "").strip()
        grade = (child.grade or "").strip()
        plan = (child.billing_plan or "").strip()
        if apps:
            app = apps[0]
            if not school:
                school = (app.student_school or "").strip()
            if not grade and hasattr(app, "get_student_grade_display"):
                grade = (app.get_student_grade_display() or "").strip()
            if not plan and hasattr(app, "get_payment_plan_display"):
                plan = (app.get_payment_plan_display() or "").strip()
        billing = (family.billing_type or "Private pay").strip() or "Private pay"
        snapshot = four_cs_snapshot(child, profiles.get(child.pk), on_date=today)
        rows.append(
            {
                "child_id": child.pk,
                "child": child.name,
                "family": family.name,
                "family_slug": family.slug,
                "family_id": family.pk,
                "contact": family.primary_contact or BLANK,
                "status": _family_status(family),
                "unit": unit_name or (family.unit.name if family.unit_id else BLANK),
                "unit_slug": unit_slug or (family.unit.slug if family.unit_id else ""),
                "school": school or BLANK,
                "grade": grade or BLANK,
                "program": ", ".join(types),
                "program_types": types,
                "billing": billing,
                "plan": plan or BLANK,
                **snapshot,
            }
        )
    return rows


def member_information_options(rows):
    schools = sorted({row["school"] for row in rows if row.get("school") and row["school"] != BLANK}, key=str.lower)
    grades = sorted({row["grade"] for row in rows if row.get("grade") and row["grade"] != BLANK}, key=str.lower)
    programs = [name for name in PROGRAM_TYPE_ORDER if any(name in (row.get("program_types") or []) for row in rows)]
    billings = sorted({row["billing"] for row in rows if row.get("billing")}, key=str.lower)
    plans = sorted({row["plan"] for row in rows if row.get("plan") and row["plan"] != BLANK}, key=str.lower)
    statuses = sorted({row["status"] for row in rows if row.get("status")}, key=str.lower)
    units = []
    seen = set()
    for row in rows:
        slug = row.get("unit_slug") or ""
        name = row.get("unit") or ""
        if slug and slug not in seen:
            seen.add(slug)
            units.append((slug, name))
    units.sort(key=lambda item: item[1].lower())
    return {
        "schools": schools,
        "grades": grades,
        "programs": programs,
        "billing_types": billings,
        "payment_plans": plans,
        "statuses": statuses,
        "units": units,
    }


def filter_member_information_rows(rows, filters=None):
    filters = filters or {}
    query = (filters.get("q") or "").strip().lower()
    school = (filters.get("school") or "").strip()
    grade = (filters.get("grade") or "").strip()
    unit = (filters.get("unit") or "").strip()
    program = (filters.get("program") or "").strip()
    billing = (filters.get("billing") or "").strip()
    plan = (filters.get("plan") or "").strip()
    four_cs = (filters.get("four_cs") or "").strip().lower()
    agency_status = (filters.get("agency_status") or "").strip().lower()
    status = (filters.get("status") or "").strip()

    filtered = []
    for row in rows:
        if unit and row.get("unit_slug") != unit:
            continue
        if query:
            hay = f"{row.get('child') or ''} {row.get('family') or ''} {row.get('contact') or ''}".lower()
            if query not in hay:
                continue
        if school and (row.get("school") or "").lower() != school.lower():
            continue
        if grade and (row.get("grade") or "").lower() != grade.lower():
            continue
        if program and program not in (row.get("program_types") or []):
            continue
        if billing and (row.get("billing") or "").lower() != billing.lower():
            continue
        if plan and plan.lower() not in (row.get("plan") or "").lower():
            continue
        if four_cs == "yes" and not row.get("four_cs_yes"):
            continue
        if four_cs == "no" and row.get("four_cs_yes"):
            continue
        if agency_status and row.get("agency_status_key") != agency_status:
            continue
        if status and (row.get("status") or "").lower() != status.lower():
            continue
        filtered.append(row)
    return filtered


def member_information_report_bundle(filters=None, *, unit=None, admin=False):
    filters = dict(filters or {})
    if not admin:
        filters["unit"] = ""
    all_rows = member_information_rows(unit=None if admin else unit)
    full_options = member_information_options(all_rows)
    scoped = filter_member_information_rows(all_rows, {"unit": filters.get("unit")}) if admin and filters.get("unit") else all_rows
    options = member_information_options(scoped)
    if admin:
        options["units"] = full_options["units"] or [
            (item.slug, item.name) for item in PortalUnit.objects.filter(is_active=True).order_by("name") if not is_placeholder_unit(item)
        ]
    rows = filter_member_information_rows(all_rows, filters)
    return {
        "report_rows": rows,
        "filter_options": options,
        "generated_date": date.today().strftime("%B %d, %Y"),
        "columns": PRINT_COLUMNS,
    }


def member_information_report_data(filters=None):
    """Admin data-report payload: rows plus filter choice lists."""
    bundle = member_information_report_bundle(filters or {}, admin=True)
    options = bundle["filter_options"]
    return {
        "rows": bundle["report_rows"],
        "schools": options.get("schools") or [],
        "grades": options.get("grades") or [],
        "programs": options.get("programs") or [],
        "billing_types": options.get("billing_types") or [],
        "payment_plans": options.get("payment_plans") or [],
        "statuses": options.get("statuses") or [],
    }


def four_cs_roster_rows(filters=None):
    """4Cs-only slice, including members still waiting for an agency profile."""
    filters = filters or {}
    query = (filters.get("q") or "").strip()
    unit = (filters.get("unit") or "").strip()
    agency = (filters.get("agency") or "").strip()
    agency_status = (filters.get("agency_status") or "").strip().lower()

    all_rows = member_information_rows(unit=None)
    agencies = set()
    rows = []
    profiles = {
        profile.child_id: profile
        for profile in PortalAgencyProfile.objects.select_related("agency")
    }
    for row in all_rows:
        if not row.get("four_cs_yes"):
            continue
        if unit and row.get("unit_slug") != unit:
            continue
        if query:
            hay = f"{row.get('child') or ''} {row.get('family') or ''} {row.get('four_cs_agency') or ''}".lower()
            if query.lower() not in hay:
                continue
        profile = profiles.get(row.get("child_id"))
        if agency:
            if not profile or not profile.agency_id or profile.agency.slug != agency:
                continue
        if agency_status and row.get("agency_status_key") != agency_status:
            continue
        if profile and profile.agency_id:
            agencies.add((profile.agency.slug, profile.agency.name))
        rows.append(
            {
                "child": row["child"],
                "family": row["family"],
                "family_slug": row["family_slug"],
                "family_id": row["family_id"],
                "unit": row["unit"],
                "school": row["school"],
                "agency": row["four_cs_agency"],
                "agency_created": row["four_cs_agency_created"],
                "auth_number": (profile.auth_number if profile else "") or WAITING,
                "auth_start": profile.auth_start.isoformat() if profile and profile.auth_start else WAITING,
                "auth_end": profile.auth_end.isoformat() if profile and profile.auth_end else WAITING,
                "daily_agency": row["four_cs_daily"],
                "daily_copay": row["four_cs_copay"],
                "weekly_copay": _money(profile.weekly_copay) if profile else WAITING,
                "weekly_agency_rate": _money(profile.weekly_agency_rate) if profile else WAITING,
                "agency_balance": _money(profile.agency_balance) if profile else WAITING,
            }
        )
    return {
        "rows": rows,
        "agencies": sorted(agencies, key=lambda item: item[1]),
    }
