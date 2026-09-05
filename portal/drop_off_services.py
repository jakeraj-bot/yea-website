"""Drop-off program: member flag, slot settings, paid bookings, and pickup lists."""

from datetime import datetime, time, timedelta
from decimal import Decimal, InvalidOperation

from django.db.models import Q
from django.utils import timezone

from .models import (
    PortalChild,
    PortalDropOffBooking,
    PortalDropOffSettings,
    PortalDropOffSlot,
    PortalFamily,
    PortalPayment,
    PortalUnit,
)

PROGRAM_DROP_OFF = "Drop-off program"
PROGRAM_AFTER_SCHOOL = "After-school program"
PROGRAM_MIXED = "After-school & drop-off"

WEEKDAYS = PortalDropOffSlot.WEEKDAY_CHOICES


def get_settings():
    settings_row = PortalDropOffSettings.objects.order_by("pk").first()
    if settings_row:
        return settings_row
    return PortalDropOffSettings.objects.create()


def family_has_drop_off(family):
    if not family:
        return False
    return family.children.filter(is_active=True, is_drop_off=True).exists()


def drop_off_children(family):
    if not family:
        return PortalChild.objects.none()
    return family.children.filter(is_active=True, is_drop_off=True).order_by("name")


def sync_family_program_label(family):
    children = list(family.children.filter(is_active=True))
    if not children:
        return family
    drop_off_count = sum(1 for child in children if child.is_drop_off)
    if drop_off_count == 0:
        label = family.program_label or PROGRAM_AFTER_SCHOOL
        if label == PROGRAM_DROP_OFF or label == PROGRAM_MIXED:
            label = PROGRAM_AFTER_SCHOOL
    elif drop_off_count == len(children):
        label = PROGRAM_DROP_OFF
    else:
        label = PROGRAM_MIXED
    if family.program_label != label:
        family.program_label = label
        family.save(update_fields=["program_label"])
    return family


def set_child_drop_off(child, is_drop_off):
    child.is_drop_off = bool(is_drop_off)
    child.save(update_fields=["is_drop_off"])
    sync_family_program_label(child.family)
    return child


def apply_drop_off_from_application(child, program):
    if not child:
        return None
    if program == "drop_off":
        return set_child_drop_off(child, True)
    return child


def _parse_amount(value):
    try:
        amount = Decimal(str(value).replace(",", "").replace("$", "").strip() or "0")
    except (InvalidOperation, TypeError):
        raise ValueError("Enter a valid price.")
    if amount < 0:
        raise ValueError("Price cannot be negative.")
    return amount.quantize(Decimal("0.01"))


def _parse_time(value):
    if isinstance(value, time):
        return value
    text = str(value or "").strip()
    for fmt in ("%H:%M", "%H:%M:%S", "%I:%M %p", "%I:%M%p"):
        try:
            return datetime.strptime(text, fmt).time()
        except ValueError:
            continue
    raise ValueError("Enter a valid time, such as 13:00 or 1:00 PM.")


def save_settings(data):
    settings_row = get_settings()
    settings_row.request_cutoff_time = _parse_time(data.get("request_cutoff_time"))
    try:
        ahead = int(data.get("book_ahead_days") or 14)
    except (TypeError, ValueError):
        raise ValueError("Enter how many days ahead parents can book.")
    if ahead < 0 or ahead > 90:
        raise ValueError("Days ahead must be between 0 and 90.")
    settings_row.book_ahead_days = ahead
    settings_row.booking_open = data.get("booking_open") in {True, "on", "1", "true", "True"}
    settings_row.parent_note = (data.get("parent_note") or "").strip()
    settings_row.save()
    return settings_row


