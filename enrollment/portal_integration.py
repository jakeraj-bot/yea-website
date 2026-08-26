"""Connect enrollment applications to the parent portal."""

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify

from portal.models import PortalFamily, PortalParentAccount, PortalUnit

from .models import EnrollmentApplication
from .policy_display import get_application_policies
from .locations import applications_queryset_for_unit, get_location_label

LOCATION_TO_UNIT_SLUG = {
    "school_18": "school-18",
    "school_26": "school-26",
    "dale_ave": "school-18",
    "caldwell": "caldwell",
}

PAYMENT_TO_BILLING_TYPE = {
    "private_pay": "Private pay",
    "4cs": "4Cs",
    "other": "Other",
}

STATUS_LABELS = {
    "under_review": "Under review",
    "waitlist": "Waitlist",
    "approved": "Approved",
    "pending_documents": "Pending documents",
    "enrolled": "Enrolled",
    "declined": "Declined",
}


def _unit_for_location(program_location):
    from .locations import get_unit_for_enrollment_key

    unit = get_unit_for_enrollment_key(program_location)
    if unit:
        return unit
    slug = LOCATION_TO_UNIT_SLUG.get(program_location, "school-18")
    unit = PortalUnit.objects.filter(slug=slug, is_active=True).first()
    if unit:
        return unit
    return PortalUnit.objects.filter(is_active=True).order_by("id").first()


def _unique_family_slug(unit, family_name):
    base = slugify(family_name) or "family"
    slug = base
    suffix = 2
    while PortalFamily.objects.filter(unit=unit, slug=slug).exists():
        slug = f"{base}-{suffix}"
        suffix += 1
    return slug


def _billing_type_from_session(session_data, child_data):
    payment = child_data.get("payment_method") or session_data.get("payment_method")
    return PAYMENT_TO_BILLING_TYPE.get(payment, "Private pay")


def _program_label_from_child(child_data):
    program = child_data.get("program", "after_school")
    return dict(EnrollmentApplication.PROGRAM_CHOICES).get(program, "After-school program")


@transaction.atomic
def create_portal_account_from_enrollment(session_data, username, password):
    family_fields = session_data
    first_child = (session_data.get("children") or [{}])[0]
    unit = _unit_for_location(first_child.get("program_location", "school_18"))
    if not unit:
        raise RuntimeError("Portal is not set up yet. Run: python manage.py seed_portal")

    primary_name = " ".join(
        part
        for part in [family_fields.get("primary_first_name", ""), family_fields.get("primary_last_name", "")]
        if part
    ).strip()

    family = PortalFamily.objects.create(
        unit=unit,
        slug=_unique_family_slug(unit, family_fields.get("family_name", "Family")),
        name=family_fields.get("family_name", "Family"),
        primary_contact=primary_name,
        balance=0,
        billing_type=_billing_type_from_session(session_data, first_child),
        program_label=_program_label_from_child(first_child),
        status="Pending enrollment",
    )

    User = get_user_model()
    from portal.usernames import portal_username

    user = User.objects.create_user(
        username=portal_username("parent", username.strip()),
        email=(family_fields.get("primary_email") or family_fields.get("primary_email_address", "")).strip(),
        password=password,
        first_name=family_fields.get("primary_first_name", "").strip(),
        last_name=family_fields.get("primary_last_name", "").strip(),
    )
    PortalParentAccount.objects.create(user=user, family=family)
    return family, user


def link_applications_to_family(applications, family):
    for app in applications:
        app.portal_family = family
        if not app.status:
            app.status = "under_review"
        app.save(update_fields=["portal_family", "status"])


def link_applications_by_email(family, email):
    if not email:
        return 0
    return EnrollmentApplication.objects.filter(
        primary_email__iexact=email.strip(),
        portal_family__isnull=True,
    ).update(portal_family=family, status="under_review")


