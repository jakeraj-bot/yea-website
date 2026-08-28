import logging
import uuid
from datetime import date, datetime

from django.contrib.auth import login
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.conf import settings
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from portal.parent_auth import get_parent_account, parent_login_required

from .notifications import send_application_submitted_emails

from .application_edit import (
    application_to_session_data,
    parent_can_edit_application,
    update_application_from_session,
)
from .application_review import resubmit_application

from .forms import (
    CHILD_STEP_SLUGS,
    FAMILY_FIELD_NAMES,
    STEP_FORMS,
    STEP_ORDER,
    STEP_TITLES,
    STEP_TAB_LABELS,
    EmergencyContactFormSet,
    PortalAccountForm,
)
from .models import EmergencyContact, EnrollmentApplication, PolicySignature
from .policies_data import POLICIES, POLICY_BY_SLUG
from .policies_loader import get_policies, get_policy_by_slug
from .portal_integration import (
    create_portal_account_from_enrollment,
    link_applications_to_family,
)
from .validators import validate_emergency_contacts

logger = logging.getLogger(__name__)

SESSION_KEY = "enrollment_application"
LINK_EXISTING_KEY = "enrollment_link_existing"


def _youtube_video_id(value):
    value = (value or "").strip()
    if not value:
        return ""
    if "youtu.be/" in value:
        return value.split("youtu.be/")[-1].split("?")[0].split("/")[0]
    if "youtube.com/shorts/" in value:
        return value.split("shorts/")[-1].split("?")[0].split("/")[0]
    if "embed/" in value:
        return value.split("embed/")[-1].split("?")[0].split("/")[0]
    if "v=" in value:
        return value.split("v=")[-1].split("&")[0]
    return value


def _apply_help_video_id(lang):
    en = _youtube_video_id(getattr(settings, "ENROLLMENT_HELP_VIDEO_EN", ""))
    es = _youtube_video_id(getattr(settings, "ENROLLMENT_HELP_VIDEO_ES", ""))
    if lang == "es":
        return es or en
    return en or es


def _apply_chrome_context(request):
    from .i18n import SUPPORTED_LANGUAGES, get_language, localized_step_tab_labels

    lang = get_language(request)
    return {
        "enrollment_lang": lang,
        "enrollment_languages": SUPPORTED_LANGUAGES,
        "step_tab_labels": localized_step_tab_labels(lang),
        "apply_help_video_id": _apply_help_video_id(lang),
    }


DATE_FIELDS = frozenset(
    {
        "student_dob",
        "payment_plan_signed_date",
        "four_cs_signed_date",
    }
)


def _serialize_for_session(value):
    if isinstance(value, date) and not isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: _serialize_for_session(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_serialize_for_session(v) for v in value]
    return value


def _deserialize_for_model(data):
    data = data.copy()
    for key in DATE_FIELDS:
        if data.get(key):
            data[key] = date.fromisoformat(data[key])
        elif key in data and not data[key]:
            data[key] = None
    if "policies" in data:
        policies = {}
        for slug, payload in data["policies"].items():
            entry = payload.copy()
            if entry.get("date"):
                entry["date"] = date.fromisoformat(entry["date"])
            policies[slug] = entry
        data["policies"] = policies
    return data


def _get_session_data(request):
    return request.session.get(SESSION_KEY, {})


def _save_session_data(request, data):
    request.session[SESSION_KEY] = _serialize_for_session(data)
    request.session.modified = True


def _step_index(step):
    return STEP_ORDER.index(step)


def _ensure_children(session_data):
    if "children" not in session_data:
        session_data["children"] = [{}]
    if "current_child_index" not in session_data:
        session_data["current_child_index"] = 0
    return session_data


def _current_child(session_data):
    session_data = _ensure_children(session_data)
    idx = session_data["current_child_index"]
    while len(session_data["children"]) <= idx:
        session_data["children"].append({})
    return session_data["children"][idx], idx


def _child_count(session_data):
    return len(session_data.get("children", []))


