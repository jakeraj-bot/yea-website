"""Printable attendance report grouped by grade, with staff/admin filters."""

from datetime import timedelta

from .member_admin import is_placeholder_unit
from .models import AttendanceRecord, PortalChild, PortalProgram, PortalUnit
from .report_sheets import _weekday_monday, parse_sheet_date, week_day_columns
from .unit_visibility import children_for_unit, unit_label_for_child

BLANK = "—"
RANGE_DAY = "day"
RANGE_WEEK = "week"

STATUS_LABELS = {
    AttendanceRecord.STATUS_PRESENT: "Present",
    AttendanceRecord.STATUS_ABSENT: "Absent",
    AttendanceRecord.STATUS_EXPECTED: "Not arrived",
}

FILTER_KEYS = ("q", "unit", "program", "school", "grade", "date", "range", "status")

PRINT_COLUMNS = [
    ("child", "Child"),
    ("family", "Family"),
    ("grade", "Grade"),
    ("unit", "Unit"),
    ("school", "School"),
    ("program", "Program"),
    ("date", "Date"),
    ("status", "Status"),
    ("check_in", "Check in"),
    ("check_out", "Check out"),
]


def _status_label(status):
    return STATUS_LABELS.get(status or AttendanceRecord.STATUS_EXPECTED, "Not arrived")


def _parse_range(filters):
    filters = filters or {}
    raw_date = (filters.get("date") or "").strip()
    anchor = parse_sheet_date(raw_date) if raw_date else parse_sheet_date(None)
    mode = (filters.get("range") or RANGE_DAY).strip().lower()
    if mode not in {RANGE_DAY, RANGE_WEEK}:
        mode = RANGE_DAY
    if mode == RANGE_WEEK:
        monday = _weekday_monday(anchor)
        days = [monday + timedelta(days=i) for i in range(5)]
        return mode, days, days[0]
    return mode, [anchor], anchor


def _scope_children(*, unit=None, admin=False, unit_slug=""):
    if admin:
        if unit_slug:
            chosen = PortalUnit.objects.filter(slug=unit_slug, is_active=True).first()
            children = children_for_unit(chosen, active_only=True) if chosen else PortalChild.objects.none()
        else:
            children = PortalChild.objects.filter(is_active=True).select_related("family", "family__unit", "unit")
    else:
        children = children_for_unit(unit, active_only=True)
    return list(children.order_by("grade", "name", "id"))


def _programs_in_scope(*, unit=None, admin=False, unit_slug="", program_id=""):
    qs = PortalProgram.objects.filter(is_active=True).select_related("unit").order_by("unit__name", "name")
    if not admin and unit:
        qs = qs.filter(unit=unit)
    elif admin and unit_slug:
        qs = qs.filter(unit__slug=unit_slug)
    if program_id:
        qs = qs.filter(pk=program_id)
    return list(qs)


def attendance_grade_options(rows, programs):
    schools = sorted({row["school"] for row in rows if row.get("school") and row["school"] != BLANK}, key=str.lower)
    grades = sorted({row["grade"] for row in rows if row.get("grade") and row["grade"] != BLANK}, key=str.lower)
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
        "statuses": statuses,
        "units": units,
        "programs": [(str(program.pk), program.name if not program.unit_id else f"{program.name} · {program.unit.name}") for program in programs],
    }


def _record_lookup(children, programs, days):
    if not children or not programs or not days:
        return {}
    records = AttendanceRecord.objects.filter(
        child_id__in=[child.pk for child in children],
        program_id__in=[program.pk for program in programs],
        date__in=days,
    ).select_related("program")
    lookup = {}
    for record in records:
        lookup.setdefault((record.child_id, record.date), record)
    return lookup


def _base_row(child, program=None):
    family = child.family
    child_unit = child.unit or family.unit
    if is_placeholder_unit(child_unit or family.unit):
        return None
    unit_name, unit_slug = unit_label_for_child(child)
    school = (child.school or "").strip() or BLANK
    grade = (child.grade or "").strip() or BLANK
    return {
        "child_id": child.pk,
        "child": child.name,
        "family": family.name,
        "family_slug": family.slug,
        "family_id": family.pk,
        "grade": grade,
        "school": school,
        "unit": unit_name or (family.unit.name if family.unit_id else BLANK),
        "unit_slug": unit_slug or (family.unit.slug if family.unit_id else ""),
        "program": program.name if program else BLANK,
        "program_id": str(program.pk) if program else "",
    }


def _matches_filters(row, filters):
    filters = filters or {}
    query = (filters.get("q") or "").strip().lower()
    school = (filters.get("school") or "").strip()
    grade = (filters.get("grade") or "").strip()
    unit = (filters.get("unit") or "").strip()
    status = (filters.get("status") or "").strip()
    if unit and row.get("unit_slug") != unit:
        return False
    if query:
        hay = f"{row.get('child') or ''} {row.get('family') or ''}".lower()
        if query not in hay:
            return False
    if school and (row.get("school") or "").lower() != school.lower():
        return False
    if grade and (row.get("grade") or "").lower() != grade.lower():
        return False
    if status and (row.get("status") or "").lower() != status.lower():
        return False
    return True


