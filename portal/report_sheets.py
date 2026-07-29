"""Context helpers for blank printable staff report sheets."""

from datetime import date, datetime, timedelta

from .demo_data import ATTENDANCE_SESSION, PROGRAM_ROSTER

EXTRA_BLANK_ROWS = 4


def parse_sheet_date(raw):
    """Parse ?date=YYYY-MM-DD or return today."""
    if raw:
        try:
            return datetime.strptime(raw.strip(), "%Y-%m-%d").date()
        except ValueError:
            pass
    return date.today()


def _weekday_monday(anchor):
    """Monday of the week containing anchor."""
    return anchor - timedelta(days=anchor.weekday())


def _format_long(d):
    return d.strftime("%A, %B %d, %Y")


def _format_short(d):
    return d.strftime("%b %d")


def _format_iso(d):
    return d.isoformat()


def sheet_meta(unit_name=None, program=None):
    program = program or ATTENDANCE_SESSION["program"]
    unit = unit_name or ATTENDANCE_SESSION["unit"]
    return {"unit": unit, "program": program}


def enrolled_rows_for_sheet(sheet_date, live=False, unit=None, program=None):
    """Active/enrolled children for the unit at the given date."""
    if live and unit and program:
        from .attendance_service import build_roster

        roster = build_roster(unit, program, sheet_date)
        rows = [
            {
                "child": row["child"],
                "family": row.get("family", ""),
                "grade": row.get("grade", ""),
            }
            for row in roster
        ]
    else:
        rows = [
            {
                "child": row["child"],
                "family": row.get("family", ""),
                "grade": row.get("grade", ""),
            }
            for row in PROGRAM_ROSTER
            if row.get("status", "").lower() == "active"
        ]
        rows.sort(key=lambda row: row["child"].lower())

    return rows


def _sheet_roster_context(sheet_date, unit_name=None, program=None, live=False, unit=None, program_obj=None):
    enrolled_rows = enrolled_rows_for_sheet(sheet_date, live=live, unit=unit, program=program_obj)
    return {
        "enrolled_rows": enrolled_rows,
        "enrolled_count": len(enrolled_rows),
        "extra_blank_rows": range(EXTRA_BLANK_ROWS),
    }


def daily_blank_context(sheet_date, unit_name=None, program=None, live=False, unit=None, program_obj=None):
    meta = sheet_meta(unit_name, program)
    return {
        **meta,
        **_sheet_roster_context(sheet_date, unit_name, program, live, unit, program_obj),
        "sheet_date": sheet_date,
        "sheet_date_display": _format_long(sheet_date),
        "sheet_date_value": _format_iso(sheet_date),
    }


def weekly_blank_context(sheet_date, unit_name=None, program=None, live=False, unit=None, program_obj=None):
    meta = sheet_meta(unit_name, program)
    monday = _weekday_monday(sheet_date)
    weekdays = [monday + timedelta(days=i) for i in range(5)]
    friday = weekdays[4]
    return {
        **meta,
        **_sheet_roster_context(sheet_date, unit_name, program, live, unit, program_obj),
        "sheet_date": sheet_date,
        "sheet_date_value": _format_iso(sheet_date),
        "week_start_display": _format_long(monday),
        "week_end_display": _format_long(friday),
        "week_range_display": f"{monday.strftime('%B %d')} – {friday.strftime('%B %d, %Y')}",
        "week_days": [
            {
                "label": day.strftime("%a"),
                "date_short": _format_short(day),
                "date_display": day.strftime("%a, %b %d"),
                "iso": _format_iso(day),
            }
            for day in weekdays
        ],
    }


def signout_blank_context(sheet_date, unit_name=None, program=None, live=False, unit=None, program_obj=None):
    meta = sheet_meta(unit_name, program)
    return {
        **meta,
        **_sheet_roster_context(sheet_date, unit_name, program, live, unit, program_obj),
        "sheet_date": sheet_date,
        "sheet_date_display": _format_long(sheet_date),
        "sheet_date_value": _format_iso(sheet_date),
    }
