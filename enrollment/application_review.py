"""Staff review actions for enrollment applications."""

import logging
from decimal import Decimal

from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from portal.models import PortalChild, PortalLedgerEntry

from .application_edit import EDITABLE_STATUSES

logger = logging.getLogger(__name__)

MEMBERSHIP_FEE = Decimal("20.00")
REVIEWABLE_STATUSES = {"under_review", "pending_documents"}


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
        if not child.is_active:
            child.is_active = True
            child.save(update_fields=["is_active"])
        return child

    return PortalChild.objects.create(
        family=family,
        name=name,
        grade=app.get_student_grade_display(),
        is_active=True,
    )


def _post_membership_fee_if_needed(app):
    family = app.portal_family
    if not family or app.membership_fee_agreed != "yes":
        return

    child_name = child_display_name(app)
    description = f"Membership fee — {child_name}"
    if PortalLedgerEntry.objects.filter(family=family, description=description).exists():
        return

    family.balance += MEMBERSHIP_FEE
    family.save(update_fields=["balance"])
    PortalLedgerEntry.objects.create(
        family=family,
        child_name=child_name,
        date=timezone.localdate(),
        entry_type="membership",
        description=description,
        amount=MEMBERSHIP_FEE,
        is_manual=False,
    )


def _activate_family_if_needed(family):
    if family and family.status == "Pending enrollment":
        family.status = "Active"
        family.save(update_fields=["status"])


@transaction.atomic
def approve_application(app):
    if app.status not in REVIEWABLE_STATUSES:
        raise ValueError("This application has already been reviewed.")

    _ensure_child_on_roster(app)
    _post_membership_fee_if_needed(app)
    if app.portal_family:
        _activate_family_if_needed(app.portal_family)

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
            f"at {app.get_program_location_display()} has been approved.\n\n"
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
            recipient_list=[settings.CONTACT_EMAIL],
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
