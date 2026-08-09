"""Read org-wide fee amounts from PortalFeeRule (Django admin / portal settings)."""

from decimal import Decimal, InvalidOperation

from .admin_config import ensure_admin_config_minimal
from .models import PortalFeeRule


def get_fee_rule(key):
    ensure_admin_config_minimal()
    return PortalFeeRule.objects.filter(key=key).first()


def get_fee_amount(key, default=None):
    """Return Decimal amount for a fee rule key, or default if missing/invalid."""
    rule = get_fee_rule(key)
    if not rule or not (rule.amount or "").strip():
        return default
    try:
        return Decimal(str(rule.amount).replace(",", "").strip())
    except (InvalidOperation, TypeError):
        return default


def get_fee_display(key, default=""):
    rule = get_fee_rule(key)
    if not rule:
        return default
    return rule.display or (f"${rule.amount}" if rule.amount else default)
