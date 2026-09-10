"""Admin tools for collections, suspend, parent accounts, emails, and family cleanup."""

import secrets
from decimal import Decimal, InvalidOperation

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from core.email_service import send_site_email
from enrollment.models import EnrollmentApplication
from enrollment.portal_integration import (
    PAYMENT_TO_BILLING_TYPE,
    _unique_family_slug,
    displayed_payment_plan,
    family_display_label,
)

from .models import (
    PortalChild,
    PortalDiscountAssignment,
    PortalDiscountPlan,
    PortalFamily,
    PortalParentAccount,
    PortalPriorBalance,
    PortalUnit,
)
from .usernames import allocate_portal_username, display_username

SUSPEND_REASONS = [
    ("late_payment", "Late payment"),
    ("missing_payment", "Missing payment"),
    ("high_balance", "High balance"),
    ("other", "Other"),
]

OPEN_APPLICATION_STATUSES = ("under_review", "pending_documents", "waitlist")
COUNTED_ENROLLED_STATUSES = ("approved", "enrolled")
PLACEHOLDER_UNIT_SLUGS = {"main-location", "main_location"}
PLACEHOLDER_UNIT_NAMES = {"main location", "main"}
PARENT_PASSWORD_RESET_FLASH_KEY = "portal_parent_password_reset_once"


def is_placeholder_unit(unit):
    if not unit:
        return True
    slug = (unit.slug or "").replace("_", "-").lower()
    name = (unit.name or "").strip().lower()
    return slug in PLACEHOLDER_UNIT_SLUGS or name in PLACEHOLDER_UNIT_NAMES


def program_units():
    return [unit for unit in PortalUnit.objects.filter(is_active=True).order_by("name") if not is_placeholder_unit(unit)]


def resolve_family(family_slug=None, family_id=None, unit=None):
    from .unit_visibility import family_visible_to_unit

    if family_id:
        family = PortalFamily.objects.filter(pk=family_id).select_related("unit").first()
        if family:
            if unit and not family_visible_to_unit(family, unit):
                return None
            return family
    qs = PortalFamily.objects.select_related("unit")
    if family_slug:
        qs = qs.filter(slug=family_slug)
    families = list(qs)
    if unit:
        families = [family for family in families if family_visible_to_unit(family, unit)]
    if not families:
        return None
    if len(families) == 1:
        return families[0]
    real = [family for family in families if not is_placeholder_unit(family.unit)]
    return (real or families)[0]


def parent_email_for_family(family):
    account = PortalParentAccount.objects.filter(family=family).select_related("user").first()
    if account and account.user.email:
        return account.user.email
    app = EnrollmentApplication.objects.filter(portal_family=family).order_by("-submitted_at").first()
    if app and app.primary_email:
        return app.primary_email
    return ""


def _split_person_name(full_name):
    parts = (full_name or "").strip().split()
    if not parts:
        return "", ""
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], " ".join(parts[1:])


def _normalize_member_email(value):
    from django.core.exceptions import ValidationError
    from django.core.validators import validate_email

    email = (value or "").strip().lower()
    if not email:
        raise ValueError("Enter a parent email.")
    try:
        validate_email(email)
    except ValidationError:
        raise ValueError("Enter a valid email address.")
    return email


def _email_in_use(email, exclude_user=None):
    User = get_user_model()
    qs = User.objects.filter(email__iexact=email)
    if exclude_user:
        qs = qs.exclude(pk=exclude_user.pk)
    return qs.exists()


def member_info_for_family(family):
    """Current live household/parent fields for the staff/admin edit form."""
    if not family:
        return None
    account = PortalParentAccount.objects.filter(family=family).select_related("user").first()
    app = EnrollmentApplication.objects.filter(portal_family=family).order_by("-submitted_at").first()
    user = account.user if account else None
    primary_first = (app.primary_first_name if app else "") or ""
    primary_last = (app.primary_last_name if app else "") or ""
    if not primary_first and not primary_last:
        primary_first, primary_last = _split_person_name(family.primary_contact)
    secondary_first = app.secondary_first_name if app else ""
    secondary_last = app.secondary_last_name if app else ""
    return {
        "family_id": family.pk,
        "family_name": family.name or (app.family_name if app else ""),
        "home_address": (app.home_address if app else "") or "",
        "primary_first_name": primary_first,
        "primary_last_name": primary_last,
        "primary_email": parent_email_for_family(family),
        "primary_phone": (app.primary_phone if app else "") or "",
        "secondary_first_name": secondary_first or "",
        "secondary_last_name": secondary_last or "",
        "secondary_email": (app.secondary_email_address if app else "") or "",
        "secondary_phone": (app.secondary_phone if app else "") or "",
        "login_username": display_username(user.username) if user else "",
        "has_parent_login": bool(account),
    }


