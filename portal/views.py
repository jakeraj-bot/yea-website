from django.conf import settings
from django.contrib import messages
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_http_methods, require_POST
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
    enrich_demo_application,
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
from .staff_auth import admin_login_required, staff_login_required, staff_login_required_post
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
    application_to_portal_dict,
    applications_for_admin,
    applications_for_staff,
    get_application_by_reference,
    parent_application_list_items,
    staff_application_detail as application_detail_dict,
    waitlist_for_admin,
    waitlist_for_staff,
)
from .pickup_services import family_authorized_pickup, pickup_report_data, pickup_report_programs
from .models import PortalUnit
from .processing_fees import stripe_fee_display
from .stripe_services import stripe_configured


def _portal_data_live():
    return portal_is_live()


def _portal_families_live():
    return portal_is_live()


def _staff_family_profile(family_slug, unit=None, family_id=None):
    if _portal_families_live():
        return family_profile_live(family_slug, unit=unit, family_id=family_id)
    profile = FAMILY_DETAILS.get(family_slug)
    if profile:
        return profile
    family = next((f for f in FAMILIES if f["slug"] == family_slug), None)
    if not family:
        return None
    from .family_list import DEMO_CHILD_SCHOOLS

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
                "school": DEMO_CHILD_SCHOOLS.get(c, ""),
                "location": "School 18",
                "program": family["program"],
                "allergies": "",
                "medications": "",
            }
            for c in family["children"]
        ],
        "emergency_contacts": [],
    }


FAMILY_TAB_URL_KEYS = {
    "profile": "family_detail",
    "pickup": "family_pickup",
    "incidents": "family_incidents",
    "billing": "family_billing",
    "plans": "family_plans",
    "agency": "family_agency",
    "applications": "family_applications",
    "policies": "family_policies",
    "email": "family_email",
}


def _family_list_rows_for_neighbors(area, unit=None):
    from .family_list import demo_family_list_rows

    if _portal_families_live():
        if area == "admin":
            from .admin_services import get_admin_families_live

            return get_admin_families_live()
        return families_for_staff(unit) if unit else []
    return demo_family_list_rows(area)


def _family_hub_url(area, family_tab, slug, family_id=None, parent_page=None):
    if family_tab == "parentview":
        if area != "admin":
            family_tab = "profile"
        elif parent_page and parent_page != "dashboard":
            url = reverse(
                "portal_admin_parent_preview_page",
                kwargs={"family_slug": slug, "page": parent_page},
            )
        else:
            url = reverse("portal_admin_parent_preview", kwargs={"family_slug": slug})
        if family_id:
            url = f"{url}?id={family_id}"
        return url
    key = FAMILY_TAB_URL_KEYS.get(family_tab, "family_detail")
    prefix = "portal_admin_" if area == "admin" else "portal_staff_"
    url = reverse(f"{prefix}{key}", kwargs={"family_slug": slug})
    if area == "admin" and family_id:
        url = f"{url}?id={family_id}"
    return url


def _family_neighbor_link(area, household, family_tab, parent_page=None):
    if not household:
        return None
    return {
        "id": household.get("id"),
        "slug": household["slug"],
        "name": household["name"],
        "url": _family_hub_url(
            area,
            family_tab,
            household["slug"],
            household.get("id"),
            parent_page=parent_page,
        ),
    }


def _family_neighbor_nav(request, area, family_slug, family_tab, family_id=None, parent_page=None):
    from .family_list import adjacent_households, unique_households_from_rows

    unit = None if area == "admin" else _staff_unit(request)
    households = unique_households_from_rows(_family_list_rows_for_neighbors(area, unit))
    previous, nxt = adjacent_households(households, slug=family_slug, family_id=family_id)
    return {
        "family_prev": _family_neighbor_link(area, previous, family_tab, parent_page=parent_page),
        "family_next": _family_neighbor_link(area, nxt, family_tab, parent_page=parent_page),
    }


def _staff_family_context(family_slug, page_title, family_tab, request=None, unit=None, **extra):
    if unit is None and request is not None:
        unit = _staff_unit(request)
    family_id = extra.get("family_id")
    if not family_id and request is not None:
        family_id = _family_id_from_request(request) or None
    profile = _staff_family_profile(family_slug, unit=unit, family_id=family_id)
    if not profile:
        return None
    if _portal_families_live():
        family_meta = family_meta_live(family_slug, unit=unit) or {}
    else:
        family_meta = next((f for f in FAMILIES if f["slug"] == family_slug), {})
    if _portal_data_live():
        family_incidents = get_incidents_for_family_live(family_slug)
    else:
        family_incidents = get_incidents_for_family(family_slug)
    parent_email = (profile.get("primary") or {}).get("email") or extra.get("parent_email") or ""
    if not parent_email and _portal_families_live():
        from .member_admin import parent_email_for_family, resolve_family

        live_family = resolve_family(family_slug=family_slug, unit=unit)
        if live_family:
            parent_email = parent_email_for_family(live_family)
    extra.setdefault("parent_email", parent_email)
    extra.setdefault("family_id", family_id or (family_meta or {}).get("id"))
    extra.setdefault("email_send_url", "portal_staff_family_email_send")
    if request is not None:
        extra.update(
            _family_neighbor_nav(request, "staff", family_slug, family_tab, extra.get("family_id"))
        )
    return _staff_context(
        page_title,
        request=request,
        profile=profile,
        family_meta=family_meta,
        family_slug=family_slug,
        family_tab=family_tab,
        family_incident_count=len(family_incidents),
        staff_page_slug="families",
        **extra,
    )


def _family_hub_context(request, area, family_slug, page_title, family_tab, **extra):
    family_id = extra.pop("family_id", None) or _family_id_from_request(request) or None
    unit = None if area == "admin" else _staff_unit(request)
    profile = extra.pop("profile", None) or _staff_family_profile(family_slug, unit=unit, family_id=family_id)
    if not profile:
        return None
    if _portal_families_live():
        family_meta = family_meta_live(family_slug, unit=unit, family_id=family_id) or {}
    else:
        family_meta = next((f for f in FAMILIES if f["slug"] == family_slug), {})
    if _portal_data_live():
        family_incidents = get_incidents_for_family_live(family_slug)
    else:
        family_incidents = get_incidents_for_family(family_slug)
    parent_email = extra.get("parent_email") or (profile.get("primary") or {}).get("email") or ""
    if not parent_email and _portal_families_live():
        from .member_admin import parent_email_for_family, resolve_family

        live_family = resolve_family(family_slug=family_slug, family_id=family_id, unit=unit)
        if live_family:
            parent_email = parent_email_for_family(live_family)
            family_id = live_family.pk
    extra.setdefault("parent_email", parent_email)
    extra.setdefault("family_id", family_id or (family_meta or {}).get("id"))
    extra.setdefault(
        "email_send_url",
        "portal_admin_family_email_send" if area == "admin" else "portal_staff_family_email_send",
    )
    extra.setdefault("medical_alert_types", MEDICAL_ALERT_TYPES)
    extra.setdefault("family_incident_count", len(family_incidents))
    extra.update(
        _family_neighbor_nav(request, area, family_slug, family_tab, extra.get("family_id"))
    )
    if area == "admin":
        if _portal_families_live():
            from .member_admin import resolve_family

            live_family = resolve_family(family_slug=family_slug, family_id=extra.get("family_id"))
            if live_family:
                extra.setdefault("family_id", live_family.pk)
                for key, value in _admin_family_ops_context(live_family).items():
                    extra.setdefault(key, value)
        return _finalize_admin_context(
            request,
            _portal_context(
                "admin",
                page_title,
                admin_page_slug="families",
                profile=profile,
                family_meta=family_meta,
                family_slug=family_slug,
                family_tab=family_tab,
                **extra,
            ),
        )
    extra.setdefault("staff_page_slug", "families")
    return _staff_context(
        page_title,
        request=request,
        profile=profile,
        family_meta=family_meta,
        family_slug=family_slug,
        family_tab=family_tab,
        **extra,
    )


