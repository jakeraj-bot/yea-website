"""Admin tools for collections, suspend, parent accounts, emails, and family cleanup."""

from decimal import Decimal, InvalidOperation

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from core.email_service import send_site_email
from enrollment.models import EnrollmentApplication
from enrollment.portal_integration import PAYMENT_TO_BILLING_TYPE, _unique_family_slug, family_display_label

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


def is_placeholder_unit(unit):
    if not unit:
        return True
    slug = (unit.slug or "").replace("_", "-").lower()
    name = (unit.name or "").strip().lower()
    return slug in PLACEHOLDER_UNIT_SLUGS or name in PLACEHOLDER_UNIT_NAMES


def program_units():
    return [unit for unit in PortalUnit.objects.filter(is_active=True).order_by("name") if not is_placeholder_unit(unit)]


def resolve_family(family_slug=None, family_id=None, unit=None):
    if family_id:
        family = PortalFamily.objects.filter(pk=family_id).select_related("unit").first()
        if family:
            if unit and family.unit_id != unit.pk:
                return None
            return family
    qs = PortalFamily.objects.select_related("unit")
    if family_slug:
        qs = qs.filter(slug=family_slug)
    if unit:
        qs = qs.filter(unit=unit)
    families = list(qs)
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


def send_parent_emails(subject, body, emails):
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
    for email in unique:
        sent += 1 if send_site_email(subject=subject, message=body, recipient_list=[email]) else 0
    return sent, len(unique)


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
    children = PortalChild.objects.filter(is_active=True).select_related("family", "family__unit")
    rows = []
    for child in children:
        if is_placeholder_unit(child.family.unit):
            continue
        app = (
            EnrollmentApplication.objects.filter(portal_family=child.family, student_first_name__iexact=child.name.split()[0])
            .order_by("-submitted_at")
            .first()
        )
        school = child.school or (app.student_school if app else "")
        billing = (child.family.billing_type or "Private pay").strip() or "Private pay"
        plan = child.billing_plan or (app.get_payment_plan_display() if app else "Weekly")
        rows.append(
            {
                "child": child.name,
                "family": child.family.name,
                "unit": child.family.unit.name,
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
    return application


def pending_4cs_children(unit=None):
    from .models import PortalAgencyProfile

    qs = PortalChild.objects.filter(is_active=True, family__billing_type__iexact="4Cs").select_related("family", "family__unit")
    if unit:
        qs = qs.filter(family__unit=unit)
    profiled = set(PortalAgencyProfile.objects.values_list("child_id", flat=True))
    return [child for child in qs if child.id not in profiled]
