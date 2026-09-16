import calendar
from datetime import date, datetime, time, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from django.db import transaction
from django.utils import timezone

from .demo_data import prepare_billing_preview
from .payment_refs import attach_ledger_reference, method_label_for_reference
from .models import (
    PortalAgencyProfile,
    PortalChild,
    PortalChildBillingPlan,
    PortalFamily,
    PortalLedgerEntry,
    PortalPayment,
    PortalScholarshipAssignment,
    PortalScholarshipFund,
)

STAFF_PAYMENT_METHOD_LABELS = {
    "card": "Card (staff entry)",
    "cash": "Cash",
    "check": "Check",
    "money_order": "Money order",
}


def agency_profile_for(child):
    if not child:
        return None
    try:
        return child.agency_profile
    except PortalAgencyProfile.DoesNotExist:
        return None


def child_uses_4cs_copay_plan(child):
    profile = agency_profile_for(child)
    if not profile:
        return False
    billing_type = (child.family.billing_type or "").lower()
    plan = (child.billing_plan or "").lower()
    return "4cs" in billing_type or "copay" in plan or "4cs" in plan


def billing_kind_from_type(billing_type):
    label = (billing_type or "").strip().lower()
    if "4cs" in label or "copay" in label:
        return "4cs"
    if "scholar" in label:
        return "scholarship"
    if "private" in label:
        return "private"
    return ""


def plan_uses_4cs_copay(child, plan=None):
    if not agency_profile_for(child):
        return False
    if plan is not None:
        kind = (plan.billing_kind or "").lower()
        cadence = (plan.billing_plan or "").lower()
        if kind == "4cs" or "copay" in cadence or "4cs" in cadence:
            return True
        if kind in ("private", "scholarship"):
            return False
        if getattr(plan, "sort_order", 1) != 1:
            return False
    return child_uses_4cs_copay_plan(child)


def primary_billing_plan(child):
    if not child or not child.pk:
        return None
    return child.billing_plans.filter(sort_order=1).first() or child.billing_plans.order_by("sort_order", "pk").first()


def next_plan_sort_order(child):
    last = child.billing_plans.order_by("-sort_order").first()
    return (last.sort_order + 1) if last else 1


def child_has_saved_plan(child):
    if child.billing_plans.exists():
        return True
    plan = (child.billing_plan or "").strip().lower()
    return bool(
        child.billing_amount is not None
        or child.auto_charge
        or child.next_charge_date
        or child.charge_weekday is not None
        or child.charge_month_day is not None
        or (plan and plan != "weekly")
    )


def ledger_charge_description(child, cadence, kind="tuition", period_label=None, description=""):
    note = (description or "").strip()
    if kind == "4cs_copay":
        base = f"{cadence or 'Copay'} — {child.name}"
        if period_label:
            base = f"{base} ({period_label})"
    else:
        base = f"{cadence or 'Plan'} tuition — {child.name}"
    if note:
        return f"{note} — {base}"
    return base


def plan_description_for(child, plan=None):
    if plan is not None:
        return (plan.description or "").strip()
    primary = primary_billing_plan(child)
    return (primary.description or "").strip() if primary else ""


def serialize_billing_plan(plan, child=None):
    child = child or plan.child
    kind = (plan.billing_kind or "").lower()
    if kind == "4cs":
        billing_type = "4Cs"
    elif kind == "scholarship":
        billing_type = "Scholarship"
    elif kind == "private":
        billing_type = "Private pay"
    else:
        billing_type = child.family.billing_type or "Private pay"
    return {
        "id": plan.pk,
        "description": plan.description or "",
        "plan": plan.billing_plan or "Weekly",
        "amount": f"{plan.billing_amount:.2f}" if plan.billing_amount is not None else "",
        "amount_display": f"{plan.billing_amount:.2f}" if plan.billing_amount is not None else "—",
        "auto_charge": plan.auto_charge,
        "next_charge_date": plan.next_charge_date.isoformat() if plan.next_charge_date else "",
        "charge_weekday": "" if plan.charge_weekday is None else plan.charge_weekday,
        "charge_month_day": "" if plan.charge_month_day is None else plan.charge_month_day,
        "auto_charge_label": plan_repeat_label(plan),
        "billing_type": billing_type,
        "is_primary": plan.sort_order == 1,
    }


def serialize_child_primary_plan(child, extra=None):
    extra = extra or {}
    row = {
        "id": extra.get("id", ""),
        "description": extra.get("description", ""),
        "plan": extra.get("plan") or child.billing_plan or "Weekly",
        "amount": extra.get("amount") if extra.get("amount") not in (None, "—") else (
            f"{child.billing_amount:.2f}" if child.billing_amount is not None else ""
        ),
        "amount_display": extra.get("amount") or (
            f"{child.billing_amount:.2f}" if child.billing_amount is not None else "—"
        ),
        "auto_charge": extra.get("auto_charge", child.auto_charge),
        "next_charge_date": extra.get("next_charge_date")
        or (child.next_charge_date.isoformat() if child.next_charge_date else ""),
        "charge_weekday": extra.get("charge_weekday", "" if child.charge_weekday is None else child.charge_weekday),
        "charge_month_day": extra.get("charge_month_day", "" if child.charge_month_day is None else child.charge_month_day),
        "auto_charge_label": extra.get("auto_charge_label") or plan_repeat_label(child),
        "billing_type": extra.get("type") or child.family.billing_type or "Private pay",
        "is_primary": True,
    }
    return row


