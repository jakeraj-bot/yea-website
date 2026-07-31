"""Admin portal configuration — units, programs, agencies, fees, scholarships, policies."""

import re
from decimal import Decimal, InvalidOperation

from django.utils import timezone
from django.utils.text import slugify

from .demo_data import (
    ADMIN_AGENCIES,
    BILLING_CHARGE_TYPES,
    CHECKIN_MODES,
    FEE_RULES,
    PORTAL_STAFF_ROLES,
    PROGRAMS,
    SCHOLARSHIP_FUNDS,
    UNITS,
)
from .models import (
    PortalAgency,
    PortalAgencyProfile,
    PortalBillingDefaultRule,
    PortalCheckInSetting,
    PortalChild,
    PortalFeeRule,
    PortalOrgPolicy,
    PortalPaymentPlan,
    PortalPolicySignatureRequest,
    PortalProcessingFee,
    PortalProgram,
    PortalScholarshipAssignment,
    PortalScholarshipFund,
    PortalStaffAccount,
    PortalStaffRole,
    PortalTaxStatementSetting,
    PortalUnit,
    PortalWaivedAbsenceCharge,
)


def _slug_unique(base, model, field="slug"):
    slug = slugify(base) or "item"
    candidate = slug
    n = 1
    while model.objects.filter(**{field: candidate}).exists():
        candidate = f"{slug}-{n}"
        n += 1
    return candidate


def _parse_decimal(value, default="0"):
    try:
        return Decimal(str(value or default).replace(",", "").strip() or default)
    except (InvalidOperation, TypeError):
        return Decimal(default)


def ensure_admin_config_minimal():
    """Org-wide defaults only — no demo units, families, agencies, or scholarships."""
    for rule in FEE_RULES:
        PortalFeeRule.objects.get_or_create(
            key=rule["key"],
            defaults={
                "name": rule["name"],
                "amount": rule.get("amount", ""),
                "display": rule.get("display", ""),
                "frequency": rule.get("frequency", ""),
                "period": rule.get("period", ""),
                "notes": rule.get("notes", ""),
            },
        )
    for mode in CHECKIN_MODES:
        PortalCheckInSetting.objects.get_or_create(
            key=mode["key"],
            defaults={
                "label": mode["label"],
                "description": mode.get("description", ""),
                "enabled": mode.get("enabled", False),
            },
        )
    for role in PORTAL_STAFF_ROLES:
        PortalStaffRole.objects.update_or_create(name=role, defaults={"is_system": True})
    defaults = [
        ("Unit staff", True, False, False, False),
        ("Unit director", True, True, False, False),
        ("Portal admin", True, True, True, True),
        ("Front desk staff", True, False, False, False),
    ]
    for role_name, add, delete, credit, plans in defaults:
        PortalBillingDefaultRule.objects.get_or_create(
            role_name=role_name,
            defaults={
                "can_add_charge": add,
                "can_delete_charge": delete,
                "can_add_credit": credit,
                "can_edit_family_plans": plans,
                "is_custom": False,
            },
        )
    if not PortalPaymentPlan.objects.exists():
        for name, interval in [("Weekly", "weekly"), ("Bi-weekly", "biweekly"), ("Monthly", "monthly")]:
            PortalPaymentPlan.objects.create(name=name, interval=interval, is_active=True)
    if not PortalProcessingFee.objects.exists():
        PortalProcessingFee.objects.create(name="Card processing", percent=Decimal("2.90"), flat_amount=Decimal("0.30"))
    if not PortalTaxStatementSetting.objects.exists():
        PortalTaxStatementSetting.objects.create()


def ensure_admin_config_seeded():
    """Org defaults for admin pages — no demo units, families, or agencies."""
    ensure_admin_config_minimal()