def _sync_parent_login_email(family, email, first_name="", last_name=""):
    """Keep the parent User email (login / password-reset) in sync."""
    account = PortalParentAccount.objects.filter(family=family).select_related("user").first()
    if not account:
        return None
    user = account.user
    if _email_in_use(email, exclude_user=user):
        raise ValueError("That email is already used by another portal login.")
    updates = []
    if (user.email or "").strip().lower() != email:
        user.email = email
        updates.append("email")
    if first_name and user.first_name != first_name:
        user.first_name = first_name
        updates.append("first_name")
    if last_name and user.last_name != last_name:
        user.last_name = last_name
        updates.append("last_name")
    if updates:
        user.save(update_fields=updates)
    return user


def generate_temporary_parent_password(user=None):
    """Create a one-time temporary password that passes Django validators."""
    for _ in range(12):
        password = f"{secrets.token_urlsafe(10)}Aa1"
        try:
            validate_password(password, user=user)
            return password
        except ValidationError:
            continue
    return f"{secrets.token_urlsafe(16)}Aa1!"


def validate_parent_portal_password(password, user=None):
    new_password = (password or "").strip()
    if not new_password:
        raise ValueError("Enter a temporary password, or leave it blank to generate one.")
    try:
        validate_password(new_password, user=user)
    except ValidationError as exc:
        raise ValueError(" ".join(exc.messages))
    return new_password


def store_parent_password_reset_flash(request, payload):
    request.session[PARENT_PASSWORD_RESET_FLASH_KEY] = payload


def consume_parent_password_reset_flash(request, family_slug=None):
    if request is None:
        return None
    data = request.session.get(PARENT_PASSWORD_RESET_FLASH_KEY)
    if not data:
        return None
    if family_slug and data.get("family_slug") != family_slug:
        return None
    request.session.pop(PARENT_PASSWORD_RESET_FLASH_KEY, None)
    return data


@transaction.atomic
def reset_parent_portal_password(family, password="", *, actor="", generate=False):
    """Set a new parent portal password. The previous hash cannot be recovered."""
    if not family:
        raise ValueError("Family not found.")
    account = PortalParentAccount.objects.filter(family=family).select_related("user").first()
    if not account:
        raise ValueError("This family does not have a parent portal login yet.")
    user = account.user
    new_password = (password or "").strip()
    if generate or not new_password:
        new_password = generate_temporary_parent_password(user)
    else:
        new_password = validate_parent_portal_password(new_password, user=user)
    user.set_password(new_password)
    user.save(update_fields=["password"])
    _record_member_info_change(
        family,
        {"parent_password_reset": True},
        actor=actor,
    )
    return {
        "family_slug": family.slug,
        "family_name": family.name,
        "username": display_username(user.username),
        "email": user.email or "",
        "password": new_password,
    }


def _record_member_info_change(family, changes, actor=""):
    from .models import PortalProfileChangeRequest

    if not changes:
        return None
    account = PortalParentAccount.objects.filter(family=family).first()
    if not account:
        return None
    return PortalProfileChangeRequest.objects.create(
        account=account,
        changes=changes,
        status=PortalProfileChangeRequest.STATUS_APPROVED,
        reviewed_at=timezone.now(),
        reviewed_by=(actor or "Staff")[:120],
        notes="Staff/admin updated live member information.",
    )