def sync_plan_from_child(child, plan=None, description=None, billing_kind=None):
    plan = plan or primary_billing_plan(child)
    fields = {
        "billing_plan": child.billing_plan or "Weekly",
        "billing_amount": child.billing_amount,
        "auto_charge": child.auto_charge,
        "next_charge_date": child.next_charge_date,
        "last_auto_charge_date": child.last_auto_charge_date,
        "charge_weekday": child.charge_weekday,
        "charge_month_day": child.charge_month_day,
        "sort_order": 1,
    }
    if description is not None:
        fields["description"] = (description or "").strip()
    if billing_kind is not None:
        fields["billing_kind"] = billing_kind
    if plan:
        for name, value in fields.items():
            setattr(plan, name, value)
        plan.save()
        return plan
    fields.setdefault("description", "")
    fields.setdefault("billing_kind", billing_kind_from_type(child.family.billing_type))
    return PortalChildBillingPlan.objects.create(child=child, **fields)


def sync_child_from_plan(child, plan):
    child.billing_plan = plan.billing_plan or child.billing_plan
    child.billing_amount = plan.billing_amount
    child.auto_charge = plan.auto_charge
    child.next_charge_date = plan.next_charge_date
    child.last_auto_charge_date = plan.last_auto_charge_date
    child.charge_weekday = plan.charge_weekday
    child.charge_month_day = plan.charge_month_day
    child.save(
        update_fields=[
            "billing_plan",
            "billing_amount",
            "auto_charge",
            "next_charge_date",
            "last_auto_charge_date",
            "charge_weekday",
            "charge_month_day",
        ]
    )
    return child


def ensure_primary_billing_plan(child):
    plan = primary_billing_plan(child)
    if plan:
        return plan
    return sync_plan_from_child(child)


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


def _parse_amount(value, allow_zero=False):
    try:
        amount = Decimal(str(value).replace(",", "").strip())
    except (InvalidOperation, TypeError):
        raise ValueError("Enter a valid dollar amount.")
    if amount < 0 or (amount == 0 and not allow_zero):
        raise ValueError("Amount must be greater than zero.")
    return amount.quantize(Decimal("0.01"))


def prepare_billing_for_staff(family, permissions, unit=None):
    billing = get_billing_live(family)
    entries = list(PortalLedgerEntry.objects.filter(family=family).order_by("-date", "-created_at"))
    if entries:
        if unit:
            from .unit_visibility import filter_ledger_entries_for_unit

            entries = filter_ledger_entries_for_unit(entries, family, unit)
        from .processing_fees import backfill_stripe_fee_totals, ledger_paid_totals

        payments = list(family.payments.all())
        backfill_stripe_fee_totals(payments)
        ledger = []
        for entry in entries:
            paid, fee, applied = ledger_paid_totals(entry)
            if entry.entry_type in ("payment", "discount", "credit"):
                amount = f"{paid:.2f}" if entry.entry_type == "payment" else f"{applied:.2f}"
            else:
                amount = f"{entry.amount:.2f}"
            row = {
                "id": entry.pk,
                "date": entry.date.isoformat(),
                "child": entry.child_name,
                "type": entry.entry_type,
                "description": entry.description,
                "amount": amount,
                "fee": f"{fee:.2f}" if entry.entry_type == "payment" and fee else "",
                "applied": f"{applied:.2f}",
                "manual": entry.is_manual,
                "editable": entry.entry_type in ("charge", "payment"),
            }
            if entry.entry_type == "payment":
                attach_ledger_reference(
                    row,
                    entry.description,
                    entry.reference_number,
                    method_label_for_reference(payments, entry.reference_number),
                )
            ledger.append(row)
        billing["ledger"] = ledger
    if unit:
        from .unit_visibility import filter_billing_dict_for_unit

        billing = filter_billing_dict_for_unit(billing, family, unit)
    return prepare_billing_preview(billing, permissions)


def get_family_for_billing(family_slug, unit=None, family_id=None):
    from .member_admin import resolve_family

    return resolve_family(family_slug=family_slug, family_id=family_id, unit=unit)


@transaction.atomic
def post_charge(family, child_name, charge_type, amount, entry_date, description, is_manual=True, notify=True):
    amount = _parse_amount(amount)
    label = description.strip() or charge_type.replace("_", " ").title()
    entry = PortalLedgerEntry.objects.create(
        family=family,
        child_name=child_name,
        date=entry_date,
        entry_type="charge",
        description=label,
        amount=amount,
        is_manual=is_manual,
    )
    from .family_list import sync_family_balance_from_ledger

    sync_family_balance_from_ledger(family)
    if notify:
        from .email_templates import notify_charge_posted

        notify_charge_posted(family, entry)
    return entry


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
    from .family_list import sync_family_balance_from_ledger

    sync_family_balance_from_ledger(family)


@transaction.atomic
def post_discount(family, child_name, amount, entry_date, description, is_manual=False):
    amount = _parse_amount(amount)
    PortalLedgerEntry.objects.create(
        family=family,
        child_name=child_name,
        date=entry_date,
        entry_type="discount",
        description=description.strip() or "Scholarship discount",
        amount=-amount,
        is_manual=is_manual,
    )
    from .family_list import sync_family_balance_from_ledger

    sync_family_balance_from_ledger(family)


def active_scholarship_for_child(child, on_date=None):
    on_date = on_date or timezone.localdate()
    assignments = child.scholarships.select_related("fund").all()
    for row in assignments:
        if (row.status or "").lower() != "active":
            continue
        if row.start_date and row.start_date > on_date:
            continue
        if row.end_date and row.end_date < on_date:
            continue
        return row
    return None