def _family_billing_bundle(request, area, family_slug):
    from .billing_services import (
        MONTH_DAYS,
        WEEKDAYS,
        get_family_for_billing,
        get_refundable_payments,
        prepare_billing_for_staff,
        run_due_plan_charges,
    )
    from .staff_auth import billing_permissions_for_staff, get_staff_account

    permissions = billing_permissions_for_staff(
        None if area == "admin" else get_staff_account(request.user),
        portal_area=area,
    )
    unit = None if area == "admin" else _staff_unit(request)
    refundable_payments = []
    if _portal_families_live() and (area == "admin" or unit):
        posted = run_due_plan_charges()
        if posted:
            messages.success(request, f"Posted {len(posted)} scheduled plan charge(s).")
        family = get_family_for_billing(family_slug, unit, family_id=_family_id_from_request(request))
        if not family:
            return None
        billing = prepare_billing_for_staff(family, permissions)
        if area == "admin":
            from .admin_services import get_member_families_live

            families = get_member_families_live()
            refundable_payments = get_refundable_payments(family)
        else:
            families = families_for_staff(unit)
    else:
        billing = FAMILIES_BILLING.get(family_slug)
        if not billing:
            return None
        billing = prepare_billing_preview(billing, permissions)
        families = ADMIN_MEMBER_FAMILIES if area == "admin" else FAMILIES
    return {
        "billing": billing,
        "billing_permissions": permissions,
        "charge_types": BILLING_CHARGE_TYPES,
        "families": families,
        "billing_live": _portal_families_live(),
        "today": date.today().isoformat(),
        "plan_weekdays": WEEKDAYS,
        "plan_month_days": MONTH_DAYS,
        "refundable_payments": refundable_payments,
    }


def _finalize_admin_context(request, context):
    from .parent_auth import portal_preview_mode
    from .staff_auth import is_admin_portal_authenticated

    context["admin_authenticated"] = portal_preview_mode() or is_admin_portal_authenticated(request)
    from .staff_auth import portal_switch_flags

    context.update(portal_switch_flags(request.user))
    return context


def _portal_back_fallback(area, pay_query=""):
    if area == "parent":
        return reverse("portal_parent_page", kwargs={"page": "dashboard"}) + pay_query
    if area == "staff":
        return reverse("portal_staff_page", kwargs={"page": "dashboard"})
    if area == "admin":
        return reverse("portal_admin_page", kwargs={"page": "dashboard"})
    return reverse("portal_home")


def _application_portal_urls(area, app_slug, *, waitlist=False):
    list_page = "waitlist" if waitlist else "applications"
    list_label = "Waitlist" if waitlist else "Applications"
    if area == "admin":
        return {
            "list": reverse("portal_admin_page", kwargs={"page": list_page}),
            "list_label": list_label,
            "review": reverse("portal_admin_application_review", kwargs={"app_slug": app_slug}),
            "print": reverse("portal_admin_application_print", kwargs={"app_slug": app_slug}),
            "edit": reverse("portal_admin_member_ops"),
            "detail": reverse("portal_admin_application_detail", kwargs={"app_slug": app_slug}),
        }
    return {
        "list": reverse("portal_staff_page", kwargs={"page": list_page}),
        "list_label": list_label,
        "review": reverse("portal_staff_application_review", kwargs={"app_slug": app_slug}),
        "print": reverse("portal_staff_application_print", kwargs={"app_slug": app_slug}),
        "detail": reverse("portal_staff_application_detail", kwargs={"app_slug": app_slug}),
    }


def _family_id_from_request(request):
    return request.GET.get("id") or request.GET.get("family_id") or ""


def _admin_family_ops_context(family):
    from .member_admin import SUSPEND_REASONS, matching_prior_balances
    from .models import PortalDiscountPlan, PortalPriorBalance

    return {
        "family_id": family.pk,
        "suspend_reasons": SUSPEND_REASONS,
        "matching_prior_balances": matching_prior_balances(family),
        "discount_plans": PortalDiscountPlan.objects.filter(is_active=True),
        "unlinked_prior_balances": PortalPriorBalance.objects.filter(linked_family__isnull=True),
    }


def _application_location_context(app):
    from enrollment.locations import get_enrollment_location_choices, get_location_label

    choices = list(get_enrollment_location_choices())
    current = app.program_location or ""
    choice_values = {value for value, _ in choices}
    if current and current not in choice_values:
        label = get_location_label(current)
        choices.insert(0, (current, f"{label} (update required)"))
    elif not current:
        choices.insert(0, ("", "Choose a location"))
    return {
        "location_choices": choices,
        "program_location": current,
    }


def _demo_waitlist_rows():
    rows = []
    for index, row in enumerate(STAFF_APPLICATIONS, start=1):
        status = (row.get("status") or "").lower()
        if "waitlist" not in status:
            continue
        item = {
            **row,
            "unit": row.get("unit", "School 18"),
            "unit_slug": row.get("unit_slug", ""),
            "status_slug": "waitlist",
            "waitlist_position": len(rows) + 1,
        }
        rows.append(item)
    if rows:
        return rows
    return [
        {
            "slug": "jordan-jacobs",
            "child": "Jordan Jacobs",
            "family": "Jacobs",
            "family_slug": "jacobs",
            "unit": "School 18",
            "submitted": "Sep 8, 2026 9:12 AM",
            "program": "Before care (waitlist)",
            "status": "Waitlist",
            "status_slug": "waitlist",
            "waitlist_position": 1,
            "returning": False,
        }
    ]


def _can_approve_this_application(request, app, portal_area):
    from .staff_auth import can_approve_enrollment_application, get_staff_account

    if portal_area == "admin":
        return True
    if not app:
        return False
    return can_approve_enrollment_application(get_staff_account(request.user), app, portal_area)


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
    if area == "admin":
        context.setdefault("can_approve_applications", True)
        context.setdefault("can_approve_waitlist", True)
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
    if extra.get("school_options") is None and unit and _portal_data_live():
        from .member_admin import known_school_names

        ctx["school_options"] = known_school_names(unit)
    if request is not None:
        from .staff_auth import (
            application_permissions_for_staff,
            billing_permissions_for_staff,
            get_staff_account,
            is_staff_portal_authenticated,
            staff_accessible_units,
        )

        account = get_staff_account(request.user)
        ctx["staff_account"] = account
        ctx["billing_permissions"] = billing_permissions_for_staff(account)
        ctx.update(application_permissions_for_staff(account, portal_area="staff"))
        ctx["staff_authenticated"] = is_staff_portal_authenticated(request) or portal_preview_mode()
        ctx["staff_units"] = list(staff_accessible_units(request.user)) if request.user.is_authenticated else []
        ctx["staff_unit_slug"] = unit.slug if unit else ""
        from .staff_auth import portal_switch_flags

        ctx.update(portal_switch_flags(request.user))
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


def append_query_params(existing_query="", **kwargs):
    from urllib.parse import urlencode

    params = {
        key: value
        for key, value in kwargs.items()
        if value is not None and str(value) != ""
    }
    if not params:
        return existing_query or ""
    encoded = urlencode(params)
    if existing_query:
        separator = "&" if existing_query.startswith("?") else "?"
        return f"{existing_query}{separator}{encoded}"
    return f"?{encoded}"


