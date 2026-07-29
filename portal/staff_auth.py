from functools import wraps

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect

from .attendance_service import get_unit
from .demo_data import ADMIN_BILLING_PERMISSIONS, STAFF_BILLING_PERMISSIONS
from .models import PortalStaffAccount, PortalUnit
from .parent_auth import portal_preview_mode


def get_staff_account(user):
    if not user.is_authenticated:
        return None
    return (
        PortalStaffAccount.objects.filter(user=user, is_active=True)
        .select_related("unit", "user")
        .first()
    )


def staff_accessible_units(user):
    account = get_staff_account(user)
    if not account:
        return PortalUnit.objects.filter(is_active=True).order_by("name")
    if account.all_units_access or account.role == "Portal admin":
        return PortalUnit.objects.filter(is_active=True).order_by("name")
    extra = account.accessible_units.filter(is_active=True)
    if extra.exists():
        return extra.order_by("name")
    if account.role == "Unit director":
        return PortalUnit.objects.filter(is_active=True).order_by("name")
    return PortalUnit.objects.filter(pk=account.unit_id)


def resolve_staff_unit(request):
    slug = request.session.get("staff_unit_slug")
    if slug:
        unit = PortalUnit.objects.filter(slug=slug, is_active=True).first()
        if unit and _can_access_unit(request.user, unit):
            return unit
    if portal_preview_mode():
        return get_unit()
    account = get_staff_account(request.user)
    if account:
        return account.unit
    return get_unit()


def _can_access_unit(user, unit):
    return staff_accessible_units(user).filter(pk=unit.pk).exists()


def billing_permissions_for_staff(account=None, portal_area="staff"):
    if portal_area == "admin":
        perms = dict(ADMIN_BILLING_PERMISSIONS)
        perms["can_edit_family_plans"] = True
        return perms
    if not account:
        return {**STAFF_BILLING_PERMISSIONS, "can_edit_family_plans": False}
    return {
        "can_add_charge": account.can_add_charge,
        "can_delete_charge": account.can_delete_charge,
        "can_add_credit": account.can_add_credit,
        "can_edit_family_plans": account.can_edit_family_plans,
        "role_label": account.role,
    }


def staff_login_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if portal_preview_mode():
            return view_func(request, *args, **kwargs)
        if request.user.is_authenticated and get_staff_account(request.user):
            return view_func(request, *args, **kwargs)
        login_url = getattr(settings, "PORTAL_STAFF_LOGIN_URL", "/portal/staff/login/")
        return redirect(f"{login_url}?next={request.get_full_path()}")

    return wrapper


def staff_login_required_post(view_func):
    login_url = getattr(settings, "PORTAL_STAFF_LOGIN_URL", "/portal/staff/login/")
    decorated = login_required(login_url=login_url)(view_func)

    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if portal_preview_mode():
            return view_func(request, *args, **kwargs)
        return decorated(request, *args, **kwargs)

    return wrapper