def parent_copay_after_scholarship(scholarship, copay_amount):
    """Return (family_pays, discount) for a 4Cs parent copay period.

    The scholarship ratio (family portion / amount before scholarship) scales
    to this period's copay. Agency week amounts are never changed here.
    """
    copay = copay_amount or Decimal("0")
    if copay <= 0 or not scholarship or not scholarship.full_rate:
        return copay, Decimal("0")
    full = scholarship.full_rate
    parent = scholarship.parent_amount or Decimal("0")
    if full <= 0 or parent >= full:
        return copay, Decimal("0")
    family_pays = (copay * parent / full).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if family_pays < 0:
        family_pays = Decimal("0")
    if family_pays > copay:
        family_pays = copay
    return family_pays, copay - family_pays


def _apply_plan_scholarship(
    child,
    scholarship_fund_id=None,
    scholarship_full_rate=None,
    scholarship_parent_amount=None,
    fallback_full_rate=None,
    full_rate_error="Enter the plan rate before the scholarship.",
):
    """Attach the per-child scholarship to a plan. Empty fund means no change."""
    if scholarship_fund_id in (None, ""):
        return None
    full_rate = scholarship_full_rate if scholarship_full_rate not in (None, "") else fallback_full_rate
    if scholarship_parent_amount in (None, ""):
        raise ValueError("Enter how much the family pays after the scholarship.")
    if full_rate in (None, ""):
        raise ValueError(full_rate_error)
    return apply_scholarship_to_child_plan(
        child,
        scholarship_fund_id,
        full_rate,
        scholarship_parent_amount,
        start_date=timezone.localdate(),
    )


def _apply_four_cs_plan_scholarship(
    child,
    scholarship_fund_id=None,
    scholarship_full_rate=None,
    scholarship_parent_amount=None,
    fallback_full_rate=None,
):
    """Attach the existing per-child scholarship to a 4Cs plan (copay only)."""
    return _apply_plan_scholarship(
        child,
        scholarship_fund_id=scholarship_fund_id,
        scholarship_full_rate=scholarship_full_rate,
        scholarship_parent_amount=scholarship_parent_amount,
        fallback_full_rate=fallback_full_rate,
        full_rate_error="Enter the parent copay before the scholarship.",
    )


def apply_scholarship_to_child_plan(child, fund_id, full_rate, parent_amount, start_date=None):
    fund = PortalScholarshipFund.objects.filter(pk=fund_id, is_active=True).first()
    if not fund:
        raise ValueError("Select a scholarship type. Add it first on the Scholarships page.")
    full = _parse_amount(full_rate)
    parent = _parse_amount(parent_amount, allow_zero=True)
    if parent > full:
        raise ValueError("Family portion cannot be more than the amount before the scholarship.")
    assignment = (
        child.scholarships.filter(status="Active").select_related("fund").first()
        or child.scholarships.filter(fund=fund).first()
    )
    if assignment:
        assignment.fund = fund
        assignment.full_rate = full
        assignment.parent_amount = parent
        assignment.status = "Active"
        if start_date:
            assignment.start_date = start_date
        assignment.save()
    else:
        assignment = PortalScholarshipAssignment.objects.create(
            child=child,
            fund=fund,
            full_rate=full,
            parent_amount=parent,
            start_date=start_date,
            status="Active",
        )
    return assignment


def staff_payment_method_label(method):
    key = (method or "").strip()
    if key in STAFF_PAYMENT_METHOD_LABELS:
        return STAFF_PAYMENT_METHOD_LABELS[key]
    return key or "Cash"


def staff_payment_note(method, note="", check_number="", money_order_number=""):
    """Return the human ledger note and the Check / money order number.

    The number is stored on ``reference_number`` and shown beside the payment.
    It is not written into the description.
    """
    note = (note or "").strip()
    key = (method or "").strip().lower().replace(" ", "_")
    if key == "check":
        return note, (check_number or money_order_number or "").strip()
    if key == "money_order":
        number = (money_order_number or check_number or "").strip()
        if not number:
            raise ValueError("Enter the money order number.")
        return note, number
    return note, ""


def datetime_for_entry_date(entry_date):
    """Aware local noon on ``entry_date`` so receipts and reports keep that calendar day."""
    if entry_date is None:
        return timezone.now()
    return timezone.make_aware(datetime.combine(entry_date, time(12, 0)))


def payment_effective_date(payment):
    """Calendar date this payment belongs on (local date of paid_at)."""
    when = getattr(payment, "paid_at", None) or getattr(payment, "created_at", None)
    if not when:
        return None
    return timezone.localtime(when).date()


@transaction.atomic
def post_payment(family, child_name, amount, entry_date, method_label, note="", reference_number=""):
    amount = _parse_amount(amount)
    if entry_date is None:
        entry_date = default_entry_date()
    description = note.strip() or f"In-person payment — {method_label}"
    reference = (reference_number or "").strip()
    PortalLedgerEntry.objects.create(
        family=family,
        child_name=child_name,
        date=entry_date,
        entry_type="payment",
        description=description,
        amount=-amount,
        is_manual=True,
        reference_number=reference,
    )
    from .family_list import sync_family_balance_from_ledger

    sync_family_balance_from_ledger(family)
    _record_in_person_receipt(
        family,
        amount,
        method_label,
        description,
        reference_number=reference,
        child_name=child_name,
        paid_at=datetime_for_entry_date(entry_date),
    )


