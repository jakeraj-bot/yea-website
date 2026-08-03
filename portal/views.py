from django.conf import settings
from django.contrib import messages
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST, require_POST
from datetime import date

from .report_sheets import (
    daily_blank_context,
    parse_sheet_date,
    signout_blank_context,
    weekly_blank_context,
)

from .attendance_service import (
    attendance_redirect,
    build_roster,
    build_session_context,
    check_in_child,
    check_out_child,
    ensure_portal_seeded,
    families_for_staff,
    get_active_program,
    get_attendance_date,
    get_unit,
    mark_absent,
    parse_time_input,
    portal_is_live,
    undo_absent,
)
from .demo_data import (
    ADMIN_AGENCIES,
    ADMIN_ALERTS,
    ADMIN_COMMUNICATIONS,
    ADMIN_DASHBOARD,
    ADMIN_ENROLLMENT_BY_UNIT,
    ADMIN_REPORTS,
    AGENCY_BILLING,
    AGENCY_UNIT_DATA,
    ATTENDANCE_ROSTER,
    ATTENDANCE_SESSION,
    BILLING_CHARGE_TYPES,
    CHECKIN_MODES,
    build_preview_payment_receipt,
    calculate_card_processing_fee,
    enrich_receipt_for_print,
    count_unread_messages,
    count_unread_support_tickets,
    DASHBOARD_ALERTS,
    FAMILIES,
    FAMILIES_BILLING,
    FAMILY_DETAILS,
    ADMIN_MEMBER_FAMILIES,
    FEE_RULES,
    get_incident,
    get_incident_roster_children,
    get_incidents_by_child_for_family,
    get_incidents_for_child,
    get_incidents_for_family,
    get_message_thread,
    get_staff_compliance_by_unit,
    get_support_ticket,
    get_support_tickets,
    INCIDENTS,
    INCIDENT_SEVERITY_OPTIONS,
    INCIDENT_TYPES,
    build_lesson_plan_preview,
    LESSON_PLANNER_SAMPLE,
    LESSON_PLANNER_TOPICS,
    MESSAGE_CATEGORIES,
    MESSAGE_THREADS,
    MEDICAL_ALERT_TYPES,
    MEDICAL_REPORT_META,
    MEDICAL_REPORT_ROWS,
    NEWSLETTER_TEMPLATES,
    NEWSLETTERS,
    NJ_LICENSING_FORMS,
    PARENT_ANNOUNCEMENTS,
    PARENT_PAYMENT_PREVIEWS,
    PARENT_ACCOUNT,
    PARENT_DROP_IN,
    PARENT_RECEIPTS,
    POLICIES_PER_CHILD,
    PORTAL_STAFF_ROLES,
    PORTAL_STAFF_USERS,
    prepare_billing_preview,
    get_family_policies,
    get_member_policy_summaries,
    PROGRAM_ROSTER,
    PROGRAMS,
    SAMPLE_APPLICATION,
    SCHOLARSHIP_ASSIGNMENTS,
    SCHOLARSHIP_CHILD_OPTIONS,
    SCHOLARSHIP_FUNDS,
    STAFF_APPLICATION_DETAILS,
    STAFF_APPLICATIONS,
    STAFF_BILLING_PERMISSIONS,
    ADMIN_BILLING_PERMISSIONS,
    ABSENCE_CHARGE_ALERTS,
    STAFF_COMPLIANCE,
    STAFF_COMPLIANCE_CPR_REQUIRED_PER_UNIT,
    STAFF_PROGRAMS_SCHOOL_18,
    STAFF_REPORTS,
    STRIPE_PROCESSING_FEE,
    SUPPORT_TICKET_CATEGORIES,
    TAX_STATEMENT_ELIGIBILITY,
    TAX_STATEMENT_SETTINGS,
    UNITS,
)
from .live_services import (
    LIVE_FEATURE_LABELS,
    STILL_DEMO_LABELS,
    count_messages_unread_live,
    count_support_unread_live,
    family_meta_live,
    family_profile_live,
    get_announcements_live,
    get_incident_children_live,
    get_incident_live,
    get_incidents_by_child_for_family_live,
    get_incidents_for_child_live,
    get_incidents_for_family_live,
    get_incidents_live,
    get_message_thread_live,
    get_message_threads_live,
    get_newsletters_live,
    get_support_ticket_live,
    get_support_tickets_live,
)
from .parent_auth import (
    get_parent_account,
    parent_login_required,
    portal_preview_mode,
    resolve_preview_key,
)
from .staff_auth import admin_login_required, staff_login_required
from .parent_services import (
    build_parent_preview_live,
    get_account_live,
    get_billing_live,
    get_drop_in_live,
    get_parent_announcement_live,
    get_parent_avatar_context,
    get_parent_billing_for_request,
    get_parent_policy_data_live,
    get_pending_profile_changes,
    get_receipts_live,
    get_tax_eligibility_live,
    get_tax_statement_data,
    payment_to_receipt_dict,
    preview_key_for_family,
)
from enrollment.portal_integration import (
    application_list_item,
    application_to_portal_dict,
    applications_for_admin,
    applications_for_staff,
    get_application_by_reference,
    get_applications_for_family,
    staff_application_detail as application_detail_dict,
)
from .pickup_services import family_authorized_pickup, pickup_report_data, pickup_report_programs
from .models import PortalUnit
from .stripe_services import stripe_configured


def _portal_data_live():
    return portal_is_live() and ensure_portal_seeded()


def _staff_family_profile(family_slug):
    if _portal_data_live():
        live_profile = family_profile_live(family_slug)
        if live_profile:
            return live_profile
    profile = FAMILY_DETAILS.get(family_slug)
    if profile:
        return profile
    family = next((f for f in FAMILIES if f["slug"] == family_slug), None)
    if not family:
        return None
    return {
        "family_name": family["name"],
        "home_address": "—",
        "primary": {
            "name": family["primary_contact"],
            "relationship": "",
            "email": "",
            "phone": "",
            "phone_type": "",
        },
        "secondary": {"name": "", "relationship": "", "email": "", "phone": "", "phone_type": ""},
        "children": [
            {
                "name": c,
                "dob": "",
                "grade": "",
                "location": "School 18",
                "program": family["program"],
                "allergies": "",
                "medications": "",
            }
            for c in family["children"]
        ],
        "emergency_contacts": [],
    }


def _staff_family_context(family_slug, page_title, family_tab, **extra):
    profile = _staff_family_profile(family_slug)
    if not profile:
        return None
    if _portal_data_live():
        family_meta = family_meta_live(family_slug) or {}
    else:
        family_meta = next((f for f in FAMILIES if f["slug"] == family_slug), {})
    if _portal_data_live():
        family_incidents = get_incidents_for_family_live(family_slug)
    else:
        family_incidents = get_incidents_for_family(family_slug)
    return _staff_context(
        page_title,
        profile=profile,
        family_meta=family_meta,
        family_slug=family_slug,
        family_tab=family_tab,
        family_incident_count=len(family_incidents),
        staff_page_slug="families",
        **extra,
    )


def _finalize_admin_context(request, context):
    from .parent_auth import portal_preview_mode
    from .staff_auth import is_admin_portal_authenticated

    context["admin_authenticated"] = portal_preview_mode() or is_admin_portal_authenticated(request)
    return context


def _portal_back_fallback(area, pay_query=""):
    if area == "parent":
        return reverse("portal_parent_page", kwargs={"page": "dashboard"}) + pay_query
    if area == "staff":
        return reverse("portal_staff_page", kwargs={"page": "dashboard"})
    if area == "admin":
        return reverse("portal_admin_page", kwargs={"page": "dashboard"})
    return reverse("portal_home")


def _application_portal_urls(area, app_slug):
    if area == "admin":
        return {
            "list": reverse("portal_admin_page", kwargs={"page": "applications"}),
            "review": reverse("portal_admin_application_review", kwargs={"app_slug": app_slug}),
            "print": reverse("portal_admin_application_print", kwargs={"app_slug": app_slug}),
        }
    return {
        "list": reverse("portal_staff_page", kwargs={"page": "applications"}),
        "review": reverse("portal_staff_application_review", kwargs={"app_slug": app_slug}),
        "print": reverse("portal_staff_application_print", kwargs={"app_slug": app_slug}),
    }


def _portal_context(area, page_title, **extra):
    from .attendance_service import portal_is_live

    preview_mode = getattr(settings, "PORTAL_PREVIEW_MODE", False)
    staging_site = getattr(settings, "STAGING_SITE", False)
    live = portal_is_live() if area in ("admin", "staff") else _portal_data_live()
    context = {
        "portal_area": area,
        "page_title": page_title,
        "preview_mode": preview_mode,
        "staging_site": staging_site,
        "show_dev_hints": preview_mode and not staging_site,
        "portal_live": live,
        "live_feature_labels": LIVE_FEATURE_LABELS if live else [],
        "still_demo_labels": STILL_DEMO_LABELS if live else [],
        **extra,
    }
    if "portal_back_fallback" not in context:
        pay_query = context.get("parent_pay_query", "")
        context["portal_back_fallback"] = _portal_back_fallback(area, pay_query)
    return context


def _staff_unit(request=None):
    if request is not None:
        from .staff_auth import resolve_staff_unit

        return resolve_staff_unit(request)
    return get_unit() if _portal_data_live() else None


def _staff_context(page_title, request=None, **extra):
    unit = _staff_unit(request)
    staff_unit = unit.name if unit else "School 18"
    ctx = _portal_context("staff", page_title, staff_unit=staff_unit, **extra)
    if request is not None:
        from .staff_auth import billing_permissions_for_staff, get_staff_account, is_staff_portal_authenticated, staff_accessible_units

        account = get_staff_account(request.user)
        ctx["staff_account"] = account
        ctx["billing_permissions"] = billing_permissions_for_staff(account)
        ctx["staff_authenticated"] = is_staff_portal_authenticated(request) or portal_preview_mode()
        ctx["staff_units"] = list(staff_accessible_units(request.user)) if request.user.is_authenticated else []
        ctx["staff_unit_slug"] = unit.slug if unit else ""
    return ctx


