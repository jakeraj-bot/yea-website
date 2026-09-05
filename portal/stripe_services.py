from decimal import Decimal

from django.conf import settings

from core.stripe_config import member_stripe, member_stripe_configured

from .processing_fees import checkout_line_items


def stripe_configured():
    return member_stripe_configured()


def _checkout_success_url(request):
    """Stripe requires a literal {CHECKOUT_SESSION_ID} — build_absolute_uri encodes braces."""
    return request.build_absolute_uri("/portal/parent/payment/success/") + "?session_id={CHECKOUT_SESSION_ID}"


def _stripe():
    return member_stripe()


def get_or_create_customer(account):
    stripe = _stripe()
    if account.stripe_customer_id:
        return stripe.Customer.retrieve(account.stripe_customer_id)
    customer = stripe.Customer.create(
        email=account.user.email,
        name=account.family.name,
        metadata={"family_slug": account.family.slug, "portal": "parent"},
    )
    account.stripe_customer_id = customer.id
    account.save(update_fields=["stripe_customer_id"])
    return customer


def list_saved_payment_methods(customer_id):
    if not stripe_configured() or not customer_id:
        return []
    stripe = _stripe()
    try:
        methods = stripe.PaymentMethod.list(customer=customer_id, type="card")
    except Exception:
        return []
    cards = []
    for index, pm in enumerate(methods.data):
        brand = (pm.card.brand or "Card").title()
        cards.append(
            {
                "type": "card",
                "label": f"{brand} ending {pm.card.last4}",
                "expires": f"{pm.card.exp_month:02d}/{pm.card.exp_year}",
                "default": index == 0,
                "stripe_id": pm.id,
            }
        )
    return cards


def create_balance_checkout_session(request, payment):
    stripe = _stripe()
    line_items = checkout_line_items(
        payment,
        f"YEA family balance — {payment.family.name}",
        f"Program balance payment (${payment.amount})",
    )
    session = stripe.checkout.Session.create(
        mode="payment",
        customer=get_or_create_customer(payment.family.parent_account).id,
        line_items=line_items,
        success_url=_checkout_success_url(request),
        cancel_url=request.build_absolute_uri("/portal/parent/payment/"),
        metadata={
            "portal_payment_id": str(payment.pk),
            "family_slug": payment.family.slug,
            "payment_kind": payment.payment_kind,
        },
    )
    payment.stripe_session_id = session.id
    payment.save(update_fields=["stripe_session_id"])
    return session


def create_dropin_checkout_session(request, payment):
    stripe = _stripe()
    description = f"{payment.dropin_child} · {payment.dropin_program} · {payment.dropin_location}"
    if payment.dropin_date:
        description += f" · {payment.dropin_date}"
    line_items = checkout_line_items(
        payment,
        f"Drop-in — {payment.dropin_program}",
        description,
    )
    session = stripe.checkout.Session.create(
        mode="payment",
        customer=get_or_create_customer(payment.family.parent_account).id,
        line_items=line_items,
        success_url=_checkout_success_url(request),
        cancel_url=request.build_absolute_uri("/portal/parent/payment/?source=dropin"),
        metadata={
            "portal_payment_id": str(payment.pk),
            "family_slug": payment.family.slug,
            "payment_kind": "dropin",
        },
    )
    payment.stripe_session_id = session.id
    payment.save(update_fields=["stripe_session_id"])
    return session


def create_field_trip_checkout_session(request, payment, signup):
    stripe = _stripe()
    trip = signup.trip
    line_items = checkout_line_items(
        payment,
        f"Field trip — {trip.title}",
        f"{signup.child.name} · {trip.location} · {trip.trip_date.isoformat()}",
    )
    session = stripe.checkout.Session.create(
        mode="payment",
        customer=get_or_create_customer(payment.family.parent_account).id,
        line_items=line_items,
        success_url=_checkout_success_url(request),
        cancel_url=request.build_absolute_uri("/portal/parent/field-trips/"),
        metadata={
            "portal_payment_id": str(payment.pk),
            "family_slug": payment.family.slug,
            "payment_kind": "field_trip",
            "field_trip_signup_id": str(signup.pk),
        },
    )
    payment.stripe_session_id = session.id
    payment.save(update_fields=["stripe_session_id"])
    return session


