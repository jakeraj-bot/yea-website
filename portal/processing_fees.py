"""Card processing fees parents pay on online payments (2.90% + $0.30 by default)."""

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from .models import PortalProcessingFee

DEFAULT_PERCENT = Decimal("2.90")
DEFAULT_FLAT = Decimal("0.30")
CENTS = Decimal("0.01")


def _as_decimal(value, fallback=Decimal("0")):
    try:
        return Decimal(str(value).replace(",", "").strip() or "0")
    except (InvalidOperation, TypeError, AttributeError):
        return fallback


def get_active_processing_fee():
    try:
        fee = PortalProcessingFee.objects.filter(is_active=True).order_by("pk").first()
    except Exception:
        fee = None
    if fee:
        return {
            "percent": fee.percent or DEFAULT_PERCENT,
            "flat": fee.flat_amount if fee.flat_amount is not None else DEFAULT_FLAT,
            "name": fee.name or "Card processing",
        }
    return {
        "percent": DEFAULT_PERCENT,
        "flat": DEFAULT_FLAT,
        "name": "Card processing",
    }


def stripe_fee_display():
    fee = get_active_processing_fee()
    percent = fee["percent"]
    flat = fee["flat"]
    return {
        "percent": float(percent),
        "percent_display": f"{percent:.2f}",
        "fixed_cents": int((flat * 100).quantize(Decimal("1"))),
        "flat_display": f"{flat:.2f}",
        "label": "Card processing fee",
        "note": f"You pay the card processing fee ({percent}% + ${flat}) on each online payment.",
    }


def calculate_card_processing_fee(amount_str):
    amount = _as_decimal(amount_str)
    if amount < 0:
        amount = Decimal("0")
    fee = get_active_processing_fee()
    if amount <= 0:
        processing = Decimal("0.00")
    else:
        processing = (amount * fee["percent"] / Decimal("100") + fee["flat"]).quantize(
            CENTS, rounding=ROUND_HALF_UP
        )
    total = (amount + processing).quantize(CENTS, rounding=ROUND_HALF_UP)
    return {
        "subtotal": f"{amount:.2f}",
        "fee": f"{processing:.2f}",
        "total": f"{total:.2f}",
        "subtotal_decimal": amount,
        "fee_decimal": processing,
        "total_decimal": total,
    }


def dollars_to_cents(amount):
    return int(
        (_as_decimal(amount).quantize(CENTS, rounding=ROUND_HALF_UP) * 100).to_integral_value()
    )


def apply_fee_to_payment(payment):
    totals = calculate_card_processing_fee(payment.amount)
    payment.fee_amount = totals["fee_decimal"]
    payment.total_charged = totals["total_decimal"]
    payment.save(update_fields=["fee_amount", "total_charged"])
    return totals


def payment_charged_totals(payment):
    """Tuition applied to the balance, fee the parent paid, and Stripe charge total."""
    tuition = payment.amount or Decimal("0")
    fee = payment.fee_amount or Decimal("0")
    charged = payment.total_charged or Decimal("0")
    if charged <= 0 and fee > 0:
        charged = (tuition + fee).quantize(CENTS, rounding=ROUND_HALF_UP)
    elif charged <= 0:
        charged = tuition
    if fee <= 0 and charged > tuition:
        fee = (charged - tuition).quantize(CENTS, rounding=ROUND_HALF_UP)
    return tuition, fee, charged


def apply_stripe_session_totals(payment, session):
    """Copy the customer charge total from a paid Stripe Checkout session."""
    amount_total = getattr(session, "amount_total", None)
    if amount_total in (None, ""):
        return payment_charged_totals(payment)
    charged = (Decimal(int(amount_total)) / Decimal("100")).quantize(CENTS, rounding=ROUND_HALF_UP)
    tuition = payment.amount or Decimal("0")
    payment.total_charged = charged
    payment.fee_amount = max(charged - tuition, Decimal("0"))
    payment.save(update_fields=["total_charged", "fee_amount"])
    return payment_charged_totals(payment)


def ensure_payment_fee_totals(payment):
    """Fill fee/total from stored Stripe charge totals. Does not invent a new fee."""
    tuition, fee, charged = payment_charged_totals(payment)
    has_stripe = bool(
        (payment.stripe_session_id or "").strip()
        or (payment.stripe_payment_intent_id or "").strip()
        or (payment.stripe_charge_id or "").strip()
    )
    if not has_stripe:
        return tuition, fee, charged
    changed = False
    if charged > tuition and fee != (charged - tuition):
        payment.fee_amount = charged - tuition
        changed = True
    elif fee > 0 and (not payment.total_charged or payment.total_charged != tuition + fee):
        payment.total_charged = tuition + fee
        changed = True
    if changed:
        payment.save(update_fields=["fee_amount", "total_charged"])
    return payment_charged_totals(payment)


def ledger_paid_totals(entry):
    """Parent-paid total and processing fee for a ledger payment row."""
    applied = abs(entry.amount or Decimal("0"))
    fee = entry.fee_amount or Decimal("0")
    return applied + fee, fee, applied


def sync_ledger_fee_from_payment(payment):
    """Write the stored Stripe fee onto matching Online payment ledger rows."""
    from .models import PortalLedgerEntry

    tuition, fee, _charged = payment_charged_totals(payment)
    if fee <= 0:
        return 0
    entries = PortalLedgerEntry.objects.filter(
        family=payment.family,
        entry_type="payment",
        amount=-tuition,
        description__istartswith="Online payment",
    )
    paid_on = payment.paid_at.date() if payment.paid_at else None
    if paid_on:
        entries = entries.filter(date=paid_on)
    if payment.receipt_no:
        matched = entries.filter(reference_number=payment.receipt_no)
        if matched.exists():
            entries = matched
    updated = 0
    for entry in entries:
        if (entry.fee_amount or Decimal("0")) == fee:
            continue
        entry.fee_amount = fee
        entry.save(update_fields=["fee_amount"])
        updated += 1
    return updated


def backfill_stripe_fee_totals(payments=None):
    """Fill missing fee/total on Stripe payments and matching ledger rows."""
    from .models import PortalPayment

    if payments is None:
        payments = PortalPayment.objects.all()
    count = 0
    for payment in payments:
        has_stripe = bool(
            (payment.stripe_session_id or "").strip()
            or (payment.stripe_payment_intent_id or "").strip()
            or (payment.stripe_charge_id or "").strip()
        )
        if not has_stripe:
            continue
        ensure_payment_fee_totals(payment)
        sync_ledger_fee_from_payment(payment)
        count += 1
    return count


def checkout_line_items(payment, product_name, description):
    totals = apply_fee_to_payment(payment)
    items = [
        {
            "price_data": {
                "currency": "usd",
                "product_data": {
                    "name": product_name,
                    "description": description,
                },
                "unit_amount": dollars_to_cents(totals["subtotal"]),
            },
            "quantity": 1,
        }
    ]
    fee_cents = dollars_to_cents(totals["fee"])
    if fee_cents > 0:
        fee = get_active_processing_fee()
        items.append(
            {
                "price_data": {
                    "currency": "usd",
                    "product_data": {
                        "name": "Card processing fee",
                        "description": f"{fee['percent']}% + ${fee['flat']}",
                    },
                    "unit_amount": fee_cents,
                },
                "quantity": 1,
            }
        )
    return items
