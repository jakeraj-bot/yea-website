"""School-week contract math for 4Cs / agency billing."""

from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_date as parse_iso_date


ZERO = Decimal("0.00")
MONEY = Decimal("0.01")
SCHOOL_DAYS = 5
# Weekly parent copay posts on Thursday for the following school week.
FOUR_CS_WEEKLY_POST_WEEKDAY = 3


def parse_money(value, allow_blank=True):
    raw = "" if value is None else str(value).replace(",", "").strip()
    if not raw:
        if allow_blank:
            return ZERO
        raise ValueError("Enter a valid dollar amount.")
    try:
        amount = Decimal(raw)
    except (InvalidOperation, TypeError):
        raise ValueError("Enter a valid dollar amount.")
    if amount < 0:
        raise ValueError("Amount cannot be negative.")
    return amount.quantize(MONEY)


def weekly_from_daily(daily):
    daily = daily if isinstance(daily, Decimal) else parse_money(daily)
    return (daily * Decimal(SCHOOL_DAYS)).quantize(MONEY)


def format_week_label(week_start, week_end):
    def _fmt(day):
        return f"{day.month}/{day.day}/{day.strftime('%y')}"

    return f"{_fmt(week_start)}–{_fmt(week_end)}"


def parse_flexible_date(raw):
    text = "" if raw is None else str(raw).strip()
    if not text:
        return None
    parsed = parse_iso_date(text)
    if parsed:
        return parsed
    for fmt in ("%m/%d/%Y", "%m/%d/%y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    parts = text.replace("-", "/").split("/")
    if len(parts) == 3:
        try:
            month, day, year = int(parts[0]), int(parts[1]), int(parts[2])
            if year < 100:
                year += 2000
            return date(year, month, day)
        except ValueError:
            return None
    return None


def parse_date_list(raw):
    dates = []
    for part in str(raw or "").replace(",", "\n").replace(";", "\n").splitlines():
        text = part.strip()
        if not text:
            continue
        parsed = parse_flexible_date(text)
        if not parsed:
            raise ValueError(f"Could not read date: {text}")
        dates.append(parsed)
    return sorted(set(dates))


def format_date_list(values):
    lines = []
    for item in values or []:
        parsed = item if isinstance(item, date) else parse_flexible_date(item)
        if parsed:
            lines.append(f"{parsed.month}/{parsed.day}/{parsed.year}")
    return "\n".join(lines)


def iso_date_list(values):
    out = []
    for item in values or []:
        parsed = item if isinstance(item, date) else parse_flexible_date(item)
        if parsed:
            out.append(parsed.isoformat())
    return out


def date_set(values):
    days = set()
    for item in values or []:
        parsed = item if isinstance(item, date) else parse_flexible_date(item)
        if parsed:
            days.add(parsed)
    return days


def get_program_calendar():
    from .models import PortalProgramCalendar

    row = PortalProgramCalendar.objects.order_by("pk").first()
    if row:
        return row
    return PortalProgramCalendar.objects.create()


def program_calendar_form(calendar=None, month=None, tab=None):
    from calendar import Calendar as MonthCalendar

    from .attendance_calendar import parse_calendar_month, shift_month

    calendar = calendar or get_program_calendar()
    weeks = sync_program_weeks(calendar)
    sync_program_months(calendar)
    fallback = calendar.program_start or timezone.localdate()
    month_start = parse_calendar_month(month, fallback)
    tab_key = "months" if str(tab or "").strip().lower() == "months" else "weeks"
    days_off = date_set(calendar.days_off)
    half_days = date_set(calendar.half_days)
    by_date = {}
    for week in weeks:
        cursor = week.week_start
        while cursor <= week.week_end:
            by_date[cursor] = week
            cursor += timedelta(days=1)
    grid = []
    for week_days in MonthCalendar(firstweekday=0).monthdatescalendar(month_start.year, month_start.month):
        mon_fri = week_days[:5]
        week_obj = None
        for day in mon_fri:
            week_obj = by_date.get(day)
            if week_obj:
                break
        grid.append(
            {
                "cc_label": f"CC WK {week_obj.week_number}" if week_obj else "",
                "week_number": week_obj.week_number if week_obj else None,
                "days": [
                    {
                        "date": day,
                        "iso": day.isoformat(),
                        "day_num": day.day,
                        "in_month": day.month == month_start.month,
                        "off": day in days_off,
                        "half": day in half_days,
                        "cc_label": f"CC WK {by_date[day].week_number}" if day in by_date else "",
                    }
                    for day in week_days
                ],
            }
        )
    week_rows = []
    for week in weeks:
        week_rows.append(
            {
                "id": week.pk,
                "week_start": week.week_start.isoformat(),
                "week_end": week.week_end.isoformat(),
                "week_number": week.week_number,
                "cc_label": f"CC WK {week.week_number}",
                "label": format_week_label(week.week_start, week.week_end),
                "number_overridden": week.number_overridden,
                "span_overridden": week.span_overridden,
                "in_view_month": week.week_start.month == month_start.month
                or week.week_end.month == month_start.month
                or thursday_of_program_week(week.week_start, week.week_end).month == month_start.month,
            }
        )
    return {
        "program_start": calendar.program_start.isoformat() if calendar.program_start else "",
        "days_off": format_date_list(calendar.days_off),
        "half_days": format_date_list(calendar.half_days),
        "weeks": week_rows,
        "months": program_month_rows(calendar),
        "tab": tab_key,
        "grid": grid,
        "month_start": month_start,
        "month_value": month_start.strftime("%Y-%m"),
        "month_label": month_start.strftime("%B %Y"),
        "prev_month": shift_month(month_start, -1).strftime("%Y-%m"),
        "next_month": shift_month(month_start, 1).strftime("%Y-%m"),
        "weekday_headers": ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"),
    }


def save_program_calendar(data):
    calendar = get_program_calendar()
    start_raw = (data.get("program_start") or "").strip()
    calendar.program_start = parse_flexible_date(start_raw) if start_raw else None
    calendar.days_off = iso_date_list(parse_date_list(data.get("days_off")))
    calendar.half_days = iso_date_list(parse_date_list(data.get("half_days")))
    calendar.save()
    sync_program_weeks(calendar)
    sync_program_months(calendar)
    apply_program_calendar_to_profiles()
    return calendar


def apply_program_calendar_to_profiles():
    from .models import PortalAgencyProfile

    for profile in PortalAgencyProfile.objects.all():
        sync_contract_weeks(profile)
    return None


def sync_program_weeks(calendar=None):
    """Rebuild CC week rows from program_start, keeping staff overrides."""
    from .models import PortalProgramWeek

    calendar = calendar or get_program_calendar()
    generated = billable_program_weeks(calendar=calendar)
    existing = {week.week_start: week for week in calendar.weeks.all()}
    keep_ids = []
    used_starts = set()
    for index, (week_start, week_end) in enumerate(generated, start=1):
        row = existing.get(week_start)
        if row is None:
            row = PortalProgramWeek(
                calendar=calendar,
                week_start=week_start,
                week_end=week_end,
                week_number=index,
            )
        else:
            if not row.span_overridden:
                row.week_end = week_end
            if not row.number_overridden:
                row.week_number = index
        row.save()
        keep_ids.append(row.pk)
        used_starts.add(row.week_start)
    for row in calendar.weeks.filter(span_overridden=True):
        if row.pk not in keep_ids:
            keep_ids.append(row.pk)
    calendar.weeks.exclude(pk__in=keep_ids).filter(
        number_overridden=False, span_overridden=False
    ).delete()
    next_number = 1
    for row in calendar.weeks.order_by("week_start", "pk"):
        if row.number_overridden:
            next_number = row.week_number + 1
            continue
        if row.week_number != next_number:
            row.week_number = next_number
            row.save(update_fields=["week_number"])
        next_number += 1
    weeks = list(calendar.weeks.order_by("week_start", "pk"))
    sync_program_months(calendar)
    return weeks


def listed_program_weeks(calendar=None):
    calendar = calendar or get_program_calendar()
    if not calendar.weeks.exists():
        return sync_program_weeks(calendar)
    return list(calendar.weeks.order_by("week_start", "pk"))


def save_program_week_override(data):
    from .models import PortalProgramWeek

    week_id = str(data.get("week_id") or "").strip()
    week = PortalProgramWeek.objects.filter(pk=week_id).select_related("calendar").first()
    if not week:
        raise ValueError("Choose a program week to edit.")
    number_raw = str(data.get("week_number") or "").strip()
    try:
        number = int(number_raw)
    except (TypeError, ValueError):
        raise ValueError("Enter a week number such as 1.")
    if number < 1:
        raise ValueError("Week numbers start at 1.")
    start = parse_flexible_date(data.get("week_start"))
    end = parse_flexible_date(data.get("week_end"))
    if not start or not end:
        raise ValueError("Enter the week start and end dates.")
    if end < start:
        raise ValueError("Week end cannot be before week start.")
    if number != week.week_number:
        week.week_number = number
        week.number_overridden = True
    if start != week.week_start or end != week.week_end:
        clash = (
            PortalProgramWeek.objects.filter(calendar=week.calendar, week_start=start)
            .exclude(pk=week.pk)
            .exists()
        )
        if clash:
            raise ValueError("Another program week already starts on that date.")
        week.week_start = start
        week.week_end = end
        week.span_overridden = True
    week.save()
    sync_program_months(week.calendar)
    return week


def parse_week_number_list(raw):
    numbers = []
    text = str(raw or "").replace(",", " ").replace(";", " ")
    for part in text.split():
        token = part.strip().upper().replace("WK", "").replace("CC", "")
        token = token.replace("#", "").strip()
        if not token:
            continue
        try:
            number = int(token)
        except (TypeError, ValueError):
            raise ValueError(f"Could not read week number: {part}")
        if number < 1:
            raise ValueError("Week numbers start at 1.")
        if number not in numbers:
            numbers.append(number)
    return numbers


def parse_month_key(data):
    raw = str(data.get("month_key") or data.get("month") or "").strip()
    if raw:
        try:
            year_text, month_text = raw.split("-", 1)
            year, month = int(year_text), int(month_text)
        except (TypeError, ValueError):
            raise ValueError("Choose a month to edit.")
    else:
        try:
            year = int(str(data.get("year") or "").strip())
            month = int(str(data.get("month_number") or data.get("month") or "").strip())
        except (TypeError, ValueError):
            raise ValueError("Choose a month to edit.")
    if month < 1 or month > 12:
        raise ValueError("Month must be between 1 and 12.")
    if year < 2000 or year > 2100:
        raise ValueError("Enter a valid year.")
    return year, month


def extend_or_trim_week_numbers(default_numbers, count):
    cleaned = [int(n) for n in default_numbers or [] if n]
    if count <= 0:
        return []
    if count <= len(cleaned):
        return cleaned[:count]
    last = cleaned[-1] if cleaned else 0
    extra = list(range(last + 1, last + 1 + (count - len(cleaned))))
    return cleaned + extra


def _week_stub(week_start, week_end, number, pk=None):
    return type(
        "Week",
        (),
        {
            "week_start": week_start,
            "week_end": week_end,
            "week_number": number,
            "pk": pk,
        },
    )()


def _match_stored_week(stored, week_start, week_end=None, calendar=None):
    for week in stored:
        if week.week_start == week_start or (
            week.week_start <= week_start <= week.week_end
        ):
            return week
    number = cc_week_number_for_span(week_start, week_end, calendar=calendar)
    if number:
        for week in stored:
            if week.week_number == number:
                return week
    return None


def default_month_week_map(calendar=None):
    """Thursday-owned billable weeks, keyed by (year, month)."""
    calendar = calendar or get_program_calendar()
    stored = list(calendar.weeks.order_by("week_start", "pk"))
    groups = {}
    for week_start, week_end in billable_program_weeks(calendar=calendar):
        match = _match_stored_week(stored, week_start, week_end, calendar)
        number = match.week_number if match else cc_week_number_for_span(
            week_start, week_end, calendar=calendar
        )
        thursday = thursday_of_program_week(week_start, week_end)
        key = (thursday.year, thursday.month)
        groups.setdefault(key, []).append(
            _week_stub(week_start, week_end, number, pk=getattr(match, "pk", None))
        )
    return groups


def overridden_month_rows(calendar=None):
    calendar = calendar or get_program_calendar()
    return {
        (row.year, row.month): row
        for row in calendar.months.filter(overridden=True)
    }


def claimed_week_numbers(calendar=None):
    claimed = {}
    for key, row in overridden_month_rows(calendar).items():
        for number in row.week_numbers or []:
            if number:
                claimed[int(number)] = key
    return claimed


def configured_month_keys(calendar=None, on_date=None):
    calendar = calendar or get_program_calendar()
    keys = set(default_month_week_map(calendar))
    for row in calendar.months.all():
        keys.add((row.year, row.month))
    start, end = program_year_range(calendar, on_date=on_date)
    window_start = date(start.year, start.month, 1)
    window_end = date(end.year, end.month, 1)
    return [
        key
        for key in sorted(keys)
        if window_start <= date(key[0], key[1], 1) <= window_end
    ]


def effective_week_numbers_for_month(year, month, calendar=None):
    calendar = calendar or get_program_calendar()
    row = calendar.months.filter(year=year, month=month).first()
    if row and row.overridden:
        return [int(n) for n in (row.week_numbers or []) if n]
    claimed = claimed_week_numbers(calendar)
    numbers = []
    for week in default_month_week_map(calendar).get((year, month), []):
        number = week.week_number
        owner = claimed.get(number)
        if number and owner not in (None, (year, month)):
            continue
        if number and number not in numbers:
            numbers.append(number)
    return numbers


def month_key_for_span(week_start, week_end, calendar=None):
    """Month that bills this week: override first, else that week's Thursday."""
    calendar = calendar or get_program_calendar()
    number = cc_week_number_for_span(week_start, week_end, calendar=calendar)
    if number:
        claimed = claimed_week_numbers(calendar)
        if number in claimed:
            return claimed[number]
        for key in configured_month_keys(calendar):
            row = calendar.months.filter(year=key[0], month=key[1], overridden=True).first()
            if row and number in [int(n) for n in (row.week_numbers or []) if n]:
                return key
    thursday = thursday_of_program_week(week_start, week_end)
    return (thursday.year, thursday.month)


def sync_program_months(calendar=None):
    """Fill month rows from the Thursday rule without wiping overrides."""
    from .models import PortalProgramMonth

    calendar = calendar or get_program_calendar()
    defaults = default_month_week_map(calendar)
    keep_ids = []
    for (year, month), weeks in defaults.items():
        numbers = [week.week_number for week in weeks if week.week_number]
        row, _created = PortalProgramMonth.objects.get_or_create(
            calendar=calendar,
            year=year,
            month=month,
            defaults={"week_numbers": numbers, "overridden": False},
        )
        if not row.overridden and list(row.week_numbers or []) != numbers:
            row.week_numbers = numbers
            row.save(update_fields=["week_numbers"])
        keep_ids.append(row.pk)
    for row in calendar.months.filter(overridden=True):
        if row.pk not in keep_ids:
            keep_ids.append(row.pk)
    calendar.months.exclude(pk__in=keep_ids).filter(overridden=False).delete()
    return list(calendar.months.order_by("year", "month", "pk"))


def save_program_month_override(data):
    from .models import PortalProgramMonth

    calendar = get_program_calendar()
    year, month = parse_month_key(data)
    defaults = default_month_week_map(calendar)
    default_numbers = [
        week.week_number for week in defaults.get((year, month), []) if week.week_number
    ]
    row, _created = PortalProgramMonth.objects.get_or_create(
        calendar=calendar,
        year=year,
        month=month,
        defaults={"week_numbers": default_numbers, "overridden": False},
    )
    reset = str(data.get("reset") or "").strip().lower() in ("1", "on", "true", "yes")
    if reset:
        row.week_numbers = default_numbers
        row.overridden = False
        row.save(update_fields=["week_numbers", "overridden"])
        return row
    numbers = parse_week_number_list(data.get("week_numbers"))
    count_raw = str(data.get("week_count") or "").strip()
    count = None
    if count_raw:
        try:
            count = int(count_raw)
        except (TypeError, ValueError):
            raise ValueError("Enter a week count such as 4 or 5.")
        if count < 0 or count > 8:
            raise ValueError("Enter a week count from 0 to 8.")
    stored = [int(n) for n in (row.week_numbers or []) if n]
    if numbers and numbers != stored and numbers != default_numbers:
        chosen = numbers
    elif count is not None and count != len(stored or default_numbers):
        base = numbers or stored or default_numbers
        chosen = extend_or_trim_week_numbers(base, count)
    elif numbers:
        chosen = numbers
    elif count is not None:
        chosen = extend_or_trim_week_numbers(default_numbers, count)
    else:
        raise ValueError("Enter the week numbers or a week count for this month.")
    row.week_numbers = chosen
    row.overridden = chosen != default_numbers
    row.save(update_fields=["week_numbers", "overridden"])
    return row


def program_month_rows(calendar=None):
    calendar = calendar or get_program_calendar()
    sync_program_months(calendar)
    stored = list(calendar.weeks.order_by("week_start", "pk"))
    by_number = {}
    for week in stored:
        by_number.setdefault(week.week_number, week)
    defaults = default_month_week_map(calendar)
    rows = []
    for year, month in configured_month_keys(calendar):
        default_weeks = defaults.get((year, month), [])
        default_numbers = [week.week_number for week in default_weeks if week.week_number]
        numbers = effective_week_numbers_for_month(year, month, calendar)
        month_date = date(year, month, 1)
        thursdays = []
        labels = []
        for number in numbers:
            week = by_number.get(number)
            if week is None:
                continue
            thursday = thursday_of_program_week(week.week_start, week.week_end)
            thursdays.append(f"{thursday.month}/{thursday.day}/{thursday.year}")
            labels.append(f"CC WK {number} ({format_week_label(week.week_start, week.week_end)})")
        row = calendar.months.filter(year=year, month=month).first()
        rows.append(
            {
                "id": getattr(row, "pk", None),
                "year": year,
                "month": month,
                "month_key": f"{year:04d}-{month:02d}",
                "label": month_date.strftime("%B %Y"),
                "default_week_numbers": default_numbers,
                "default_week_count": len(default_numbers),
                "default_labels": ", ".join(f"CC WK {n}" for n in default_numbers),
                "week_numbers": numbers,
                "week_numbers_display": ", ".join(str(n) for n in numbers),
                "week_count": len(numbers),
                "overridden": bool(row and row.overridden),
                "charge_name": monthly_charge_name(month_date, numbers, kind="tuition"),
                "thursdays": thursdays,
                "thursdays_display": ", ".join(thursdays),
                "week_labels": labels,
                "week_labels_display": " · ".join(labels),
            }
        )
    return rows


def cc_week_label(number):
    if not number:
        return ""
    return f"CC WK {int(number)}"


def program_week_for_date(on_date, calendar=None):
    if not on_date:
        return None
    weeks = listed_program_weeks(calendar)
    for week in weeks:
        if week.week_start <= on_date <= week.week_end:
            return week
    monday = on_date - timedelta(days=on_date.weekday()) if on_date.weekday() < 5 else on_date
    friday = monday + timedelta(days=4)
    for week in weeks:
        if week.week_start <= friday and week.week_end >= monday:
            return week
    return None


def cc_week_number_for_span(week_start, week_end=None, calendar=None):
    weeks = listed_program_weeks(calendar)
    for week in weeks:
        if week.week_start == week_start:
            return week.week_number
        if week_end and week.week_start <= week_start <= week.week_end:
            return week.week_number
        if week_end and week.week_start <= week_end <= week.week_end:
            return week.week_number
    generated = billable_program_weeks(calendar=calendar)
    for index, (start, end) in enumerate(generated, start=1):
        if start == week_start or (start <= week_start <= end):
            return index
    return None


def cc_week_numbers_for_spans(spans, calendar=None):
    numbers = []
    for span in spans or []:
        if hasattr(span, "week_start"):
            week_start, week_end = span.week_start, span.week_end
        else:
            week_start, week_end = span[0], span[1]
        number = cc_week_number_for_span(week_start, week_end, calendar=calendar)
        if number and number not in numbers:
            numbers.append(number)
    return numbers


def format_mdy(day):
    """M/D/YYYY, matching Jakera's charge-description examples."""
    if not day:
        return ""
    return f"{day.month}/{day.day}/{day.year}"


def format_span_paren(week_start, week_end):
    if not week_start or not week_end:
        return ""
    return f"({format_mdy(week_start)} - {format_mdy(week_end)})"


def charge_kind_phrase(cadence, kind="tuition"):
    """Exact posted-charge wording. Plan custom descriptions are never used."""
    key = cadence_key(cadence)
    if key == "monthly":
        cycle = "Monthly Charge"
    elif key == "biweekly":
        cycle = "Bi-Weekly Charge"
    else:
        cycle = "Weekly Charge"
    if kind == "4cs_copay":
        return f"4Cs Copay {cycle}"
    if kind == "4cs_agency":
        return f"4Cs Agency {cycle}"
    return cycle


def weekly_charge_name(number, kind="tuition", cadence="weekly", week_start=None, week_end=None):
    label = cc_week_label(number) or "CC WK"
    phrase = charge_kind_phrase(cadence, kind)
    span = format_span_paren(week_start, week_end)
    if span:
        return f"{label} - {phrase} - for {span}"
    return f"{label} - {phrase}"


def biweekly_charge_name(numbers, kind="tuition", spans=None):
    cleaned = [int(n) for n in numbers or [] if n]
    spans = [span for span in (spans or []) if span and span[0] and span[1]]
    if not cleaned and not spans:
        return ""
    if len(cleaned) == 1 and len(spans) < 2:
        start = spans[0][0] if spans else None
        end = spans[0][1] if spans else None
        return weekly_charge_name(cleaned[0], kind, cadence="biweekly", week_start=start, week_end=end)
    if len(cleaned) >= 2:
        head = f"CC WK {cleaned[0]} & {cleaned[1]}"
    elif cleaned:
        head = cc_week_label(cleaned[0])
    else:
        head = "CC WK"
    phrase = charge_kind_phrase("biweekly", kind)
    if len(spans) >= 2:
        return (
            f"{head} - {phrase} - for {format_span_paren(*spans[0])} and {format_span_paren(*spans[1])}"
        )
    if len(spans) == 1:
        return f"{head} - {phrase} - for {format_span_paren(*spans[0])}"
    return f"{head} - {phrase}"


def monthly_charge_name(month_date, numbers, kind="tuition"):
    month = month_date.strftime("%B") if hasattr(month_date, "strftime") else str(month_date)
    cleaned = [str(int(n)) for n in numbers or [] if n]
    phrase = charge_kind_phrase("monthly", kind)
    if not cleaned:
        return f"{month} - {phrase}"
    return f"{month} - {phrase} - for CC WK {', '.join(cleaned)}"


def automatic_charge_name(cadence, kind="tuition", week_numbers=None, month_date=None, week_spans=None):
    key = cadence_key(cadence)
    numbers = [int(n) for n in week_numbers or [] if n]
    spans = list(week_spans or [])
    if key == "monthly":
        when = month_date or timezone.localdate()
        return monthly_charge_name(when, numbers, kind=kind)
    if key == "biweekly":
        return biweekly_charge_name(numbers, kind=kind, spans=spans)
    if numbers:
        start = spans[0][0] if spans else None
        end = spans[0][1] if spans else None
        return weekly_charge_name(
            numbers[0], kind=kind, cadence=cadence, week_start=start, week_end=end
        )
    return ""


def program_weeks_covering_charge(charge_date, cadence="weekly", calendar=None):
    """Program weeks a private-pay auto charge covers (one, two, or the month)."""
    if not charge_date:
        return []
    key = cadence_key(cadence)
    if key == "monthly":
        return numbered_weeks_for_month(charge_date.year, charge_date.month, calendar=calendar)
    current = program_week_for_date(charge_date, calendar)
    if not current:
        return []
    if key != "biweekly":
        return [current]
    found = []
    taking = False
    for week in listed_program_weeks(calendar):
        if week.week_start == current.week_start:
            taking = True
        if taking:
            found.append(week)
        if len(found) >= 2:
            break
    return found or [current]


def period_week_spans(weeks, calendar=None):
    spans = []
    for week in weeks or []:
        span = parent_span_for_week(week, calendar)
        if span:
            spans.append(span)
        else:
            spans.append((week.week_start, week.week_end))
    return spans


def cc_week_label_for_dates(dates):
    """Side-column CC WK label for a Sunday-Saturday (or any) calendar row."""
    for day in dates or []:
        if not day or getattr(day, "weekday", lambda: 0)() >= 5:
            continue
        week = program_week_for_date(day)
        if week:
            return cc_week_label(week.week_number)
    return ""


def wrap_calendar_weeks(week_rows):
    """Turn list[list[day_dict]] into list[{cc_label, days}] for a Week side column."""
    wrapped = []
    for days in week_rows or []:
        dates = [day.get("date") for day in days]
        wrapped.append({"cc_label": cc_week_label_for_dates(dates), "days": days})
    return wrapped


def numbered_weeks_for_month(year, month, calendar=None):
    """Program weeks billed in this month (configured / Thursday ownership).

    Defaults come from the Thursday of each CC week. A saved month override
    replaces that list so monthly preview and posting are not hardcoded to 5.
    """
    calendar = calendar or get_program_calendar()
    numbers = effective_week_numbers_for_month(year, month, calendar)
    stored = list(calendar.weeks.order_by("week_start", "pk"))
    by_number = {}
    for week in stored:
        by_number.setdefault(week.week_number, week)
    generated = billable_program_weeks(calendar=calendar)
    generated_by_index = {
        index: (week_start, week_end)
        for index, (week_start, week_end) in enumerate(generated, start=1)
    }
    rows = []
    for number in numbers:
        match = by_number.get(number)
        if match:
            rows.append(match)
            continue
        span = generated_by_index.get(number)
        if span:
            rows.append(_week_stub(span[0], span[1], number))
    return rows


def monthly_charge_details(weekly_rate, charge_date, calendar=None):
    """Amount, week count, and CC week numbers for the charge month."""
    weekly = weekly_rate if isinstance(weekly_rate, Decimal) else parse_money(weekly_rate)
    weeks = numbered_weeks_for_month(charge_date.year, charge_date.month, calendar=calendar)
    count = len(weeks)
    numbers = [week.week_number for week in weeks if getattr(week, "week_number", None)]
    amount = (weekly * Decimal(count)).quantize(MONEY)
    return {
        "amount": amount,
        "week_count": count,
        "week_numbers": numbers,
        "weeks": weeks,
        "charge_name": monthly_charge_name(charge_date, numbers, kind="tuition"),
    }


def monday_owned_week_count(year, month, calendar=None):
    """Wrong October count: weeks whose Monday (or clipped start) is in the month.

    9/28/2026–10/2/2026 starts in September, so a Monday-only count drops it
    and October looks like 4 weeks instead of 5.
    """
    weeks = billable_program_weeks(calendar=calendar)
    return len([start for start, _end in weeks if start.year == year and start.month == month])


def parent_week_span(week_start, week_end, calendar=None):
    """Parent-billable dates inside a contract week, or None to skip.

    Weeks that end before program start, or have no remaining school days
    after days off, are skipped. Half days are stored only — they do not
    change the weekly copay amount.
    """
    if not week_start or not week_end:
        return None
    calendar = calendar or get_program_calendar()
    program_start = getattr(calendar, "program_start", None)
    days_off = date_set(getattr(calendar, "days_off", None))
    start = week_start
    if program_start:
        if week_end < program_start:
            return None
        start = max(week_start, program_start)
    cursor = start
    has_school_day = False
    while cursor <= week_end:
        if cursor.weekday() < 5 and cursor not in days_off:
            has_school_day = True
            break
        cursor += timedelta(days=1)
    if not has_school_day:
        return None
    return (start, week_end)


def parent_span_for_week(week, calendar=None):
    calendar = calendar or get_program_calendar()
    span = parent_week_span(week.week_start, week.week_end, calendar)
    if span:
        return span
    if getattr(week, "parent_included", True) and getattr(week, "parent_included_overridden", False):
        return (week.week_start, week.week_end)
    return None


def week_is_parent_billable(week, calendar=None):
    if not getattr(week, "parent_included", True):
        return False
    return parent_span_for_week(week, calendar) is not None


def week_is_agency_billable(week):
    return getattr(week, "agency_included", True)


def school_weeks_in_range(start, end):
    """Return Mon–Fri school weeks clipped to [start, end].

    Weekend-only starts jump to the next Monday. Partial first/last weeks
    are clipped to the contract dates (e.g. Tue–Fri, or Mon–Wed).
    """
    if not start or not end or end < start:
        return []
    if start.weekday() >= 5:
        cursor = start + timedelta(days=(7 - start.weekday()))
    else:
        cursor = start - timedelta(days=start.weekday())

    weeks = []
    while cursor <= end:
        friday = cursor + timedelta(days=4)
        week_start = max(cursor, start)
        week_end = min(friday, end)
        if week_start <= week_end and week_start.weekday() < 5:
            weeks.append((week_start, week_end))
        cursor += timedelta(days=7)
    return weeks


def cadence_key(plan):
    label = (plan or "weekly").strip().lower()
    if "month" in label:
        return "monthly"
    if "bi" in label:
        return "biweekly"
    return "weekly"


def program_year_range(calendar=None, on_date=None):
    """School-year window for monthly plan schedules.

    Uses Settings → Program calendar start when set. Otherwise September 1
    of the school year that contains on_date (July–June). Ends June 30.
    """
    calendar = calendar or get_program_calendar()
    on_date = on_date or timezone.localdate()
    start = getattr(calendar, "program_start", None)
    if not start:
        year = on_date.year if on_date.month >= 7 else on_date.year - 1
        start = date(year, 9, 1)
    if start.month >= 7:
        end = date(start.year + 1, 6, 30)
    else:
        end = date(start.year, 6, 30)
    if on_date > end:
        start = date(end.year, 9, 1)
        end = date(end.year + 1, 6, 30)
    return start, end


def thursday_of_program_week(week_start, week_end=None):
    """Thursday that decides which month a program week is billed in.

    9/28/2026–10/2/2026 has Thursday 10/1, so it is October, not September.
    A week whose Thursday is still in September stays September.
    """
    if week_end is not None and week_end.weekday() == 3:
        return week_end
    monday = week_start - timedelta(days=week_start.weekday())
    return monday + timedelta(days=3)


def friday_of_program_week(week_start, week_end=None):
    """Wrong path: Friday-owned month. Kept to document why Thursday is used.

    4/27/2026–5/1/2026 has Friday 5/1 (May) but Thursday 4/30 (April).
    9/28/2026–10/2/2026 agrees on October either way (Thu 10/1, Fri 10/2).
    """
    if week_end is not None and week_end.weekday() == 4:
        return week_end
    monday = week_start - timedelta(days=week_start.weekday())
    return monday + timedelta(days=4)


def billable_program_weeks(start=None, end=None, calendar=None):
    """Program weeks that have at least one school day after days off.

    week_start is Monday, or the first program day when the range clips a
    partial week. A week with no remaining program days is omitted.
    """
    calendar = calendar or get_program_calendar()
    if start is None or end is None:
        start, end = program_year_range(calendar)
    weeks = []
    for week_start, week_end in school_weeks_in_range(start, end):
        if parent_week_span(week_start, week_end, calendar) is None:
            continue
        weeks.append((week_start, week_end))
    return weeks


def group_program_weeks_by_month(weeks=None, calendar=None):
    """A week belongs to its configured month, else the month of its Thursday."""
    calendar = calendar or get_program_calendar()
    groups = {}
    if weeks is None:
        for year, month in configured_month_keys(calendar):
            for week in numbered_weeks_for_month(year, month, calendar=calendar):
                groups.setdefault((year, month), []).append((week.week_start, week.week_end))
        return groups
    for week_start, week_end in weeks:
        key = month_key_for_span(week_start, week_end, calendar)
        groups.setdefault(key, []).append((week_start, week_end))
    return groups


def friday_owned_week_count(year, month, calendar=None):
    """Wrong path: count weeks by Friday instead of Thursday / month config."""
    weeks = billable_program_weeks(calendar=calendar)
    return len(
        [
            1
            for start, end in weeks
            if friday_of_program_week(start, end).year == year
            and friday_of_program_week(start, end).month == month
        ]
    )


def billable_week_count_for_month(year, month, calendar=None, weeks=None):
    if weeks is None:
        return len(effective_week_numbers_for_month(year, month, calendar))
    groups = group_program_weeks_by_month(weeks=weeks, calendar=calendar)
    return len(groups.get((year, month), []))


def monthly_charge_for_date(weekly_rate, charge_date, calendar=None, weeks=None):
    """Return (amount, week_count) for the month that contains charge_date.

    Weeks are owned by the month of their Thursday, so 9/28/2026–10/2/2026
    counts in October. A month override replaces that default list.
    """
    if weeks is None:
        details = monthly_charge_details(weekly_rate, charge_date, calendar=calendar)
        return details["amount"], details["week_count"]
    weekly = weekly_rate if isinstance(weekly_rate, Decimal) else parse_money(weekly_rate)
    count = billable_week_count_for_month(
        charge_date.year, charge_date.month, calendar=calendar, weeks=weeks
    )
    return (weekly * Decimal(count)).quantize(MONEY), count


def weekly_rate_for_plan(target):
    """Weekly figure used to build monthly charges."""
    rate = getattr(target, "weekly_rate", None)
    if rate is not None:
        return rate
    return getattr(target, "billing_amount", None) or ZERO


def group_weeks_for_cadence(weeks, plan):
    """Group contract weeks into weekly, bi-weekly, or monthly charge periods."""
    rows = list(weeks)
    key = cadence_key(plan)
    if not rows:
        return []
    if key == "monthly":
        buckets = []
        index = {}
        calendar = get_program_calendar()
        for week in rows:
            month_key = month_key_for_span(week.week_start, week.week_end, calendar)
            if month_key not in index:
                index[month_key] = []
                buckets.append(index[month_key])
            index[month_key].append(week)
        return buckets
    if key == "biweekly":
        return [rows[i : i + 2] for i in range(0, len(rows), 2)]
    return [[week] for week in rows]


def period_parent_total(weeks):
    total = ZERO
    for week in weeks:
        total += week.parent_amount or ZERO
    return total.quantize(MONEY)


def period_agency_total(weeks):
    total = ZERO
    for week in weeks:
        total += week.agency_amount or ZERO
    return total.quantize(MONEY)


def _week_row_labels(week_start, week_end, calendar=None, week=None):
    calendar = calendar or get_program_calendar()
    if week is not None:
        span = parent_span_for_week(week, calendar)
    else:
        span = parent_week_span(week_start, week_end, calendar)
    contract_label = format_week_label(week_start, week_end)
    if span:
        parent_label = format_week_label(span[0], span[1])
    else:
        parent_label = contract_label
    number = cc_week_number_for_span(week_start, week_end, calendar=calendar)
    cc_label = cc_week_label(number)
    if cc_label:
        contract_label = f"{cc_label} · {contract_label}"
        parent_label = f"{cc_label} · {parent_label}" if parent_label else contract_label
    return {
        "label": contract_label,
        "parent_label": parent_label,
        "parent_start": span[0].isoformat() if span else "",
        "parent_end": span[1].isoformat() if span else "",
        "parent_billable": span is not None,
        "week_number": number,
        "cc_label": cc_label,
    }


def serialize_week(week):
    labels = _week_row_labels(week.week_start, week.week_end, week=week)
    return {
        "id": week.pk,
        "week_start": week.week_start.isoformat(),
        "week_end": week.week_end.isoformat(),
        "label": labels["label"],
        "parent_label": labels["parent_label"],
        "parent_start": labels["parent_start"],
        "parent_end": labels["parent_end"],
        "agency_amount": f"{week.agency_amount:.2f}",
        "parent_amount": f"{week.parent_amount:.2f}",
        "agency_overridden": week.agency_overridden,
        "parent_overridden": week.parent_overridden,
        "received": week.received,
        "parent_posted": week.parent_posted,
        "parent_included": week.parent_included,
        "agency_included": week.agency_included,
        "parent_billable": labels["parent_billable"],
        "week_number": labels["week_number"],
        "cc_label": labels["cc_label"],
    }


def preview_weeks(start, end, weekly_agency=None, weekly_parent=None):
    weekly_agency = weekly_agency if weekly_agency is not None else ZERO
    weekly_parent = weekly_parent if weekly_parent is not None else ZERO
    calendar = get_program_calendar()
    rows = []
    for week_start, week_end in school_weeks_in_range(start, end):
        labels = _week_row_labels(week_start, week_end, calendar=calendar)
        rows.append(
            {
                "week_start": week_start.isoformat(),
                "week_end": week_end.isoformat(),
                "label": labels["label"],
                "parent_label": labels["parent_label"],
                "parent_start": labels["parent_start"],
                "parent_end": labels["parent_end"],
                "agency_amount": f"{weekly_agency:.2f}",
                "parent_amount": f"{weekly_parent:.2f}",
                "parent_included": labels["parent_billable"],
                "agency_included": True,
                "parent_billable": labels["parent_billable"],
                "week_number": labels["week_number"],
                "cc_label": labels["cc_label"],
            }
        )
    return rows


def _parent_weeks_for_periods(profile, start_from=None):
    calendar = get_program_calendar()
    weeks = []
    for week in profile.contract_weeks.order_by("week_start"):
        if not week_is_parent_billable(week, calendar):
            continue
        span = parent_span_for_week(week, calendar)
        if start_from and not week.parent_posted and span and span[1] < start_from:
            continue
        weeks.append(week)
    return weeks, calendar


def _period_dates(weeks, calendar=None):
    starts = []
    ends = []
    for week in weeks:
        span = parent_span_for_week(week, calendar)
        if span:
            starts.append(span[0])
            ends.append(span[1])
        else:
            starts.append(week.week_start)
            ends.append(week.week_end)
    return min(starts), max(ends)


def parent_charge_periods(profile, plan, start_from=None):
    """Group parent copay weeks. start_from skips unposted weeks that ended earlier.

    Used so bi-weekly can begin on the date staff typed instead of the
    contract start when the child or program starts later. Weeks before
    the program start, fully closed weeks, and unchecked parent weeks
    are left off.
    """
    weeks, calendar = _parent_weeks_for_periods(profile, start_from=start_from)
    periods = []
    for group in group_weeks_for_cadence(weeks, plan):
        periods.append(
            _parent_period_dict(
                group, plan, calendar, posted=all(week.parent_posted for week in group)
            )
        )
    return periods


def _parent_period_dict(group, plan, calendar=None, posted=False):
    start, end = _period_dates(group, calendar)
    numbers = cc_week_numbers_for_spans(group, calendar=calendar)
    spans = period_week_spans(group, calendar)
    month_label = ""
    month_date = None
    if cadence_key(plan) == "monthly" and group:
        year, month = month_key_for_span(group[0].week_start, group[0].week_end, calendar)
        month_date = date(year, month, 1)
        month_label = month_date.strftime("%B %Y")
    label = automatic_charge_name(
        plan,
        kind="4cs_copay",
        week_numbers=numbers,
        month_date=month_date,
        week_spans=spans,
    ) or format_week_label(start, end)
    return {
        "start": start,
        "end": end,
        "label": label,
        "amount": period_parent_total(group),
        "weeks": group,
        "week_count": len(group),
        "week_numbers": numbers,
        "week_spans": spans,
        "month_label": month_label,
        "posted": posted,
    }


def _period_from_remaining_weeks(remaining, calendar=None, cadence="weekly"):
    rebuilt = _parent_period_dict(remaining, cadence, calendar, posted=False)
    amount = ZERO
    for week in remaining:
        amount += week.parent_amount or ZERO
    rebuilt["amount"] = amount.quantize(MONEY)
    return rebuilt


def next_unposted_parent_period(profile, plan):
    calendar = get_program_calendar()
    for period in parent_charge_periods(profile, plan):
        remaining = [week for week in period["weeks"] if not week.parent_posted]
        if remaining == period["weeks"]:
            return period
        if remaining:
            return _period_from_remaining_weeks(remaining, calendar, cadence=plan)
    return None


def most_recent_thursday(on_date):
    """Thursday on or before on_date."""
    return on_date - timedelta(days=(on_date.weekday() - FOUR_CS_WEEKLY_POST_WEEKDAY) % 7)


def week_monday_covered_by_thursday(thursday):
    """Monday of the school week a Thursday copay post covers (the next week)."""
    return thursday + timedelta(days=4)


def next_thursday_on_or_after(on_date):
    return on_date + timedelta(days=(FOUR_CS_WEEKLY_POST_WEEKDAY - on_date.weekday()) % 7)


def next_thursday_after(on_date):
    nxt = next_thursday_on_or_after(on_date)
    if nxt == on_date:
        return on_date + timedelta(days=7)
    return nxt


def parent_period_for_biweekly_from_date(profile, plan, start_from):
    """Next unposted bi-weekly copay window starting from start_from.

    Ignores contract weeks that ended before the entered start/post date so a
    late-starting child is not billed from the authorization range. Also
    skips weeks before program start, fully closed weeks, and unchecked
    parent weeks.
    """
    calendar = get_program_calendar()
    weeks = []
    for week in profile.contract_weeks.order_by("week_start"):
        if week.parent_posted:
            continue
        if not week_is_parent_billable(week, calendar):
            continue
        span = parent_span_for_week(week, calendar)
        if span and span[1] < start_from:
            continue
        weeks.append(week)
    if not weeks:
        return None
    return _period_from_remaining_weeks(weeks[:2], calendar, cadence=plan)


def next_biweekly_charge_date(current):
    if not current:
        return None
    return current + timedelta(days=14)


def parent_period_for_weekly_thursday_post(profile, plan, post_date):
    """Next unposted weekly period that Thursday-for-next-week would charge.

    Does not back-bill older unposted weeks. If the target week is already
    posted or missing, returns the next later unposted week.
    """
    calendar = get_program_calendar()
    target_monday = week_monday_covered_by_thursday(most_recent_thursday(post_date))
    for period in parent_charge_periods(profile, plan):
        remaining = [week for week in period["weeks"] if not week.parent_posted]
        if not remaining:
            continue
        week_monday = remaining[0].week_start - timedelta(days=remaining[0].week_start.weekday())
        if week_monday >= target_monday:
            return _period_from_remaining_weeks(remaining, calendar, cadence=plan)
    return None


def typical_parent_period_amount(profile, plan, start_from=None):
    periods = parent_charge_periods(profile, plan, start_from=start_from)
    if not periods:
        return profile.weekly_copay or ZERO
    for period in periods:
        if period["amount"] > 0:
            return period["amount"]
    return periods[0]["amount"]


@transaction.atomic
def sync_contract_weeks(
    profile,
    posted_weeks=None,
    reset_overrides=False,
):
    """Rebuild week rows for the contract range without wiping staff overrides.

    New weeks (added because dates expanded) default to the weekly rates.
    Existing weeks keep per-week overrides unless reset_overrides is True.
    Weeks that fall outside the new range are removed only when they have
    not been received or posted to the parent ledger.
    """
    from .models import PortalAgencyContractWeek

    start = profile.auth_start
    end = profile.auth_end
    canonical = school_weeks_in_range(start, end)
    keep_starts = {week_start for week_start, _week_end in canonical}
    existing = {week.week_start: week for week in profile.contract_weeks.all()}
    posted_map = {}
    for row in posted_weeks or []:
        week_start = row.get("week_start")
        if week_start:
            posted_map[week_start] = row

    weekly_agency = profile.weekly_agency_rate or ZERO
    weekly_parent = profile.weekly_copay or ZERO
    calendar = get_program_calendar()

    for week_start, week_end in canonical:
        week = existing.get(week_start)
        posted = posted_map.get(week_start)
        default_parent_included = parent_week_span(week_start, week_end, calendar) is not None
        if week is None:
            agency_amount = weekly_agency
            parent_amount = weekly_parent
            agency_overridden = False
            parent_overridden = False
            parent_included = default_parent_included
            agency_included = True
            parent_included_overridden = False
            agency_included_overridden = False
            if posted:
                if "agency_amount" in posted:
                    agency_amount = posted["agency_amount"]
                    agency_overridden = agency_amount != weekly_agency
                if "parent_amount" in posted:
                    parent_amount = posted["parent_amount"]
                    parent_overridden = parent_amount != weekly_parent
                if "parent_included" in posted:
                    parent_included = bool(posted["parent_included"])
                    parent_included_overridden = True
                if "agency_included" in posted:
                    agency_included = bool(posted["agency_included"])
                    agency_included_overridden = True
            PortalAgencyContractWeek.objects.create(
                profile=profile,
                week_start=week_start,
                week_end=week_end,
                agency_amount=agency_amount,
                parent_amount=parent_amount,
                agency_overridden=agency_overridden,
                parent_overridden=parent_overridden,
                parent_included=parent_included,
                agency_included=agency_included,
                parent_included_overridden=parent_included_overridden,
                agency_included_overridden=agency_included_overridden,
            )
            continue

        week.week_end = week_end
        if reset_overrides:
            week.agency_amount = weekly_agency
            week.parent_amount = weekly_parent
            week.agency_overridden = False
            week.parent_overridden = False
            week.parent_included = default_parent_included
            week.agency_included = True
            week.parent_included_overridden = False
            week.agency_included_overridden = False
        else:
            if posted and "agency_amount" in posted:
                week.agency_amount = posted["agency_amount"]
                week.agency_overridden = posted["agency_amount"] != weekly_agency
            elif not week.agency_overridden:
                week.agency_amount = weekly_agency
            if posted and "parent_amount" in posted:
                week.parent_amount = posted["parent_amount"]
                week.parent_overridden = posted["parent_amount"] != weekly_parent
            elif not week.parent_overridden:
                week.parent_amount = weekly_parent
            if posted and "parent_included" in posted:
                week.parent_included = bool(posted["parent_included"])
                week.parent_included_overridden = True
            elif not week.parent_included_overridden:
                week.parent_included = default_parent_included
            if posted and "agency_included" in posted:
                week.agency_included = bool(posted["agency_included"])
                week.agency_included_overridden = True
            elif not week.agency_included_overridden:
                week.agency_included = True
        week.save()

    stale = profile.contract_weeks.exclude(week_start__in=keep_starts)
    stale.filter(received=False, parent_posted=False).delete()
    return list(profile.contract_weeks.order_by("week_start"))


def apply_weekly_rate_defaults(profile, which="both"):
    """Fill non-overridden week amounts from the profile weekly rates."""
    weekly_agency = profile.weekly_agency_rate or ZERO
    weekly_parent = profile.weekly_copay or ZERO
    updated = []
    for week in profile.contract_weeks.all():
        changed = False
        if which in ("agency", "both") and not week.agency_overridden:
            week.agency_amount = weekly_agency
            changed = True
        if which in ("parent", "both") and not week.parent_overridden:
            week.parent_amount = weekly_parent
            changed = True
        if changed:
            week.save()
            updated.append(week)
    return updated


@transaction.atomic
def mark_agency_week_received(week, received=True):
    """Record (or undo) agency receipt on the 4Cs ledger only — never the parent ledger."""
    from .models import PortalAgencyLedgerEntry

    profile = week.profile
    if received and week.received:
        return week
    if not received and not week.received:
        return week

    if received:
        amount = week.agency_amount or ZERO
        if amount > 0:
            number = cc_week_number_for_span(week.week_start, week.week_end)
            received_name = (
                weekly_charge_name(
                    number,
                    kind="4cs_agency",
                    week_start=week.week_start,
                    week_end=week.week_end,
                )
                if number
                else ""
            )
            received_label = received_name or format_week_label(week.week_start, week.week_end)
            PortalAgencyLedgerEntry.objects.create(
                profile=profile,
                date=timezone.localdate(),
                entry_type="payment",
                description=f"Received {received_label}",
                amount=-amount,
                is_manual=True,
            )
            profile.agency_balance = max(ZERO, (profile.agency_balance or ZERO) - amount)
            profile.save(update_fields=["agency_balance"])
        week.received = True
        week.received_at = timezone.now()
        week.save(update_fields=["received", "received_at"])
        return week

    amount = week.agency_amount or ZERO
    if amount > 0:
        PortalAgencyLedgerEntry.objects.create(
            profile=profile,
            date=timezone.localdate(),
            entry_type="charge",
            description=f"Unmarked received {format_week_label(week.week_start, week.week_end)}",
            amount=amount,
            is_manual=True,
        )
        profile.agency_balance = (profile.agency_balance or ZERO) + amount
        profile.save(update_fields=["agency_balance"])
    week.received = False
    week.received_at = None
    week.save(update_fields=["received", "received_at"])
    return week


def refresh_agency_expected_balance(profile):
    """Expected agency balance is unreceived week amounts (not parent copays)."""
    outstanding = ZERO
    for week in profile.contract_weeks.all():
        if not week.received and week_is_agency_billable(week):
            outstanding += week.agency_amount or ZERO
    profile.agency_balance = outstanding.quantize(MONEY)
    profile.save(update_fields=["agency_balance"])
    return profile.agency_balance


def mark_parent_period_posted(weeks, charge_date):
    for week in weeks:
        week.parent_posted = True
        week.parent_posted_on = charge_date
        week.save(update_fields=["parent_posted", "parent_posted_on"])


def apply_week_includes_from_form(profile, data):
    if not hasattr(data, "get") or data.get("four_cs_weeks_posted") != "1":
        return None
    parent_starts = []
    agency_starts = []
    getter = data.getlist if hasattr(data, "getlist") else lambda key: data.get(key) or []
    for raw in getter("parent_week_include"):
        parsed = parse_iso_date(str(raw or "").strip()) or parse_flexible_date(raw)
        if parsed:
            parent_starts.append(parsed)
    for raw in getter("agency_week_include"):
        parsed = parse_iso_date(str(raw or "").strip()) or parse_flexible_date(raw)
        if parsed:
            agency_starts.append(parsed)
    return apply_week_includes(profile, parent_starts, agency_starts)


def apply_week_includes(profile, parent_starts=None, agency_starts=None):
    """Staff picks which contract weeks post for parent copay vs agency."""
    parent_set = set(parent_starts or [])
    agency_set = set(agency_starts or [])
    for week in profile.contract_weeks.all():
        week.parent_included = week.week_start in parent_set
        week.parent_included_overridden = True
        week.agency_included = week.week_start in agency_set
        week.agency_included_overridden = True
        week.save(
            update_fields=[
                "parent_included",
                "parent_included_overridden",
                "agency_included",
                "agency_included_overridden",
            ]
        )
    refresh_agency_expected_balance(profile)
    return list(profile.contract_weeks.order_by("week_start"))
