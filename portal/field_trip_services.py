from decimal import Decimal, InvalidOperation

from django.utils import timezone
from django.utils.text import slugify

from .models import PortalChild, PortalFieldTrip, PortalFieldTripSignup, PortalPayment, PortalUnit

DEFAULT_PERMISSION_SLIP = (
    "I give permission for my child to attend this Youth Enrichment Academy field trip. "
    "I understand the date, destination, and fee. I authorize YEA staff to seek emergency "
    "medical care if needed. I have read this permission slip and agree to its terms."
)


def _parse_amount(value):
    try:
        amount = Decimal(str(value).replace(",", "").strip() or "0")
    except (InvalidOperation, TypeError):
        raise ValueError("Enter a valid trip fee.")
    if amount < 0:
        raise ValueError("Trip fee cannot be negative.")
    return amount.quantize(Decimal("0.01"))


def create_field_trip(data):
    title = (data.get("title") or "").strip()
    if not title:
        raise ValueError("Enter a field trip name.")
    trip_date = data.get("trip_date")
    if not trip_date:
        raise ValueError("Pick the trip date.")
    slip = (data.get("permission_slip") or "").strip() or DEFAULT_PERMISSION_SLIP
    unit_slug = (data.get("unit") or "").strip()
    unit = PortalUnit.objects.filter(slug=unit_slug).first() if unit_slug else None
    base_slug = slugify(f"{title}-{trip_date}") or "field-trip"
    slug = base_slug
    suffix = 2
    while PortalFieldTrip.objects.filter(slug=slug).exists():
        slug = f"{base_slug}-{suffix}"
        suffix += 1
    trip = PortalFieldTrip.objects.create(
        unit=unit,
        title=title,
        slug=slug,
        trip_date=trip_date,
        location=(data.get("location") or "").strip(),
        description=(data.get("description") or "").strip(),
        fee_amount=_parse_amount(data.get("fee_amount", "0")),
        permission_slip=slip,
        is_active=True,
    )
    assign_trip_to_children(trip)
    return trip


def assign_trip_to_children(trip):
    children = PortalChild.objects.filter(is_active=True, family__status="Active").select_related("family")
    if trip.unit_id:
        children = children.filter(family__unit=trip.unit)
    created = 0
    for child in children:
        _, was_created = PortalFieldTripSignup.objects.get_or_create(
            trip=trip,
            child=child,
            defaults={"family": child.family},
        )
        if was_created:
            created += 1
    return created


def get_admin_field_trips():
    trips = []
    for trip in PortalFieldTrip.objects.select_related("unit").prefetch_related("signups"):
        signups = list(trip.signups.all())
        trips.append(
            {
                "pk": trip.pk,
                "title": trip.title,
                "trip_date": trip.trip_date.isoformat(),
                "location": trip.location,
                "unit": trip.unit.name if trip.unit_id else "All units",
                "fee": f"{trip.fee_amount:.2f}",
                "is_active": trip.is_active,
                "total": len(signups),
                "signed": sum(1 for s in signups if s.status in (s.STATUS_SIGNED, s.STATUS_PAID)),
                "paid": sum(1 for s in signups if s.status == s.STATUS_PAID),
                "signups": [
                    {
                        "child": signup.child.name,
                        "family": signup.family.name,
                        "status": signup.get_status_display(),
                        "signed_at": timezone.localtime(signup.signed_at).strftime("%b %d, %Y") if signup.signed_at else "",
                    }
                    for signup in signups
                ],
            }
        )
    return trips


def get_family_field_trips(family):
    signups = (
        PortalFieldTripSignup.objects.filter(family=family, trip__is_active=True)
        .select_related("trip", "child")
        .order_by("trip__trip_date", "child__name")
    )
    rows = []
    for signup in signups:
        trip = signup.trip
        rows.append(
            {
                "id": signup.pk,
                "title": trip.title,
                "trip_date": trip.trip_date.isoformat(),
                "location": trip.location,
                "description": trip.description,
                "fee": f"{trip.fee_amount:.2f}",
                "needs_payment": trip.fee_amount > 0 and signup.status != signup.STATUS_PAID,
                "permission_slip": trip.permission_slip,
                "child": signup.child.name,
                "status": signup.status,
                "status_label": signup.get_status_display(),
                "signature_name": signup.signature_name,
            }
        )
    return rows


def pending_field_trip_count(family):
    return PortalFieldTripSignup.objects.filter(
        family=family,
        trip__is_active=True,
    ).exclude(status=PortalFieldTripSignup.STATUS_PAID).count()


def sign_field_trip(family, signup_id, signature_name):
    signup = PortalFieldTripSignup.objects.select_related("trip", "child", "family").filter(
        pk=signup_id,
        family=family,
    ).first()
    if not signup:
        raise ValueError("Field trip not found for this family.")
    name = (signature_name or "").strip()
    if len(name) < 2:
        raise ValueError("Type your full name to sign the permission slip.")
    if signup.status == PortalFieldTripSignup.STATUS_PENDING:
        signup.signature_name = name
        signup.signed_at = timezone.now()
        signup.status = PortalFieldTripSignup.STATUS_SIGNED
        signup.save(update_fields=["signature_name", "signed_at", "status"])
    if signup.trip.fee_amount <= 0:
        signup.status = PortalFieldTripSignup.STATUS_PAID
        signup.save(update_fields=["status"])
    return signup


def start_field_trip_payment(request, family, signup):
    from .stripe_services import create_field_trip_checkout_session, stripe_configured

    if signup.trip.fee_amount <= 0:
        return None
    if not stripe_configured():
        raise ValueError("Stripe is not configured yet, so this trip cannot be paid online.")
    payment = signup.payment
    if not payment or payment.status != PortalPayment.STATUS_PENDING:
        payment = PortalPayment.objects.create(
            family=family,
            amount=signup.trip.fee_amount,
            payment_kind="field_trip",
            dropin_child=signup.child.name,
            dropin_program=signup.trip.title,
            dropin_location=signup.trip.location,
            dropin_date=signup.trip.trip_date.isoformat(),
        )
        signup.payment = payment
        signup.save(update_fields=["payment"])
    return create_field_trip_checkout_session(request, payment, signup)


def mark_field_trip_paid(payment):
    signup = payment.field_trip_signups.select_related("trip").first()
    if not signup:
        return
    signup.status = PortalFieldTripSignup.STATUS_PAID
    signup.save(update_fields=["status"])