def _apply_program_preset(request, session_data):
    preset = (request.GET.get("program") or "").strip()
    valid_programs = {choice[0] for choice in EnrollmentApplication.PROGRAM_CHOICES}
    if preset not in valid_programs:
        return session_data
    session_data = _ensure_children(session_data)
    child, _ = _current_child(session_data)
    child["programs"] = [preset]
    child["program"] = preset
    from .locations import location_keys_for_program

    keys = location_keys_for_program(preset)
    location = (request.GET.get("location") or "").strip()
    if location and location in keys:
        child["program_location"] = location
    elif keys:
        child["program_location"] = keys[0]
    return session_data


def _create_application(data):
    data = _deserialize_for_model(data)
    data["needs_dale_ave_bus"] = data.get("program_location") == "dale_ave"
    if data.get("program") == "before_care" and not data.get("status"):
        data["status"] = "waitlist"
    emergency_data = data.pop("emergency_contacts", [])
    policy_data = data.pop("policies", {})

    app = EnrollmentApplication.objects.create(**data)
    for idx, contact in enumerate(emergency_data, start=1):
        if not contact.get("first_name") and not contact.get("last_name"):
            continue
        EmergencyContact.objects.create(application=app, order=idx, **contact)

    for slug, payload in policy_data.items():
        policy = POLICY_BY_SLUG[slug]
        PolicySignature.objects.create(
            application=app,
            policy_slug=slug,
            policy_title=policy["title"],
            signature_name=payload["signature"],
            signed_date=payload["date"],
            extra_data=payload.get("extra", {}),
        )
    return app


def _create_applications(session_data):
    from .add_program import programs_for_child_data

    family_group = uuid.uuid4()
    family_fields = {k: session_data[k] for k in FAMILY_FIELD_NAMES if k in session_data}
    applications = []
    for child_index, child_data in enumerate(session_data.get("children", []), start=1):
        programs = programs_for_child_data(child_data)
        for program in programs:
            merged = {**family_fields, **child_data, "program": program}
            merged.pop("programs", None)
            merged["family_group"] = family_group
            merged["child_number"] = child_index
            applications.append(_create_application(merged))
    return applications


def _max_step_index(session_data):
    return min(session_data.get("max_step_index", 0), len(STEP_ORDER) - 1)


def _mark_step_reached(session_data, step_idx):
    session_data["max_step_index"] = max(session_data.get("max_step_index", 0), step_idx)
    return session_data


def _is_editing(session_data):
    return bool(session_data.get("editing_reference"))


def _editing_application(session_data):
    if not _is_editing(session_data):
        return None
    return EnrollmentApplication.objects.filter(reference=session_data["editing_reference"]).first()


def _policy_form_fields(form):
    grouped = {}
    for field in form:
        slug = field.name.split("__", 1)[0]
        grouped.setdefault(slug, []).append(field)
    return grouped


def _wizard_context(request, step, session_data, **extra):
    from .i18n import get_language, localized_step_tab_labels, localized_step_titles

    step_idx = _step_index(step)
    lang = get_language(request)
    _ensure_children(session_data)
    child_index = session_data.get("current_child_index", 0)
    editing_app = _editing_application(session_data)
    step_order = [s for s in STEP_ORDER if s != "add_child"] if editing_app else STEP_ORDER
    program_location_rules = ""
    if step == "program":
        from .locations import program_location_rules_json

        program_location_rules = program_location_rules_json()
    return {
        **_apply_chrome_context(request),
        "step": step,
        "step_titles": localized_step_titles(lang),
        "step_tab_labels": localized_step_tab_labels(lang),
        "step_order": step_order,
        "step_index": step_idx,
        "max_step_index": _max_step_index(session_data),
        "prev_step": STEP_ORDER[step_idx - 1] if step_idx > 0 else None,
        "child_index": child_index,
        "child_number": child_index + 1,
        "child_count": _child_count(session_data),
        "policies": get_policies(get_language(request)) if step == "policies" else None,
        "is_editing": bool(editing_app),
        "editing_child_name": (
            f"{editing_app.student_first_name} {editing_app.student_last_name}".strip()
            if editing_app
            else ""
        ),
        "staff_change_message": editing_app.staff_message if editing_app else "",
        "is_adding_child": bool(session_data.get("adding_to_existing_family")),
        "four_cs_contact_email": settings.CONTACT_EMAIL,
        "program_location_rules": program_location_rules,
        **extra,
    }