def _parent_pay_query(request):
    if _parent_live_mode(request):
        return ""
    preview_key = _parent_preview_key(request)
    demo_key = preview_key if preview_key in PARENT_PAYMENT_PREVIEWS else "private-pay"
    return f"?pay={demo_key}"


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
    if policy_data:
        _attach_parent_policy_print_urls(policy_data)
    parent_avatar = get_parent_avatar_context(account, preview)
    from .staff_auth import get_portal_auth

    parent_signed_in = bool(account) and get_portal_auth(request) == "parent"
    support_view = None
    if account and parent_signed_in:
        from .support_view import active_support_view

        support_view = active_support_view(account.family)
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
        parent_support_view_active=bool(support_view),
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
        "attendance_live": portal_is_live(),
        "attendance_needs_seed": False,
        "checkin_modes": CHECKIN_MODES,
        "medical_alert_types": MEDICAL_ALERT_TYPES,
        "show_checkin_panel": request.GET.get("checkin") == "1" and request.GET.get("bulk") != "1",
        "show_bulk_checkin_panel": request.GET.get("checkin") == "1" and request.GET.get("bulk") == "1",
        "show_checkout_panel": request.GET.get("checkout") == "1" and request.GET.get("bulk") != "1",
        "show_bulk_checkout_panel": request.GET.get("checkout") == "1" and request.GET.get("bulk") == "1",
    }


def _attendance_program_or_redirect(request, attendance_date):
    unit = _staff_unit(request)
    program = get_active_program(unit)
    if not unit or not program:
        messages.error(request, "No active program is set up for this unit yet.")
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

    from .staff_auth import portal_switch_flags

    if not getattr(settings, "PORTALS_PUBLIC", True):
        return render(request, "core/portals_unavailable.html")
    return render(request, "core/portals.html", portal_switch_flags(request.user))


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
        "field-trips": "portal/parent/field_trips.html",
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
        for payment in context["parent_preview"].get("stripe_reconciled") or []:
            messages.success(request, f"Payment recorded — receipt {payment.receipt_no}.")
    if page == "profile":
        context["profile"] = context["parent_preview"]["profile"]
    if page == "dashboard":
        context["dashboard"] = context["parent_preview"]["dashboard"]
        account = get_parent_account(request.user) if request.user.is_authenticated else None
        if account and _parent_live_mode(request):
            from .field_trip_services import pending_field_trip_count

            context["pending_field_trips"] = pending_field_trip_count(account.family)
    if page == "field-trips":
        account = get_parent_account(request.user) if request.user.is_authenticated else None
        if account and _parent_live_mode(request):
            from .field_trip_services import get_family_field_trips

            context["field_trips"] = get_family_field_trips(account.family)
        else:
            context["field_trips"] = []
    if page == "applications":
        account = get_parent_account(request.user) if request.user.is_authenticated else None
        if account:
            context["parent_applications"] = parent_application_list_items(account.family)
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

            app = (
                EnrollmentApplication.objects.filter(
                    portal_family=account.family,
                    reference=app_ref,
                )
                .prefetch_related("policy_signatures", "emergency_contacts")
                .first()
            )
            if app:
                application = _application_with_policy_print_urls(
                    application_to_portal_dict(app),
                    "portal_parent_application_policy_print",
                    query={"ref": app_ref},
                )
        if not application and portal_preview_mode():
            application = _application_with_policy_print_urls(
                enrich_demo_application(SAMPLE_APPLICATION),
                "portal_parent_application_policy_print",
                query={"ref": "demo"},
            )
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
        family = None
        if _parent_live_mode(request) and account:
            preview_key = preview_key_for_family(account.family)
            family = account.family
        paid_receipts = [r for r in context.get("receipts", []) if r.get("reference")]
        context["receipt_previews"] = [enrich_receipt_for_print(r, preview_key, family=family) for r in paid_receipts[:2]]
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
        amount = request.GET.get("amount") or billing.get("balance_due") or billing["running_balance"]
        dropin_context = None
        page_title = "Pay or add credit"
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
            stripe_fee=stripe_fee_display(),
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
    balance = float(billing.get("balance_due") or max(float(billing["running_balance"]), 0))
    is_dropin = request.GET.get("source") == "dropin"
    amount_raw = request.GET.get("amount", billing.get("balance_due") or billing["running_balance"])
    try:
        pay_amount = float(str(amount_raw).replace(",", ""))
    except (TypeError, ValueError):
        pay_amount = balance
    if pay_amount <= 0:
        if is_dropin:
            pay_amount = float(request.GET.get("amount") or 35)
        else:
            messages.error(request, "Enter an amount to pay or add as account credit.")
            return redirect("portal_parent_payment")
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
            stripe_fee=stripe_fee_display(),
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
    account = get_parent_account(request.user)
    if stripe_configured():
        from .stripe_services import confirm_checkout_payment, reconcile_pending_stripe_payments_for_family

        if session_id:
            payment = confirm_checkout_payment(session_id)
        if not payment and account:
            reconciled = reconcile_pending_stripe_payments_for_family(account.family)
            if reconciled:
                payment = reconciled[-1]
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
    application = None
    if account and app_ref:
        from enrollment.models import EnrollmentApplication

        app = (
            EnrollmentApplication.objects.filter(
                portal_family=account.family,
                reference=app_ref,
            )
            .prefetch_related("policy_signatures", "emergency_contacts")
            .first()
        )
        if app:
            application = application_detail_dict(app)
    if not application and portal_preview_mode():
        application = enrich_demo_application(SAMPLE_APPLICATION)
    if not application:
        return render(request, "portal/404.html", status=404)
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


def _attach_parent_policy_print_urls(policy_data):
    from enrollment.policy_display import attach_policy_print_urls

    for child in policy_data.get("children", []):
        attach_policy_print_urls(
            child["policies"],
            "portal_parent_policy_print",
            query={"child": child["child_name"]},
        )
    return policy_data


def _attach_family_policy_print_urls(policy_data, url_name, family_slug):
    from enrollment.policy_display import attach_policy_print_urls

    for child in policy_data.get("children", []):
        attach_policy_print_urls(
            child["policies"],
            url_name,
            query={"child": child["child_name"]},
            family_slug=family_slug,
        )
    return policy_data


def _application_with_policy_print_urls(application, url_name, **url_kwargs):
    from enrollment.policy_display import attach_policy_print_urls

    application = enrich_demo_application(application)
    policies = application.get("signed_policies", [])
    query = url_kwargs.pop("query", None)
    attach_policy_print_urls(policies, url_name, query=query, **url_kwargs)
    application["signed_policies"] = policies
    return application


def _policy_from_family_data(policy_data, child_name, policy_slug):
    for child in policy_data.get("children", []):
        if child_name and child["child_name"] != child_name:
            continue
        for policy in child["policies"]:
            if policy["slug"] == policy_slug:
                return child["child_name"], policy
    return None, None


def _render_single_policy_print(request, *, policy, child_name, family_name, breadcrumb, back_url, context_builder):
    return render(
        request,
        "portal/includes/single_policy_print_page.html",
        context_builder(
            request,
            policy["title"],
            breadcrumb=breadcrumb,
            back_url=back_url,
            child_name=child_name,
            family_name=family_name,
            policy=policy,
            policy_list=[policy],
        ),
    )


@require_GET
@parent_login_required
def parent_policy_print(request, policy_slug):
    child_name = request.GET.get("child", "").strip()
    account = get_parent_account(request.user)
    if _parent_live_mode(request) and account:
        policy_data = get_parent_policy_data_live(account.family)
    else:
        policy_data = _parent_policy_data(_parent_preview_key(request))
    if not policy_data:
        return render(request, "portal/404.html", status=404)
    child_name, policy = _policy_from_family_data(policy_data, child_name, policy_slug)
    if not policy:
        return render(request, "portal/404.html", status=404)
    pay_query = _parent_pay_query(request)
    return _render_single_policy_print(
        request,
        policy=policy,
        child_name=child_name,
        family_name=policy_data["family_name"],
        breadcrumb=f'<a href="{reverse("portal_parent_page", kwargs={"page": "policies"})}{pay_query}">Policies</a> / Print',
        back_url=f"{reverse('portal_parent_page', kwargs={'page': 'policies'})}{pay_query}",
        context_builder=lambda req, title, **kwargs: _parent_context(req, title, page_slug="policies", **kwargs),
    )


