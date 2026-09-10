"""Editable portal email templates — welcome, charge notices, reminders."""

from django.conf import settings
from django.urls import reverse

from core.email_service import send_site_email

from .models import PortalEmailTemplate

DEFAULT_TEMPLATES = {
    PortalEmailTemplate.KEY_STAFF_WELCOME: {
        "name": "Staff / admin welcome",
        "subject": "Your YEA {portal_label} login",
        "body": (
            "Hello {name},\n\n"
            "An account has been created for you on the Youth Education Academy {portal_label}.\n\n"
            "Sign in here: {portal_url}\n"
            "Username: {username}\n"
            "Password: {password}\n\n"
            "Please sign in and change your password after your first login.\n\n"
            "Youth Education Academy\n"
        ),
    },
    PortalEmailTemplate.KEY_CHARGE_NOTICE: {
        "name": "Charge posted",
        "subject": "New charge on your YEA account",
        "body": (
            "Hello {family_name},\n\n"
            "A charge has been posted to your account:\n\n"
            "Child: {child_name}\n"
            "Description: {description}\n"
            "Amount: ${amount}\n"
            "Date: {date}\n\n"
            "Your current balance is ${balance}.\n\n"
            "You can review and pay in the parent portal:\n"
            "{portal_url}\n\n"
            "Youth Education Academy\n"
        ),
    },
    PortalEmailTemplate.KEY_FIRST_DAY_REMINDER: {
        "name": "First-day payment reminder",
        "subject": "School starts September 8 — accounts must be paid",
        "body": (
            "Hello {family_name},\n\n"
            "School starts September 8th. All accounts need to be paid by the first day of "
            "program for your child to begin.\n\n"
            "Please also remember the $20 membership fee for the year.\n\n"
            "Sign in to review your balance and pay:\n"
            "{portal_url}\n\n"
            "Youth Education Academy\n"
        ),
    },
}


def ensure_email_templates():
    for key, defaults in DEFAULT_TEMPLATES.items():
        PortalEmailTemplate.objects.get_or_create(key=key, defaults=defaults)


def get_email_template(key):
    ensure_email_templates()
    template = PortalEmailTemplate.objects.filter(key=key).first()
    if template:
        return template
    defaults = DEFAULT_TEMPLATES[key]
    return PortalEmailTemplate.objects.create(key=key, **defaults)


def save_email_template(key, subject, body, is_enabled=True):
    if key not in DEFAULT_TEMPLATES:
        raise ValueError("Unknown email template.")
    template = get_email_template(key)
    subject = (subject or "").strip()
    body = (body or "").strip()
    if not subject or not body:
        raise ValueError("Enter a subject and message for the email template.")
    template.subject = subject
    template.body = body
    template.is_enabled = bool(is_enabled)
    template.save(update_fields=["subject", "body", "is_enabled", "updated_at"])
    return template


def render_email(key, context):
    template = get_email_template(key)
    return _fill(template.subject, context), _fill(template.body, context)


def _fill(text, context):
    rendered = text or ""
    for name, value in context.items():
        rendered = rendered.replace("{" + name + "}", "" if value is None else str(value))
    return rendered


def absolute_portal_url(url_name):
    return settings.SITE_URL.rstrip("/") + reverse(url_name)


def parent_portal_url():
    return absolute_portal_url("portal_parent_login")


def welcome_portal_url(portal_type):
    if portal_type == "admin":
        return absolute_portal_url("portal_admin_login")
    return absolute_portal_url("portal_staff_login")


def send_staff_welcome_email(account, username, password, portal_type="staff"):
    email = (account.user.email or "").strip()
    if not email:
        return 0
    template = get_email_template(PortalEmailTemplate.KEY_STAFF_WELCOME)
    if not template.is_enabled:
        return 0
    portal_label = "admin portal" if portal_type == "admin" else "staff portal"
    subject, body = render_email(
        PortalEmailTemplate.KEY_STAFF_WELCOME,
        {
            "name": account.display_name or username,
            "username": username,
            "password": password,
            "portal_url": welcome_portal_url(portal_type),
            "portal_label": portal_label,
        },
    )
    if portal_type == "admin":
        body = (
            body.rstrip()
            + "\n\nYou can open the staff portal from the header after you sign in "
            "(Staff portal). Same login — you do not need a separate staff account "
            "to take attendance or work at a unit.\n"
        )
    return send_site_email(subject=subject, message=body, recipient_list=[email])


def notify_charge_posted(family, entry):
    from .member_admin import parent_email_for_family

    template = get_email_template(PortalEmailTemplate.KEY_CHARGE_NOTICE)
    if not template.is_enabled:
        return 0
    email = parent_email_for_family(family)
    if not email:
        return 0
    family.refresh_from_db(fields=["balance", "name"])
    subject, body = render_email(
        PortalEmailTemplate.KEY_CHARGE_NOTICE,
        {
            "family_name": family.name,
            "child_name": entry.child_name or "Family",
            "description": entry.description,
            "amount": f"{abs(entry.amount):.2f}",
            "date": entry.date.isoformat(),
            "balance": f"{family.balance:.2f}",
            "portal_url": parent_portal_url(),
        },
    )
    return send_site_email(subject=subject, message=body, recipient_list=[email])


def send_first_day_reminders(emails=None, sender=None):
    from .member_admin import parent_email_recipients, send_parent_emails

    template = get_email_template(PortalEmailTemplate.KEY_FIRST_DAY_REMINDER)
    if not template.is_enabled:
        raise ValueError("The first-day reminder template is turned off.")
    recipients = emails
    if recipients is None:
        recipients = [row["email"] for row in parent_email_recipients()]
    if not recipients:
        raise ValueError("No parent emails on file yet.")
    subject, body = render_email(
        PortalEmailTemplate.KEY_FIRST_DAY_REMINDER,
        {
            "family_name": "families",
            "portal_url": parent_portal_url(),
        },
    )
    from .models import PortalParentEmail

    return send_parent_emails(
        subject,
        body,
        recipients,
        sender=sender,
        source=PortalParentEmail.SOURCE_REMINDER,
    )