def ensure_demo_admin_content():
    """Demo units, agencies, and scholarships — run only via seed_portal."""
    for unit_data in UNITS:
        PortalUnit.objects.get_or_create(
            slug=unit_data["slug"],
            defaults={
                "name": unit_data["name"],
                "is_active": unit_data.get("active", True),
                "program_type": unit_data.get("program_type", "after_school"),
                "address": unit_data.get("address", ""),
                "city": unit_data.get("city", ""),
                "phone": unit_data.get("phone", ""),
                "manager_name": unit_data.get("manager", ""),
                "capacity": unit_data.get("capacity", 0),
            },
        )
    if not PortalScholarshipFund.objects.exists():
        for fund in SCHOLARSHIP_FUNDS:
            PortalScholarshipFund.objects.create(
                name=fund["name"],
                description=fund.get("description", ""),
                is_active=fund.get("active", True),
            )
    if not PortalAgency.objects.exists():
        for agency in ADMIN_AGENCIES:
            obj, _ = PortalAgency.objects.update_or_create(
                slug=agency.get("slug", slugify(agency["name"])),
                defaults={
                    "name": agency["name"],
                    "contact_name": agency.get("contact_name", ""),
                    "contact_email": agency.get("contact_email", ""),
                    "contact_phone": agency.get("contact_phone", ""),
                    "default_weekly_rate": _parse_decimal(agency.get("default_weekly_rate", "0")),
                    "remittance_schedule": agency.get("remittance_schedule", ""),
                    "is_active": agency.get("active", True),
                    "rate_tiers": [
                        {"key": "standard", "label": "Standard weekly", "amount": agency.get("default_weekly_rate", "110.00"), "basis": "week"},
                        {"key": "daily", "label": "Per day (4Cs)", "amount": "22.00", "basis": "day"},
                        {"key": "august", "label": "August (partial month)", "amount": "88.00", "basis": "month"},
                    ],
                },
            )
            for unit_name in agency.get("units", []):
                unit = PortalUnit.objects.filter(name=unit_name).first()
                if unit:
                    obj.units.add(unit)


def unit_delete_blockers(unit):
    blockers = []
    n_families = unit.families.count()
    if n_families:
        blockers.append(f"{n_families} families")
    n_programs = unit.programs.count()
    if n_programs:
        blockers.append(f"{n_programs} programs")
    n_staff = unit.staff_accounts.count()
    if n_staff:
        blockers.append(f"{n_staff} staff logins")
    return blockers


def delete_unit(unit_pk):
    unit = PortalUnit.objects.filter(pk=unit_pk).first()
    if not unit:
        raise ValueError("Unit not found.")
    blockers = unit_delete_blockers(unit)
    if blockers:
        raise ValueError(
            "Cannot delete this unit — it still has "
            + ", ".join(blockers)
            + ". Deactivate the unit instead, or remove/move that data first."
        )
    unit.delete()
    return True


def get_units_admin():
    ensure_admin_config_seeded()
    rows = []
    for unit in PortalUnit.objects.order_by("name"):
        enrolled = unit.families.filter(children__is_active=True).distinct().count()
        blockers = unit_delete_blockers(unit)
        rows.append(
            {
                "pk": unit.pk,
                "slug": unit.slug,
                "name": unit.name,
                "program_type": unit.program_type or "after_school",
                "active": unit.is_active,
                "address": unit.address,
                "city": unit.city,
                "capacity": unit.capacity or max(enrolled, 1),
                "enrolled": enrolled,
                "manager": unit.manager_name,
                "phone": unit.phone,
                "can_delete": not blockers,
                "delete_blockers": blockers,
            }
        )
    return rows


def save_unit(data, unit_pk=None):
    name = (data.get("name") or "").strip()
    if not name:
        raise ValueError("Unit name is required.")
    slug = data.get("slug") or _slug_unique(name, PortalUnit)
    defaults = {
        "name": name,
        "program_type": data.get("program_type", "after_school"),
        "address": data.get("address", ""),
        "city": data.get("city", ""),
        "phone": data.get("phone", ""),
        "manager_name": data.get("manager", ""),
        "capacity": int(data.get("capacity") or 0),
        "is_active": data.get("is_active", True) if unit_pk else True,
    }
    if unit_pk:
        unit = PortalUnit.objects.filter(pk=unit_pk).first()
        if not unit:
            raise ValueError("Unit not found.")
        for k, v in defaults.items():
            setattr(unit, k, v)
        unit.save()
        return unit
    return PortalUnit.objects.create(slug=slug, **defaults)


def set_unit_active(unit_pk, active):
    unit = PortalUnit.objects.filter(pk=unit_pk).first()
    if not unit:
        raise ValueError("Unit not found.")
    unit.is_active = active
    unit.save(update_fields=["is_active"])
    return unit


