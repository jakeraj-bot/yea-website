"""School-week contract math for 4Cs / agency billing."""

from datetime import timedelta
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.utils import timezone


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


def serialize_week(week):
    return {
        "id": week.pk,
        "week_start": week.week_start.isoformat(),
        "week_end": week.week_end.isoformat(),
        "label": format_week_label(week.week_start, week.week_end),
        "agency_amount": f"{week.agency_amount:.2f}",
        "parent_amount": f"{week.parent_amount:.2f}",
        "agency_overridden": week.agency_overridden,
        "parent_overridden": week.parent_overridden,
        "received": week.received,
        "parent_posted": week.parent_posted,
    }


def preview_weeks(start, end, weekly_agency=None, weekly_parent=None):
    weekly_agency = weekly_agency if weekly_agency is not None else ZERO
    weekly_parent = weekly_parent if weekly_parent is not None else ZERO
    rows = []
    for week_start, week_end in school_weeks_in_range(start, end):
        rows.append(
            {
                "week_start": week_start.isoformat(),
                "week_end": week_end.isoformat(),
                "label": format_week_label(week_start, week_end),
                "agency_amount": f"{weekly_agency:.2f}",
                "parent_amount": f"{weekly_parent:.2f}",
            }
        )
    return rows


def parent_charge_periods(profile, plan, start_from=None):
    """Group parent copay weeks. start_from skips unposted weeks that ended earlier.

    Used so bi-weekly can begin on the date staff typed instead of the
    contract start when the child or program starts later.
    """
    weeks = list(profile.contract_weeks.order_by("week_start"))
    if start_from:
        weeks = [week for week in weeks if week.parent_posted or week.week_end >= start_from]
    periods = []
    for group in group_weeks_for_cadence(weeks, plan):
        start = group[0].week_start
        end = group[-1].week_end
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


def _period_from_remaining_weeks(remaining):
    amount = ZERO
    for week in remaining:
        amount += week.parent_amount or ZERO
    return {
        "start": remaining[0].week_start,
        "end": remaining[-1].week_end,
        "label": format_week_label(remaining[0].week_start, remaining[-1].week_end),
        "amount": amount.quantize(MONEY),
        "weeks": remaining,
        "posted": False,
    }


def next_unposted_parent_period(profile, plan):
    for period in parent_charge_periods(profile, plan):
        remaining = [week for week in period["weeks"] if not week.parent_posted]
        if remaining:
            return _period_from_remaining_weeks(remaining)
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
    late-starting child is not billed from the authorization range.
    """
    weeks = [
        week
        for week in profile.contract_weeks.order_by("week_start")
        if not week.parent_posted and week.week_end >= start_from
    ]
    if not weeks:
        return None
    return _period_from_remaining_weeks(weeks[:2])


def next_biweekly_charge_date(current):
    if not current:
        return None
    return current + timedelta(days=14)


def parent_period_for_weekly_thursday_post(profile, plan, post_date):
    """Next unposted weekly period that Thursday-for-next-week would charge.

    Does not back-bill older unposted weeks. If the target week is already
    posted or missing, returns the next later unposted week.
    """
    target_monday = week_monday_covered_by_thursday(most_recent_thursday(post_date))
    for period in parent_charge_periods(profile, plan):
        remaining = [week for week in period["weeks"] if not week.parent_posted]
        if not remaining:
            continue
        week_monday = remaining[0].week_start - timedelta(days=remaining[0].week_start.weekday())
        if week_monday >= target_monday:
            return _period_from_remaining_weeks(remaining)
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

    for week_start, week_end in canonical:
        week = existing.get(week_start)
        posted = posted_map.get(week_start)
        if week is None:
            agency_amount = weekly_agency
            parent_amount = weekly_parent
            agency_overridden = False
            parent_overridden = False
            if posted:
                if "agency_amount" in posted:
                    agency_amount = posted["agency_amount"]
                    agency_overridden = agency_amount != weekly_agency
                if "parent_amount" in posted:
                    parent_amount = posted["parent_amount"]
                    parent_overridden = parent_amount != weekly_parent
            PortalAgencyContractWeek.objects.create(
                profile=profile,
                week_start=week_start,
                week_end=week_end,
                agency_amount=agency_amount,
                parent_amount=parent_amount,
                agency_overridden=agency_overridden,
                parent_overridden=parent_overridden,
            )
            continue

        week.week_end = week_end
        if reset_overrides:
            week.agency_amount = weekly_agency
            week.parent_amount = weekly_parent
            week.agency_overridden = False
            week.parent_overridden = False
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
        if not week.received:
            outstanding += week.agency_amount or ZERO
    profile.agency_balance = outstanding.quantize(MONEY)
    profile.save(update_fields=["agency_balance"])
    return profile.agency_balance


def mark_parent_period_posted(weeks, charge_date):
    for week in weeks:
        week.parent_posted = True
        week.parent_posted_on = charge_date
        week.save(update_fields=["parent_posted", "parent_posted_on"])
