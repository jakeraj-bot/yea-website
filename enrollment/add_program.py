"""Add program requests for children who already have an enrollment application."""

import uuid

from django.db import transaction

from .locations import location_keys_for_program
from .models import EmergencyContact, EnrollmentApplication, PolicySignature
from .notifications import send_application_submitted_emails

PROGRAM_LABELS = {
    "before_care": "Before care",
    "after_school": "After-care",
    "drop_off": "Drop-off",
    "summer_camp": "Summer camp",
}


def programs_for_child_data(child_data):
    programs = child_data.get("programs")
    if programs:
        return list(programs)
    program = child_data.get("program")
    return [program] if program else []


def child_key(app):
    return (
        (app.student_first_name or "").strip().lower(),
        (app.student_last_name or "").strip().lower(),
    )


def primary_applications_by_child(apps):
    """One enrollment record per child — before-care waitlist add-ons share policies with after-school."""
    grouped = {}
    for app in apps:
        grouped.setdefault(child_key(app), []).append(app)
    primaries = []
    for group in grouped.values():
        primary = next((item for item in group if item.program != "before_care"), group[0])
        primaries.append(primary)
    return primaries


def child_has_program(family, first_name, last_name, program):
    if not family:
        return False
    return (
        EnrollmentApplication.objects.filter(
            portal_family=family,
            program=program,
            student_first_name__iexact=(first_name or "").strip(),
            student_last_name__iexact=(last_name or "").strip(),
        )
        .exclude(status="declined")
        .exists()
    )


def child_has_before_care(family, first_name, last_name):
    return child_has_program(family, first_name, last_name, "before_care")


def child_has_after_school(family, first_name, last_name):
    return child_has_program(family, first_name, last_name, "after_school")


def can_add_program_for_application(app, program):
    if not app or not app.portal_family_id or app.program == program:
        return False
    return not child_has_program(app.portal_family, app.student_first_name, app.student_last_name, program)


def can_add_before_care_for_application(app):
    return can_add_program_for_application(app, "before_care")


def can_add_after_school_for_application(app):
    return can_add_program_for_application(app, "after_school")


def copy_policy_signatures(source, dest):
    for signature in source.policy_signatures.all():
        PolicySignature.objects.get_or_create(
            application=dest,
            policy_slug=signature.policy_slug,
            defaults={
                "policy_title": signature.policy_title,
                "signature_name": signature.signature_name,
                "signed_date": signature.signed_date,
                "extra_data": signature.extra_data or {},
            },
        )


def _clone_field_names():
    skip = {
        "id",
        "reference",
        "submitted_at",
        "status",
        "reviewed_at",
        "staff_message",
        "internal_note",
        "program",
        "program_location",
        "needs_dale_ave_bus",
    }
    return [field.name for field in EnrollmentApplication._meta.fields if field.name not in skip]


def _program_label(program):
    return PROGRAM_LABELS.get(program) or program.replace("_", " ")


def _choose_location(source, program, program_location, location_keys):
    chosen = (program_location or "").strip()
    if not chosen:
        if source.program_location in location_keys:
            return source.program_location
        if program == "before_care" and source.program_location == "dale_ave" and "school_18" in location_keys:
            return "school_18"
        if location_keys:
            return location_keys[0]
        raise ValueError(f"{_program_label(program)} is not available right now.")
    if chosen not in location_keys:
        raise ValueError(f"That location is not available for {_program_label(program).lower()}.")
    return chosen


@transaction.atomic
def create_program_from_application(source, program, program_location=None, status=None):
    """Clone an existing application onto another program without a new enrollment form."""
    label = _program_label(program)
    if source.program == program:
        raise ValueError(f"This application is already for {label.lower()}.")
    if child_has_program(source.portal_family, source.student_first_name, source.student_last_name, program):
        if program == "before_care":
            raise ValueError("Before care is already on the waitlist for this child.")
        raise ValueError(f"{label} is already on file for this child.")

    location_keys = location_keys_for_program(program)
    if not location_keys:
        raise ValueError(f"{label} is not available right now.")

    chosen = _choose_location(source, program, program_location, location_keys)
    if status is None:
        status = "waitlist" if program == "before_care" else "under_review"

    family_group = source.family_group
    if not family_group:
        family_group = uuid.uuid4()
        if source.pk:
            source.family_group = family_group
            source.save(update_fields=["family_group"])

    data = {name: getattr(source, name) for name in _clone_field_names()}
    data.update(
        {
            "reference": uuid.uuid4(),
            "family_group": family_group,
            "program": program,
            "program_location": chosen,
            "needs_dale_ave_bus": False if program == "before_care" else chosen == "dale_ave",
            "status": status,
            "portal_family": source.portal_family,
        }
    )
    app = EnrollmentApplication.objects.create(**data)

    for contact in source.emergency_contacts.all():
        EmergencyContact.objects.create(
            application=app,
            order=contact.order,
            first_name=contact.first_name,
            last_name=contact.last_name,
            phone=contact.phone,
            relationship=contact.relationship,
            authorized_pickup=contact.authorized_pickup,
        )

    copy_policy_signatures(source, app)
    send_application_submitted_emails(app)
    return app


def create_before_care_from_application(source, program_location=None):
    return create_program_from_application(
        source, "before_care", program_location=program_location, status="waitlist"
    )


def create_after_school_from_application(source, program_location=None):
    return create_program_from_application(
        source, "after_school", program_location=program_location, status="under_review"
    )
