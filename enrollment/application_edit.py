"""Load and save enrollment applications for parent edit/resubmit."""

from django.utils.dateparse import parse_date

from enrollment.forms import FAMILY_FIELD_NAMES, STEP_ORDER
from enrollment.models import EmergencyContact, EnrollmentApplication, PolicySignature
from enrollment.policies_data import POLICY_BY_SLUG

EDITABLE_STATUSES = {"pending_documents"}

META_FIELDS = frozenset(
    {
        "reference",
        "family_group",
        "child_number",
        "submitted_at",
        "portal_family",
        "status",
        "internal_note",
        "staff_message",
        "reviewed_at",
        "needs_dale_ave_bus",
    }
)


def child_field_names():
    return [
        field.name
        for field in EnrollmentApplication._meta.fields
        if field.name not in META_FIELDS and field.name not in FAMILY_FIELD_NAMES
    ]


def _serialize_field_value(value):
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def application_to_session_data(app):
    family_data = {name: getattr(app, name) for name in FAMILY_FIELD_NAMES}
    child_data = {}
    for name in child_field_names():
        child_data[name] = _serialize_field_value(getattr(app, name))

    child_data["emergency_contacts"] = [
        {
            "first_name": contact.first_name,
            "last_name": contact.last_name,
            "phone": contact.phone,
            "relationship": contact.relationship,
            "authorized_pickup": contact.authorized_pickup,
        }
        for contact in app.emergency_contacts.all()
    ]
    child_data["policies"] = {
        signature.policy_slug: {
            "signature": signature.signature_name,
            "date": signature.signed_date.isoformat(),
            "extra": signature.extra_data or {},
        }
        for signature in app.policy_signatures.all()
    }

    return {
        **family_data,
        "editing_reference": str(app.reference),
        "children": [child_data],
        "current_child_index": 0,
        "max_step_index": len(STEP_ORDER) - 1,
    }


def _parse_session_value(key, value):
    date_fields = {
        "student_dob",
        "payment_plan_signed_date",
        "four_cs_signed_date",
    }
    if key in date_fields and value:
        if isinstance(value, str):
            return parse_date(value)
    return value


def update_application_from_session(app, session_data):
    child_data = (session_data.get("children") or [{}])[0]

    for name in FAMILY_FIELD_NAMES:
        if name in session_data:
            setattr(app, name, session_data[name])

    for name in child_field_names():
        if name in child_data:
            setattr(app, name, _parse_session_value(name, child_data[name]))

    app.needs_dale_ave_bus = app.program_location == "dale_ave"
    app.save()

    app.emergency_contacts.all().delete()
    for idx, contact in enumerate(child_data.get("emergency_contacts") or [], start=1):
        if not contact.get("first_name") and not contact.get("last_name"):
            continue
        EmergencyContact.objects.create(
            application=app,
            order=idx,
            first_name=contact.get("first_name", ""),
            last_name=contact.get("last_name", ""),
            phone=contact.get("phone", ""),
            relationship=contact.get("relationship", ""),
            authorized_pickup=bool(contact.get("authorized_pickup")),
        )

    app.policy_signatures.all().delete()
    for slug, payload in (child_data.get("policies") or {}).items():
        policy = POLICY_BY_SLUG.get(slug)
        if not policy:
            continue
        signed_date = payload.get("date")
        if isinstance(signed_date, str):
            signed_date = parse_date(signed_date)
        PolicySignature.objects.create(
            application=app,
            policy_slug=slug,
            policy_title=policy["title"],
            signature_name=payload.get("signature", ""),
            signed_date=signed_date,
            extra_data=payload.get("extra") or {},
        )

    return app


def parent_can_edit_application(account, app):
    if not account or not app:
        return False
    return app.portal_family_id == account.family_id and app.status in EDITABLE_STATUSES