@transaction.atomic
def update_family_member_info(family, data, *, actor=""):
    """Edit live parent/household details after approval, including login email."""
    if not family:
        raise ValueError("Family not found.")

    email = _normalize_member_email(data.get("primary_email"))
    family_name = (data.get("family_name") or family.name or "").strip()
    if not family_name:
        raise ValueError("Enter a family name.")
    primary_first = (data.get("primary_first_name") or "").strip()
    primary_last = (data.get("primary_last_name") or "").strip()
    contact = f"{primary_first} {primary_last}".strip() or family.primary_contact
    primary_phone = (data.get("primary_phone") or "").strip()
    home_address = (data.get("home_address") or "").strip()
    secondary_first = (data.get("secondary_first_name") or "").strip()
    secondary_last = (data.get("secondary_last_name") or "").strip()
    secondary_phone = (data.get("secondary_phone") or "").strip()
    secondary_email = (data.get("secondary_email") or "").strip().lower()
    if secondary_email:
        secondary_email = _normalize_member_email(secondary_email)

    before = member_info_for_family(family)
    account = PortalParentAccount.objects.filter(family=family).select_related("user").first()
    if _email_in_use(email, exclude_user=account.user if account else None):
        raise ValueError("That email is already used by another portal login.")
    _sync_parent_login_email(family, email, first_name=primary_first, last_name=primary_last)

    family_updates = []
    if family.name != family_name:
        family.name = family_name
        family_updates.append("name")
    if contact and family.primary_contact != contact:
        family.primary_contact = contact
        family_updates.append("primary_contact")
    if family_updates:
        family.save(update_fields=family_updates)

    app_fields = {
        "family_name": family_name,
        "primary_email": email,
        "primary_email_address": email,
        "primary_first_name": primary_first or None,
        "primary_last_name": primary_last or None,
        "primary_phone": primary_phone or None,
        "home_address": home_address or None,
        "secondary_first_name": secondary_first,
        "secondary_last_name": secondary_last,
        "secondary_phone": secondary_phone,
        "secondary_email_address": secondary_email,
    }
    applications = list(EnrollmentApplication.objects.filter(portal_family=family))
    for app in applications:
        changed = []
        for field, value in app_fields.items():
            if value is None:
                continue
            if getattr(app, field) != value:
                setattr(app, field, value)
                changed.append(field)
        if changed:
            app.save(update_fields=changed)

    after = member_info_for_family(family)
    tracked = [
        "family_name",
        "home_address",
        "primary_first_name",
        "primary_last_name",
        "primary_email",
        "primary_phone",
        "secondary_first_name",
        "secondary_last_name",
        "secondary_email",
        "secondary_phone",
    ]
    changes = {}
    for key in tracked:
        old = (before or {}).get(key) or ""
        new = (after or {}).get(key) or ""
        if old != new:
            changes[key] = {"from": old, "to": new}
    _record_member_info_change(family, changes, actor=actor)
    return after, changes


def _parse_amount(value):
    try:
        amount = Decimal(str(value).replace(",", "").strip())
    except (InvalidOperation, TypeError):
        raise ValueError("Enter a valid dollar amount.")
    if amount <= 0:
        raise ValueError("Amount must be greater than zero.")
    return amount.quantize(Decimal("0.01"))


def add_prior_balance(name, amount, child_name="", notes=""):
    return PortalPriorBalance.objects.create(
        name=(name or "").strip(),
        child_name=(child_name or "").strip(),
        amount=_parse_amount(amount),
        notes=(notes or "").strip(),
    )


@transaction.atomic
def link_prior_balance(balance_id, family):
    from .billing_services import post_charge

    balance = PortalPriorBalance.objects.filter(pk=balance_id).first()
    if not balance:
        raise ValueError("Collection record not found.")
    if balance.linked_family_id:
        raise ValueError("That balance is already linked to a family.")
    description = f"Prior balance — {balance.name}"
    if balance.child_name:
        description = f"{description} ({balance.child_name})"
    post_charge(
        family,
        balance.child_name,
        "prior_balance",
        balance.amount,
        timezone.localdate(),
        description,
        is_manual=True,
    )
    balance.linked_family = family
    balance.linked_at = timezone.now()
    balance.save(update_fields=["linked_family", "linked_at"])
    return balance


