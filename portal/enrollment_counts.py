"""One enrollment count for dashboard, units, programs, and reports.

Enrolled means an active child at their own program site who is approved
or already on the roster. Waitlist-only and other unapproved children are
not enrolled, even when a sibling in the same household is approved.
"""

from django.db.models import Exists, OuterRef, Q, Value
from django.db.models.functions import Concat, Lower, Trim

from enrollment.models import EnrollmentApplication

from .models import PortalChild, PortalUnit

COUNTED_ENROLLED_STATUSES = ("approved", "enrolled")


def application_child_name(app):
    return f"{app.student_first_name} {app.student_last_name}".strip()


def _application_full_name():
    return Lower(Trim(Concat("student_first_name", Value(" "), "student_last_name")))


def _apps_for_child(*, statuses=None):
    qs = EnrollmentApplication.objects.annotate(full_name=_application_full_name()).filter(
        portal_family_id=OuterRef("family_id"),
        full_name=Lower(Trim(OuterRef("name"))),
    )
    if statuses is not None:
        return qs.filter(status__in=statuses)
    return qs


def annotate_visible_members(qs):
    """Keep roster kids with no application, or kids with an approved/enrolled app.

    Pending, under-review, waitlist, pending-documents, and declined-only
    leftovers are not members on family lists or reports.
    """
    return qs.annotate(
        has_application=Exists(_apps_for_child()),
        has_approved=Exists(_apps_for_child(statuses=COUNTED_ENROLLED_STATUSES)),
    ).filter(Q(has_application=False) | Q(has_approved=True))


def visible_member_children_qs(*, unit=None, active_only=True):
    """Children that count as members on family lists and reports.

    Approved/enrolled applications count. Roster kids with no application still
    count (already-active members). Unapproved-only leftovers do not.
    """
    from .unit_visibility import child_unit_q

    qs = PortalChild.objects.exclude(family__slug="practice")
    if active_only:
        qs = qs.filter(is_active=True)
    if unit is not None:
        qs = qs.filter(child_unit_q(unit))
    return annotate_visible_members(qs.select_related("family", "family__unit", "unit"))


def enrolled_children_qs(unit=None):
    """Active children who count as enrolled, optionally limited to one unit.

    A child is counted at `child.unit`, or the family unit when that is unset.
    Children with only waitlist (or other non-approved) applications are left out.
    Children with no application still count — they are already on the roster.
    """
    return visible_member_children_qs(unit=unit, active_only=True)


def unit_enrollment_count(unit):
    if not unit:
        return 0
    return enrolled_children_qs(unit).count()


def unit_capacity(unit):
    if not unit:
        return 0
    return int(getattr(unit, "capacity", 0) or 0)


def unit_enrollment_snapshot(unit):
    """Enrolled / stored capacity for one unit, including inactive sites."""
    return {
        "enrolled": unit_enrollment_count(unit),
        "capacity": unit_capacity(unit),
    }


def dashboard_enrollment_totals():
    """Org-wide enrolled total plus per-unit rows used on the admin dashboard.

    Placeholder sites such as Main location are omitted from the dashboard table
    and the org total. Units & locations still uses `unit_enrollment_count` for
    those cards so a leftover placeholder shows 0 / its stored cap honestly.
    """
    from .member_admin import is_placeholder_unit

    by_unit = []
    total = 0
    for unit in PortalUnit.objects.order_by("name"):
        enrolled = unit_enrollment_count(unit)
        if is_placeholder_unit(unit):
            continue
        total += enrolled
        by_unit.append(
            {
                "unit": unit.name,
                "slug": unit.slug,
                "enrolled": enrolled,
                "capacity": unit_capacity(unit),
                "active": unit.is_active,
                "pk": unit.pk,
            }
        )
    return {"total_enrolled": total, "by_unit": by_unit}
