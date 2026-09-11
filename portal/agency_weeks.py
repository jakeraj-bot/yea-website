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


def program_calendar_form(calendar=None):
    calendar = calendar or get_program_calendar()
    return {
        "program_start": calendar.program_start.isoformat() if calendar.program_start else "",
        "days_off": format_date_list(calendar.days_off),
        "half_days": format_date_list(calendar.half_days),
    }


def save_program_calendar(data):
    calendar = get_program_calendar()
    start_raw = (data.get("program_start") or "").strip()
    calendar.program_start = parse_flexible_date(start_raw) if start_raw else None
    calendar.days_off = iso_date_list(parse_date_list(data.get("days_off")))
    calendar.half_days = iso_date_list(parse_date_list(data.get("half_days")))
    calendar.save()
    apply_program_calendar_to_profiles()
    return calendar


def apply_program_calendar_to_profiles():
    from .models import PortalAgencyProfile

    for profile in PortalAgencyProfile.objects.all():
        sync_contract_weeks(profile)
    return None


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


def group_weeks_for_cadence(weeks, plan):
    """Group contract weeks into weekly, bi-weekly, or monthly charge periods."""
    rows = list(weeks)
    key = cadence_key(plan)
    if not rows:
        return []
    if key == "monthly":
        groups = []
        bucket = []
        current = None
        for week in rows:
            month_key = (week.week_start.year, week.week_start.month)
            if current is None:
                current = month_key
            if month_key != current:
                groups.append(bucket)
                bucket = [week]
                current = month_key
            else:
                bucket.append(week)
        if bucket:
            groups.append(bucket)
        return groups
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
    return {
        "label": contract_label,
        "parent_label": parent_label,
        "parent_start": span[0].isoformat() if span else "",
        "parent_end": span[1].isoformat() if span else "",
        "parent_billable": span is not None,
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
        start, end = _period_dates(group, calendar)
        periods.append(
            {
                "start": start,
                "end": end,
                "label": format_week_label(start, end),
                "amount": period_parent_total(group),
                "weeks": group,
                "posted": all(week.parent_posted for week in group),
            }
        )
    return periods


def _period_from_remaining_weeks(remaining, calendar=None):
    amount = ZERO
    for week in remaining:
        amount += week.parent_amount or ZERO
    start, end = _period_dates(remaining, calendar)
    return {
        "start": start,
        "end": end,
        "label": format_week_label(start, end),
        "amount": amount.quantize(MONEY),
        "weeks": remaining,
        "posted": False,
    }


def next_unposted_parent_period(profile, plan):
    calendar = get_program_calendar()
    for period in parent_charge_periods(profile, plan):
        remaining = [week for week in period["weeks"] if not week.parent_posted]
        if remaining:
            return _period_from_remaining_weeks(remaining, calendar)
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
    return _period_from_remaining_weeks(weeks[:2], calendar)


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
            return _period_from_remaining_weeks(remaining, calendar)
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
            PortalAgencyLedgerEntry.objects.create(
                profile=profile,
                date=timezone.localdate(),
                entry_type="payment",
                description=f"Received {format_week_label(week.week_start, week.week_end)}",
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