def matching_prior_balances(family):
    if not family:
        return []
    tokens = {part.lower() for part in family.name.split() if len(part) > 2}
    if family.primary_contact:
        tokens.update(part.lower() for part in family.primary_contact.split() if len(part) > 2)
    unmatched = PortalPriorBalance.objects.filter(linked_family__isnull=True)
    matches = []
    for row in unmatched:
        hay = f"{row.name} {row.child_name}".lower()
        if any(token in hay for token in tokens):
            matches.append(row)
    return matches


@transaction.atomic
def suspend_family(family, reason, note=""):
    reason = (reason or "other").strip()
    valid = {key for key, _ in SUSPEND_REASONS}
    if reason not in valid:
        reason = "other"
    family.is_suspended = True
    family.suspend_reason = reason
    family.suspend_note = (note or "").strip()
    family.suspended_at = timezone.now()
    if family.status != "Suspended":
        family.status = "Suspended"
    family.save(update_fields=["is_suspended", "suspend_reason", "suspend_note", "suspended_at", "status"])
    reason_label = dict(SUSPEND_REASONS).get(reason, "program policy")
    email = parent_email_for_family(family)
    children = ", ".join(child.name for child in family.children.filter(is_active=True)) or "your child"
    extra = f"\n\nNote: {family.suspend_note}" if family.suspend_note else ""
    sent = False
    if email:
        sent = bool(
            send_site_email(
                subject=f"Program suspension — {family.name}",
                message=(
                    f"Hello,\n\n"
                    f"{children} has been suspended from Youth Education Academy programming "
                    f"until the account balance is satisfied or this matter is resolved.\n\n"
                    f"Reason: {reason_label}.{extra}\n\n"
                    f"Please sign in to the parent portal to view your balance and make a payment, "
                    f"or contact us at info@yeanj.org / 609-357-8608.\n\n"
                    f"Youth Education Academy\n"
                ),
                recipient_list=[email],
            )
        )
    return sent


@transaction.atomic
def unsuspend_family(family):
    family.is_suspended = False
    family.suspend_reason = ""
    family.suspend_note = ""
    family.suspended_at = None
    if family.status == "Suspended":
        family.status = "Active"
    family.save(update_fields=["is_suspended", "suspend_reason", "suspend_note", "suspended_at", "status"])
    return family


def families_without_applications():
    return PortalFamily.objects.filter(enrollment_applications__isnull=True).select_related("unit").distinct()


def applications_without_accounts():
    return EnrollmentApplication.objects.filter(portal_family__isnull=True).order_by("-submitted_at")


def families_without_parent_login():
    return PortalFamily.objects.filter(parent_account__isnull=True).select_related("unit").order_by("name")


@transaction.atomic
def create_parent_account_for_family(family, username, password, email=""):
    if PortalParentAccount.objects.filter(family=family).exists():
        raise ValueError("This family already has a parent portal login.")
    email = (email or parent_email_for_family(family) or "").strip()
    User = get_user_model()
    stored = allocate_portal_username("parent", username.strip())
    user = User.objects.create_user(
        username=stored,
        email=email,
        password=password,
        first_name=(family.primary_contact or family.name).split()[0],
        last_name=" ".join((family.primary_contact or family.name).split()[1:]),
    )
    PortalParentAccount.objects.create(user=user, family=family)
    return display_username(stored), password


@transaction.atomic
def create_account_from_application(application, username, password):
    from enrollment.locations import get_unit_for_enrollment_key
    from enrollment.portal_integration import link_applications_to_family

    if application.portal_family_id and PortalParentAccount.objects.filter(family=application.portal_family).exists():
        raise ValueError("This application already has a parent portal login.")

    unit = get_unit_for_enrollment_key(application.program_location)
    if not unit or is_placeholder_unit(unit):
        unit = program_units()[0] if program_units() else PortalUnit.objects.filter(is_active=True).first()
    if not unit:
        raise ValueError("No program unit is set up yet.")

    family = application.portal_family
    if not family:
        family = PortalFamily.objects.create(
            unit=unit,
            slug=_unique_family_slug(unit, application.family_name or "Family"),
            name=application.family_name or "Family",
            primary_contact=f"{application.primary_first_name} {application.primary_last_name}".strip(),
            billing_type=PAYMENT_TO_BILLING_TYPE.get(application.payment_method, "Private pay"),
            program_label=application.get_program_display(),
            status="Pending enrollment",
        )
        link_applications_to_family([application], family)
    login_name, _ = create_parent_account_for_family(
        family,
        username,
        password,
        email=application.primary_email,
    )
    return family, login_name


