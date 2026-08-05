"""Spanish labels and choices for enrollment forms."""

from enrollment.models import EnrollmentApplication as M

YES_NO_ES = [("yes", "Sí"), ("no", "No")]
GENDER_ES = [("female", "Femenino"), ("male", "Masculino")]
LANGUAGE_ES = [("english", "Inglés"), ("spanish", "Español"), ("other", "Otro")]
RELATIONSHIP_ES = [
    ("mother", "Madre"),
    ("father", "Padre"),
    ("guardian", "Tutor legal"),
    ("other", "Otro"),
]
PHONE_TYPE_ES = [("cell", "Teléfono celular"), ("home", "Teléfono de casa")]
PROGRAM_ES = [
    ("after_school", "Programa después de la escuela"),
    ("summer_camp", "Campamento de verano"),
]
LOCATION_ES = [
    ("school_18", "School 18 — Paterson"),
    ("school_26", "School 26 — Paterson"),
    ("dale_ave", "Dale Ave — Paterson (autobús a School 18)"),
    ("caldwell", "Universidad de Caldwell"),
]
ETHNICITY_ES = [
    ("hispanic", "Hispano/Latino"),
    ("non_hispanic", "No Hispano/Latino"),
    ("unknown", "Desconocido"),
]
RACE_ES = [
    ("black", "Negro o afroamericano"),
    ("white", "Blanco"),
    ("native_hawaiian", "Nativo de Hawái"),
    ("asian", "Asiático"),
    ("american_indian", "Indígena americano"),
    ("unknown", "Desconocido"),
    ("other", "Otro"),
]
GRADE_ES = [
    ("pre_k", "Pre-K"),
    ("kindergarten", "Kindergarten"),
    ("1", "1.º"),
    ("2", "2.º"),
    ("3", "3.º"),
    ("4", "4.º"),
    ("5", "5.º"),
    ("6", "6.º"),
    ("7", "7.º"),
    ("8", "8.º"),
]
HEALTH_ES = [
    (
        "good_health",
        "Mi hijo/a goza de buena salud y puede participar en actividades normales.",
    ),
    (
        "needs_accommodation",
        "Mi hijo/a puede participar pero tiene condiciones que requieren adaptaciones especiales.",
    ),
]
PAYMENT_METHOD_ES = [
    ("private_pay", "Pago privado (tarjeta)"),
    ("4cs", "4Cs"),
    ("other", "Otro"),
]
PAYMENT_PLAN_ES = [
    ("weekly", "Semanal"),
    ("biweekly", "Quincenal"),
    ("monthly", "Mensual"),
]
ADD_CHILD_ES = [
    ("yes", "Sí — agregar otro niño"),
    ("no", "No — terminé de agregar niños"),
]

FORM_LABELS_ES = {
    "family_name": "Nombre de la familia",
    "primary_email": "Correo principal",
    "home_address": "Dirección del hogar",
    "primary_first_name": "Nombre",
    "primary_last_name": "Apellido",
    "primary_gender": "Género",
    "primary_language": "Idioma principal",
    "primary_language_other": "Si es otro, especifique",
    "primary_relationship": "Relación con el niño/a",
    "primary_relationship_other": "Si es otro, especifique",
    "primary_phone": "Teléfono",
    "primary_phone_type": "Tipo de teléfono",
    "primary_text_subscription": "Suscripción a mensajes de texto",
    "primary_email_subscription": "Suscripción a correo electrónico",
    "primary_email_address": "Correo electrónico",
    "primary_authorized_pickup": "¿Autorizado para recoger al niño/a?",
    "secondary_first_name": "Nombre",
    "secondary_last_name": "Apellido",
    "secondary_gender": "Género",
    "secondary_language": "Idioma principal",
    "secondary_language_other": "Si es otro, especifique",
    "secondary_relationship": "Relación con el niño/a",
    "secondary_relationship_other": "Si es otro, especifique",
    "secondary_phone": "Teléfono",
    "secondary_phone_type": "Tipo de teléfono",
    "secondary_text_subscription": "Suscripción a mensajes de texto",
    "secondary_email_subscription": "Suscripción a correo electrónico",
    "secondary_email_address": "Correo electrónico",
    "secondary_authorized_pickup": "¿Autorizado para recoger al niño/a?",
    "program": "¿Para qué programa solicita?",
    "program_location": "¿Qué ubicación?",
    "student_first_name": "Nombre del estudiante",
    "student_last_name": "Apellido del estudiante",
    "student_gender": "Género",
    "student_dob": "Fecha de nacimiento",
    "student_language": "Idioma principal",
    "student_language_other": "Si es otro, especifique",
    "student_ethnicity": "Etnicidad",
    "student_race": "Raza",
    "student_race_other": "Si es otro, especifique",
    "student_grade": "Grado",
    "student_school": "Escuela",
    "doctor_name": "Nombre del médico",
    "doctor_phone": "Teléfono del médico",
    "insurance_provider": "Compañía de seguro",
    "insurance_policy_group": "N.º de póliza/grupo",
    "insurance_member_id": "N.º de miembro",
    "no_insurance": "Sin seguro",
    "allergies": "Alergias",
    "no_known_allergies": "Sin alergias conocidas",
    "requires_allergy_plan": "El niño/a requiere un plan de acción para alergias",
    "requires_asthma_plan": "El niño/a requiere un plan de acción para asma",
    "requires_epipen_plan": "El niño/a requiere un plan de EpiPen",
    "has_disability": "¿Discapacidad?",
    "has_special_needs": "¿Necesidades especiales?",
    "requires_medication": "¿Medicación?",
    "has_medical_condition": "¿Condición médica?",
    "medical_condition_explain": "Por favor explique",
    "health_statement": "Declaración de salud (marque solo una)",
    "membership_fee_agreed": "¿Acepta la cuota de membresía de $20 para el año escolar 2026–2027?",
    "payment_method": "Forma de pago",
    "payment_method_other": "Si es otro, especifique",
    "late_fees_understood": (
        "Entiendo las multas por retraso: $15 por pagos atrasados; $15 por cada 15 minutos "
        "de retraso en la recogida (el programa cierra a las 6:00 p.m.)."
    ),
    "payment_plan": "Plan de pago preferido",
    "payment_plan_signature": "Firma del plan de pago (escriba su nombre completo)",
    "payment_plan_signed_date": "Fecha",
    "four_cs_signature": "Firma 4Cs (escriba su nombre completo)",
    "four_cs_signed_date": "Fecha 4Cs",
    "add_another": "¿Necesita agregar otro niño a esta solicitud?",
    "first_name": "Nombre",
    "last_name": "Apellido",
    "phone": "Teléfono",
    "relationship": "Relación con el niño/a",
    "authorized_pickup": "Autorizado para recoger al niño/a",
    "username": "Nombre de usuario",
    "password1": "Contraseña",
    "password2": "Confirmar contraseña",
}