def _prefill_family_from_portal(session_data, account):
    user = account.user
    family = account.family
    session_data.setdefault("family_name", family.name)
    session_data.setdefault("primary_email", user.email)
    session_data.setdefault("primary_email_address", user.email)
    session_data.setdefault("primary_first_name", user.first_name)
    session_data.setdefault("primary_last_name", user.last_name)
    if family.primary_contact and not user.first_name:
        parts = family.primary_contact.split(" ", 1)
        session_data.setdefault("primary_first_name", parts[0])
        session_data.setdefault("primary_last_name", parts[1] if len(parts) > 1 else "")
    return session_data


def _prefill_family_from_application(session_data, family):
    latest = (
        EnrollmentApplication.objects.filter(portal_family=family)
        .order_by("-submitted_at")
        .first()
    )
    if not latest:
        return session_data
    for key in FAMILY_FIELD_NAMES:
        value = getattr(latest, key, "")
        if value:
            session_data[key] = value
    return session_data


def _start_session_for_existing_family(account):
    session_data = _prefill_family_from_portal({}, account)
    session_data = _prefill_family_from_application(session_data, account.family)
    session_data["children"] = [{}]
    session_data["current_child_index"] = 0
    session_data["max_step_index"] = 0
    session_data["adding_to_existing_family"] = True
    return session_data


@require_http_methods(["GET"])
def apply_start(request):
    account = get_parent_account(request.user) if request.user.is_authenticated else None
    context = {
        **_apply_chrome_context(request),
        "portal_account": account,
    }
    return render(request, "enrollment/apply_gate.html", context)


@require_http_methods(["GET"])
def apply_help(request):
    context = _apply_chrome_context(request)
    context["apply_help_page"] = True
    return render(request, "enrollment/apply_help.html", context)


@require_http_methods(["POST"])
def set_language(request):
    from .i18n import set_language as store_language

    store_language(request, request.POST.get("lang", "en"))
    next_url = request.POST.get("next") or reverse("apply")
    if next_url.startswith("/"):
        return redirect(next_url)
    return redirect("apply")


@require_http_methods(["GET"])
@parent_login_required
def apply_add_child(request):
    account = get_parent_account(request.user)
    if SESSION_KEY in request.session:
        del request.session[SESSION_KEY]
    session_data = _start_session_for_existing_family(account)
    request.session[LINK_EXISTING_KEY] = True
    _save_session_data(request, session_data)
    messages.info(
        request,
        f"Apply for another child on your {account.family.name} family account. Your household information is prefilled.",
    )
    return redirect("enrollment_apply", step="family")


@require_http_methods(["GET"])
@parent_login_required
def apply_edit_start(request, reference):
    account = get_parent_account(request.user)
    application = get_object_or_404(EnrollmentApplication, reference=reference)
    if not parent_can_edit_application(account, application):
        messages.error(
            request,
            "This application cannot be edited right now. You can only update applications when staff requests changes.",
        )
        return redirect(
            f"{reverse('portal_parent_page', kwargs={'page': 'application'})}?ref={reference}"
        )

    session_data = application_to_session_data(application)
    _save_session_data(request, session_data)
    messages.info(
        request,
        f"Update {application.student_first_name}'s application, then resubmit for staff review.",
    )
    return redirect("enrollment_apply", step="family")