@transaction.atomic
def delete_family_record(family):
    label = f"{family.name} ({family.unit.name})"
    account = PortalParentAccount.objects.filter(family=family).select_related("user").first()
    EnrollmentApplication.objects.filter(portal_family=family).update(portal_family=None)
    if account:
        user = account.user
        account.delete()
        user.delete()
    family.delete()
    return label


def delete_application_record(application):
    label = f"{application.student_first_name} {application.student_last_name}".strip()
    application.delete()
    return label


def parent_email_recipients():
    rows = []
    seen = set()
    for family in PortalFamily.objects.select_related("unit", "parent_account__user").order_by("name"):
        email = parent_email_for_family(family)
        if not email or email.lower() in seen:
            continue
        seen.add(email.lower())
        rows.append(
            {
                "family_id": family.pk,
                "family": family_display_label(family),
                "unit": family.unit.name,
                "email": email,
                "suspended": family.is_suspended,
            }
        )
    for app in applications_without_accounts():
        email = (app.primary_email or "").strip()
        if not email or email.lower() in seen:
            continue
        seen.add(email.lower())
        rows.append(
            {
                "family_id": f"app-{app.pk}",
                "family": f"{app.family_name} (application only)",
                "unit": app.program_location.replace("_", " ").title(),
                "email": email,
                "suspended": False,
            }
        )
    return rows


def send_parent_emails(
    subject,
    body,
    emails,
    reply_to=None,
    attachments=None,
    *,
    family=None,
    unit=None,
    sender=None,
    source=None,
):
    from .models import PortalParentEmail
    from .parent_email_log import record_sent_parent_email

    subject = (subject or "").strip()
    body = (body or "").strip()
    if not subject or not body:
        raise ValueError("Enter a subject and message.")
    unique = []
    seen = set()
    for email in emails:
        cleaned = (email or "").strip()
        if cleaned and cleaned.lower() not in seen:
            seen.add(cleaned.lower())
            unique.append(cleaned)
    if not unique:
        raise ValueError("Choose at least one parent.")
    sent = 0
    delivered = []
    replies = [reply_to] if reply_to else None
    for email in unique:
        if send_site_email(
            subject=subject,
            message=body,
            recipient_list=[email],
            reply_to=replies,
            attachments=attachments,
        ):
            sent += 1
            delivered.append(email)
    if delivered:
        record_sent_parent_email(
            subject=subject,
            body=body,
            recipients=delivered,
            attachments=attachments,
            family=family,
            unit=unit,
            sender=sender,
            source=source or (
                PortalParentEmail.SOURCE_FAMILY if family else PortalParentEmail.SOURCE_BULK
            ),
        )
    return sent, len(unique)


def send_family_parent_email(family, subject, body, reply_to=None, attachments=None, sender=None):
    from .models import PortalParentEmail

    email = parent_email_for_family(family)
    if not email:
        raise ValueError("This family does not have a parent email on file.")
    return send_parent_emails(
        subject,
        body,
        [email],
        reply_to=reply_to,
        attachments=attachments,
        family=family,
        unit=getattr(family, "unit", None),
        sender=sender,
        source=PortalParentEmail.SOURCE_FAMILY,
    )


def save_discount_plan(name, kind, value, description="", plan_id=None):
    amount = _parse_amount(value)
    kind = kind if kind in {PortalDiscountPlan.KIND_AMOUNT, PortalDiscountPlan.KIND_PERCENT} else PortalDiscountPlan.KIND_AMOUNT
    if plan_id:
        plan = PortalDiscountPlan.objects.filter(pk=plan_id).first()
        if not plan:
            raise ValueError("Discount plan not found.")
        plan.name = name.strip()
        plan.kind = kind
        plan.value = amount
        plan.description = description.strip()
        plan.save()
        return plan
    return PortalDiscountPlan.objects.create(
        name=name.strip(),
        kind=kind,
        value=amount,
        description=description.strip(),
    )


