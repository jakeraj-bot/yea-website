from functools import wraps

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect

from .models import PortalParentAccount

FAMILY_SLUG_TO_PREVIEW_KEY = {
    "jacobs": "private-pay",
    "martinez": "4cs",
    "williams": "scholarship",
}

PREVIEW_KEY_TO_FAMILY_SLUG = {v: k for k, v in FAMILY_SLUG_TO_PREVIEW_KEY.items()}


def portal_preview_mode():
    return getattr(settings, "PORTAL_PREVIEW_MODE", False)


def get_parent_account(user):
    if not user.is_authenticated:
        return None
    return (
        PortalParentAccount.objects.filter(user=user)
        .select_related("family", "family__unit", "user")
        .first()
    )


def parent_login_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if portal_preview_mode():
            return view_func(request, *args, **kwargs)
        if request.user.is_authenticated and get_parent_account(request.user):
            return view_func(request, *args, **kwargs)
        login_url = settings.PORTAL_PARENT_LOGIN_URL
        return redirect(f"{login_url}?next={request.get_full_path()}")

    return wrapper


def parent_login_required_post(view_func):
    decorated = login_required(login_url=settings.PORTAL_PARENT_LOGIN_URL)(view_func)

    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if portal_preview_mode():
            return view_func(request, *args, **kwargs)
        return decorated(request, *args, **kwargs)

    return wrapper


def resolve_parent_family(request):
    if portal_preview_mode():
        return None
    account = get_parent_account(request.user)
    if account:
        return account.family
    return None


def resolve_preview_key(request):
    if portal_preview_mode():
        key = request.GET.get("pay", "private-pay")
        from .demo_data import PARENT_PAYMENT_PREVIEWS

        if key not in PARENT_PAYMENT_PREVIEWS:
            key = "private-pay"
        return key
    account = get_parent_account(request.user)
    if account and not portal_preview_mode():
        return account.family.slug
    key = request.GET.get("pay")
    if key and key in PREVIEW_KEY_TO_FAMILY_SLUG:
        return key
    if account:
        return FAMILY_SLUG_TO_PREVIEW_KEY.get(account.family.slug, "private-pay")
    return "private-pay"
