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