@require_GET
@parent_login_required
def parent_application_policy_print(request, policy_slug):
    app_ref = request.GET.get("ref", "").strip()
    account = get_parent_account(request.user)
    if account and app_ref:
        app = get_application_by_reference(app_ref)
        if app and app.portal_family_id == account.family_id:
            from enrollment.policy_display import get_application_policy

            policy = get_application_policy(app, policy_slug)
            if policy:
                pay_query = _parent_pay_query(request)
                app_url = f"{reverse('portal_parent_page', kwargs={'page': 'application'})}{append_query_params(pay_query, ref=app_ref)}"
                return _render_single_policy_print(
                    request,
                    policy=policy,
                    child_name=f"{app.student_first_name} {app.student_last_name}".strip(),
                    family_name=app.family_name,
                    breadcrumb=f'<a href="{app_url}">Application</a> / Print policy',
                    back_url=app_url,
                    context_builder=lambda req, title, **kwargs: _parent_context(req, title, page_slug="application", **kwargs),
                )
    return render(request, "portal/404.html", status=404)


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
        "waitlist": "portal/staff/waitlist.html",
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
        from .family_list import demo_family_list_rows

        if portal_is_live():
            unit = _staff_unit(request)
            context["families"] = families_for_staff(unit) if unit else []
        else:
            context["families"] = demo_family_list_rows("staff")
        context["family_count"] = len({row["slug"] for row in context["families"]})
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
        context["applications_tab"] = "all"
        if portal_is_live():
            unit = _staff_unit(request)
            context["applications"] = applications_for_staff(unit) if unit else []
        else:
            context["applications"] = STAFF_APPLICATIONS
    if page == "waitlist":
        context["applications_tab"] = "waitlist"
        context["waitlist_next"] = request.get_full_path()
        if portal_is_live():
            unit = _staff_unit(request)
            context["applications"] = waitlist_for_staff(unit) if unit else []
        else:
            context["applications"] = _demo_waitlist_rows()
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


@staff_login_required
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
    _attach_family_policy_print_urls(policy_data, "portal_staff_family_policy_print", family_slug)
    context = _staff_family_context(
        family_slug,
        f"{policy_data['family_name']} — signed policies",
        "policies",
        request=request,
        policy_data=policy_data,
    )
    if not context:
        return render(request, "portal/404.html", status=404)
    return render(request, "portal/staff/family_policies.html", context)


@staff_login_required
@require_GET
def staff_family_policy_print(request, family_slug, policy_slug):
    from .staff_services import get_family_policies_for_staff

    child_name = request.GET.get("child", "").strip()
    policy_data = get_family_policies_for_staff(family_slug)
    if not policy_data:
        return render(request, "portal/404.html", status=404)
    child_name, policy = _policy_from_family_data(policy_data, child_name, policy_slug)
    if not policy:
        return render(request, "portal/404.html", status=404)
    back_url = reverse("portal_staff_family_policies", kwargs={"family_slug": family_slug})
    return _render_single_policy_print(
        request,
        policy=policy,
        child_name=child_name,
        family_name=policy_data["family_name"],
        breadcrumb=f'<a href="{back_url}">Signed policies</a> / Print',
        back_url=back_url,
        context_builder=lambda req, title, **kwargs: _staff_context(title, **kwargs),
    )


@staff_login_required
@require_GET
def staff_member_policies_print(request):
    from .staff_services import get_family_policies_for_staff, get_member_summaries_for_unit

    if portal_is_live():
        unit = _staff_unit(request)
        summaries = get_member_summaries_for_unit(unit) if unit else []
        families_data = []
        for summary in summaries:
            data = get_family_policies_for_staff(summary["slug"])
            if data:
                families_data.append(data)
        print_scope = unit.name if unit else "Your unit"
    else:
        families_data = []
        for summary in get_member_policy_summaries(FAMILIES):
            data = get_family_policies(summary["slug"])
            if data:
                families_data.append(data)
        print_scope = "School 18"
    return render(
        request,
        "portal/staff/member_policies_print.html",
        _staff_context(
            "Member policies — print all",
            families_data=families_data,
            print_scope=print_scope,
            policies_per_child=POLICIES_PER_CHILD,
        ),
    )


@staff_login_required
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


@staff_login_required
@require_GET
def staff_school_bus_report(request):
    unit = _staff_unit(request) if _portal_data_live() else None
    if unit:
        from .staff_services import (
            build_school_bus_roster,
            filter_school_bus_roster,
            school_bus_report_meta,
            school_bus_roster_school_names,
        )

        all_sections = build_school_bus_roster(unit)
        report_meta = school_bus_report_meta(unit)
    else:
        from .demo_data import MEDICAL_REPORT_META, SCHOOL_BUS_ROSTER_SECTIONS
        from .staff_services import filter_school_bus_roster, school_bus_roster_school_names

        all_sections = SCHOOL_BUS_ROSTER_SECTIONS
        report_meta = MEDICAL_REPORT_META
    all_schools = school_bus_roster_school_names(all_sections)
    selected_schools = [name for name in request.GET.getlist("school") if str(name).strip()]
    selected_set = set(selected_schools) if selected_schools else set(all_schools)
    visible_sections = filter_school_bus_roster(all_sections, selected_schools)
    school_sections = all_sections
    total_children = sum(len(section["children"]) for section in visible_sections)
    return render(
        request,
        "portal/staff/school_bus_report.html",
        _staff_context(
            "School bus roster",
            report_meta=report_meta,
            school_sections=school_sections,
            all_schools=all_schools,
            selected_schools=selected_set,
            school_filter_active=bool(selected_schools),
            total_children=total_children,
            staff_page_slug="reports",
        ),
    )


@staff_login_required
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


@staff_login_required
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


@staff_login_required
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


@staff_login_required
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


@staff_login_required
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
    bundle = _family_billing_bundle(request, "staff", family_slug)
    if not bundle:
        return render(request, "portal/404.html", status=404)
    context = _family_hub_context(
        request,
        "staff",
        family_slug,
        f"{bundle['billing']['family_name']} billing",
        "billing",
        **bundle,
    )
    if not context:
        return render(request, "portal/404.html", status=404)
    return render(request, "portal/staff/family_billing.html", context)


@require_GET
@admin_login_required
def admin_family_billing(request, family_slug):
    bundle = _family_billing_bundle(request, "admin", family_slug)
    if not bundle:
        return render(request, "portal/404.html", status=404)
    context = _family_hub_context(
        request,
        "admin",
        family_slug,
        f"{bundle['billing']['family_name']} account",
        "billing",
        **bundle,
    )
    if not context:
        return render(request, "portal/404.html", status=404)
    return render(request, "portal/staff/family_billing.html", context)


@require_GET
@admin_login_required
def admin_family_policies(request, family_slug):
    from .staff_services import get_family_policies_for_staff

    policy_data = get_family_policies_for_staff(family_slug, family_id=_family_id_from_request(request) or None)
    if not policy_data:
        return render(request, "portal/404.html", status=404)
    _attach_family_policy_print_urls(policy_data, "portal_admin_family_policy_print", family_slug)
    family_meta = next((f for f in ADMIN_MEMBER_FAMILIES if f["slug"] == family_slug), {})
    if _portal_families_live():
        from .member_admin import resolve_family

        live_family = resolve_family(family_slug=family_slug, family_id=_family_id_from_request(request) or None)
        if live_family:
            family_meta = {
                "id": live_family.pk,
                "slug": live_family.slug,
                "name": live_family.name,
                "unit": live_family.unit.name if live_family.unit_id else "",
            }
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
                family_id=family_meta.get("id"),
                family_tab="policies",
                **_family_neighbor_nav(request, "admin", family_slug, "policies", family_meta.get("id")),
            ),
        ),
    )


@require_GET
@admin_login_required
def admin_family_applications(request, family_slug):
    return _render_family_applications(request, "admin", family_slug)


