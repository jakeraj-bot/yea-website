"""Expected 4Cs copay and agency amounts — forecast from plans, not the ledger."""

from decimal import Decimal, ROUND_HALF_UP

from django.http import HttpResponse

from .agency_weeks import billable_week_count_for_month, cadence_key, weekly_from_daily, weekly_rate_for_plan
from .billing_services import (
    active_scholarship_for_child,
    agency_profile_for,
    parent_copay_after_scholarship,
    plan_uses_4cs_copay,
)
from .member_admin import is_placeholder_unit
from .member_report import program_types_for_child
from .models import PortalAgencyProfile, PortalChild, PortalScholarshipFund, PortalUnit
from .unit_visibility import child_unit_q, unit_label_for_child

ZERO = Decimal("0.00")
MONEY = Decimal("0.01")
BLANK = "—"

CADENCE_WEEKS = {"weekly": 1, "biweekly": 2, "monthly": 4}
CADENCE_LABELS = {"weekly": "Weekly", "biweekly": "Bi-weekly", "monthly": "Monthly"}
CADENCE_FILTER_CHOICES = (
    ("weekly", "Weekly"),
    ("biweekly", "Bi-weekly"),
    ("monthly", "Monthly"),
)

FILTER_KEYS = (
    "q",
    "unit",
    "status",
    "school",
    "grade",
    "program",
    "copay_cadence",
    "agency_cadence",
    "scholarship",
    "scholarship_fund",
    "agency",
    "agency_status",
)

PRINT_COLUMNS = [
    ("child", "Child"),
    ("family", "Family"),
    ("status", "Status"),
    ("unit", "Unit"),
    ("school", "School"),
    ("grade", "Grade"),
    ("program", "Program"),
    ("copay_plan", "Copay plan"),
    ("agency_cadence_label", "4Cs cadence"),
    ("scholarship", "Scholarship"),
    ("copay_before", "Copay before scholarship"),
    ("copay_cycle", "Copay I should collect"),
    ("weekly_copay", "Weekly copay (all members)"),
    ("agency_cycle", "4Cs this cycle"),
    ("weekly_agency", "Weekly 4Cs / agency"),
    ("agency", "Agency"),
]


def _quantize(value):
    amount = value if isinstance(value, Decimal) else Decimal(str(value or 0))
    return amount.quantize(MONEY, rounding=ROUND_HALF_UP)


def _money(value):
    return f"{_quantize(value):.2f}"


def _cadence_from_label(plan):
    return cadence_key(plan)


def _cadence_from_schedule(schedule):
    text = (schedule or "").strip().lower()
    if not text:
        return ""
    if "bi" in text:
        return "biweekly"
    if "month" in text:
        return "monthly"
    if "week" in text:
        return "weekly"
    return ""


def _family_status(family, child=None):
    if family.is_suspended:
        return "Suspended"
    if child is not None and not child.is_active:
        return "Inactive"
    return (family.status or "Active").strip() or "Active"


def _is_4cs_plan_row(plan):
    if plan is None:
        return False
    kind = (plan.billing_kind or "").lower()
    cadence = (plan.billing_plan or "").lower()
    description = (plan.description or "").lower()
    if kind == "4cs" or "copay" in cadence or "4cs" in cadence:
        return True
    if "copay" in description or "4cs" in description:
        return True
    return False


def four_cs_copay_plan(child):
    """The parent copay plan for a 4Cs child (weekly / bi-weekly / monthly)."""
    plans = list(child.billing_plans.all())
    for plan in plans:
        if _is_4cs_plan_row(plan):
            return plan
    for plan in plans:
        if plan_uses_4cs_copay(child, plan):
            return plan
    return None


