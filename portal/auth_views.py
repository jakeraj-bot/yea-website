from django.contrib import messages
from django.contrib.auth import get_user_model, login, logout
from django.contrib.auth.forms import AuthenticationForm
from django.db import transaction
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.text import slugify
from django.views.decorators.http import require_GET, require_http_methods

from .attendance_service import get_unit
from .forms import ParentSignupForm
from .models import PortalFamily, PortalParentAccount, PortalUnit
from .parent_auth import get_parent_account, portal_preview_mode
from enrollment.portal_integration import family_display_label, link_applications_by_email


@require_http_methods(["GET", "POST"])
def parent_login(request):
    if portal_preview_mode():
        messages.info(request, "Design preview mode — parent login is not required.")
        return redirect("portal_parent_page", page="dashboard")

    if request.user.is_authenticated and get_parent_account(request.user):
        return redirect(_login_redirect(request))

    form = AuthenticationForm(request, data=request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.get_user()
        account = get_parent_account(user)
        if not account:
            messages.error(
                request,
                "That login exists but is not linked to a parent portal family yet. "
                "Create a parent account or contact YEA staff.",
            )
        else:
            login(request, user)
            messages.success(request, f"Welcome back, {family_display_label(account.family)} family.")
            return redirect(_login_redirect(request))

    return render(
        request,
        "portal/login.html",
        {
            "form": form,
            "page_title": "Parent login",
            "portal_area": "public",
        },
    )


@require_http_methods(["GET", "POST"])
def parent_signup(request):
    if portal_preview_mode():
        messages.info(request, "Design preview mode — sign up is not required.")
        return redirect("portal_parent_page", page="dashboard")

    if request.user.is_authenticated and get_parent_account(request.user):
        return redirect("portal_parent_page", page="dashboard")

    form = ParentSignupForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        unit = get_unit()
        if not unit:
            unit = PortalUnit.objects.filter(is_active=True).first()
        if not unit:
            messages.error(request, "Portal is not set up yet. Ask YEA staff to run: python manage.py seed_portal")
            return render(
                request,
                "portal/signup.html",
                {"form": form, "page_title": "Create parent account", "portal_area": "public"},
            )

        family_name = form.cleaned_data["family_name"].strip()
        base_slug = slugify(family_name) or "family"
        slug = base_slug
        suffix = 2
        while PortalFamily.objects.filter(unit=unit, slug=slug).exists():
            slug = f"{base_slug}-{suffix}"
            suffix += 1

        with transaction.atomic():
            family = PortalFamily.objects.create(
                unit=unit,
                slug=slug,
                name=family_name,
                primary_contact=form.cleaned_data["your_name"].strip(),
                balance=0,
                billing_type="Private pay",
                status="Active",
            )
            user = get_user_model().objects.create_user(
                username=form.cleaned_data["username"].strip(),
                email=form.cleaned_data["email"].strip(),
                password=form.cleaned_data["password1"],
                first_name=form.cleaned_data["your_name"].strip(),
            )
            PortalParentAccount.objects.create(user=user, family=family)
            link_applications_by_email(family, form.cleaned_data["email"].strip())
            login(request, user)

        messages.success(
            request,
            f"Account created for the {family_name} family. You can update your profile and billing anytime.",
        )
        return redirect("portal_parent_page", page="dashboard")

    return render(
        request,
        "portal/signup.html",
        {
            "form": form,
            "page_title": "Create parent account",
            "portal_area": "public",
        },
    )


@require_http_methods(["GET", "POST"])
def staff_login(request):
    from .staff_auth import get_staff_account

    if portal_preview_mode():
        messages.info(request, "Design preview mode — staff login is not required.")
        return redirect("portal_staff_page", page="dashboard")

    if request.user.is_authenticated and get_staff_account(request.user):
        return redirect(_staff_login_redirect(request))

    form = AuthenticationForm(request, data=request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.get_user()
        account = get_staff_account(user)
        if not account:
            messages.error(
                request,
                "That login is not linked to a staff portal account. Contact your portal admin.",
            )
        else:
            login(request, user)
            messages.success(request, f"Welcome back, {account.display_name}.")
            return redirect(_staff_login_redirect(request))

    return render(
        request,
        "portal/staff_login.html",
        {
            "form": form,
            "page_title": "Staff login",
            "portal_area": "public",
        },
    )


@require_http_methods(["GET", "POST"])
def admin_login(request):
    from .staff_auth import get_staff_account, is_portal_admin

    if portal_preview_mode():
        messages.info(request, "Design preview mode — admin login is not required.")
        return redirect("portal_admin_page", page="dashboard")

    if request.user.is_authenticated and is_portal_admin(request.user):
        return redirect(_admin_login_redirect(request))

    form = AuthenticationForm(request, data=request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.get_user()
        account = get_staff_account(user)
        if not account or not is_portal_admin(user):
            messages.error(
                request,
                "That login is not linked to a portal admin account. Contact your organization administrator.",
            )
        else:
            login(request, user)
            messages.success(request, f"Welcome back, {account.display_name}.")
            return redirect(_admin_login_redirect(request))

    return render(
        request,
        "portal/admin_login.html",
        {
            "form": form,
            "page_title": "Portal admin login",
            "portal_area": "public",
        },
    )


@require_GET
def admin_logout(request):
    logout(request)
    messages.success(request, "You have been signed out.")
    return redirect("portal_home")


def _admin_login_redirect(request):
    next_url = request.GET.get("next") or request.POST.get("next")
    if next_url and next_url.startswith("/portal/admin"):
        return next_url
    return reverse("portal_admin_page", kwargs={"page": "dashboard"})


@require_GET
def staff_logout(request):
    logout(request)
    messages.success(request, "You have been signed out.")
    return redirect("portal_home")


def _staff_login_redirect(request):
    next_url = request.GET.get("next") or request.POST.get("next")
    if next_url and next_url.startswith("/portal/staff"):
        return next_url
    return reverse("portal_staff_page", kwargs={"page": "dashboard"})


@require_GET
def parent_logout(request):
    logout(request)
    messages.success(request, "You have been signed out.")
    return redirect("portal_home")


def _login_redirect(request):
    next_url = request.GET.get("next") or request.POST.get("next")
    if next_url and (next_url.startswith("/portal/") or next_url.startswith("/apply/")):
        return next_url
    return reverse("portal_parent_page", kwargs={"page": "dashboard"})
