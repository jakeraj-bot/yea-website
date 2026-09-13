"""Record and query portal activity without storing secrets."""

from datetime import datetime, time

from django.contrib.auth import get_user_model
from django.utils import timezone
from django.utils.dateparse import parse_date

from .models import PortalActivityEvent, PortalParentAccount, PortalStaffAccount

SENSITIVE_KEYS = {
    "password",
    "password1",
    "password2",
    "new_password",
    "confirm_password",
    "current_password",
    "old_password",
    "temp_password",
    "card",
    "card_number",
    "cardnumber",
    "cc_number",
    "cvc",
    "cvv",
    "exp",
    "expiry",
    "exp_month",
    "exp_year",
    "card_cvc",
    "stripe_token",
    "payment_method",
    "client_secret",
    "secret",
}

SKIP_PATH_PREFIXES = (
    "/portal/stripe/webhook/",
    "/static/",
    "/media/",
)

SKIP_PATH_EXACT = {
    "/portal/staff/unit/switch/",
}

ACTION_LABELS = dict(PortalActivityEvent.ACTION_CHOICES)

REQUEST_ATTR = "_portal_activity_logged"


def mark_logged(request):
    if request is not None:
        setattr(request, REQUEST_ATTR, True)


def already_logged(request):
    return bool(request is not None and getattr(request, REQUEST_ATTR, False))


def delete_reason_from_post(request):
    return (getattr(request, "POST", {}) or {}).get("delete_reason", "").strip()


def require_delete_reason(request):
    reason = delete_reason_from_post(request)
    if not reason:
        mark_logged(request)
        raise ValueError("Enter a reason before deleting. Cancel if you do not want to delete.")
    return reason


def _related_or_none(user, attr):
    if user is None:
        return None
    try:
        return getattr(user, attr)
    except Exception:
        return None


def actor_display_name(user):
    if not user or not getattr(user, "is_authenticated", False):
        return ""
    account = _related_or_none(user, "portal_staff_account")
    if account and getattr(account, "display_name", ""):
        return account.display_name
    parent = _related_or_none(user, "portal_parent_account")
    if parent and getattr(parent, "family", None):
        return f"{parent.family.name} parent"
    return (user.get_full_name() or user.username or "").strip()


def actor_role_label(user):
    if not user or not getattr(user, "is_authenticated", False):
        return ""
    account = _related_or_none(user, "portal_staff_account")
    if account:
        if account.role == "Portal admin" or account.all_units_access:
            return "Admin"
        return "Staff"
    if _related_or_none(user, "portal_parent_account"):
        return "Parent"
    return "User"


def _client_path(request):
    if request is None:
        return ""
    return (getattr(request, "path", "") or "")[:255]


def _safe_details(text):
    return (text or "").strip()[:2000]


def log_activity(
    request=None,
    *,
    user=None,
    action,
    action_label="",
    object_type="",
    object_label="",
    details="",
    delete_reason="",
    unit=None,
    page_path="",
):
    actor = user
    if actor is None and request is not None:
        actor = getattr(request, "user", None)
    if actor is not None and not getattr(actor, "is_authenticated", False):
        actor = None
    if actor is None:
        return None

    label = (action_label or ACTION_LABELS.get(action) or action.replace("_", " ").title())[:120]
    event = PortalActivityEvent.objects.create(
        actor=actor,
        actor_username=(actor.username or "")[:150],
        actor_name=actor_display_name(actor)[:200],
        actor_role=actor_role_label(actor)[:32],
        unit=unit,
        action=action or PortalActivityEvent.ACTION_OTHER,
        action_label=label,
        object_type=(object_type or "")[:64],
        object_label=(object_label or "")[:255],
        page_path=(page_path or _client_path(request))[:255],
        details=_safe_details(details),
        delete_reason=(delete_reason or "")[:2000],
    )
    mark_logged(request)
    return event


def log_delete(request, *, object_type, object_label, details="", unit=None):
    reason = require_delete_reason(request)
    return log_activity(
        request,
        action=PortalActivityEvent.ACTION_DELETE,
        action_label=f"Deleted {object_type}",
        object_type=object_type,
        object_label=object_label,
        details=details,
        delete_reason=reason,
        unit=unit,
    )


def _infer_action(request):
    path = (getattr(request, "path", "") or "").lower()
    posted = getattr(request, "POST", {}) or {}
    action = (posted.get("action") or "").lower()
    if "delete" in path or action.startswith("delete") or action == "delete":
        return PortalActivityEvent.ACTION_DELETE, "Deleted"
    if "login" in path:
        return PortalActivityEvent.ACTION_LOGIN, "Signed in"
    if "email" in path:
        return PortalActivityEvent.ACTION_EMAIL, "Sent email"
    if "password" in path:
        return PortalActivityEvent.ACTION_PASSWORD_RESET, "Reset password"
    if "attendance" in path or "check-in" in path or "check-out" in path or "absent" in path:
        return PortalActivityEvent.ACTION_ATTENDANCE, "Attendance"
    if "billing" in path or action in {"charge", "payment", "credit", "card_checkout"}:
        if action == "charge":
            return PortalActivityEvent.ACTION_CHARGE, "Posted a charge"
        if action == "payment":
            return PortalActivityEvent.ACTION_PAYMENT, "Recorded a payment"
        if action == "card_checkout":
            return PortalActivityEvent.ACTION_PAYMENT, "Started a card payment"
        return PortalActivityEvent.ACTION_SAVE, "Saved billing"
    if "agency" in path or "4cs" in path:
        return PortalActivityEvent.ACTION_AGENCY, "Saved 4Cs"
    if "plan" in path:
        return PortalActivityEvent.ACTION_PLAN, "Saved a plan"
    if "application" in path or "review" in path:
        return PortalActivityEvent.ACTION_APPLICATION, "Application review"
    return PortalActivityEvent.ACTION_SAVE, "Saved"


