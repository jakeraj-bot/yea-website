"""Live data builders for staff portal pages."""

from datetime import date, timedelta
from decimal import Decimal

from django.db.models import Count, Q
from django.utils import timezone

from enrollment.portal_integration import applications_for_staff

from .attendance_service import (
    build_roster,
    build_session_context,
    get_active_program,
    get_unit,
    portal_is_live,
)
from .demo_data import (
    AGENCY_UNIT_DATA,
    CHILD_MEDICAL,
    DASHBOARD_ALERTS,
    FAMILIES,
    FAMILY_DETAILS,
    MEDICAL_ALERT_TYPES,
    MEDICAL_REPORT_META,
    PROGRAM_ROSTER,
    STAFF_PROGRAMS_SCHOOL_18,
    get_family_policies,
    get_member_policy_summaries,
)
from .live_services import count_messages_unread_live
from .medical import alerts_from_medical_dict, application_for_child, medical_from_application
from .models import AttendanceRecord, PortalChild, PortalFamily, PortalProgram
from .unit_visibility import children_for_unit, families_qs_for_unit
from .parent_services import get_parent_policy_data_live
from .pickup_services import pickup_report_data, pickup_report_programs


def get_programs_for_unit(unit):
    programs = PortalProgram.objects.filter(unit=unit, is_active=True).order_by("name")
    if not programs.exists():
        return []
    rows = []
    for program in programs:
        enrolled = children_for_unit(unit, active_only=True).count()
        rows.append(
            {
                "name": program.name,
                "enrolled": enrolled,
                "dates": "Active season",
                "slug": program.name.lower().replace(" ", "-").replace("–", "-"),
                "program_id": program.pk,
            }
        )
    return rows


def get_program_roster(unit, program_name=None):
    children = children_for_unit(unit, active_only=True).order_by("name")
    if not children.exists():
        return []
    roster = []
    for child in children:
        roster.append(
            {
                "child": child.name,
                "family": child.family.name,
                "family_slug": child.family.slug,
                "grade": child.grade,
                "status": child.family.status or "Active",
            }
        )
    return roster


def get_member_summaries_for_unit(unit):
    families = list(families_qs_for_unit(unit).order_by("name"))
    if not families:
        return []
    summaries = []
    for family in families:
        policy_data = get_parent_policy_data_live(family)
        if not policy_data:
            continue
        children = policy_data.get("children") or []
        if unit:
            from .unit_visibility import visible_child_names

            allowed = visible_child_names(family, unit, include_pending=True)
            children = [
                child
                for child in children
                if (child.get("child_name") or "").strip().lower() in allowed
            ]
        child_summary = ", ".join(
            f"{child['child_name'].split()[0]} {child['signed_count']}/{child['total_count']}"
            for child in children
            if child.get("child_name")
        )
        summaries.append(
            {
                "slug": family.slug,
                "family_name": policy_data.get("family_name") or family.name,
                "primary_contact": family.primary_contact or family.name,
                "children": [child.get("child_name", "") for child in children if child.get("child_name")],
                "child_count": policy_data.get("child_count", len(children)),
                "unit": policy_data.get("unit") or unit.name,
                "signed_count": policy_data.get("signed_count", 0),
                "total_count": policy_data.get("total_count", 0),
                "policies_per_child": policy_data.get("policies_per_child", 0),
                "complete": policy_data.get("complete", False),
                "program_year": policy_data.get("program_year", ""),
                "child_summary": child_summary,
            }
        )
    return summaries


def get_family_policies_for_staff(family_slug, family_id=None, unit=None):
    from .member_admin import resolve_family
    from .unit_visibility import visible_child_names

    family = resolve_family(family_slug=family_slug, family_id=family_id, unit=unit)
    if family:
        live = get_parent_policy_data_live(family)
        if live:
            if unit:
                allowed = visible_child_names(family, unit, include_pending=True)
                live = dict(live)
                live["children"] = [
                    child
                    for child in (live.get("children") or [])
                    if (child.get("child_name") or "").strip().lower() in allowed
                ]
            return live
        if portal_is_live():
            return None
    if portal_is_live():
        return None
    return get_family_policies(family_slug)


