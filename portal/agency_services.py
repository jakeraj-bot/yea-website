"""4Cs / agency billing services for staff portal."""

from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.utils import timezone

from .demo_data import AGENCY_BILLING, AGENCY_UNIT_DATA
from .models import (
    PortalAgencyLedgerEntry,
    PortalAgencyProfile,
    PortalAgencyRemittance,
    PortalAgencyRemittanceAllocation,
    PortalChild,
    PortalFamily,
    PortalProgram,
    PortalUnit,
)


def _parse_amount(value):
    try:
        amount = Decimal(str(value).replace(",", "").strip())
    except (InvalidOperation, TypeError):
        raise ValueError("Enter a valid dollar amount.")
    return amount.quantize(Decimal("0.01"))


DEMO_AGENCY_AUTH_NUMBERS = frozenset({"4CS-2026-8841", "4CS-2026-9012"})
DEMO_AGENCY_CHILDREN = frozenset({("martinez", "sofia martinez"), ("chen", "ethan chen")})


def get_agency_billing_live(family_slug, unit=None):
    profile = (
        PortalAgencyProfile.objects.filter(family__slug=family_slug)
        .select_related("child", "family")
        .first()
    )
    if not profile:
        if _portal_data_live():
            return None
        return AGENCY_BILLING.get(family_slug)
    ledger = [
        {
            "date": entry.date.isoformat(),
            "type": entry.entry_type,
            "description": entry.description,
            "amount": f"{entry.amount:.2f}" if entry.entry_type == "charge" else f"-{abs(entry.amount):.2f}",
        }
        for entry in profile.ledger_entries.all()
    ]
    if not ledger and not _portal_data_live():
        demo = AGENCY_BILLING.get(family_slug)
        if demo:
            ledger = demo.get("ledger", [])
    return {
        "family_name": profile.family.name,
        "slug": profile.family.slug,
        "child_name": profile.child.name,
        "auth_number": profile.auth_number,
        "agency_name": "Passaic County 4Cs",
        "running_balance": f"{profile.agency_balance:.2f}",
        "weekly_agency_rate": f"{profile.weekly_agency_rate:.2f}",
        "ledger": ledger,
    }


def _empty_agency_page(unit):
    return {
        "agency_name": "Passaic County 4Cs",
        "unit": unit.name if unit else "",
        "children": [],
        "recent_agency_payments": [],
        "family_options": [],
        "program_options": ["After-School 2026–27"],
        "pending_4cs": [],
        "agency_live": True,
    }


def purge_demo_agency_members():
    """Delete seeded Sofia Martinez / Ethan Chen 4Cs profiles (and leftover demo families)."""
    deleted_profiles = 0
    for profile in PortalAgencyProfile.objects.select_related("child", "family"):
        slug = (profile.family.slug or "").lower()
        child_name = (profile.child.name or "").strip().lower()
        if profile.auth_number in DEMO_AGENCY_AUTH_NUMBERS or (slug, child_name) in DEMO_AGENCY_CHILDREN:
            profile.delete()
            deleted_profiles += 1

    deleted_families = 0
    demo_slugs = {slug for slug, _name in DEMO_AGENCY_CHILDREN}
    for family in PortalFamily.objects.filter(slug__in=demo_slugs):
        has_real_app = family.enrollment_applications.exists()
        kids = list(family.children.all())
        only_demo_kids = kids and all(
            (family.slug.lower(), kid.name.strip().lower()) in DEMO_AGENCY_CHILDREN for kid in kids
        )
        if has_real_app and not only_demo_kids:
            continue
        if has_real_app:
            family.billing_type = family.billing_type if family.billing_type != "4Cs" else ""
            if family.billing_type == "":
                family.billing_type = "Private pay"
                family.save(update_fields=["billing_type"])
            continue
        family.delete()
        deleted_families += 1
    return deleted_profiles, deleted_families


