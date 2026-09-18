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
            "A charge has been posted to your account.\n\n"
            "What you owe for: {owe_for}\n"
            "Child: {child_name}\n"
            "Week: {week}\n"
            "This charge: ${amount}\n"
            "Date: {date}\n\n"
            "Current balance for {child_name}: ${child_balance}\n"
            "Family balance (what the household owes): ${family_balance}\n\n"
            "You can pay in the parent portal. Pay now:\n"
            "{payment_url}\n\n"
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
            "Sign in to review your balance and pay now:\n"
            "{portal_url}\n\n"
            "Youth Education Academy\n"
        ),
    },
    PortalEmailTemplate.KEY_BALANCE_UPDATED: {
        "name": "Balance updated",
        "subject": "Your YEA balance was updated",
        "body": (
            "Hello {family_name},\n\n"
            "Your balance was updated.\n\n"
            "What it is for: {owe_for}\n"
            "Child: {child_name}\n"
            "Week: {week}\n"
            "Previous charge amount: ${previous_amount}\n"
            "New charge amount: ${amount}\n\n"
            "Current balance for {child_name}: ${child_balance}\n"
            "Family balance (what the household owes): ${family_balance}\n\n"
            "You can pay in the parent portal. Pay now:\n"
            "{payment_url}\n\n"
            "Youth Education Academy\n"
        ),
    },
    PortalEmailTemplate.KEY_LATE_PAYMENT: {
        "name": "Late payment reminder",
        "subject": "Payment due Friday — ${late_fee} late fee as of Tuesday",
        "body": (
            "Hello {family_name},\n\n"
            "Payments are due Friday. If you do not pay, a ${late_fee} late fee will be "
            "added as of Tuesday (one-day grace: due Friday, fee Tuesday).\n\n"
            "Your current family balance is ${family_balance}.\n"
            "{child_lines}\n"
            "Please pay now in the parent portal:\n"
            "{portal_url}\n\n"
            "Youth Education Academy\n"
        ),
    },
    PortalEmailTemplate.KEY_APPLICATION_SUBMITTED: {
        "name": "Application submitted",
        "subject": "[YEA] Application received — {child_name}",
        "body": (
            "Hello {parent_name},\n\n"
            "Thank you for submitting your enrollment application for {child_name}.\n\n"
            "Reference: {reference}\n"
            "Program: {program} — {unit}\n\n"
            "We'll review your application and contact you if we need anything else. "
            "Track status anytime in the parent portal:\n"
            "{portal_url}\n\n"
            "Youth Education Academy\n"
        ),
    },
    PortalEmailTemplate.KEY_APPLICATION_SUBMITTED_WAITLIST: {
        "name": "Waitlist application submitted",
        "subject": "[YEA] You're on the before care waitlist — {child_name}",
        "body": (
            "Hello {parent_name},\n\n"
            "Thank you for joining the before care waitlist at {unit} for {child_name}.\n\n"
            "Reference: {reference}\n"
            "Program: {program} — {unit}\n\n"
            "Families on the waitlist are contacted in the order requests were received when a spot opens. "
            "Track status anytime in the parent portal:\n"
            "{portal_url}\n\n"
            "Youth Education Academy\n"
        ),
    },
    PortalEmailTemplate.KEY_APPLICATION_APPROVED: {
        "name": "Application approved",
        "subject": "Enrollment approved — {child_name}",
        "body": (
            "Hi {parent_name},\n\n"
            "Great news — {child_name}'s enrollment application for {program} "
            "at {unit} has been approved. They are on the active roster.\n\n"
            "{child_name} can start on {start_date}. Payment is due before the program start. "
            "You can pay in the parent portal.\n\n"
            "{amount_due}\n"
            "{membership_fee}\n"
            "{four_cs_contract}\n\n"
            "Pay now (this link opens your payment page after you sign in):\n"
            "{payment_url}\n\n"
            "{payment_steps}\n\n"
            "Youth Education Academy\n"
        ),
    },
    PortalEmailTemplate.KEY_APPLICATION_APPROVED_WAITLIST: {
        "name": "Waitlist application approved",
        "subject": "Waitlist approved — {child_name} can start {start_date}",
        "body": (
            "Hi {parent_name},\n\n"
            "A spot opened — {child_name}'s waitlist request for {program} "
            "at {unit} has been approved. They are on the active roster.\n\n"
            "{child_name} can start on {start_date}. Payment is due before the program start. "
            "You can pay in the parent portal.\n\n"
            "{amount_due}\n"
            "{membership_fee}\n"
            "{four_cs_contract}\n\n"
            "Pay now (this link opens your payment page after you sign in):\n"
            "{payment_url}\n\n"
            "{payment_steps}\n\n"
            "Youth Education Academy\n"
        ),
    },
}

