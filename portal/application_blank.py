"""Blank printable enrollment application for staff and admin reports."""

from django.urls import reverse
from django.utils import timezone

from enrollment.locations import get_enrollment_location_choices
from enrollment.models import EnrollmentApplication
from enrollment.policies_loader import get_policies


def blank_application_form_context():
    """Empty field/choice payload matching the live enrollment application."""
    return {
        "program_choices": EnrollmentApplication.PROGRAM_CHOICES,
        "location_choices": get_enrollment_location_choices(),
        "gender_choices": EnrollmentApplication.GENDER_CHOICES,
        "language_choices": EnrollmentApplication.LANGUAGE_CHOICES,
        "relationship_choices": EnrollmentApplication.RELATIONSHIP_CHOICES,
        "phone_type_choices": EnrollmentApplication.PHONE_TYPE_CHOICES,
        "yes_no_choices": EnrollmentApplication.YES_NO,
        "ethnicity_choices": EnrollmentApplication.ETHNICITY_CHOICES,
        "race_choices": EnrollmentApplication.RACE_CHOICES,
        "grade_choices": EnrollmentApplication.GRADE_CHOICES,
        "health_statement_choices": EnrollmentApplication.HEALTH_STATEMENT_CHOICES,
        "payment_method_choices": EnrollmentApplication.PAYMENT_METHOD_CHOICES,
        "payment_plan_choices": EnrollmentApplication.PAYMENT_PLAN_CHOICES,
        "policies": get_policies(),
        "emergency_contact_slots": [1, 2, 3],
    }


def blank_application_page_context(*, admin=False):
    extras = blank_application_form_context()
    if admin:
        extras["hub_url"] = reverse("portal_admin_page", kwargs={"page": "reports"})
        extras["hub_label"] = "Organization reports"
    else:
        extras["hub_url"] = reverse("portal_staff_page", kwargs={"page": "reports"})
        extras["hub_label"] = "Reports"
    extras["generated_date"] = timezone.localdate().strftime("%B %d, %Y")
    extras["page_guide_key"] = "application-blank"
    return extras
