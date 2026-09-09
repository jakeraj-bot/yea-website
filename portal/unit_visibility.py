"""One family account can have children in different program sites.

Staff only see children (and child-named ledger rows) for their current unit.
Portal admin and parents see the whole household. Family-level balance is
shared on the family row; staff still must not see the other unit's child names.
"""

from django.db.models import Q

from .models import PortalChild, PortalFamily


def child_effective_unit(child):
    if getattr(child, "unit_id", None):
        return child.unit
    family = getattr(child, "family", None)
    return family.unit if family else None


def child_unit_q(unit, prefix=""):
    """Q matching children whose own unit (or family unit if unset) is `unit`."""
    unit_field = f"{prefix}unit" if prefix else "unit"
    family_unit = f"{prefix}family__unit" if prefix else "family__unit"
    return Q(**{unit_field: unit}) | Q(**{f"{unit_field}__isnull": True, family_unit: unit})


def child_unit_slug_q(unit_slug, prefix=""):
    unit_field = f"{prefix}unit__slug" if prefix else "unit__slug"
    family_unit = f"{prefix}family__unit__slug" if prefix else "family__unit__slug"
    unit_isnull = f"{prefix}unit__isnull" if prefix else "unit__isnull"
    return Q(**{unit_field: unit_slug}) | Q(**{unit_isnull: True, family_unit: unit_slug})


def children_for_unit(unit, *, active_only=True):
    if not unit:
        qs = PortalChild.objects.none()
    else:
        qs = PortalChild.objects.filter(child_unit_q(unit))
    if active_only:
        qs = qs.filter(is_active=True)
    return qs.select_related("family", "family__unit", "unit")


def child_belongs_to_unit(child, unit):
    if not unit:
        return True
    if not child:
        return False
    effective_id = child.unit_id or getattr(child.family, "unit_id", None)
    return effective_id == unit.pk


def application_belongs_to_unit(app, unit):
    if not unit:
        return True
    if not app:
        return False
    from enrollment.locations import enrollment_keys_for_unit, get_unit_for_enrollment_key

    location = (getattr(app, "program_location", None) or "").strip()
    if location:
        return location in enrollment_keys_for_unit(unit)
    app_unit = get_unit_for_enrollment_key(location) if location else None
    return bool(app_unit and app_unit.pk == unit.pk)


def visible_child_names(family, unit, *, include_pending=True):
    """Lowercased child names staff at `unit` are allowed to see."""
    if not family:
        return set()
    names = set()
    qs = family.children.all()
    if unit:
        qs = [child for child in qs if child_belongs_to_unit(child, unit)]
    else:
        qs = list(qs)
    for child in qs:
        if child.is_active and child.name:
            names.add(child.name.strip().lower())
    if include_pending:
        from enrollment.models import EnrollmentApplication

        apps = EnrollmentApplication.objects.filter(portal_family=family).exclude(status="declined")
        for app in apps:
            if unit and not application_belongs_to_unit(app, unit):
                continue
            label = f"{app.student_first_name} {app.student_last_name}".strip().lower()
            if label:
                names.add(label)
    return names


def hidden_child_names(family, unit):
    if not family or not unit:
        return set()
    all_names = {child.name.strip().lower() for child in family.children.all() if child.name}
    return all_names - visible_child_names(family, unit, include_pending=True)


def family_visible_to_unit(family, unit):
    if not family:
        return False
    if not unit:
        return True
    if family.children.filter(child_unit_q(unit)).exists():
        return True
    from enrollment.locations import enrollment_keys_for_unit
    from enrollment.models import EnrollmentApplication

    if EnrollmentApplication.objects.filter(
        portal_family=family,
        program_location__in=enrollment_keys_for_unit(unit),
    ).exclude(status="declined").exists():
        return True
    if family.unit_id == unit.pk and not family.children.exists():
        return True
    return False


def families_qs_for_unit(unit):
    """Families staff at this unit should be able to open (have a child or application here)."""
    if not unit:
        return PortalFamily.objects.none()
    child_family_ids = PortalChild.objects.filter(child_unit_q(unit)).values("family_id")
    from enrollment.locations import enrollment_keys_for_unit
    from enrollment.models import EnrollmentApplication

    app_family_ids = (
        EnrollmentApplication.objects.filter(program_location__in=enrollment_keys_for_unit(unit))
        .exclude(status="declined")
        .values("portal_family_id")
    )
    empty_home = PortalFamily.objects.filter(unit=unit, children__isnull=True).values("pk")
    return PortalFamily.objects.filter(
        Q(pk__in=child_family_ids) | Q(pk__in=app_family_ids) | Q(pk__in=empty_home)
    ).distinct()


def family_can_move_home_unit(family, new_unit):
    """Move the family row only when it is a placeholder or has no kids at another site."""
    from .member_admin import is_placeholder_unit

    if not family or not new_unit:
        return False
    if family.unit_id == new_unit.pk:
        return False
    if is_placeholder_unit(family.unit):
        return True
    for child in family.children.filter(is_active=True):
        effective_id = child.unit_id or family.unit_id
        if effective_id and effective_id != new_unit.pk:
            return False
    return True


def assign_child_unit(child, unit, *, save=True):
    if not child or not unit:
        return child
    if child.unit_id == unit.pk:
        return child
    child.unit = unit
    if save:
        child.save(update_fields=["unit"])
    return child


def ledger_entry_visible_to_unit(entry, family, unit):
    """Staff see charges named for their unit's children; hide the other unit's names.

    Family-level rows (blank child_name) stay visible unless the description names
    a child from another unit. Family.balance itself is still shared.
    """
    if not unit:
        return True
    visible = visible_child_names(family, unit, include_pending=True)
    hidden = hidden_child_names(family, unit)
    name = (getattr(entry, "child_name", None) or "").strip().lower()
    if name:
        return name in visible
    description = (getattr(entry, "description", None) or "").lower()
    for hidden_name in hidden:
        if hidden_name and hidden_name in description:
            return False
    return True


def filter_ledger_entries_for_unit(entries, family, unit):
    if not unit:
        return list(entries)
    return [entry for entry in entries if ledger_entry_visible_to_unit(entry, family, unit)]


def filter_billing_dict_for_unit(billing, family, unit):
    """Strip other-unit children and ledger rows from a billing payload for staff."""
    if not billing or not unit:
        return billing
    visible = visible_child_names(family, unit, include_pending=False)
    hidden = hidden_child_names(family, unit)
    filtered = dict(billing)
    children = []
    for child in billing.get("children") or []:
        label = (child.get("name") or "").strip().lower()
        if label in visible:
            children.append(child)
    filtered["children"] = children
    ledger = []
    for row in billing.get("ledger") or []:
        child_name = (row.get("child") or "").strip().lower()
        if child_name:
            if child_name in visible:
                ledger.append(row)
            continue
        description = (row.get("description") or "").lower()
        if any(hidden_name and hidden_name in description for hidden_name in hidden):
            continue
        ledger.append(row)
    filtered["ledger"] = ledger
    return filtered


def child_name_allowed_for_unit(family, child_name, unit):
    if not unit:
        return True
    label = (child_name or "").strip().lower()
    if not label:
        return True
    return label in visible_child_names(family, unit, include_pending=True)


def unit_label_for_child(child):
    unit = child_effective_unit(child)
    if unit:
        return unit.name, unit.slug
    return "", ""
