"""Enrollment location choices synced with portal units."""

from django.db.models import Q

# Legacy application values → portal unit slug
LEGACY_LOCATION_TO_UNIT_SLUG = {
    "school_18": "school-18",
    "school_26": "school-26",
    "dale_ave": "school-18",
    "caldwell": "caldwell",
}


def _unit_label(unit):
    if unit.city:
        return f"{unit.name} — {unit.city}"
    return unit.name


def enrollment_key_for_unit(unit):
    """Stored on EnrollmentApplication.program_location."""
    return unit.slug.replace("-", "_")


def get_enrollment_location_choices():
    from portal.models import PortalUnit

    units = list(PortalUnit.objects.filter(is_active=True).order_by("name"))
    if units:
        return [(enrollment_key_for_unit(unit), _unit_label(unit)) for unit in units]
    from enrollment.models import EnrollmentApplication

    return list(EnrollmentApplication.LOCATION_CHOICES)


def get_location_label(key):
    if not key:
        return ""
    for value, label in get_enrollment_location_choices():
        if value == key:
            return label
    return key.replace("_", " ").title()


def unit_slug_for_enrollment_key(key):
    from portal.models import PortalUnit

    if not key:
        return None
    slug = key.replace("_", "-")
    unit = PortalUnit.objects.filter(slug=slug, is_active=True).first()
    if unit:
        return unit.slug
    return LEGACY_LOCATION_TO_UNIT_SLUG.get(key)


def get_unit_for_enrollment_key(key):
    from portal.models import PortalUnit

    slug = unit_slug_for_enrollment_key(key)
    if not slug:
        return None
    return PortalUnit.objects.filter(slug=slug, is_active=True).first()


def enrollment_keys_for_unit(unit):
    keys = {enrollment_key_for_unit(unit)}
    for legacy_key, slug in LEGACY_LOCATION_TO_UNIT_SLUG.items():
        if slug == unit.slug:
            keys.add(legacy_key)
    return keys


def unit_allows_program(unit, program):
    if not unit:
        return True
    program_type = (unit.program_type or "after_school").lower()
    if program == "summer_camp":
        return program_type in {"summer_camp", "summer", "camp", "both", "all"}
    return program_type in {"after_school", "both", "all", ""}


def applications_queryset_for_unit(unit):
    from enrollment.models import EnrollmentApplication

    if not unit:
        return EnrollmentApplication.objects.none()
    family_ids = unit.families.values_list("id", flat=True)
    location_keys = enrollment_keys_for_unit(unit)
    return EnrollmentApplication.objects.filter(
        Q(portal_family_id__in=family_ids) | Q(portal_family__isnull=True, program_location__in=location_keys)
    )