def get_medical_data_for_child(child_name, family_slug=None):
    demo = CHILD_MEDICAL.get(child_name, {})
    children = PortalChild.objects.select_related("family")
    if family_slug:
        child = children.filter(family__slug=family_slug, name=child_name).first()
    else:
        child = children.filter(name=child_name).first()
    if not child:
        app = application_for_child(child_name=child_name, family_slug=family_slug)
        if app:
            medical = medical_from_application(app)
            alerts = alerts_from_medical_dict(medical)
            return {**medical, "alerts": alerts, "staff_notes": demo.get("staff_notes", "")}
        if portal_is_live():
            return {"alerts": [], "staff_notes": ""}
        return demo

    app = application_for_child(child=child, child_name=child_name)
    if app:
        medical = medical_from_application(app)
        alerts = alerts_from_medical_dict(medical)
        return {
            **medical,
            "alerts": alerts,
            "staff_notes": demo.get("staff_notes", child.note or ""),
        }
    if portal_is_live():
        return {"alerts": [], "staff_notes": child.note or ""}
    return demo


def build_medical_report_rows(unit):
    children = children_for_unit(unit, active_only=True).order_by("name")
    if not children.exists():
        if portal_is_live():
            return []
        from .demo_data import build_medical_report_rows

        return build_medical_report_rows()

    rows = []
    for child in children:
        medical = get_medical_data_for_child(child.name, child.family.slug)
        alerts = []
        for item in medical.get("alerts", []):
            key = item.get("key", "")
            definition = MEDICAL_ALERT_TYPES.get(key, {})
            alerts.append(
                {
                    "key": key,
                    "label": definition.get("label", key),
                    "symbol": definition.get("symbol", "?"),
                    "detail": item.get("detail", ""),
                }
            )
        rows.append(
            {
                "child": child.name,
                "family": child.family.name,
                "grade": child.grade,
                "program": child.family.program_label or "After-School",
                "has_medical": bool(alerts),
                "alerts": alerts,
                "allergies": medical.get("allergies") or "None reported",
                "medications": medical.get("medications") or "None reported",
                "doctor_name": medical.get("doctor_name") or "—",
                "doctor_phone": medical.get("doctor_phone") or "—",
                "plans_on_file": medical.get("plans_on_file") or [],
                "staff_notes": medical.get("staff_notes") or "",
            }
        )
    return rows


def medical_report_meta(unit):
    program = get_active_program(unit)
    return {
        "unit": unit.name if unit else MEDICAL_REPORT_META["unit"],
        "program": program.name if program else MEDICAL_REPORT_META["program"],
        "generated_date": timezone.localdate().strftime("%B %d, %Y"),
    }


def _school_name_for_child(child):
    school = (child.school or "").strip()
    if school:
        return school
    app = application_for_child(child=child, child_name=child.name)
    if app and app.student_school:
        return app.student_school.strip()
    return ""


def build_school_bus_roster(unit):
    children = children_for_unit(unit, active_only=True).order_by("name")
    if not children.exists():
        if portal_is_live():
            return []
        from .demo_data import SCHOOL_BUS_ROSTER_SECTIONS

        return SCHOOL_BUS_ROSTER_SECTIONS

    grouped = {}
    for child in children:
        school = _school_name_for_child(child) or "School not listed"
        grouped.setdefault(school, []).append(
            {
                "child": child.name,
                "grade": child.grade or "—",
                "family": child.family.name,
                "family_slug": child.family.slug,
                "child_id": child.pk,
                "school": school,
            }
        )

    sections = []
    for school in sorted(grouped, key=lambda value: value.lower()):
        rows = sorted(grouped[school], key=lambda row: row["child"].lower())
        sections.append({"school": school, "children": rows})
    return sections


def school_bus_roster_school_names(sections):
    return [section["school"] for section in sections]


def filter_school_bus_roster(sections, selected_schools):
    wanted = {str(name).strip() for name in selected_schools or [] if str(name).strip()}
    if not wanted:
        return list(sections)
    return [section for section in sections if section["school"] in wanted]


def school_bus_report_meta(unit):
    program = get_active_program(unit)
    return {
        "unit": unit.name if unit else MEDICAL_REPORT_META["unit"],
        "program": program.name if program else MEDICAL_REPORT_META["program"],
        "generated_date": timezone.localdate().strftime("%B %d, %Y"),
    }


def pickup_report_for_unit(unit, program_filter="all"):
    from .live_services import family_profile_live

    families = []
    family_details = {}
    for family in families_qs_for_unit(unit).prefetch_related("children", "children__unit").order_by("name"):
        profile = family_profile_live(family.slug, unit=unit, family_id=family.pk)
        if not profile:
            continue
        families.append(
            {
                "slug": family.slug,
                "name": family.name,
                "children": [child.get("name", "") for child in profile.get("children") or []],
                "program": family.program_label or "After-School 2026–27",
            }
        )
        family_details[family.slug] = profile
    if not families:
        return pickup_report_programs([], {}), pickup_report_data(
            [], {}, program_filter=program_filter
        )
    return pickup_report_programs(families, family_details), pickup_report_data(
        families, family_details, program_filter=program_filter
    )


