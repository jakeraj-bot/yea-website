"""Add program requests for children who already have an enrollment application."""

import uuid

from django.db import transaction

from .locations import location_keys_for_program
from .models import EmergencyContact, EnrollmentApplication, PolicySignature
from .notifications import send_application_submitted_emails


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


def child_has_before_care(family, first_name, last_name):
    if not family:
        return False
    return (
        EnrollmentApplication.objects.filter(
            portal_family=family,
            program="before_care",
            student_first_name__iexact=first_name.strip(),
            student_last_name__iexact=last_name.strip(),
        )
        .exclude(status="declined")
        .exists()
    )


def can_add_before_care_for_application(app):
    if not app or not app.portal_family_id or app.program == "before_care":
        return False
    return not child_has_before_care(app.portal_family, app.student_first_name, app.student_last_name)


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


@transaction.atomic
def create_before_care_from_application(source, program_location=None):
    if source.program == "before_care":
        raise ValueError("This application is already for before care.")
    if child_has_before_care(source.portal_family, source.student_first_name, source.student_last_name):
        raise ValueError("Before care is already on the waitlist for this child.")

    location_keys = location_keys_for_program("before_care")
    if not location_keys:
        raise ValueError("Before care is not available right now.")

    chosen = (program_location or "").strip()
    if not chosen:
        if source.program_location in location_keys:
            chosen = source.program_location
        elif source.program_location == "dale_ave" and "school_18" in location_keys:
            chosen = "school_18"
        else:
            chosen = location_keys[0]
    elif chosen not in location_keys:
        raise ValueError("That location is not available for before care.")

    data = {name: getattr(source, name) for name in _clone_field_names()}
    data.update(
        {
            "reference": uuid.uuid4(),
            "family_group": source.family_group or uuid.uuid4(),
            "program": "before_care",
            "program_location": chosen,
            "needs_dale_ave_bus": False,
            "status": "waitlist",
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
