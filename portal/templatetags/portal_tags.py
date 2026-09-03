from urllib.parse import urlencode

from django import template

from portal.demo_data import CHILD_MEDICAL, MEDICAL_ALERT_TYPES

register = template.Library()


def _alerts_for_child(child_name, family_slug=None):
    from portal.staff_services import get_medical_data_for_child

    medical = get_medical_data_for_child(child_name, family_slug)
    slug = child_name.lower().replace(" ", "-")
    alerts = []
    for index, item in enumerate(medical.get("alerts", [])):
        key = item["key"]
        definition = MEDICAL_ALERT_TYPES.get(key, {})
        alerts.append(
            {
                "key": key,
                "label": definition.get("label", key),
                "symbol": definition.get("symbol", "?"),
                "detail": item.get("detail", ""),
                "tip_id": f"med-{slug}-{key}-{index}",
            }
        )
    return alerts


@register.inclusion_tag("portal/staff/includes/medical_badges.html")
def medical_badges(child_name, size="md", family_slug=None):
    return {
        "alerts": _alerts_for_child(child_name, family_slug),
        "size": size,
    }


@register.inclusion_tag("portal/staff/includes/child_medical_card.html", takes_context=True)
def child_medical_card(context, child_name, child=None):
    from portal.staff_services import get_medical_data_for_child

    child = child or {}
    family_slug = child.get("family_slug") if isinstance(child, dict) else context.get("family_slug")
    medical = child.get("medical") if isinstance(child, dict) else None
    medical = medical or get_medical_data_for_child(child_name, family_slug)
    return {
        "child_name": child_name,
        "child": child,
        "alerts": _alerts_for_child(child_name, family_slug),
        "medical": medical,
        "request": context.get("request"),
        "school_options": context.get("school_options", []),
        "portal_live": context.get("portal_live"),
    }


@register.filter
def split_csv(value, separator=","):
    if not value:
        return []
    return [part.strip() for part in str(value).split(separator) if part.strip()]


@register.simple_tag
def append_query(existing_query="", **kwargs):
    """Append URL-encoded GET params to an optional existing query string."""
    params = {
        key: value
        for key, value in kwargs.items()
        if value is not None and str(value) != ""
    }
    if not params:
        return existing_query or ""
    encoded = urlencode(params)
    if existing_query:
        separator = "&" if existing_query.startswith("?") else "?"
        return f"{existing_query}{separator}{encoded}"
    return f"?{encoded}"
