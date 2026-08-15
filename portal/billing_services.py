import calendar
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.utils import timezone

from .demo_data import prepare_billing_preview
from .models import PortalAgencyProfile, PortalChild, PortalFamily, PortalLedgerEntry
from .parent_services import get_billing_live

WEEKDAYS = (
    (0, "Monday"),
    (1, "Tuesday"),
    (2, "Wednesday"),
    (3, "Thursday"),
    (4, "Friday"),
    (5, "Saturday"),
    (6, "Sunday"),
)
MONTH_DAYS = [(0, "Last day of month")] + [(day, str(day)) for day in range(1, 32)]


def _parse_amount(value):
    try:
        amount = Decimal(str(value).replace(",", "").strip())
    except (InvalidOperation, TypeError):
        raise ValueError("Enter a valid dollar amount.")
    if amount <= 0:
        raise ValueError("Amount must be greater than zero.")
    return amount.quantize(Decimal("0.01"))


def prepare_billing_for_staff(family, permissions):
    billing = get_billing_live(family)
    entries = list(PortalLedgerEntry.objects.filter(family=family).order_by("-date", "-created_at"))
    if entries:
        ledger = []
        for entry in entries:
            if entry.entry_type in ("payment", "discount", "credit"):
                amount = f"{abs(entry.amount):.2f}"
            else:
                amount = f"{entry.amount:.2f}"
            ledger.append(
                {
                    "id": entry.pk,
                    "date": entry.date.isoformat(),
                    "child": entry.child_name,
                    "type": entry.entry_type,
                    "description": entry.description,
                    "amount": amount,
                    "manual": entry.is_manual,
                }
            )
        billing["ledger"] = ledger
    return prepare_billing_preview(billing, permissions)


def get_family_for_billing(family_slug, unit=None):
    qs = PortalFamily.objects.filter(slug=family_slug)
    if unit:
        qs = qs.filter(unit=unit)
    return qs.first()


@transaction.atomic
def post_charge(family, child_name, charge_type, amount, entry_date, description, is_manual=True):
    amount = _parse_amount(amount)
    label = description.strip() or charge_type.replace("_", " ").title()
    PortalLedgerEntry.objects.create(
        family=family,
        child_name=child_name,
        date=entry_date,
        entry_type="charge",
        description=label,
        amount=amount,
        is_manual=is_manual,
    )
    family.balance += amount
    family.save(update_fields=["balance"])


@transaction.atomic
def post_credit(family, child_name, amount, entry_date, reason):
    amount = _parse_amount(amount)
    PortalLedgerEntry.objects.create(
        family=family,
        child_name=child_name,
        date=entry_date,
        entry_type="credit",
        description=reason.strip(),
        amount=-amount,
        is_manual=True,
    )
    family.balance = family.balance - amount
    family.save(update_fields=["balance"])


@transaction.atomic
def post_payment(family, child_name, amount, entry_date, method_label, note=""):
    amount = _parse_amount(amount)
    description = note.strip() or f"In-person payment — {method_label}"
    PortalLedgerEntry.objects.create(
        family=family,
        child_name=child_name,
        date=entry_date,
        entry_type="payment",
        description=description,
        amount=-amount,
        is_manual=True,
    )
    family.balance = family.balance - amount
    family.save(update_fields=["balance"])


@transaction.atomic
def delete_ledger_entry(family, entry_id):
    entry = PortalLedgerEntry.objects.filter(family=family, pk=entry_id).first()
    if not entry:
        raise ValueError("Ledger entry not found.")
    if entry.entry_type == "payment":
        family.balance += abs(entry.amount)
    elif entry.entry_type in ("credit", "discount"):
        family.balance += abs(entry.amount)
    elif entry.entry_type == "charge":
        family.balance = max(Decimal("0"), family.balance - entry.amount)
    else:
        raise ValueError("This entry cannot be deleted.")
    entry.delete()
    family.save(update_fields=["balance"])


def default_entry_date():
    return timezone.localdate()


def _billing_type_matches(family_billing_type, filter_text):
    if not filter_text:
        return True
    return filter_text.lower() in (family_billing_type or "").lower()