def _object_from_request(request):
    posted = getattr(request, "POST", {}) or {}
    for key in ("family_slug", "child_name", "app_slug"):
        value = (posted.get(key) or "").strip()
        if value:
            return key.replace("_", " "), value
    path = getattr(request, "path", "") or ""
    return "page", path


def should_middleware_log(request, response):
    if request is None or already_logged(request):
        return False
    if request.method not in {"POST", "PUT", "PATCH", "DELETE"}:
        return False
    user = getattr(request, "user", None)
    if user is None or not getattr(user, "is_authenticated", False):
        return False
    path = getattr(request, "path", "") or ""
    if not path.startswith("/portal/"):
        return False
    if path in SKIP_PATH_EXACT:
        return False
    if any(path.startswith(prefix) for prefix in SKIP_PATH_PREFIXES):
        return False
    status = getattr(response, "status_code", 0)
    return 200 <= int(status) < 400


def log_from_middleware(request, response):
    if not should_middleware_log(request, response):
        return None
    action, label = _infer_action(request)
    object_type, object_label = _object_from_request(request)
    return log_activity(
        request,
        action=action,
        action_label=label,
        object_type=object_type,
        object_label=object_label,
    )


def _date_bound(value, end=False):
    if not value:
        return None
    parsed = parse_date(str(value).strip())
    if not parsed:
        return None
    clock = time.max if end else time.min
    combined = datetime.combine(parsed, clock)
    if timezone.is_naive(combined):
        combined = timezone.make_aware(combined, timezone.get_current_timezone())
    return combined


def activity_people(*, search=""):
    User = get_user_model()
    staff_ids = set(
        PortalStaffAccount.objects.filter(is_active=True).values_list("user_id", flat=True)
    )
    parent_ids = set(PortalParentAccount.objects.values_list("user_id", flat=True))
    logged_ids = set(PortalActivityEvent.objects.values_list("actor_id", flat=True))
    user_ids = {pk for pk in (staff_ids | parent_ids | logged_ids) if pk}
    users = (
        User.objects.filter(pk__in=user_ids)
        .select_related(
            "portal_staff_account",
            "portal_staff_account__unit",
            "portal_parent_account",
            "portal_parent_account__family",
            "portal_parent_account__family__unit",
        )
        .order_by("first_name", "last_name", "username")
    )
    needle = (search or "").strip().lower()
    people = []
    for user in users:
        staff = _related_or_none(user, "portal_staff_account")
        parent = _related_or_none(user, "portal_parent_account")
        name = actor_display_name(user) or user.username
        role = actor_role_label(user)
        unit_name = ""
        if staff and staff.unit_id:
            unit_name = staff.unit.name
        elif parent and parent.family_id and parent.family.unit_id:
            unit_name = parent.family.unit.name
        haystack = " ".join(
            [
                name,
                user.username,
                user.email or "",
                role,
                unit_name,
                getattr(staff, "role", "") if staff else "",
                getattr(parent, "family", None).name if parent and parent.family_id else "",
            ]
        ).lower()
        if needle and needle not in haystack:
            continue
        people.append(
            {
                "id": user.pk,
                "name": name,
                "username": user.username,
                "email": user.email or "",
                "role": role,
                "unit": unit_name,
            }
        )
    people.sort(key=lambda row: (row["name"].lower(), row["username"].lower()))
    return people


def events_for_user(user_id, *, date_from="", date_to=""):
    qs = PortalActivityEvent.objects.filter(actor_id=user_id).select_related("unit")
    start = _date_bound(date_from, end=False)
    end = _date_bound(date_to, end=True)
    if start:
        qs = qs.filter(created_at__gte=start)
    if end:
        qs = qs.filter(created_at__lte=end)
    return qs


def activity_page_context(request, *, area="admin"):
    selected_id = (request.GET.get("user") or "").strip()
    search = (request.GET.get("q") or "").strip()
    date_from = (request.GET.get("date_from") or "").strip()
    date_to = (request.GET.get("date_to") or "").strip()
    people = activity_people(search=search)
    selected = None
    events = []
    if selected_id.isdigit():
        selected = next((row for row in people if str(row["id"]) == selected_id), None)
        if selected is None:
            User = get_user_model()
            user = User.objects.filter(pk=int(selected_id)).first()
            if user:
                selected = {
                    "id": user.pk,
                    "name": actor_display_name(user) or user.username,
                    "username": user.username,
                    "email": user.email or "",
                    "role": actor_role_label(user),
                    "unit": "",
                }
        if selected:
            events = list(events_for_user(selected["id"], date_from=date_from, date_to=date_to)[:200])
    return {
        "activity_people": people,
        "activity_selected": selected,
        "activity_events": events,
        "activity_search": search,
        "activity_date_from": date_from,
        "activity_date_to": date_to,
        "activity_user_id": selected_id,
        "page_title": "Activity",
    }
