"""Staff-initiated enrollment applications."""

import uuid
from datetime import date

from django.conf import settings
from django.utils.text import slugify

from enrollment.models import EnrollmentApplication
from enrollment.portal_integration import link_applications_by_email

from portal.models import PortalFamily, PortalUnit


GRADE_MAP = {
    "pre_k": "pre_k",
    "kindergarten": "kindergarten",
    "k": "kindergarten",
    "1st": "1",
    "2nd": "2",
    "3rd": "3",
    "4th": "4",
    "5th": "5",
    "6th": "6",
    "7th": "7",
    "8th": "8",
}


def _program_location_for_unit(unit):
    from enrollment.locations import enrollment_key_for_unit

    return enrollment_key_for_unit(unit)


def _split_name(full_name):
    parts = (full_name or "").strip().split()
    if not parts:
        return "Parent", "Guardian"
    if len(parts) == 1:
        return parts[0], parts[0]
    return parts[0], " ".join(parts[1:])


def create_staff_application(form, unit):
    family_name = form["family_name"].strip()
    parent_first, parent_last = _split_name(form["primary_parent_name"])
    email = form["email"].strip().lower()
    phone = form["phone"].strip()
    address = form["home_address"].strip()
    student_first = form["student_first_name"].strip()
    student_last = form["student_last_name"].strip()
    grade = GRADE_MAP.get(form["grade"].strip().lower(), form["grade"].strip())
    payment_method = form.get("payment_method", "private_pay")
    if payment_method == "4Cs":
        payment_method = "4cs"
    returning = form.get("returning_member") == "yes"
    save_draft = form.get("action") == "draft"
    today = date.today()

    portal_family = _get_or_create_family(unit, family_name, parent_first, parent_last, email, payment_method)

    app = EnrollmentApplication.objects.create(
        family_group=uuid.uuid4(),
        child_number=1,
        program="after_school",
        program_location=_program_location_for_unit(unit),
        family_name=family_name,
        primary_email=email,
        home_address=address or "Address pending",
        primary_first_name=parent_first,
        primary_last_name=parent_last,
        primary_gender="female",
        primary_language="english",
        primary_relationship="guardian",
        primary_phone=phone or "000-000-0000",
        primary_phone_type="cell",
        primary_text_subscription="no",
        primary_email_subscription="yes",
        primary_email_address=email,
        primary_authorized_pickup="yes",
        student_first_name=student_first,
        student_last_name=student_last,
        student_gender="female",
        student_dob=form.get("student_dob") or today.replace(year=today.year - 8),
        student_language="english",
        student_ethnicity="unknown",
        student_race="unknown",
        student_grade=grade,
        student_school=unit.name if unit else "School 18",
        no_known_allergies=True,
        allergies="",
        health_statement="good_health",
        membership_fee_agreed="no" if returning else "yes",
        payment_method=payment_method,
        payment_plan="weekly",
        payment_plan_signature=f"{parent_first} {parent_last}".strip(),
        payment_plan_signed_date=today,
        status="pending_documents" if save_draft else "under_review",
        internal_note="Created by staff on behalf of family.",
        portal_family=portal_family,
    )
    link_applications_by_email(portal_family, email)
    return app


def _get_or_create_family(unit, family_name, parent_first, parent_last, email, payment_method):
    billing_type = {"4cs": "4Cs", "private_pay": "Private pay"}.get(payment_method, "Private pay")
    existing = PortalFamily.objects.filter(unit=unit, primary_contact__icontains=parent_last).first()
    if existing:
        return existing
    base_slug = slugify(family_name) or "family"
    slug = base_slug
    suffix = 2
    while PortalFamily.objects.filter(unit=unit, slug=slug).exists():
        slug = f"{base_slug}-{suffix}"
        suffix += 1
    return PortalFamily.objects.create(
        unit=unit,
        slug=slug,
        name=family_name,
        primary_contact=f"{parent_first} {parent_last}".strip(),
        balance=0,
        billing_type=billing_type,
        program_label="After-School 2026–27",
        status="Active",
    )
