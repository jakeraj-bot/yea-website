"""Enrollment application UI translations (English + Spanish)."""

SUPPORTED_LANGUAGES = {
    "en": "English",
    "es": "Español",
}

SESSION_KEY = "enrollment_lang"


def get_language(request):
    code = (request.session.get(SESSION_KEY) or "en").lower()
    return code if code in SUPPORTED_LANGUAGES else "en"


def set_language(request, code):
    code = (code or "en").lower()
    if code in SUPPORTED_LANGUAGES:
        request.session[SESSION_KEY] = code
        request.session.modified = True


def translate(lang, key, **kwargs):
    lang = lang if lang in SUPPORTED_LANGUAGES else "en"
    text = _STRINGS.get(lang, {}).get(key) or _STRINGS["en"].get(key, key)
    if kwargs:
        return text.format(**kwargs)
    return text


STEP_TITLES = {
    "en": {
        "family": "Family & parent/guardian information",
        "program": "Program & location",
        "student": "Student & medical information",
        "billing": "Billing & emergency contacts",
        "policies": "Policies & signatures",
        "add_child": "Add another child?",
        "review": "Review & submit",
    },
    "es": {
        "family": "Información de la familia y padres/tutores",
        "program": "Programa y ubicación",
        "student": "Información del estudiante y médica",
        "billing": "Facturación y contactos de emergencia",
        "policies": "Políticas y firmas",
        "add_child": "¿Agregar otro niño?",
        "review": "Revisar y enviar",
    },
}

STEP_TAB_LABELS = {
    "en": {
        "family": "Family",
        "program": "Program",
        "student": "Student",
        "billing": "Billing",
        "policies": "Policies",
        "add_child": "Add child",
        "review": "Review",
    },
    "es": {
        "family": "Familia",
        "program": "Programa",
        "student": "Estudiante",
        "billing": "Facturación",
        "policies": "Políticas",
        "add_child": "Otro niño",
        "review": "Revisar",
    },
}

FORM_LABELS_ES = {
    "family_name": "Nombre de la familia",
    "primary_email": "Correo principal",
    "home_address": "Dirección",
    "primary_first_name": "Nombre",
    "primary_last_name": "Apellido",
    "primary_phone": "Teléfono",
    "student_first_name": "Nombre del estudiante",
    "student_last_name": "Apellido del estudiante",
    "student_dob": "Fecha de nacimiento",
    "student_grade": "Grado",
    "student_school": "Escuela",
    "membership_fee_agreed": "¿Acepta la cuota de membresía de $20?",
    "payment_method": "Forma de pago",
    "payment_plan": "Plan de pago preferido",
}


def localized_step_titles(lang):
    return STEP_TITLES.get(lang, STEP_TITLES["en"])


def localized_step_tab_labels(lang):
    return STEP_TAB_LABELS.get(lang, STEP_TAB_LABELS["en"])


def localize_form_labels(form, lang):
    if lang != "es":
        return
    for name, label in FORM_LABELS_ES.items():
        if name in form.fields:
            form.fields[name].label = label


_STRINGS = {
    "en": {
        "apply_title": "Apply for enrollment",
        "apply_lead": "Start a new application or sign in to your parent portal if you already have an account.",
        "language_label": "Application language",
        "already_have_account": "Already have a parent portal account?",
        "already_have_account_desc": "Sign in to apply using your saved family information. Submitted applications appear in your portal automatically.",
        "sign_in_parent": "Sign in to parent portal",
        "new_family": "New family applying?",
        "new_family_desc": "Start the enrollment application online. Before you submit, you'll create a username and password so you can track your application in the parent portal.",
        "new_family_note": "Different households with the same last name each get their own portal account — they stay separate.",
        "start_application": "Start new application",
        "continue": "Continue",
        "back": "Back",
        "submit": "Submit application",
        "submit_resubmit": "Resubmit for review",
        "saving": "Saving…",
        "submitting": "Submitting…",
        "required_items": "Please complete the required items below",
        "check_other_tabs": "If you don't see the problem, check the other section tabs on this step.",
        "policies_english_note": "",
        "review_title": "Review your application",
        "review_lead": "Check your information, create your parent portal login, then submit.",
        "portal_login_section": "Create your parent portal login",
        "policy_read_full": "Read the full policy before signing ↗",
    },
    "es": {
        "apply_title": "Solicitar inscripción",
        "apply_lead": "Comience una nueva solicitud o inicie sesión en el portal de padres si ya tiene una cuenta.",
        "language_label": "Idioma de la solicitud",
        "already_have_account": "¿Ya tiene una cuenta del portal de padres?",
        "already_have_account_desc": "Inicie sesión para solicitar usando la información guardada de su familia. Las solicitudes enviadas aparecen automáticamente en su portal.",
        "sign_in_parent": "Iniciar sesión en el portal de padres",
        "new_family": "¿Familia nueva?",
        "new_family_desc": "Complete la solicitud en línea. Antes de enviar, creará un usuario y contraseña para seguir su solicitud en el portal de padres.",
        "new_family_note": "Hogares diferentes con el mismo apellido tienen cuentas separadas.",
        "start_application": "Comenzar solicitud",
        "continue": "Continuar",
        "back": "Atrás",
        "submit": "Enviar solicitud",
        "submit_resubmit": "Reenviar para revisión",
        "saving": "Guardando…",
        "submitting": "Enviando…",
        "required_items": "Complete los campos obligatorios",
        "check_other_tabs": "Si no ve el error, revise las otras pestañas de esta sección.",
        "policies_english_note": "El texto legal de las políticas está en inglés. Puede abrir la política completa o contactarnos si necesita ayuda.",
        "review_title": "Revise su solicitud",
        "review_lead": "Verifique su información, cree su acceso al portal de padres y envíe.",
        "portal_login_section": "Cree su acceso al portal de padres",
        "policy_read_full": "Lea la política completa antes de firmar ↗",
    },
}
