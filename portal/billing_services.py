from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.utils import timezone

from .demo_data import prepare_billing_preview
from .models import PortalAgencyProfile, PortalFamily, PortalLedgerEntry
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
