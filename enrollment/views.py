import logging
import uuid
from datetime import date, datetime

from django.contrib.admin.views.decorators import staff_member_required
from django.core.mail import send_mail
from django.conf import settings
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from .forms import (
    CHILD_STEP_SLUGS,
    FAMILY_FIELD_NAMES,
    STEP_FORMS,
    STEP_ORDER,
    STEP_TITLES,
    EmergencyContactFormSet,
)
from .models import EmergencyContact, EnrollmentApplication, PolicySignature
from .policies_data import POLICIES, POLICY_BY_SLUG

logger = logging.getLogger(__name__)

SESSION_KEY = "enrollment_application"

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


def _create_application(data):
    data = _deserialize_for_model(data)
    data["needs_dale_ave_bus"] = data.get("program_location") == "dale_ave"
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
    family_group = uuid.uuid4()
    family_fields = {k: session_data[k] for k in FAMILY_FIELD_NAMES if k in session_data}
    applications = []
    for child_number, child_data in enumerate(session_data.get("children", []), start=1):
        merged = {**family_fields, **child_data}
        merged["family_group"] = family_group
        merged["child_number"] = child_number
        applications.append(_create_application(merged))
    return applications


def _notify_staff(application):
    print_url = settings.SITE_URL.rstrip("/") + reverse(
        "enrollment_print", args=[application.reference]
    )
    subject = f"[YEA] New enrollment application — {application.student_first_name} {application.student_last_name}"
    sibling_note = ""
    if application.family_group:
        sibling_count = EnrollmentApplication.objects.filter(
            family_group=application.family_group
        ).count()
        if sibling_count > 1:
            sibling_note = f"Child {application.child_number} of {sibling_count} in this family submission.\n"
    body = (
        f"A new enrollment application was submitted.\n\n"
        f"{sibling_note}"
        f"Student: {application.student_first_name} {application.student_last_name}\n"
        f"Program: {application.get_program_display()} — {application.get_program_location_display()}\n"
        f"Family: {application.family_name}\n"
        f"Family email: {application.primary_email}\n"
        f"Reference: {application.reference}\n\n"
        f"Print for your files (staff login required):\n{print_url}\n\n"
        f"Or open Django admin → Enrollment applications.\n"
    )
    send_mail(
        subject=subject,
        message=body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[settings.CONTACT_EMAIL],
        fail_silently=False,
    )


def _wizard_context(request, step, session_data, **extra):
    step_idx = _step_index(step)
    _ensure_children(session_data)
    child_index = session_data.get("current_child_index", 0)
    return {
        "step": step,
        "step_titles": STEP_TITLES,
        "step_order": STEP_ORDER,
        "step_index": step_idx,
        "prev_step": STEP_ORDER[step_idx - 1] if step_idx > 0 else None,
        "child_index": child_index,
        "child_number": child_index + 1,
        "child_count": _child_count(session_data),
        "policies": POLICIES if step == "policies" else None,
        **extra,
    }


@require_http_methods(["GET", "POST"])
def apply_wizard(request, step="family"):
    if step not in STEP_ORDER:
        return redirect("enrollment_apply", step="family")

    session_data = _get_session_data(request)
    _ensure_children(session_data)
    step_idx = _step_index(step)

    if step == "review":
        if request.method == "POST":
            if not session_data.get("children"):
                return redirect("enrollment_apply", step="family")
            applications = _create_applications(session_data.copy())
            family_group = applications[0].family_group
            if SESSION_KEY in request.session:
                del request.session[SESSION_KEY]
            for app in applications:
                try:
                    _notify_staff(app)
                except Exception:
                    logger.exception("Failed to send enrollment notification email")
            return redirect("enrollment_confirmation_group", family_group=family_group)
        return render(
            request,
            "enrollment/review.html",
            _wizard_context(
                request,
                step,
                session_data,
                data=session_data,
                policies=POLICIES,
            ),
        )

    if step == "add_child":
        if request.method == "POST":
            form = STEP_FORMS["add_child"](request.POST)
            if form.is_valid():
                if form.cleaned_data["add_another"] == "yes":
                    session_data["current_child_index"] = session_data.get("current_child_index", 0) + 1
                    session_data["children"].append({})
                    _save_session_data(request, session_data)
                    return redirect("enrollment_apply", step="program")
                return redirect("enrollment_apply", step="review")
        else:
            form = STEP_FORMS["add_child"]()
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
        billing_ok = True
        if emergency_formset is not None:
            billing_ok = emergency_formset.is_valid()
            filled = [
                f for f in emergency_formset
                if f.cleaned_data.get("first_name") or f.cleaned_data.get("last_name")
            ]
            if len(filled) < 2:
                billing_ok = False
                emergency_formset._non_form_errors = emergency_formset.error_class(
                    ["Two emergency contacts are required."]
                )

        if form.is_valid() and billing_ok:
            cleaned = form.cleaned_data.copy()
            if step == "family":
                for key in FAMILY_FIELD_NAMES:
                    if key in cleaned:
                        session_data[key] = cleaned[key]
            elif step == "policies":
                policy_payload = {}
                for policy in POLICIES:
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
            _save_session_data(request, session_data)
            return redirect("enrollment_apply", step=STEP_ORDER[step_idx + 1])
    else:
        if step == "family":
            initial = {k: session_data.get(k, "") for k in FAMILY_FIELD_NAMES}
        elif step == "policies":
            initial = {}
            for slug, payload in child_data.get("policies", {}).items():
                initial[f"{slug}__signature"] = payload.get("signature", "")
                initial[f"{slug}__date"] = payload.get("date")
                for key, value in payload.get("extra", {}).items():
                    initial[f"{slug}__{key}"] = value
        else:
            initial = {k: v for k, v in child_data.items() if k not in ("emergency_contacts", "policies")}
        form = form_class(initial=initial)
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
        ),
    )


def policy_detail(request, slug):
    policy = POLICY_BY_SLUG.get(slug)
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
        {"applications": applications, "family_group": family_group},
    )


@staff_member_required
def print_application(request, reference):
    application = get_object_or_404(EnrollmentApplication, reference=reference)
    return render(
        request,
        "enrollment/print.html",
        {
            "application": application,
            "policies": POLICIES,
            "policy_by_slug": POLICY_BY_SLUG,
        },
    )
