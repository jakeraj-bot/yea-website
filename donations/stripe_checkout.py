from decimal import Decimal

from django.conf import settings

from . import giving

GIVING_BY_ID = {c["id"]: c for c in giving.GIVING_CARDS}


def _fee_cents(amount_cents):
    return int(round(amount_cents * 0.029 + 30))


def resolve_checkout_amount(giving_id, post_data):
    card = GIVING_BY_ID.get(giving_id)
    if not card:
        raise ValueError("Invalid giving option")

    cover_fees = post_data.get("cover_fees") == "1"
    recurring = post_data.get("recurring") == "monthly"

    if card["type"] == "fixed_with_plans":
        plan_id = post_data.get("plan")
        plan = next((p for p in card["plans"] if p["id"] == plan_id), None)
        if not plan:
            raise ValueError("Invalid payment plan")
        amount_dollars = Decimal(plan["amount"])
        mode = "subscription" if plan_id != "full" else "payment"
        interval = None
        if plan_id == "monthly":
            interval = {"interval": "month", "interval_count": 1}
        elif plan_id == "biweekly":
            interval = {"interval": "week", "interval_count": 2}
        elif plan_id == "weekly":
            interval = {"interval": "week", "interval_count": 1}
    elif card["type"] == "suggested_amounts":
        amount_raw = post_data.get("amount")
        if amount_raw == "custom":
            amount_dollars = Decimal(post_data.get("custom_amount", "0"))
        else:
            amount_dollars = Decimal(amount_raw or "0")
        if amount_dollars < giving.MIN_GIFT:
            raise ValueError(f"Minimum gift is ${giving.MIN_GIFT}")
        mode = "payment"
        interval = None
        recurring = False
    elif card["type"] == "custom_amount":
        amount_dollars = Decimal(post_data.get("amount", "0"))
        if amount_dollars < giving.MIN_GIFT:
            raise ValueError(f"Minimum gift is ${giving.MIN_GIFT}")
        mode = "subscription" if recurring else "payment"
        interval = {"interval": "month", "interval_count": 1} if recurring else None
    else:
        raise ValueError("Unsupported giving type")

    amount_cents = int(amount_dollars * 100)
    if cover_fees:
        amount_cents += _fee_cents(amount_cents)

    return {
        "card": card,
        "amount_cents": amount_cents,
        "mode": mode,
        "interval": interval,
        "cover_fees": cover_fees,
    }


def create_checkout_session(request, post_data):
    import stripe

    if not settings.STRIPE_SECRET_KEY:
        raise RuntimeError("Stripe is not configured yet. Add STRIPE_SECRET_KEY to your .env file.")

    stripe.api_key = settings.STRIPE_SECRET_KEY
    checkout = resolve_checkout_amount(post_data.get("giving_id"), post_data)

    line_item = {
        "price_data": {
            "currency": "usd",
            "product_data": {"name": checkout["card"]["title"]},
            "unit_amount": checkout["amount_cents"],
        },
        "quantity": 1,
    }

    if checkout["mode"] == "subscription" and checkout["interval"]:
        line_item["price_data"]["recurring"] = checkout["interval"]

    session_kwargs = {
        "mode": checkout["mode"],
        "line_items": [line_item],
        "success_url": request.build_absolute_uri("/donate/?success=1"),
        "cancel_url": request.build_absolute_uri("/donate/?canceled=1"),
        "metadata": {
            "giving_id": checkout["card"]["id"],
            "cover_fees": str(checkout["cover_fees"]),
        },
    }

    return stripe.checkout.Session.create(**session_kwargs)
