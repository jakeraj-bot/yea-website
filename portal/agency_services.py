"""4Cs / agency billing services for staff portal."""

from decimal import Decimal

from django.db import transaction
from django.utils.dateparse import parse_date

from .agency_weeks import (
    parse_money,
    preview_weeks,
    refresh_agency_expected_balance,
    serialize_week,
    sync_contract_weeks,
    weekly_from_daily,
)
from .demo_data import AGENCY_BILLING, AGENCY_UNIT_DATA
from .models import (
    PortalAgency,
    PortalAgencyLedgerEntry,
    PortalAgencyProfile,
    PortalAgencyRemittance,
    PortalAgencyRemittanceAllocation,
    PortalChild,
    PortalFamily,
    PortalProgram,
)


def _parse_amount(value):
    return parse_money(value, allow_blank=False)


DEMO_AGENCY_AUTH_NUMBERS = frozenset({"4CS-2026-8841", "4CS-2026-9012"})
DEMO_AGENCY_CHILDREN = frozenset({("martinez", "sofia martinez"), ("chen", "ethan chen")})


def _agency_account_from_profile(profile, ledger=None):
    if ledger is None:
        ledger = [
            {
                "date": entry.date.isoformat(),
                "type": entry.entry_type,
                "description": entry.description,
                "amount": f"{entry.amount:.2f}" if entry.entry_type == "charge" else f"-{abs(entry.amount):.2f}",
            }
            for entry in profile.ledger_entries.all()
        ]
    return {
        "family_name": profile.family.name,
        "slug": profile.family.slug,
        "child_name": profile.child.name,
        "child_id": profile.child_id,
        "auth_number": profile.auth_number,
        "agency_name": profile.agency.name if profile.agency_id else "Passaic County 4Cs",
        "running_balance": f"{profile.agency_balance:.2f}",
        "weekly_agency_rate": f"{profile.weekly_agency_rate:.2f}",
        "daily_agency_rate": f"{profile.daily_agency_rate:.2f}",
        "daily_copay": f"{profile.daily_copay:.2f}",
        "weekly_copay": f"{profile.weekly_copay:.2f}",
        "contract_start": profile.auth_start.isoformat() if profile.auth_start else "",
        "contract_end": profile.auth_end.isoformat() if profile.auth_end else "",
        "profile_id": profile.pk,
        "weeks": [serialize_week(week) for week in profile.contract_weeks.order_by("week_start")],
        "ledger": ledger,
    }


