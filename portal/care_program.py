"""After-care / Before-care membership for attendance sheets and the before-care roster.

Before-care kids are children with an approved or enrolled before-care application.
Waitlist-only before-care does not count. Children with no approved care application
are treated as After-care on sheets (the historical after-school roster).
An inactive application does not count for that program — the child can stay on
the other program’s sheets.
"""

from django.utils import timezone

from enrollment.models import EnrollmentApplication
from enrollment.portal_integration import program_display_for_application

from .member_report import _family_status, _match_apps_for_child
from .models import PortalChild
from .phone_format import format_us_phone

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

PROGRAM_ACTION_LABELS = {
    "after_school": "after-care",
    "before_care": "before-care",
    "drop_off": "drop-off",
    "summer_camp": "summer camp",
}


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


def _care_key_for_app(app):
    program = (app.program or "").strip()
    if program == "before_care":
        return CARE_BEFORE
    if program == "after_school":
        return CARE_AFTER
    return ""


def _is_approved_care_app(app):
    return (app.status or "").strip().lower() in APPROVED_CARE_STATUSES


def application_is_program_active(app):
    """Approved/enrolled applications default to active when the flag is missing."""
    if app is None:
        return False
    return bool(getattr(app, "is_active", True))


def approved_care_keys_for_child(child, apps=None):
    """Return {'after'} and/or {'before'} from active approved/enrolled applications only."""
    keys = set()
    for app in apps or []:
        if not _is_approved_care_app(app) or not application_is_program_active(app):
            continue
        key = _care_key_for_app(app)
        if key:
            keys.add(key)
    return keys


def inactive_approved_care_keys_for_child(child, apps=None):
    """Approved/enrolled applications staff marked inactive for a program."""
    keys = set()
    for app in apps or []:
        if not _is_approved_care_app(app) or application_is_program_active(app):
            continue
        key = _care_key_for_app(app)
        if key:
            keys.add(key)
    return keys


def child_matches_care_filter(child, apps, care):
    care = normalize_care_filter(care)
    keys = approved_care_keys_for_child(child, apps)
    inactive_keys = inactive_approved_care_keys_for_child(child, apps)
    if care == CARE_ALL:
        if not keys and inactive_keys:
            return False
        return True
    if care == CARE_BEFORE:
        return CARE_BEFORE in keys
    if CARE_AFTER in keys:
        return True
    if CARE_BEFORE in keys:
        return False
    if inactive_keys:
        return False
    return True


def filter_children_by_care(children, care):
    child_list = list(children)
    if not child_list:
        return child_list
    apps_by_family = apps_by_family_for_children(child_list)
    matched = []
    for child in child_list:
        apps = _match_apps_for_child(child, apps_by_family.get(child.family_id, []))
        if child_matches_care_filter(child, apps, care):
            matched.append(child)
    return matched


def program_action_label(app):
    key = (getattr(app, "program", None) or "").strip()
    return PROGRAM_ACTION_LABELS.get(key) or (program_display_for_application(app, short=True) or "program").lower()


def serialize_application_status(app):
    """Staff UI payload for one program application on a family profile."""
    if app is None:
        return None
    label = program_display_for_application(app, short=True) or app.get_program_display() or "Program"
    return {
        "app_slug": str(app.reference),
        "program_key": app.program,
        "program_label": label,
        "program_short": program_action_label(app),
        "is_active": application_is_program_active(app),
        "status": app.get_status_display() if hasattr(app, "get_status_display") else (app.status or ""),
    }


def application_status_rows_for_child(child, apps=None):
    rows = []
    for app in apps or []:
        if (app.status or "").strip().lower() == "declined":
            continue
        rows.append(serialize_application_status(app))
    rows.sort(key=lambda row: ((row.get("program_label") or "").casefold(), row.get("app_slug") or ""))
    return rows


def parent_contact_for_child(child, apps=None):
    """Primary parent name, formatted phone, and email for weekly attendance."""
    family = getattr(child, "family", None)
    name = (getattr(family, "primary_contact", None) or "").strip()
    phone = ""
    email = ""
    for app in apps or []:
        app_name = f"{getattr(app, 'primary_first_name', '')} {getattr(app, 'primary_last_name', '')}".strip()
        if app_name and not name:
            name = app_name
        raw_phone = (getattr(app, "primary_phone", None) or "").strip()
        if raw_phone:
            phone = raw_phone
            email = (
                getattr(app, "primary_email_address", None) or getattr(app, "primary_email", None) or ""
            ).strip()
            if app_name:
                name = name or app_name
            break
    if not name and family:
        name = (family.primary_contact or family.name or "").strip()
    return {
        "parent_name": name,
        "parent_phone": format_us_phone(phone),
        "parent_email": email,
    }


def truthy_query_flag(value):
    raw = (value or "").strip().lower()
    return raw in {"1", "true", "yes", "on"}


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
            if (
                app.program == "before_care"
                and (app.status or "").strip().lower() in APPROVED_CARE_STATUSES
                and application_is_program_active(app)
            ):
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