def _program_label_for_child(child, app=None):
    if getattr(child, "is_drop_off", False):
        return "Drop-off program"
    if app:
        return app.get_program_display()
    return child.family.program_label or "After-school program"


def emergency_contact_report_for_unit(unit):
    """One row per child/contact (or a gap row when a child has none). Unit-scoped."""
    from .medical import application_for_child
    from .pickup_services import (
        child_emergency_contact_rows,
        emergency_contact_report_data,
        emergency_contacts_from_application,
    )
    from .unit_visibility import children_for_unit, unit_label_for_child

    children = children_for_unit(unit, active_only=True).order_by("family__name", "name")
    if not children.exists():
        if portal_is_live():
            return []
        from .demo_data import FAMILIES, FAMILY_DETAILS

        return emergency_contact_report_data(FAMILIES, FAMILY_DETAILS)

    rows = []
    for child in children:
        unit_name, unit_slug = unit_label_for_child(child)
        app = application_for_child(child=child, child_name=child.name)
        contacts = emergency_contacts_from_application(app)
        school = (child.school or (app.student_school if app else "") or "").strip()
        grade = child.grade or (app.get_student_grade_display() if app else "") or "—"
        program = _program_label_for_child(child, app)
        base = {
            "child": child.name,
            "family": child.family.name,
            "family_slug": child.family.slug,
            "unit": unit_name or (unit.name if unit else ""),
            "unit_slug": unit_slug or (unit.slug if unit else ""),
            "program": program,
            "grade": grade or "—",
            "school": school or "—",
        }
        rows.extend(child_emergency_contact_rows(base, contacts))
    rows.sort(key=lambda row: (row["unit"].lower(), row["child"].lower(), row["contact_name"].lower()))
    return rows


def emergency_contact_report_for_units(units=None):
    """Admin: all visible units, or a given list. Children stay on their own site."""
    from .member_admin import is_placeholder_unit
    from .models import PortalUnit

    if units is None:
        units = [
            unit
            for unit in PortalUnit.objects.filter(is_active=True).order_by("name")
            if not is_placeholder_unit(unit)
        ]
    rows = []
    for unit in units:
        rows.extend(emergency_contact_report_for_unit(unit))
    rows.sort(key=lambda row: (row["unit"].lower(), row["child"].lower(), row["contact_name"].lower()))
    return rows


def build_dashboard_live(unit, program):
    today = timezone.localdate()
    roster = build_roster(unit, program, today) if unit and program else []
    session = build_session_context(unit, program, today, roster) if unit and program else {}
    apps = applications_for_staff(unit) if unit else []
    open_apps = [a for a in apps if a.get("status") in ("Under review", "Pending documents", "Waitlist")]
    past_due = families_qs_for_unit(unit).filter(balance__gt=Decimal("0")).count()
    unread = count_messages_unread_live(for_admin=False)

    alerts = []
    if open_apps:
        alerts.append(
            {
                "text": f"{len(open_apps)} application{'s' if len(open_apps) != 1 else ''} awaiting review",
                "link_name": "portal_staff_page",
                "link_arg": "applications",
            }
        )
    if past_due:
        alerts.append(
            {
                "text": f"{past_due} {'families' if past_due != 1 else 'family'} with balance due",
                "link_name": "portal_staff_page",
                "link_arg": "families",
            }
        )
    overdue_family = (
        families_qs_for_unit(unit).filter(balance__gt=Decimal("0")).order_by("-balance").first()
    )
    if overdue_family:
        alerts.append(
            {
                "text": f"{overdue_family.name} — ${overdue_family.balance:.2f} balance due",
                "link_name": "portal_staff_family_billing",
                "link_kw": {"family_slug": overdue_family.slug},
            }
        )
    if unread:
        alerts.append(
            {
                "text": f"{unread} unread team message{'s' if unread != 1 else ''}",
                "link_name": "portal_staff_page",
                "link_arg": "messages",
            }
        )
    from .drop_off_services import pickup_rows

    drop_off_today = pickup_rows(unit=unit, care_date=today)
    paid_pickups = [row for row in drop_off_today if row["paid"]]
    waiting = [row for row in drop_off_today if not row["paid"]]
    if paid_pickups:
        alerts.append(
            {
                "text": f"{len(paid_pickups)} drop-off pickup{'s' if len(paid_pickups) != 1 else ''} today",
                "link_name": "portal_staff_page",
                "link_arg": "drop-off-pickup",
            }
        )
    if waiting:
        alerts.append(
            {
                "text": f"{len(waiting)} drop-off request{'s' if len(waiting) != 1 else ''} waiting for payment",
                "link_name": "portal_staff_page",
                "link_arg": "drop-off-pickup",
            }
        )
    if not alerts:
        pass

    return {
        "attendance": session or {
            "date_display": today.strftime("%A, %B %d, %Y"),
            "summary": {
                "present": 0,
                "not_arrived": 0,
                "absent": 0,
                "enrolled": 0,
                "checked_out": 0,
            },
        },
        "application_count": len(open_apps),
        "alerts": alerts,
    }