def child_is_4cs_member(child, profile=None):
    """4Cs membership = approved 4Cs/agency plan or a live agency profile.

    Family billing type alone is not enough — waitlist-only kids without a
    4Cs plan are not counted as members YEA is getting paid for.
    """
    if profile is not None:
        return True
    if agency_profile_for(child) is not None:
        return True
    if four_cs_copay_plan(child) is not None:
        return True
    plan = (child.billing_plan or "").lower()
    if "copay" in plan or "4cs" in plan:
        return True
    return False


def _weekly_copay_gross(profile, plan, child, weeks):
    if profile is not None:
        weekly = profile.weekly_copay or ZERO
        if weekly > 0:
            return _quantize(weekly)
        daily = profile.daily_copay or ZERO
        if daily > 0:
            return weekly_from_daily(daily)
    target = plan if plan is not None else child
    rate = weekly_rate_for_plan(target) if target is not None else None
    if rate:
        return _quantize(rate)
    amount = None
    if plan is not None and plan.billing_amount is not None:
        amount = plan.billing_amount
    elif child.billing_amount is not None:
        amount = child.billing_amount
    if amount and weeks and weeks > 1:
        return _quantize(amount / Decimal(weeks))
    if amount:
        return _quantize(amount)
    return ZERO


def _weekly_agency_gross(profile):
    if profile is None:
        return ZERO
    weekly = profile.weekly_agency_rate or ZERO
    if weekly > 0:
        return _quantize(weekly)
    daily = profile.daily_agency_rate or ZERO
    if daily > 0:
        return weekly_from_daily(daily)
    return ZERO


def _child_school_grade(child, apps):
    school = (child.school or "").strip()
    grade = (child.grade or "").strip()
    app = apps[0] if apps else None
    if app:
        if not school:
            school = (app.student_school or "").strip()
        if not grade and hasattr(app, "get_student_grade_display"):
            grade = (app.get_student_grade_display() or "").strip()
        elif not grade:
            grade = (getattr(app, "student_grade", None) or "").strip()
    return school, grade


def _build_row(child, profile, apps):
    family = child.family
    unit_name, unit_slug = unit_label_for_child(child)
    copay_plan = four_cs_copay_plan(child)
    copay_label = (copay_plan.billing_plan if copay_plan else child.billing_plan) or "Weekly"
    copay_cadence = _cadence_from_label(copay_label)
    agency_weeks = CADENCE_WEEKS.get(copay_cadence, 1)
    weeks = agency_weeks
    if copay_cadence == "monthly":
        from django.utils import timezone

        today = timezone.localdate()
        weeks = billable_week_count_for_month(today.year, today.month) or weeks
    weekly_gross = _weekly_copay_gross(profile, copay_plan, child, weeks)
    cycle_gross = _quantize(weekly_gross * Decimal(weeks))
    scholarship = active_scholarship_for_child(child)
    weekly_net, weekly_discount = parent_copay_after_scholarship(scholarship, weekly_gross)
    cycle_net, cycle_discount = parent_copay_after_scholarship(scholarship, cycle_gross)
    weekly_agency = _weekly_agency_gross(profile)
    agency_schedule = ""
    if profile and profile.agency_id:
        agency_schedule = profile.agency.remittance_schedule or ""
    agency_cadence = _cadence_from_schedule(agency_schedule) or "weekly"
    # 4Cs still posts weekly. Bi-weekly / monthly agency figures stay two and
    # four weeks of that weekly agency rate — there is no agency monthly plan.
    agency_cycle = _quantize(weekly_agency * Decimal(agency_weeks))
    school, grade = _child_school_grade(child, apps)
    types = program_types_for_child(child, apps)
    agency_name = ""
    agency_slug = ""
    agency_status_key = "no"
    if profile:
        if profile.agency_id:
            agency_name = profile.agency.name
            agency_slug = profile.agency.slug
            agency_status_key = "yes"
        else:
            agency_name = "Waiting"
            agency_status_key = "waiting"
    status = _family_status(family, child)
    scholarship_name = scholarship.fund.name if scholarship else ""
    return {
        "child_id": child.pk,
        "child": child.name,
        "family": family.name,
        "family_slug": family.slug,
        "family_id": family.pk,
        "status": status,
        "unit": unit_name or (family.unit.name if family.unit_id else BLANK),
        "unit_slug": unit_slug or (family.unit.slug if family.unit_id else ""),
        "school": school or BLANK,
        "grade": grade or BLANK,
        "program": ", ".join(types) or BLANK,
        "program_types": types,
        "copay_plan": CADENCE_LABELS.get(copay_cadence, copay_label),
        "copay_cadence": copay_cadence,
        "agency_cadence": agency_cadence,
        "agency_cadence_label": CADENCE_LABELS.get(agency_cadence, "Weekly"),
        "scholarship": scholarship_name or "No",
        "scholarship_yes": bool(scholarship),
        "scholarship_fund_id": str(scholarship.fund_id) if scholarship else "",
        "copay_before": _money(cycle_gross),
        "copay_before_amount": cycle_gross,
        "copay_cycle": _money(cycle_net),
        "copay_cycle_amount": cycle_net,
        "copay_discount_amount": cycle_discount,
        "weekly_copay": _money(weekly_net),
        "weekly_copay_amount": weekly_net,
        "weekly_copay_before": _money(weekly_gross),
        "weekly_copay_before_amount": weekly_gross,
        "weekly_discount_amount": weekly_discount,
        "agency_cycle": _money(agency_cycle),
        "agency_cycle_amount": agency_cycle,
        "weekly_agency": _money(weekly_agency),
        "weekly_agency_amount": weekly_agency,
        "agency": agency_name or BLANK,
        "agency_slug": agency_slug,
        "agency_status_key": agency_status_key,
        "auth_number": (profile.auth_number if profile else "") or BLANK,
    }