def _parent_preview_key(request):
    return resolve_preview_key(request)


PREVIEW_FAMILY_SLUG = {
    "private-pay": "jacobs",
    "4cs": "martinez",
    "scholarship": "williams",
}


def _parent_live_mode(request):
    if portal_preview_mode() or not request.user.is_authenticated:
        return False
    if not portal_is_live():
        return False
    return bool(get_parent_account(request.user))


def _parent_policy_data(preview_key):
    slug = PREVIEW_FAMILY_SLUG.get(preview_key, "jacobs")
    return get_family_policies(slug)


def _parent_context(request, page_title, page_slug="", **extra):
    preview_key = _parent_preview_key(request)
    account = get_parent_account(request.user) if request.user.is_authenticated else None
    if _parent_live_mode(request) and account:
        preview = build_parent_preview_live(account.family, account)
        pay_query = ""
        account_data = get_account_live(account)
        receipts = get_receipts_live(account.family)
        policy_data = get_parent_policy_data_live(account.family)
        parent_announcement = get_parent_announcement_live(account.family)
        drop_in = get_drop_in_live(account)
        preview_key = preview_key_for_family(account.family)
        pending_profile_changes = get_pending_profile_changes(account)
    else:
        demo_key = preview_key if preview_key in PARENT_PAYMENT_PREVIEWS else "private-pay"
        preview = PARENT_PAYMENT_PREVIEWS[demo_key]
        pay_query = f"?pay={demo_key}"
        account_data = PARENT_ACCOUNT.get(demo_key, {})
        receipts = PARENT_RECEIPTS.get(demo_key, [])
        policy_data = _parent_policy_data(demo_key)
        parent_announcement = PARENT_ANNOUNCEMENTS.get(demo_key, {})
        drop_in = dict(PARENT_DROP_IN.get(demo_key, {}))
        drop_in.setdefault("offered", True)
        drop_in.setdefault("show_program_details", True)
        pending_profile_changes = []
    parent_avatar = get_parent_avatar_context(account, preview)
    from .staff_auth import get_portal_auth

    parent_signed_in = bool(account) and get_portal_auth(request) == "parent"
    return _portal_context(
        "parent",
        page_title,
        parent_preview_key=preview_key,
        parent_preview=preview,
        parent_page_slug=page_slug,
        parent_pay_query=pay_query,
        parent_announcement=parent_announcement,
        receipts=receipts,
        drop_in=drop_in,
        account=account_data,
        policy_data=policy_data,
        policies_per_child=POLICIES_PER_CHILD,
        parent_stripe_enabled=_parent_live_mode(request) and stripe_configured(),
        parent_authenticated=parent_signed_in or portal_preview_mode(),
        parent_avatar=parent_avatar,
        parent_can_manage_photo=bool(account) and not portal_preview_mode(),
        pending_profile_changes=pending_profile_changes,
        **extra,
    )


def _staff_attendance_context(request):
    unit = _staff_unit(request)
    program = get_active_program(unit)
    attendance_date = get_attendance_date(request)
    roster = build_roster(unit, program, attendance_date)
    return {
        "attendance": build_session_context(unit, program, attendance_date, roster),
        "roster": roster,
        "attendance_live": portal_is_live() and ensure_portal_seeded(),
        "attendance_needs_seed": portal_is_live() and not ensure_portal_seeded(),
        "checkin_modes": CHECKIN_MODES,
        "medical_alert_types": MEDICAL_ALERT_TYPES,
        "show_checkin_panel": request.GET.get("checkin") == "1" and request.GET.get("bulk") != "1",
        "show_bulk_checkin_panel": request.GET.get("checkin") == "1" and request.GET.get("bulk") == "1",
        "show_checkout_panel": request.GET.get("checkout") == "1" and request.GET.get("bulk") != "1",
        "show_bulk_checkout_panel": request.GET.get("checkout") == "1" and request.GET.get("bulk") == "1",
    }


def _attendance_program_or_redirect(request, attendance_date):
    unit = get_unit()
    program = get_active_program(unit)
    if not unit or not program:
        messages.error(request, "Portal members are not set up yet. Run: python manage.py seed_portal")
        return None, None, attendance_redirect(request, attendance_date)
    return unit, program, None


def _messages_context(area, page_title, request, **extra):
    thread_id = request.GET.get("thread")
    base = _staff_context(page_title, request=request) if area == "staff" else _portal_context("admin", page_title)
    base["portal_area"] = area
    staff_unit = None
    if area == "staff":
        from .staff_auth import resolve_staff_unit

        staff_unit = resolve_staff_unit(request)
    if portal_is_live():
        base.update(
            {
                "message_threads": get_message_threads_live(
                    unit=staff_unit,
                    for_admin=(area == "admin"),
                ),
                "active_thread": get_message_thread_live(
                    thread_id,
                    unit=staff_unit,
                    for_admin=(area == "admin"),
                ),
                "message_categories": MESSAGE_CATEGORIES,
                "messages_unread_count": count_messages_unread_live(
                    for_admin=(area == "admin"),
                    unit=staff_unit,
                ),
                "show_compose": request.GET.get("compose") == "1",
            }
        )
    else:
        base.update(
            {
                "message_threads": MESSAGE_THREADS,
                "active_thread": get_message_thread(thread_id),
                "message_categories": MESSAGE_CATEGORIES,
                "messages_unread_count": count_unread_messages(for_admin=(area == "admin")),
                "show_compose": request.GET.get("compose") == "1",
            }
        )
    base.update(extra)
    return base


def _support_context(area, page_title, request, preview_family=None, **extra):
    ticket_id = request.GET.get("ticket")
    if area == "parent":
        base = _parent_context(request, page_title, page_slug="support", **extra)
    elif area == "staff":
        base = _staff_context(page_title, **extra)
    else:
        base = _portal_context("admin", page_title, **extra)
    base["portal_area"] = area
    if portal_is_live():
        tickets = get_support_tickets_live(area, preview_family)
        active_ticket = get_support_ticket_live(ticket_id, area, preview_family)
        unread = count_support_unread_live(for_admin=(area == "admin"))
    else:
        tickets = get_support_tickets(area, preview_family)
        active_ticket = get_support_ticket(ticket_id, area, preview_family)
        unread = count_unread_support_tickets(for_admin=(area == "admin"))
    base.update(
        {
            "support_tickets": tickets,
            "active_ticket": active_ticket,
            "support_categories": SUPPORT_TICKET_CATEGORIES,
            "support_unread_count": unread,
            "show_new_ticket": request.GET.get("new") == "1",
        }
    )
    return base


@require_GET
def portal_home(request):
    from django.conf import settings

    if not getattr(settings, "PORTALS_PUBLIC", True):
        return render(request, "core/portals_unavailable.html")
    return render(request, "core/portals.html")


@require_GET
@parent_login_required
def parent_page(request, page):
    templates = {
        "dashboard": "portal/parent/dashboard.html",
        "profile": "portal/parent/profile.html",
        "applications": "portal/parent/applications.html",
        "application": "portal/parent/application_detail.html",
        "policies": "portal/parent/policies.html",
        "billing": "portal/parent/billing.html",
        "receipts": "portal/parent/receipts.html",
        "drop-in": "portal/parent/drop_in.html",
        "account": "portal/parent/account.html",
        "tax-statements": "portal/parent/tax_statements.html",
        "support": "portal/support/support.html",
    }
    template = templates.get(page)
    if not template:
        return render(request, "portal/404.html", status=404)

    context = _parent_context(request, page.replace("-", " ").title(), page_slug=page)
    if page == "billing":
        context["billing"] = context["parent_preview"]["billing"]
    if page == "profile":
        context["profile"] = context["parent_preview"]["profile"]
    if page == "dashboard":
        context["dashboard"] = context["parent_preview"]["dashboard"]
    if page == "applications":
        account = get_parent_account(request.user) if request.user.is_authenticated else None
        if account:
            live_apps = get_applications_for_family(account.family)
            context["parent_applications"] = [application_list_item(app) for app in live_apps]
        elif _portal_data_live() and not portal_preview_mode():
            context["parent_applications"] = []
        else:
            context["parent_applications"] = [
                {
                    "reference": "demo-jordan",
                    "child_name": "Jordan Jacobs",
                    "program": "After-school",
                    "location": "School 18",
                    "submitted": "Sep 8, 2026",
                    "status": "Under review",
                    "status_slug": "under-review",
                    "demo": True,
                },
                {
                    "reference": "demo-maya",
                    "child_name": "Maya Jacobs",
                    "program": "After-school",
                    "location": "School 18",
                    "submitted": "Sep 1, 2026",
                    "status": "Enrolled",
                    "status_slug": "enrolled",
                    "demo": True,
                },
            ]
    if page == "application":
        account = get_parent_account(request.user) if request.user.is_authenticated else None
        app_ref = request.GET.get("ref")
        application = None
        if account and app_ref:
            from enrollment.models import EnrollmentApplication

            app = EnrollmentApplication.objects.filter(
                portal_family=account.family,
                reference=app_ref,
            ).first()
            if app:
                application = application_to_portal_dict(app)
        if not application and portal_preview_mode():
            application = SAMPLE_APPLICATION
            application["status_slug"] = "under-review"
        if not application:
            return render(request, "portal/404.html", status=404)
        context["application"] = application
    if page == "policies":
        policy_data = context["policy_data"]
        context["policies_signed_count"] = policy_data["signed_count"]
        context["policies_total"] = policy_data["total_count"]
    if page == "tax-statements":
        account = get_parent_account(request.user) if request.user.is_authenticated else None
        context["tax_settings"] = TAX_STATEMENT_SETTINGS
        if _parent_live_mode(request) and account:
            context["tax_eligibility"] = get_tax_eligibility_live(account.family)
        else:
            preview_key = _parent_preview_key(request)
            context["tax_eligibility"] = TAX_STATEMENT_ELIGIBILITY.get(preview_key, {})
    if page == "receipts":
        preview_key = _parent_preview_key(request)
        account = get_parent_account(request.user) if request.user.is_authenticated else None
        if _parent_live_mode(request) and account:
            preview_key = preview_key_for_family(account.family)
        paid_receipts = [r for r in context.get("receipts", []) if r.get("reference")]
        context["receipt_previews"] = [enrich_receipt_for_print(r, preview_key) for r in paid_receipts[:2]]
    if page == "support":
        preview_key = _parent_preview_key(request)
        family_slug = PREVIEW_FAMILY_SLUG.get(preview_key, "jacobs")
        if _parent_live_mode(request):
            account = get_parent_account(request.user)
            if account:
                family_slug = account.family.slug
        context = _support_context("parent", "Support", request, preview_family=family_slug)
    return render(request, template, context)


