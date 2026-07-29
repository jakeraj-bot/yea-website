"""Live data and admin actions for the organization admin portal."""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db.models import Count, Sum
from django.utils import timezone

from enrollment.models import EnrollmentApplication

from .demo_data import ADMIN_AGENCIES, ADMIN_ALERTS, PROGRAMS, UNITS
from .models import (
    PortalAgencyProfile,
    PortalChild,
    PortalFamily,
    PortalProfileChangeRequest,
    PortalProgram,
    PortalStaffAccount,
    PortalUnit,
)


def _demo_unit(slug):
    return next((u for u in UNITS if u["slug"] == slug), {})


def get_admin_dashboard_live():
    enrolled = PortalChild.objects.filter(is_active=True).count()
    families = PortalFamily.objects.count()
    open_apps = EnrollmentApplication.objects.exclude(status__in=("enrolled", "declined")).count()
    overdue_qs = PortalFamily.objects.filter(balance__gt=0)
    overdue_total = overdue_qs.aggregate(total=Sum("balance"))["total"] or Decimal("0")
    staff_count = PortalStaffAccount.objects.filter(is_active=True).count()
    signed_apps = EnrollmentApplication.objects.filter(status="enrolled").count()
    total_apps = max(EnrollmentApplication.objects.count(), 1)
    policy_pct = min(100, int(signed_apps / total_apps * 100)) if total_apps else 0
    active_programs = PortalProgram.objects.filter(is_active=True).count()
    agency_children = PortalAgencyProfile.objects.count()
    return {
        "total_enrolled": enrolled,
        "total_families": families,
        "open_applications": open_apps,
        "overdue_families": overdue_qs.count(),
        "overdue_amount": f"{overdue_total:.2f}",
        "policy_completion_pct": policy_pct,
        "staff_count": staff_count,
        "active_programs": active_programs,
        "agency_children": agency_children,
    }


def get_enrollment_by_unit_live():
    rows = []
    for unit in PortalUnit.objects.order_by("name"):
        demo = _demo_unit(unit.slug)
        enrolled = PortalChild.objects.filter(family__unit=unit, is_active=True).count()
        capacity = demo.get("capacity", max(enrolled, 1))
        programs = PortalProgram.objects.filter(unit=unit, is_active=True).count()
        open_apps = EnrollmentApplication.objects.filter(
            portal_family__unit=unit,
        ).exclude(status__in=("enrolled", "declined")).count()
        rows.append(
            {
                "unit": unit.name,
                "slug": unit.slug,
                "enrolled": enrolled,
                "capacity": capacity,
                "programs": programs or demo.get("programs", 1),
                "open_apps": open_apps,
            }
        )
    if not rows:
        return []
    return rows


def get_units_live():
    rows = []
    for unit in PortalUnit.objects.order_by("name"):
        demo = _demo_unit(unit.slug)
        enrolled = PortalChild.objects.filter(family__unit=unit, is_active=True).count()
        rows.append(
            {
                "slug": unit.slug,
                "name": unit.name,
                "active": unit.is_active,
                "program_type": demo.get("program_type", "after_school"),
                "address": demo.get("address", ""),
                "city": demo.get("city", ""),
                "capacity": demo.get("capacity", enrolled or 50),
                "enrolled": enrolled,
                "manager": demo.get("manager", ""),
                "phone": demo.get("phone", ""),
                "pk": unit.pk,
            }
        )
    return rows or list(UNITS)


def get_programs_live():
    rows = []
    for program in PortalProgram.objects.select_related("unit").order_by("unit__name", "name"):
        demo = next((p for p in PROGRAMS if p.get("name") == program.name), {})
        rows.append(
            {
                "name": program.name,
                "unit": program.unit.name,
                "unit_slug": program.unit.slug,
                "season": demo.get("season", "2026–27"),
                "schedule": demo.get("schedule", f"{program.start_time:%I:%M %p} – {program.end_time:%I:%M %p}"),
                "capacity": demo.get("capacity", "—"),
                "enrolled": PortalChild.objects.filter(family__unit=program.unit, is_active=True).count(),
                "active": program.is_active,
                "pk": program.pk,
            }
        )
    return rows or list(PROGRAMS)