def get_programs_admin():
    ensure_admin_config_seeded()
    grouped = {}
    for program in PortalProgram.objects.select_related("unit").order_by("name", "unit__name"):
        key = program.name
        if key not in grouped:
            demo = next((p for p in PROGRAMS if p["name"] == program.name), {})
            grouped[key] = {
                "pk": program.pk,
                "name": program.name,
                "type": (program.program_type or "after_school").replace("_", " ").title(),
                "start_date": program.start_date.isoformat() if program.start_date else demo.get("start_date", ""),
                "end_date": program.end_date.isoformat() if program.end_date else demo.get("end_date", ""),
                "units": [],
                "unit_pks": [],
                "enrolled_count": 0,
                "status": program.status_label or demo.get("status", "Active"),
                "program_ids": [],
            }
        grouped[key]["units"].append(program.unit.name)
        grouped[key]["unit_pks"].append(program.unit.pk)
        grouped[key]["program_ids"].append(program.pk)
        grouped[key]["enrolled_count"] += program.unit.families.filter(children__is_active=True).count()
    if not grouped:
        return [
            {
                "pk": p.get("id"),
                "name": p["name"],
                "type": p.get("type", ""),
                "start_date": p.get("start_date", ""),
                "end_date": p.get("end_date", ""),
                "units": p.get("units", []),
                "unit_pks": [],
                "enrolled_count": p.get("enrolled_count", 0),
                "status": p.get("status", ""),
                "program_ids": [],
            }
            for p in PROGRAMS
        ]
    return list(grouped.values())


def save_program(data, program_name=None):
    from django.utils.dateparse import parse_date, parse_time

    name = (data.get("name") or program_name or "").strip()
    if not name:
        raise ValueError("Program name is required.")
    unit_slugs = data.get("unit_slugs") or []
    if not unit_slugs:
        raise ValueError("Select at least one unit.")
    start_time = parse_time(data.get("start_time") or "15:00") or parse_time("15:00")
    end_time = parse_time(data.get("end_time") or "18:00") or parse_time("18:00")
    start_date = parse_date(data.get("start_date") or "")
    end_date = parse_date(data.get("end_date") or "")
    program_type = data.get("program_type", "after_school")
    status_label = data.get("status_label", "Active")
    created = []
    for slug in unit_slugs:
        unit = PortalUnit.objects.filter(slug=slug).first()
        if not unit:
            continue
        program, _ = PortalProgram.objects.update_or_create(
            unit=unit,
            name=name,
            defaults={
                "start_time": start_time,
                "end_time": end_time,
                "is_active": status_label.lower() not in ("closed", "ended"),
                "program_type": program_type,
                "start_date": start_date,
                "end_date": end_date,
                "reg_open": parse_date(data.get("reg_open") or ""),
                "reg_close": parse_date(data.get("reg_close") or ""),
                "age_min": data.get("age_min", ""),
                "age_max": data.get("age_max", ""),
                "capacity": int(data.get("capacity") or 0),
                "description": data.get("description", ""),
                "status_label": status_label,
            },
        )
        created.append(program)
    if not created:
        raise ValueError("No valid units selected.")
    return created[0]


def delete_program(program_ids):
    ids = program_ids or []
    PortalProgram.objects.filter(pk__in=ids).delete()


def get_agencies_admin():
    ensure_admin_config_seeded()
    rows = []
    for agency in PortalAgency.objects.prefetch_related("units").order_by("name"):
        children = PortalAgencyProfile.objects.filter(agency=agency).count()
        rows.append(
            {
                "pk": agency.pk,
                "slug": agency.slug,
                "name": agency.name,
                "contact_name": agency.contact_name,
                "contact_email": agency.contact_email,
                "contact_phone": agency.contact_phone,
                "contract_start": agency.contract_start.isoformat() if agency.contract_start else "",
                "contract_end": agency.contract_end.isoformat() if agency.contract_end else "",
                "default_weekly_rate": f"{agency.default_weekly_rate:.2f}",
                "children_enrolled": children,
                "units": [u.name for u in agency.units.all()],
                "unit_pks": [u.pk for u in agency.units.all()],
                "remittance_schedule": agency.remittance_schedule,
                "rate_tiers": agency.rate_tiers or [],
                "active": agency.is_active,
            }
        )
    return rows or [
        {**a, "pk": None, "slug": a.get("slug", ""), "unit_pks": [], "rate_tiers": []} for a in ADMIN_AGENCIES
    ]