def _next_in_person_receipt_no():
    today = timezone.localdate().strftime("%y%m%d")
    prefix = f"RCPT-{today}"
    count = PortalPayment.objects.filter(receipt_no__startswith=prefix).count() + 1
    return f"{prefix}-{count:03d}"


def _record_in_person_receipt(
    family, amount, method_label, description, reference_number="", child_name="", paid_at=None
):
    from .payment_refs import clean_in_person_method_label

    reference = (reference_number or "").strip()
    receipt_method = clean_in_person_method_label(method_label) or method_label
    if not receipt_method and description:
        receipt_method = description
    PortalPayment.objects.create(
        family=family,
        receipt_no=_next_in_person_receipt_no(),
        amount=amount,
        total_charged=amount,
        method_label=receipt_method,
        reference_number=reference,
        payment_kind="balance",
        dropin_child=child_name or "",
        status=PortalPayment.STATUS_PAID,
        paid_at=paid_at or timezone.now(),
        stripe_bank_status="not_stripe",
    )


class _DeletedCharge:
    def __init__(self, entry):
        self.child_name = entry.child_name
        self.description = entry.description
        self.date = entry.date
        self.amount = Decimal("0.00")


@transaction.atomic
def update_ledger_description(family, entry_id, description):
    entry = PortalLedgerEntry.objects.filter(family=family, pk=entry_id).first()
    if not entry:
        raise ValueError("Ledger entry not found.")
    if entry.entry_type not in ("charge", "payment"):
        raise ValueError("Only charge and payment descriptions can be edited.")
    label = (description or "").strip()
    if not label:
        raise ValueError("Enter a description.")
    if len(label) > 255:
        raise ValueError("Description is too long.")
    entry.description = label
    entry.save(update_fields=["description"])
    return entry


@transaction.atomic
def update_ledger_amount(family, entry_id, amount, notify=True):
    entry = PortalLedgerEntry.objects.filter(family=family, pk=entry_id).first()
    if not entry:
        raise ValueError("Ledger entry not found.")
    if entry.entry_type != "charge":
        raise ValueError("Only charge amounts can be edited.")
    previous = entry.amount
    new_amount = _parse_amount(amount, allow_zero=True)
    if new_amount == previous:
        return entry
    entry.amount = new_amount
    entry.save(update_fields=["amount"])
    from .family_list import sync_family_balance_from_ledger

    sync_family_balance_from_ledger(family)
    if notify:
        from .email_templates import notify_balance_updated

        notify_balance_updated(family, entry, previous_amount=previous)
    return entry


@transaction.atomic
def delete_ledger_entry(family, entry_id, notify=False):
    entry = PortalLedgerEntry.objects.filter(family=family, pk=entry_id).first()
    if not entry:
        raise ValueError("Ledger entry not found.")
    if entry.entry_type not in ("payment", "credit", "discount", "charge"):
        raise ValueError("This entry cannot be deleted.")
    snapshot = _DeletedCharge(entry) if entry.entry_type == "charge" else None
    previous = entry.amount if entry.entry_type == "charge" else None
    entry.delete()
    from .family_list import sync_family_balance_from_ledger

    sync_family_balance_from_ledger(family)
    if notify and snapshot is not None:
        from .email_templates import notify_balance_updated

        notify_balance_updated(family, snapshot, previous_amount=previous)


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
    from .processing_fees import backfill_stripe_fee_totals

    backfill_stripe_fee_totals()
    qs = PortalLedgerEntry.objects.select_related("family", "family__unit").order_by("-date", "-created_at")
    if unit_slug:
        qs = qs.filter(family__unit__slug=unit_slug)
    entries = []
    for entry in qs[:limit]:
        credit_types = ("payment", "credit", "discount")
        from .processing_fees import ledger_paid_totals

        paid, fee, applied = ledger_paid_totals(entry)
        display_amount = paid if entry.entry_type == "payment" else applied
        row = {
            "id": entry.pk,
            "date": entry.date.isoformat(),
            "family_slug": entry.family.slug,
            "family_name": entry.family.name,
            "unit": entry.family.unit.name,
            "child": entry.child_name or "—",
            "type": entry.entry_type,
            "description": entry.description,
            "amount": f"{display_amount:.2f}",
            "fee": f"{fee:.2f}" if entry.entry_type == "payment" and fee else "",
            "is_credit": entry.entry_type in credit_types,
            "manual": entry.is_manual,
        }
        if entry.entry_type == "payment":
            attach_ledger_reference(row, entry.description, entry.reference_number)
        entries.append(row)
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
    """Return the first charge date.

    An explicit start date is honored as-is so staff can post today's charge
    even when the repeat weekday or month-day is different. When no date is
    given, the next matching repeat day from today is used.
    """
    if start:
        return start
    start = timezone.localdate()
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
    if "bi" in label:
        return current + timedelta(days=14)
    if weekday is not None:
        return next_weekday_on_or_after(after, weekday)
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


