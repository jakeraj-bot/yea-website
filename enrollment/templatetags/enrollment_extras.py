from django import template

register = template.Library()


from enrollment.models import EnrollmentApplication


@register.filter
def get_item(mapping, key):
    if mapping is None:
        return ""
    return mapping.get(key, "")


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