def build_bulk_charge_preview(
    unit_slug=None,
    charge_mode="weekly_tuition",
    billing_filter="",
    custom_amount=None,
    custom_description="",
):
    rows = []
    families = PortalFamily.objects.select_related("unit").prefetch_related("children").filter(status="Active")
    if unit_slug:
        families = families.filter(unit__slug=unit_slug)

    if charge_mode == "weekly_tuition":
        for family in families:
            billing_type = family.billing_type or "Private pay"
            lowered = billing_type.lower()
            if "4cs" in lowered or "copay" in lowered:
                continue
            if not _billing_type_matches(billing_type, billing_filter):
                continue
            for child in family.children.filter(is_active=True):
                if not child.billing_amount or child.billing_amount <= 0:
                    continue
                rows.append(
                    {
                        "family_slug": family.slug,
                        "family_name": family.name,
                        "unit": family.unit.name,
                        "child_name": child.name,
                        "amount": child.billing_amount,
                        "amount_display": f"{child.billing_amount:.2f}",
                        "description": f"Weekly tuition — {child.name}",
                        "charge_type": "tuition",
                        "billing_type": billing_type,
                    }
                )
    elif charge_mode == "4cs_copay":
        profiles = PortalAgencyProfile.objects.select_related("child", "family", "family__unit", "unit")
        if unit_slug:
            profiles = profiles.filter(unit__slug=unit_slug)
        for profile in profiles:
            if profile.weekly_copay <= 0:
                continue
            family = profile.family
            if family.status != "Active":
                continue
            child_name = profile.child.name if profile.child else ""
            rows.append(
                {
                    "family_slug": family.slug,
                    "family_name": family.name,
                    "unit": profile.unit.name,
                    "child_name": child_name,
                    "amount": profile.weekly_copay,
                    "amount_display": f"{profile.weekly_copay:.2f}",
                    "description": f"Weekly 4Cs copay — {child_name or 'Child'}",
                    "charge_type": "4cs_copay",
                    "billing_type": family.billing_type or "4Cs copay",
                }
            )
    elif charge_mode == "custom":
        if not custom_amount:
            return []
        amount = _parse_amount(custom_amount)
        description = custom_description.strip() or "Charge"
        for family in families:
            billing_type = family.billing_type or ""
            if not _billing_type_matches(billing_type, billing_filter):
                continue
            rows.append(
                {
                    "family_slug": family.slug,
                    "family_name": family.name,
                    "unit": family.unit.name,
                    "child_name": "",
                    "amount": amount,
                    "amount_display": f"{amount:.2f}",
                    "description": description,
                    "charge_type": "manual",
                    "billing_type": billing_type or "—",
                }
            )
    return rows


@transaction.atomic
def post_bulk_charges(rows, entry_date):
    posted = 0
    for row in rows:
        family = PortalFamily.objects.filter(slug=row["family_slug"]).first()
        if not family:
            continue
        post_charge(
            family,
            row.get("child_name", ""),
            row.get("charge_type", "manual"),
            row["amount"],
            entry_date,
            row.get("description", ""),
        )
        posted += 1
    return posted


def get_org_ledger_live(limit=150, unit_slug=None):
    qs = PortalLedgerEntry.objects.select_related("family", "family__unit").order_by("-date", "-created_at")
    if unit_slug:
        qs = qs.filter(family__unit__slug=unit_slug)
    entries = []
    for entry in qs[:limit]:
        credit_types = ("payment", "credit", "discount")
        entries.append(
            {
                "id": entry.pk,
                "date": entry.date.isoformat(),
                "family_slug": entry.family.slug,
                "family_name": entry.family.name,
                "unit": entry.family.unit.name,
                "child": entry.child_name or "—",
                "type": entry.entry_type,
                "description": entry.description,
                "amount": f"{abs(entry.amount):.2f}",
                "is_credit": entry.entry_type in credit_types,
                "manual": entry.is_manual,
            }
        )
    return entries


def _parse_optional_int(value, minimum, maximum):
    if value in (None, ""):
        return None
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    if number < minimum or number > maximum:
        return None
    return number


def next_weekday_on_or_after(start, weekday):
    days_ahead = (weekday - start.weekday()) % 7
    return start + timedelta(days=days_ahead)


def month_day_in(year, month, month_day):
    last = calendar.monthrange(year, month)[1]
    if month_day == 0:
        return date(year, month, last)
    return date(year, month, min(month_day, last))