def _apply_plan_schedule(
    target,
    plan,
    amount=None,
    billing_type=None,
    auto_charge=None,
    next_charge_date=None,
    charge_weekday=None,
    charge_month_day=None,
    four_cs_profile=None,
):
    target.billing_plan = (plan or "").strip() or target.billing_plan
    billing_label = (billing_type or "").strip()
    if amount not in (None, "") and not four_cs_profile:
        target.billing_amount = _parse_amount(amount)
    if four_cs_profile:
        from .agency_weeks import (
            FOUR_CS_WEEKLY_POST_WEEKDAY,
            cadence_key,
            next_thursday_on_or_after,
            next_unposted_parent_period,
            typical_parent_period_amount,
        )

        four_cs_cadence = cadence_key(target.billing_plan)
        four_cs_weekly = four_cs_cadence == "weekly"
        four_cs_biweekly = four_cs_cadence == "biweekly"
        target.billing_amount = typical_parent_period_amount(
            four_cs_profile,
            target.billing_plan,
            start_from=next_charge_date if four_cs_biweekly else None,
        )
        if four_cs_weekly and charge_weekday in (None, ""):
            charge_weekday = FOUR_CS_WEEKLY_POST_WEEKDAY
        if not next_charge_date:
            if four_cs_weekly:
                next_charge_date = next_thursday_on_or_after(timezone.localdate())
            elif four_cs_biweekly:
                next_charge_date = timezone.localdate()
            else:
                upcoming = next_unposted_parent_period(four_cs_profile, target.billing_plan)
                if upcoming:
                    next_charge_date = upcoming["start"]
    if auto_charge is not None:
        target.auto_charge = bool(auto_charge)
        if target.auto_charge and not target.billing_amount and not four_cs_profile:
            raise ValueError("Set a plan amount before turning on automatic charges.")
        if target.auto_charge:
            target.charge_weekday = _parse_optional_int(charge_weekday, 0, 6)
            target.charge_month_day = _parse_optional_int(charge_month_day, 0, 31)
            label = (target.billing_plan or "").lower()
            if four_cs_profile:
                target.next_charge_date = next_charge_date or timezone.localdate()
                if target.charge_weekday is None and target.next_charge_date:
                    target.charge_weekday = target.next_charge_date.weekday()
            elif "month" in label:
                target.charge_weekday = None
                if target.charge_month_day is None:
                    raise ValueError("Pick the day of the month this plan should repeat.")
                target.next_charge_date = first_plan_charge_date(
                    next_charge_date,
                    target.billing_plan,
                    weekday=target.charge_weekday,
                    month_day=target.charge_month_day,
                )
            else:
                target.charge_month_day = None
                if target.charge_weekday is None:
                    raise ValueError("Pick the weekday this plan should repeat.")
                target.next_charge_date = first_plan_charge_date(
                    next_charge_date,
                    target.billing_plan,
                    weekday=target.charge_weekday,
                    month_day=target.charge_month_day,
                )
        else:
            target.next_charge_date = None
            target.charge_weekday = None
            target.charge_month_day = None
    elif next_charge_date is not None:
        target.next_charge_date = next_charge_date
    return target