@require_GET
@admin_login_required
def admin_member_type_report(request):
    import csv

    from django.http import HttpResponse

    from .member_admin import member_reports

    rows = member_reports() if _portal_data_live() else []
    billing_filter = request.GET.get("billing", "").strip()
    plan_filter = request.GET.get("plan", "").strip()
    if billing_filter:
        rows = [row for row in rows if row["billing"].lower() == billing_filter.lower()]
    if plan_filter:
        rows = [row for row in rows if plan_filter.lower() in row["plan"].lower()]
    if request.GET.get("format") == "csv":
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="member-type-report.csv"'
        writer = csv.writer(response)
        writer.writerow(["Child", "Family", "Unit", "School", "Billing", "Payment plan", "Status"])
        for row in rows:
            writer.writerow([row["child"], row["family"], row["unit"], row["school"], row["billing"], row["plan"], row["status"]])
        return response
    billing_types = sorted({row["billing"] for row in member_reports()} if _portal_data_live() else {"4Cs", "Private pay", "Other"})
    plans = sorted({row["plan"] for row in member_reports()} if _portal_data_live() else {"Weekly", "Bi-Weekly", "Monthly"})
    return render(
        request,
        "portal/admin/member_type_report.html",
        _finalize_admin_context(
            request,
            _portal_context(
                "admin",
                "Member type & payment plan report",
                admin_page_slug="reports",
                member_rows=rows,
                billing_filter=billing_filter,
                plan_filter=plan_filter,
                billing_types=billing_types,
                payment_plans=plans,
            ),
        ),
    )


@require_GET
@admin_login_required
def admin_family_policy_print(request, family_slug, policy_slug):
    from .staff_services import get_family_policies_for_staff

    child_name = request.GET.get("child", "").strip()
    policy_data = get_family_policies_for_staff(family_slug)
    if not policy_data:
        return render(request, "portal/404.html", status=404)
    child_name, policy = _policy_from_family_data(policy_data, child_name, policy_slug)
    if not policy:
        return render(request, "portal/404.html", status=404)
    back_url = reverse("portal_admin_family_policies", kwargs={"family_slug": family_slug})
    return _render_single_policy_print(
        request,
        policy=policy,
        child_name=child_name,
        family_name=policy_data["family_name"],
        breadcrumb=f'<a href="{back_url}">Signed policies</a> / Print',
        back_url=back_url,
        context_builder=lambda req, title, **kwargs: _finalize_admin_context(
            req,
            _portal_context("admin", title, admin_page_slug="member-policies", **kwargs),
        ),
    )


@staff_login_required
@require_GET
def staff_family_pickup(request, family_slug):
    profile = _staff_family_profile(family_slug, unit=_staff_unit(request))
    if not profile:
        return render(request, "portal/404.html", status=404)
    pickup_data = family_authorized_pickup(profile, family_slug=family_slug if _portal_families_live() else None)
    context = _staff_family_context(
        family_slug,
        f"{profile['family_name']} — Authorized pickup",
        "pickup",
        request=request,
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


@staff_login_required
@require_GET
def staff_family_detail(request, family_slug):
    unit = _staff_unit(request)
    profile = _staff_family_profile(family_slug, unit=unit)
    if not profile:
        return render(request, "portal/404.html", status=404)
    context = _staff_family_context(
        family_slug,
        f"{profile['family_name']} family",
        "profile",
        request=request,
        unit=unit,
        medical_alert_types=MEDICAL_ALERT_TYPES,
    )
    return render(request, "portal/staff/family_detail.html", context)


@staff_login_required
@require_GET
def staff_family_email(request, family_slug):
    unit = _staff_unit(request)
    profile = _staff_family_profile(family_slug, unit=unit)
    if not profile:
        return render(request, "portal/404.html", status=404)
    context = _staff_family_context(
        family_slug,
        f"{profile['family_name']} — email parent",
        "email",
        request=request,
        unit=unit,
        email_send_url="portal_staff_family_email_send",
    )
    return render(request, "portal/staff/family_email.html", context)


@require_GET
@admin_login_required
def admin_family_email(request, family_slug):
    context = _family_hub_context(
        request,
        "admin",
        family_slug,
        "Email parent",
        "email",
    )
    if not context:
        return render(request, "portal/404.html", status=404)
    context["page_title"] = f"{context['profile']['family_name']} — email parent"
    return render(request, "portal/staff/family_email.html", context)


@require_GET
@admin_login_required
def admin_family_detail(request, family_slug):
    context = _family_hub_context(
        request,
        "admin",
        family_slug,
        "Family account",
        "profile",
    )
    if not context:
        return render(request, "portal/404.html", status=404)
    context["page_title"] = f"Family account — {context['profile']['family_name']}"
    return render(request, "portal/staff/family_detail.html", context)


@require_GET
@admin_login_required
def admin_family_pickup(request, family_slug):
    context = _family_hub_context(request, "admin", family_slug, "Authorized pickup", "pickup")
    if not context:
        return render(request, "portal/404.html", status=404)
    context["pickup_data"] = family_authorized_pickup(
        context["profile"],
        family_slug=family_slug if _portal_families_live() else None,
    )
    return render(request, "portal/staff/family_pickup.html", context)


@require_GET
@admin_login_required
def admin_family_incidents(request, family_slug):
    context = _family_hub_context(request, "admin", family_slug, "Incidents", "incidents")
    if not context:
        return render(request, "portal/404.html", status=404)
    if _portal_data_live():
        family_incidents = get_incidents_for_family_live(family_slug)
        incidents_by_child = get_incidents_by_child_for_family_live(family_slug)
    else:
        family_incidents = get_incidents_for_family(family_slug)
        incidents_by_child = get_incidents_by_child_for_family(family_slug)
    context["family_incidents"] = family_incidents
    context["incident_print_children"] = [
        {"child": name, "count": len(incs)} for name, incs in incidents_by_child.items() if incs
    ]
    return render(request, "portal/staff/family_incidents.html", context)


def _render_family_plans(request, area, family_slug):
    bundle = _family_billing_bundle(request, area, family_slug)
    if not bundle:
        return render(request, "portal/404.html", status=404)
    context = _family_hub_context(
        request,
        area,
        family_slug,
        f"{bundle['billing']['family_name']} plans",
        "plans",
        **bundle,
    )
    if not context:
        return render(request, "portal/404.html", status=404)
    return render(request, "portal/staff/family_plans.html", context)


@staff_login_required
@require_GET
def staff_family_plans(request, family_slug):
    return _render_family_plans(request, "staff", family_slug)


@require_GET
@admin_login_required
def admin_family_plans(request, family_slug):
    return _render_family_plans(request, "admin", family_slug)


def _render_family_agency(request, area, family_slug):
    from .agency_services import get_agency_accounts_for_family

    unit = None if area == "admin" else _staff_unit(request)
    context = _family_hub_context(request, area, family_slug, "4Cs", "agency")
    if not context:
        return render(request, "portal/404.html", status=404)
    context["agency_accounts"] = get_agency_accounts_for_family(family_slug, unit)
    return render(request, "portal/staff/family_agency.html", context)


@staff_login_required
@require_GET
def staff_family_agency(request, family_slug):
    return _render_family_agency(request, "staff", family_slug)


@require_GET
@admin_login_required
def admin_family_agency(request, family_slug):
    return _render_family_agency(request, "admin", family_slug)


@require_GET
@admin_login_required
def admin_family_refund(request, family_slug):
    bundle = _family_billing_bundle(request, "admin", family_slug)
    if not bundle:
        return render(request, "portal/404.html", status=404)
    context = _family_hub_context(
        request,
        "admin",
        family_slug,
        f"{bundle['billing']['family_name']} refund",
        "billing",
        **bundle,
    )
    if not context:
        return render(request, "portal/404.html", status=404)
    return render(request, "portal/staff/family_refund.html", context)


def _render_family_applications(request, area, family_slug):
    from enrollment.portal_integration import staff_application_row
    from .member_admin import applications_for_family_admin, resolve_family

    unit = None if area == "admin" else _staff_unit(request)
    family = resolve_family(family_slug=family_slug, family_id=_family_id_from_request(request) or None, unit=unit)
    if not family:
        return render(request, "portal/404.html", status=404)
    linked, extras = applications_for_family_admin(family)
    family_applications = []
    print_name = "portal_admin_application_policy_print" if area == "admin" else "portal_staff_application_policy_print"
    for app in linked:
        app_slug = str(app.reference)
        family_applications.append(
            {
                "app_slug": app_slug,
                "application": _application_with_policy_print_urls(
                    application_detail_dict(app),
                    print_name,
                    app_slug=app_slug,
                ),
                **_application_location_context(app),
            }
        )
    context = _family_hub_context(
        request,
        area,
        family_slug,
        f"{family.name} — applications",
        "applications",
        family=family,
        family_id=family.pk,
        family_applications=family_applications,
        unmatched_applications=[staff_application_row(app) for app in extras],
    )
    if not context:
        return render(request, "portal/404.html", status=404)
    return render(request, "portal/admin/family_applications.html", context)


@staff_login_required
@require_GET
def staff_family_applications(request, family_slug):
    return _render_family_applications(request, "staff", family_slug)


@staff_login_required
@require_GET
def staff_family_incidents(request, family_slug):
    unit = _staff_unit(request)
    profile = _staff_family_profile(family_slug, unit=unit)
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
        request=request,
        unit=unit,
        family_incidents=family_incidents,
        incident_print_children=[
            {"child": name, "count": len(incs)}
            for name, incs in incidents_by_child.items()
            if incs
        ],
    )
    return render(request, "portal/staff/family_incidents.html", context)


