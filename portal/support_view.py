import re
from datetime import timedelta

from django.utils import timezone

from .models import PortalSupportViewSession

SUPPORT_VIEW_MINUTES = 120
_CARD_LAST4_RE = re.compile(r"(ending\s+)\d{4}", re.IGNORECASE)


def mask_card_text(value):
    return _CARD_LAST4_RE.sub(r"\1••••", value or "")


def mask_parent_account_cards(account_data):
    """Hide card numbers, expiry, and Stripe ids from admin support views."""
    data = dict(account_data or {})
    masked_methods = []
    for method in data.get("payment_methods") or []:
        brand = method.get("brand") or (method.get("label") or "Card").split()[0] or "Card"
        masked_methods.append(
            {
                **method,
                "label": f"{brand} on file · ••••",
                "last4": "••••",
                "expires": "••/••",
                "stripe_id": "",
            }
        )
    data["payment_methods"] = masked_methods
    data["saved_cards"] = [
        {**card, "last4": "••••", "brand": card.get("brand", "Card"), "expires": "••/••"}
        for card in data.get("saved_cards") or []
    ]
    data["stripe_customer_id"] = ""
    data["password_preview"] = ""
    return data


def mask_billing_card_mentions(billing):
    data = dict(billing or {})
    data["ledger"] = [
        {**row, "description": mask_card_text(row.get("description", ""))}
        for row in data.get("ledger") or []
    ]
    return data


def mask_receipt_card_mentions(receipts):
    masked = []
    for receipt in receipts or []:
        item = dict(receipt)
        item["method"] = mask_card_text(item.get("method", ""))
        item["description"] = mask_card_text(item.get("description", ""))
        masked.append(item)
    return masked


def start_support_view(family, admin_user):
    now = timezone.now()
    session = (
        PortalSupportViewSession.objects.filter(family=family, ended_at__isnull=True, expires_at__gt=now)
        .order_by("-started_at")
        .first()
    )
    if session:
        session.admin_user = admin_user
        session.expires_at = now + timedelta(minutes=SUPPORT_VIEW_MINUTES)
        session.save(update_fields=["admin_user", "expires_at", "last_seen_at"])
        return session
    return PortalSupportViewSession.objects.create(
        family=family,
        admin_user=admin_user,
        expires_at=now + timedelta(minutes=SUPPORT_VIEW_MINUTES),
    )


def end_support_view(family):
    now = timezone.now()
    return PortalSupportViewSession.objects.filter(family=family, ended_at__isnull=True).update(ended_at=now)


def active_support_view(family):
    if not family:
        return None
    now = timezone.now()
    return (
        PortalSupportViewSession.objects.filter(family=family, ended_at__isnull=True, expires_at__gt=now)
        .select_related("admin_user")
        .order_by("-started_at")
        .first()
    )
