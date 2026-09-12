"""Month calendar of one child's attendance records. Never invents days."""

from calendar import SUNDAY, Calendar
from datetime import date
from urllib.parse import parse_qsl, urlencode

from django.utils.dateparse import parse_date
from django.utils.formats import date_format

from .attendance_service import format_time_display
from .models import AttendanceRecord
from .unit_visibility import child_belongs_to_unit


WEEKDAYS = ("Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat")

MARK_PRESENT = "present"
MARK_ABSENT = "absent"
MARK_UNMARKED = "unmarked"

MARK_LABELS = {
    MARK_PRESENT: "Present",
    MARK_ABSENT: "Absent",
    MARK_UNMARKED: "Not marked",
}


def parse_calendar_month(raw, fallback=None):
    fallback = fallback or date.today()
    text = (raw or "").strip()
    if text:
        parsed = parse_date(f"{text}-01") if len(text) == 7 and text[4] == "-" else parse_date(text)
        if parsed:
            return date(parsed.year, parsed.month, 1)
    return date(fallback.year, fallback.month, 1)


def shift_month(month_start, delta):
    month = month_start.month + delta
    year = month_start.year
    while month < 1:
        month += 12
        year -= 1
    while month > 12:
        month -= 12
        year += 1
    return date(year, month, 1)


def merge_attendance_query(base_query, **updates):
    items = dict(parse_qsl(base_query or "", keep_blank_values=True))
    for key, value in updates.items():
        if value in (None, ""):
            items.pop(key, None)
        else:
            items[key] = str(value)
    return urlencode(items)


def resolve_account_child(family, *, child_id=None, child_name=None, unit=None):
    """Return the visible enrolled child for this account, or None."""
    if not family:
        return None
    children = [
        child
        for child in family.children.filter(is_active=True).select_related("unit", "family", "family__unit")
        if child_belongs_to_unit(child, unit)
    ]
    child_id_text = str(child_id).strip() if child_id not in (None, "") else ""
    if child_id_text:
        for child in children:
            if str(child.pk) == child_id_text:
                return child
        return None
    name = (child_name or "").strip().casefold()
    if name:
        for child in children:
            if child.name.strip().casefold() == name:
                return child
    return children[0] if children else None


def _mark_for_records(records):
    if not records:
        return MARK_UNMARKED
    statuses = {record.status for record in records}
    if AttendanceRecord.STATUS_PRESENT in statuses:
        return MARK_PRESENT
    if AttendanceRecord.STATUS_ABSENT in statuses:
        return MARK_ABSENT
    return MARK_UNMARKED


def _record_detail(record):
    return {
        "status": record.status,
        "status_label": dict(AttendanceRecord.STATUS_CHOICES).get(record.status, record.status),
        "check_in": format_time_display(record.check_in_time),
        "check_out": format_time_display(record.check_out_time),
        "method": record.method or "",
        "note": record.note or "",
        "program": record.program.name if record.program_id else "",
        "has_record": True,
    }


def child_attendance_records(child, month_start):
    if not child or not getattr(child, "pk", None):
        return []
    year, month = month_start.year, month_start.month
    return list(
        AttendanceRecord.objects.filter(child=child, date__year=year, date__month=month)
        .select_related("program")
        .order_by("date", "program_id")
    )


def child_attendance_month(child, month_start, *, selected_day=None):
    """Build a Sunday-start month grid from stored attendance only."""
    records = child_attendance_records(child, month_start)
    by_date = {}
    for record in records:
        by_date.setdefault(record.date, []).append(record)

    weeks = []
    for week in Calendar(firstweekday=SUNDAY).monthdatescalendar(month_start.year, month_start.month):
        days = []
        for day in week:
            day_records = by_date.get(day, []) if day.month == month_start.month else []
            mark = _mark_for_records(day_records) if day.month == month_start.month else ""
            days.append(
                {
                    "date": day,
                    "iso": day.isoformat(),
                    "day": day.day,
                    "in_month": day.month == month_start.month,
                    "is_today": day == date.today(),
                    "is_selected": bool(selected_day and day == selected_day),
                    "mark": mark,
                    "mark_label": MARK_LABELS.get(mark, ""),
                    "has_record": bool(day_records),
                    "records": [_record_detail(record) for record in day_records],
                }
            )
        weeks.append(days)

    selected = None
    if selected_day:
        for week in weeks:
            for day in week:
                if day["iso"] == selected_day.isoformat() and day["in_month"]:
                    selected = day
                    break
    return {
        "child_id": getattr(child, "pk", None),
        "child_name": getattr(child, "name", "") if child else "",
        "month_start": month_start,
        "month_value": month_start.strftime("%Y-%m"),
        "month_label": date_format(month_start, "F Y"),
        "prev_month": shift_month(month_start, -1).strftime("%Y-%m"),
        "next_month": shift_month(month_start, 1).strftime("%Y-%m"),
        "weekdays": WEEKDAYS,
        "weeks": weeks,
        "selected": selected,
        "selected_day": selected_day,
    }


def visible_child_for_attendance(family, request, unit=None):
    list_child_id = request.GET.get("child_id")
    list_child = request.GET.get("child")
    child = resolve_account_child(
        family,
        child_id=list_child_id,
        child_name=list_child,
        unit=unit,
    )
    if child:
        return child
    if list_child_id or (list_child or "").strip():
        return None
    return resolve_account_child(family, unit=unit)
