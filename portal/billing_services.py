from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.utils import timezone

from .demo_data import prepare_billing_preview
from .models import PortalFamily, PortalLedgerEntry
from .parent_services import get_billing_live


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
def post_charge(family, child_name, charge_type, amount, entry_date, description):
    amount = _parse_amount(amount)
    label = description.strip() or charge_type.replace("_", " ").title()
    PortalLedgerEntry.objects.create(
        family=family,
        child_name=child_name,
        date=entry_date,
        entry_type="charge",
        description=label,
        amount=amount,
        is_manual=True,
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
    family.balance = max(Decimal("0"), family.balance - amount)
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
    family.balance = max(Decimal("0"), family.balance - amount)
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


@transaction.atomic
def update_child_billing_plan(family, child_name, plan, amount=None, billing_type=None):
    child = family.children.filter(name=child_name, is_active=True).first()
    if not child:
        raise ValueError("Child not found on this family account.")
    child.billing_plan = plan.strip() or child.billing_plan
    if amount not in (None, ""):
        child.billing_amount = _parse_amount(amount)
    child.save(update_fields=["billing_plan", "billing_amount"])
    if billing_type:
        family.billing_type = billing_type.strip()
        family.save(update_fields=["billing_type"])
    return child
