import re


def normalize_phone(value):
    return re.sub(r"\D", "", value or "")


def normalize_name(first_name, last_name):
    return f"{(first_name or '').strip()} {(last_name or '').strip()}".strip().lower()


def contact_identity(first_name, last_name, phone):
    return (normalize_name(first_name, last_name), normalize_phone(phone))


def contact_is_complete(data):
    return all(data.get(field) for field in ("first_name", "last_name", "phone", "relationship"))


_VALIDATION_STRINGS = {
    "en": {
        "complete_fields": "Complete all fields for this emergency contact.",
        "two_required": "Two complete emergency contacts are required — fill in all fields for at least two contacts.",
        "name_phone_required": "Name and phone are required.",
        "different_from_primary": "Emergency contacts must be different from the primary parent/guardian (different name and phone).",
        "different_people": "Emergency contacts must be different people (different name and phone number).",
    },
    "es": {
        "complete_fields": "Complete todos los campos de este contacto de emergencia.",
        "two_required": "Se requieren dos contactos de emergencia completos — complete todos los campos de al menos dos contactos.",
        "name_phone_required": "El nombre y el teléfono son obligatorios.",
        "different_from_primary": "Los contactos de emergencia deben ser diferentes del padre/tutor principal (nombre y teléfono distintos).",
        "different_people": "Los contactos de emergencia deben ser personas diferentes (nombre y teléfono distintos).",
    },
}


def _msg(lang, key):
    lang = lang if lang in _VALIDATION_STRINGS else "en"
    return _VALIDATION_STRINGS[lang].get(key, _VALIDATION_STRINGS["en"][key])


def validate_emergency_contacts(formset, session_data, lang="en"):
    """Return True if valid; attach errors to formset/forms otherwise."""
    ok = True
    primary_identity = contact_identity(
        session_data.get("primary_first_name"),
        session_data.get("primary_last_name"),
        session_data.get("primary_phone"),
    )

    completed = []
    for form in formset:
        data = form.cleaned_data
        if not any(data.get(field) for field in ("first_name", "last_name", "phone", "relationship")):
            continue
        if not contact_is_complete(data):
            form.add_error(None, _msg(lang, "complete_fields"))
            ok = False
            continue
        completed.append((form, data))

    if len(completed) < 2:
        formset._non_form_errors = formset.error_class([_msg(lang, "two_required")])
        return False

    identities = []
    for form, data in completed:
        identity = contact_identity(data.get("first_name"), data.get("last_name"), data.get("phone"))
        if not identity[0] or not identity[1]:
            form.add_error(None, _msg(lang, "name_phone_required"))
            ok = False
            continue
        if identity == primary_identity:
            form.add_error(None, _msg(lang, "different_from_primary"))
            ok = False
        identities.append(identity)

    if len(set(identities)) < len(identities):
        formset._non_form_errors = formset.error_class([_msg(lang, "different_people")])
        ok = False

    return ok