@require_GET
@parent_login_required
def parent_payment(request):
    account = get_parent_account(request.user)
    preview_key = _parent_preview_key(request)
    if _parent_live_mode(request) and account:
        billing = get_parent_billing_for_request(account.family, preview_key)
        preview_key = preview_key_for_family(account.family)
    else:
        preview = PARENT_PAYMENT_PREVIEWS[preview_key]
        billing = preview["billing"]
    is_dropin = request.GET.get("source") == "dropin"
    if is_dropin:
        amount = request.GET.get("amount") or "35.00"
        program_label = request.GET.get("program_label") or "After-school drop-in"
        dropin_context = {
            "child": request.GET.get("child", ""),
            "program": program_label,
            "location": request.GET.get("location", "School 18"),
            "date": request.GET.get("date", ""),
            "fee": amount,
        }
        page_title = "Pay for drop-in"
    else:
        amount = request.GET.get("amount") or billing["running_balance"]
        dropin_context = None
        page_title = "Pay balance"
    payment_totals = calculate_card_processing_fee(amount)
    return render(
        request,
        "portal/parent/payment.html",
        _parent_context(
            request,
            page_title,
            page_slug="billing",
            billing=billing,
            payment_amount=amount,
            payment_totals=payment_totals,
            stripe_fee=STRIPE_PROCESSING_FEE,
            is_dropin_payment=is_dropin,
            dropin=dropin_context,
        ),
    )


@require_GET
@parent_login_required
def parent_payment_preview(request):
    account = get_parent_account(request.user)
    preview_key = _parent_preview_key(request)
    if _parent_live_mode(request) and account:
        billing = get_parent_billing_for_request(account.family, preview_key)
        preview_key = preview_key_for_family(account.family)
    else:
        billing = PARENT_PAYMENT_PREVIEWS[preview_key]["billing"]
    balance = float(billing["running_balance"])
    is_dropin = request.GET.get("source") == "dropin"
    amount_raw = request.GET.get("amount", billing["running_balance"])
    try:
        pay_amount = float(str(amount_raw).replace(",", ""))
    except (TypeError, ValueError):
        pay_amount = balance
    if pay_amount <= 0:
        pay_amount = balance if not is_dropin else float(request.GET.get("amount") or 35)
    credit_amount = 0.0 if is_dropin else max(0.0, round(pay_amount - balance, 2))
    payment_totals = calculate_card_processing_fee(str(pay_amount))
    method = request.GET.get("method", "Visa ending 4242")
    dropin_context = None
    if is_dropin:
        dropin_context = {
            "child": request.GET.get("child", ""),
            "program": request.GET.get("program_label") or request.GET.get("program", "After-school drop-in"),
            "location": request.GET.get("location", "School 18"),
            "date": request.GET.get("date", ""),
            "fee": f"{pay_amount:.2f}",
        }
    return render(
        request,
        "portal/parent/payment_preview.html",
        _parent_context(
            request,
            "Review drop-in payment" if is_dropin else "Review payment",
            page_slug="billing",
            billing=billing,
            payment_amount=f"{pay_amount:.2f}",
            credit_amount=f"{credit_amount:.2f}",
            payment_totals=payment_totals,
            stripe_fee=STRIPE_PROCESSING_FEE,
            payment_method=method,
            is_dropin_payment=is_dropin,
            dropin=dropin_context,
        ),
    )


@require_GET
@parent_login_required
def parent_payment_complete(request):
    preview_key = _parent_preview_key(request)
    amount_raw = request.GET.get("amount", "0")
    method = request.GET.get("method", "Visa ending 4242")
    try:
        pay_amount = float(str(amount_raw).replace(",", ""))
    except (TypeError, ValueError):
        pay_amount = 0.0
    receipt = build_preview_payment_receipt(preview_key, pay_amount, method_label=method)
    return render(
        request,
        "portal/parent/receipts_print.html",
        _parent_context(
            request,
            "Payment receipt",
            page_slug="receipts",
            print_receipts=[receipt],
            print_receipt_ref=receipt["receipt_no"],
            payment_just_completed=True,
        ),
    )


@require_GET
@parent_login_required
def parent_payment_success(request):
    session_id = request.GET.get("session_id")
    payment = None
    if session_id and stripe_configured():
        from .stripe_services import confirm_checkout_payment

        payment = confirm_checkout_payment(session_id)
    if not payment:
        messages.error(request, "We could not confirm your payment. Contact YEA if you were charged.")
        return redirect("portal_parent_page", page="billing")
    preview_key = _parent_preview_key(request)
    receipt = payment_to_receipt_dict(payment, preview_key)
    messages.success(request, f"Payment received — receipt {payment.receipt_no}.")
    return render(
        request,
        "portal/parent/receipts_print.html",
        _parent_context(
            request,
            "Payment receipt",
            page_slug="receipts",
            print_receipts=[receipt],
            print_receipt_ref=receipt["receipt_no"],
            payment_just_completed=True,
        ),
    )


@require_GET
@parent_login_required
def parent_application_print(request):
    account = get_parent_account(request.user) if request.user.is_authenticated else None
    app_ref = request.GET.get("ref")
    application = SAMPLE_APPLICATION
    if account and app_ref:
        from enrollment.models import EnrollmentApplication

        app = EnrollmentApplication.objects.filter(
            portal_family=account.family,
            reference=app_ref,
        ).first()
        if app:
            application = application_to_portal_dict(app)
    return render(
        request,
        "portal/parent/application_print.html",
        _parent_context(
            request,
            "Application — print",
            page_slug="application",
            application=application,
        ),
    )


@require_GET
@parent_login_required
def parent_policies_print(request):
    account = get_parent_account(request.user)
    if _parent_live_mode(request) and account:
        policy_data = get_parent_policy_data_live(account.family)
    else:
        preview_key = _parent_preview_key(request)
        policy_data = _parent_policy_data(preview_key)
    return render(
        request,
        "portal/parent/policies_print.html",
        _parent_context(
            request,
            "Policies — print",
            page_slug="policies",
            print_policy_data=policy_data,
        ),
    )


@require_GET
@parent_login_required
def parent_receipts_print(request):
    account = get_parent_account(request.user)
    preview_key = _parent_preview_key(request)
    ref = request.GET.get("ref", "")
    if _parent_live_mode(request) and account:
        preview_key = preview_key_for_family(account.family)
        receipts = get_receipts_live(account.family)
        payments = account.family.payments.filter(status="paid").order_by("-paid_at")
        if ref:
            payments = payments.filter(receipt_no=ref)
        print_receipts = [payment_to_receipt_dict(p, preview_key) for p in payments]
    else:
        receipts = PARENT_RECEIPTS.get(preview_key, [])
        if ref:
            receipts = [r for r in receipts if r.get("reference") == ref]
        print_receipts = [enrich_receipt_for_print(r, preview_key) for r in receipts]
    return render(
        request,
        "portal/parent/receipts_print.html",
        _parent_context(
            request,
            "Receipts — print",
            page_slug="receipts",
            print_receipts=print_receipts,
            print_receipt_ref=ref,
        ),
    )


@require_GET
@parent_login_required
def parent_tax_statement_print(request):
    account = get_parent_account(request.user)
    if not account:
        return render(request, "portal/404.html", status=404)
    eligibility = get_tax_eligibility_live(account.family)
    if not eligibility.get("eligible"):
        messages.error(request, eligibility.get("reason") or "Tax statement not available.")
        return redirect("portal_parent_page", page="tax-statements")
    statement = get_tax_statement_data(account.family)
    return render(
        request,
        "portal/parent/tax_statement_print.html",
        _parent_context(
            request,
            f"Tax statement {statement['tax_year']}",
            page_slug="tax-statements",
            tax_statement=statement,
        ),
    )