def _save_extra_billing_plan(
    child,
    family,
    existing=None,
    plan="Weekly",
    amount=None,
    billing_type=None,
    auto_charge=None,
    next_charge_date=None,
    charge_weekday=None,
    charge_month_day=None,
    description="",
    scholarship_fund_id=None,
    scholarship_full_rate=None,
    scholarship_parent_amount=None,
):
    billing_label = (billing_type or "").strip()
    four_cs_profile = (
        agency_profile_for(child)
        if billing_label.lower() == "4cs" or "4cs" in billing_label.lower()
        else None
    )
    row = existing or PortalChildBillingPlan(
        child=child,
        sort_order=next_plan_sort_order(child),
    )
    if amount not in (None, "") and not four_cs_profile:
        row.billing_amount = _parse_amount(amount)
    _apply_plan_schedule(
        row,
        plan,
        amount=amount,
        billing_type=billing_type,
        auto_charge=auto_charge,
        next_charge_date=next_charge_date,
        charge_weekday=charge_weekday,
        charge_month_day=charge_month_day,
        four_cs_profile=four_cs_profile,
    )
    row.description = (description or "").strip()
    row.billing_kind = billing_kind_from_type(billing_label) or row.billing_kind or "private"
    row.save()
    if four_cs_profile:
        _apply_four_cs_plan_scholarship(
            child,
            scholarship_fund_id=scholarship_fund_id,
            scholarship_full_rate=scholarship_full_rate,
            scholarship_parent_amount=scholarship_parent_amount,
            fallback_full_rate=row.billing_amount,
        )
    else:
        _apply_plan_scholarship(
            child,
            scholarship_fund_id=scholarship_fund_id,
            scholarship_full_rate=scholarship_full_rate,
            scholarship_parent_amount=scholarship_parent_amount,
            fallback_full_rate=row.billing_amount if row.billing_amount is not None else amount,
        )
    posted = []
    if row.auto_charge and row.next_charge_date and row.next_charge_date <= timezone.localdate():
        posted = run_due_plan_charges(child=child, plan=row)
    return child, posted


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
    scholarship_fund_id=None,
    scholarship_full_rate=None,
    scholarship_parent_amount=None,
    description=None,
    plan_id=None,
    create_new=False,
):
    child = family.children.filter(name=child_name, is_active=True).first()
    if not child:
        raise ValueError("Child not found on this family account.")
    existing_plan = None
    if plan_id:
        existing_plan = child.billing_plans.filter(pk=plan_id).first()
        if not existing_plan:
            raise ValueError("Plan not found on this child.")
    is_extra = False
    if create_new:
        is_extra = child_has_saved_plan(child)
        if is_extra:
            ensure_primary_billing_plan(child)
            existing_plan = None
    elif existing_plan and existing_plan.sort_order != 1 and existing_plan != primary_billing_plan(child):
        is_extra = True
    if is_extra:
        return _save_extra_billing_plan(
            child,
            family,
            existing=existing_plan,
            plan=plan,
            amount=amount,
            billing_type=billing_type,
            auto_charge=auto_charge,
            next_charge_date=next_charge_date,
            charge_weekday=charge_weekday,
            charge_month_day=charge_month_day,
            description="" if description is None else description,
            scholarship_fund_id=scholarship_fund_id,
            scholarship_full_rate=scholarship_full_rate,
            scholarship_parent_amount=scholarship_parent_amount,
        )
    child.billing_plan = plan.strip() or child.billing_plan
    billing_label = (billing_type or "").strip()
    four_cs_profile = agency_profile_for(child) if billing_label.lower() == "4cs" or "4cs" in billing_label.lower() else None
    if billing_label.lower() == "scholarship":
        parent_amount = scholarship_parent_amount if scholarship_parent_amount not in (None, "") else amount
        assignment = apply_scholarship_to_child_plan(
            child,
            scholarship_fund_id,
            scholarship_full_rate,
            parent_amount,
            start_date=timezone.localdate(),
        )
        child.billing_amount = assignment.parent_amount
    elif not four_cs_profile:
        assignment = _apply_plan_scholarship(
            child,
            scholarship_fund_id=scholarship_fund_id,
            scholarship_full_rate=scholarship_full_rate,
            scholarship_parent_amount=scholarship_parent_amount,
            fallback_full_rate=amount if amount not in (None, "") else child.billing_amount,
        )
        # Keep the plan amount as full tuition before scholarship. Family-pays
        # lives on the scholarship assignment — do not replace the monthly/weekly rate.
        if amount not in (None, ""):
            child.billing_amount = _parse_amount(amount)
        elif assignment and assignment.full_rate is not None:
            child.billing_amount = assignment.full_rate
    elif amount not in (None, ""):
        child.billing_amount = _parse_amount(amount)
    if four_cs_profile:
        from .agency_weeks import (
            FOUR_CS_WEEKLY_POST_WEEKDAY,
            cadence_key,
            next_thursday_on_or_after,
            next_unposted_parent_period,
            typical_parent_period_amount,
        )

        four_cs_cadence = cadence_key(child.billing_plan)
        four_cs_weekly = four_cs_cadence == "weekly"
        four_cs_biweekly = four_cs_cadence == "biweekly"
        child.billing_amount = typical_parent_period_amount(
            four_cs_profile,
            child.billing_plan,
            start_from=next_charge_date if four_cs_biweekly else None,
        )
        _apply_four_cs_plan_scholarship(
            child,
            scholarship_fund_id=scholarship_fund_id,
            scholarship_full_rate=scholarship_full_rate,
            scholarship_parent_amount=scholarship_parent_amount,
            fallback_full_rate=child.billing_amount,
        )
        if four_cs_weekly and charge_weekday in (None, ""):
            charge_weekday = FOUR_CS_WEEKLY_POST_WEEKDAY
        if not next_charge_date:
            if four_cs_weekly:
                next_charge_date = next_thursday_on_or_after(timezone.localdate())
            elif four_cs_biweekly:
                # Start from the day staff is saving — never the contract week
                # range, which can begin before the child or program starts.
                next_charge_date = timezone.localdate()
            else:
                upcoming = next_unposted_parent_period(four_cs_profile, child.billing_plan)
                if upcoming:
                    next_charge_date = upcoming["start"]
    if auto_charge is not None:
        child.auto_charge = bool(auto_charge)
        if child.auto_charge and not child.billing_amount and not four_cs_profile:
            raise ValueError("Set a plan amount before turning on automatic charges.")
        if child.auto_charge:
            child.charge_weekday = _parse_optional_int(charge_weekday, 0, 6)
            child.charge_month_day = _parse_optional_int(charge_month_day, 0, 31)
            label = (child.billing_plan or "").lower()
            if four_cs_profile:
                child.next_charge_date = next_charge_date or timezone.localdate()
                if child.charge_weekday is None and child.next_charge_date:
                    child.charge_weekday = child.next_charge_date.weekday()
            elif "month" in label:
                child.charge_weekday = None
                if child.charge_month_day is None:
                    raise ValueError("Pick the day of the month this plan should repeat.")
                child.next_charge_date = first_plan_charge_date(
                    next_charge_date,
                    child.billing_plan,
                    weekday=child.charge_weekday,
                    month_day=child.charge_month_day,
                )
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
    kind = billing_kind_from_type(billing_type) if billing_type else None
    note = description
    if note is None and existing_plan:
        note = existing_plan.description
    sync_plan_from_child(child, plan=existing_plan if existing_plan and existing_plan.sort_order == 1 else None, description=note, billing_kind=kind)
    if billing_type:
        family.billing_type = billing_type.strip()
        family.save(update_fields=["billing_type"])
    posted = []
    if child.auto_charge and child.next_charge_date and child.next_charge_date <= timezone.localdate():
        posted = run_due_plan_charges(child=child)
    return child, posted


def _next_4cs_charge_date(plan, today, profile, scheduled=None):
    from .agency_weeks import (
        cadence_key,
        next_biweekly_charge_date,
        next_thursday_after,
        next_unposted_parent_period,
    )

    key = cadence_key(plan)
    if key == "weekly":
        return next_thursday_after(today)
    if key == "biweekly":
        return next_biweekly_charge_date(scheduled or today)
    nxt = next_unposted_parent_period(profile, plan)
    return nxt["start"] if nxt else None