@transaction.atomic
def apply_discount_to_family(family, plan_id, child_name=""):
    from .billing_services import post_credit

    plan = PortalDiscountPlan.objects.filter(pk=plan_id, is_active=True).first()
    if not plan:
        raise ValueError("Choose an active discount plan.")
    assignment = PortalDiscountAssignment.objects.create(
        family=family,
        plan=plan,
        child_name=(child_name or "").strip(),
    )
    label = f"Discount — {plan.name}"
    if child_name:
        label = f"{label} ({child_name})"
    if plan.kind == PortalDiscountPlan.KIND_PERCENT:
        child = family.children.filter(name=child_name).first() if child_name else family.children.filter(is_active=True).first()
        base = Decimal("0")
        if child and child.billing_amount:
            base = child.billing_amount
        elif family.balance > 0:
            base = family.balance
        credit_amount = (base * plan.value / Decimal("100")).quantize(Decimal("0.01"))
        if credit_amount <= 0:
            raise ValueError("Percent discounts need a child plan amount or a family balance to calculate from.")
    else:
        credit_amount = plan.value
    post_credit(family, child_name, credit_amount, timezone.localdate(), label)
    return assignment


def member_reports():
    from .unit_visibility import child_effective_unit, unit_label_for_child

    children = PortalChild.objects.filter(is_active=True).select_related("family", "family__unit", "unit")
    rows = []
    for child in children:
        child_unit = child_effective_unit(child)
        if is_placeholder_unit(child_unit or child.family.unit):
            continue
        app = (
            EnrollmentApplication.objects.filter(portal_family=child.family, student_first_name__iexact=child.name.split()[0])
            .order_by("-submitted_at")
            .first()
        )
        school = child.school or (app.student_school if app else "")
        billing = (child.family.billing_type or "Private pay").strip() or "Private pay"
        plan = displayed_payment_plan(child, app) or "Weekly"
        unit_name, _unit_slug = unit_label_for_child(child)
        rows.append(
            {
                "child": child.name,
                "family": child.family.name,
                "unit": unit_name or child.family.unit.name,
                "school": school or "—",
                "billing": billing,
                "plan": plan,
                "status": "Suspended" if child.family.is_suspended else child.family.status,
                "family_slug": child.family.slug,
                "family_id": child.family_id,
            }
        )
    return rows


def applications_for_family_admin(family):
    linked = list(
        EnrollmentApplication.objects.filter(portal_family=family)
        .select_related("portal_family")
        .prefetch_related("emergency_contacts")
        .order_by("-submitted_at")
    )
    seen = {app.pk for app in linked}
    extras = []
    email = parent_email_for_family(family)
    if email:
        extras = list(
            EnrollmentApplication.objects.filter(primary_email__iexact=email)
            .exclude(pk__in=seen)
            .order_by("-submitted_at")
        )
    if family.name:
        extras += list(
            EnrollmentApplication.objects.filter(family_name__iexact=family.name, portal_family__isnull=True)
            .exclude(pk__in=seen | {app.pk for app in extras})
            .order_by("-submitted_at")
        )
    return linked, extras


def link_application_to_family(application, family):
    application.portal_family = family
    application.save(update_fields=["portal_family"])
    return application