@staff_login_required
@require_GET
def staff_application_detail(request, app_slug):
    if _portal_data_live():
        app = get_application_by_reference(app_slug)
        if app:
            on_waitlist = app.status == "waitlist"
            application_urls = _application_portal_urls("staff", app_slug, waitlist=on_waitlist)
            application = _application_with_policy_print_urls(
                application_detail_dict(app),
                "portal_staff_application_policy_print",
                app_slug=app_slug,
            )
            return render(
                request,
                "portal/staff/application_detail.html",
                _staff_context(
                    f"Application — {app.student_first_name} {app.student_last_name}".strip(),
                    request=request,
                    application=application,
                    app_slug=app_slug,
                    is_live_application=True,
                    staff_page_slug="waitlist" if on_waitlist else "applications",
                    application_urls=application_urls,
                    can_approve_this_application=_can_approve_this_application(request, app, "staff"),
                    **_application_location_context(app),
                ),
            )
    application = _application_with_policy_print_urls(
        enrich_demo_application(STAFF_APPLICATION_DETAILS.get(app_slug, {})),
        "portal_staff_application_policy_print",
        app_slug=app_slug,
    )
    if not application.get("child_name"):
        return render(request, "portal/404.html", status=404)
    on_waitlist = (application.get("status_slug") or "") == "waitlist"
    return render(
        request,
        "portal/staff/application_detail.html",
        _staff_context(
            f"Application — {application['child_name']}",
            application=application,
            app_slug=app_slug,
            staff_page_slug="waitlist" if on_waitlist else "applications",
            application_urls=_application_portal_urls("staff", app_slug, waitlist=on_waitlist),
            can_approve_this_application=False,
        ),
    )


@require_GET
@admin_login_required
def admin_application_detail(request, app_slug):
    if _portal_data_live():
        app = get_application_by_reference(app_slug)
        if app:
            on_waitlist = app.status == "waitlist"
            application_urls = _application_portal_urls("admin", app_slug, waitlist=on_waitlist)
            application = _application_with_policy_print_urls(
                application_detail_dict(app),
                "portal_admin_application_policy_print",
                app_slug=app_slug,
            )
            return render(
                request,
                "portal/staff/application_detail.html",
                _portal_context(
                    "admin",
                    f"Application — {app.student_first_name} {app.student_last_name}".strip(),
                    application=application,
                    app_slug=app_slug,
                    is_live_application=True,
                    admin_page_slug="waitlist" if on_waitlist else "applications",
                    application_urls=application_urls,
                    can_approve_this_application=True,
                    **_application_location_context(app),
                ),
            )
    application = _application_with_policy_print_urls(
        enrich_demo_application(STAFF_APPLICATION_DETAILS.get(app_slug, {})),
        "portal_admin_application_policy_print",
        app_slug=app_slug,
    )
    if not application.get("child_name"):
        return render(request, "portal/404.html", status=404)
    on_waitlist = (application.get("status_slug") or "") == "waitlist"
    return render(
        request,
        "portal/staff/application_detail.html",
        _portal_context(
            "admin",
            f"Application — {application['child_name']}",
            application=application,
            app_slug=app_slug,
            admin_page_slug="waitlist" if on_waitlist else "applications",
            application_urls=_application_portal_urls("admin", app_slug, waitlist=on_waitlist),
            can_approve_this_application=True,
        ),
    )


