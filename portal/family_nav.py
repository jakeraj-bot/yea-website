"""Previous/next navigation between member (family) accounts."""

from django.urls import reverse

from .models import PortalFamily

FAMILY_TAB_URL_KEYS = {
    "profile": "family_detail",
    "pickup": "family_pickup",
    "incidents": "family_incidents",
    "billing": "family_billing",
    "plans": "family_plans",
    "agency": "family_agency",
    "applications": "family_applications",
    "policies": "family_policies",
    "email": "family_email",
}


def family_account_url(area, tab, family_slug, family_id=None):
    prefix = "portal_admin_" if area == "admin" else "portal_staff_"
    name = prefix + FAMILY_TAB_URL_KEYS.get(tab or "profile", "family_detail")
    url = reverse(name, kwargs={"family_slug": family_slug})
    if family_id:
        url = f"{url}?id={family_id}"
    return url


def _nav_entry(area, tab, family):
    family_id = getattr(family, "pk", None) or family.get("id")
    slug = getattr(family, "slug", None) or family.get("slug")
    name = getattr(family, "name", None) or family.get("name")
    return {
        "id": family_id,
        "slug": slug,
        "name": name,
        "url": family_account_url(area, tab, slug, family_id),
    }


def _demo_family_list(area):
    from .demo_data import ADMIN_MEMBER_FAMILIES, FAMILIES

    return ADMIN_MEMBER_FAMILIES if area == "admin" else FAMILIES


def member_families_for_nav(unit=None):
    qs = PortalFamily.objects.select_related("unit")
    if unit is not None:
        qs = qs.filter(unit=unit)
    return list(qs.order_by("unit__name", "name", "pk"))


def family_account_nav_context(
    area,
    family_slug,
    family_tab="profile",
    family_id=None,
    unit=None,
    live=True,
):
    if live:
        families = member_families_for_nav(unit=unit)
        current_index = None
        if family_id:
            try:
                family_id = int(family_id)
            except (TypeError, ValueError):
                family_id = None
        for index, family in enumerate(families):
            if family_id and family.pk == family_id:
                current_index = index
                break
            if not family_id and family.slug == family_slug:
                current_index = index
                break
    else:
        families = _demo_family_list(area)
        current_index = next((i for i, family in enumerate(families) if family.get("slug") == family_slug), None)

    empty = {
        "family_prev": None,
        "family_next": None,
        "family_nav_index": 0,
        "family_nav_count": len(families),
    }
    if current_index is None or len(families) < 2:
        return empty

    prev_family = families[current_index - 1]
    next_family = families[(current_index + 1) % len(families)]
    return {
        "family_prev": _nav_entry(area, family_tab, prev_family),
        "family_next": _nav_entry(area, family_tab, next_family),
        "family_nav_index": current_index + 1,
        "family_nav_count": len(families),
    }