def _post_4cs_copay_period(locked, today, plan=None):
    """Post a parent-copay period dated today. Returns True if a family charge was posted.

    Weekly 4Cs copay covers the school week after the most recent Thursday
    (Thursday posts the following week). The ledger date is the post day so
    "post today" appears immediately instead of waiting for the week Monday.
    """
    from .agency_weeks import (
        cadence_key,
        mark_parent_period_posted,
        next_unposted_parent_period,
        parent_period_for_biweekly_from_date,
        parent_period_for_weekly_thursday_post,
    )

    profile = agency_profile_for(locked)
    if not profile:
        return False
    target = plan or locked
    key = cadence_key(target.billing_plan)
    scheduled = target.next_charge_date or today
    if key == "weekly":
        period = parent_period_for_weekly_thursday_post(profile, target.billing_plan, today)
    elif key == "biweekly":
        period = parent_period_for_biweekly_from_date(profile, target.billing_plan, scheduled)
    else:
        period = next_unposted_parent_period(profile, target.billing_plan)
    if not period:
        target.next_charge_date = None
        return False
    charge_date = today
    if target.last_auto_charge_date == charge_date:
        target.next_charge_date = _next_4cs_charge_date(
            target.billing_plan, today, profile, scheduled=scheduled
        )
        return False
    amount = period["amount"]
    if amount > 0:
        post_charge(
            locked.family,
            locked.name,
            "4cs_copay",
            amount,
            charge_date,
            ledger_charge_description(
                locked,
                target.billing_plan,
                "4cs_copay",
                period["label"],
                plan_description_for(locked, plan),
            ),
            is_manual=False,
        )
        scholarship = active_scholarship_for_child(locked, charge_date)
        _family_pays, discount = parent_copay_after_scholarship(scholarship, amount)
        if discount > 0:
            post_discount(
                locked.family,
                locked.name,
                discount,
                charge_date,
                f"{scholarship.fund.name} scholarship",
            )
    mark_parent_period_posted(period["weeks"], charge_date)
    target.last_auto_charge_date = charge_date
    target.next_charge_date = _next_4cs_charge_date(
        target.billing_plan, today, profile, scheduled=scheduled
    )
    return amount > 0


def _post_regular_plan_charge(child, target, today):
    """Post one regular (non-4Cs) period for a child or extra plan. Returns True if posted."""
    charge_date = target.next_charge_date
    if not charge_date:
        return False
    if target.last_auto_charge_date == charge_date:
        target.next_charge_date = next_plan_charge_date(
            charge_date,
            target.billing_plan,
            weekday=target.charge_weekday,
            month_day=target.charge_month_day,
        )
        return False
    plan_row = target if isinstance(target, PortalChildBillingPlan) else None
    note = plan_description_for(child, plan_row)
    scholarship = active_scholarship_for_child(child, charge_date) if plan_row is None or plan_row.sort_order == 1 else None
    if scholarship and scholarship.full_rate:
        post_charge(
            child.family,
            child.name,
            "tuition",
            scholarship.full_rate,
            charge_date,
            ledger_charge_description(child, target.billing_plan, "tuition", description=note),
            is_manual=False,
        )
        discount = scholarship.full_rate - scholarship.parent_amount
        if discount > 0:
            post_discount(
                child.family,
                child.name,
                discount,
                charge_date,
                f"{scholarship.fund.name} scholarship",
            )
    else:
        if not target.billing_amount:
            target.next_charge_date = next_plan_charge_date(
                charge_date,
                target.billing_plan,
                weekday=target.charge_weekday,
                month_day=target.charge_month_day,
            )
            return False
        post_charge(
            child.family,
            child.name,
            "tuition",
            target.billing_amount,
            charge_date,
            ledger_charge_description(child, target.billing_plan, "tuition", description=note),
            is_manual=False,
        )
    target.last_auto_charge_date = charge_date
    target.next_charge_date = next_plan_charge_date(
        charge_date,
        target.billing_plan,
        weekday=target.charge_weekday,
        month_day=target.charge_month_day,
    )
    return True


def _run_due_extra_plan(plan, today):
    child = plan.child
    uses_4cs = plan_uses_4cs_copay(child, plan)
    if not uses_4cs and not plan.billing_amount:
        return False
    did_post = False
    periods = 0
    while plan.next_charge_date and plan.next_charge_date <= today and periods < 8:
        if uses_4cs:
            if _post_4cs_copay_period(child, today, plan=plan):
                did_post = True
            periods += 1
            if not plan.next_charge_date or plan.next_charge_date > today:
                break
            continue
        if _post_regular_plan_charge(child, plan, today):
            did_post = True
        periods += 1
    plan.save(update_fields=["last_auto_charge_date", "next_charge_date", "billing_amount"])
    return did_post