def get_agency_child_rates():
    rows = []
    for profile in PortalAgencyProfile.objects.select_related("child", "family", "unit", "agency").order_by("unit__name"):
        rows.append(
            {
                "pk": profile.pk,
                "child": profile.child.name,
                "family": profile.family.name,
                "unit": profile.unit.name,
                "agency_rate": f"{profile.weekly_agency_rate:.2f}",
                "copay": f"{profile.weekly_copay:.2f}",
                "auth_number": profile.auth_number,
                "use_variable_rates": profile.use_variable_rates,
                "rate_tier_key": profile.rate_tier_key,
                "daily_copay_rates": profile.daily_copay_rates or {},
            }
        )
    return rows


def save_agency(data, agency_pk=None):
    from django.utils.dateparse import parse_date

    name = (data.get("name") or "").strip()
    if not name:
        raise ValueError("Agency name is required.")
    rate_tiers = []
    tier_labels = data.getlist("tier_label") if hasattr(data, "getlist") else data.get("tier_labels", [])
    tier_amounts = data.getlist("tier_amount") if hasattr(data, "getlist") else data.get("tier_amounts", [])
    tier_bases = data.getlist("tier_basis") if hasattr(data, "getlist") else data.get("tier_bases", [])
    for i, label in enumerate(tier_labels):
        if not label:
            continue
        rate_tiers.append(
            {
                "key": slugify(label) or f"tier-{i}",
                "label": label,
                "amount": tier_amounts[i] if i < len(tier_amounts) else "0",
                "basis": tier_bases[i] if i < len(tier_bases) else "week",
            }
        )
    if not rate_tiers:
        default_rate = data.get("default_weekly_rate", "110.00")
        rate_tiers = [
            {"key": "standard", "label": "Standard weekly", "amount": default_rate, "basis": "week"},
            {"key": "daily", "label": "Per day", "amount": str(_parse_decimal(default_rate) / 5), "basis": "day"},
        ]
    defaults = {
        "name": name,
        "contact_name": data.get("contact_name", ""),
        "contact_email": data.get("contact_email", ""),
        "contact_phone": data.get("contact_phone", ""),
        "contract_start": parse_date(data.get("contract_start") or ""),
        "contract_end": parse_date(data.get("contract_end") or ""),
        "default_weekly_rate": _parse_decimal(data.get("default_weekly_rate", "0")),
        "remittance_schedule": data.get("remittance_schedule", "Monthly (1st business day)"),
        "rate_tiers": rate_tiers,
        "is_active": True,
    }
    unit_ids = data.getlist("unit_ids") if hasattr(data, "getlist") else data.get("unit_ids", [])
    if agency_pk:
        agency = PortalAgency.objects.filter(pk=agency_pk).first()
        if not agency:
            raise ValueError("Agency not found.")
        for k, v in defaults.items():
            setattr(agency, k, v)
        agency.save()
    else:
        agency = PortalAgency.objects.create(slug=_slug_unique(name, PortalAgency), **defaults)
    agency.units.set(PortalUnit.objects.filter(pk__in=unit_ids))
    return agency


def get_fee_rules_admin():
    ensure_admin_config_seeded()
    return list(PortalFeeRule.objects.order_by("name").values(
        "pk", "key", "name", "amount", "display", "frequency", "period", "notes"
    )) or FEE_RULES


def save_fee_rule(fee_pk, data):
    rule = PortalFeeRule.objects.filter(pk=fee_pk).first()
    if not rule:
        raise ValueError("Fee rule not found.")
    rule.name = data.get("name", rule.name)
    amount = (data.get("amount") or "").strip()
    display = (data.get("display") or "").strip()
    if amount:
        rule.amount = amount
        if not display or display.startswith("$"):
            display = f"${amount}" if not amount.startswith("$") else amount
    if display:
        rule.display = display
    rule.frequency = data.get("frequency", rule.frequency)
    rule.period = data.get("period", rule.period)
    rule.notes = data.get("notes", rule.notes)
    rule.save()
    return rule