def get_staff_users_live():
    rows = []
    for account in PortalStaffAccount.objects.select_related("user", "unit").prefetch_related("accessible_units").order_by("display_name"):
        user = account.user
        if account.all_units_access or account.role == "Portal admin":
            units_label = "All units"
        else:
            extra = list(account.accessible_units.values_list("name", flat=True))
            names = extra or [account.unit.name]
            units_label = ", ".join(dict.fromkeys(names))
        rows.append(
            {
                "id": account.pk,
                "user_id": user.pk,
                "name": account.display_name or user.get_full_name() or user.username,
                "email": user.email,
                "role": account.role,
                "units": units_label,
                "status": "Active" if account.is_active else "Inactive",
                "last_login": _format_login(user),
                "can_add_charge": account.can_add_charge,
                "can_delete_charge": account.can_delete_charge,
                "can_add_credit": account.can_add_credit,
                "can_edit_family_plans": account.can_edit_family_plans,
                "all_units_access": account.all_units_access,
                "unit_slug": account.unit.slug,
            }
        )
    return rows


def get_member_families_live():
    rows = []
    for family in PortalFamily.objects.select_related("unit").prefetch_related("children").order_by("unit__name", "name"):
        child_names = [c.name for c in family.children.all() if c.is_active]
        rows.append(
            {
                "name": family.name,
                "slug": family.slug,
                "unit": family.unit.name,
                "primary_contact": family.primary_contact or "—",
                "children": child_names,
                "balance": f"{family.balance:.2f}",
                "billing_type": family.billing_type or "Private pay",
                "status": family.status,
            }
        )
    return rows


def get_agencies_admin_live():
    profiles = PortalAgencyProfile.objects.select_related("child", "family", "unit").order_by("unit__name")
    if not profiles.exists():
        return ADMIN_AGENCIES
    rows = []
    for profile in profiles:
        rows.append(
            {
                "name": "Passaic County 4Cs",
                "unit": profile.unit.name,
                "children_enrolled": 1,
                "contract_rate": f"${profile.weekly_agency_rate:.2f}/wk",
                "status": "Active",
                "contact": profile.auth_number,
            }
        )
    by_unit = {}
    for row in rows:
        key = row["unit"]
        if key not in by_unit:
            by_unit[key] = {**row, "children_enrolled": 0}
        by_unit[key]["children_enrolled"] += 1
    return list(by_unit.values()) or ADMIN_AGENCIES


def get_admin_alerts_live():
    alerts = list(ADMIN_ALERTS)
    pending_profiles = PortalProfileChangeRequest.objects.filter(
        status=PortalProfileChangeRequest.STATUS_PENDING
    ).count()
    if pending_profiles:
        alerts.insert(
            0,
            {
                "text": f"{pending_profiles} parent profile change(s) awaiting review",
                "link_name": "portal_admin_page",
                "link_arg": "dashboard",
            },
        )
    overdue = PortalFamily.objects.filter(balance__gt=0).count()
    if overdue:
        alerts.insert(
            0,
            {
                "text": f"{overdue} families with overdue balances",
                "link_name": "portal_admin_page",
                "link_arg": "member-billing",
            },
        )
    return alerts


def get_pending_profile_changes_admin():
    return list(
        PortalProfileChangeRequest.objects.filter(status=PortalProfileChangeRequest.STATUS_PENDING)
        .select_related("account__family", "account__user")
        .order_by("-submitted_at")[:20]
    )


def save_billing_permissions(staff_id, can_add_charge, can_delete_charge, can_add_credit, can_edit_family_plans=False, charge_type_permissions=None):
    account = PortalStaffAccount.objects.filter(pk=staff_id).first()
    if not account:
        raise ValueError("Staff account not found.")
    account.can_add_charge = can_add_charge
    account.can_delete_charge = can_delete_charge
    account.can_add_credit = can_add_credit
    account.can_edit_family_plans = can_edit_family_plans
    if charge_type_permissions is not None:
        account.charge_type_permissions = charge_type_permissions
    account.save(
        update_fields=[
            "can_add_charge",
            "can_delete_charge",
            "can_add_credit",
            "can_edit_family_plans",
            "charge_type_permissions",
        ]
    )
    return account