@staff_login_required
@require_GET
def staff_application_print(request, app_slug):
    application_urls = _application_portal_urls("staff", app_slug)
    if _portal_data_live():
        app = get_application_by_reference(app_slug)
        if app:
            application = application_detail_dict(app)
            return render(
                request,
                "portal/staff/application_print.html",
                _staff_context(
                    f"Application — {app.student_first_name} {app.student_last_name}".strip(),
                    application=application,
                    app_slug=app_slug,
                    application_urls=application_urls,
                ),
            )
    application = enrich_demo_application(STAFF_APPLICATION_DETAILS.get(app_slug, {}))
    if not application.get("child_name"):
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
@staff_login_required
def staff_application_policy_print(request, app_slug, policy_slug):
    app = get_application_by_reference(app_slug)
    if not app:
        return render(request, "portal/404.html", status=404)
    from enrollment.policy_display import get_application_policy

    policy = get_application_policy(app, policy_slug)
    if not policy:
        return render(request, "portal/404.html", status=404)
    back_url = reverse("portal_staff_application_detail", kwargs={"app_slug": app_slug})
    child_name = f"{app.student_first_name} {app.student_last_name}".strip()
    return _render_single_policy_print(
        request,
        policy=policy,
        child_name=child_name,
        family_name=app.family_name,
        breadcrumb=f'<a href="{back_url}">Application</a> / Print policy',
        back_url=back_url,
        context_builder=lambda req, title, **kwargs: _staff_context(title, **kwargs),
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
    application = enrich_demo_application(STAFF_APPLICATION_DETAILS.get(app_slug, {}))
    if not application.get("child_name"):
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


@require_GET
@admin_login_required
def admin_application_policy_print(request, app_slug, policy_slug):
    app = get_application_by_reference(app_slug)
    if not app:
        return render(request, "portal/404.html", status=404)
    from enrollment.policy_display import get_application_policy

    policy = get_application_policy(app, policy_slug)
    if not policy:
        return render(request, "portal/404.html", status=404)
    back_url = reverse("portal_admin_application_detail", kwargs={"app_slug": app_slug})
    child_name = f"{app.student_first_name} {app.student_last_name}".strip()
    return _render_single_policy_print(
        request,
        policy=policy,
        child_name=child_name,
        family_name=app.family_name,
        breadcrumb=f'<a href="{back_url}">Application</a> / Print policy',
        back_url=back_url,
        context_builder=lambda req, title, **kwargs: _finalize_admin_context(
            req,
            _portal_context("admin", title, admin_page_slug="applications", **kwargs),
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


@require_http_methods(["GET", "POST"])
def portal_area_switch(request, area):
    from .staff_auth import activate_portal_area

    if area not in {"staff", "admin"}:
        return redirect("portal_home")
    if activate_portal_area(request, area):
        if area == "staff":
            next_url = request.POST.get("next") or request.GET.get("next") or ""
            if next_url.startswith("/portal/staff"):
                return redirect(next_url)
            return redirect("portal_staff_page", page="dashboard")
        next_url = request.POST.get("next") or request.GET.get("next") or ""
        if next_url.startswith("/portal/admin"):
            return redirect(next_url)
        return redirect("portal_admin_page", page="dashboard")
    if area == "admin":
        return redirect("portal_admin_login")
    return redirect("portal_staff_login")


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
        "waitlist": "portal/admin/waitlist.html",
        "agencies": "portal/admin/agencies.html",
        "fees": "portal/admin/fees.html",
        "member-billing": "portal/admin/member_billing.html",
        "billing-settings": "portal/admin/billing_settings.html",
        "billing-permissions": "portal/admin/billing_permissions.html",
        "scholarships": "portal/admin/scholarships.html",
        "discounts": "portal/admin/discounts.html",
        "collections": "portal/admin/collections.html",
        "member-policies": "portal/admin/member_policies.html",
        "field-trips": "portal/admin/field_trips.html",
        "checkin-settings": "portal/admin/checkin_settings.html",
        "reports": "portal/admin/reports.html",
        "messages": "portal/messages/messages.html",
        "communications": "portal/admin/communications.html",
        "parent-emails": "portal/admin/parent_emails.html",
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
    show_add_admin = request.GET.get("add_admin") == "1"
    show_add_agency = request.GET.get("add") == "1"
    context = _portal_context(
        "admin",
        page.replace("-", " ").title(),
        admin_page_slug=page,
        show_add_program=show_add_program,
        show_add_unit=show_add_unit,
        show_add_staff=show_add_staff,
        show_add_admin=show_add_admin,
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
            from .member_admin import pending_4cs_children

            context["pending_4cs"] = pending_4cs_children()
        else:
            context["agencies"] = ADMIN_AGENCIES
            context["units"] = UNITS
            context["agency_child_rates"] = []
            context["editing_agency"] = None
            context["pending_4cs"] = []
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
        unit_slug = request.GET.get("unit", "")
        charge_mode = request.GET.get("mode", "weekly_tuition")
        billing_filter = request.GET.get("billing_type", "")
        custom_amount = request.GET.get("custom_amount", "")
        custom_description = request.GET.get("custom_description", "")
        show_preview = request.GET.get("preview") == "1"
        if context.get("portal_live"):
            from .admin_services import get_units_live
            from .billing_services import (
                build_bulk_charge_preview,
                get_org_ledger_live,
                get_scheduled_plan_charges,
                run_due_plan_charges,
            )

            posted = run_due_plan_charges()
            if posted:
                messages.success(request, f"Posted {len(posted)} scheduled plan charge(s).")
            context["units"] = get_units_live()
            context["scheduled_plan_charges"] = get_scheduled_plan_charges()
            context["bulk_filter"] = {
                "unit": unit_slug,
                "mode": charge_mode,
                "billing_type": billing_filter,
                "custom_amount": custom_amount,
                "custom_description": custom_description,
            }
            context["bulk_preview"] = (
                build_bulk_charge_preview(
                    unit_slug=unit_slug or None,
                    charge_mode=charge_mode,
                    billing_filter=billing_filter,
                    custom_amount=custom_amount or None,
                    custom_description=custom_description,
                )
                if show_preview
                else []
            )
            context["ledger_entries"] = get_org_ledger_live(unit_slug=unit_slug or None)
            context["show_bulk_preview"] = show_preview
            from .billing_services import default_entry_date

            context["today"] = default_entry_date().isoformat()
        else:
            context["units"] = UNITS
            context["bulk_filter"] = {"unit": "", "mode": "weekly_tuition", "billing_type": "", "custom_amount": "", "custom_description": ""}
            context["bulk_preview"] = []
            context["ledger_entries"] = []
            context["show_bulk_preview"] = False
            context["scheduled_plan_charges"] = []
            context["today"] = date.today().isoformat()
    if page == "billing-settings":
        if context.get("portal_live"):
            from .admin_services import get_member_families_live, get_parent_accounts_live

            context["families"] = get_member_families_live()
            context["parent_accounts"] = get_parent_accounts_live()
        else:
            context["families"] = ADMIN_MEMBER_FAMILIES
            context["parent_accounts"] = []
    if page == "families":
        if context.get("portal_live"):
            from .admin_services import get_admin_families_live, get_units_live
            from .member_admin import families_without_applications, families_without_parent_login

            context["families"] = get_admin_families_live()
            context["units"] = get_units_live()
            context["families_without_login"] = families_without_parent_login()
            context["families_without_applications"] = families_without_applications()
        else:
            from .family_list import demo_family_list_rows

            context["families"] = demo_family_list_rows("admin")
            context["units"] = UNITS
            context["families_without_login"] = []
            context["families_without_applications"] = []
        context["family_count"] = len({row["slug"] for row in context["families"]})
        if context.get("portal_live"):
            from .member_admin import known_school_names

            context["school_options"] = known_school_names()
    if page == "applications":
        unit_filter = request.GET.get("unit", "")
        context["applications_tab"] = "all"
        if context.get("portal_live"):
            from .admin_services import get_units_live
            from .member_admin import applications_without_accounts

            context["applications"] = applications_for_admin(unit_filter or None)
            context["units"] = get_units_live()
            context["applications_unit_filter"] = unit_filter
            context["applications_without_accounts"] = applications_without_accounts()
        else:
            context["applications"] = [{**row, "unit": row.get("unit", "School 18"), "unit_slug": row.get("unit_slug", ""), "status_slug": row.get("status", "under-review").lower().replace(" ", "-")} for row in STAFF_APPLICATIONS]
            context["units"] = UNITS
            context["applications_unit_filter"] = unit_filter
            context["applications_without_accounts"] = []
    if page == "waitlist":
        unit_filter = request.GET.get("unit", "")
        context["applications_tab"] = "waitlist"
        context["waitlist_next"] = request.get_full_path()
        if context.get("portal_live"):
            context["applications"] = waitlist_for_admin(unit_filter or None)
            from .admin_services import get_units_live

            context["units"] = get_units_live()
            context["applications_unit_filter"] = unit_filter
        else:
            context["applications"] = _demo_waitlist_rows()
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
            "Approve applications — let this staff member approve after-school and other enrollment applications in the staff portal.",
            "Approve waitlist — let this staff member approve before care waitlist applications in the staff portal. Admin can always approve.",
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
            from .admin_services import get_member_families_live, get_member_policy_summaries_live

            families = get_member_families_live()
            context["org_policies"] = get_org_policies_admin()
            context["member_summaries"] = get_member_policy_summaries_live()
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
    if page == "field-trips":
        from .field_trip_services import DEFAULT_PERMISSION_SLIP

        context["default_permission_slip"] = DEFAULT_PERMISSION_SLIP
        if context.get("portal_live"):
            from .admin_services import get_units_live
            from .field_trip_services import get_admin_field_trips

            context["units"] = get_units_live()
            context["field_trips"] = get_admin_field_trips()
        else:
            context["units"] = UNITS
            context["field_trips"] = []
    if page == "collections":
        if context.get("portal_live"):
            from .admin_services import get_admin_families_live
            from .models import PortalPriorBalance

            context["prior_balances"] = PortalPriorBalance.objects.select_related("linked_family", "linked_family__unit")
            context["families"] = get_admin_families_live()
        else:
            context["prior_balances"] = []
            context["families"] = ADMIN_MEMBER_FAMILIES
    if page == "parent-emails":
        if context.get("portal_live"):
            from .member_admin import parent_email_recipients

            context["parent_recipients"] = parent_email_recipients()
        else:
            context["parent_recipients"] = []
        context["preselect_family_id"] = request.GET.get("family_id", "")
    if page == "discounts":
        if context.get("portal_live"):
            from .admin_services import get_member_families_live
            from .models import PortalDiscountAssignment, PortalDiscountPlan

            context["discount_plans"] = PortalDiscountPlan.objects.all()
            context["discount_assignments"] = PortalDiscountAssignment.objects.select_related("family", "plan", "family__unit")[:50]
            context["families"] = get_member_families_live()
        else:
            context["discount_plans"] = []
            context["discount_assignments"] = []
            context["families"] = ADMIN_MEMBER_FAMILIES
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
    from .staff_services import get_family_policies_for_staff

    families_data = []
    if _portal_data_live():
        from .admin_services import get_member_policy_summaries_live

        for summary in get_member_policy_summaries_live():
            data = get_family_policies_for_staff(summary["slug"])
            if data:
                families_data.append(data)
    else:
        for summary in get_member_policy_summaries(ADMIN_MEMBER_FAMILIES):
            data = get_family_policies(summary["slug"])
            if data:
                families_data.append(data)
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


PARENT_PREVIEW_TEMPLATES = {
    "dashboard": "portal/parent/dashboard.html",
    "profile": "portal/parent/profile.html",
    "applications": "portal/parent/applications.html",
    "policies": "portal/parent/policies.html",
    "billing": "portal/parent/billing.html",
    "receipts": "portal/parent/receipts.html",
    "drop-in": "portal/parent/drop_in.html",
    "field-trips": "portal/parent/field_trips.html",
    "account": "portal/parent/account.html",
    "tax-statements": "portal/parent/tax_statements.html",
    "support": "portal/support/support.html",
}


@require_GET
@admin_login_required
def admin_parent_preview(request, family_slug, page="dashboard"):
    """Admin troubleshooting view — browse parent portal pages with sensitive data masked."""
    from enrollment.models import EnrollmentApplication

    from .models import PortalFamily, PortalParentAccount
    from enrollment.portal_integration import parent_application_list_items
    from .parent_services import (
        build_parent_preview_live,
        get_account_live,
        get_drop_in_live,
        get_parent_announcement_live,
        get_parent_policy_data_live,
        get_receipts_live,
        get_tax_eligibility_live,
    )

    template = PARENT_PREVIEW_TEMPLATES.get(page)
    if not template:
        return render(request, "portal/404.html", status=404)

    from .member_admin import resolve_family
    from .support_view import (
        mask_billing_card_mentions,
        mask_parent_account_cards,
        mask_receipt_card_mentions,
        start_support_view,
    )

    family = resolve_family(family_slug=family_slug, family_id=_family_id_from_request(request) or None)
    if _portal_data_live() and not family:
        messages.error(request, "Family not found.")
        return redirect("portal_admin_page", page="families")
    if _portal_data_live() and family:
        account = PortalParentAccount.objects.filter(family=family).select_related("user").first()
        preview = build_parent_preview_live(family, account)
        account_data = mask_parent_account_cards(get_account_live(account) if account else {})
        if request.user.is_authenticated:
            start_support_view(family, request.user)
        context = _portal_context(
            "parent",
            page.replace("-", " ").title(),
            admin_page_slug="communications",
            admin_support_preview=True,
            admin_preview_family_slug=family.slug,
            admin_preview_family_id=family.pk,
            hide_card_details=True,
            parent_preview=preview,
            parent_page_slug=page,
            parent_pay_query="",
            parent_announcement=get_parent_announcement_live(family),
            receipts=mask_receipt_card_mentions(get_receipts_live(family) if account else []),
            drop_in=get_drop_in_live(account) if account else {},
            account=account_data,
            policy_data=get_parent_policy_data_live(family),
            policies_per_child=POLICIES_PER_CHILD,
            parent_stripe_enabled=False,
            parent_authenticated=True,
            portal_live=False,
            parent_avatar={
                "initials": family.name[:2].upper(),
                "photo_url": "",
                "display_name": family.primary_contact or family.name,
            },
            parent_can_manage_photo=False,
            pending_profile_changes=[],
            preview_family_name=family.name,
        )
        context.update(
            _family_neighbor_nav(
                request,
                "admin",
                family.slug,
                "parentview",
                family.pk,
                parent_page=page,
            )
        )
        if page == "billing":
            context["billing"] = mask_billing_card_mentions(preview["billing"])
        if page == "profile":
            context["profile"] = preview["profile"]
        if page == "dashboard":
            context["dashboard"] = preview["dashboard"]
        if page == "field-trips":
            from .field_trip_services import get_family_field_trips

            context["field_trips"] = get_family_field_trips(family)
        if page == "applications" and account:
            context["parent_applications"] = parent_application_list_items(account.family)
        if page == "policies":
            _attach_parent_policy_print_urls(context["policy_data"])
            context["policies_signed_count"] = context["policy_data"]["signed_count"]
            context["policies_total"] = context["policy_data"]["total_count"]
        if page == "tax-statements":
            context["tax_settings"] = TAX_STATEMENT_SETTINGS
            context["tax_eligibility"] = get_tax_eligibility_live(family)
        if page == "receipts":
            paid_receipts = [r for r in context.get("receipts", []) if r.get("reference")]
            context["receipt_previews"] = [
                enrich_receipt_for_print(r, preview_key_for_family(family), family=family) for r in paid_receipts[:2]
            ]
        if page == "support":
            context = _support_context("parent", "Support", request, preview_family=family.slug)
            context["admin_support_preview"] = True
            context["admin_preview_family_slug"] = family.slug
            context["admin_preview_family_id"] = family.pk
            context["hide_card_details"] = True
            context["parent_page_slug"] = "support"
            context["portal_area"] = "parent"
            context["preview_family_name"] = family.name
            context["portal_live"] = False
            context.update(
                _family_neighbor_nav(
                    request,
                    "admin",
                    family.slug,
                    "parentview",
                    family.pk,
                    parent_page=page,
                )
            )
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
        hide_card_details=True,
        portal_live=False,
    )
    context["account"] = mask_parent_account_cards(context.get("account") or {})
    context["receipts"] = mask_receipt_card_mentions(context.get("receipts") or [])
    context["parent_stripe_enabled"] = False
    if page == "billing":
        context["billing"] = mask_billing_card_mentions(context["parent_preview"]["billing"])
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
        context["hide_card_details"] = True
        context["portal_live"] = False
    context.update(
        _family_neighbor_nav(
            request,
            "admin",
            family_slug,
            "parentview",
            _family_id_from_request(request) or None,
            parent_page=page,
        )
    )
    return render(request, template, context)


@require_GET
@admin_login_required
def admin_parent_preview_sample(request, page="dashboard"):
    """Open the demo parent portal so admins can check updates without a parent login."""
    template = PARENT_PREVIEW_TEMPLATES.get(page)
    if not template:
        return render(request, "portal/404.html", status=404)
    request.GET = request.GET.copy()
    request.GET["pay"] = request.GET.get("pay") or "private-pay"
    context = _parent_context(
        request,
        page.replace("-", " ").title(),
        page_slug=page,
        admin_support_preview=True,
        admin_preview_sample=True,
        hide_card_details=True,
        preview_family_name="Sample parent portal",
        portal_live=False,
    )
    from .support_view import mask_billing_card_mentions, mask_parent_account_cards, mask_receipt_card_mentions

    context["account"] = mask_parent_account_cards(context.get("account") or {})
    context["receipts"] = mask_receipt_card_mentions(context.get("receipts") or [])
    context["parent_stripe_enabled"] = False
    context["admin_preview_family_slug"] = ""
    if page == "billing":
        context["billing"] = mask_billing_card_mentions(context["parent_preview"]["billing"])
    if page == "profile":
        context["profile"] = context["parent_preview"]["profile"]
    if page == "dashboard":
        context["dashboard"] = context["parent_preview"]["dashboard"]
    return render(request, template, context)


@require_http_methods(["GET", "POST"])
@admin_login_required
def admin_parent_preview_end(request, family_slug):
    from .member_admin import resolve_family
    from .support_view import end_support_view

    family = resolve_family(
        family_slug=family_slug,
        family_id=request.POST.get("family_id") or _family_id_from_request(request) or None,
    )
    if family:
        end_support_view(family)
        messages.success(request, f"Ended the parent-portal support view for {family.name}.")
        return redirect("portal_admin_family_detail", family_slug=family.slug)
    messages.error(request, "Family not found.")
    return redirect("portal_admin_page", page="families")


@require_POST
@staff_login_required_post
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
@staff_login_required_post
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
@staff_login_required_post
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
@staff_login_required_post
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
@staff_login_required_post
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
@staff_login_required_post
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
