from django import template
from django.forms import RadioSelect

register = template.Library()


from enrollment.models import EnrollmentApplication


@register.filter
def get_item(mapping, key):
    if mapping is None:
        return ""
    return mapping.get(key, "")


@register.filter
def policy_fields_for(grouped, slug):
    if not grouped:
        return []
    return grouped.get(slug, [])


@register.filter
def get_policy_signature(signatures, slug):
    for sig in signatures.all():
        if sig.policy_slug == slug:
            return sig
    return None


@register.filter
def policy_field(field_name, slug):
    return str(field_name).startswith(f"{slug}__")


@register.filter
def program_label(value):
    return dict(EnrollmentApplication.PROGRAM_CHOICES).get(value, value)


@register.filter
def location_label(value):
    return dict(EnrollmentApplication.LOCATION_CHOICES).get(value, value)


@register.simple_tag(takes_context=True)
def localized_program_label(context, value):
    from enrollment.form_i18n import PROGRAM_ES

    request = context.get("request")
    from enrollment.i18n import get_language

    lang = get_language(request) if request else "en"
    if lang == "es":
        return dict(PROGRAM_ES).get(value, program_label(value))
    return program_label(value)


@register.simple_tag(takes_context=True)
def localized_location_label(context, value):
    from enrollment.form_i18n import LOCATION_ES

    request = context.get("request")
    from enrollment.i18n import get_language

    lang = get_language(request) if request else "en"
    if lang == "es":
        return dict(LOCATION_ES).get(value, location_label(value))
    return location_label(value)


@register.filter
def is_radio_select(field):
    return isinstance(field.field.widget, RadioSelect)


@register.simple_tag(takes_context=True)
def enrollment_t(context, key, **kwargs):
    from django.utils.safestring import mark_safe

    from enrollment.i18n import get_language, translate

    request = context.get("request")
    lang = get_language(request) if request else "en"
    text = translate(lang, key, **kwargs)
    if "<" in text:
        return mark_safe(text)
    return text


@register.inclusion_tag("enrollment/includes/apply_field.html")
def apply_field(field, full=False):
    return {"field": field, "full": full}