def invite_staff_user(name, email, role, unit_slug=None, unit_slugs=None, all_units_access=False):
    from .admin_config import ensure_admin_config_seeded
    from .models import PortalBillingDefaultRule

    ensure_admin_config_seeded()
    User = get_user_model()
    username = email.split("@")[0].lower().replace(".", "")
    base = username
    counter = 1
    while User.objects.filter(username=username).exists():
        username = f"{base}{counter}"
        counter += 1
    if all_units_access or role == "Portal admin":
        all_units_access = True
        unit = PortalUnit.objects.filter(is_active=True).order_by("name").first()
    else:
        slugs = unit_slugs or ([unit_slug] if unit_slug else [])
        unit = PortalUnit.objects.filter(slug__in=slugs).first() if slugs else PortalUnit.objects.filter(is_active=True).first()
    if not unit:
        raise ValueError("No active unit configured.")
    user, created = User.objects.get_or_create(
        username=username,
        defaults={"email": email, "first_name": name.split()[0] if name else "", "last_name": " ".join(name.split()[1:]) if name else ""},
    )
    if not created and not user.email:
        user.email = email
        user.save(update_fields=["email"])
    temp_password = "ChangeMe2026!"
    if created:
        user.set_password(temp_password)
        user.save()
    default_rule = PortalBillingDefaultRule.objects.filter(role_name=role).first()
    account, _ = PortalStaffAccount.objects.update_or_create(
        user=user,
        defaults={
            "unit": unit,
            "display_name": name.strip() or username,
            "role": role or "Unit staff",
            "all_units_access": all_units_access,
            "is_active": True,
            "can_add_charge": default_rule.can_add_charge if default_rule else True,
            "can_delete_charge": default_rule.can_delete_charge if default_rule else False,
            "can_add_credit": default_rule.can_add_credit if default_rule else False,
            "can_edit_family_plans": default_rule.can_edit_family_plans if default_rule else False,
        },
    )
    if all_units_access:
        account.accessible_units.clear()
    elif unit_slugs:
        account.accessible_units.set(PortalUnit.objects.filter(slug__in=unit_slugs))
    elif unit_slug:
        account.accessible_units.set(PortalUnit.objects.filter(slug=unit_slug))
    return account, created, temp_password if created else None


def update_staff_user(staff_id, data):
    account = PortalStaffAccount.objects.filter(pk=staff_id).select_related("user").first()
    if not account:
        raise ValueError("Staff account not found.")
    name = (data.get("name") or "").strip()
    if name:
        account.display_name = name
    email = (data.get("email") or "").strip()
    if email:
        account.user.email = email
        account.user.save(update_fields=["email"])
    role = data.get("role")
    if role:
        account.role = role
    all_units = data.get("all_units_access") == "on" or role == "Portal admin"
    account.all_units_access = all_units
    if data.get("is_active") is not None:
        account.is_active = data.get("is_active") == "1"
    unit_slug = data.get("unit_slug")
    unit_slugs = data.getlist("unit_slugs") if hasattr(data, "getlist") else data.get("unit_slugs", [])
    if all_units:
        account.accessible_units.clear()
    elif unit_slugs:
        units = PortalUnit.objects.filter(slug__in=unit_slugs)
        if units.exists():
            account.unit = units.first()
            account.accessible_units.set(units)
    elif unit_slug:
        unit = PortalUnit.objects.filter(slug=unit_slug).first()
        if unit:
            account.unit = unit
            account.accessible_units.set([unit])
    account.save()
    return account


def approve_profile_change(change_id, reviewer="Admin", approve=True, notes=""):
    change = PortalProfileChangeRequest.objects.filter(pk=change_id).select_related("account__family").first()
    if not change:
        raise ValueError("Change request not found.")
    if approve:
        family = change.account.family
        data = change.changes
        if data.get("primary_name"):
            family.primary_contact = data["primary_name"]
            family.save(update_fields=["primary_contact"])
        change.status = PortalProfileChangeRequest.STATUS_APPROVED
    else:
        change.status = PortalProfileChangeRequest.STATUS_REJECTED
    change.reviewed_at = timezone.now()
    change.reviewed_by = reviewer
    change.notes = notes
    change.save()
    return change


def _format_login(user):
    if not user.last_login:
        return "Never"
    return timezone.localtime(user.last_login).strftime("%b %d, %Y")
