from functools import wraps

from django.conf import settings
from django.shortcuts import redirect

from .attendance_service import get_unit
from .demo_data import ADMIN_BILLING_PERMISSIONS, STAFF_BILLING_PERMISSIONS
from .models import PortalStaffAccount, PortalUnit
from .parent_auth import portal_preview_mode

PORTAL_AUTH_SESSION_KEY = "portal_auth_area"


def set_portal_auth(request, area):
    request.session[PORTAL_AUTH_SESSION_KEY] = area


def get_portal_auth(request):
    return request.session.get(PORTAL_AUTH_SESSION_KEY)


def clear_portal_auth(request):
    request.session.pop(PORTAL_AUTH_SESSION_KEY, None)


def is_admin_portal_authenticated(request):
    return (
        request.user.is_authenticated
        and is_portal_admin(request.user)
        and get_portal_auth(request) == "admin"
    )


def is_staff_portal_authenticated(request):
    return (
        request.user.is_authenticated
        and get_staff_account(request.user)
        and get_portal_auth(request) == "staff"
    )


def can_open_staff_portal(user):
    return bool(get_staff_account(user))


def can_open_admin_portal(user):
    return is_portal_admin(user)


def activate_portal_area(request, area):
    """Flip the session to staff or admin without signing out."""
    if area == "staff" and can_open_staff_portal(request.user):
        set_portal_auth(request, "staff")
        return True
    if area == "admin" and can_open_admin_portal(request.user):
        set_portal_auth(request, "admin")
        return True
    return False


def portal_switch_flags(user):
    if portal_preview_mode():
        return {"can_open_staff_portal": True, "can_open_admin_portal": True}
    return {
        "can_open_staff_portal": can_open_staff_portal(user),
        "can_open_admin_portal": can_open_admin_portal(user),
    }


def get_staff_account(user):
    if not user.is_authenticated:
        return None
    return (
        PortalStaffAccount.objects.filter(user=user, is_active=True)
        .select_related("unit", "user")
        .first()
    )


def is_portal_admin(user):
    account = get_staff_account(user)
    if not account:
        return False
    return account.role == "Portal admin" or account.all_units_access


def staff_accessible_units(user):
    account = get_staff_account(user)
    if not account:
        if portal_preview_mode():
            return PortalUnit.objects.filter(is_active=True).order_by("name")
        return PortalUnit.objects.none()
    if account.all_units_access or account.role == "Portal admin":
        return PortalUnit.objects.filter(is_active=True).order_by("name")
    extra = account.accessible_units.filter(is_active=True)
    if extra.exists():
        unit_ids = list(extra.values_list("pk", flat=True))
        if account.unit_id and account.unit_id not in unit_ids:
            unit_ids.append(account.unit_id)
        return PortalUnit.objects.filter(pk__in=unit_ids, is_active=True).order_by("name")
    return PortalUnit.objects.filter(pk=account.unit_id, is_active=True)


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
    return None


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


def application_permissions_for_staff(account=None, portal_area="staff"):
    if portal_area == "admin":
        return {
            "can_approve_applications": True,
            "can_approve_waitlist": True,
        }
    if not account:
        return {
            "can_approve_applications": False,
            "can_approve_waitlist": False,
        }
    return {
        "can_approve_applications": bool(account.can_approve_applications),
        "can_approve_waitlist": bool(account.can_approve_waitlist),
    }


def can_approve_enrollment_application(account, app, portal_area="staff"):
    perms = application_permissions_for_staff(account, portal_area)
    status = getattr(app, "status", "") or ""
    if status == "waitlist":
        return perms["can_approve_waitlist"]
    return perms["can_approve_applications"]


def staff_login_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if portal_preview_mode():
            return view_func(request, *args, **kwargs)
        if is_staff_portal_authenticated(request):
            return view_func(request, *args, **kwargs)
        if activate_portal_area(request, "staff"):
            return view_func(request, *args, **kwargs)
        login_url = getattr(settings, "PORTAL_STAFF_LOGIN_URL", "/portal/staff/login/")
        return redirect(f"{login_url}?next={request.get_full_path()}")

    return wrapper


def staff_login_required_post(view_func):
    login_url = getattr(settings, "PORTAL_STAFF_LOGIN_URL", "/portal/staff/login/")

    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if portal_preview_mode():
            return view_func(request, *args, **kwargs)
        if is_staff_portal_authenticated(request):
            return view_func(request, *args, **kwargs)
        if activate_portal_area(request, "staff"):
            return view_func(request, *args, **kwargs)
        return redirect(f"{login_url}?next={request.get_full_path()}")

    return wrapper


def admin_login_required(view_func):
    login_url = getattr(settings, "PORTAL_ADMIN_LOGIN_URL", "/portal/admin/login/")

    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if portal_preview_mode():
            return view_func(request, *args, **kwargs)
        if is_admin_portal_authenticated(request):
            return view_func(request, *args, **kwargs)
        if activate_portal_area(request, "admin"):
            return view_func(request, *args, **kwargs)
        return redirect(f"{login_url}?next={request.get_full_path()}")

    return wrapper


def admin_login_required_post(view_func):
    login_url = getattr(settings, "PORTAL_ADMIN_LOGIN_URL", "/portal/admin/login/")

    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if portal_preview_mode():
            return view_func(request, *args, **kwargs)
        if is_admin_portal_authenticated(request):
            return view_func(request, *args, **kwargs)
        if activate_portal_area(request, "admin"):
            return view_func(request, *args, **kwargs)
        return redirect(f"{login_url}?next={request.get_full_path()}")

    return wrapper