def application_to_portal_dict(app):
    contacts = [
        {
            "name": f"{contact.first_name} {contact.last_name}".strip(),
            "phone": contact.phone,
        }
        for contact in app.emergency_contacts.all()
    ]
    signed_policies = get_application_policies(app)
    return {
        "reference": str(app.reference),
        "status": STATUS_LABELS.get(app.status, "Under review"),
        "status_slug": (app.status or "under_review").replace("_", "-"),
        "staff_message": app.staff_message or "",
        "submitted": timezone.localtime(app.submitted_at).strftime("%B %d, %Y"),
        "submitted_short": timezone.localtime(app.submitted_at).strftime("%b %d, %Y"),
        "child_name": f"{app.student_first_name} {app.student_last_name}",
        "program": app.get_program_display(),
        "program_location": app.program_location,
        "location": get_location_label(app.program_location),
        "family_name": app.family_name,
        "student_dob": app.student_dob.strftime("%B %d, %Y"),
        "grade": app.get_student_grade_display(),
        "primary_parent": f"{app.primary_first_name} {app.primary_last_name}".strip(),
        "primary_email": app.primary_email,
        "primary_phone": app.primary_phone,
        "home_address": app.home_address,
        "student_school": app.student_school or "",
        "payment_method": app.get_payment_method_display(),
        "payment_method_key": app.payment_method,
        "payment_method_other": app.payment_method_other or "",
        "payment_plan": app.get_payment_plan_display(),
        "membership_fee_agreed": "Yes" if app.membership_fee_agreed == "yes" else "No",
        "emergency_contacts": contacts,
        "policies_signed": sum(1 for policy in signed_policies if policy["signed"]),
        "policies_total": len(signed_policies),
        "signed_policies": signed_policies,
        "family_slug": app.portal_family.slug if app.portal_family_id else "",
        "family_id": app.portal_family_id or "",
    }


def application_list_item(app):
    from .add_program import can_add_before_care_for_application

    data = application_to_portal_dict(app)
    return {
        "reference": data["reference"],
        "child_name": data["child_name"],
        "program": data["program"],
        "location": data["location"].split(" — ")[0],
        "submitted": data["submitted_short"],
        "status": data["status"],
        "status_slug": data["status_slug"],
        "can_edit": app.status == "pending_documents",
        "can_add_before_care": can_add_before_care_for_application(app),
    }


def get_applications_for_family(family):
    return EnrollmentApplication.objects.filter(portal_family=family).order_by("-submitted_at")


def family_display_label(family):
    """Disambiguate families that share the same last name."""
    dupes = PortalFamily.objects.filter(unit=family.unit, name__iexact=family.name).count()
    if dupes <= 1:
        return family.name
    account = PortalParentAccount.objects.filter(family=family).select_related("user").first()
    if account and account.user.email:
        return f"{family.name} ({account.user.email})"
    if family.primary_contact:
        return f"{family.name} ({family.primary_contact})"
    return f"{family.name} ({family.slug})"


def _application_family_label(app):
    if app.portal_family_id:
        return family_display_label(app.portal_family)
    return app.family_name


def staff_application_row(app):
    from .locations import get_unit_for_enrollment_key

    unit_name = ""
    unit_slug = ""
    if app.portal_family_id and getattr(app.portal_family, "unit_id", None):
        unit_name = app.portal_family.unit.name
        unit_slug = app.portal_family.unit.slug
    elif app.program_location:
        unit = get_unit_for_enrollment_key(app.program_location)
        if unit:
            unit_name = unit.name
            unit_slug = unit.slug
    return {
        "slug": str(app.reference),
        "child": f"{app.student_first_name} {app.student_last_name}".strip(),
        "family": _application_family_label(app),
        "family_slug": app.portal_family.slug if app.portal_family_id else "",
        "family_id": app.portal_family_id or "",
        "has_parent_login": bool(
            app.portal_family_id
            and PortalParentAccount.objects.filter(family_id=app.portal_family_id).exists()
        ),
        "unit": unit_name or "—",
        "unit_slug": unit_slug,
        "submitted": timezone.localtime(app.submitted_at).strftime("%b %d, %Y"),
        "program": app.get_program_display().replace(" program", ""),
        "school": app.student_school or "—",
        "status": STATUS_LABELS.get(app.status, "Under review"),
        "status_slug": (app.status or "under_review").replace("_", "-"),
        "returning": False,
    }


def staff_application_detail(app):
    data = application_to_portal_dict(app)
    data.update(
        {
            "id": app.pk,
            "family_id": app.portal_family_id or "",
            "has_parent_login": bool(
                app.portal_family_id
                and PortalParentAccount.objects.filter(family_id=app.portal_family_id).exists()
            ),
            "returning_member": False,
            "membership_required": app.membership_fee_agreed == "yes",
            "internal_note": app.internal_note or "",
            "staff_message": app.staff_message or "",
            "can_review": app.status in {"under_review", "pending_documents", "waitlist"},
            "status_slug": (app.status or "under_review").replace("_", "-"),
            "reviewed_at": timezone.localtime(app.reviewed_at).strftime("%B %d, %Y at %-I:%M %p")
            if app.reviewed_at
            else "",
            "student_first_name": app.student_first_name,
            "student_last_name": app.student_last_name,
            "student_grade": app.student_grade,
            "student_dob_iso": app.student_dob.isoformat() if app.student_dob else "",
            "primary_first_name": app.primary_first_name,
            "primary_last_name": app.primary_last_name,
            "allergies": app.allergies or "",
            "no_known_allergies": app.no_known_allergies,
            "medical_condition_explain": app.medical_condition_explain or "",
            "has_disability": app.get_has_disability_display() if app.has_disability else "",
            "has_special_needs": app.get_has_special_needs_display() if app.has_special_needs else "",
            "requires_medication": app.get_requires_medication_display() if app.requires_medication else "",
            "doctor_name": app.doctor_name or "",
            "doctor_phone": app.doctor_phone or "",
            "secondary_parent": f"{app.secondary_first_name} {app.secondary_last_name}".strip(),
            "secondary_email": app.secondary_email_address or "",
            "secondary_phone": app.secondary_phone or "",
            "program_key": app.program,
            "payment_plan_key": app.payment_plan,
            "grade_choices": EnrollmentApplication.GRADE_CHOICES,
            "program_choices": EnrollmentApplication.PROGRAM_CHOICES,
            "payment_method_choices": EnrollmentApplication.PAYMENT_METHOD_CHOICES,
            "payment_plan_choices": EnrollmentApplication.PAYMENT_PLAN_CHOICES,
            **application_neighbors(app),
        }
    )
    return data


