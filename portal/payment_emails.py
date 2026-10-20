"""Whether automatic parent payment emails should go out for a family or charge.

Settings → Email ``send_charge_posted_emails`` (off by default) is the org switch
for charge-posted notices. Child-level ``PortalChild.is_active=False`` still
skips mail when that switch is on. Per-application inactive (before-care vs
after-care) suppresses mail for that program's charges only. Staff-composed
Email parent, approval, password-reset, receipts, and Friday late-fee reminders
are not gated by the charge-posted toggle.
"""

from decimal import Decimal

from .care_program import (
    CARE_AFTER,
    CARE_BEFORE,
    approved_care_keys_for_child,
    inactive_approved_care_keys_for_child,
)
from .family_list import child_balance_from_map, child_balance_map, household_ledger_totals
from .member_report import _match_apps_for_child
from .models import PortalFamily


def child_matching_ledger_name(family, child_name):
    needle = (child_name or "").strip().casefold()
    if not needle or family is None:
        return None
    children = family.children.all() if getattr(family, "pk", None) else []
    for child in children:
        if (child.name or "").strip().casefold() == needle:
            return child
    return None


def family_has_active_member(family):
    """True when the household has at least one active child on the roster."""
    if family is None or not getattr(family, "pk", None):
        return False
    cached = getattr(family, "_prefetched_objects_cache", None)
    if cached and "children" in cached:
        return any(getattr(child, "is_active", True) for child in family.children.all())
    return family.children.filter(is_active=True).exists()


def family_may_receive_automatic_payment_email(family):
    """Skip when every roster child is inactive.

    Families with no children yet (application-only / new login) still receive
    household reminders — there is no inactive member to hide.
    """
    if family is None or not getattr(family, "pk", None):
        return False
    children = list(family.children.all())
    if not children:
        return True
    return any(getattr(child, "is_active", True) for child in children)


def care_key_from_charge_text(text):
    hay = (text or "").lower().replace("_", " ").replace("-", " ")
    if "before care" in hay:
        return CARE_BEFORE
    if "after care" in hay or "after school" in hay:
        return CARE_AFTER
    return ""


def _apps_for_child(child):
    family = getattr(child, "family", None) if child is not None else None
    if family is None:
        return []
    return _match_apps_for_child(child, list(family.enrollment_applications.all()))


def charge_is_for_inactive_program(child, entry=None):
    """True when this ledger line is for a program staff marked inactive."""
    if child is None:
        return False
    apps = _apps_for_child(child)
    active_keys = approved_care_keys_for_child(child, apps)
    inactive_keys = inactive_approved_care_keys_for_child(child, apps)
    if not inactive_keys:
        return False
    text = " ".join(
        [
            getattr(entry, "description", None) or "",
            getattr(entry, "child_name", None) or "",
        ]
    )
    care = care_key_from_charge_text(text)
    if care:
        return care in inactive_keys
    if not active_keys:
        return True
    return False


def charge_posted_emails_enabled():
    """Settings → Email toggle. Off until staff turns automatic charge mail back on."""
    from .models import PortalOrgSetting

    return bool(PortalOrgSetting.load().send_charge_posted_emails)


def set_charge_posted_emails_enabled(enabled=True):
    from .models import PortalOrgSetting

    setting = PortalOrgSetting.load()
    setting.send_charge_posted_emails = bool(enabled)
    setting.save(update_fields=["send_charge_posted_emails"])
    return setting


def should_send_automatic_payment_email(family, entry=None):
    """Charge notices, late-fee/balance jobs, and auto plan posts use this gate."""
    if not family_may_receive_automatic_payment_email(family):
        return False
    child_name = (getattr(entry, "child_name", None) or "").strip() if entry is not None else ""
    child = child_matching_ledger_name(family, child_name) if child_name else None
    if child is None:
        return True
    if not child.is_active:
        return False
    if charge_is_for_inactive_program(child, entry):
        return False
    return True


def active_member_family_balance(family):
    """Household amount used in automatic payment emails: active children only."""
    if family is None or not getattr(family, "pk", None):
        return Decimal("0")
    children = list(family.children.all())
    if not children:
        return household_ledger_totals([family.pk]).get(family.pk, Decimal("0"))
    active = [child for child in children if child.is_active]
    if not active:
        return Decimal("0")
    maps = child_balance_map(family)
    total = Decimal("0")
    for child in active:
        total += child_balance_from_map(maps, child.name)
    return total


def families_with_active_member_balance(*, unit=None):
    """Active families whose *active* children still owe.

    Leftover balances on inactive children do not trigger automatic reminders.
    """
    from .member_admin import is_placeholder_unit
    from .unit_visibility import children_for_unit

    families = (
        PortalFamily.objects.select_related("unit")
        .prefetch_related("children")
        .filter(status="Active")
        .exclude(slug="practice")
    )
    if unit:
        family_ids = set(children_for_unit(unit, active_only=True).values_list("family_id", flat=True))
        families = families.filter(pk__in=family_ids)
    rows = []
    for family in families:
        if is_placeholder_unit(family.unit):
            continue
        if not family_has_active_member(family):
            continue
        total = active_member_family_balance(family)
        if total <= 0:
            continue
        rows.append({"family": family, "balance": total})
    return rows


def parent_emails_for_automatic_payment_mail():
    """Parent addresses for first-day / bulk payment reminders (active members)."""
    from .member_admin import parent_email_recipients

    allowed = []
    seen = set()
    rows = parent_email_recipients()
    family_ids = [row["family_id"] for row in rows if not isinstance(row.get("family_id"), str)]
    families = {
        family.pk: family
        for family in PortalFamily.objects.filter(pk__in=family_ids).prefetch_related("children")
    }
    for row in rows:
        email = (row.get("email") or "").strip()
        if not email or email.lower() in seen:
            continue
        fid = row.get("family_id")
        if isinstance(fid, str):
            allowed.append(email)
            seen.add(email.lower())
            continue
        family = families.get(fid)
        if family is None or family_may_receive_automatic_payment_email(family):
            allowed.append(email)
            seen.add(email.lower())
    return allowed