def run_due_plan_charges(today=None, child=None, plan=None):
    """Post due child plan charges and advance each next charge date."""
    from django.db.models import Q

    today = today or timezone.localdate()
    posted = []
    only_child = child
    only_plan = plan
    if only_plan is not None:
        try:
            with transaction.atomic():
                locked_plan = (
                    PortalChildBillingPlan.objects.select_for_update()
                    .select_related("child", "child__family")
                    .filter(pk=only_plan.pk, auto_charge=True, next_charge_date__lte=today)
                    .first()
                )
                if locked_plan and _run_due_extra_plan(locked_plan, today):
                    posted.append(locked_plan.child)
        except Exception:
            if only_child is not None or only_plan is not None:
                raise
        return posted
    due = PortalChild.objects.select_related("family").filter(
        is_active=True,
        auto_charge=True,
        next_charge_date__isnull=False,
        next_charge_date__lte=today,
        family__status="Active",
    ).filter(Q(billing_amount__gt=0) | Q(agency_profile__isnull=False))
    if only_child is not None:
        due = due.filter(pk=only_child.pk)
    for due_child in due:
        try:
            with transaction.atomic():
                locked = (
                    PortalChild.objects.select_for_update()
                    .select_related("family")
                    .filter(pk=due_child.pk, auto_charge=True, next_charge_date__lte=today)
                    .first()
                )
                if not locked:
                    continue
                uses_4cs = child_uses_4cs_copay_plan(locked)
                if not uses_4cs and not locked.billing_amount:
                    continue
                periods = 0
                while (
                    locked.next_charge_date
                    and locked.next_charge_date <= today
                    and periods < 8
                ):
                    if uses_4cs:
                        did_post = _post_4cs_copay_period(locked, today)
                        if did_post:
                            posted.append(locked)
                        periods += 1
                        if not locked.next_charge_date or locked.next_charge_date > today:
                            break
                        continue
                    if _post_regular_plan_charge(locked, locked, today):
                        posted.append(locked)
                    periods += 1
                locked.save(update_fields=["last_auto_charge_date", "next_charge_date"])
                primary = primary_billing_plan(locked)
                if primary:
                    primary.next_charge_date = locked.next_charge_date
                    primary.last_auto_charge_date = locked.last_auto_charge_date
                    primary.billing_amount = locked.billing_amount
                    primary.auto_charge = locked.auto_charge
                    primary.billing_plan = locked.billing_plan
                    primary.charge_weekday = locked.charge_weekday
                    primary.charge_month_day = locked.charge_month_day
                    primary.save(
                        update_fields=[
                            "next_charge_date",
                            "last_auto_charge_date",
                            "billing_amount",
                            "auto_charge",
                            "billing_plan",
                            "charge_weekday",
                            "charge_month_day",
                        ]
                    )
        except Exception:
            if only_child is not None:
                raise
            continue
    extra = PortalChildBillingPlan.objects.select_related("child", "child__family").filter(
        auto_charge=True,
        next_charge_date__isnull=False,
        next_charge_date__lte=today,
        child__is_active=True,
        child__family__status="Active",
        sort_order__gt=1,
    ).filter(Q(billing_amount__gt=0) | Q(child__agency_profile__isnull=False))
    if only_child is not None:
        extra = extra.filter(child=only_child)
    for extra_plan in extra:
        try:
            with transaction.atomic():
                locked_plan = (
                    PortalChildBillingPlan.objects.select_for_update()
                    .select_related("child", "child__family")
                    .filter(pk=extra_plan.pk, auto_charge=True, next_charge_date__lte=today)
                    .first()
                )
                if locked_plan and _run_due_extra_plan(locked_plan, today):
                    posted.append(locked_plan.child)
        except Exception:
            if only_child is not None:
                raise
            continue
    return posted


def _scheduled_row(child, plan_label, repeat, amount, next_charge_date, description=""):
    label = plan_label
    note = (description or "").strip()
    if note:
        label = f"{note} · {plan_label}" if plan_label else note
    return {
        "family_slug": child.family.slug,
        "family_name": child.family.name,
        "unit": child.family.unit.name if child.family.unit_id else "",
        "child_name": child.name,
        "plan": label,
        "repeat": repeat,
        "amount": f"{amount:.2f}" if amount is not None else "—",
        "next_charge_date": next_charge_date.isoformat() if next_charge_date else "",
    }


def get_scheduled_plan_charges(limit=50):
    children = (
        PortalChild.objects.select_related("family", "family__unit")
        .filter(is_active=True, auto_charge=True, next_charge_date__isnull=False)
        .order_by("next_charge_date", "family__name", "name")[:limit]
    )
    rows = []
    for child in children:
        primary = primary_billing_plan(child)
        rows.append(
            _scheduled_row(
                child,
                child.billing_plan,
                plan_repeat_label(child),
                child.billing_amount,
                child.next_charge_date,
                primary.description if primary else "",
            )
        )
    extras = (
        PortalChildBillingPlan.objects.select_related("child", "child__family", "child__family__unit")
        .filter(
            auto_charge=True,
            next_charge_date__isnull=False,
            child__is_active=True,
            sort_order__gt=1,
        )
        .order_by("next_charge_date", "child__family__name", "child__name")[:limit]
    )
    for plan in extras:
        rows.append(
            _scheduled_row(
                plan.child,
                plan.billing_plan,
                plan_repeat_label(plan),
                plan.billing_amount,
                plan.next_charge_date,
                plan.description,
            )
        )
    rows.sort(key=lambda row: (row["next_charge_date"] or "", row["family_name"], row["child_name"], row["plan"]))
    return rows[:limit]


@transaction.atomic
def delete_child_billing_plan(family, child_name, plan_id):
    child = family.children.filter(name=child_name, is_active=True).first()
    if not child:
        raise ValueError("Child not found on this family account.")
    plan = child.billing_plans.filter(pk=plan_id).first()
    if not plan:
        raise ValueError("Plan not found on this child.")
    was_primary = plan.sort_order == 1 or plan == primary_billing_plan(child)
    plan.delete()
    if was_primary:
        nxt = child.billing_plans.order_by("sort_order", "pk").first()
        if nxt:
            nxt.sort_order = 1
            nxt.save(update_fields=["sort_order"])
            sync_child_from_plan(child, nxt)
        else:
            child.auto_charge = False
            child.next_charge_date = None
            child.charge_weekday = None
            child.charge_month_day = None
            child.save(
                update_fields=["auto_charge", "next_charge_date", "charge_weekday", "charge_month_day"]
            )
    return child


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
    from .family_list import sync_family_balance_from_ledger

    sync_family_balance_from_ledger(family)
    return payment