def get_agency_billing_live(family_slug, unit=None):
    profile = (
        PortalAgencyProfile.objects.filter(family__slug=family_slug)
        .select_related("child", "family", "agency")
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
    return _agency_account_from_profile(profile, ledger)


def get_agency_accounts_for_family(family_slug, unit=None):
    profiles = list(
        PortalAgencyProfile.objects.filter(family__slug=family_slug)
        .select_related("child", "family", "agency")
        .prefetch_related("contract_weeks")
        .order_by("child__name")
    )
    if profiles:
        return [_agency_account_from_profile(profile) for profile in profiles]
    if _portal_data_live():
        return []
    demo = AGENCY_BILLING.get(family_slug)
    return [demo] if demo else []


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
        "agency_options": [],
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
        .select_related("child", "family", "agency")
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
                    "agency_name": profile.agency.name if profile.agency_id else "Passaic County 4Cs",
                    "copay_balance": f"{profile.family.balance:.2f}",
                    "agency_balance": f"{profile.agency_balance:.2f}",
                    "last_agency_payment": "",
                    "agency_payment_amount": f"{profile.weekly_agency_rate:.2f}",
                    "child_id": profile.child_id,
                }
            )
        data["children"] = children

    from .unit_visibility import child_belongs_to_unit, families_qs_for_unit

    families = families_qs_for_unit(unit).order_by("name")
    data["family_options"] = [
        {
            "slug": family.slug,
            "name": family.name,
            "children": [
                child.name
                for child in family.children.filter(is_active=True)
                if child_belongs_to_unit(child, unit)
            ],
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
    data["pending_4cs"] = pending_4cs_rows(unit)
    data["agency_options"] = list(PortalAgency.objects.filter(is_active=True).order_by("name").values("pk", "name"))
    return data


def pending_4cs_rows(unit=None):
    from .member_admin import pending_4cs_children

    rows = []
    for child in pending_4cs_children(unit):
        rows.append(
            {
                "child": child.name,
                "child_id": child.pk,
                "family": child.family.name,
                "family_slug": child.family.slug,
                "family_id": child.family_id,
                "unit": child.family.unit.name if child.family.unit_id else "",
                "unit_id": child.family.unit_id,
                "school": child.school or "—",
            }
        )
    return rows


def resolve_agency_by_name(name, unit=None):
    from .admin_config import _slug_unique

    name = (name or "").strip()
    if not name:
        raise ValueError("Agency name is required.")
    agency = PortalAgency.objects.filter(name__iexact=name).first()
    if agency:
        if unit and not agency.units.filter(pk=unit.pk).exists():
            agency.units.add(unit)
        return agency
    agency = PortalAgency.objects.create(
        slug=_slug_unique(name, PortalAgency),
        name=name,
        is_active=True,
    )
    if unit:
        agency.units.add(unit)
    return agency


def posted_weeks_from_form(data):
    starts = data.getlist("week_start") if hasattr(data, "getlist") else data.get("week_start") or []
    ends = data.getlist("week_end") if hasattr(data, "getlist") else data.get("week_end") or []
    agency_amounts = data.getlist("week_agency") if hasattr(data, "getlist") else data.get("week_agency") or []
    parent_amounts = data.getlist("week_parent") if hasattr(data, "getlist") else data.get("week_parent") or []
    rows = []
    for index, start_raw in enumerate(starts):
        week_start = parse_date(str(start_raw or "").strip())
        week_end = parse_date(str(ends[index] if index < len(ends) else "").strip()) if ends else None
        if not week_start:
            continue
        rows.append(
            {
                "week_start": week_start,
                "week_end": week_end,
                "agency_amount": parse_money(agency_amounts[index] if index < len(agency_amounts) else "0"),
                "parent_amount": parse_money(parent_amounts[index] if index < len(parent_amounts) else "0"),
            }
        )
    return rows


def _portal_data_live():
    from .attendance_service import portal_is_live

    return portal_is_live()


def _resolve_family_and_child(unit, family_slug, child_name, child_id=None, grade=""):
    family = None
    if unit:
        family = PortalFamily.objects.filter(unit=unit, slug=family_slug).first()
    if not family and family_slug:
        family = PortalFamily.objects.filter(slug=family_slug).first()
    if child_id:
        child = PortalChild.objects.select_related("family", "family__unit").filter(pk=child_id).first()
        if not child:
            raise ValueError("Member not found.")
        if unit and child.family.unit_id != unit.pk:
            raise ValueError("That member is not at this unit.")
        family = child.family
        return family, child
    if not family:
        raise ValueError("Family not found.")
    name = (child_name or "").strip()
    if not name:
        raise ValueError("Member name is required.")
    child = family.children.filter(name=name).first()
    if child is None:
        child = PortalChild.objects.create(
            family=family,
            name=name,
            grade=grade or "",
            is_active=True,
        )
    else:
        if grade:
            child.grade = grade
            child.save(update_fields=["grade"])
        if not child.is_active:
            child.is_active = True
            child.save(update_fields=["is_active"])
    return family, child


@transaction.atomic
def save_agency_member(
    unit,
    family_slug,
    child_name,
    agency_name,
    auth_start=None,
    auth_end=None,
    daily_agency_rate="0",
    weekly_agency_rate="0",
    weekly_agency_overridden=False,
    daily_copay="0",
    weekly_copay="0",
    weekly_copay_overridden=False,
    posted_weeks=None,
    reset_week_rates=False,
    child_id=None,
    grade="",
    auth_number="",
    program_label="",
    notes="",
    profile=None,
):
    family, child = _resolve_family_and_child(unit, family_slug, child_name, child_id=child_id, grade=grade)
    if unit is None:
        unit = family.unit
    family.billing_type = "4Cs"
    if program_label:
        family.program_label = program_label
    family.save(update_fields=["billing_type", "program_label"])

    agency = resolve_agency_by_name(agency_name, unit)
    daily_agency = parse_money(daily_agency_rate)
    daily_parent = parse_money(daily_copay)
    if weekly_agency_overridden:
        weekly_agency = parse_money(weekly_agency_rate)
    else:
        weekly_agency = weekly_from_daily(daily_agency) if daily_agency else parse_money(weekly_agency_rate)
    if weekly_copay_overridden:
        weekly_parent = parse_money(weekly_copay)
    else:
        weekly_parent = weekly_from_daily(daily_parent) if daily_parent else parse_money(weekly_copay)

    defaults = {
        "unit": unit,
        "family": family,
        "agency": agency,
        "auth_number": (auth_number or "").strip(),
        "auth_start": auth_start,
        "auth_end": auth_end,
        "daily_agency_rate": daily_agency,
        "weekly_agency_rate": weekly_agency,
        "weekly_agency_overridden": bool(weekly_agency_overridden),
        "daily_copay": daily_parent,
        "weekly_copay": weekly_parent,
        "weekly_copay_overridden": bool(weekly_copay_overridden),
        "notes": notes or "",
    }
    if profile is None:
        profile = PortalAgencyProfile.objects.filter(child=child).first()
    if profile:
        for key, value in defaults.items():
            setattr(profile, key, value)
        profile.save()
    else:
        profile = PortalAgencyProfile.objects.create(child=child, **defaults)

    sync_contract_weeks(profile, posted_weeks=posted_weeks or [], reset_overrides=reset_week_rates)
    refresh_agency_expected_balance(profile)
    return profile


@transaction.atomic
def add_agency_child(
    unit,
    family_slug,
    child_name,
    grade,
    auth_number,
    weekly_copay,
    weekly_rate,
    program_label="",
    notes="",
    auth_start=None,
    auth_end=None,
    agency_name="",
    daily_agency_rate="0",
    daily_copay="0",
    weekly_agency_overridden=True,
    weekly_copay_overridden=True,
    posted_weeks=None,
    reset_week_rates=False,
    child_id=None,
):
    return save_agency_member(
        unit,
        family_slug,
        child_name,
        agency_name or "Passaic County 4Cs",
        auth_start=auth_start,
        auth_end=auth_end,
        daily_agency_rate=daily_agency_rate,
        weekly_agency_rate=weekly_rate,
        weekly_agency_overridden=weekly_agency_overridden,
        daily_copay=daily_copay,
        weekly_copay=weekly_copay,
        weekly_copay_overridden=weekly_copay_overridden,
        posted_weeks=posted_weeks,
        reset_week_rates=reset_week_rates,
        child_id=child_id,
        grade=grade,
        auth_number=auth_number,
        program_label=program_label,
        notes=notes,
    )


def agency_form_context(profile=None, child=None, family=None, unit=None, data=None):
    agencies = list(PortalAgency.objects.filter(is_active=True).order_by("name"))
    form = {
        "agency_name": "",
        "family_slug": family.slug if family else "",
        "family_name": family.name if family else "",
        "child_name": child.name if child else "",
        "child_id": child.pk if child else "",
        "grade": child.grade if child else "",
        "auth_number": "",
        "auth_start": "",
        "auth_end": "",
        "daily_agency_rate": "",
        "weekly_agency_rate": "",
        "weekly_agency_overridden": False,
        "daily_copay": "",
        "weekly_copay": "",
        "weekly_copay_overridden": False,
        "notes": "",
        "weeks": [],
        "locked_member": bool(child),
        "unit_name": (unit.name if unit else "") or (family.unit.name if family and family.unit_id else ""),
        "four_cs": True,
        "profile_id": profile.pk if profile else "",
    }
    if profile:
        form.update(
            {
                "agency_name": profile.agency.name if profile.agency_id else "",
                "family_slug": profile.family.slug,
                "family_name": profile.family.name,
                "child_name": profile.child.name,
                "child_id": profile.child_id,
                "grade": profile.child.grade,
                "auth_number": profile.auth_number,
                "auth_start": profile.auth_start.isoformat() if profile.auth_start else "",
                "auth_end": profile.auth_end.isoformat() if profile.auth_end else "",
                "daily_agency_rate": f"{profile.daily_agency_rate:.2f}",
                "weekly_agency_rate": f"{profile.weekly_agency_rate:.2f}",
                "weekly_agency_overridden": profile.weekly_agency_overridden,
                "daily_copay": f"{profile.daily_copay:.2f}",
                "weekly_copay": f"{profile.weekly_copay:.2f}",
                "weekly_copay_overridden": profile.weekly_copay_overridden,
                "notes": profile.notes,
                "weeks": [serialize_week(week) for week in profile.contract_weeks.order_by("week_start")],
                "locked_member": True,
                "unit_name": profile.unit.name if profile.unit_id else form["unit_name"],
                "profile_id": profile.pk,
            }
        )
    if data:
        form["agency_name"] = data.get("agency_name", form["agency_name"])
        form["family_slug"] = data.get("family_slug", form["family_slug"])
        form["child_name"] = data.get("child_name", form["child_name"])
        form["child_id"] = data.get("child_id") or form["child_id"]
        form["auth_number"] = data.get("auth_number", form["auth_number"])
        form["auth_start"] = data.get("auth_start", form["auth_start"])
        form["auth_end"] = data.get("auth_end", form["auth_end"])
        form["daily_agency_rate"] = data.get("daily_agency_rate", form["daily_agency_rate"])
        form["weekly_agency_rate"] = data.get("weekly_agency_rate", form["weekly_agency_rate"])
        form["weekly_agency_overridden"] = data.get("weekly_agency_overridden") == "on" or form["weekly_agency_overridden"]
        form["daily_copay"] = data.get("daily_copay", form["daily_copay"])
        form["weekly_copay"] = data.get("weekly_copay", form["weekly_copay"])
        form["weekly_copay_overridden"] = data.get("weekly_copay_overridden") == "on" or form["weekly_copay_overridden"]
        form["notes"] = data.get("notes", form["notes"])
        start = parse_date(form["auth_start"] or "") if form["auth_start"] else None
        end = parse_date(form["auth_end"] or "") if form["auth_end"] else None
        weekly_agency = parse_money(form["weekly_agency_rate"])
        weekly_parent = parse_money(form["weekly_copay"])
        if start and end:
            form["weeks"] = preview_weeks(start, end, weekly_agency, weekly_parent)
    elif not form["weeks"] and form["auth_start"] and form["auth_end"]:
        start = parse_date(form["auth_start"])
        end = parse_date(form["auth_end"])
        form["weeks"] = preview_weeks(
            start,
            end,
            parse_money(form["weekly_agency_rate"]),
            parse_money(form["weekly_copay"]),
        )
    return {
        "form": form,
        "agencies": agencies,
        "profile": profile,
        "child": child,
        "family": family,
    }


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
    from .unit_visibility import families_qs_for_unit

    rows = []
    for family in families_qs_for_unit(unit).order_by("name"):
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
