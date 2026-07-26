from datetime import date, datetime

from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, LogoutView
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from enrollment.policies_data import POLICIES, POLICY_BY_SLUG

from . import constants
from .forms import (
    STEP_ORDER,
    STEP_TITLES,
    BookingForm,
    EmergencyContactFormSet,
    STEP_FORMS,
)
from .models import (
    DropInBooking,
    DropInChild,
    DropInEmergencyContact,
    DropInFamilyProfile,
    DropInPolicySignature,
    DropInWaitlistEntry,
)
from .notifications import (
    notify_staff_new_booking,
    notify_staff_new_registration,
)
from .services import validate_booking, validate_waitlist_join, waitlist_count
from .stripe_checkout import confirm_booking_payment, create_dropin_checkout_session

SESSION_KEY = "dropin_registration"

FAMILY_FIELDS = [
    "family_name",
    "primary_email",
    "home_address",
    "primary_first_name",
    "primary_last_name",
    "primary_phone",
    "secondary_first_name",
    "secondary_last_name",
    "secondary_phone",
]

MEDICAL_FIELDS = [
    "doctor_name",
    "doctor_phone",
    "allergies",
    "no_known_allergies",
    "requires_allergy_plan",
    "requires_asthma_plan",
    "requires_epipen_plan",
    "has_medical_condition",
    "medical_condition_explain",
    "health_statement",
]


def _serialize_for_session(value):
    if isinstance(value, date) and not isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: _serialize_for_session(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_serialize_for_session(v) for v in value]
    return value


def _parse_date(value):
    if not value:
        return None
    if isinstance(value, date):
        return value
    return date.fromisoformat(value)


def _get_session_data(request):
    return request.session.get(SESSION_KEY, {})


def _save_session_data(request, data):
    request.session[SESSION_KEY] = _serialize_for_session(data)
    request.session.modified = True


def _step_index(step):
    return STEP_ORDER.index(step)


@transaction.atomic
def _create_profile_from_session(user, data):
    profile_data = {field: data.get(field, "") for field in FAMILY_FIELDS + MEDICAL_FIELDS}
    profile = DropInFamilyProfile.objects.create(user=user, **profile_data)

    child_data = data["child"]
    DropInChild.objects.create(
        profile=profile,
        first_name=child_data["first_name"],
        last_name=child_data["last_name"],
        gender=child_data["gender"],
        date_of_birth=_parse_date(child_data["date_of_birth"]),
        grade=child_data["grade"],
        school=child_data["school"],
    )

    for idx, contact in enumerate(data.get("emergency_contacts", []), start=1):
        DropInEmergencyContact.objects.create(profile=profile, order=idx, **contact)

    for slug, payload in data.get("policies", {}).items():
        policy = POLICY_BY_SLUG[slug]
        DropInPolicySignature.objects.create(
            profile=profile,
            policy_slug=slug,
            policy_title=policy["title"],
            signature_name=payload["signature"],
            signed_date=_parse_date(payload["date"]),
            extra_data=payload.get("extra", {}),
        )

    return profile


def index(request):
    return render(
        request,
        "dropin/index.html",
        {
            "fees": constants.FEE_DOLLARS,
            "deadlines": constants.DEADLINE_LABEL,
            "dropin_locations": constants.DROPIN_LOCATIONS_BY_PROGRAM,
        },
    )


class DropInLoginView(LoginView):
    template_name = "dropin/login.html"
    redirect_authenticated_user = True


class DropInLogoutView(LogoutView):
    next_page = "dropin_index"