def _group_by_grade(rows):
    grouped = {}
    for row in rows:
        key = row.get("grade") or "No grade"
        grouped.setdefault(key, []).append(row)
    groups = []
    for grade in sorted(grouped, key=lambda name: (name == "No grade", name.lower())):
        items = grouped[grade]
        present = sum(1 for row in items if row.get("status_key") == AttendanceRecord.STATUS_PRESENT)
        absent = sum(1 for row in items if row.get("status_key") == AttendanceRecord.STATUS_ABSENT)
        groups.append(
            {
                "grade": grade,
                "rows": items,
                "count": len(items),
                "present": present,
                "absent": absent,
            }
        )
    return groups


def attendance_grade_report_bundle(filters=None, *, unit=None, admin=False):
    filters = dict(filters or {})
    if not admin:
        filters["unit"] = ""
    mode, days, anchor = _parse_range(filters)
    program_id = (filters.get("program") or "").strip()
    unit_slug = (filters.get("unit") or "").strip() if admin else ""
    children = _scope_children(unit=unit, admin=admin, unit_slug=unit_slug)
    all_programs = _programs_in_scope(unit=unit, admin=admin, unit_slug=unit_slug)
    programs = _programs_in_scope(unit=unit, admin=admin, unit_slug=unit_slug, program_id=program_id)
    if not programs and not program_id:
        programs = all_programs
    lookup = _record_lookup(children, programs, days)
    default_program = programs[0] if programs else None
    rows = []
    option_rows = []

    if mode == RANGE_WEEK:
        week_days = week_day_columns(days)
        friday = days[-1]
        for child in children:
            base = _base_row(child, default_program)
            if not base:
                continue
            day_marks = []
            present_count = 0
            status_keys = []
            for day in days:
                record = lookup.get((child.pk, day))
                status = record.status if record else AttendanceRecord.STATUS_EXPECTED
                status_keys.append(status)
                present = status == AttendanceRecord.STATUS_PRESENT
                if present:
                    present_count += 1
                day_marks.append(
                    {
                        "iso": day.isoformat(),
                        "present": present,
                        "status": _status_label(status),
                        "status_key": status,
                    }
                )
            if AttendanceRecord.STATUS_PRESENT in status_keys:
                status_key = AttendanceRecord.STATUS_PRESENT
            elif AttendanceRecord.STATUS_ABSENT in status_keys and AttendanceRecord.STATUS_PRESENT not in status_keys:
                status_key = AttendanceRecord.STATUS_ABSENT
            else:
                status_key = AttendanceRecord.STATUS_EXPECTED
            row = {
                **base,
                "date": f"{days[0].isoformat()} – {friday.isoformat()}",
                "status": _status_label(status_key),
                "status_key": status_key,
                "check_in": BLANK,
                "check_out": BLANK,
                "days": day_marks,
                "total": present_count,
            }
            option_rows.append(row)
            if _matches_filters(row, filters):
                rows.append(row)
        period_display = f"{days[0].strftime('%B %d')} – {friday.strftime('%B %d, %Y')}"
    else:
        week_days = []
        day = days[0]
        for child in children:
            record = lookup.get((child.pk, day))
            program = record.program if record else default_program
            base = _base_row(child, program)
            if not base:
                continue
            status_key = record.status if record else AttendanceRecord.STATUS_EXPECTED
            row = {
                **base,
                "date": day.isoformat(),
                "status": _status_label(status_key),
                "status_key": status_key,
                "check_in": record.check_in_time.strftime("%-I:%M %p") if record and record.check_in_time else BLANK,
                "check_out": record.check_out_time.strftime("%-I:%M %p") if record and record.check_out_time else BLANK,
                "days": [],
                "total": 1 if status_key == AttendanceRecord.STATUS_PRESENT else 0,
            }
            option_rows.append(row)
            if _matches_filters(row, filters):
                rows.append(row)
        period_display = day.strftime("%A, %B %d, %Y")

    scoped_for_options = option_rows
    if admin and unit_slug:
        scoped_for_options = [row for row in option_rows if row.get("unit_slug") == unit_slug]
    options = attendance_grade_options(scoped_for_options, all_programs)
    if admin:
        options["units"] = [
            (item.slug, item.name)
            for item in PortalUnit.objects.filter(is_active=True).order_by("name")
            if not is_placeholder_unit(item)
        ]
    return {
        "report_rows": rows,
        "grade_groups": _group_by_grade(rows),
        "filter_options": options,
        "generated_date": anchor.strftime("%B %d, %Y"),
        "period_display": period_display,
        "range_mode": mode,
        "week_days": week_days,
        "sheet_date": anchor.isoformat(),
        "columns": PRINT_COLUMNS,
    }