OPEN_REVIEW_STATUSES = ("under_review", "pending_documents", "waitlist")


def application_neighbors(app, unit=None):
    qs = EnrollmentApplication.objects.all()
    if unit:
        qs = applications_queryset_for_unit(unit)
    slugs = [str(row.reference) for row in qs.order_by("-submitted_at")]
    current = str(app.reference)
    try:
        idx = slugs.index(current)
    except ValueError:
        return {"prev_slug": "", "next_slug": "", "queue_position": 0, "queue_total": len(slugs)}
    return {
        "prev_slug": slugs[idx - 1] if idx > 0 else "",
        "next_slug": slugs[idx + 1] if idx < len(slugs) - 1 else "",
        "queue_position": idx + 1,
        "queue_total": len(slugs),
    }


def next_reviewable_application(app, unit=None):
    qs = EnrollmentApplication.objects.filter(status__in=OPEN_REVIEW_STATUSES).exclude(pk=app.pk)
    if unit:
        qs = applications_queryset_for_unit(unit).filter(status__in=OPEN_REVIEW_STATUSES).exclude(pk=app.pk)
    following = qs.filter(submitted_at__lte=app.submitted_at).order_by("-submitted_at").first()
    return following or qs.order_by("-submitted_at").first()


def applications_for_staff(unit=None):
    qs = (
        applications_queryset_for_unit(unit)
        if unit
        else EnrollmentApplication.objects.none()
    )
    return [
        staff_application_row(app)
        for app in qs.select_related("portal_family", "portal_family__unit").prefetch_related("emergency_contacts").order_by(
            "-submitted_at"
        )
    ]


def applications_for_admin(unit_slug=None):
    if unit_slug:
        unit = PortalUnit.objects.filter(slug=unit_slug, is_active=True).first()
        qs = applications_queryset_for_unit(unit) if unit else EnrollmentApplication.objects.none()
    else:
        qs = EnrollmentApplication.objects.all()
    return [
        staff_application_row(app)
        for app in qs.select_related("portal_family", "portal_family__unit").prefetch_related("emergency_contacts").order_by(
            "-submitted_at"
        )
    ]


def _waitlist_rows(qs):
    rows = []
    ordered = (
        qs.filter(status="waitlist")
        .select_related("portal_family", "portal_family__unit")
        .prefetch_related("emergency_contacts")
        .order_by("submitted_at", "id")
    )
    for index, app in enumerate(ordered, start=1):
        row = staff_application_row(app)
        row["waitlist_position"] = index
        row["submitted"] = timezone.localtime(app.submitted_at).strftime("%b %d, %Y %-I:%M %p")
        rows.append(row)
    return rows


def waitlist_for_staff(unit=None):
    qs = applications_queryset_for_unit(unit) if unit else EnrollmentApplication.objects.none()
    return _waitlist_rows(qs)


def waitlist_for_admin(unit_slug=None):
    if unit_slug:
        unit = PortalUnit.objects.filter(slug=unit_slug, is_active=True).first()
        qs = applications_queryset_for_unit(unit) if unit else EnrollmentApplication.objects.none()
    else:
        qs = EnrollmentApplication.objects.all()
    return _waitlist_rows(qs)


def get_application_by_reference(reference):
    try:
        ref = reference if hasattr(reference, "hex") else __import__("uuid").UUID(str(reference))
    except (ValueError, AttributeError, TypeError):
        return None
    return (
        EnrollmentApplication.objects.filter(reference=ref)
        .select_related("portal_family")
        .prefetch_related("emergency_contacts", "policy_signatures")
        .first()
    )