def _normalized_grade_list(grades):
    if not grades:
        return []
    if isinstance(grades, str):
        grades = [part.strip() for part in grades.split(",")]
    return [str(item).strip() for item in grades if str(item).strip()]


def _grade_sort_key(grade):
    raw = (grade or "").strip()
    lower = raw.lower()
    if lower in {"k", "kindergarten"}:
        return (0, 0, lower)
    digits = "".join(ch for ch in raw if ch.isdigit())
    if digits:
        return (1, int(digits), lower)
    return (2, 0, lower)


def _weekly_status_label(status_keys):
    if AttendanceRecord.STATUS_PRESENT in status_keys:
        return AttendanceRecord.STATUS_PRESENT, "Present"
    if AttendanceRecord.STATUS_ABSENT in status_keys:
        return AttendanceRecord.STATUS_ABSENT, "Absent"
    return AttendanceRecord.STATUS_EXPECTED, "Not arrived"


def resolve_weekly_attendance_unit(requested_slug, *, header_unit=None, allowed_units=None, admin=False):
    """Pick the weekly-attendance unit without leaking sites the viewer cannot open."""
    from .member_admin import is_placeholder_unit
    from .models import PortalUnit

    requested_slug = (requested_slug or "").strip()
    if admin:
        if not requested_slug:
            return None
        match = PortalUnit.objects.filter(slug=requested_slug, is_active=True).first()
        if match and not is_placeholder_unit(match):
            return match
        return None

    allowed = []
    if allowed_units is not None:
        allowed = [item for item in allowed_units if item and not is_placeholder_unit(item)]
    elif header_unit and not is_placeholder_unit(header_unit):
        allowed = [header_unit]
    if requested_slug:
        for item in allowed:
            if item.slug == requested_slug:
                return item
    return header_unit


def _weekly_unit_choices(*, admin=False, allowed_units=None, unit=None):
    from .member_admin import is_placeholder_unit
    from .models import PortalUnit

    if admin:
        source = list(PortalUnit.objects.filter(is_active=True).order_by("name"))
    elif allowed_units is not None:
        source = list(allowed_units)
    else:
        source = [unit] if unit else []
    choices = [(item.slug, item.name) for item in source if item and not is_placeholder_unit(item)]
    choices.sort(key=lambda pair: (pair[1] or "").lower())
    return choices


