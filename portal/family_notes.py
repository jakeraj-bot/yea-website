"""Staff and admin notes on a child / family account. Parents never see these."""

from django.db.models import Q

from .activity_log import actor_display_name, actor_role_label, log_activity, require_delete_reason
from .models import PortalActivityEvent, PortalChild, PortalFamilyNote
from .unit_visibility import child_belongs_to_unit, child_effective_unit, child_unit_q


def notes_qs_for_family(family, unit=None):
    qs = PortalFamilyNote.objects.filter(family=family).select_related("author", "child", "unit")
    if unit is None:
        return qs
    child_ids = family.children.filter(child_unit_q(unit)).values_list("pk", flat=True)
    return qs.filter(Q(unit=unit) | Q(child_id__in=child_ids))


def note_visible_to_unit(note, unit):
    if not unit:
        return True
    if note.unit_id == unit.pk:
        return True
    if note.child_id and child_belongs_to_unit(note.child, unit):
        return True
    return False


def add_family_note(family, *, body, user, child=None, unit=None):
    text = (body or "").strip()
    if not text:
        raise ValueError("Enter a note.")
    if child and child.family_id != family.pk:
        raise ValueError("That child is not on this family.")
    if unit and child and not child_belongs_to_unit(child, unit):
        raise ValueError("That child is not at this unit.")
    if child:
        note_unit = child_effective_unit(child)
    else:
        note_unit = unit or family.unit
    display = ""
    role = ""
    author = None
    if user is not None and getattr(user, "is_authenticated", False):
        author = user
        display = actor_display_name(user) or (user.username or "").strip()
        role = actor_role_label(user)
    return PortalFamilyNote.objects.create(
        family=family,
        child=child,
        unit=note_unit,
        author=author,
        author_name=(display or "Staff")[:200],
        author_role=(role or "")[:64],
        body=text,
    )


def resolve_note_child(family, child_id, unit=None):
    raw = str(child_id or "").strip()
    if not raw:
        return None
    if not raw.isdigit():
        raise ValueError("Choose a child on this account.")
    child = (
        PortalChild.objects.select_related("family", "family__unit", "unit")
        .filter(pk=int(raw), family=family)
        .first()
    )
    if not child:
        raise ValueError("That child is not on this family.")
    if unit and not child_belongs_to_unit(child, unit):
        raise ValueError("That child is not at this unit.")
    return child


def delete_family_note(note, request, unit=None):
    if not note_visible_to_unit(note, unit):
        raise ValueError("Note not found.")
    reason = require_delete_reason(request)
    log_activity(
        request,
        action=PortalActivityEvent.ACTION_DELETE,
        action_label="Deleted a family note",
        object_type="family note",
        object_label=note.family.name,
        details=(note.body or "")[:200],
        delete_reason=reason,
        unit=note.unit or unit,
    )
    note.delete()
    return reason
