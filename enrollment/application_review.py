"""Staff review actions for enrollment applications."""

import logging
from decimal import Decimal

from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from portal.fee_config import get_fee_amount, get_fee_display
from portal.models import PortalChild, PortalFamily, PortalLedgerEntry

from .application_edit import EDITABLE_STATUSES
from .locations import get_enrollment_location_choices, get_location_label, get_unit_for_enrollment_key, unit_allows_program
from .models import EnrollmentApplication

logger = logging.getLogger(__name__)

MEMBERSHIP_FEE_KEY = "membership"
DEFAULT_MEMBERSHIP_FEE = Decimal("20.00")
REVIEWABLE_STATUSES = {"under_review", "pending_documents", "waitlist"}


def child_display_name(app):
    return f"{app.student_first_name} {app.student_last_name}".strip()


def _portal_applications_url():
    return settings.SITE_URL.rstrip("/") + reverse("portal_parent_page", kwargs={"page": "applications"})


def _application_detail_url(app):
    return (
        settings.SITE_URL.rstrip("/")
        + reverse("portal_parent_page", kwargs={"page": "application"})
        + f"?ref={app.reference}"
    )


def _email_parent(app, subject, body):
    try:
        send_mail(
            subject=subject,
            message=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[app.primary_email],
            fail_silently=False,
        )
    except Exception:
        logger.exception("Failed to email parent about application %s", app.reference)


def _ensure_child_on_roster(app):
    family = app.portal_family
    if not family:
        return None

    name = child_display_name(app)
    child = family.children.filter(name__iexact=name).first()
    if child:
        fields = []
        if not child.is_active:
            child.is_active = True
            fields.append("is_active")
        if app.student_school and not child.school:
            child.school = app.student_school
            fields.append("school")
        if fields:
            child.save(update_fields=fields)
        return child

    return PortalChild.objects.create(
        family=family,
        name=name,
        grade=app.get_student_grade_display(),
        school=app.student_school or "",
        is_active=True,
    )


def _membership_fee_amount():
    return get_fee_amount(MEMBERSHIP_FEE_KEY, DEFAULT_MEMBERSHIP_FEE)


def _post_membership_fee_if_needed(app):
    family = app.portal_family
    if not family or app.membership_fee_agreed != "yes":
        return

    amount = _membership_fee_amount()
    if not amount:
        return

    child_name = child_display_name(app)
    label = get_fee_display(MEMBERSHIP_FEE_KEY, f"${amount}")
    description = f"Membership fee ({label}) — {child_name}"
    if PortalLedgerEntry.objects.filter(family=family, description=description).exists():
        return

    family.balance += amount
    family.save(update_fields=["balance"])
    PortalLedgerEntry.objects.create(
        family=family,
        child_name=child_name,
        date=timezone.localdate(),
        entry_type="membership",
        description=description,
        amount=amount,
        is_manual=False,
    )


def _activate_family_if_needed(family):
    if family and family.status == "Pending enrollment":
        family.status = "Active"
        family.save(update_fields=["status"])


def _move_family_to_unit(family, unit):
    from .portal_integration import _unique_family_slug

    if not family or not unit or family.unit_id == unit.id:
        return family
    new_slug = family.slug
    if PortalFamily.objects.filter(unit=unit, slug=family.slug).exclude(pk=family.pk).exists():
        new_slug = _unique_family_slug(unit, family.name)
    family.unit = unit
    family.slug = new_slug
    family.save(update_fields=["unit", "slug"])
    return family


def _sync_family_to_application_unit(app):
    """Keep the family account on the same program site as the application."""
    from portal.member_admin import is_placeholder_unit

    family = app.portal_family
    if not family or not app.program_location:
        return family
    unit = get_unit_for_enrollment_key(app.program_location)
    if not unit or is_placeholder_unit(unit):
        return family
    return _move_family_to_unit(family, unit)


def preferred_application_for_family(family):
    apps = list(
        EnrollmentApplication.objects.filter(portal_family=family)
        .exclude(program_location="")
        .exclude(status="declined")
        .order_by("-reviewed_at", "-submitted_at")
    )
    if not apps:
        return None
    for status in ("enrolled", "approved", "under_review", "pending_documents", "waitlist"):
        match = next((row for row in apps if row.status == status), None)
        if match:
            return match
    return apps[0]


def repair_family_units_from_applications():
    """Move family accounts off Main location (or the wrong site) onto the application site."""
    from portal.member_admin import is_placeholder_unit

    moved = 0
    for family in PortalFamily.objects.select_related("unit"):
        app = preferred_application_for_family(family)
        if not app:
            continue
        unit = get_unit_for_enrollment_key(app.program_location)
        if not unit or is_placeholder_unit(unit):
            continue
        if family.unit_id == unit.id:
            continue
        _move_family_to_unit(family, unit)
        moved += 1
    return moved


@transaction.atomic
def assign_application_location(app, program_location):
    program_location = (program_location or "").strip()
    valid_keys = {key for key, _ in get_enrollment_location_choices()}
    if not program_location:
        raise ValueError("Choose a location before saving.")
    if program_location not in valid_keys:
        raise ValueError("Choose a valid location from the list.")

    unit = get_unit_for_enrollment_key(program_location)
    if not unit:
        raise ValueError("That location is not set up in the portal yet.")
    if not unit_allows_program(unit, app.program):
        raise ValueError(
            f"{unit.name} is not available for {app.get_program_display().lower()}."
        )

    app.program_location = program_location
    app.needs_dale_ave_bus = program_location == "dale_ave"
    app.save(update_fields=["program_location", "needs_dale_ave_bus"])

    family = app.portal_family
    if family and family.unit_id != unit.id:
        _move_family_to_unit(family, unit)
        sibling_updates = {
            "program_location": program_location,
            "needs_dale_ave_bus": app.needs_dale_ave_bus,
        }
        EnrollmentApplication.objects.filter(portal_family=family).exclude(pk=app.pk).update(**sibling_updates)

    return app