def four_cs_payout_rows(*, unit=None, admin=False):
    """One row per 4Cs member. Staff pass unit to scope to that site."""
    children = PortalChild.objects.select_related("family", "family__unit", "unit").prefetch_related(
        "billing_plans", "scholarships__fund", "family__enrollment_applications"
    )
    if not admin:
        if unit:
            children = children.filter(child_unit_q(unit))
        else:
            children = children.none()
    children = children.order_by("name", "family__name")
    child_list = list(children)
    profiles = {
        profile.child_id: profile
        for profile in PortalAgencyProfile.objects.filter(child_id__in=[child.pk for child in child_list])
        .select_related("agency")
    }
    from enrollment.models import EnrollmentApplication
    from .member_report import _match_apps_for_child

    family_ids = {child.family_id for child in child_list}
    apps_by_family = {}
    if family_ids:
        for app in EnrollmentApplication.objects.filter(portal_family_id__in=family_ids).exclude(status="declined"):
            apps_by_family.setdefault(app.portal_family_id, []).append(app)

    rows = []
    for child in child_list:
        family = child.family
        child_unit = child.unit or family.unit
        if is_placeholder_unit(child_unit or family.unit):
            continue
        profile = profiles.get(child.pk)
        if not child_is_4cs_member(child, profile):
            continue
        apps = _match_apps_for_child(child, apps_by_family.get(family.pk, []))
        rows.append(_build_row(child, profile, apps))
    rows.sort(key=lambda row: ((row.get("child") or "").casefold(), (row.get("family") or "").casefold()))
    return rows


