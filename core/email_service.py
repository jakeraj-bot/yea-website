"""Central email helper — logs clearly when SMTP is not configured."""

import logging
from email.utils import formataddr, parseaddr

from django.conf import settings
from django.core.mail import EmailMessage

logger = logging.getLogger(__name__)

ORG_FROM_NAME = "Youth Education Academy"


def email_is_configured():
    backend = (settings.EMAIL_BACKEND or "").lower()
    if "console" in backend or "locmem" in backend:
        return False
    if "smtp" in backend:
        return bool(settings.EMAIL_HOST and settings.EMAIL_HOST_USER and settings.EMAIL_HOST_PASSWORD)
    return True


def _bare_email(value):
    if not value:
        return ""
    _name, address = parseaddr(str(value))
    return (address or str(value)).strip()


def _org_email_settings():
    try:
        from portal.models import PortalOrgSetting

        return PortalOrgSetting.load()
    except Exception:
        return None


def portal_sending_email():
    """From address for automated / basic portal mail."""
    org = _org_email_settings()
    if org:
        stored = _bare_email(getattr(org, "portal_sending_email", "") or "")
        if stored:
            return stored
    return _bare_email(settings.DEFAULT_FROM_EMAIL) or settings.DEFAULT_FROM_EMAIL


def portal_bcc_email():
    """Copy inbox for mail to parents. Defaults to the portal sending address."""
    org = _org_email_settings()
    if org:
        stored = _bare_email(getattr(org, "portal_bcc_email", "") or "")
        if stored:
            return stored
    return portal_sending_email()


def formatted_portal_from(display_name=None):
    address = portal_sending_email()
    name = (display_name or "").strip() or ORG_FROM_NAME
    if not address:
        return settings.DEFAULT_FROM_EMAIL
    return formataddr((name, address))


def staff_sender_name(user):
    if not user:
        return ""
    account = getattr(user, "portal_staff_account", None)
    if account and (account.display_name or "").strip():
        return account.display_name.strip()
    full = (user.get_full_name() or "").strip()
    if full:
        return full
    return (getattr(user, "email", "") or "").strip() or "YEA staff"


def staff_reply_to_email(user):
    if not user:
        return ""
    account = getattr(user, "portal_staff_account", None)
    if account and getattr(account.user, "email", ""):
        email = (account.user.email or "").strip()
        if email:
            return email
    return (getattr(user, "email", "") or "").strip()


def staff_from_display_name(user):
    name = staff_sender_name(user) or "YEA staff"
    return f"{name} via {ORG_FROM_NAME}"


def _clean_address_list(values):
    unique = []
    seen = set()
    for value in values or []:
        if isinstance(value, (list, tuple)):
            continue
        cleaned = _bare_email(value)
        key = cleaned.lower()
        if cleaned and key not in seen:
            seen.add(key)
            unique.append(cleaned)
    return unique


def parent_copy_bcc(*, to_emails=None, cc_emails=None, extra_bcc=None):
    """BCC the portal copy inbox unless it is already on the message."""
    copy_to = portal_bcc_email()
    already = {addr.lower() for addr in _clean_address_list(list(to_emails or []) + list(cc_emails or []) + list(extra_bcc or []))}
    bcc = list(_clean_address_list(extra_bcc))
    if copy_to and copy_to.lower() not in already:
        bcc.append(copy_to)
    return bcc


def _attach_files(email, attachments):
    for item in attachments or []:
        if isinstance(item, (tuple, list)) and item:
            name = item[0]
            content = item[1] if len(item) > 1 else b""
            mimetype = item[2] if len(item) > 2 else None
            email.attach(name, content, mimetype)
        elif hasattr(item, "read"):
            name = getattr(item, "name", "attachment")
            content = item.read()
            mimetype = getattr(item, "content_type", None)
            email.attach(name, content, mimetype)


def send_site_email(
    subject,
    message,
    recipient_list,
    *,
    fail_silently=True,
    reply_to=None,
    attachments=None,
    cc=None,
    bcc=None,
    from_email=None,
    sender=None,
    copy_to_portal=True,
):
    recipients = _clean_address_list(recipient_list)
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

    cc_list = _clean_address_list(cc)
    extra_bcc = _clean_address_list(bcc)
    if copy_to_portal:
        bcc_list = parent_copy_bcc(to_emails=recipients, cc_emails=cc_list, extra_bcc=extra_bcc)
    else:
        bcc_list = extra_bcc

    replies = _clean_address_list(reply_to if not isinstance(reply_to, str) else [reply_to])
    from_name = None
    if sender is not None:
        from_name = staff_from_display_name(sender)
        staff_reply = staff_reply_to_email(sender)
        if staff_reply and staff_reply.lower() not in {addr.lower() for addr in replies}:
            replies.append(staff_reply)

    from_header = from_email or formatted_portal_from(from_name)

    try:
        email = EmailMessage(
            subject=subject,
            body=message,
            from_email=from_header,
            to=recipients,
            cc=cc_list or None,
            bcc=bcc_list or None,
            reply_to=replies or None,
        )
        _attach_files(email, attachments)
        sent = email.send(fail_silently=False)
        logger.info("Email sent: subject=%r recipients=%s", subject, recipients)
        return sent
    except Exception:
        logger.exception("Failed to send email: subject=%r recipients=%s", subject, recipients)
        if not fail_silently:
            raise
        return 0
