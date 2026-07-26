from datetime import datetime, time

from django.utils import timezone

from . import constants
from .models import DropInBooking, DropInDayCapacity


def locations_for_program(program):
    if program == constants.PROGRAM_SUMMER_CAMP:
        return constants.SUMMER_CAMP_LOCATIONS
    return constants.AFTER_SCHOOL_LOCATIONS


def signup_deadline_for(program, care_date):
    """Return timezone-aware datetime for the signup cutoff on care_date."""
    deadline_time = constants.SIGNUP_DEADLINE[program]
    naive = datetime.combine(care_date, deadline_time)
    return timezone.make_aware(naive, timezone.get_current_timezone())


def booking_is_open(program, care_date, now=None):
    now = now or timezone.localtime()
    if care_date < now.date():
        return False, "That date has already passed."
    deadline = signup_deadline_for(program, care_date)
    if now > deadline:
        label = constants.DEADLINE_LABEL[program]
        return False, f"Signup closed. Drop-in registration ends by {label}."
    return True, ""


def get_capacity(program, location, care_date):
    try:
        return DropInDayCapacity.objects.get(
            program=program,
            location=location,
            date=care_date,
        )
    except DropInDayCapacity.DoesNotExist:
        return None


def booked_count(program, location, care_date):
    return DropInBooking.objects.filter(
        program=program,
        location=location,
        date=care_date,
        status=DropInBooking.STATUS_PAID,
    ).count()


def pending_count(program, location, care_date):
    return DropInBooking.objects.filter(
        program=program,
        location=location,
        date=care_date,
        status=DropInBooking.STATUS_PENDING,
    ).count()


def spots_remaining(program, location, care_date):
    capacity = get_capacity(program, location, care_date)
    if not capacity:
        return 0, None
    used = booked_count(program, location, care_date)
    return max(capacity.max_slots - used, 0), capacity


def validate_booking(program, location, care_date, child, profile=None, now=None):
    if profile and not profile.is_booking_ready:
        return False, "Your registration must be approved by staff before you can book drop-in days."

    if location not in locations_for_program(program):
        return False, "That location is not available for the selected program."

    open_ok, open_msg = booking_is_open(program, care_date, now=now)
    if not open_ok:
        return False, open_msg

    capacity = get_capacity(program, location, care_date)
    if not capacity:
        return False, "Drop-in is not available on that date. Contact us if you have questions."

    remaining, _ = spots_remaining(program, location, care_date)
    if remaining <= 0:
        return False, "That day is full. You can join the waitlist — families are contacted in the order requests were received if a spot opens up."

    if DropInBooking.objects.filter(
        child=child,
        program=program,
        location=location,
        date=care_date,
        status__in=[DropInBooking.STATUS_PAID, DropInBooking.STATUS_PENDING],
    ).exists():
        return False, "This child is already signed up for that day."

    return True, ""


def waitlist_count(program, location, care_date):
    from .models import DropInWaitlistEntry

    return DropInWaitlistEntry.objects.filter(
        program=program,
        location=location,
        date=care_date,
        status=DropInWaitlistEntry.STATUS_WAITING,
    ).count()


def validate_waitlist_join(program, location, care_date, child, profile=None, now=None):
    if profile and not profile.is_booking_ready:
        return False, "Your registration must be approved by staff before joining a waitlist."

    if location not in locations_for_program(program):
        return False, "That location is not available for the selected program."

    open_ok, open_msg = booking_is_open(program, care_date, now=now)
    if not open_ok:
        return False, open_msg

    capacity = get_capacity(program, location, care_date)
    if not capacity:
        return False, "Drop-in is not available on that date."

    remaining, _ = spots_remaining(program, location, care_date)
    if remaining > 0:
        return False, "Spots are still available — book directly instead of joining the waitlist."

    from .models import DropInBooking, DropInWaitlistEntry

    if DropInWaitlistEntry.objects.filter(
        child=child,
        program=program,
        location=location,
        date=care_date,
        status=DropInWaitlistEntry.STATUS_WAITING,
    ).exists():
        return False, "This child is already on the waitlist for that day."

    if DropInBooking.objects.filter(
        child=child,
        program=program,
        location=location,
        date=care_date,
        status__in=[DropInBooking.STATUS_PAID, DropInBooking.STATUS_PENDING],
    ).exists():
        return False, "This child already has a booking for that day."

    return True, ""