@staff_login_required
@require_GET
def staff_page(request, page):
    templates = {
        "dashboard": "portal/staff/dashboard.html",
        "programs": "portal/staff/programs.html",
        "attendance": "portal/staff/attendance.html",
        "applications": "portal/staff/applications.html",
        "create-application": "portal/staff/create_application.html",
        "families": "portal/staff/families.html",
        "member-policies": "portal/staff/member_policies.html",
        "agency": "portal/staff/agency.html",
        "reports": "portal/staff/reports.html",
        "messages": "portal/messages/messages.html",
        "incidents": "portal/staff/incidents.html",
        "support": "portal/support/support.html",
    }
    template = templates.get(page)
    if not template:
        return render(request, "portal/404.html", status=404)

    context = _staff_context(
        page.replace("-", " ").title(),
        request=request,
        staff_page_slug="applications" if page == "create-application" else page,
    )
    if page == "messages":
        context.update(_messages_context("staff", "Team messages", request))
    if page == "support":
        context.update(_support_context("staff", "Support", request))
    if page == "incidents":
        if context.get("portal_live"):
            context["incidents"] = get_incidents_live()
            context["incident_children"] = get_incident_children_live()
            context["viewing_incident"] = get_incident_live(request.GET.get("view"))
        else:
            context["incidents"] = INCIDENTS
            context["incident_children"] = get_incident_roster_children()
            context["viewing_incident"] = get_incident(request.GET.get("view"))
        context["incident_types"] = INCIDENT_TYPES
        context["incident_severity_options"] = INCIDENT_SEVERITY_OPTIONS
        context["show_log_incident"] = request.GET.get("log") == "1"
    if page == "families":
        if portal_is_live():
            unit = _staff_unit(request)
            context["families"] = families_for_staff(unit) if unit else []
        else:
            context["families"] = FAMILIES
    if page == "member-policies":
        unit = _staff_unit(request)
        if unit and context.get("portal_live"):
            from .staff_services import get_member_summaries_for_unit

            context["member_summaries"] = get_member_summaries_for_unit(unit)
        elif context.get("portal_live"):
            context["member_summaries"] = []
        else:
            context["member_summaries"] = get_member_policy_summaries(FAMILIES)
        context["policies_per_child"] = POLICIES_PER_CHILD
    if page == "programs":
        unit = _staff_unit(request)
        if unit and context.get("portal_live"):
            from .staff_services import get_programs_for_unit

            context["programs"] = get_programs_for_unit(unit)
        elif context.get("portal_live"):
            context["programs"] = []
        else:
            context["programs"] = STAFF_PROGRAMS_SCHOOL_18
    if page == "attendance":
        if portal_is_live():
            context.update(_staff_attendance_context(request))
        else:
            context["attendance"] = ATTENDANCE_SESSION
            context["roster"] = ATTENDANCE_ROSTER
            context["attendance_live"] = False
            context["checkin_modes"] = CHECKIN_MODES
            context["medical_alert_types"] = MEDICAL_ALERT_TYPES
            context["show_checkin_panel"] = request.GET.get("checkin") == "1" and request.GET.get("bulk") != "1"
            context["show_bulk_checkin_panel"] = request.GET.get("checkin") == "1" and request.GET.get("bulk") == "1"
            context["show_checkout_panel"] = request.GET.get("checkout") == "1" and request.GET.get("bulk") != "1"
            context["show_bulk_checkout_panel"] = request.GET.get("checkout") == "1" and request.GET.get("bulk") == "1"
    if page == "applications":
        if portal_is_live():
            unit = _staff_unit(request)
            context["applications"] = applications_for_staff(unit) if unit else []
        else:
            context["applications"] = STAFF_APPLICATIONS
    if page == "agency":
        unit = _staff_unit(request)
        context["today"] = date.today().isoformat()
        if unit and _portal_data_live():
            from .agency_services import agency_page_data

            context["agency"] = agency_page_data(unit)
        else:
            context["agency"] = AGENCY_UNIT_DATA
            context["agency"]["agency_live"] = False
    if page == "reports":
        context["reports"] = STAFF_REPORTS
    if page == "dashboard":
        unit = _staff_unit(request)
        program = get_active_program(unit) if unit else None
        if portal_is_live():
            from .staff_services import build_dashboard_live

            if unit and program:
                context.update(build_dashboard_live(unit, program))
            else:
                today = date.today()
                context["attendance"] = {
                    "date_display": today.strftime("%A, %B %d, %Y"),
                    "summary": {
                        "present": 0,
                        "not_arrived": 0,
                        "absent": 0,
                        "enrolled": 0,
                        "checked_out": 0,
                    },
                }
                context["application_count"] = 0
                context["alerts"] = []
        elif unit and program:
            from .staff_services import build_dashboard_live

            context.update(build_dashboard_live(unit, program))
        else:
            context["alerts"] = DASHBOARD_ALERTS
            context["attendance"] = ATTENDANCE_SESSION
            context["application_count"] = len(STAFF_APPLICATIONS)
        if context.get("portal_live"):
            context["messages_unread_count"] = count_messages_unread_live(for_admin=False)
        else:
            context["messages_unread_count"] = count_unread_messages(for_admin=False)
    if page == "create-application":
        unit = _staff_unit(request)
        program = get_active_program(unit) if unit else None
        context["active_program"] = program.name if program else ATTENDANCE_SESSION["program"]
        context["today"] = date.today().isoformat()
    return render(request, template, context)


@require_GET
def staff_incidents_print(request):
    incident_id = request.GET.get("incident")
    child_name = request.GET.get("child")
    live = _portal_data_live()
    if incident_id:
        incident = get_incident_live(incident_id) if live else get_incident(incident_id)
        if not incident:
            return render(request, "portal/404.html", status=404)
        incidents = [incident]
        print_scope = incident["child"]
        print_label = f"{incident['child']} — {incident['type']} · {incident['date']}"
    elif child_name:
        incidents = get_incidents_for_child_live(child_name) if live else get_incidents_for_child(child_name)
        print_scope = child_name
        print_label = f"{child_name} — incident history"
    else:
        incidents = get_incidents_live() if live else INCIDENTS
        print_scope = "School 18"
        print_label = "Incident & accident log — School 18"
    return render(
        request,
        "portal/staff/incidents_print.html",
        _staff_context(
            "Incident & accident log",
            incidents=incidents,
            print_scope=print_scope,
            print_label=print_label,
            print_single=bool(incident_id),
            print_child=child_name or "",
        ),
    )


@staff_login_required
@require_GET
def staff_family_policies(request, family_slug):
    from .staff_services import get_family_policies_for_staff

    policy_data = get_family_policies_for_staff(family_slug)
    if not policy_data:
        return render(request, "portal/404.html", status=404)
    context = _staff_family_context(
        family_slug,
        f"{policy_data['family_name']} — signed policies",
        "policies",
        policy_data=policy_data,
    )
    if not context:
        return render(request, "portal/404.html", status=404)
    return render(request, "portal/staff/family_policies.html", context)


@require_GET
def staff_member_policies_print(request):
    families_data = []
    for summary in get_member_policy_summaries(FAMILIES):
        families_data.append(get_family_policies(summary["slug"]))
    return render(
        request,
        "portal/staff/member_policies_print.html",
        _staff_context(
            "Member policies — print all",
            families_data=families_data,
            print_scope="School 18",
            policies_per_child=POLICIES_PER_CHILD,
        ),
    )


@require_GET
def staff_medical_report(request):
    unit = _staff_unit(request) if _portal_data_live() else None
    if unit:
        from .staff_services import build_medical_report_rows, medical_report_meta

        report_rows = build_medical_report_rows(unit)
        report_meta = medical_report_meta(unit)
    else:
        report_rows = MEDICAL_REPORT_ROWS
        report_meta = MEDICAL_REPORT_META
    alert_count = sum(1 for row in report_rows if row["has_medical"])
    return render(
        request,
        "portal/staff/medical_report.html",
        _staff_context(
            "Medical report",
            report_meta=report_meta,
            report_rows=report_rows,
            medical_alert_types=MEDICAL_ALERT_TYPES,
            alert_count=alert_count,
            staff_page_slug="reports",
        ),
    )


@require_GET
def staff_attendance_report(request):
    unit = _staff_unit(request) if _portal_data_live() else None
    program = get_active_program(unit) if unit else None
    sheet_date = date.today()
    if unit and program:
        roster = build_roster(unit, program, sheet_date)
        attendance = build_session_context(unit, program, sheet_date, roster)
    else:
        attendance = ATTENDANCE_SESSION
        roster = ATTENDANCE_ROSTER
    return render(
        request,
        "portal/staff/attendance_report.html",
        _staff_context(
            "Daily attendance sheet",
            attendance=attendance,
            roster=roster,
            staff_page_slug="reports",
        ),
    )


@require_GET
def staff_weekly_attendance_report(request):
    unit = _staff_unit(request) if _portal_data_live() else None
    program = get_active_program(unit) if unit else None
    sheet_date = date.today()
    if unit and program:
        from .staff_services import weekly_attendance_report_data

        weekly_rows, weekdays = weekly_attendance_report_data(unit, program, sheet_date)
        roster = build_roster(unit, program, sheet_date)
        attendance = build_session_context(unit, program, sheet_date, roster)
    else:
        weekly_rows = None
        weekdays = None
        attendance = ATTENDANCE_SESSION
        roster = ATTENDANCE_ROSTER
    return render(
        request,
        "portal/staff/weekly_attendance_report.html",
        _staff_context(
            "Weekly attendance summary",
            attendance=attendance,
            roster=roster,
            weekly_rows=weekly_rows,
            week_days=weekdays,
            staff_page_slug="reports",
        ),
    )


def _report_sheet_sources(request=None):
    """Return (live, unit, program) for printable roster sheets."""
    if _portal_data_live():
        unit = _staff_unit(request)
        program = get_active_program(unit) if unit else None
        return True, unit, program
    return False, None, None


def _report_names(unit, program):
    unit_name = unit.name if unit else ATTENDANCE_SESSION["unit"]
    program_name = program.name if program else ATTENDANCE_SESSION["program"]
    return unit_name, program_name


