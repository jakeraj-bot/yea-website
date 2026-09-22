"""After-care / Before-care membership for attendance sheets and the before-care roster.

Before-care kids are children with an approved or enrolled before-care application.
Waitlist-only before-care does not count. Children with no approved care application
are treated as After-care on sheets (the historical after-school roster).
"""

from django.utils import timezone

from enrollment.models import EnrollmentApplication

from .member_report import _family_status, _match_apps_for_child
from .models import PortalChild

CARE_ALL = "all"
CARE_AFTER = "after"
CARE_BEFORE = "before"

CARE_FILTER_CHOICES = (
    ("", "All"),
    (CARE_AFTER, "After-care"),
    (CARE_BEFORE, "Before-care"),
)

CARE_LABELS = {
    CARE_ALL: "All",
    CARE_AFTER: "After-care",
    CARE_BEFORE: "Before-care",
}

APPROVED_CARE_STATUSES = frozenset({"approved", "enrolled"})


def normalize_care_filter(value):
    raw = (value or "").strip().lower().replace(" ", "_").replace("-", "_")
    if raw in {"after", "after_care", "after_school"}:
        return CARE_AFTER
    if raw in {"before", "before_care"}:
        return CARE_BEFORE
    return CARE_ALL


def care_filter_label(value):
    return CARE_LABELS.get(normalize_care_filter(value), "All")


def apps_by_family_for_children(children):
    family_ids = {child.family_id for child in children if getattr(child, "family_id", None)}
    apps_by_family = {}
    if not family_ids:
        return apps_by_family
    for app in EnrollmentApplication.objects.filter(portal_family_id__in=family_ids):
        apps_by_family.setdefault(app.portal_family_id, []).append(app)
    return apps_by_family


def approved_care_keys_for_child(child, apps=None):
    """Return {'after'} and/or {'before'} from approved/enrolled applications only."""
    keys = set()
    for app in apps or []:
        if (app.status or "").strip().lower() not in APPROVED_CARE_STATUSES:
            continue
        program = (app.program or "").strip()
        if program == "before_care":
            keys.add(CARE_BEFORE)
        elif program == "after_school":
            keys.add(CARE_AFTER)
    return keys


def child_matches_care_filter(child, apps, care):
    care = normalize_care_filter(care)
    if care == CARE_ALL:
        return True
    keys = approved_care_keys_for_child(child, apps)
    if care == CARE_BEFORE:
        return CARE_BEFORE in keys
    if CARE_AFTER in keys:
        return True
    if CARE_BEFORE in keys:
        return False
    return True


def filter_children_by_care(children, care):
    care = normalize_care_filter(care)
    child_list = list(children)
    if care == CARE_ALL or not child_list:
        return child_list
    apps_by_family = apps_by_family_for_children(child_list)
    matched = []
    for child in child_list:
        apps = _match_apps_for_child(child, apps_by_family.get(child.family_id, []))
        if child_matches_care_filter(child, apps, care):
            matched.append(child)
    return matched


def before_care_roster_rows(*, unit=None, admin=False, query=""):
    """Active children with approved/enrolled before-care. Inactive and waitlist-only stay off."""
    from .member_admin import is_placeholder_unit
    from .unit_visibility import children_for_unit, unit_label_for_child

    if admin and not unit:
        children = [
            child
            for child in PortalChild.objects.filter(is_active=True)
            .select_related("family", "family__unit", "unit")
            .order_by("name", "id")
            if not is_placeholder_unit(child.unit or (child.family.unit if child.family_id else None))
        ]
    elif unit:
        children = list(children_for_unit(unit, active_only=True).order_by("name", "id"))
    else:
        children = []

    apps_by_family = apps_by_family_for_children(children)
    needle = (query or "").strip().lower()
    rows = []
    for child in children:
        family = child.family
        apps = _match_apps_for_child(child, apps_by_family.get(child.family_id, []))
        if CARE_BEFORE not in approved_care_keys_for_child(child, apps):
            continue
        if needle:
            hay = f"{child.name or ''} {family.name if family else ''}".lower()
            if needle not in hay:
                continue
        unit_name, unit_slug = unit_label_for_child(child)
        school = (child.school or "").strip()
        for app in apps:
            if app.program == "before_care" and (app.status or "").strip().lower() in APPROVED_CARE_STATUSES:
                if not school:
                    school = (app.student_school or "").strip()
                break
        rows.append(
            {
                "child_id": child.pk,
                "child": child.name,
                "family": family.name if family else "",
                "family_slug": family.slug if family else "",
                "family_id": family.pk if family else "",
                "unit": unit_name,
                "unit_slug": unit_slug,
                "school": school or "—",
                "status": _family_status(family, child) if family else "Active",
            }
        )
    rows.sort(
        key=lambda row: (
            (row.get("child") or "").casefold(),
            (row.get("family") or "").casefold(),
            row.get("child_id") or 0,
        )
    )
    return rows


def before_care_roster_bundle(filters=None, *, unit=None, admin=False):
    from .member_admin import is_placeholder_unit
    from .models import PortalUnit
    from .staff_services import resolve_weekly_attendance_unit

    filters = dict(filters or {})
    query = (filters.get("q") or "").strip()
    unit_slug = (filters.get("unit") or "").strip()
    scoped_unit = unit
    if admin:
        scoped_unit = resolve_weekly_attendance_unit(unit_slug, admin=True)
    rows = before_care_roster_rows(unit=scoped_unit, admin=admin, query=query)
    if admin:
        units = [
            (item.slug, item.name)
            for item in PortalUnit.objects.filter(is_active=True).order_by("name")
            if not is_placeholder_unit(item)
        ]
    else:
        units = [(unit.slug, unit.name)] if unit and not is_placeholder_unit(unit) else []
    return {
        "report_rows": rows,
        "listed_count": len(rows),
        "generated_date": timezone.localdate().strftime("%B %d, %Y"),
        "selected_unit_slug": scoped_unit.slug if scoped_unit else "",
        "selected_unit_name": scoped_unit.name if scoped_unit else ("All units" if admin else ""),
        "filter_options": {"units": units},
    }