APPLICATION_TEMPLATE_PLACEHOLDERS = (
    "{parent_name} {child_name} {program} {unit} {start_date} {payment_url} {payment_steps} "
    "{amount_due} {membership_fee} {four_cs_contract}"
)

FOUR_CS_CONTRACT_EMAIL = "jakeraj@yeanj.org"

FOUR_CS_CONTRACT_REMINDER = (
    "Because this is a 4Cs membership, please send your 4Cs contract to "
    f"{FOUR_CS_CONTRACT_EMAIL} so Youth Education Academy can sign it. "
    "We will email the signed contract back to you for you to give to 4Cs."
)


def application_uses_waitlist_emails(app):
    return app.program == "before_care" or app.status == "waitlist"


def submitted_template_key(app):
    if application_uses_waitlist_emails(app):
        return PortalEmailTemplate.KEY_APPLICATION_SUBMITTED_WAITLIST
    return PortalEmailTemplate.KEY_APPLICATION_SUBMITTED


def approved_template_key(app, *, waitlist=None):
    if waitlist is None:
        waitlist = application_uses_waitlist_emails(app)
    if waitlist:
        return PortalEmailTemplate.KEY_APPLICATION_APPROVED_WAITLIST
    return PortalEmailTemplate.KEY_APPLICATION_APPROVED


def format_member_start_date(value):
    if not value:
        return ""
    from django.utils.formats import date_format

    return date_format(value, "F j, Y")


def application_email_context(app, *, start_date=None, portal_url=None, membership_amount=None, plan=None, membership_already_posted=False):
    from enrollment.application_review import child_display_name, first_payment_steps_text, program_name_for_email
    from enrollment.locations import get_location_label

    start = start_date if start_date is not None else getattr(app, "member_start_date", None)
    payment_url = parent_pay_now_url()
    track_url = portal_url or (settings.SITE_URL.rstrip("/") + reverse("portal_parent_login"))
    context = {
        "parent_name": (app.primary_first_name or "").strip() or "there",
        "family_name": app.family_name or "",
        "child_name": child_display_name(app),
        "program": program_name_for_email(app),
        "unit": get_location_label(app.program_location),
        "start_date": format_member_start_date(start),
        "payment_url": payment_url,
        "portal_url": track_url,
        "payment_steps": first_payment_steps_text(),
        "reference": str(app.reference),
    }
    context.update(
        approval_payment_placeholders(
            app,
            membership_amount=membership_amount,
            plan=plan,
            membership_already_posted=membership_already_posted,
        )
    )
    return context


def _money(amount):
    from decimal import Decimal

    value = amount if amount is not None else Decimal("0.00")
    return f"${value:.2f}"


def _plan_cadence_words(plan_label):
    label = (plan_label or "Weekly").strip().lower()
    if "month" in label:
        return "monthly"
    if "bi" in label:
        return "bi-weekly"
    return "weekly"


def approval_payment_placeholders(app, *, membership_amount=None, plan=None, membership_already_posted=False):
    """Fill {amount_due}, {membership_fee}, and {four_cs_contract} for approval emails."""
    from decimal import Decimal

    from enrollment.application_review import empty_approve_plan, membership_amount_for_email

    plan = plan if plan is not None else empty_approve_plan(app)
    if membership_amount is None:
        membership_amount = membership_amount_for_email(app, None)
    membership = membership_amount if membership_amount is not None else Decimal("0.00")
    attached = bool(plan.get("attached") and plan.get("family_pays") is not None)
    family_pays = plan.get("family_pays") if attached else None
    if family_pays is None:
        family_pays = Decimal("0.00")
    membership_line = ""
    amount_due = ""
    if attached and family_pays > 0:
        total = (membership if not membership_already_posted else Decimal("0.00")) + family_pays
        cadence = _plan_cadence_words(plan.get("billing_plan"))
        kind = "parent copay" if plan.get("is_four_cs") else "tuition"
        scholarship_note = " (family-pays after scholarship)" if plan.get("has_scholarship") else ""
        if membership_already_posted:
            amount_due = (
                f"Amount due to start: {_money(family_pays)}. This is the first {_money(family_pays)} "
                f"{cadence} {kind}{scholarship_note}. Membership is already on your account."
            )
        elif membership > 0:
            amount_due = (
                f"Amount due to start: {_money(total)}. This includes the {_money(membership)} membership fee "
                f"and the first {_money(family_pays)} {cadence} {kind}{scholarship_note}."
            )
        else:
            amount_due = (
                f"Amount due to start: {_money(family_pays)}. This is the first {_money(family_pays)} "
                f"{cadence} {kind}{scholarship_note}."
            )
    else:
        if membership_already_posted:
            membership_line = "Membership is already on your account — it is not charged again."
        elif membership > 0:
            membership_line = f"The membership fee to start is {_money(membership)}."
        else:
            membership_line = "The membership fee is waived."
    four_cs_contract = FOUR_CS_CONTRACT_REMINDER if plan.get("is_four_cs") else ""
    return {
        "amount_due": amount_due,
        "membership_fee": membership_line,
        "four_cs_contract": four_cs_contract,
    }