def four_cs_payout_options(rows):
    schools = sorted({row["school"] for row in rows if row.get("school") and row["school"] != BLANK}, key=str.lower)
    grades = sorted({row["grade"] for row in rows if row.get("grade") and row["grade"] != BLANK}, key=str.lower)
    programs = sorted({name for row in rows for name in (row.get("program_types") or [])}, key=str.lower)
    statuses = sorted({row["status"] for row in rows if row.get("status")}, key=str.lower)
    if "Inactive" not in statuses:
        statuses.append("Inactive")
        statuses.sort(key=str.lower)
    agencies = []
    seen_agencies = set()
    for row in rows:
        slug = row.get("agency_slug") or ""
        name = row.get("agency") or ""
        if slug and slug not in seen_agencies:
            seen_agencies.add(slug)
            agencies.append((slug, name))
    agencies.sort(key=lambda item: item[1].lower())
    units = []
    seen_units = set()
    for row in rows:
        slug = row.get("unit_slug") or ""
        name = row.get("unit") or ""
        if slug and slug not in seen_units:
            seen_units.add(slug)
            units.append((slug, name))
    units.sort(key=lambda item: item[1].lower())
    funds = list(
        PortalScholarshipFund.objects.filter(is_active=True).order_by("name").values_list("pk", "name")
    )
    return {
        "schools": schools,
        "grades": grades,
        "programs": programs,
        "statuses": statuses,
        "agencies": agencies,
        "units": units,
        "scholarship_funds": [(str(pk), name) for pk, name in funds],
        "cadence_choices": CADENCE_FILTER_CHOICES,
        "scholarship_choices": (("yes", "Yes"), ("no", "No")),
        "agency_status_choices": (("yes", "Agency on file"), ("waiting", "Waiting for agency")),
    }


def filter_four_cs_payout_rows(rows, filters=None):
    filters = filters or {}
    query = (filters.get("q") or "").strip().lower()
    unit = (filters.get("unit") or "").strip()
    status = (filters.get("status") or "").strip()
    school = (filters.get("school") or "").strip()
    grade = (filters.get("grade") or "").strip()
    program = (filters.get("program") or "").strip()
    copay_cadence = (filters.get("copay_cadence") or "").strip().lower()
    agency_cadence = (filters.get("agency_cadence") or "").strip().lower()
    scholarship = (filters.get("scholarship") or "").strip().lower()
    scholarship_fund = (filters.get("scholarship_fund") or "").strip()
    agency = (filters.get("agency") or "").strip()
    agency_status = (filters.get("agency_status") or "").strip().lower()

    filtered = []
    for row in rows:
        if unit and row.get("unit_slug") != unit:
            continue
        if query:
            hay = f"{row.get('child') or ''} {row.get('family') or ''} {row.get('agency') or ''}".lower()
            if query not in hay:
                continue
        if status and (row.get("status") or "").lower() != status.lower():
            continue
        if school and (row.get("school") or "").lower() != school.lower():
            continue
        if grade and (row.get("grade") or "").lower() != grade.lower():
            continue
        if program and program not in (row.get("program_types") or []):
            continue
        if copay_cadence and row.get("copay_cadence") != copay_cadence:
            continue
        if agency_cadence and row.get("agency_cadence") != agency_cadence:
            continue
        if scholarship == "yes" and not row.get("scholarship_yes"):
            continue
        if scholarship == "no" and row.get("scholarship_yes"):
            continue
        if scholarship_fund and row.get("scholarship_fund_id") != str(scholarship_fund):
            continue
        if agency and row.get("agency_slug") != agency:
            continue
        if agency_status and row.get("agency_status_key") != agency_status:
            continue
        filtered.append(row)
    return filtered


def _sum_amount(rows, key):
    total = ZERO
    for row in rows:
        total += row.get(key) or ZERO
    return _quantize(total)