def weekly_attendance_report_data(unit, program, anchor_date=None, filters=None, *, admin=False, allowed_units=None):
    """Mon–Fri present/absent marks plus printable weekday column labels.

    Empty grade filter includes every grade. Selected grades stay on one sheet.
    Staff can pick one allowed unit (default: the header unit), including a child
    at that site whose family account lives elsewhere. Admins can pick one unit
    or all units.
    """
    from .member_admin import is_placeholder_unit
    from .models import PortalProgram
    from .report_sheets import parse_sheet_date, week_day_columns, _weekday_monday
    from .unit_visibility import unit_label_for_child

    filters = dict(filters or {})
    raw_date = (filters.get("date") or "").strip()
    if raw_date:
        anchor_date = parse_sheet_date(raw_date)
    else:
        anchor_date = anchor_date or timezone.localdate()

    monday = _weekday_monday(anchor_date)
    weekdays = [monday + timedelta(days=i) for i in range(5)]
    friday = weekdays[4]
    week_days = week_day_columns(weekdays)
    selected_grades = _normalized_grade_list(filters.get("grades") or filters.get("grade"))
    selected_grade_keys = {grade.lower() for grade in selected_grades}
    query = (filters.get("q") or "").strip().lower()
    school = (filters.get("school") or "").strip()
    status_filter = (filters.get("status") or "").strip()
    program_id = (filters.get("program") or "").strip()
    unit_slug = (filters.get("unit") or "").strip()
    scoped_unit = resolve_weekly_attendance_unit(
        unit_slug, header_unit=unit, allowed_units=allowed_units, admin=admin
    )

    if admin and not scoped_unit:
        roster_children = [
            child
            for child in PortalChild.objects.filter(is_active=True)
            .select_related("family", "family__unit", "unit")
            .order_by("name", "id")
            if not is_placeholder_unit(child.unit or (child.family.unit if child.family_id else None))
        ]
    else:
        roster_children = list(children_for_unit(scoped_unit, active_only=True).order_by("name", "id"))

    programs_qs = PortalProgram.objects.filter(is_active=True).select_related("unit").order_by("unit__name", "name")
    if scoped_unit:
        programs_qs = programs_qs.filter(unit=scoped_unit)
    all_programs = list(programs_qs)

    chosen_program = program
    if program_id:
        chosen_program = next((item for item in all_programs if str(item.pk) == program_id), None)
    elif chosen_program and scoped_unit and chosen_program.unit_id != scoped_unit.pk:
        chosen_program = get_active_program(scoped_unit)
    if chosen_program and scoped_unit and chosen_program.unit_id != scoped_unit.pk:
        chosen_program = None
    record_programs = [chosen_program] if chosen_program else all_programs

    present_lookup = {}
    status_lookup = {}
    if roster_children and record_programs:
        records = AttendanceRecord.objects.filter(
            program_id__in=[item.pk for item in record_programs if item],
            date__in=weekdays,
            child_id__in=[child.pk for child in roster_children],
        )
        for record in records:
            key = (record.child_id, record.date)
            is_present = record.status == AttendanceRecord.STATUS_PRESENT
            if key not in present_lookup or is_present:
                present_lookup[key] = is_present
                status_lookup[key] = record.status

    rows = []
    option_statuses = set()
    for child in roster_children:
        family = child.family
        grade = (child.grade or "").strip() or "—"
        school_name = (child.school or "").strip()
        unit_name, child_unit_slug = unit_label_for_child(child)
        day_marks = [bool(present_lookup.get((child.pk, day))) for day in weekdays]
        status_keys = [status_lookup.get((child.pk, day)) for day in weekdays]
        _status_key, status_label = _weekly_status_label(status_keys)
        option_statuses.add(status_label)
        row = {
            "child": child.name,
            "family": family.name if family else "",
            "grade": grade,
            "school": school_name,
            "unit": unit_name,
            "unit_slug": child_unit_slug,
            "program": chosen_program.name if chosen_program else (record_programs[0].name if record_programs else ""),
            "days": day_marks,
            "weekday_labels": [column["label"] for column in week_days],
            "total": sum(1 for present in day_marks if present),
            "status": status_label,
        }
        if selected_grade_keys and grade.lower() not in selected_grade_keys:
            continue
        if query:
            hay = f"{row['child']} {row['family']}".lower()
            if query not in hay:
                continue
        if school and school_name.lower() != school.lower():
            continue
        if status_filter and status_label.lower() != status_filter.lower():
            continue
        rows.append(row)

    filter_options = {
        "grades": sorted(
            {(child.grade or "").strip() for child in roster_children if (child.grade or "").strip()},
            key=_grade_sort_key,
        ),
        "schools": sorted(
            {(child.school or "").strip() for child in roster_children if (child.school or "").strip()},
            key=str.lower,
        ),
        "programs": [
            (str(item.pk), item.name if not admin or not item.unit_id else f"{item.name} · {item.unit.name}")
            for item in all_programs
        ],
        "units": _weekly_unit_choices(admin=admin, allowed_units=allowed_units, unit=unit),
        "statuses": sorted(option_statuses, key=str.lower),
    }
    return {
        "weekly_rows": rows,
        "week_days": week_days,
        "week_range_display": f"{monday.strftime('%B %d')} – {friday.strftime('%B %d, %Y')}",
        "filter_options": filter_options,
        "sheet_date": anchor_date.isoformat(),
        "generated_date": timezone.localdate().strftime("%B %d, %Y"),
        "selected_grades": selected_grades,
        "selected_unit_slug": scoped_unit.slug if scoped_unit else "",
        "selected_unit_name": scoped_unit.name if scoped_unit else ("All units" if admin else ""),
        "unit_filter_allows_all": admin,
    }