@transaction.atomic
def approve_application(app, program_location=None):
    if app.status not in REVIEWABLE_STATUSES:
        raise ValueError("This application has already been reviewed.")

    if program_location and program_location.strip() != (app.program_location or ""):
        assign_application_location(app, program_location.strip())
        app.refresh_from_db()
    else:
        _sync_family_to_application_unit(app)

    _ensure_child_on_roster(app)
    _post_membership_fee_if_needed(app)
    if app.portal_family:
        _activate_family_if_needed(app.portal_family)
        from enrollment.portal_integration import PAYMENT_TO_BILLING_TYPE

        billing_type = PAYMENT_TO_BILLING_TYPE.get(app.payment_method, app.portal_family.billing_type)
        updates = []
        if billing_type and app.portal_family.billing_type != billing_type:
            app.portal_family.billing_type = billing_type
            updates.append("billing_type")
        if app.get_program_display() and not app.portal_family.program_label:
            app.portal_family.program_label = app.get_program_display()
            updates.append("program_label")
        if updates:
            app.portal_family.save(update_fields=updates)

    app.status = "approved"
    app.reviewed_at = timezone.now()
    app.save(update_fields=["status", "reviewed_at"])

    child_name = child_display_name(app)
    _email_parent(
        app,
        f"Enrollment approved — {child_name}",
        (
            f"Hi {app.primary_first_name},\n\n"
            f"Great news — {child_name}'s enrollment application for {app.get_program_display()} "
            f"at {get_location_label(app.program_location)} has been approved.\n\n"
            f"Sign in to your parent portal to view billing and your family profile:\n"
            f"{_portal_applications_url()}\n\n"
            f"Youth Education Academy"
        ),
    )
    return app


@transaction.atomic
def request_application_changes(app, message):
    message = (message or "").strip()
    if not message:
        raise ValueError("Describe what the family needs to update before sending.")
    if app.status == "declined":
        raise ValueError("This application was declined and cannot be updated here.")

    app.status = "pending_documents"
    app.staff_message = message
    app.reviewed_at = timezone.now()
    app.save(update_fields=["status", "staff_message", "reviewed_at"])

    _email_parent(
        app,
        f"Action needed on your enrollment application — {child_display_name(app)}",
        (
            f"Hi {app.primary_first_name},\n\n"
            f"We reviewed {child_display_name(app)}'s enrollment application and need a few updates "
            f"before we can approve it:\n\n"
            f"{message}\n\n"
            f"View this message in your parent portal:\n"
            f"{_application_detail_url(app)}\n\n"
            f"Reply through portal Support or contact the office if you have questions.\n\n"
            f"Youth Education Academy"
        ),
    )
    return app


@transaction.atomic
def reject_application(app, message=""):
    if app.status in {"declined", "approved", "enrolled"}:
        raise ValueError("This application has already been finalized.")

    message = (message or "").strip()
    app.status = "declined"
    app.staff_message = message
    app.reviewed_at = timezone.now()
    app.save(update_fields=["status", "staff_message", "reviewed_at"])

    body = (
        f"Hi {app.primary_first_name},\n\n"
        f"Thank you for applying to Youth Education Academy for {child_display_name(app)}. "
        f"After review, we are unable to approve this application at this time.\n\n"
    )
    if message:
        body += f"Note from our team:\n{message}\n\n"
    body += (
        f"If you have questions, please contact us through the office.\n\n"
        f"Youth Education Academy"
    )
    _email_parent(app, f"Enrollment application update — {child_display_name(app)}", body)
    return app


def save_internal_note(app, note):
    app.internal_note = (note or "").strip()
    app.save(update_fields=["internal_note"])
    return app


def resubmit_application(app):
    if app.status not in EDITABLE_STATUSES:
        raise ValueError("This application is not open for editing.")

    app.status = "under_review"
    app.staff_message = ""
    app.reviewed_at = None
    app.save(update_fields=["status", "staff_message", "reviewed_at"])

    child_name = child_display_name(app)
    staff_url = (
        settings.SITE_URL.rstrip("/")
        + reverse("portal_staff_application_detail", kwargs={"app_slug": str(app.reference)})
    )
    try:
        send_mail(
            subject=f"[YEA] Application updated — {child_name}",
            message=(
                f"A family resubmitted an enrollment application after your change request.\n\n"
                f"Student: {child_name}\n"
                f"Family: {app.family_name}\n"
                f"Email: {app.primary_email}\n"
                f"Reference: {app.reference}\n\n"
                f"Review in the staff portal:\n{staff_url}\n"
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[
                email.strip()
                for email in settings.ENROLLMENT_NOTIFICATION_EMAIL.split(",")
                if email.strip()
            ],
            fail_silently=False,
        )
    except Exception:
        logger.exception("Failed to notify staff about resubmitted application %s", app.reference)

    _email_parent(
        app,
        f"Application resubmitted — {child_name}",
        (
            f"Hi {app.primary_first_name},\n\n"
            f"Thanks — we received your updated enrollment application for {child_name}. "
            f"Our team will review it again and email you when there's an update.\n\n"
            f"Track status in your parent portal:\n"
            f"{_portal_applications_url()}\n\n"
            f"Youth Education Academy"
        ),
    )
    return app
