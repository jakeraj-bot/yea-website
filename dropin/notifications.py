import logging

from django.core.mail import send_mail

logger = logging.getLogger(__name__)


def notify_staff_new_registration(profile):
    try:
        from django.conf import settings

        send_mail(
            subject=f"Drop-in registration to review — {profile.family_name}",
            message=(
                f"A family completed drop-in registration and needs your approval before they can book.\n\n"
                f"Family: {profile.family_name}\n"
                f"Email: {profile.primary_email}\n"
                f"Phone: {profile.primary_phone}\n\n"
                f"Approve in Django admin → Drop-in family profiles."
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[settings.CONTACT_EMAIL],
            fail_silently=False,
        )
    except Exception:
        logger.exception("Failed to send drop-in registration notification")


def notify_parent_approved(profile):
    try:
        from django.conf import settings

        send_mail(
            subject="Your YEA drop-in registration is approved",
            message=(
                f"Hi {profile.primary_first_name},\n\n"
                f"Your drop-in registration for {profile.family_name} has been approved.\n"
                f"You can now log in and book individual drop-in days:\n"
                f"{settings.SITE_URL.rstrip('/')}/drop-in/login/\n\n"
                f"After-school drop-in: $20/day (sign up by 2:00 PM the day of care)\n"
                f"Summer camp drop-in: $35/day (sign up by 7:30 AM the day of care)\n\n"
                f"Youth Education Academy"
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[profile.primary_email],
            fail_silently=False,
        )
    except Exception:
        logger.exception("Failed to send drop-in approval email to parent")


def notify_staff_new_booking(booking):
    try:
        from django.conf import settings

        send_mail(
            subject=f"Drop-in booking — {booking.child} on {booking.date}",
            message=(
                f"Paid drop-in booking.\n\n"
                f"Child: {booking.child.first_name} {booking.child.last_name}\n"
                f"Program: {booking.get_program_display()}\n"
                f"Location: {booking.get_location_display()}\n"
                f"Date: {booking.date}\n"
                f"Family: {booking.profile.family_name}\n"
                f"Phone: {booking.profile.primary_phone}\n"
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[settings.CONTACT_EMAIL],
            fail_silently=False,
        )
    except Exception:
        logger.exception("Failed to send drop-in booking notification")
