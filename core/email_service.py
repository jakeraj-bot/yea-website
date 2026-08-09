"""Central email helper — logs clearly when SMTP is not configured."""

import logging

from django.conf import settings
from django.core.mail import EmailMessage

logger = logging.getLogger(__name__)


def email_is_configured():
    backend = (settings.EMAIL_BACKEND or "").lower()
    if "console" in backend or "locmem" in backend:
        return False
    if "smtp" in backend:
        return bool(settings.EMAIL_HOST and settings.EMAIL_HOST_USER and settings.EMAIL_HOST_PASSWORD)
    return True


def send_site_email(subject, message, recipient_list, *, fail_silently=True, reply_to=None):
    recipients = [email.strip() for email in recipient_list if email and email.strip()]
    if not recipients:
        logger.warning("Email skipped (no recipients): subject=%r", subject)
        return 0

    if not email_is_configured():
        logger.warning(
            "Email NOT sent — SMTP is not configured. subject=%r recipients=%s. "
            "On Render, set EMAIL_HOST, EMAIL_PORT, EMAIL_HOST_USER, EMAIL_HOST_PASSWORD, and EMAIL_USE_TLS.",
            subject,
            recipients,
        )
        return 0

    try:
        email = EmailMessage(
            subject=subject,
            body=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=recipients,
            reply_to=list(reply_to or []),
        )
        sent = email.send(fail_silently=False)
        logger.info("Email sent: subject=%r recipients=%s", subject, recipients)
        return sent
    except Exception:
        logger.exception("Failed to send email: subject=%r recipients=%s", subject, recipients)
        if not fail_silently:
            raise
        return 0