def get_payment_plans_admin():
    ensure_admin_config_seeded()
    return list(PortalPaymentPlan.objects.order_by("name").values("pk", "name", "interval", "is_active"))


def save_payment_plan(data, plan_pk=None):
    name = (data.get("name") or "").strip()
    if not name:
        raise ValueError("Plan name is required.")
    if plan_pk:
        plan = PortalPaymentPlan.objects.filter(pk=plan_pk).first()
        if not plan:
            raise ValueError("Plan not found.")
        plan.name = name
        plan.interval = data.get("interval", plan.interval)
        plan.is_active = data.get("is_active", "1") == "1"
        plan.save()
        return plan
    return PortalPaymentPlan.objects.create(name=name, interval=data.get("interval", ""), is_active=True)


def delete_payment_plan(plan_pk):
    PortalPaymentPlan.objects.filter(pk=plan_pk).delete()


def get_processing_fees_admin():
    ensure_admin_config_seeded()
    return list(PortalProcessingFee.objects.order_by("name").values("pk", "name", "percent", "flat_amount", "is_active"))


def save_processing_fee(data, fee_pk=None):
    name = (data.get("name") or "").strip()
    if not name:
        raise ValueError("Fee name is required.")
    defaults = {
        "name": name,
        "percent": _parse_decimal(data.get("percent", "0")),
        "flat_amount": _parse_decimal(data.get("flat_amount", "0")),
        "is_active": data.get("is_active", "1") == "1",
    }
    if fee_pk:
        fee = PortalProcessingFee.objects.filter(pk=fee_pk).first()
        if not fee:
            raise ValueError("Processing fee not found.")
        for k, v in defaults.items():
            setattr(fee, k, v)
        fee.save()
        return fee
    return PortalProcessingFee.objects.create(**defaults)


def delete_processing_fee(fee_pk):
    PortalProcessingFee.objects.filter(pk=fee_pk).delete()


def get_tax_settings_admin():
    ensure_admin_config_seeded()
    setting = PortalTaxStatementSetting.objects.first()
    if not setting:
        setting = PortalTaxStatementSetting.objects.create()
    staff_options = list(
        PortalStaffAccount.objects.filter(is_active=True).select_related("user").order_by("display_name")
    )
    return setting, staff_options


def save_tax_settings(data):
    setting, _ = get_tax_settings_admin()
    setting.require_zero_balance = data.get("require_zero_balance") == "on"
    setting.parents_enabled = data.get("parents_enabled") == "on"
    staff_ids = data.getlist("staff_can_view") if hasattr(data, "getlist") else data.get("staff_can_view", [])
    setting.staff_can_view = [int(x) for x in staff_ids if str(x).isdigit()]
    setting.save()
    return setting


def get_scholarships_admin():
    ensure_admin_config_seeded()
    funds = list(PortalScholarshipFund.objects.filter(is_active=True).values("pk", "name", "description"))
    assignments = []
    for row in PortalScholarshipAssignment.objects.select_related("child", "child__family", "fund", "child__family__unit"):
        discount = row.full_rate - row.parent_amount
        assignments.append(
            {
                "pk": row.pk,
                "child": row.child.name,
                "family": row.child.family.name,
                "family_slug": row.child.family.slug,
                "unit": row.child.family.unit.name,
                "fund": row.fund.name,
                "fund_pk": row.fund.pk,
                "full_rate": f"{row.full_rate:.2f}",
                "parent_amount": f"{row.parent_amount:.2f}",
                "discount": f"{discount:.2f}",
                "start": row.start_date.isoformat() if row.start_date else "",
                "end": row.end_date.isoformat() if row.end_date else "",
                "status": row.status,
            }
        )
    child_options = [
        {"pk": c.pk, "name": c.name, "family": c.family.name}
        for c in PortalChild.objects.filter(is_active=True).select_related("family").order_by("family__name", "name")
    ]
    return funds, assignments, child_options


