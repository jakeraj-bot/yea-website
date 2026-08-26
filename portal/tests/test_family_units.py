from datetime import date

from django.test import TestCase

from enrollment.application_review import (
    approve_application,
    repair_family_units_from_applications,
)
from enrollment.models import EnrollmentApplication
from portal.admin_services import get_admin_families_live
from portal.models import PortalFamily, PortalUnit


def _make_application(family, *, location="school_18", status="approved"):
    return EnrollmentApplication.objects.create(
        program="after_school",
        program_location=location,
        family_name=family.name,
        primary_email="parent@example.com",
        home_address="1 Main St",
        primary_first_name="Pat",
        primary_last_name=family.name,
        primary_gender="female",
        primary_language="english",
        primary_relationship="mother",
        primary_phone="555-0100",
        primary_phone_type="cell",
        primary_text_subscription="yes",
        primary_email_subscription="yes",
        primary_email_address="parent@example.com",
        primary_authorized_pickup="yes",
        student_first_name="Ada",
        student_last_name=family.name,
        student_gender="female",
        student_dob=date(2016, 1, 1),
        student_language="english",
        student_ethnicity="unknown",
        student_race="unknown",
        student_grade="3",
        student_school="School 18",
        health_statement="good_health",
        membership_fee_agreed="no",
        payment_method="private_pay",
        payment_plan="weekly",
        payment_plan_signature="Pat",
        payment_plan_signed_date=date(2026, 8, 1),
        status=status,
        portal_family=family,
    )


class FamilyUnitSyncTests(TestCase):
    def setUp(self):
        self.main = PortalUnit.objects.create(slug="main-location", name="Main location")
        self.school_18 = PortalUnit.objects.create(
            slug="school-18",
            name="School 18",
            program_type="after_school",
            is_active=True,
        )

    def test_repair_moves_placeholder_family_to_application_site(self):
        family = PortalFamily.objects.create(unit=self.main, slug="rivera", name="Rivera")
        _make_application(family, location="school_18", status="approved")

        moved = repair_family_units_from_applications()
        family.refresh_from_db()

        self.assertEqual(moved, 1)
        self.assertEqual(family.unit_id, self.school_18.id)

    def test_all_families_list_shows_application_unit(self):
        family = PortalFamily.objects.create(unit=self.main, slug="chen", name="Chen")
        _make_application(family, location="school_18", status="approved")

        rows = get_admin_families_live()
        row = next(item for item in rows if item["slug"] == "chen")
        self.assertEqual(row["unit"], "School 18")
        self.assertEqual(row["unit_slug"], "school-18")

    def test_approve_moves_family_even_when_location_already_matches(self):
        family = PortalFamily.objects.create(unit=self.main, slug="patel", name="Patel")
        app = _make_application(family, location="school_18", status="under_review")

        approve_application(app, program_location="school_18")
        family.refresh_from_db()

        self.assertEqual(family.unit_id, self.school_18.id)
        app.refresh_from_db()
        self.assertEqual(app.status, "approved")
