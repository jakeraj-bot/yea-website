from decimal import Decimal

from django.conf import settings

from core.stripe_config import member_stripe, member_stripe_configured

from .demo_data import calculate_card_processing_fee


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
    methods = stripe.PaymentMethod.list(customer=customer_id, type="card")
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
    totals = calculate_card_processing_fee(str(payment.amount))
    total_cents = int(Decimal(str(totals["total"])) * 100)
    session = stripe.checkout.Session.create(
        mode="payment",
        customer=get_or_create_customer(payment.family.parent_account).id,
        line_items=[
            {
                "price_data": {
                    "currency": "usd",
                    "product_data": {
                        "name": f"YEA family balance — {payment.family.name}",
                        "description": f"Program balance payment (${payment.amount})",
                    },
                    "unit_amount": total_cents,
                },
                "quantity": 1,
            }
        ],
        success_url=_checkout_success_url(request),
        cancel_url=request.build_absolute_uri("/portal/parent/payment/"),
        metadata={
            "portal_payment_id": str(payment.pk),
            "family_slug": payment.family.slug,
            "payment_kind": payment.payment_kind,
        },
    )
    payment.stripe_session_id = session.id
    payment.fee_amount = Decimal(str(totals["fee"]))
    payment.total_charged = Decimal(str(totals["total"]))
    payment.save(update_fields=["stripe_session_id", "fee_amount", "total_charged"])
    return session


def create_dropin_checkout_session(request, payment):
    stripe = _stripe()
    totals = calculate_card_processing_fee(str(payment.amount))
    total_cents = int(Decimal(str(totals["total"])) * 100)
    description = f"{payment.dropin_child} · {payment.dropin_program} · {payment.dropin_location}"
    if payment.dropin_date:
        description += f" · {payment.dropin_date}"
    session = stripe.checkout.Session.create(
        mode="payment",
        customer=get_or_create_customer(payment.family.parent_account).id,
        line_items=[
            {
                "price_data": {
                    "currency": "usd",
                    "product_data": {
                        "name": f"Drop-in — {payment.dropin_program}",
                        "description": description,
                    },
                    "unit_amount": total_cents,
                },
                "quantity": 1,
            }
        ],
        success_url=_checkout_success_url(request),
        cancel_url=request.build_absolute_uri("/portal/parent/payment/?source=dropin"),
        metadata={
            "portal_payment_id": str(payment.pk),
            "family_slug": payment.family.slug,
            "payment_kind": "dropin",
        },
    )
    payment.stripe_session_id = session.id
    payment.fee_amount = Decimal(str(totals["fee"]))
    payment.total_charged = Decimal(str(totals["total"]))
    payment.save(update_fields=["stripe_session_id", "fee_amount", "total_charged"])
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
    payment_id = session.metadata.get("portal_payment_id")
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
    if session.payment_intent and getattr(session.payment_intent, "payment_method", None):
        try:
            pm = stripe.PaymentMethod.retrieve(session.payment_intent.payment_method)
            if pm.card:
                method_label = f"{(pm.card.brand or 'Card').title()} ending {pm.card.last4}"
        except Exception:
            pass
    return record_successful_payment(payment, method_label=method_label)


def reconcile_pending_stripe_payments_for_family(family):
    """Apply paid Stripe checkout sessions that never reached the success page."""
    if not stripe_configured():
        return []
    from .models import PortalPayment

    pending = PortalPayment.objects.filter(
        family=family,
        status=PortalPayment.STATUS_PENDING,
    ).exclude(stripe_session_id="")
    reconciled = []
    for payment in pending:
        confirmed = confirm_checkout_payment(payment.stripe_session_id)
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