@require_http_methods(["GET", "POST"])
def apply_wizard(request, step="family"):
    if step not in STEP_ORDER:
        return redirect("enrollment_apply", step="family")

    session_data = _get_session_data(request)
    session_data = _apply_program_preset(request, session_data)
    _ensure_children(session_data)
    step_idx = _step_index(step)
    portal_account = get_parent_account(request.user) if request.user.is_authenticated else None
    editing = _is_editing(session_data)

    if step_idx > _max_step_index(session_data):
        return redirect("enrollment_apply", step=STEP_ORDER[_max_step_index(session_data)])

    if editing and step == "add_child":
        return redirect("enrollment_apply", step="review")

    if step == "family" and request.method == "GET" and not session_data.get("family_name"):
        if portal_account:
            if request.GET.get("existing") == "1":
                session_data = _start_session_for_existing_family(portal_account)
                request.session[LINK_EXISTING_KEY] = True
                _save_session_data(request, session_data)
            elif not editing:
                return redirect("apply")
        elif not request.GET.get("new"):
            return redirect("apply")

    if editing and not portal_account:
        return redirect(f"{settings.PORTAL_PARENT_LOGIN_URL}?next={request.get_full_path()}")

    if step == "review":
        from .form_i18n import localize_form
        from .i18n import get_language

        if request.method == "POST":
            if not session_data.get("children"):
                return redirect("enrollment_apply", step="family")
            if editing:
                application = _editing_application(session_data)
                if not application or not parent_can_edit_application(portal_account, application):
                    messages.error(request, "This application is no longer open for editing.")
                    if SESSION_KEY in request.session:
                        del request.session[SESSION_KEY]
                    return redirect("portal_parent_page", page="applications")
                update_application_from_session(application, session_data.copy())
                resubmit_application(application)
                if SESSION_KEY in request.session:
                    del request.session[SESSION_KEY]
                messages.success(
                    request,
                    f"Application for {application.student_first_name} {application.student_last_name} resubmitted for review.",
                )
                return redirect("portal_parent_page", page="applications")
            if portal_account and not request.session.get(LINK_EXISTING_KEY) and not editing:
                request.session[LINK_EXISTING_KEY] = True
            portal_form = None
            if not portal_account:
                portal_form = PortalAccountForm(request.POST)
                lang = get_language(request)
                localize_form(portal_form, lang)
                if not portal_form.is_valid():
                    return render(
                        request,
                        "enrollment/review.html",
                        _wizard_context(
                            request,
                            step,
                            session_data,
                            data=session_data,
                            policies=get_policies(get_language(request)),
                            portal_form=portal_form,
                            portal_account=portal_account,
                        ),
                    )
            applications = _create_applications(session_data.copy())
            family_group = applications[0].family_group
            linked_existing = bool(portal_account) and not editing
            if linked_existing:
                link_applications_to_family(applications, portal_account.family)
            else:
                family, user = create_portal_account_from_enrollment(
                    session_data,
                    portal_form.cleaned_data["username"],
                    portal_form.cleaned_data["password1"],
                )
                link_applications_to_family(applications, family)
                login(request, user)
            if SESSION_KEY in request.session:
                del request.session[SESSION_KEY]
            if LINK_EXISTING_KEY in request.session:
                del request.session[LINK_EXISTING_KEY]
            for app in applications:
                send_application_submitted_emails(app)
            if linked_existing:
                child_names = ", ".join(
                    f"{app.student_first_name} {app.student_last_name}".strip() for app in applications
                )
                messages.success(
                    request,
                    f"Application submitted for {child_names}. Track status anytime in your parent portal.",
                )
                return redirect("portal_parent_page", page="applications")
            return redirect("enrollment_confirmation_group", family_group=family_group)
        portal_form = None if portal_account or editing else PortalAccountForm()
        if portal_form:
            localize_form(portal_form, get_language(request))
        return render(
            request,
            "enrollment/review.html",
            _wizard_context(
                request,
                step,
                session_data,
                data=session_data,
                policies=get_policies(get_language(request)),
                portal_form=portal_form,
                portal_account=portal_account,
            ),
        )

    if step == "add_child":
        if request.method == "POST":
            form = STEP_FORMS["add_child"](request.POST)
            if form.is_valid():
                if form.cleaned_data["add_another"] == "yes":
                    session_data["current_child_index"] = session_data.get("current_child_index", 0) + 1
                    session_data["children"].append({})
                    session_data["max_step_index"] = _step_index("program")
                    _save_session_data(request, session_data)
                    return redirect("enrollment_apply", step="program")
                session_data = _mark_step_reached(session_data, _step_index("review"))
                _save_session_data(request, session_data)
                return redirect("enrollment_apply", step="review")
        else:
            form = STEP_FORMS["add_child"]()
        from .form_i18n import localize_form
        from .i18n import get_language

        lang = get_language(request)
        localize_form(form, lang)
        return render(
            request,
            "enrollment/steps/add_child.html",
            _wizard_context(request, step, session_data, form=form),
        )

    form_class = STEP_FORMS[step]
    emergency_formset = None
    child_data, child_index = _current_child(session_data)

    if step == "billing":
        emergency_formset = EmergencyContactFormSet(
            request.POST if request.method == "POST" else None,
            prefix="emergency",
            initial=child_data.get("emergency_contacts"),
        )

    if request.method == "POST":
        form = form_class(request.POST)
        from .form_i18n import localize_form, localize_formset, localize_policy_form
        from .i18n import get_language

        lang = get_language(request)
        localize_form(form, lang)
        if step == "policies":
            localize_policy_form(form, lang)
        localize_formset(emergency_formset, lang)
        billing_ok = True
        if emergency_formset is not None:
            billing_ok = emergency_formset.is_valid()
            if billing_ok:
                billing_ok = validate_emergency_contacts(emergency_formset, session_data, lang)

        if form.is_valid() and billing_ok:
            cleaned = form.cleaned_data.copy()
            if step == "family":
                for key in FAMILY_FIELD_NAMES:
                    if key in cleaned:
                        session_data[key] = cleaned[key]
            elif step == "policies":
                policy_payload = {}
                for policy in get_policies(get_language(request)):
                    slug = policy["slug"]
                    extra = {}
                    for field in policy.get("fields", []):
                        key = f"{slug}__{field['name']}"
                        if key in cleaned:
                            extra[field["name"]] = cleaned.pop(key)
                    policy_payload[slug] = {
                        "signature": cleaned.pop(f"{slug}__signature"),
                        "date": cleaned.pop(f"{slug}__date"),
                        "extra": extra,
                    }
                child_data["policies"] = policy_payload
            elif step == "billing":
                contacts = []
                for form_item in emergency_formset:
                    contacts.append(form_item.cleaned_data)
                child_data["emergency_contacts"] = contacts
                child_data.update(cleaned)
            elif step in CHILD_STEP_SLUGS:
                child_data.update(cleaned)

            session_data["children"][child_index] = child_data
            session_data = _mark_step_reached(session_data, step_idx + 1)
            _save_session_data(request, session_data)
            next_step = STEP_ORDER[step_idx + 1]
            if editing and next_step == "add_child":
                next_step = "review"
            return redirect("enrollment_apply", step=next_step)
    else:
        from .form_i18n import localize_form, localize_formset, localize_policy_form
        from .i18n import get_language

        lang = get_language(request)
        if step == "family":
            initial = {k: session_data.get(k, "") for k in FAMILY_FIELD_NAMES}
        elif step == "policies":
            initial = {}
            today = date.today()
            for slug, payload in child_data.get("policies", {}).items():
                initial[f"{slug}__signature"] = payload.get("signature", "")
                initial[f"{slug}__date"] = payload.get("date") or today
                for key, value in payload.get("extra", {}).items():
                    initial[f"{slug}__{key}"] = value
            for policy in get_policies(lang):
                slug = policy["slug"]
                initial.setdefault(f"{slug}__date", today)
        else:
            initial = {k: v for k, v in child_data.items() if k not in ("emergency_contacts", "policies")}
            if step == "program":
                if child_data.get("programs"):
                    initial["programs"] = list(child_data["programs"])
                elif child_data.get("program"):
                    initial["programs"] = [child_data["program"]]
        form = form_class(initial=initial)
        localize_form(form, lang)
        if step == "policies":
            localize_policy_form(form, lang)
        localize_formset(emergency_formset, lang)
        if emergency_formset is None and step == "billing":
            emergency_formset = EmergencyContactFormSet(
                prefix="emergency",
                initial=child_data.get("emergency_contacts") or [{}, {}, {}],
            )

    return render(
        request,
        f"enrollment/steps/{step}.html",
        _wizard_context(
            request,
            step,
            session_data,
            form=form,
            emergency_formset=emergency_formset,
            policy_form_fields=_policy_form_fields(form) if step == "policies" else None,
        ),
    )