@require_GET
def staff_attendance_blank_daily(request):
    sheet_date = parse_sheet_date(request.GET.get("date"))
    live, unit, program = _report_sheet_sources(request)
    unit_name, program_name = _report_names(unit, program)
    return render(
        request,
        "portal/staff/attendance_blank_daily.html",
        _staff_context(
            "Daily attendance — blank sheet",
            staff_page_slug="reports",
            **daily_blank_context(
                sheet_date,
                unit_name,
                program_name,
                live=live,
                unit=unit,
                program_obj=program,
            ),
        ),
    )


@require_GET
def staff_attendance_blank_weekly(request):
    sheet_date = parse_sheet_date(request.GET.get("date"))
    live, unit, program = _report_sheet_sources(request)
    unit_name, program_name = _report_names(unit, program)
    return render(
        request,
        "portal/staff/attendance_blank_weekly.html",
        _staff_context(
            "Weekly attendance — blank sheet",
            staff_page_slug="reports",
            **weekly_blank_context(
                sheet_date,
                unit_name,
                program_name,
                live=live,
                unit=unit,
                program_obj=program,
            ),
        ),
    )


@require_GET
def staff_signout_blank(request):
    sheet_date = parse_sheet_date(request.GET.get("date"))
    live, unit, program = _report_sheet_sources(request)
    unit_name, program_name = _report_names(unit, program)
    return render(
        request,
        "portal/staff/signout_blank.html",
        _staff_context(
            "Sign-out sheet — blank",
            staff_page_slug="reports",
            **signout_blank_context(
                sheet_date,
                unit_name,
                program_name,
                live=live,
                unit=unit,
                program_obj=program,
            ),
        ),
    )


@staff_login_required
@require_GET
def staff_agency_billing(request, family_slug):
    from .agency_services import get_agency_billing_live

    unit = _staff_unit(request)
    billing = get_agency_billing_live(family_slug, unit) if _portal_data_live() else AGENCY_BILLING.get(family_slug)
    if not billing:
        return render(request, "portal/404.html", status=404)
    return render(
        request,
        "portal/staff/agency_billing.html",
        _staff_context(
            f"{billing['child_name']} — 4Cs agency account",
            request=request,
            billing=billing,
            staff_page_slug="agency",
        ),
    )


@staff_login_required
@require_GET
def staff_family_billing(request, family_slug):
    from .billing_services import get_family_for_billing, prepare_billing_for_staff
    from .staff_auth import billing_permissions_for_staff, get_staff_account

    permissions = billing_permissions_for_staff(get_staff_account(request.user))
    unit = _staff_unit(request)
    if _portal_data_live() and unit:
        family = get_family_for_billing(family_slug, unit)
        if not family:
            return render(request, "portal/404.html", status=404)
        billing = prepare_billing_for_staff(family, permissions)
        families = families_for_staff(unit)
    else:
        billing = FAMILIES_BILLING.get(family_slug)
        if not billing:
            return render(request, "portal/404.html", status=404)
        billing = prepare_billing_preview(billing, permissions)
        families = FAMILIES
    context = _staff_family_context(
        family_slug,
        f"{billing['family_name']} billing",
        "billing",
        billing=billing,
        billing_permissions=permissions,
        charge_types=BILLING_CHARGE_TYPES,
        families=families,
        billing_live=_portal_data_live(),
        today=date.today().isoformat(),
    )
    if not context:
        return render(request, "portal/404.html", status=404)
    return render(request, "portal/staff/family_billing.html", context)


@require_GET
@admin_login_required
def admin_family_billing(request, family_slug):
    from .billing_services import get_family_for_billing, prepare_billing_for_staff
    from .staff_auth import billing_permissions_for_staff

    permissions = billing_permissions_for_staff(None, portal_area="admin")
    if _portal_data_live():
        from .admin_services import get_member_families_live

        family = get_family_for_billing(family_slug, unit=None)
        if not family:
            return render(request, "portal/404.html", status=404)
        billing = prepare_billing_for_staff(family, permissions)
        families = get_member_families_live()
    else:
        billing = FAMILIES_BILLING.get(family_slug)
        if not billing:
            return render(request, "portal/404.html", status=404)
        billing = prepare_billing_preview(billing, permissions)
        families = ADMIN_MEMBER_FAMILIES
    return render(
        request,
        "portal/staff/family_billing.html",
        _finalize_admin_context(
            request,
            _portal_context(
                "admin",
                f"{billing['family_name']} billing",
                admin_page_slug="member-billing",
                billing=billing,
                billing_permissions=permissions,
                charge_types=BILLING_CHARGE_TYPES,
                families=families,
                billing_live=_portal_data_live(),
                today=date.today().isoformat(),
            ),
        ),
    )


@require_GET
@admin_login_required
def admin_family_policies(request, family_slug):
    policy_data = get_family_policies(family_slug)
    if not policy_data:
        return render(request, "portal/404.html", status=404)
    family_meta = next((f for f in ADMIN_MEMBER_FAMILIES if f["slug"] == family_slug), {})
    return render(
        request,
        "portal/staff/family_policies.html",
        _finalize_admin_context(
            request,
            _portal_context(
                "admin",
                f"{policy_data['family_name']} — signed policies",
                admin_page_slug="member-policies",
                policy_data=policy_data,
                family_meta=family_meta,
                family_slug=family_slug,
            ),
        ),
    )


@require_GET
def staff_family_pickup(request, family_slug):
    profile = _staff_family_profile(family_slug)
    if not profile:
        return render(request, "portal/404.html", status=404)
    pickup_data = family_authorized_pickup(profile, family_slug=family_slug if _portal_data_live() else None)
    context = _staff_family_context(
        family_slug,
        f"{profile['family_name']} — Authorized pickup",
        "pickup",
        pickup_data=pickup_data,
    )
    return render(request, "portal/staff/family_pickup.html", context)


@staff_login_required
@require_GET
def staff_pickup_report(request):
    program = request.GET.get("program", "all")
    unit = _staff_unit(request) if _portal_data_live() else None
    if unit:
        from .staff_services import pickup_report_for_unit

        programs, rows = pickup_report_for_unit(unit, program_filter=program)
    else:
        programs = pickup_report_programs(FAMILIES, FAMILY_DETAILS)
        rows = pickup_report_data(FAMILIES, FAMILY_DETAILS, program_filter=program)
    return render(
        request,
        "portal/staff/pickup_report.html",
        _staff_context(
            "Authorized pickup report",
            report_rows=rows,
            report_programs=programs,
            selected_program=program,
            generated_date=date.today().strftime("%B %d, %Y"),
            staff_page_slug="reports",
        ),
    )


@require_GET
def staff_family_detail(request, family_slug):
    profile = _staff_family_profile(family_slug)
    if not profile:
        return render(request, "portal/404.html", status=404)
    context = _staff_family_context(
        family_slug,
        f"{profile['family_name']} family",
        "profile",
        medical_alert_types=MEDICAL_ALERT_TYPES,
    )
    return render(request, "portal/staff/family_detail.html", context)


@require_GET
def staff_family_incidents(request, family_slug):
    profile = _staff_family_profile(family_slug)
    if not profile:
        return render(request, "portal/404.html", status=404)
    if _portal_data_live():
        family_incidents = get_incidents_for_family_live(family_slug)
        incidents_by_child = get_incidents_by_child_for_family_live(family_slug)
    else:
        family_incidents = get_incidents_for_family(family_slug)
        incidents_by_child = get_incidents_by_child_for_family(family_slug)
    context = _staff_family_context(
        family_slug,
        f"{profile['family_name']} — incidents",
        "incidents",
        family_incidents=family_incidents,
        incident_print_children=[
            {"child": name, "count": len(incs)}
            for name, incs in incidents_by_child.items()
            if incs
        ],
    )
    return render(request, "portal/staff/family_incidents.html", context)


@require_GET
def staff_application_detail(request, app_slug):
    application_urls = _application_portal_urls("staff", app_slug)
    if _portal_data_live():
        app = get_application_by_reference(app_slug)
        if app:
            return render(
                request,
                "portal/staff/application_detail.html",
                _staff_context(
                    f"Application — {app.student_first_name} {app.student_last_name}".strip(),
                    application=application_detail_dict(app),
                    app_slug=app_slug,
                    is_live_application=True,
                    staff_page_slug="applications",
                    application_urls=application_urls,
                ),
            )
    application = STAFF_APPLICATION_DETAILS.get(app_slug)
    if not application:
        return render(request, "portal/404.html", status=404)
    return render(
        request,
        "portal/staff/application_detail.html",
        _staff_context(
            f"Application — {application['child_name']}",
            application=application,
            app_slug=app_slug,
            staff_page_slug="applications",
            application_urls=application_urls,
        ),
    )


@require_GET
@admin_login_required
def admin_application_detail(request, app_slug):
    application_urls = _application_portal_urls("admin", app_slug)
    if _portal_data_live():
        app = get_application_by_reference(app_slug)
        if app:
            return render(
                request,
                "portal/staff/application_detail.html",
                _portal_context(
                    "admin",
                    f"Application — {app.student_first_name} {app.student_last_name}".strip(),
                    application=application_detail_dict(app),
                    app_slug=app_slug,
                    is_live_application=True,
                    admin_page_slug="applications",
                    application_urls=application_urls,
                ),
            )
    application = STAFF_APPLICATION_DETAILS.get(app_slug)
    if not application:
        return render(request, "portal/404.html", status=404)
    return render(
        request,
        "portal/staff/application_detail.html",
        _portal_context(
            "admin",
            f"Application — {application['child_name']}",
            application=application,
            app_slug=app_slug,
            admin_page_slug="applications",
            application_urls=application_urls,
        ),
    )