def agency_page_data(unit):
    """Build agency page context from live 4Cs profiles only — never demo Sofia/Ethan."""
    if _portal_data_live():
        data = _empty_agency_page(unit)
    else:
        data = {
            **AGENCY_UNIT_DATA,
            "children": list(AGENCY_UNIT_DATA.get("children", [])),
            "recent_agency_payments": list(AGENCY_UNIT_DATA.get("recent_agency_payments", [])),
            "family_options": list(AGENCY_UNIT_DATA.get("family_options", [])),
            "program_options": list(AGENCY_UNIT_DATA.get("program_options", [])),
        }
        data["unit"] = unit.name if unit else data.get("unit", "School 18")
    if not unit:
        return data

    profiles = (
        PortalAgencyProfile.objects.filter(unit=unit)
        .select_related("child", "family")
        .order_by("child__name")
    )
    if profiles.exists():
        children = []
        for profile in profiles:
            children.append(
                {
                    "slug": profile.child.name.lower().replace(" ", "-"),
                    "child": profile.child.name,
                    "family": profile.family.name,
                    "family_slug": profile.family.slug,
                    "profile_id": profile.pk,
                    "dob": "",
                    "grade": profile.child.grade,
                    "program": profile.family.program_label or "After-School 2026–27",
                    "auth_number": profile.auth_number,
                    "auth_start": profile.auth_start.isoformat() if profile.auth_start else "",
                    "auth_end": profile.auth_end.isoformat() if profile.auth_end else "",
                    "weekly_copay": f"{profile.weekly_copay:.2f}",
                    "agency_rate": f"{profile.weekly_agency_rate:.2f}",
                    "copay_balance": f"{profile.family.balance:.2f}",
                    "agency_balance": f"{profile.agency_balance:.2f}",
                    "last_agency_payment": "",
                    "agency_payment_amount": f"{profile.weekly_agency_rate:.2f}",
                }
            )
        data["children"] = children

    families = PortalFamily.objects.filter(unit=unit).order_by("name")
    data["family_options"] = [
        {
            "slug": family.slug,
            "name": family.name,
            "children": [c.name for c in family.children.filter(is_active=True)],
        }
        for family in families
    ]

    program = PortalProgram.objects.filter(unit=unit, is_active=True).first()
    if program:
        data["program_options"] = [program.name]

    remittances = PortalAgencyRemittance.objects.filter(unit=unit).prefetch_related(
        "allocations__profile__child", "allocations__profile__family"
    )[:10]
    if remittances.exists():
        data["recent_agency_payments"] = [
            {
                "date": rem.date.isoformat(),
                "reference": rem.reference,
                "amount": f"{rem.total_amount:.2f}",
                "children": ", ".join(
                    {a.profile.family.name for a in rem.allocations.all()}
                ),
                "allocations": [
                    {
                        "child": alloc.profile.child.name,
                        "family_slug": alloc.profile.family.slug,
                        "amount": f"{alloc.amount:.2f}",
                    }
                    for alloc in rem.allocations.all()
                ],
            }
            for rem in remittances
        ]

    data["agency_live"] = _portal_data_live()
    from .member_admin import pending_4cs_children

    data["pending_4cs"] = [
        {
            "child": child.name,
            "family": child.family.name,
            "family_slug": child.family.slug,
            "family_id": child.family_id,
            "school": child.school or "—",
        }
        for child in pending_4cs_children(unit)
    ]
    return data


def _portal_data_live():
    from .attendance_service import portal_is_live

    return portal_is_live()


@transaction.atomic
def add_agency_child(unit, family_slug, child_name, grade, auth_number, weekly_copay, weekly_rate, program_label="", notes="", auth_start=None, auth_end=None):
    family = PortalFamily.objects.filter(unit=unit, slug=family_slug).first()
    if not family:
        raise ValueError("Family not found.")

    family.billing_type = "4Cs"
    if program_label:
        family.program_label = program_label
    family.save(update_fields=["billing_type", "program_label"])

    child, _ = PortalChild.objects.get_or_create(
        family=family,
        name=child_name.strip(),
        defaults={"grade": grade, "is_active": True},
    )
    if grade:
        child.grade = grade
        child.save(update_fields=["grade"])

    profile, created = PortalAgencyProfile.objects.update_or_create(
        child=child,
        defaults={
            "unit": unit,
            "family": family,
            "auth_number": auth_number.strip(),
            "auth_start": auth_start,
            "auth_end": auth_end,
            "weekly_copay": _parse_amount(weekly_copay or "0"),
            "weekly_agency_rate": _parse_amount(weekly_rate or "0"),
            "notes": notes,
        },
    )
    return profile


@transaction.atomic
def post_agency_remittance(unit, remittance_date, reference, total_amount, allocations):
    total = _parse_amount(total_amount)
    allocated = sum(_parse_amount(item["amount"]) for item in allocations)
    if allocated != total:
        raise ValueError("Allocated total must match the payment amount.")

    remittance = PortalAgencyRemittance.objects.create(
        unit=unit,
        date=remittance_date,
        reference=reference.strip(),
        total_amount=total,
    )
    for item in allocations:
        profile = PortalAgencyProfile.objects.filter(pk=item["profile_id"], unit=unit).first()
        if not profile:
            continue
        amount = _parse_amount(item["amount"])
        PortalAgencyRemittanceAllocation.objects.create(
            remittance=remittance,
            profile=profile,
            amount=amount,
        )
        PortalAgencyLedgerEntry.objects.create(
            profile=profile,
            date=remittance_date,
            entry_type="payment",
            description=f"Agency remittance {reference}",
            amount=-amount,
            is_manual=True,
        )
        profile.agency_balance = max(Decimal("0"), profile.agency_balance - amount)
        profile.save(update_fields=["agency_balance"])
    return remittance


def copay_report_rows(unit):
    rows = []
    for profile in PortalAgencyProfile.objects.filter(unit=unit).select_related("child", "family"):
        rows.append(
            {
                "child": profile.child.name,
                "family": profile.family.name,
                "family_slug": profile.family.slug,
                "weekly_copay": f"{profile.weekly_copay:.2f}",
                "copay_balance": f"{profile.family.balance:.2f}",
                "agency_balance": f"{profile.agency_balance:.2f}",
                "auth_number": profile.auth_number,
            }
        )
    return rows


def balances_report_rows(unit):
    rows = []
    for family in PortalFamily.objects.filter(unit=unit).order_by("name"):
        if family.balance <= 0:
            continue
        rows.append(
            {
                "family": family.name,
                "slug": family.slug,
                "contact": family.primary_contact,
                "billing_type": family.billing_type,
                "balance": f"{family.balance:.2f}",
                "program": family.program_label,
            }
        )
    return rows