@transaction.atomic
def update_application_fields(application, data):
    from enrollment.application_review import assign_application_location

    old_name = f"{application.student_first_name} {application.student_last_name}".strip()
    old_location = application.program_location
    fields = [
        "family_name",
        "primary_email",
        "home_address",
        "primary_first_name",
        "primary_last_name",
        "primary_phone",
        "student_first_name",
        "student_last_name",
        "student_school",
        "student_grade",
        "student_dob",
        "program",
        "payment_method",
        "payment_method_other",
        "payment_plan",
        "allergies",
        "medical_condition_explain",
        "doctor_name",
        "doctor_phone",
        "insurance_provider",
        "secondary_first_name",
        "secondary_last_name",
        "secondary_phone",
        "secondary_email_address",
    ]
    for field in fields:
        if field not in data:
            continue
        value = data[field]
        if field == "student_dob" and not value:
            continue
        setattr(application, field, value)
    if application.payment_method == "other" and not (application.payment_method_other or "").strip():
        raise ValueError("Specify what Other payment method means.")
    application.save()

    new_location = (data.get("program_location") or "").strip()
    if new_location and new_location != old_location:
        assign_application_location(application, new_location)

    family = application.portal_family
    if family:
        new_name = f"{application.student_first_name} {application.student_last_name}".strip()
        child = family.children.filter(name__iexact=old_name).first()
        if child:
            child.name = new_name
            child.school = application.student_school or child.school
            child.grade = application.get_student_grade_display()
            child.save(update_fields=["name", "school", "grade"])
        updates = []
        if application.family_name and family.name != application.family_name:
            family.name = application.family_name
            updates.append("name")
        contact = f"{application.primary_first_name} {application.primary_last_name}".strip()
        if contact and family.primary_contact != contact:
            family.primary_contact = contact
            updates.append("primary_contact")
        billing_type = PAYMENT_TO_BILLING_TYPE.get(application.payment_method, family.billing_type)
        if billing_type and family.billing_type != billing_type:
            family.billing_type = billing_type
            updates.append("billing_type")
        program_label = application.get_program_display()
        if program_label and family.program_label != program_label:
            family.program_label = program_label
            updates.append("program_label")
        if updates:
            family.save(update_fields=updates)
        new_email = (application.primary_email or "").strip().lower()
        if new_email:
            application.primary_email_address = new_email
            application.save(update_fields=["primary_email_address"])
            _sync_parent_login_email(
                family,
                new_email,
                first_name=application.primary_first_name,
                last_name=application.primary_last_name,
            )
    return application


def _normalize_school_name(school):
    school = (school or "").strip()
    if not school:
        raise ValueError("Enter a school name.")
    if len(school) > 120:
        raise ValueError("School name is too long.")
    return school


def update_child_school(*, child=None, application=None, school):
    """Set the child's daytime school and keep the enrollment application in sync."""
    from .medical import application_for_child

    school = _normalize_school_name(school)
    if child:
        child.school = school
        child.save(update_fields=["school"])
        app = application or application_for_child(child=child, child_name=child.name)
        if app:
            app.student_school = school
            app.save(update_fields=["student_school"])
        return child

    if application:
        application.student_school = school
        application.save(update_fields=["student_school"])
        family = application.portal_family
        if family:
            child_name = f"{application.student_first_name} {application.student_last_name}".strip()
            linked = family.children.filter(name__iexact=child_name).first()
            if linked:
                linked.school = school
                linked.save(update_fields=["school"])
        return application

    raise ValueError("Child not found.")


def rename_children_school(child_ids, school, unit=None):
    school = _normalize_school_name(school)
    children = PortalChild.objects.filter(pk__in=child_ids, is_active=True).select_related("family")
    if unit:
        from .unit_visibility import child_unit_q

        children = children.filter(child_unit_q(unit))
    updated = 0
    for child in children:
        update_child_school(child=child, school=school)
        updated += 1
    return updated


def known_school_names(unit=None):
    names = set()
    children = PortalChild.objects.filter(is_active=True)
    applications = EnrollmentApplication.objects.exclude(student_school="")
    if unit:
        from .unit_visibility import child_unit_q
        from enrollment.locations import enrollment_keys_for_unit

        children = children.filter(child_unit_q(unit))
        applications = applications.filter(program_location__in=enrollment_keys_for_unit(unit))
    names.update(name.strip() for name in children.exclude(school="").values_list("school", flat=True) if name.strip())
    names.update(
        name.strip() for name in applications.values_list("student_school", flat=True) if name.strip()
    )
    return sorted(names, key=str.lower)


def pending_4cs_children(unit=None):
    from .models import PortalAgencyProfile

    qs = PortalChild.objects.filter(is_active=True, family__billing_type__iexact="4Cs").select_related("family", "family__unit")
    if unit:
        from .unit_visibility import child_unit_q

        qs = qs.filter(child_unit_q(unit))
    profiled = set(PortalAgencyProfile.objects.values_list("child_id", flat=True))
    return [child for child in qs if child.id not in profiled]