FIELD_CHOICES_ES = {
    "primary_gender": GENDER_ES,
    "secondary_gender": [("", "---------")] + GENDER_ES,
    "student_gender": GENDER_ES,
    "primary_language": LANGUAGE_ES,
    "secondary_language": [("", "---------")] + LANGUAGE_ES,
    "student_language": LANGUAGE_ES,
    "primary_relationship": RELATIONSHIP_ES,
    "secondary_relationship": [("", "---------")] + RELATIONSHIP_ES,
    "primary_phone_type": PHONE_TYPE_ES,
    "secondary_phone_type": [("", "---------")] + PHONE_TYPE_ES,
    "primary_text_subscription": YES_NO_ES,
    "primary_email_subscription": YES_NO_ES,
    "primary_authorized_pickup": YES_NO_ES,
    "secondary_text_subscription": [("", "---------")] + YES_NO_ES,
    "secondary_email_subscription": [("", "---------")] + YES_NO_ES,
    "secondary_authorized_pickup": [("", "---------")] + YES_NO_ES,
    "program": PROGRAM_ES,
    "program_location": LOCATION_ES,
    "student_ethnicity": ETHNICITY_ES,
    "student_race": RACE_ES,
    "student_grade": GRADE_ES,
    "health_statement": HEALTH_ES,
    "has_disability": YES_NO_ES,
    "has_special_needs": YES_NO_ES,
    "requires_medication": YES_NO_ES,
    "has_medical_condition": YES_NO_ES,
    "membership_fee_agreed": YES_NO_ES,
    "payment_method": PAYMENT_METHOD_ES,
    "payment_plan": PAYMENT_PLAN_ES,
    "add_another": ADD_CHILD_ES,
}

SIGNATURE_HELP_ES = "Escriba su nombre legal completo"


def localize_form(form, lang):
    if lang != "es":
        return
    for name, field in form.fields.items():
        if name in FORM_LABELS_ES:
            field.label = FORM_LABELS_ES[name]
        if name in FIELD_CHOICES_ES:
            field.choices = FIELD_CHOICES_ES[name]
        if name.endswith("__signature") and getattr(field, "help_text", None):
            field.help_text = SIGNATURE_HELP_ES


def localize_policy_form(form, lang):
    if lang != "es":
        return
    from .policies_loader import get_policies

    by_slug = {p["slug"]: p for p in get_policies(lang)}
    for name, field in form.fields.items():
        if "__" not in name:
            continue
        slug, rest = name.split("__", 1)
        policy = by_slug.get(slug)
        if not policy:
            continue
        if rest == "signature":
            field.label = f"Firma — {policy['title']}"
            field.help_text = SIGNATURE_HELP_ES
        elif rest == "date":
            field.label = "Fecha de firma"
        else:
            for extra in policy.get("fields", []):
                if extra["name"] == rest:
                    field.label = extra["label"]
                    if extra.get("type") == "choice":
                        field.choices = list(extra["choices"])


def localize_formset(formset, lang):
    if lang != "es" or not formset:
        return
    for form in formset.forms:
        localize_form(form, lang)