def next_month_day_on_or_after(start, month_day):
    candidate = month_day_in(start.year, start.month, month_day)
    if candidate >= start:
        return candidate
    month = start.month + 1
    year = start.year
    if month > 12:
        month = 1
        year += 1
    return month_day_in(year, month, month_day)


def first_plan_charge_date(start, plan, weekday=None, month_day=None):
    start = start or timezone.localdate()
    label = (plan or "").lower()
    if "month" in label:
        return next_month_day_on_or_after(start, month_day if month_day is not None else start.day)
    if weekday is not None:
        return next_weekday_on_or_after(start, weekday)
    return start


def next_plan_charge_date(current, plan, weekday=None, month_day=None):
    if not current:
        return None
    after = current + timedelta(days=1)
    label = (plan or "").lower()
    if "month" in label:
        return next_month_day_on_or_after(after, month_day if month_day is not None else current.day)
    if weekday is not None:
        nxt = next_weekday_on_or_after(after, weekday)
        if "bi" in label:
            return nxt + timedelta(days=7)
        return nxt
    if "bi" in label:
        return current + timedelta(days=14)
    return current + timedelta(days=7)


def plan_repeat_label(child):
    if not getattr(child, "auto_charge", False):
        return "Off"
    plan = (child.billing_plan or "").lower()
    weekday = getattr(child, "charge_weekday", None)
    month_day = getattr(child, "charge_month_day", None)
    next_date = child.next_charge_date.isoformat() if child.next_charge_date else ""
    if "month" in plan:
        if month_day == 0:
            repeat = "Monthly on the last day"
        elif month_day:
            repeat = f"Monthly on the {month_day}"
        else:
            repeat = "Monthly"
    elif weekday is not None and 0 <= weekday <= 6:
        day_name = WEEKDAYS[weekday][1]
        repeat = f"Every other {day_name}" if "bi" in plan else f"Every {day_name}"
    else:
        repeat = child.billing_plan or "Scheduled"
    if next_date:
        return f"{repeat} · next {next_date}"
    return repeat


@transaction.atomic
def update_child_billing_plan(
    family,
    child_name,
    plan,
    amount=None,
    billing_type=None,
    auto_charge=None,
    next_charge_date=None,
    charge_weekday=None,
    charge_month_day=None,
):
    child = family.children.filter(name=child_name, is_active=True).first()
    if not child:
        raise ValueError("Child not found on this family account.")
    child.billing_plan = plan.strip() or child.billing_plan
    if amount not in (None, ""):
        child.billing_amount = _parse_amount(amount)
    if auto_charge is not None:
        child.auto_charge = bool(auto_charge)
        if child.auto_charge and not child.billing_amount:
            raise ValueError("Set a plan amount before turning on automatic charges.")
        if child.auto_charge:
            child.charge_weekday = _parse_optional_int(charge_weekday, 0, 6)
            child.charge_month_day = _parse_optional_int(charge_month_day, 0, 31)
            label = (child.billing_plan or "").lower()
            if "month" in label:
                child.charge_weekday = None
                if child.charge_month_day is None:
                    raise ValueError("Pick the day of the month this plan should repeat.")
            else:
                child.charge_month_day = None
                if child.charge_weekday is None:
                    raise ValueError("Pick the weekday this plan should repeat.")
            child.next_charge_date = first_plan_charge_date(
                next_charge_date,
                child.billing_plan,
                weekday=child.charge_weekday,
                month_day=child.charge_month_day,
            )
        else:
            child.next_charge_date = None
            child.charge_weekday = None
            child.charge_month_day = None
    elif next_charge_date is not None:
        child.next_charge_date = next_charge_date
    child.save(
        update_fields=[
            "billing_plan",
            "billing_amount",
            "auto_charge",
            "next_charge_date",
            "charge_weekday",
            "charge_month_day",
        ]
    )
    if billing_type:
        family.billing_type = billing_type.strip()
        family.save(update_fields=["billing_type"])
    return child