def send_application_submitted_parent_email(app, *, staff_created=False, save_draft=False):
    """Parent email after an application is submitted. Drafts keep the complete-your-form copy."""
    email = (app.primary_email or "").strip()
    if not email:
        return 0
    if save_draft:
        child_name = f"{app.student_first_name} {app.student_last_name}".strip()
        portal_url = settings.SITE_URL.rstrip("/") + reverse("portal_parent_login")
        return send_site_email(
            subject="[YEA] Complete your enrollment application",
            message=(
                f"Hello {app.primary_first_name},\n\n"
                f"YEA staff started an enrollment application for {child_name}. "
                f"Please sign in to the parent portal to complete medical information, policies, and billing.\n\n"
                f"Reference: {app.reference}\n\n"
                f"Parent portal:\n{portal_url}\n\n"
                f"Youth Education Academy\n"
            ),
            recipient_list=[email],
        )
    key = submitted_template_key(app)
    template = get_email_template(key)
    if not template.is_enabled:
        return 0
    context = application_email_context(app)
    subject, body = render_email(key, context)
    return send_site_email(subject=subject, message=body, recipient_list=[email])


def render_application_approved_email(
    app,
    *,
    start_date=None,
    waitlist=None,
    membership_amount=None,
    plan=None,
    membership_already_posted=False,
):
    key = approved_template_key(app, waitlist=waitlist)
    template = get_email_template(key)
    context = application_email_context(
        app,
        start_date=start_date,
        portal_url=parent_pay_now_url(),
        membership_amount=membership_amount,
        plan=plan,
        membership_already_posted=membership_already_posted,
    )
    subject, body = render_email(key, context)
    body = with_pay_now_link(body, context["payment_url"])
    body = _collapse_blank_lines(body)
    return template, subject, body


def _collapse_blank_lines(text):
    import re

    return re.sub(r"\n{3,}", "\n\n", text or "").strip() + "\n"


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


PAYMENT_PATH = "/portal/parent/payment/"


def absolute_portal_url(url_name):
    return settings.SITE_URL.rstrip("/") + reverse(url_name)


def parent_payment_page_url():
    """Absolute Pay now URL. After login this is `/portal/parent/payment/`."""
    return absolute_portal_url("portal_parent_payment")


def parent_pay_now_url():
    """Pay now link for parent emails (SITE_URL + payment page)."""
    return parent_payment_page_url()


def parent_portal_url():
    """Parent emails use the payment page, not login-then-dashboard."""
    return parent_payment_page_url()


def with_pay_now_link(body, payment_url=None):
    """Guarantee a Pay now payment-page URL is visible in the email body."""
    payment_url = payment_url or parent_pay_now_url()
    text = body or ""
    if PAYMENT_PATH in text:
        return text
    block = f"You can pay in the parent portal. Pay now:\n{payment_url}\n"
    marker = "Youth Education Academy"
    idx = text.rfind(marker)
    if idx >= 0:
        return text[:idx].rstrip() + "\n\n" + block + "\n" + text[idx:]
    return text.rstrip() + "\n\n" + block


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


def _charge_email_context(family, entry=None, *, previous_amount=None):
    from .owed_weeks import charge_owe_for, ledger_balance_context, week_label_from_charge

    child_name = (getattr(entry, "child_name", None) or "").strip() or ("your family" if entry is None else "Family")
    description = (getattr(entry, "description", None) or "").strip()
    charge_date = getattr(entry, "date", None)
    week = week_label_from_charge(description, charge_date) if entry else ""
    balances = ledger_balance_context(family, "" if child_name == "Family" else child_name)
    amount = abs(entry.amount) if entry is not None and getattr(entry, "amount", None) is not None else 0
    previous = previous_amount if previous_amount is not None else amount
    return {
        "family_name": family.name,
        "child_name": child_name,
        "description": description,
        "owe_for": charge_owe_for(entry),
        "week": week or "—",
        "amount": f"{amount:.2f}",
        "previous_amount": f"{abs(previous):.2f}",
        "date": charge_date.isoformat() if charge_date else "",
        "child_balance": balances["child_balance_display"],
        "family_balance": balances["family_balance_display"],
        "balance": balances["family_balance_display"],
        "portal_url": parent_pay_now_url(),
        "payment_url": parent_pay_now_url(),
    }