def create_drop_off_checkout_session(request, payment, booking):
    stripe = _stripe()
    when = booking.care_date.isoformat()
    line_items = checkout_line_items(
        payment,
        f"Drop-off — {booking.slot_label}",
        f"{booking.child.name} · {when} · {booking.start_time.strftime('%-I:%M %p').lstrip('0')}",
    )
    session = stripe.checkout.Session.create(
        mode="payment",
        customer=get_or_create_customer(payment.family.parent_account).id,
        line_items=line_items,
        success_url=_checkout_success_url(request),
        cancel_url=request.build_absolute_uri("/portal/parent/drop-off/"),
        metadata={
            "portal_payment_id": str(payment.pk),
            "family_slug": payment.family.slug,
            "payment_kind": "drop_off",
            "drop_off_booking_id": str(booking.pk),
        },
    )
    payment.stripe_session_id = session.id
    payment.save(update_fields=["stripe_session_id"])
    return session


def create_setup_checkout_session(request, account):
    stripe = _stripe()
    customer = get_or_create_customer(account)
    session = stripe.checkout.Session.create(
        mode="setup",
        customer=customer.id,
        payment_method_types=["card"],
        success_url=request.build_absolute_uri("/portal/parent/account/?card_saved=1"),
        cancel_url=request.build_absolute_uri("/portal/parent/account/"),
        metadata={"family_slug": account.family.slug, "portal": "parent_setup"},
    )
    return session


def confirm_checkout_payment(session_id):
    if not stripe_configured() or not session_id:
        return None
    if session_id in {"{CHECKOUT_SESSION_ID}", "%7BCHECKOUT_SESSION_ID%7D"}:
        return None
    from .models import PortalPayment
    from .parent_services import record_successful_payment

    stripe = _stripe()
    try:
        session = stripe.checkout.Session.retrieve(session_id, expand=["payment_intent"])
    except Exception:
        return None
    if session.payment_status != "paid":
        return None
    metadata = getattr(session, "metadata", None) or {}
    payment_id = metadata.get("portal_payment_id") if hasattr(metadata, "get") else None
    payment = None
    if payment_id:
        payment = PortalPayment.objects.filter(pk=payment_id).select_related("family").first()
    if not payment:
        payment = PortalPayment.objects.filter(stripe_session_id=session_id).select_related("family").first()
    if not payment:
        return None
    if payment.status == PortalPayment.STATUS_PAID:
        return payment
    method_label = "Card"
    payment_intent = getattr(session, "payment_intent", None)
    intent_id = payment_intent if isinstance(payment_intent, str) else getattr(payment_intent, "id", "")
    if intent_id and not payment.stripe_payment_intent_id:
        payment.stripe_payment_intent_id = intent_id
        payment.save(update_fields=["stripe_payment_intent_id"])
    payment_method_id = getattr(payment_intent, "payment_method", None) if payment_intent and not isinstance(payment_intent, str) else None
    if payment_method_id:
        try:
            pm = stripe.PaymentMethod.retrieve(payment_method_id)
            if pm.card:
                method_label = f"{(pm.card.brand or 'Card').title()} ending {pm.card.last4}"
        except Exception:
            pass
    try:
        return record_successful_payment(payment, method_label=method_label)
    except Exception:
        return None


def reconcile_pending_stripe_payments_for_family(family):
    """Apply paid Stripe checkout sessions that never reached the success page."""
    if not stripe_configured() or not family:
        return []
    from .models import PortalPayment

    try:
        pending = list(
            PortalPayment.objects.filter(
                family=family,
                status=PortalPayment.STATUS_PENDING,
            ).exclude(stripe_session_id="")
        )
    except Exception:
        return []
    reconciled = []
    for payment in pending:
        try:
            confirmed = confirm_checkout_payment(payment.stripe_session_id)
        except Exception:
            continue
        if confirmed and confirmed.status == PortalPayment.STATUS_PAID:
            reconciled.append(confirmed)
    return reconciled


def handle_member_stripe_webhook(payload, signature):
    """Process Stripe webhook events for member portal payments."""
    if not stripe_configured():
        return False
    stripe = _stripe()
    secret = settings.MEMBER_STRIPE_WEBHOOK_SECRET
    if secret:
        try:
            event = stripe.Webhook.construct_event(payload, signature, secret)
        except Exception:
            return False
    else:
        import json

        try:
            event = json.loads(payload)
        except (TypeError, ValueError):
            return False
    if event.get("type") != "checkout.session.completed":
        return True
    session = event.get("data", {}).get("object") or {}
    if session.get("payment_status") != "paid":
        return True
    session_id = session.get("id")
    if session_id:
        confirm_checkout_payment(session_id)
    return True