def run_due_plan_charges(today=None):
    """Post due child plan charges and advance each next charge date."""
    today = today or timezone.localdate()
    due = PortalChild.objects.select_related("family").filter(
        is_active=True,
        auto_charge=True,
        next_charge_date__isnull=False,
        next_charge_date__lte=today,
        billing_amount__gt=0,
        family__status="Active",
    )
    posted = []
    for child in due:
        try:
            with transaction.atomic():
                locked = (
                    PortalChild.objects.select_for_update()
                    .select_related("family")
                    .filter(pk=child.pk, auto_charge=True, next_charge_date__lte=today)
                    .first()
                )
                if not locked or not locked.billing_amount:
                    continue
                periods = 0
                while (
                    locked.next_charge_date
                    and locked.next_charge_date <= today
                    and periods < 8
                ):
                    charge_date = locked.next_charge_date
                    if locked.last_auto_charge_date == charge_date:
                        locked.next_charge_date = next_plan_charge_date(
                            charge_date,
                            locked.billing_plan,
                            weekday=locked.charge_weekday,
                            month_day=locked.charge_month_day,
                        )
                        continue
                    post_charge(
                        locked.family,
                        locked.name,
                        "tuition",
                        locked.billing_amount,
                        charge_date,
                        f"{locked.billing_plan or 'Plan'} tuition — {locked.name}",
                        is_manual=False,
                    )
                    locked.last_auto_charge_date = charge_date
                    locked.next_charge_date = next_plan_charge_date(
                        charge_date,
                        locked.billing_plan,
                        weekday=locked.charge_weekday,
                        month_day=locked.charge_month_day,
                    )
                    posted.append(locked)
                    periods += 1
                locked.save(update_fields=["last_auto_charge_date", "next_charge_date"])
        except Exception:
            continue
    return posted


def get_scheduled_plan_charges(limit=50):
    children = (
        PortalChild.objects.select_related("family", "family__unit")
        .filter(is_active=True, auto_charge=True, next_charge_date__isnull=False)
        .order_by("next_charge_date", "family__name", "name")[:limit]
    )
    rows = []
    for child in children:
        rows.append(
            {
                "family_slug": child.family.slug,
                "family_name": child.family.name,
                "unit": child.family.unit.name if child.family.unit_id else "",
                "child_name": child.name,
                "plan": child.billing_plan,
                "repeat": plan_repeat_label(child),
                "amount": f"{child.billing_amount:.2f}" if child.billing_amount is not None else "—",
                "next_charge_date": child.next_charge_date.isoformat() if child.next_charge_date else "",
            }
        )
    return rows


def get_refundable_payments(family):
    from .models import PortalPayment

    payments = PortalPayment.objects.filter(family=family, status=PortalPayment.STATUS_PAID).order_by("-paid_at")
    rows = []
    for payment in payments:
        remaining = (payment.amount or Decimal("0")) - (payment.refunded_amount or Decimal("0"))
        if remaining <= 0:
            continue
        rows.append(
            {
                "id": payment.pk,
                "receipt_no": payment.receipt_no,
                "date": timezone.localtime(payment.paid_at).strftime("%b %d, %Y") if payment.paid_at else "",
                "amount": f"{payment.amount:.2f}",
                "charged": f"{(payment.total_charged or payment.amount):.2f}",
                "refunded": f"{(payment.refunded_amount or Decimal('0')):.2f}",
                "remaining": f"{remaining:.2f}",
                "method": payment.method_label or "Card",
                "can_refund_card": bool(payment.stripe_session_id or payment.stripe_payment_intent_id),
            }
        )
    return rows


@transaction.atomic
def refund_family_payment(family, payment_id, amount, reason=""):
    from .models import PortalPayment
    from .stripe_services import refund_stripe_payment

    payment = PortalPayment.objects.select_related("family").filter(pk=payment_id, family=family).first()
    if not payment:
        raise ValueError("Payment not found on this family account.")
    amount = _parse_amount(amount)
    remaining = (payment.amount or Decimal("0")) - (payment.refunded_amount or Decimal("0"))
    if amount > remaining:
        raise ValueError(f"Refund cannot exceed the remaining ${remaining:.2f}.")
    if payment.stripe_session_id or payment.stripe_payment_intent_id:
        refund_stripe_payment(payment, amount)
    payment.refunded_amount = (payment.refunded_amount or Decimal("0")) + amount
    payment.save(update_fields=["refunded_amount"])
    family.balance = family.balance + amount
    family.save(update_fields=["balance"])
    note = reason.strip() or f"Refund of {payment.receipt_no or 'card payment'}"
    PortalLedgerEntry.objects.create(
        family=family,
        child_name="",
        date=timezone.localdate(),
        entry_type="refund",
        description=note,
        amount=amount,
        is_manual=False,
    )
    return payment