@require_GET
def staff_application_print(request, app_slug):
    application_urls = _application_portal_urls("staff", app_slug)
    if _portal_data_live():
        app = get_application_by_reference(app_slug)
        if app:
            return render(
                request,
                "portal/staff/application_print.html",
                _staff_context(
                    f"Application — {app.student_first_name} {app.student_last_name}".strip(),
                    application=application_detail_dict(app),
                    app_slug=app_slug,
                    application_urls=application_urls,
                ),
            )
    application = STAFF_APPLICATION_DETAILS.get(app_slug)
    if not application:
        return render(request, "portal/404.html", status=404)
    return render(
        request,
        "portal/staff/application_print.html",
        _staff_context(
            f"Application — {application['child_name']}",
            application=application,
            app_slug=app_slug,
            application_urls=application_urls,
        ),
    )


@require_GET
@admin_login_required
def admin_application_print(request, app_slug):
    application_urls = _application_portal_urls("admin", app_slug)
    if _portal_data_live():
        app = get_application_by_reference(app_slug)
        if app:
            return render(
                request,
                "portal/staff/application_print.html",
                _portal_context(
                    "admin",
                    f"Application — {app.student_first_name} {app.student_last_name}".strip(),
                    application=application_detail_dict(app),
                    app_slug=app_slug,
                    admin_page_slug="applications",
                    application_urls=application_urls,
                ),
            )
    application = STAFF_APPLICATION_DETAILS.get(app_slug)
    if not application:
        return render(request, "portal/404.html", status=404)
    return render(
        request,
        "portal/staff/application_print.html",
        _portal_context(
            "admin",
            f"Application — {application['child_name']}",
            application=application,
            app_slug=app_slug,
            admin_page_slug="applications",
            application_urls=application_urls,
        ),
    )


@staff_login_required
@require_GET
def staff_program_roster(request, program_slug):
    unit = _staff_unit(request) if _portal_data_live() else None
    if unit:
        from .staff_services import get_program_roster, get_programs_for_unit

        programs = get_programs_for_unit(unit)
        program = next(
            (p for p in programs if program_slug in p.get("slug", p["name"].lower().replace(" ", "-"))),
            programs[0] if programs else STAFF_PROGRAMS_SCHOOL_18[0],
        )
        roster = get_program_roster(unit, program.get("name"))
    else:
        program = next(
            (p for p in STAFF_PROGRAMS_SCHOOL_18 if program_slug in p["name"].lower().replace(" ", "-")),
            STAFF_PROGRAMS_SCHOOL_18[0],
        )
        roster = PROGRAM_ROSTER
    return render(
        request,
        "portal/staff/program_roster.html",
        _staff_context(
            f"{program['name']} roster",
            request=request,
            program=program,
            roster=roster,
            medical_alert_types=MEDICAL_ALERT_TYPES,
            staff_page_slug="programs",
        ),
    )


@staff_login_required
@require_POST
def staff_unit_switch(request):
    from .staff_auth import _can_access_unit

    slug = request.POST.get("unit_slug", "").strip()
    unit = PortalUnit.objects.filter(slug=slug, is_active=True).first()
    if unit and _can_access_unit(request.user, unit):
        request.session["staff_unit_slug"] = slug
        messages.success(request, f"Switched to {unit.name}.")
    else:
        messages.error(request, "Could not switch unit.")
    next_url = request.POST.get("next") or reverse("portal_staff_page", kwargs={"page": "dashboard"})
    return redirect(next_url)


@staff_login_required
@require_GET
def staff_balances_export(request):
    import csv

    from django.http import HttpResponse

    from .agency_services import balances_report_rows

    unit = _staff_unit(request)
    rows = balances_report_rows(unit) if unit and _portal_data_live() else []
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="outstanding-balances-{unit.slug if unit else "unit"}.csv"'
    writer = csv.writer(response)
    writer.writerow(["Family", "Contact", "Billing type", "Program", "Balance due"])
    for row in rows:
        writer.writerow([row["family"], row["contact"], row["billing_type"], row["program"], row["balance"]])
    return response


@staff_login_required
@require_GET
def staff_agency_copay_export(request):
    import csv

    from django.http import HttpResponse

    from .agency_services import copay_report_rows

    unit = _staff_unit(request)
    rows = copay_report_rows(unit) if unit and _portal_data_live() else []
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="4cs-copay-report-{unit.slug if unit else "unit"}.csv"'
    writer = csv.writer(response)
    writer.writerow(["Child", "Family", "Auth #", "Weekly copay", "Copay balance", "Agency balance"])
    for row in rows:
        writer.writerow(
            [row["child"], row["family"], row["auth_number"], row["weekly_copay"], row["copay_balance"], row["agency_balance"]]
        )
    return response