def refund_stripe_payment(payment, amount):
    """Refund a parent card payment in Stripe. Returns the refunded Decimal amount."""
    if not stripe_configured():
        raise ValueError("Member Stripe is not configured.")
    if payment.status != payment.STATUS_PAID:
        raise ValueError("Only paid card payments can be refunded.")
    remaining = (payment.amount or Decimal("0")) - (payment.refunded_amount or Decimal("0"))
    if remaining <= 0:
        raise ValueError("This payment has already been fully refunded.")
    if amount > remaining:
        raise ValueError(f"Refund cannot exceed the remaining ${remaining:.2f}.")

    stripe = _stripe()
    intent_id = payment.stripe_payment_intent_id
    if not intent_id and payment.stripe_session_id:
        try:
            session = stripe.checkout.Session.retrieve(payment.stripe_session_id)
        except Exception as exc:
            raise ValueError(f"Could not look up this Stripe payment: {exc}") from exc
        payment_intent = getattr(session, "payment_intent", None)
        intent_id = payment_intent if isinstance(payment_intent, str) else getattr(payment_intent, "id", "")
        if intent_id:
            payment.stripe_payment_intent_id = intent_id
            payment.save(update_fields=["stripe_payment_intent_id"])
    if not intent_id:
        raise ValueError("This payment has no Stripe card charge to refund.")

    charged = payment.total_charged or payment.amount
    already_refunded = payment.refunded_amount or Decimal("0")
    stripe_remaining = charged - already_refunded
    if amount >= remaining:
        stripe_amount = stripe_remaining
    else:
        stripe_amount = amount
    cents = int((stripe_amount * 100).quantize(Decimal("1")))
    if cents <= 0:
        raise ValueError("Refund amount is too small.")
    try:
        stripe.Refund.create(payment_intent=intent_id, amount=cents)
    except Exception as exc:
        raise ValueError(f"Stripe could not refund this payment: {exc}") from exc
    return amount


BANK_STATUS_LABELS = {
    "waiting_for_card": "Waiting for parent to finish card payment",
    "received_by_stripe": "Stripe received — waiting to become available",
    "waiting_for_bank": "Available in Stripe — waiting for bank payout",
    "in_transit": "On the way to the bank",
    "in_bank": "Paid out to bank",
    "not_stripe": "Not Stripe — recorded in portal",
    "unknown": "Stripe payment — bank status unavailable",
}


def bank_status_label(code):
    return BANK_STATUS_LABELS.get(code, code or "—")


def _unix_date(value):
    if not value:
        return None
    from datetime import datetime, timezone

    try:
        return datetime.fromtimestamp(int(value), tz=timezone.utc).date()
    except (TypeError, ValueError, OSError):
        return None


def _payout_charge_map(stripe, limit=15):
    """Map Stripe charge IDs to the payout that included them."""
    mapping = {}
    try:
        payouts = stripe.Payout.list(limit=limit)
    except Exception:
        return mapping
    for payout in payouts.data:
        try:
            transactions = stripe.BalanceTransaction.list(payout=payout.id, limit=100)
        except Exception:
            continue
        for txn in transactions.data:
            source = getattr(txn, "source", None)
            source_id = source if isinstance(source, str) else getattr(source, "id", "")
            if source_id:
                mapping[source_id] = payout
    return mapping