def notify_charge_posted(family, entry):
    from .member_admin import parent_email_for_family

    template = get_email_template(PortalEmailTemplate.KEY_CHARGE_NOTICE)
    if not template.is_enabled:
        return 0
    email = parent_email_for_family(family)
    if not email:
        return 0
    context = _charge_email_context(family, entry)
    subject, body = render_email(PortalEmailTemplate.KEY_CHARGE_NOTICE, context)
    body = with_pay_now_link(body, context["payment_url"])
    return send_site_email(subject=subject, message=body, recipient_list=[email])


def notify_balance_updated(family, entry=None, *, previous_amount=None):
    from .member_admin import parent_email_for_family

    template = get_email_template(PortalEmailTemplate.KEY_BALANCE_UPDATED)
    if not template.is_enabled:
        return 0
    email = parent_email_for_family(family)
    if not email:
        return 0
    context = _charge_email_context(family, entry, previous_amount=previous_amount)
    subject, body = render_email(PortalEmailTemplate.KEY_BALANCE_UPDATED, context)
    body = with_pay_now_link(body, context["payment_url"])
    return send_site_email(subject=subject, message=body, recipient_list=[email])


def send_updated_balance_email(family, entry=None, *, previous_amount=None):
    """Manual send from the family Billing tab."""
    template = get_email_template(PortalEmailTemplate.KEY_BALANCE_UPDATED)
    if not template.is_enabled:
        raise ValueError("The updated-balance email template is turned off.")
    sent = notify_balance_updated(family, entry, previous_amount=previous_amount)
    if not sent:
        raise ValueError("No parent email is on file for this family.")
    return sent


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


def late_notice_preview_rows(*, unit=None):
    from .member_admin import parent_email_for_family
    from .owed_weeks import families_with_balance

    rows = []
    seen = set()
    for item in families_with_balance(unit=unit):
        family = item["family"]
        email = parent_email_for_family(family)
        if not email or email.lower() in seen:
            continue
        seen.add(email.lower())
        rows.append(
            {
                "family_id": family.pk,
                "family": family.name,
                "email": email,
                "unit": family.unit.name,
                "balance": f"{item['balance']:.2f}",
            }
        )
    return rows


def _child_balance_lines(family):
    from .family_list import child_balance_from_map, child_balance_map

    maps = child_balance_map(family)
    lines = []
    for child in family.children.filter(is_active=True).order_by("name"):
        amount = child_balance_from_map(maps, child.name)
        if amount > 0:
            lines.append(f"- {child.name}: ${amount:.2f}")
    return "\n".join(lines)


def send_late_payment_notices(emails=None, sender=None, *, unit=None):
    from .member_admin import parent_email_for_family, send_parent_emails
    from .models import PortalParentEmail
    from .owed_weeks import families_with_balance, late_fee_amount

    template = get_email_template(PortalEmailTemplate.KEY_LATE_PAYMENT)
    if not template.is_enabled:
        raise ValueError("The late payment email template is turned off.")
    wanted = None
    if emails is not None:
        wanted = {email.strip().lower() for email in emails if email and email.strip()}
    rows = []
    seen = set()
    for item in families_with_balance(unit=unit):
        family = item["family"]
        email = parent_email_for_family(family)
        if not email or email.lower() in seen:
            continue
        if wanted is not None and email.lower() not in wanted:
            continue
        seen.add(email.lower())
        rows.append((family, email, item["balance"]))
    if not rows:
        raise ValueError("No families with a balance and a parent email.")
    sent = 0
    fee = f"{late_fee_amount():.2f}"
    for family, email, balance in rows:
        subject, body = render_email(
            PortalEmailTemplate.KEY_LATE_PAYMENT,
            {
                "family_name": family.name,
                "family_balance": f"{balance:.2f}",
                "late_fee": fee,
                "child_lines": _child_balance_lines(family),
                "portal_url": parent_portal_url(),
            },
        )
        count, _total = send_parent_emails(
            subject,
            body,
            [email],
            sender=sender,
            source=PortalParentEmail.SOURCE_REMINDER,
        )
        sent += count
    return sent, len(rows)
