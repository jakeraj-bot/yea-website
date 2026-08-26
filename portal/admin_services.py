"""Live data and admin actions for the organization admin portal."""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Count, Sum
from django.utils import timezone

from enrollment.models import EnrollmentApplication

from .demo_data import ADMIN_AGENCIES, ADMIN_ALERTS, PROGRAMS, UNITS
from .models import (
    PortalAgencyProfile,
    PortalChild,
    PortalFamily,
    PortalParentAccount,
    PortalProfileChangeRequest,
    PortalProgram,
    PortalStaffAccount,
    PortalUnit,
)


def _demo_unit(slug):
    return next((u for u in UNITS if u["slug"] == slug), {})


def get_admin_dashboard_live():
    enrolled = PortalChild.objects.filter(is_active=True).exclude(
        family__unit__slug__in=("main-location", "main_location")
    ).count()
    families = PortalFamily.objects.exclude(unit__slug__in=("main-location", "main_location")).count()
    open_apps = EnrollmentApplication.objects.filter(
        status__in=("under_review", "pending_documents", "waitlist")
    ).count()
    overdue_qs = PortalFamily.objects.filter(balance__gt=0)
    overdue_total = overdue_qs.aggregate(total=Sum("balance"))["total"] or Decimal("0")
    staff_count = PortalStaffAccount.objects.filter(is_active=True).count()
    signed_apps = EnrollmentApplication.objects.filter(status="enrolled").count()
    total_apps = max(EnrollmentApplication.objects.count(), 1)
    policy_pct = min(100, int(signed_apps / total_apps * 100)) if total_apps else 0
    active_programs = PortalProgram.objects.filter(is_active=True).count()
    from .member_admin import pending_4cs_children

    agency_children = PortalAgencyProfile.objects.count()
    pending_4cs = pending_4cs_children()
    approved_4cs = PortalChild.objects.filter(is_active=True, family__billing_type__iexact="4Cs").exclude(
        family__unit__slug__in=("main-location", "main_location")
    ).count()
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
        "pending_4cs_count": len(pending_4cs),
        "approved_4cs_count": approved_4cs,
        "pending_4cs": [
            {
                "child": child.name,
                "family": child.family.name,
                "unit": child.family.unit.name,
                "family_slug": child.family.slug,
                "family_id": child.family_id,
            }
            for child in pending_4cs
        ],
    }


def get_enrollment_by_unit_live():
    from .member_admin import is_placeholder_unit

    rows = []
    for unit in PortalUnit.objects.order_by("name"):
        if is_placeholder_unit(unit):
            continue
        enrolled = PortalChild.objects.filter(family__unit=unit, is_active=True).count()
        capacity = unit.capacity or enrolled
        programs = PortalProgram.objects.filter(unit=unit, is_active=True).count()
        open_apps = EnrollmentApplication.objects.filter(
            portal_family__unit=unit,
            status__in=("under_review", "pending_documents", "waitlist"),
        ).count()
        approved = EnrollmentApplication.objects.filter(
            portal_family__unit=unit,
            status__in=("approved", "enrolled"),
        ).count()
        rows.append(
            {
                "unit": unit.name,
                "slug": unit.slug,
                "enrolled": enrolled,
                "approved_applications": approved,
                "capacity": capacity,
                "programs": programs,
                "open_apps": open_apps,
            }
        )
    return rows


def get_units_live():
    rows = []
    for unit in PortalUnit.objects.order_by("name"):
        enrolled = PortalChild.objects.filter(family__unit=unit, is_active=True).count()
        rows.append(
            {
                "slug": unit.slug,
                "name": unit.name,
                "active": unit.is_active,
                "program_type": unit.program_type or "after_school",
                "address": unit.address or "",
                "city": unit.city or "",
                "capacity": unit.capacity or enrolled,
                "enrolled": enrolled,
                "manager": unit.manager_name or "",
                "phone": unit.phone or "",
                "pk": unit.pk,
            }
        )
    return rows


