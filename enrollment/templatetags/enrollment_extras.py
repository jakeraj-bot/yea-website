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


@register.filter
def is_radio_select(field):
    return isinstance(field.field.widget, RadioSelect)


@register.simple_tag(takes_context=True)
def enrollment_t(context, key, **kwargs):
    from enrollment.i18n import get_language, translate

    request = context.get("request")
    lang = get_language(request) if request else "en"
    return translate(lang, key, **kwargs)


@register.inclusion_tag("enrollment/includes/apply_field.html")
def apply_field(field, full=False):
    return {"field": field, "full": full}