@require_http_methods(["GET", "POST"])
def register_wizard(request, step="account"):
    if step not in STEP_ORDER:
        return redirect("dropin_register", step="account")

    if request.user.is_authenticated and hasattr(request.user, "dropin_profile"):
        messages.info(request, "You already have a drop-in account.")
        return redirect("dropin_dashboard")

    session_data = _get_session_data(request)
    step_idx = _step_index(step)

    if request.method == "POST":
        if step == "emergency":
            formset = EmergencyContactFormSet(request.POST)
            if formset.is_valid():
                session_data["emergency_contacts"] = formset.cleaned_data
                _save_session_data(request, session_data)
                return redirect("dropin_register", step=STEP_ORDER[step_idx + 1])
        elif step == "review":
            from django.contrib.auth.models import User

            user_id = session_data.get("user_id")
            if not user_id:
                return redirect("dropin_register", step="account")
            user = User.objects.get(pk=user_id)
            profile = _create_profile_from_session(user, session_data)
            login(request, user)
            request.session.pop(SESSION_KEY, None)
            notify_staff_new_registration(profile)
            messages.success(
                request,
                "Registration submitted. Our team will review your application — you can book drop-in days after approval.",
            )
            return redirect("dropin_dashboard")
        elif step == "account":
            form = STEP_FORMS["account"](request.POST)
            if form.is_valid():
                user = form.save()
                user.email = form.cleaned_data["email"]
                user.save(update_fields=["email"])
                session_data["user_id"] = user.pk
                _save_session_data(request, session_data)
                return redirect("dropin_register", step=STEP_ORDER[step_idx + 1])
        elif step == "policies":
            form = STEP_FORMS["policies"](request.POST)
            if form.is_valid():
                policies = {}
                for policy in POLICIES:
                    slug = policy["slug"]
                    entry = {
                        "signature": form.cleaned_data[f"{slug}__signature"],
                        "date": form.cleaned_data[f"{slug}__date"],
                        "extra": {},
                    }
                    for extra in policy.get("fields", []):
                        key = f"{slug}__{extra['name']}"
                        if key in form.cleaned_data:
                            entry["extra"][extra["name"]] = form.cleaned_data[key]
                    policies[slug] = entry
                session_data["policies"] = policies
                _save_session_data(request, session_data)
                return redirect("dropin_register", step=STEP_ORDER[step_idx + 1])
        elif step == "child":
            form = STEP_FORMS["child"](request.POST)
            if form.is_valid():
                session_data["child"] = form.cleaned_data
                _save_session_data(request, session_data)
                return redirect("dropin_register", step=STEP_ORDER[step_idx + 1])
        else:
            form = STEP_FORMS[step](request.POST)
            if form.is_valid():
                session_data.update(form.cleaned_data)
                _save_session_data(request, session_data)
                return redirect("dropin_register", step=STEP_ORDER[step_idx + 1])

    if step == "emergency":
        formset = EmergencyContactFormSet(initial=session_data.get("emergency_contacts"))
        return render(
            request,
            "dropin/steps/emergency.html",
            _wizard_context(step, session_data, formset=formset),
        )
    if step == "review":
        return render(request, "dropin/review.html", _wizard_context(step, session_data))

    if step == "account":
        form = STEP_FORMS["account"]()
    elif step == "policies":
        initial = {}
        for policy in POLICIES:
            slug = policy["slug"]
            saved = session_data.get("policies", {}).get(slug, {})
            initial[f"{slug}__signature"] = saved.get("signature", "")
            initial[f"{slug}__date"] = saved.get("date", "")
        form = STEP_FORMS["policies"](initial=initial)
    elif step == "child":
        form = STEP_FORMS["child"](initial=session_data.get("child"))
    else:
        form = STEP_FORMS[step](initial={k: session_data.get(k, "") for k in STEP_FORMS[step].base_fields})

    return render(
        request,
        f"dropin/steps/{step}.html",
        _wizard_context(step, session_data, form=form),
    )


def _wizard_context(step, session_data, form=None, formset=None):
    step_idx = _step_index(step)
    return {
        "step": step,
        "step_index": step_idx,
        "step_titles": STEP_TITLES,
        "step_order": STEP_ORDER,
        "prev_step": STEP_ORDER[step_idx - 1] if step_idx > 0 else None,
        "session_data": session_data,
        "policies": POLICIES,
        "form": form,
        "formset": formset,
    }