def four_cs_payout_totals(rows):
    weekly_rows = [row for row in rows if row.get("copay_cadence") == "weekly"]
    biweekly_rows = [row for row in rows if row.get("copay_cadence") == "biweekly"]
    monthly_rows = [row for row in rows if row.get("copay_cadence") == "monthly"]
    return {
        "member_count": len(rows),
        "copay_weekly_plans": _money(_sum_amount(weekly_rows, "copay_cycle_amount")),
        "copay_weekly_plans_amount": _sum_amount(weekly_rows, "copay_cycle_amount"),
        "copay_biweekly_plans": _money(_sum_amount(biweekly_rows, "copay_cycle_amount")),
        "copay_biweekly_plans_amount": _sum_amount(biweekly_rows, "copay_cycle_amount"),
        "copay_monthly_plans": _money(_sum_amount(monthly_rows, "copay_cycle_amount")),
        "copay_monthly_plans_amount": _sum_amount(monthly_rows, "copay_cycle_amount"),
        "weekly_copay_all": _money(_sum_amount(rows, "weekly_copay_amount")),
        "weekly_copay_all_amount": _sum_amount(rows, "weekly_copay_amount"),
        "agency_weekly_plans": _money(_sum_amount(weekly_rows, "agency_cycle_amount")),
        "agency_weekly_plans_amount": _sum_amount(weekly_rows, "agency_cycle_amount"),
        "agency_biweekly_plans": _money(_sum_amount(biweekly_rows, "agency_cycle_amount")),
        "agency_biweekly_plans_amount": _sum_amount(biweekly_rows, "agency_cycle_amount"),
        "agency_monthly_plans": _money(_sum_amount(monthly_rows, "agency_cycle_amount")),
        "agency_monthly_plans_amount": _sum_amount(monthly_rows, "agency_cycle_amount"),
        "weekly_agency_all": _money(_sum_amount(rows, "weekly_agency_amount")),
        "weekly_agency_all_amount": _sum_amount(rows, "weekly_agency_amount"),
        "copay_before_all": _money(_sum_amount(rows, "copay_before_amount")),
        "copay_cycle_all": _money(_sum_amount(rows, "copay_cycle_amount")),
        "agency_cycle_all": _money(_sum_amount(rows, "agency_cycle_amount")),
        "weekly_count": len(weekly_rows),
        "biweekly_count": len(biweekly_rows),
        "monthly_count": len(monthly_rows),
    }


def four_cs_payout_report_bundle(filters=None, *, unit=None, admin=False, default_status="Active"):
    filters = dict(filters or {})
    if not admin:
        filters["unit"] = ""
    if "status" not in filters:
        filters["status"] = default_status
    all_rows = four_cs_payout_rows(unit=None if admin else unit, admin=admin)
    full_options = four_cs_payout_options(all_rows)
    scoped = filter_four_cs_payout_rows(all_rows, {"unit": filters.get("unit")}) if admin and filters.get("unit") else all_rows
    options = four_cs_payout_options(scoped)
    if admin:
        options["units"] = full_options["units"] or [
            (item.slug, item.name)
            for item in PortalUnit.objects.filter(is_active=True).order_by("name")
            if not is_placeholder_unit(item)
        ]
        options["scholarship_funds"] = full_options["scholarship_funds"]
    rows = filter_four_cs_payout_rows(all_rows, filters)
    totals = four_cs_payout_totals(rows)
    summary = (
        f"{totals['member_count']} 4Cs member"
        f"{'' if totals['member_count'] == 1 else 's'}"
        f" · weekly copay ${totals['weekly_copay_all']}"
        f" · weekly 4Cs ${totals['weekly_agency_all']}"
    )
    return {
        "report_rows": rows,
        "filter_options": options,
        "totals": totals,
        "summary": summary,
        "columns": PRINT_COLUMNS,
    }


def four_cs_payout_csv_response(bundle, filename="4cs-expected-amounts.csv"):
    import csv

    rows = bundle.get("report_rows") or []
    totals = bundle.get("totals") or four_cs_payout_totals(rows)
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    writer = csv.writer(response)
    writer.writerow([label for _key, label in PRINT_COLUMNS])
    for row in rows:
        writer.writerow([row.get(key, "") for key, _label in PRINT_COLUMNS])
    writer.writerow(
        [
            f"Total ({totals.get('member_count') or 0} members)",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            totals.get("copay_before_all") or "0.00",
            totals.get("copay_cycle_all") or "0.00",
            totals.get("weekly_copay_all") or "0.00",
            totals.get("agency_cycle_all") or "0.00",
            totals.get("weekly_agency_all") or "0.00",
            "",
        ]
    )
    return response
