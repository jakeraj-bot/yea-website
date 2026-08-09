"""Enrollment application email notifications."""

from django.conf import settings
from django.urls import reverse

from core.email_service import send_site_email

from .models import EnrollmentApplication


def notify_staff_new_application(application):
    print_url = settings.SITE_URL.rstrip("/") + reverse(
        "enrollment_print", args=[application.reference]
    )
    staff_url = settings.SITE_URL.rstrip("/") + reverse(
        "portal_staff_application_detail", kwargs={"app_slug": str(application.reference)}
    )
    admin_url = settings.SITE_URL.rstrip("/") + reverse(
        "portal_admin_page", kwargs={"page": "applications"}
    )
    subject = f"[YEA] New enrollment application — {application.student_first_name} {application.student_last_name}"
    sibling_note = ""
    if application.family_group:
        sibling_count = EnrollmentApplication.objects.filter(
            family_group=application.family_group
        ).count()
        if sibling_count > 1:
            sibling_note = f"Child {application.child_number} of {sibling_count} in this family submission.\n"
    source = "submitted online"
    if application.internal_note and "Created by staff" in application.internal_note:
        source = "created by staff"
    body = (
        f"A new enrollment application was {source}.\n\n"
        f"{sibling_note}"
        f"Student: {application.student_first_name} {application.student_last_name}\n"
        f"Program: {application.get_program_display()} — {application.get_program_location_display()}\n"
        f"Family: {application.family_name}\n"
        f"Family email: {application.primary_email}\n"
        f"Reference: {application.reference}\n\n"
        f"Review in staff portal:\n{staff_url}\n\n"
        f"Admin applications list:\n{admin_url}\n\n"
        f"Print for your files (staff login required):\n{print_url}\n"
    )
    recipients = [
        email.strip()
        for email in settings.ENROLLMENT_NOTIFICATION_EMAIL.split(",")
        if email.strip()
    ]
    return bool(
        send_site_email(
            subject=subject,
            message=body,
            recipient_list=recipients,
        )
    )


def notify_parent_application_received(application, *, staff_created=False, save_draft=False):
    portal_url = settings.SITE_URL.rstrip("/") + reverse("portal_parent_login")
    child_name = f"{application.student_first_name} {application.student_last_name}".strip()

    if save_draft:
        subject = "[YEA] Complete your enrollment application"
        body = (
            f"Hello {application.primary_first_name},\n\n"
            f"YEA staff started an enrollment application for {child_name}. "
            f"Please sign in to the parent portal to complete medical information, policies, and billing.\n\n"
            f"Reference: {application.reference}\n\n"
            f"Parent portal:\n{portal_url}\n\n"
            f"Youth Education Academy\n"
        )
    elif staff_created:
        subject = f"[YEA] Application received — {child_name}"
        body = (
            f"Hello {application.primary_first_name},\n\n"
            f"Your enrollment application for {child_name} has been submitted to Youth Education Academy.\n\n"
            f"Reference: {application.reference}\n"
            f"Program: {application.get_program_display()} — {application.get_program_location_display()}\n\n"
            f"We'll review your application and contact you if we need anything else. "
            f"Track status anytime in the parent portal:\n{portal_url}\n\n"
            f"Youth Education Academy\n"
        )
    else:
        subject = f"[YEA] Application received — {child_name}"
        body = (
            f"Hello {application.primary_first_name},\n\n"
            f"Thank you for submitting your enrollment application for {child_name}.\n\n"
            f"Reference: {application.reference}\n"
            f"Program: {application.get_program_display()} — {application.get_program_location_display()}\n\n"
            f"We'll review your application and contact you if we need anything else. "
            f"Track status anytime in the parent portal:\n{portal_url}\n\n"
            f"Youth Education Academy\n"
        )

    return bool(
        send_site_email(
            subject=subject,
            message=body,
            recipient_list=[application.primary_email],
        )
    )


def send_application_submitted_emails(application, *, staff_created=False, save_draft=False):
    """Notify staff and parent. Returns (staff_sent, parent_sent)."""
    staff_sent = notify_staff_new_application(application)
    parent_sent = notify_parent_application_received(
        application,
        staff_created=staff_created,
        save_draft=save_draft,
    )
    return staff_sent, parent_sent