def save_slot(data, slot_id=None):
    unit_id = data.get("unit_id") or data.get("unit")
    unit = PortalUnit.objects.filter(pk=unit_id).first() if str(unit_id).isdigit() else None
    if not unit and data.get("unit_slug"):
        unit = PortalUnit.objects.filter(slug=data.get("unit_slug")).first()
    if not unit:
        raise ValueError("Choose a unit for this time slot.")
    try:
        weekday = int(data.get("weekday"))
    except (TypeError, ValueError):
        raise ValueError("Choose a weekday.")
    if weekday not in {choice[0] for choice in WEEKDAYS}:
        raise ValueError("Choose a weekday from Monday to Friday.")
    start = _parse_time(data.get("start_time"))
    label = (data.get("label") or "").strip() or start.strftime("%-I:%M %p").replace(" 0", " ")
    try:
        capacity = int(data.get("capacity") or 0)
    except (TypeError, ValueError):
        raise ValueError("Enter how many spots this slot has.")
    if capacity < 1:
        raise ValueError("Each slot needs at least 1 spot.")
    price = _parse_amount(data.get("price"))
    school_note = (data.get("school_note") or "").strip()
    if slot_id:
        is_active = data.get("is_active") in {True, "on", "1", "true", "True"}
    else:
        is_active = data.get("is_active") not in {False, "0", "false", "False"}
    if slot_id:
        slot = PortalDropOffSlot.objects.filter(pk=slot_id).first()
        if not slot:
            raise ValueError("Time slot not found.")
        slot.unit = unit
        slot.weekday = weekday
        slot.start_time = start
        slot.label = label
        slot.capacity = capacity
        slot.price = price
        slot.school_note = school_note
        slot.is_active = is_active
        slot.save()
        return slot
    return PortalDropOffSlot.objects.create(
        unit=unit,
        weekday=weekday,
        start_time=start,
        label=label,
        capacity=capacity,
        price=price,
        school_note=school_note,
        is_active=is_active,
    )


def delete_slot(slot_id):
    slot = PortalDropOffSlot.objects.filter(pk=slot_id).first()
    if not slot:
        raise ValueError("Time slot not found.")
    slot.is_active = False
    slot.save(update_fields=["is_active"])
    return slot


def _held_statuses():
    return [PortalDropOffBooking.STATUS_REQUESTED, PortalDropOffBooking.STATUS_PAID]


def spots_remaining(slot, care_date):
    taken = PortalDropOffBooking.objects.filter(
        slot=slot,
        care_date=care_date,
        status__in=_held_statuses(),
    ).count()
    return max(slot.capacity - taken, 0)


def request_deadline_for(care_date, settings_row=None):
    settings_row = settings_row or get_settings()
    naive = datetime.combine(care_date, settings_row.request_cutoff_time)
    if timezone.is_naive(naive):
        return timezone.make_aware(naive, timezone.get_current_timezone())
    return naive


def booking_window_error(care_date, now=None, settings_row=None):
    settings_row = settings_row or get_settings()
    now = now or timezone.localtime()
    today = timezone.localdate()
    if not settings_row.booking_open:
        return "Drop-off booking is closed right now."
    if care_date < today:
        return "Pick a date that has not already passed."
    if care_date > today + timedelta(days=settings_row.book_ahead_days):
        return f"Drop-off can be requested up to {settings_row.book_ahead_days} days ahead."
    if now > request_deadline_for(care_date, settings_row):
        cutoff = settings_row.request_cutoff_time.strftime("%-I:%M %p").lstrip("0")
        if care_date == today:
            return f"The cutoff for today was {cutoff}. Try another day."
        return f"The cutoff to request this date was {cutoff}."
    return ""


def slots_for_date(unit, care_date, settings_row=None):
    settings_row = settings_row or get_settings()
    weekday = care_date.weekday()
    window_error = booking_window_error(care_date, settings_row=settings_row)
    rows = []
    for slot in PortalDropOffSlot.objects.filter(unit=unit, weekday=weekday, is_active=True):
        remaining = spots_remaining(slot, care_date)
        rows.append(
            {
                "id": slot.pk,
                "label": slot.label,
                "start_time": slot.start_time.strftime("%H:%M"),
                "start_display": slot.start_time.strftime("%-I:%M %p").lstrip("0"),
                "price": f"{slot.price:.2f}",
                "capacity": slot.capacity,
                "spots_left": remaining,
                "school_note": slot.school_note,
                "available": remaining > 0 and not window_error,
            }
        )
    return rows, window_error


def parent_drop_off_page(family, selected_date=None):
    settings_row = get_settings()
    today = timezone.localdate()
    max_date = today + timedelta(days=settings_row.book_ahead_days)
    children = list(drop_off_children(family))
    care_date = selected_date or today
    slots, window_error = slots_for_date(family.unit, care_date, settings_row) if family.unit_id else ([], "")
    bookings = [
        _booking_row(booking)
        for booking in PortalDropOffBooking.objects.filter(family=family)
        .exclude(status=PortalDropOffBooking.STATUS_CANCELLED)
        .select_related("child", "unit")
        .order_by("care_date", "start_time")
    ]
    return {
        "enabled": bool(children),
        "children": [{"id": child.pk, "name": child.name, "school": child.school} for child in children],
        "settings": _settings_public(settings_row),
        "care_date": care_date.isoformat(),
        "min_date": today.isoformat(),
        "max_date": max_date.isoformat(),
        "slots": slots,
        "window_error": window_error,
        "bookings": bookings,
        "has_paid": any(row["status"] == PortalDropOffBooking.STATUS_PAID for row in bookings),
    }


