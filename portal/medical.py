"""Shared medical-alert helpers so icons only show for real conditions."""

import re

from enrollment.models import EnrollmentApplication

# Values parents type when they mean "nothing to flag".
_NEGATIVE_EXACT = {
    "",
    "-",
    "—",
    "–",
    "n/a",
    "na",
    "none",
    "no",
    "none reported",
    "none known",
    "no known",
    "no known allergies",
    "no known allergy",
    "no allergies",
    "no allergy",
    "nkda",
    "nka",
    "not applicable",
    "none listed",
    "none noted",
    "none given",
    "no medication",
    "no medications",
    "no meds",
    "no med",
    "does not apply",
    "nothing",
    "nil",
}

_NEGATIVE_PREFIXES = (
    "no known",
    "none known",
    "none reported",
    "no allergy",
    "no allergies",
    "no medication",
    "no medications",
)


def normalize_medical_text(value):
    text = str(value or "").strip().lower()
    text = text.replace(".", " ").replace(",", " ")
    text = re.sub(r"\s+", " ", text)
    return text


def medical_value_is_positive(value):
    """True when the field names a real allergy, medication, or condition."""
    text = normalize_medical_text(value)
    if not text or text in _NEGATIVE_EXACT:
        return False
    for prefix in _NEGATIVE_PREFIXES:
        if text == prefix or text.startswith(prefix + " "):
            return False
    return True


def application_for_child(child=None, child_name="", family_slug=None):
    """Match an enrollment application to one child — never first-name-only across families."""
    name = ((child.name if child else child_name) or "").strip()
    parts = name.split()
    first = parts[0] if parts else ""
    last = " ".join(parts[1:]) if len(parts) > 1 else ""
    qs = EnrollmentApplication.objects.all()
    if child is not None:
        qs = qs.filter(portal_family=child.family)
    elif family_slug:
        qs = qs.filter(portal_family__slug=family_slug)
    if first and last:
        qs = qs.filter(student_first_name__iexact=first, student_last_name__iexact=last)
    elif first:
        qs = qs.filter(student_first_name__iexact=first)
        if child is None and not family_slug:
            qs = qs.filter(student_last_name="")
    else:
        return None
    return qs.order_by("-submitted_at").first()


def medical_from_application(app):
    if app.no_known_allergies:
        allergies = "None reported"
        has_allergies = False
    else:
        allergies = (app.allergies or "").strip()
        has_allergies = medical_value_is_positive(allergies)
        if not has_allergies:
            allergies = allergies or "None reported"

    has_medications = app.requires_medication == "yes"
    medications = "Yes — see application" if has_medications else "None reported"

    plans = []
    if has_allergies and app.requires_allergy_plan:
        plans.append("Allergy plan")
    if app.requires_asthma_plan:
        plans.append("Asthma plan")
    if app.requires_epipen_plan:
        plans.append("EpiPen plan")

    return {
        "allergies": allergies,
        "has_allergies": has_allergies,
        "medications": medications,
        "has_medications": has_medications,
        "doctor_name": app.doctor_name,
        "doctor_phone": app.doctor_phone,
        "plans_on_file": plans,
    }


def alerts_from_medical_dict(medical):
    alerts = []
    has_allergies = medical.get("has_allergies")
    if has_allergies is None:
        has_allergies = medical_value_is_positive(medical.get("allergies"))
    if has_allergies:
        alerts.append({"key": "allergy", "detail": medical.get("allergies") or ""})

    has_medications = medical.get("has_medications")
    if has_medications is None:
        has_medications = medical_value_is_positive(medical.get("medications"))
    if has_medications:
        alerts.append({"key": "medication", "detail": medical.get("medications") or ""})

    for plan in medical.get("plans_on_file") or []:
        key = plan.lower().replace(" ", "_").replace("-", "_")
        if "epi" in key:
            alerts.append({"key": "epipen", "detail": plan})
        elif "asthma" in key:
            alerts.append({"key": "asthma", "detail": plan})
        elif "allergy" in key and has_allergies:
            if not any(item["key"] == "allergy_plan" for item in alerts):
                alerts.append({"key": "allergy_plan", "detail": plan})
    return alerts