def get_programs_live():
    rows = []
    for program in PortalProgram.objects.select_related("unit").order_by("unit__name", "name"):
        rows.append(
            {
                "name": program.name,
                "unit": program.unit.name,
                "unit_slug": program.unit.slug,
                "season": program.season or "",
                "schedule": f"{program.start_time:%I:%M %p} – {program.end_time:%I:%M %p}",
                "capacity": program.capacity if program.capacity else "—",
                "enrolled": PortalChild.objects.filter(family__unit=program.unit, is_active=True).count(),
                "active": program.is_active,
                "pk": program.pk,
            }
        )
    return rows


def get_staff_users_live():
    from .usernames import display_username

    rows = []
    for account in PortalStaffAccount.objects.select_related("user", "unit").prefetch_related("accessible_units").order_by("display_name"):
        user = account.user
        if account.all_units_access or account.role == "Portal admin":
            units_label = "All units"
        else:
            extra = list(account.accessible_units.values_list("name", flat=True))
            names = extra or [account.unit.name]
            units_label = ", ".join(dict.fromkeys(names))
        login_name = display_username(user.username)
        lowered = user.username.lower()
        if lowered.startswith("admin:") or account.role == "Portal admin":
            login_portal = "admin"
            login_path = "/portal/admin/login/"
        else:
            login_portal = "staff"
            login_path = "/portal/staff/login/"
        rows.append(
            {
                "id": account.pk,
                "user_id": user.pk,
                "username": login_name,
                "login_portal": login_portal,
                "login_path": login_path,
                "name": account.display_name or user.get_full_name() or login_name,
                "email": user.email,
                "role": account.role,
                "units": units_label,
                "status": "Active" if account.is_active else "Inactive",
                "last_login": _format_login(user),
                "can_add_charge": account.can_add_charge,
                "can_delete_charge": account.can_delete_charge,
                "can_add_credit": account.can_add_credit,
                "can_edit_family_plans": account.can_edit_family_plans,
                "can_approve_applications": account.can_approve_applications,
                "can_approve_waitlist": account.can_approve_waitlist,
                "all_units_access": account.all_units_access,
                "unit_slug": account.unit.slug,
            }
        )
    return rows


def get_member_families_live():
    from enrollment.application_review import repair_family_units_from_applications

    repair_family_units_from_applications()
    rows = []
    for family in PortalFamily.objects.select_related("unit").prefetch_related("children").order_by("unit__name", "name"):
        child_names = [c.name for c in family.children.all() if c.is_active]
        rows.append(
            {
                "id": family.pk,
                "name": family.name,
                "slug": family.slug,
                "unit": family.unit.name,
                "primary_contact": family.primary_contact or "—",
                "children": child_names,
                "balance": f"{family.balance:.2f}",
                "billing_type": family.billing_type or "Private pay",
                "status": "Suspended" if family.is_suspended else family.status,
            }
        )
    return rows


def get_member_policy_summaries_live():
    from .parent_services import get_parent_policy_data_live

    summaries = []
    for family in PortalFamily.objects.select_related("unit").order_by("unit__name", "name"):
        data = get_parent_policy_data_live(family)
        if not data:
            continue
        child_summary = ", ".join(
            f"{child['child_name'].split()[0]} {child['signed_count']}/{child['total_count']}"
            for child in data["children"]
        )
        summaries.append(
            {
                "slug": family.slug,
                "family_name": data["family_name"],
                "primary_contact": family.primary_contact or family.name,
                "children": [child["child_name"] for child in data["children"]],
                "child_count": data["child_count"],
                "unit": data["unit"],
                "signed_count": data["signed_count"],
                "total_count": data["total_count"],
                "policies_per_child": data["policies_per_child"],
                "complete": data["complete"],
                "program_year": data["program_year"],
                "child_summary": child_summary,
            }
        )
    return summaries