def _settings_public(settings_row):
    cutoff = settings_row.request_cutoff_time.strftime("%-I:%M %p").lstrip("0")
    return {
        "cutoff_display": cutoff,
        "book_ahead_days": settings_row.book_ahead_days,
        "booking_open": settings_row.booking_open,
        "parent_note": settings_row.parent_note,
    }


def _booking_row(booking):
    return {
        "id": booking.pk,
        "child": booking.child.name,
        "school": booking.child.school,
        "date": booking.care_date.isoformat(),
        "date_display": booking.care_date.strftime("%A, %b %-d"),
        "time": booking.start_time.strftime("%-I:%M %p").lstrip("0"),
        "slot_label": booking.slot_label,
        "amount": f"{booking.amount:.2f}",
        "status": booking.status,
        "status_label": booking.get_status_display(),
        "unit": booking.unit.name if booking.unit_id else "",
        "parent": booking.family.primary_contact,
        "family": booking.family.name,
        "family_slug": booking.family.slug,
        "family_id": booking.family_id,
        "paid": booking.status == PortalDropOffBooking.STATUS_PAID,
    }


def create_drop_off_request(family, child_id, slot_id, care_date):
    settings_row = get_settings()
    try:
        child_id = int(child_id)
        slot_id = int(slot_id)
    except (TypeError, ValueError):
        raise ValueError("Choose a child and a time.")
    child = drop_off_children(family).filter(pk=child_id).first()
    if not child:
        raise ValueError("Choose a drop-off child on this account.")
    slot = PortalDropOffSlot.objects.filter(pk=slot_id, is_active=True).first()
    if not slot:
        raise ValueError("That time is no longer available.")
    if slot.unit_id != family.unit_id:
        raise ValueError("That time is for a different unit.")
    if slot.weekday != care_date.weekday():
        raise ValueError("That time is not offered on the day you picked.")
    error = booking_window_error(care_date, settings_row=settings_row)
    if error:
        raise ValueError(error)
    existing = PortalDropOffBooking.objects.filter(
        child=child,
        care_date=care_date,
        status__in=_held_statuses(),
    ).first()
    if existing:
        raise ValueError(f"{child.name} already has drop-off on that day.")
    if spots_remaining(slot, care_date) < 1:
        raise ValueError("That time is full. Pick another time or day.")
    booking = PortalDropOffBooking.objects.create(
        child=child,
        family=family,
        unit=family.unit,
        slot=slot,
        care_date=care_date,
        start_time=slot.start_time,
        slot_label=slot.label,
        amount=slot.price,
        status=PortalDropOffBooking.STATUS_REQUESTED,
    )
    notify_drop_off_request(booking)
    return booking


def start_drop_off_payment(request, booking):
    from .stripe_services import create_drop_off_checkout_session, stripe_configured

    if booking.amount <= 0:
        mark_booking_paid(booking, method_label="No fee")
        return None
    if not stripe_configured():
        return None
    payment = booking.payment
    if not payment or payment.status != PortalPayment.STATUS_PENDING:
        payment = PortalPayment.objects.create(
            family=booking.family,
            amount=booking.amount,
            payment_kind="drop_off",
            dropin_child=booking.child.name,
            dropin_program=booking.slot_label,
            dropin_location=booking.unit.name if booking.unit_id else "",
            dropin_date=booking.care_date.isoformat(),
        )
        booking.payment = payment
        booking.save(update_fields=["payment"])
    return create_drop_off_checkout_session(request, payment, booking)


def mark_booking_paid(booking, payment=None, method_label="Card"):
    booking.status = PortalDropOffBooking.STATUS_PAID
    booking.paid_at = timezone.now()
    updates = ["status", "paid_at"]
    if payment:
        booking.payment = payment
        updates.append("payment")
    booking.save(update_fields=updates)
    notify_drop_off_confirmed(booking)
    return booking


def mark_drop_off_paid(payment):
    booking = payment.drop_off_bookings.first()
    if not booking:
        return None
    return mark_booking_paid(booking, payment=payment, method_label=payment.method_label or "Card")