@login_required
def dashboard(request):
    try:
        profile = request.user.dropin_profile
    except DropInFamilyProfile.DoesNotExist:
        messages.info(request, "Complete drop-in registration to book days.")
        return redirect("dropin_register", step="account")

    bookings = profile.bookings.select_related("child").all()[:20]
    return render(
        request,
        "dropin/dashboard.html",
        {
            "profile": profile,
            "bookings": bookings,
            "fees": constants.FEE_DOLLARS,
            "deadlines": constants.DEADLINE_LABEL,
            "canceled": request.GET.get("canceled") == "1",
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def book(request):
    profile = get_object_or_404(DropInFamilyProfile, user=request.user)
    if not profile.is_booking_ready:
        messages.warning(
            request,
            "Your drop-in registration is pending approval. We'll email you when you can book days.",
        )
        return redirect("dropin_dashboard")

    show_waitlist = False

    if request.method == "POST":
        form = BookingForm(profile, request.POST)
        join_waitlist = request.POST.get("action") == "waitlist"

        if form.is_valid():
            child = form.cleaned_data["child"]
            program = form.cleaned_data["program"]
            location = form.cleaned_data["location"]
            care_date = form.cleaned_data["date"]

            if join_waitlist:
                ok, msg = validate_waitlist_join(
                    program, location, care_date, child, profile=profile
                )
                if ok:
                    DropInWaitlistEntry.objects.create(
                        profile=profile,
                        child=child,
                        program=program,
                        location=location,
                        date=care_date,
                    )
                    messages.success(
                        request,
                        f"Added to the waitlist for {care_date:%B %d, %Y}. We'll contact you if a spot opens up.",
                    )
                    return redirect("dropin_dashboard")
                messages.error(request, msg)
                show_waitlist = "full" in msg.lower() or "waitlist" in msg.lower()
            else:
                ok, msg = validate_booking(
                    program, location, care_date, child, profile=profile
                )
                if not ok:
                    messages.error(request, msg)
                    if "full" in msg.lower():
                        show_waitlist = True
                else:
                    amount_cents = int(constants.FEE_DOLLARS[program] * 100)
                    booking = DropInBooking.objects.create(
                        profile=profile,
                        child=child,
                        program=program,
                        location=location,
                        date=care_date,
                        amount_cents=amount_cents,
                    )
                    try:
                        session = create_dropin_checkout_session(request, booking)
                        booking.stripe_session_id = session.id
                        booking.save(update_fields=["stripe_session_id"])
                        return redirect(session.url, code=303)
                    except Exception as exc:
                        booking.delete()
                        messages.error(request, f"Unable to start payment: {exc}")
    else:
        form = BookingForm(profile)

    return render(
        request,
        "dropin/book.html",
        {
            "form": form,
            "profile": profile,
            "fees": constants.FEE_DOLLARS,
            "deadlines": constants.DEADLINE_LABEL,
            "show_waitlist": show_waitlist,
        },
    )


@staff_member_required
def daily_roster(request):
    from datetime import date as date_cls

    care_date = request.GET.get("date")
    program = request.GET.get("program", constants.PROGRAM_AFTER_SCHOOL)
    location = request.GET.get("location", "school_18")
    bookings = []
    waitlist = []
    capacity = None
    spots_left = None

    if care_date:
        care_date = date_cls.fromisoformat(care_date)
        bookings = (
            DropInBooking.objects.filter(
                date=care_date,
                program=program,
                location=location,
                status=DropInBooking.STATUS_PAID,
            )
            .select_related("child", "profile")
            .order_by("child__last_name", "child__first_name")
        )
        waitlist = (
            DropInWaitlistEntry.objects.filter(
                date=care_date,
                program=program,
                location=location,
                status=DropInWaitlistEntry.STATUS_WAITING,
            )
            .select_related("child", "profile")
            .order_by("created_at")
        )
        from .services import get_capacity, spots_remaining

        capacity = get_capacity(program, location, care_date)
        spots_left, _ = spots_remaining(program, location, care_date)

    context = {
        "care_date": care_date,
        "program": program,
        "location": location,
        "program_label": dict(constants.PROGRAM_CHOICES).get(program, program),
        "location_label": dict(constants.LOCATION_CHOICES).get(location, location),
        "program_choices": constants.PROGRAM_CHOICES,
        "location_choices": constants.LOCATION_CHOICES,
        "bookings": bookings,
        "waitlist": waitlist,
        "capacity": capacity,
        "spots_left": spots_left,
        "waitlist_count": len(waitlist),
        "print_mode": request.GET.get("print") == "1",
    }
    template = "dropin/roster_print.html" if context["print_mode"] and care_date else "dropin/roster.html"
    return render(request, template, context)


@login_required
def booking_success(request):
    ref = request.GET.get("ref")
    booking = get_object_or_404(DropInBooking, reference=ref, profile__user=request.user)
    if not booking.profile.is_booking_ready:
        messages.error(request, "This booking is not valid.")
        return redirect("dropin_dashboard")
    if confirm_booking_payment(booking):
        notify_staff_new_booking(booking)
    if booking.status != DropInBooking.STATUS_PAID:
        messages.warning(
            request,
            "Payment is still processing. Your booking will appear once payment is confirmed.",
        )
    else:
        messages.success(request, f"Drop-in booked for {booking.date:%B %d, %Y}.")
    return render(request, "dropin/booking_success.html", {"booking": booking})