def policy_detail(request, slug):
    from .i18n import get_language

    policy = get_policy_by_slug(slug, get_language(request))
    if not policy:
        from django.http import Http404
        raise Http404
    return render(request, "enrollment/policy_detail.html", {"policy": policy})


def confirmation(request, reference):
    application = get_object_or_404(EnrollmentApplication, reference=reference)
    return render(request, "enrollment/confirmation.html", {"application": application})


def confirmation_group(request, family_group):
    applications = EnrollmentApplication.objects.filter(family_group=family_group).order_by("child_number")
    if not applications.exists():
        from django.http import Http404
        raise Http404
    return render(
        request,
        "enrollment/confirmation_group.html",
        {
            "applications": applications,
            "family_group": family_group,
            "has_before_care_waitlist": applications.filter(program="before_care").exists(),
        },
    )


@require_http_methods(["GET", "POST"])
@parent_login_required
def apply_add_before_care(request, reference):
    from .add_program import can_add_before_care_for_application, create_before_care_from_application
    from .locations import get_enrollment_location_choices, get_location_label, location_keys_for_program

    account = get_parent_account(request.user)
    application = get_object_or_404(EnrollmentApplication, reference=reference)
    if application.portal_family_id != account.family_id:
        messages.error(request, "You can only add before care for children on your family account.")
        return redirect("portal_parent_page", page="applications")

    if not can_add_before_care_for_application(application):
        messages.error(request, "Before care is already on the waitlist for this child, or is not available.")
        return redirect("portal_parent_page", page="applications")

    child_name = f"{application.student_first_name} {application.student_last_name}".strip()
    location_keys = location_keys_for_program("before_care")
    location_choices = [(key, label) for key, label in get_enrollment_location_choices() if key in location_keys]
    default_location = application.program_location if application.program_location in location_keys else ""
    if not default_location and application.program_location == "dale_ave" and "school_18" in location_keys:
        default_location = "school_18"
    if not default_location and location_keys:
        default_location = location_keys[0]
    location_label = get_location_label(default_location) if default_location else "School 18"

    if request.method == "POST":
        try:
            new_app = create_before_care_from_application(
                application,
                program_location=request.POST.get("program_location", "").strip() or None,
            )
            messages.success(
                request,
                f"Before care waitlist request submitted for {child_name}. We'll contact you when a spot opens.",
            )
            return redirect(f"{reverse('portal_parent_page', kwargs={'page': 'application'})}?ref={new_app.reference}")
        except ValueError as exc:
            messages.error(request, str(exc))
            return redirect("portal_parent_page", page="applications")

    return render(
        request,
        "enrollment/add_before_care_confirm.html",
        {
            "application": application,
            "child_name": child_name,
            "location_label": location_label,
            "location_choices": location_choices,
            "default_location": default_location,
        },
    )


@staff_member_required
def print_application(request, reference):
    from enrollment.policy_display import get_application_policies

    application = get_object_or_404(
        EnrollmentApplication.objects.prefetch_related("policy_signatures"),
        reference=reference,
    )
    return render(
        request,
        "enrollment/print.html",
        {
            "application": application,
            "signed_policies": get_application_policies(application),
        },
    )