@require_GET
@admin_login_required
def admin_page(request, page):
    templates = {
        "dashboard": "portal/admin/dashboard.html",
        "units": "portal/admin/units.html",
        "programs": "portal/admin/programs.html",
        "staff": "portal/admin/staff_users.html",
        "families": "portal/admin/families.html",
        "applications": "portal/admin/applications.html",
        "agencies": "portal/admin/agencies.html",
        "fees": "portal/admin/fees.html",
        "member-billing": "portal/admin/member_billing.html",
        "billing-permissions": "portal/admin/billing_permissions.html",
        "scholarships": "portal/admin/scholarships.html",
        "member-policies": "portal/admin/member_policies.html",
        "checkin-settings": "portal/admin/checkin_settings.html",
        "reports": "portal/admin/reports.html",
        "messages": "portal/messages/messages.html",
        "communications": "portal/admin/communications.html",
        "lesson-planner": "portal/admin/lesson_planner.html",
        "staff-compliance": "portal/admin/staff_compliance.html",
        "licensing": "portal/admin/licensing.html",
        "support": "portal/support/support.html",
    }
    template = templates.get(page)
    if not template:
        return render(request, "portal/404.html", status=404)

    show_add_program = request.GET.get("add") == "1"
    show_add_unit = request.GET.get("add") == "1"
    show_add_staff = request.GET.get("add") == "1"
    show_add_agency = request.GET.get("add") == "1"
    context = _portal_context(
        "admin",
        page.replace("-", " ").title(),
        admin_page_slug=page,
        show_add_program=show_add_program,
        show_add_unit=show_add_unit,
        show_add_staff=show_add_staff,
        show_add_agency=show_add_agency,
    )
    if page == "dashboard":
        if context.get("portal_live"):
            from .admin_services import (
                get_admin_alerts_live,
                get_admin_dashboard_live,
                get_enrollment_by_unit_live,
                get_pending_profile_changes_admin,
            )

            context["dashboard"] = get_admin_dashboard_live()
            context["enrollment_by_unit"] = get_enrollment_by_unit_live()
            context["alerts"] = get_admin_alerts_live()
            context["pending_profile_changes"] = get_pending_profile_changes_admin()
        else:
            context["dashboard"] = ADMIN_DASHBOARD
            context["enrollment_by_unit"] = ADMIN_ENROLLMENT_BY_UNIT
            context["alerts"] = ADMIN_ALERTS
            context["pending_profile_changes"] = []
        context["absence_charge_alerts"] = ABSENCE_CHARGE_ALERTS
        if context.get("portal_live"):
            from .admin_config import get_absence_charge_alerts

            context["absence_charge_alerts"] = get_absence_charge_alerts()
        if context.get("portal_live"):
            context["messages_unread_count"] = count_messages_unread_live(for_admin=True)
        else:
            context["messages_unread_count"] = count_unread_messages(for_admin=True)
    if page == "messages":
        context = _messages_context("admin", "Team messages", request)
        context["admin_page_slug"] = "messages"
    if page == "communications":
        edit_id = request.GET.get("edit")
        send_id = request.GET.get("send")
        add = request.GET.get("add")
        if context.get("portal_live"):
            announcements = get_announcements_live()
            newsletters = get_newsletters_live()
        else:
            announcements = ADMIN_COMMUNICATIONS
            newsletters = NEWSLETTERS
        context["announcements"] = announcements
        context["newsletter_templates"] = NEWSLETTER_TEMPLATES
        context["newsletters"] = newsletters
        if context.get("portal_live"):
            from .admin_config import get_units_admin

            context["units"] = get_units_admin()
        else:
            context["units"] = UNITS
        context["show_add_announcement"] = add == "announcement"
        context["show_add_newsletter"] = add == "newsletter"
        context["editing_announcement"] = (
            next((a for a in announcements if a["id"] == edit_id), None)
            if edit_id and edit_id.startswith("ann")
            else None
        )
        context["editing_newsletter"] = (
            next((n for n in newsletters if n["id"] == edit_id), None)
            if edit_id and edit_id.startswith("nl")
            else None
        )
        context["sending_newsletter"] = (
            next((n for n in newsletters if n["id"] == send_id), None) if send_id else None
        )
    if page == "support":
        context = _support_context("admin", "Support inbox", request)
        context["admin_page_slug"] = "support"
    if page == "lesson-planner":
        context["lesson_topics"] = LESSON_PLANNER_TOPICS
        if context.get("portal_live"):
            from .admin_config import get_units_admin

            context["units"] = get_units_admin()
        else:
            context["units"] = UNITS
        default_age = "Grades 1–3"
        default_size = 12
        default_duration = "45 minutes"
        if request.GET.get("generate") == "1":
            topic_key = request.GET.get("topic", "")
            custom_topic = request.GET.get("custom_topic", "").strip()
            sample_topic = LESSON_PLANNER_SAMPLE["topic"] if not context.get("portal_live") else "Custom activity"
            topic = custom_topic if topic_key == "__custom__" else topic_key or sample_topic
            context["lesson_sample"] = build_lesson_plan_preview(
                topic=topic,
                goals=request.GET.get("goals", ""),
                age_group=request.GET.get("age_group", default_age),
                group_size=int(request.GET.get("group_size") or default_size),
                duration=request.GET.get("duration", default_duration),
                accommodations=request.GET.get("accommodations", ""),
            )
            context["lesson_generated"] = True
            context["lesson_form"] = {
                "topic": topic_key or LESSON_PLANNER_TOPICS[0],
                "custom_topic": custom_topic,
                "goals": request.GET.get("goals", ""),
                "age_group": request.GET.get("age_group", default_age),
                "group_size": request.GET.get("group_size", default_size),
                "duration": request.GET.get("duration", default_duration),
                "accommodations": request.GET.get("accommodations", ""),
            }
        elif context.get("portal_live"):
            context["lesson_sample"] = None
            context["lesson_generated"] = False
            context["lesson_form"] = {
                "topic": LESSON_PLANNER_TOPICS[0],
                "custom_topic": "",
                "goals": "",
                "age_group": default_age,
                "group_size": default_size,
                "duration": default_duration,
                "accommodations": "",
            }
        else:
            context["lesson_sample"] = LESSON_PLANNER_SAMPLE
            context["lesson_generated"] = False
            context["lesson_form"] = {
                "topic": LESSON_PLANNER_TOPICS[0],
                "custom_topic": "",
                "goals": LESSON_PLANNER_SAMPLE.get("goals", ""),
                "age_group": LESSON_PLANNER_SAMPLE["age_group"],
                "group_size": LESSON_PLANNER_SAMPLE["group_size"],
                "duration": LESSON_PLANNER_SAMPLE["duration"],
                "accommodations": LESSON_PLANNER_SAMPLE["accommodations"],
            }
    if page == "staff-compliance":
        context["cpr_required_per_unit"] = STAFF_COMPLIANCE_CPR_REQUIRED_PER_UNIT
        if context.get("portal_live"):
            context["staff_compliance"] = []
            context["compliance_by_unit"] = []
        else:
            context["staff_compliance"] = STAFF_COMPLIANCE
            context["compliance_by_unit"] = get_staff_compliance_by_unit()
    if page == "licensing":
        context["licensing_forms"] = NJ_LICENSING_FORMS
        if context.get("portal_live"):
            from .admin_config import get_units_admin

            context["units"] = get_units_admin()
        else:
            context["units"] = UNITS
    if page == "units":
        edit_id = request.GET.get("edit")
        if context.get("portal_live"):
            from .admin_config import get_units_admin

            context["units"] = get_units_admin()
            context["editing_unit"] = next((u for u in context["units"] if str(u.get("pk")) == edit_id), None)
        else:
            context["units"] = UNITS
            context["editing_unit"] = None
    if page == "programs":
        if context.get("portal_live"):
            from .admin_config import get_programs_admin, get_units_admin

            context["programs"] = get_programs_admin()
            context["units"] = get_units_admin()
        else:
            context["programs"] = PROGRAMS
            context["units"] = UNITS
    if page == "staff":
        edit_id = request.GET.get("edit")
        if context.get("portal_live"):
            from .admin_config import get_staff_roles_admin, get_units_admin
            from .admin_services import get_staff_users_live

            context["portal_staff_users"] = get_staff_users_live()
            context["units"] = get_units_admin()
            context["portal_staff_roles"] = get_staff_roles_admin()
            context["editing_staff"] = next((u for u in context["portal_staff_users"] if str(u.get("id")) == edit_id), None)
        else:
            context["portal_staff_users"] = PORTAL_STAFF_USERS
            context["units"] = UNITS
            context["portal_staff_roles"] = PORTAL_STAFF_ROLES
            context["editing_staff"] = None
    if page == "agencies":
        edit_id = request.GET.get("edit")
        if context.get("portal_live"):
            from .admin_config import get_agencies_admin, get_agency_child_rates, get_units_admin

            context["agencies"] = get_agencies_admin()
            context["agency_child_rates"] = get_agency_child_rates()
            context["units"] = get_units_admin()
            context["editing_agency"] = next((a for a in context["agencies"] if str(a.get("pk")) == edit_id), None)
        else:
            context["agencies"] = ADMIN_AGENCIES
            context["units"] = UNITS
            context["agency_child_rates"] = []
            context["editing_agency"] = None
    if page == "fees":
        if context.get("portal_live"):
            from .admin_config import (
                get_charge_types_admin,
                get_fee_rules_admin,
                get_payment_plans_admin,
                get_processing_fees_admin,
                get_tax_settings_admin,
            )

            context["fee_rules"] = get_fee_rules_admin()
            context["billing_charge_types"] = get_charge_types_admin()
            context["payment_plans"] = get_payment_plans_admin()
            context["processing_fees"] = get_processing_fees_admin()
            context["tax_settings"], context["tax_staff_options"] = get_tax_settings_admin()
        else:
            context["fee_rules"] = FEE_RULES
            context["billing_charge_types"] = BILLING_CHARGE_TYPES
            context["payment_plans"] = []
            context["processing_fees"] = []
            context["tax_settings"] = None
            context["tax_staff_options"] = []
    if page == "checkin-settings":
        if context.get("portal_live"):
            from .admin_config import get_checkin_settings_admin, get_units_admin

            context["checkin_modes"] = get_checkin_settings_admin()
            context["checkin_units"] = get_units_admin()
        else:
            context["checkin_modes"] = CHECKIN_MODES
            context["checkin_units"] = UNITS
    if page == "member-billing":
        if context.get("portal_live"):
            from .admin_services import get_member_families_live

            context["families"] = get_member_families_live()
        else:
            context["families"] = ADMIN_MEMBER_FAMILIES
    if page == "families":
        if context.get("portal_live"):
            from .admin_services import get_admin_families_live, get_units_live

            context["families"] = get_admin_families_live()
            context["units"] = get_units_live()
        else:
            context["families"] = [
                {
                    **row,
                    "unit": row.get("unit", "School 18"),
                    "unit_slug": row.get("unit_slug", "school-18"),
                    "program": row.get("program", "After-School 2026–27"),
                }
                for row in ADMIN_MEMBER_FAMILIES
            ]
            context["units"] = UNITS
    if page == "applications":
        unit_filter = request.GET.get("unit", "")
        if context.get("portal_live"):
            context["applications"] = applications_for_admin(unit_filter or None)
            from .admin_services import get_units_live

            context["units"] = get_units_live()
            context["applications_unit_filter"] = unit_filter
        else:
            context["applications"] = [{**row, "unit": row.get("unit", "School 18"), "unit_slug": row.get("unit_slug", ""), "status_slug": row.get("status", "under-review").lower().replace(" ", "-")} for row in STAFF_APPLICATIONS]
            context["units"] = UNITS
            context["applications_unit_filter"] = unit_filter
    if page == "billing-permissions":
        if context.get("portal_live"):
            from .admin_config import get_charge_types_admin, get_default_billing_rules
            from .admin_services import get_staff_users_live

            context["portal_staff_users"] = get_staff_users_live()
            context["billing_charge_types"] = get_charge_types_admin()
            context["default_billing_rules"] = get_default_billing_rules()
        else:
            context["portal_staff_users"] = PORTAL_STAFF_USERS
            context["billing_charge_types"] = BILLING_CHARGE_TYPES
            context["default_billing_rules"] = []
        context["billing_permission_notes"] = [
            "Add charge — post fees to a member account.",
            "Delete charge — remove a posted charge.",
            "Add credit — post a credit/adjustment that reduces balance.",
            "Edit family plans — change billing plan and amount on a child account.",
        ]
    if page == "scholarships":
        if context.get("portal_live"):
            from .admin_config import get_scholarships_admin

            funds, assignments, child_options = get_scholarships_admin()
            context["scholarship_funds"] = funds
            context["scholarship_assignments"] = assignments
            context["scholarship_child_options"] = child_options
        else:
            context["scholarship_funds"] = SCHOLARSHIP_FUNDS
            context["scholarship_assignments"] = SCHOLARSHIP_ASSIGNMENTS
            context["scholarship_child_options"] = SCHOLARSHIP_CHILD_OPTIONS
    if page == "member-policies":
        if context.get("portal_live"):
            from .admin_config import get_org_policies_admin
            from .admin_services import get_member_families_live

            families = get_member_families_live()
            context["org_policies"] = get_org_policies_admin()
        else:
            families = ADMIN_MEMBER_FAMILIES
            context["org_policies"] = []
        context["member_summaries"] = get_member_policy_summaries(families)
        context["policies_per_child"] = POLICIES_PER_CHILD
        if context.get("portal_live"):
            from .admin_config import get_units_admin

            context["units"] = get_units_admin()
        else:
            context["units"] = UNITS
    if page == "reports":
        context["reports"] = ADMIN_REPORTS
    return render(request, template, _finalize_admin_context(request, context))


@require_GET
@admin_login_required
def admin_enrollment_report(request):
    if _portal_data_live():
        from .admin_services import get_admin_dashboard_live, get_enrollment_by_unit_live, get_member_families_live

        dashboard = get_admin_dashboard_live()
        enrollment_by_unit = get_enrollment_by_unit_live()
        families = get_member_families_live()
    else:
        dashboard = ADMIN_DASHBOARD
        enrollment_by_unit = ADMIN_ENROLLMENT_BY_UNIT
        families = ADMIN_MEMBER_FAMILIES
    return render(
        request,
        "portal/admin/enrollment_report.html",
        _finalize_admin_context(
            request,
            _portal_context(
                "admin",
                "Organization enrollment summary",
                admin_page_slug="reports",
                dashboard=dashboard,
                enrollment_by_unit=enrollment_by_unit,
                families=families,
            ),
        ),
    )


