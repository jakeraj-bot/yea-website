from django.conf import settings

from . import constants


def create_dropin_checkout_session(request, booking):
    import stripe

    if not settings.STRIPE_SECRET_KEY:
        raise RuntimeError("Stripe is not configured yet. Add STRIPE_SECRET_KEY to your .env file.")

    stripe.api_key = settings.STRIPE_SECRET_KEY
    fee = constants.FEE_DOLLARS[booking.program]
    program_label = dict(constants.PROGRAM_CHOICES)[booking.program]
    location_label = dict(constants.LOCATION_CHOICES)[booking.location]

    session = stripe.checkout.Session.create(
        mode="payment",
        line_items=[
            {
                "price_data": {
                    "currency": "usd",
                    "product_data": {
                        "name": f"Drop-in — {program_label}",
                        "description": (
                            f"{booking.child.first_name} {booking.child.last_name} · "
                            f"{location_label} · {booking.date:%B %d, %Y}"
                        ),
                    },
                    "unit_amount": booking.amount_cents,
                },
                "quantity": 1,
            }
        ],
        success_url=request.build_absolute_uri(
            f"/drop-in/booking/success/?ref={booking.reference}"
        ),
        cancel_url=request.build_absolute_uri("/drop-in/dashboard/?canceled=1"),
        metadata={
            "dropin_booking_ref": str(booking.reference),
            "program": booking.program,
        },
    )
    return session


def confirm_booking_payment(booking):
    import stripe

    if not booking.stripe_session_id or not settings.STRIPE_SECRET_KEY:
        return False

    stripe.api_key = settings.STRIPE_SECRET_KEY
    session = stripe.checkout.Session.retrieve(booking.stripe_session_id)
    if session.payment_status == "paid" and booking.status != booking.STATUS_PAID:
        from django.utils import timezone

        booking.status = booking.STATUS_PAID
        booking.paid_at = timezone.now()
        booking.save(update_fields=["status", "paid_at"])
        return True
    return booking.status == booking.STATUS_PAID
