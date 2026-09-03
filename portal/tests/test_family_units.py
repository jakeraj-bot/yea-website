from datetime import date

from decimal import Decimal

from django.test import TestCase

from enrollment.application_review import (
    approve_application,
    repair_family_units_from_applications,
)
from enrollment.models import EnrollmentApplication
from portal.admin_services import get_admin_families_live
from portal.attendance_service import families_for_staff
from portal.family_list import child_balance_map, expand_demo_families
from portal.models import PortalFamily, PortalLedgerEntry, PortalUnit
from portal.staff_services import build_school_bus_roster


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


class FamilyListRowTests(TestCase):
    def setUp(self):
        self.unit = PortalUnit.objects.create(slug="school-18", name="School 18", is_active=True)

    def test_families_for_staff_expands_children_into_separate_rows(self):
        family = PortalFamily.objects.create(unit=self.unit, slug="jacobs", name="Jacobs", balance=Decimal("80.00"))
        child_one = family.children.create(name="Jordan Jacobs", school="Lincoln Elementary", is_active=True)
        child_two = family.children.create(name="Maya Jacobs", school="Lincoln Elementary", is_active=True)
        PortalLedgerEntry.objects.create(
            family=family,
            child_name=child_one.name,
            date="2026-09-01",
            entry_type="charge",
            description="Weekly tuition",
            amount=Decimal("35.00"),
        )
        PortalLedgerEntry.objects.create(
            family=family,
            child_name=child_two.name,
            date="2026-09-01",
            entry_type="charge",
            description="Weekly tuition",
            amount=Decimal("45.00"),
        )

        rows = families_for_staff(self.unit)
        jacobs_rows = [row for row in rows if row["slug"] == "jacobs"]

        self.assertEqual(len(jacobs_rows), 2)
        self.assertEqual(jacobs_rows[0]["child_name"], "Jordan Jacobs")
        self.assertEqual(jacobs_rows[1]["child_name"], "Maya Jacobs")
        self.assertEqual(jacobs_rows[0]["child_balance"], "35.00")
        self.assertEqual(jacobs_rows[1]["child_balance"], "45.00")
        self.assertEqual(jacobs_rows[0]["family_balance"], "80.00")
        self.assertTrue(jacobs_rows[0]["is_first_child"])
        self.assertFalse(jacobs_rows[1]["is_first_child"])

    def test_child_balance_map_sums_ledger_entries_per_child(self):
        family = PortalFamily.objects.create(unit=self.unit, slug="nguyen", name="Nguyen")
        PortalLedgerEntry.objects.create(
            family=family,
            child_name="An Nguyen",
            date="2026-09-01",
            entry_type="charge",
            description="Weekly tuition",
            amount=Decimal("25.00"),
        )
        PortalLedgerEntry.objects.create(
            family=family,
            child_name="An Nguyen",
            date="2026-09-02",
            entry_type="payment",
            description="Card payment",
            amount=Decimal("-10.00"),
        )

        balances = child_balance_map(family)
        self.assertEqual(balances["An Nguyen"], Decimal("15.00"))

    def test_expand_demo_families_splits_multi_child_family(self):
        from portal.demo_data import FAMILIES

        rows = expand_demo_families(FAMILIES)
        jacobs_rows = [row for row in rows if row["slug"] == "jacobs"]
        self.assertEqual(len(jacobs_rows), 2)
        self.assertEqual({row["child_name"] for row in jacobs_rows}, {"Jordan Jacobs", "Maya Jacobs"})


class SchoolBusRosterTests(TestCase):
    def setUp(self):
        self.unit = PortalUnit.objects.create(slug="school-18", name="School 18", is_active=True)

    def test_build_school_bus_roster_groups_by_school_attending(self):
        family_a = PortalFamily.objects.create(unit=self.unit, slug="williams", name="Williams")
        family_b = PortalFamily.objects.create(unit=self.unit, slug="jacobs", name="Jacobs")
        family_a.children.create(name="Aiden Williams", grade="3rd", school="Roosevelt Elementary", is_active=True)
        family_b.children.create(name="Jordan Jacobs", grade="4th", school="Lincoln Elementary", is_active=True)
        family_b.children.create(name="Maya Jacobs", grade="1st", school="Lincoln Elementary", is_active=True)

        sections = build_school_bus_roster(self.unit)
        schools = {section["school"]: section["children"] for section in sections}

        self.assertEqual(len(sections), 2)
        self.assertEqual(len(schools["Lincoln Elementary"]), 2)
        self.assertEqual(len(schools["Roosevelt Elementary"]), 1)
        self.assertEqual(schools["Lincoln Elementary"][0]["child"], "Jordan Jacobs")