def get_parent_accounts_live():
    from .usernames import display_username

    rows = []
    for account in PortalParentAccount.objects.select_related("user", "family", "family__unit").order_by(
        "family__unit__name", "family__name"
    ):
        user = account.user
        rows.append(
            {
                "id": account.pk,
                "user_id": user.pk,
                "family_slug": account.family.slug,
                "family_name": account.family.name,
                "unit": account.family.unit.name if account.family.unit_id else "—",
                "username": display_username(user.username),
                "email": user.email,
                "primary_contact": account.family.primary_contact or "—",
                "last_login": _format_login(user),
                "is_active": user.is_active,
            }
        )
    return rows


@transaction.atomic
def delete_parent_login(parent_account_id, *, delete_family=False):
    account = (
        PortalParentAccount.objects.filter(pk=parent_account_id)
        .select_related("user", "family")
        .first()
    )
    if not account:
        raise ValueError("Parent account not found.")
    family = account.family
    user = account.user
    label = f"{account.login_username} ({family.name})"
    account.delete()
    user.delete()
    if delete_family:
        family.delete()
    return label


@transaction.atomic
def delete_staff_login(staff_account_id, *, current_user_id=None):
    account = PortalStaffAccount.objects.filter(pk=staff_account_id).select_related("user").first()
    if not account:
        raise ValueError("Staff account not found.")
    if current_user_id and account.user_id == current_user_id:
        raise ValueError("You cannot delete your own account while signed in.")
    if account.role == "Portal admin":
        remaining = (
            PortalStaffAccount.objects.filter(role="Portal admin", is_active=True)
            .exclude(pk=account.pk)
            .count()
        )
        if remaining == 0:
            raise ValueError("Cannot delete the last active portal admin account.")
    label = account.display_name or account.login_username
    user = account.user
    account.delete()
    user.delete()
    return label


def get_admin_families_live():
    from enrollment.application_review import repair_family_units_from_applications
    from enrollment.models import EnrollmentApplication
    from enrollment.portal_integration import family_display_label

    repair_family_units_from_applications()
    rows = []
    for family in PortalFamily.objects.select_related("unit").prefetch_related("children").order_by("unit__name", "name"):
        enrolled = [child.name for child in family.children.filter(is_active=True)]
        enrolled_lower = {name.lower() for name in enrolled}
        pending_children = []
        for app in EnrollmentApplication.objects.filter(portal_family=family).order_by("-submitted_at"):
            child_name = f"{app.student_first_name} {app.student_last_name}".strip()
            if child_name.lower() not in enrolled_lower and app.status not in {"declined", "enrolled"}:
                pending_children.append(child_name)
        rows.append(
            {
                "id": family.pk,
                "slug": family.slug,
                "name": family_display_label(family),
                "unit": family.unit.name,
                "unit_slug": family.unit.slug,
                "primary_contact": family.primary_contact or "—",
                "children": enrolled + pending_children,
                "school": ", ".join(
                    sorted({child.school for child in family.children.filter(is_active=True) if child.school})
                )
                or "—",
                "balance": format(family.balance, ".2f"),
                "program": family.program_label or "—",
                "billing_type": family.billing_type or "Private pay",
                "status": "Suspended" if family.is_suspended else family.status,
                "is_suspended": family.is_suspended,
                "has_parent_login": PortalParentAccount.objects.filter(family=family).exists(),
                "has_application": family.enrollment_applications.exists(),
            }
        )
    return rows