def refresh_payment_settlement(payment, payout_map=None):
    """Cache whether Stripe still holds this payment or has paid it out to the bank."""
    from django.utils import timezone

    from .models import PortalPayment

    has_stripe = bool(payment.stripe_session_id or payment.stripe_payment_intent_id)
    if not has_stripe:
        payment.stripe_bank_status = "not_stripe"
        payment.stripe_settlement_checked_at = timezone.now()
        payment.save(update_fields=["stripe_bank_status", "stripe_settlement_checked_at"])
        return payment
    if payment.status != PortalPayment.STATUS_PAID:
        payment.stripe_bank_status = "waiting_for_card"
        payment.stripe_settlement_checked_at = timezone.now()
        payment.save(update_fields=["stripe_bank_status", "stripe_settlement_checked_at"])
        return payment
    if not stripe_configured():
        payment.stripe_bank_status = "unknown"
        payment.stripe_settlement_checked_at = timezone.now()
        payment.save(update_fields=["stripe_bank_status", "stripe_settlement_checked_at"])
        return payment

    stripe = _stripe()
    charge_id = payment.stripe_charge_id
    available_on = payment.stripe_bank_date
    try:
        intent_id = payment.stripe_payment_intent_id
        if not intent_id and payment.stripe_session_id:
            session = stripe.checkout.Session.retrieve(payment.stripe_session_id, expand=["payment_intent.latest_charge.balance_transaction"])
            payment_intent = getattr(session, "payment_intent", None)
            if isinstance(payment_intent, str):
                intent_id = payment_intent
            else:
                intent_id = getattr(payment_intent, "id", "") or ""
                charge = getattr(payment_intent, "latest_charge", None) if payment_intent else None
                charge_id = charge if isinstance(charge, str) else getattr(charge, "id", "") or charge_id
                bt = getattr(charge, "balance_transaction", None) if charge and not isinstance(charge, str) else None
                available_on = _unix_date(getattr(bt, "available_on", None)) or available_on
        if intent_id and not charge_id:
            intent = stripe.PaymentIntent.retrieve(intent_id, expand=["latest_charge.balance_transaction"])
            intent_id = intent.id
            charge = getattr(intent, "latest_charge", None)
            charge_id = charge if isinstance(charge, str) else getattr(charge, "id", "") or charge_id
            bt = getattr(charge, "balance_transaction", None) if charge and not isinstance(charge, str) else None
            available_on = _unix_date(getattr(bt, "available_on", None)) or available_on
        if intent_id and not payment.stripe_payment_intent_id:
            payment.stripe_payment_intent_id = intent_id
    except Exception:
        payment.stripe_bank_status = "unknown"
        payment.stripe_settlement_checked_at = timezone.now()
        payment.save(update_fields=["stripe_bank_status", "stripe_settlement_checked_at"])
        return payment

    payout = None
    if charge_id and payout_map is not None:
        payout = payout_map.get(charge_id)
    status = "waiting_for_bank"
    today = timezone.localdate()
    if payout is not None:
        payout_status = getattr(payout, "status", "") or ""
        available_on = _unix_date(getattr(payout, "arrival_date", None)) or available_on
        if payout_status == "paid":
            status = "in_bank"
        elif payout_status in {"in_transit", "pending"}:
            status = "in_transit"
    elif available_on and available_on > today:
        status = "received_by_stripe"
    payment.stripe_charge_id = charge_id or payment.stripe_charge_id
    payment.stripe_bank_status = status
    payment.stripe_bank_date = available_on
    payment.stripe_settlement_checked_at = timezone.now()
    payment.save(
        update_fields=[
            "stripe_payment_intent_id",
            "stripe_charge_id",
            "stripe_bank_status",
            "stripe_bank_date",
            "stripe_settlement_checked_at",
        ]
    )
    return payment


def refresh_stripe_settlements(payments):
    payout_map = {}
    if stripe_configured() and any(p.stripe_session_id or p.stripe_payment_intent_id for p in payments):
        try:
            payout_map = _payout_charge_map(_stripe())
        except Exception:
            payout_map = {}
    for payment in payments:
        try:
            refresh_payment_settlement(payment, payout_map=payout_map)
        except Exception:
            continue
    return payments


def stripe_payout_rows(limit=20):
    if not stripe_configured():
        return []
    stripe = _stripe()
    try:
        payouts = stripe.Payout.list(limit=limit)
    except Exception:
        return []
    rows = []
    for payout in payouts.data:
        amount = Decimal(getattr(payout, "amount", 0) or 0) / Decimal("100")
        status = getattr(payout, "status", "") or "unknown"
        if status == "paid":
            bank = "Paid out to bank"
        elif status == "in_transit":
            bank = "On the way to the bank"
        elif status == "pending":
            bank = "Stripe payout pending"
        else:
            bank = status.replace("_", " ").title()
        rows.append(
            {
                "date": (_unix_date(getattr(payout, "arrival_date", None)) or _unix_date(getattr(payout, "created", None)) or "").isoformat()
                if (_unix_date(getattr(payout, "arrival_date", None)) or _unix_date(getattr(payout, "created", None)))
                else "—",
                "family": "Stripe payout",
                "family_slug": "",
                "family_id": "",
                "child": "—",
                "paid_by": "Stripe → bank",
                "amount": f"{amount:.2f}",
                "method": "Bank payout",
                "status": bank,
                "bank_status": bank,
                "bank_date": (_unix_date(getattr(payout, "arrival_date", None)) or "").isoformat()
                if _unix_date(getattr(payout, "arrival_date", None))
                else "—",
            }
        )
    return rows