def save_scholarship_assignment(data, assignment_pk=None):
    from django.utils.dateparse import parse_date

    child = PortalChild.objects.filter(pk=data.get("child_id")).first()
    fund = PortalScholarshipFund.objects.filter(pk=data.get("fund_id")).first()
    if not child or not fund:
        raise ValueError("Select a child and scholarship fund.")
    full_rate = _parse_decimal(data.get("full_rate", "0"))
    parent_amount = _parse_decimal(data.get("parent_amount", "0"))
    defaults = {
        "child": child,
        "fund": fund,
        "full_rate": full_rate,
        "parent_amount": parent_amount,
        "start_date": parse_date(data.get("start_date") or ""),
        "end_date": parse_date(data.get("end_date") or ""),
        "status": data.get("status", "Active"),
    }
    if assignment_pk:
        row = PortalScholarshipAssignment.objects.filter(pk=assignment_pk).first()
        if not row:
            raise ValueError("Assignment not found.")
        for k, v in defaults.items():
            setattr(row, k, v)
        row.save()
        return row
    return PortalScholarshipAssignment.objects.create(**defaults)


def get_checkin_settings_admin():
    ensure_admin_config_seeded()
    return list(PortalCheckInSetting.objects.order_by("label").values("pk", "key", "label", "description", "enabled"))


def save_checkin_settings(data):
    for setting in PortalCheckInSetting.objects.all():
        setting.enabled = data.get(f"enabled_{setting.key}") == "on"
        setting.save()


def get_staff_roles_admin():
    ensure_admin_config_seeded()
    return list(PortalStaffRole.objects.order_by("name").values_list("name", flat=True))


def save_custom_role(name):
    name = (name or "").strip()
    if not name:
        raise ValueError("Role name is required.")
    role, created = PortalStaffRole.objects.get_or_create(name=name, defaults={"is_system": False})
    PortalBillingDefaultRule.objects.get_or_create(
        role_name=name,
        defaults={
            "can_add_charge": True,
            "can_delete_charge": False,
            "can_add_credit": False,
            "can_edit_family_plans": False,
            "is_custom": True,
        },
    )
    return role, created


def get_default_billing_rules():
    ensure_admin_config_seeded()
    return list(PortalBillingDefaultRule.objects.order_by("role_name"))


def save_default_billing_rule(data):
    role_name = (data.get("role_name") or "").strip()
    rule = PortalBillingDefaultRule.objects.filter(role_name=role_name).first()
    if not rule:
        raise ValueError("Role not found.")
    rule.can_add_charge = data.get("can_add_charge") == "on"
    rule.can_delete_charge = data.get("can_delete_charge") == "on"
    rule.can_add_credit = data.get("can_add_credit") == "on"
    rule.can_edit_family_plans = data.get("can_edit_family_plans") == "on"
    rule.save()
    return rule


def waive_absence_charge(family_slug, child_name, week_label, charge_description, amount):
    PortalWaivedAbsenceCharge.objects.get_or_create(
        family_slug=family_slug,
        child_name=child_name,
        week_label=week_label,
        charge_description=charge_description,
        defaults={"amount": _parse_decimal(amount)},
    )


def get_absence_charge_alerts():
    from .demo_data import ABSENCE_CHARGE_ALERTS

    waived = {
        (w.family_slug, w.child_name, w.week_label, w.charge_description)
        for w in PortalWaivedAbsenceCharge.objects.all()
    }
    data = {**ABSENCE_CHARGE_ALERTS, "families": []}
    for row in ABSENCE_CHARGE_ALERTS.get("families", []):
        charges = []
        for charge in row.get("charges_to_review", []):
            key = (row["slug"], row["child"], row["week_label"], charge["description"])
            if key not in waived:
                charges.append(charge)
        if charges:
            data["families"].append({**row, "charges_to_review": charges})
    return data


def get_org_policies_admin():
    return list(PortalOrgPolicy.objects.filter(is_active=True).order_by("-created_at"))


def create_org_policy(title, body, notify_families=True):
    policy = PortalOrgPolicy.objects.create(title=title.strip(), body=body.strip())
    if notify_families:
        now = timezone.now()
        for child in PortalChild.objects.filter(is_active=True).select_related("family"):
            PortalPolicySignatureRequest.objects.get_or_create(
                family=child.family,
                child=child,
                policy=policy,
                defaults={"status": PortalPolicySignatureRequest.STATUS_PENDING, "notified_at": now},
            )
    return policy


def get_charge_types_admin():
    return BILLING_CHARGE_TYPES
