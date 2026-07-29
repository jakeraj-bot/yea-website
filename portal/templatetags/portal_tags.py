from django import template

from portal.demo_data import CHILD_MEDICAL, MEDICAL_ALERT_TYPES

register = template.Library()


def _alerts_for_child(child_name):
    from portal.staff_services import get_medical_data_for_child

    medical = get_medical_data_for_child(child_name)
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
def medical_badges(child_name, size="md"):
    return {
        "alerts": _alerts_for_child(child_name),
        "size": size,
    }


@register.inclusion_tag("portal/staff/includes/child_medical_card.html")
def child_medical_card(child_name, child=None):
    from portal.staff_services import get_medical_data_for_child

    child = child or {}
    medical = child.get("medical") or get_medical_data_for_child(child_name)
    return {
        "child_name": child_name,
        "child": child,
        "alerts": _alerts_for_child(child_name),
        "medical": medical,
    }