def get_agencies_admin_live():
    profiles = PortalAgencyProfile.objects.select_related("child", "family", "unit").order_by("unit__name")
    if not profiles.exists():
        return []
    rows = []
    for profile in profiles:
        rows.append(
            {
                "name": profile.agency_name or "Agency",
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
    return list(by_unit.values())


def get_admin_alerts_live():
    from .live_services import count_messages_unread_live

    alerts = []
    open_apps = EnrollmentApplication.objects.filter(
        status__in=("under_review", "pending_documents", "waitlist")
    ).count()
    if open_apps:
        alerts.append(
            {
                "text": f"{open_apps} application(s) awaiting review across all units",
                "link_name": "portal_admin_page",
                "link_arg": "applications",
            }
        )
    overdue_qs = PortalFamily.objects.filter(balance__gt=0)
    overdue = overdue_qs.count()
    if overdue:
        total = overdue_qs.aggregate(total=Sum("balance"))["total"] or Decimal("0")
        alerts.append(
            {
                "text": f"{overdue} families with overdue balances (${total:.2f} total)",
                "link_name": "portal_admin_page",
                "link_arg": "member-billing",
            }
        )
    pending_profiles = PortalProfileChangeRequest.objects.filter(
        status=PortalProfileChangeRequest.STATUS_PENDING
    ).count()
    if pending_profiles:
        alerts.append(
            {
                "text": f"{pending_profiles} parent profile change(s) awaiting review",
                "link_name": "portal_admin_page",
                "link_arg": "dashboard",
            }
        )
    unread = count_messages_unread_live(for_admin=True)
    if unread:
        alerts.append(
            {
                "text": f"{unread} unread staff message(s)",
                "link_name": "portal_admin_page",
                "link_arg": "messages",
            }
        )
    from .member_admin import pending_4cs_children

    pending_4cs = pending_4cs_children()
    if pending_4cs:
        alerts.append(
            {
                "text": f"{len(pending_4cs)} approved 4Cs child(ren) waiting for authorization / copay info",
                "link_name": "portal_admin_page",
                "link_arg": "agencies",
            }
        )
    return alerts


def get_pending_profile_changes_admin():
    return list(
        PortalProfileChangeRequest.objects.filter(status=PortalProfileChangeRequest.STATUS_PENDING)
        .select_related("account__family", "account__user")
        .order_by("-submitted_at")[:20]
    )


def save_billing_permissions(
    staff_id,
    can_add_charge,
    can_delete_charge,
    can_add_credit,
    can_edit_family_plans=False,
    charge_type_permissions=None,
    can_approve_applications=False,
    can_approve_waitlist=False,
):
    account = PortalStaffAccount.objects.filter(pk=staff_id).first()
    if not account:
        raise ValueError("Staff account not found.")
    account.can_add_charge = can_add_charge
    account.can_delete_charge = can_delete_charge
    account.can_add_credit = can_add_credit
    account.can_edit_family_plans = can_edit_family_plans
    account.can_approve_applications = can_approve_applications
    account.can_approve_waitlist = can_approve_waitlist
    if charge_type_permissions is not None:
        account.charge_type_permissions = charge_type_permissions
    account.save(
        update_fields=[
            "can_add_charge",
            "can_delete_charge",
            "can_add_credit",
            "can_edit_family_plans",
            "can_approve_applications",
            "can_approve_waitlist",
            "charge_type_permissions",
        ]
    )
    return account


def invite_staff_user(name, email, role, unit_slug=None, unit_slugs=None, all_units_access=False, password=None):
    import secrets

    from .admin_config import ensure_admin_config_seeded
    from .models import PortalBillingDefaultRule
    from .usernames import allocate_portal_username, display_username

    ensure_admin_config_seeded()
    User = get_user_model()
    base_login = email.split("@")[0].lower().replace(".", "")
    portal_type = "admin" if role == "Portal admin" else "staff"
    stored_username = allocate_portal_username(portal_type, base_login)
    login_name = display_username(stored_username)
    if all_units_access or role == "Portal admin":
        all_units_access = True
        unit = PortalUnit.objects.filter(is_active=True).order_by("name").first()
    else:
        slugs = unit_slugs or ([unit_slug] if unit_slug else [])
        unit = PortalUnit.objects.filter(slug__in=slugs).first() if slugs else PortalUnit.objects.filter(is_active=True).first()
    if not unit:
        raise ValueError("No active unit configured.")
    user, created = User.objects.get_or_create(
        username=stored_username,
        defaults={"email": email, "first_name": name.split()[0] if name else "", "last_name": " ".join(name.split()[1:]) if name else ""},
    )
    if not created and not user.email:
        user.email = email
        user.save(update_fields=["email"])
    temp_password = (password or "").strip() or secrets.token_urlsafe(10)
    if created:
        user.set_password(temp_password)
        user.save()
    elif password:
        user.set_password(temp_password)
        user.save()
    default_rule = PortalBillingDefaultRule.objects.filter(role_name=role).first()
    account, _ = PortalStaffAccount.objects.update_or_create(
        user=user,
        defaults={
            "unit": unit,
            "display_name": name.strip() or login_name,
            "role": role or "Unit staff",
            "all_units_access": all_units_access,
            "is_active": True,
            "can_add_charge": default_rule.can_add_charge if default_rule else True,
            "can_delete_charge": default_rule.can_delete_charge if default_rule else False,
            "can_add_credit": default_rule.can_add_credit if default_rule else False,
            "can_edit_family_plans": default_rule.can_edit_family_plans if default_rule else False,
            "can_approve_applications": default_rule.can_approve_applications if default_rule else False,
            "can_approve_waitlist": default_rule.can_approve_waitlist if default_rule else False,
        },
    )
    if all_units_access:
        account.accessible_units.clear()
    elif unit_slugs:
        account.accessible_units.set(PortalUnit.objects.filter(slug__in=unit_slugs))
    elif unit_slug:
        account.accessible_units.set(PortalUnit.objects.filter(slug=unit_slug))
    return account, created, temp_password if created or password else None, login_name


def invite_admin_user(name, username, email="", password=None):
    import secrets

    from .admin_config import ensure_admin_config_seeded
    from .models import PortalBillingDefaultRule
    from .usernames import display_username, portal_username, portal_username_taken

    ensure_admin_config_seeded()
    User = get_user_model()
    login_name = (username or "").strip()
    if not login_name:
        raise ValueError("Username is required.")
    if portal_username_taken("admin", login_name):
        raise ValueError("That admin username is already taken.")
    stored_username = portal_username("admin", login_name)
    unit = PortalUnit.objects.filter(is_active=True).order_by("name").first()
    if not unit:
        raise ValueError("No active unit configured.")
    email = (email or "").strip() or f"{login_name}@yeanj.org"
    user, created = User.objects.get_or_create(
        username=stored_username,
        defaults={
            "email": email,
            "first_name": name.split()[0] if name else "",
            "last_name": " ".join(name.split()[1:]) if name else "",
        },
    )
    if not created and email and user.email != email:
        user.email = email
        user.save(update_fields=["email"])
    temp_password = (password or "").strip() or secrets.token_urlsafe(10)
    if len(temp_password) < 8:
        raise ValueError("Password must be at least 8 characters.")
    user.set_password(temp_password)
    user.save()
    default_rule = PortalBillingDefaultRule.objects.filter(role_name="Portal admin").first()
    account, _ = PortalStaffAccount.objects.update_or_create(
        user=user,
        defaults={
            "unit": unit,
            "display_name": name.strip() or login_name,
            "role": "Portal admin",
            "all_units_access": True,
            "is_active": True,
            "can_add_charge": default_rule.can_add_charge if default_rule else True,
            "can_delete_charge": default_rule.can_delete_charge if default_rule else True,
            "can_add_credit": default_rule.can_add_credit if default_rule else True,
            "can_edit_family_plans": default_rule.can_edit_family_plans if default_rule else True,
            "can_approve_applications": default_rule.can_approve_applications if default_rule else True,
            "can_approve_waitlist": default_rule.can_approve_waitlist if default_rule else True,
        },
    )
    account.accessible_units.clear()
    return account, created, temp_password, display_username(stored_username)


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
    if role == "Portal admin":
        from .usernames import allocate_portal_username, display_username, portal_username

        User = get_user_model()
        user = account.user
        lowered = user.username.lower()
        if lowered.startswith("staff:"):
            login_part = display_username(user.username)
            new_stored = portal_username("admin", login_part)
            if User.objects.filter(username__iexact=new_stored).exclude(pk=user.pk).exists():
                new_stored = allocate_portal_username("admin", login_part)
            user.username = new_stored
            user.save(update_fields=["username"])
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
    new_password = (data.get("new_password") or "").strip()
    if new_password:
        if len(new_password) < 8:
            raise ValueError("Password must be at least 8 characters.")
        account.user.set_password(new_password)
        account.user.save()
    account.save()
    return account, new_password if new_password else None


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