def cancel_booking(booking):
    if booking.status == PortalDropOffBooking.STATUS_CANCELLED:
        return booking
    booking.status = PortalDropOffBooking.STATUS_CANCELLED
    booking.cancelled_at = timezone.now()
    booking.save(update_fields=["status", "cancelled_at"])
    return booking


def pickup_rows(unit=None, care_date=None, include_unpaid=True):
    care_date = care_date or timezone.localdate()
    qs = (
        PortalDropOffBooking.objects.filter(care_date=care_date)
        .exclude(status=PortalDropOffBooking.STATUS_CANCELLED)
        .select_related("child", "family", "unit")
        .order_by("start_time", "child__name")
    )
    if unit:
        qs = qs.filter(Q(unit=unit) | Q(family__unit=unit))
    if not include_unpaid:
        qs = qs.filter(status=PortalDropOffBooking.STATUS_PAID)
    return [_booking_row(booking) for booking in qs]


def drop_off_member_rows(unit=None):
    children = PortalChild.objects.filter(is_active=True, is_drop_off=True).select_related(
        "family", "family__unit"
    )
    if unit:
        children = children.filter(family__unit=unit)
    rows = []
    for child in children.order_by("family__unit__name", "name"):
        rows.append(
            {
                "child": child.name,
                "school": child.school,
                "family": child.family.name,
                "family_slug": child.family.slug,
                "family_id": child.family_id,
                "unit": child.family.unit.name if child.family.unit_id else "",
                "parent": child.family.primary_contact,
                "program": PROGRAM_DROP_OFF,
            }
        )
    return rows


def admin_settings_page():
    settings_row = get_settings()
    slots = []
    for slot in PortalDropOffSlot.objects.select_related("unit"):
        slots.append(
            {
                "id": slot.pk,
                "unit_id": slot.unit_id,
                "unit": slot.unit.name,
                "weekday": slot.weekday,
                "weekday_label": slot.get_weekday_display(),
                "start_time": slot.start_time.strftime("%H:%M"),
                "start_display": slot.start_time.strftime("%-I:%M %p").lstrip("0"),
                "label": slot.label,
                "capacity": slot.capacity,
                "price": f"{slot.price:.2f}",
                "school_note": slot.school_note,
                "is_active": slot.is_active,
            }
        )
    return {
        "settings": {
            "request_cutoff_time": settings_row.request_cutoff_time.strftime("%H:%M"),
            "cutoff_display": settings_row.request_cutoff_time.strftime("%-I:%M %p").lstrip("0"),
            "book_ahead_days": settings_row.book_ahead_days,
            "booking_open": settings_row.booking_open,
            "parent_note": settings_row.parent_note,
        },
        "slots": slots,
        "weekdays": [{"value": value, "label": label} for value, label in WEEKDAYS],
        "units": list(PortalUnit.objects.filter(is_active=True).order_by("name").values("id", "name")),
    }


def notify_drop_off_request(booking):
    child = booking.child.name
    when = f"{booking.care_date.strftime('%A, %b %-d')} at {booking.start_time.strftime('%-I:%M %p').lstrip('0')}"
    subject = f"We have your drop-off request for {child}"
    body = (
        f"We received your drop-off request for {child} on {when}.\n\n"
        f"Time: {booking.slot_label}\n"
        f"Amount: ${booking.amount:.2f}\n\n"
        "Finish payment if you have not already. Once it is paid, staff will pick up your child "
        "at that time. You can check the request anytime on the Drop-off tab in your portal."
    )
    _send_family_notice(booking.family, subject, body)
    booking.parent_notified_at = timezone.now()
    booking.save(update_fields=["parent_notified_at"])


def notify_drop_off_confirmed(booking):
    child = booking.child.name
    when = f"{booking.care_date.strftime('%A, %b %-d')} at {booking.start_time.strftime('%-I:%M %p').lstrip('0')}"
    subject = f"Drop-off is confirmed for {child}"
    body = (
        f"Drop-off is confirmed for {child} on {when}.\n\n"
        "Staff have this pickup on their list for that day. If plans change, contact your site "
        "as soon as you can."
    )
    _send_family_notice(booking.family, subject, body)


def _send_family_notice(family, subject, body):
    try:
        from .member_admin import send_family_parent_email

        send_family_parent_email(family, subject, body)
    except Exception:
        return


def today_pickup_count(unit=None):
    return len(pickup_rows(unit=unit, include_unpaid=True))