@require_GET
@admin_login_required
def admin_financial_report(request):
    if _portal_data_live():
        from .admin_services import get_admin_dashboard_live, get_member_families_live

        families = get_member_families_live()
        dashboard = get_admin_dashboard_live()
    else:
        families = ADMIN_MEMBER_FAMILIES
        dashboard = ADMIN_DASHBOARD
    overdue = [f for f in families if float(f.get("balance", "0") or 0) > 0]
    return render(
        request,
        "portal/admin/financial_report.html",
        _finalize_admin_context(
            request,
            _portal_context(
                "admin",
                "Cross-unit financial summary",
                admin_page_slug="reports",
                families=families,
                overdue_families=overdue,
                dashboard=dashboard,
            ),
        ),
    )


@require_GET
@admin_login_required
def admin_member_policies_print(request):
    families_data = []
    for summary in get_member_policy_summaries(ADMIN_MEMBER_FAMILIES):
        families_data.append(get_family_policies(summary["slug"]))
    return render(
        request,
        "portal/admin/member_policies_print.html",
        _finalize_admin_context(
            request,
            _portal_context(
                "admin",
                "Member policies — print all",
                families_data=families_data,
                print_scope="All units",
                policies_per_child=POLICIES_PER_CHILD,
            ),
        ),
    )


@require_GET
@admin_login_required
def admin_parent_preview(request, family_slug, page="dashboard"):
    """Admin troubleshooting view — browse parent portal pages with sensitive data masked."""
    from enrollment.models import EnrollmentApplication

    from .models import PortalFamily, PortalParentAccount
    from .parent_services import (
        application_list_item,
        application_to_portal_dict,
        build_parent_preview_live,
        get_account_live,
        get_applications_for_family,
        get_drop_in_live,
        get_parent_announcement_live,
        get_parent_policy_data_live,
        get_receipts_live,
        get_tax_eligibility_live,
    )

    templates = {
        "dashboard": "portal/parent/dashboard.html",
        "profile": "portal/parent/profile.html",
        "applications": "portal/parent/applications.html",
        "policies": "portal/parent/policies.html",
        "billing": "portal/parent/billing.html",
        "receipts": "portal/parent/receipts.html",
        "drop-in": "portal/parent/drop_in.html",
        "account": "portal/parent/account.html",
        "tax-statements": "portal/parent/tax_statements.html",
        "support": "portal/support/support.html",
    }
    template = templates.get(page)
    if not template:
        return render(request, "portal/404.html", status=404)

    family = PortalFamily.objects.filter(slug=family_slug).select_related("unit").first()
    if _portal_data_live() and family:
        account = PortalParentAccount.objects.filter(family=family).select_related("user").first()
        preview = build_parent_preview_live(family, account)
        account_data = get_account_live(account) if account else {}
        if account_data.get("saved_cards"):
            account_data["saved_cards"] = [
                {**card, "last4": "••••", "brand": card.get("brand", "Card"), "expires": "••/••"}
                for card in account_data.get("saved_cards", [])
            ]
        account_data["stripe_customer_id"] = ""
        context = _portal_context(
            "parent",
            page.replace("-", " ").title(),
            admin_page_slug="communications",
            admin_support_preview=True,
            admin_preview_family_slug=family_slug,
            parent_preview=preview,
            parent_page_slug=page,
            parent_pay_query="",
            parent_announcement=get_parent_announcement_live(family),
            receipts=get_receipts_live(family) if account else [],
            drop_in=get_drop_in_live(account) if account else {},
            account=account_data,
            policy_data=get_parent_policy_data_live(family),
            policies_per_child=POLICIES_PER_CHILD,
            parent_stripe_enabled=False,
            parent_authenticated=True,
            parent_avatar={
                "initials": family.name[:2].upper(),
                "photo_url": "",
                "display_name": family.primary_contact or family.name,
            },
            parent_can_manage_photo=False,
            pending_profile_changes=[],
            preview_family_name=family.name,
        )
        if page == "billing":
            context["billing"] = preview["billing"]
        if page == "profile":
            context["profile"] = preview["profile"]
        if page == "dashboard":
            context["dashboard"] = preview["dashboard"]
        if page == "applications" and account:
            context["parent_applications"] = [
                application_list_item(app) for app in get_applications_for_family(account.family)
            ]
        if page == "policies":
            context["policies_signed_count"] = context["policy_data"]["signed_count"]
            context["policies_total"] = context["policy_data"]["total_count"]
        if page == "tax-statements":
            context["tax_settings"] = TAX_STATEMENT_SETTINGS
            context["tax_eligibility"] = get_tax_eligibility_live(family)
        if page == "receipts":
            paid_receipts = [r for r in context.get("receipts", []) if r.get("reference")]
            context["receipt_previews"] = [
                enrich_receipt_for_print(r, preview_key_for_family(family)) for r in paid_receipts[:2]
            ]
        if page == "support":
            context = _support_context("parent", "Support", request, preview_family=family_slug)
            context["admin_support_preview"] = True
            context["admin_preview_family_slug"] = family_slug
            context["parent_page_slug"] = "support"
            context["portal_area"] = "parent"
        return render(request, template, context)

    preview_key = {"jacobs": "private-pay", "martinez": "4cs", "williams": "scholarship"}.get(family_slug, "private-pay")
    request.GET = request.GET.copy()
    request.GET["pay"] = preview_key
    context = _parent_context(
        request,
        page.replace("-", " ").title(),
        page_slug=page,
        admin_support_preview=True,
        admin_preview_family_slug=family_slug,
        preview_family_name=family_slug.title(),
    )
    if page == "billing":
        context["billing"] = context["parent_preview"]["billing"]
    if page == "profile":
        context["profile"] = context["parent_preview"]["profile"]
    if page == "dashboard":
        context["dashboard"] = context["parent_preview"]["dashboard"]
    if page == "support":
        context = _support_context(
            "parent",
            "Support",
            request,
            preview_family=PREVIEW_FAMILY_SLUG.get(preview_key, family_slug),
        )
        context["admin_support_preview"] = True
        context["admin_preview_family_slug"] = family_slug
        context["parent_page_slug"] = "support"
    return render(request, template, context)


@require_POST
def staff_attendance_checkin(request):
    attendance_date = get_attendance_date(request)
    _unit, program, redirect_response = _attendance_program_or_redirect(request, attendance_date)
    if redirect_response:
        return redirect_response
    child_id = request.POST.get("child_id")
    method = request.POST.get("method", "Staff")
    note = request.POST.get("note", "")
    check_in_time = parse_time_input(request.POST.get("check_in_time"))
    try:
        record = check_in_child(child_id, program, attendance_date, check_in_time, method, note)
        from .attendance_service import format_time_display as _format_time_display

        messages.success(
            request,
            f"Checked in {record.child.name} at {_format_time_display(record.check_in_time)}.",
        )
    except Exception as exc:
        messages.error(request, str(exc))
    return attendance_redirect(request, attendance_date)


@require_POST
def staff_attendance_checkout(request):
    attendance_date = get_attendance_date(request)
    _unit, program, redirect_response = _attendance_program_or_redirect(request, attendance_date)
    if redirect_response:
        return redirect_response
    child_id = request.POST.get("child_id")
    check_out_time = parse_time_input(request.POST.get("check_out_time"))
    try:
        record = check_out_child(child_id, program, attendance_date, check_out_time)
        messages.success(request, f"Checked out {record.child.name}.")
    except Exception as exc:
        messages.error(request, str(exc))
    return attendance_redirect(request, attendance_date)


@require_POST
def staff_attendance_absent(request):
    attendance_date = get_attendance_date(request)
    _unit, program, redirect_response = _attendance_program_or_redirect(request, attendance_date)
    if redirect_response:
        return redirect_response
    child_id = request.POST.get("child_id")
    note = request.POST.get("note", "")
    try:
        record = mark_absent(child_id, program, attendance_date, note)
        messages.success(request, f"Marked {record.child.name} absent.")
    except Exception as exc:
        messages.error(request, str(exc))
    return attendance_redirect(request, attendance_date)


@require_POST
def staff_attendance_undo_absent(request):
    attendance_date = get_attendance_date(request)
    _unit, program, redirect_response = _attendance_program_or_redirect(request, attendance_date)
    if redirect_response:
        return redirect_response
    child_id = request.POST.get("child_id")
    try:
        record = undo_absent(child_id, program, attendance_date)
        messages.success(request, f"{record.child.name} marked as expected again.")
    except Exception as exc:
        messages.error(request, str(exc))
    return attendance_redirect(request, attendance_date)


@require_POST
def staff_attendance_bulk_checkin(request):
    attendance_date = get_attendance_date(request)
    _unit, program, redirect_response = _attendance_program_or_redirect(request, attendance_date)
    if redirect_response:
        return redirect_response
    child_ids = request.POST.getlist("child_ids")
    method = request.POST.get("method", "Staff")
    count = 0
    for child_id in child_ids:
        time_value = request.POST.get(f"check_in_time_{child_id}") or request.POST.get("program_time")
        try:
            check_in_child(child_id, program, attendance_date, parse_time_input(time_value), method)
            count += 1
        except Exception:
            continue
    messages.success(request, f"Checked in {count} child{'ren' if count != 1 else ''}.")
    return attendance_redirect(request, attendance_date)


@require_POST
def staff_attendance_bulk_checkout(request):
    attendance_date = get_attendance_date(request)
    _unit, program, redirect_response = _attendance_program_or_redirect(request, attendance_date)
    if redirect_response:
        return redirect_response
    child_ids = request.POST.getlist("child_ids")
    count = 0
    for child_id in child_ids:
        time_value = request.POST.get(f"check_out_time_{child_id}") or request.POST.get("program_time")
        try:
            check_out_child(child_id, program, attendance_date, parse_time_input(time_value))
            count += 1
        except Exception:
            continue
    messages.success(request, f"Checked out {count} child{'ren' if count != 1 else ''}.")
    return attendance_redirect(request, attendance_date)
