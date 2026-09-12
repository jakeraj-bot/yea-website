from datetime import time

from django.test import TestCase

from portal.admin_config import get_programs_admin, get_units_admin
from portal.admin_services import get_admin_dashboard_live, get_enrollment_by_unit_live
from portal.enrollment_counts import (
    dashboard_enrollment_totals,
    unit_capacity,
    unit_enrollment_count,
)
from portal.models import PortalChild, PortalFamily, PortalProgram, PortalUnit
from portal.staff_services import get_programs_for_unit
from portal.tests.test_family_units import _make_application


def _enrolled_child(family, name, unit, *, status="approved", location="school_18"):
    child = PortalChild.objects.create(family=family, unit=unit, name=name, is_active=True)
    first, last = name.split(" ", 1)
    app = _make_application(family, location=location, status=status)
    app.student_first_name = first
    app.student_last_name = last
    app.save(update_fields=["student_first_name", "student_last_name"])
    return child


class EnrollmentCountTests(TestCase):
    def setUp(self):
        self.main = PortalUnit.objects.create(
            slug="main-location",
            name="Main location",
            capacity=0,
            is_active=False,
        )
        self.school_18 = PortalUnit.objects.create(
            slug="school-18",
            name="School 18",
            capacity=75,
            is_active=True,
        )
        self.school_26 = PortalUnit.objects.create(
            slug="school-26",
            name="School 26",
            capacity=60,
            is_active=True,
        )
        self.family = PortalFamily.objects.create(unit=self.school_18, slug="rivera", name="Rivera")

    def _dashboard_row(self, slug):
        return next(row for row in dashboard_enrollment_totals()["by_unit"] if row["slug"] == slug)

    def _units_row(self, slug):
        return next(row for row in get_units_admin() if row["slug"] == slug)

    def test_dashboard_and_units_helpers_match(self):
        _enrolled_child(self.family, "Ada Rivera", self.school_18)
        _enrolled_child(self.family, "Ben Rivera", self.school_18)
        other = PortalFamily.objects.create(unit=self.school_26, slug="chen", name="Chen")
        _enrolled_child(other, "Mia Chen", self.school_26, location="school_26")

        dashboard = get_admin_dashboard_live()
        by_unit = {row["slug"]: row for row in get_enrollment_by_unit_live()}
        units = {row["slug"]: row for row in get_units_admin()}
        totals = dashboard_enrollment_totals()

        self.assertEqual(unit_enrollment_count(self.school_18), 2)
        self.assertEqual(unit_enrollment_count(self.school_26), 1)
        self.assertEqual(self._dashboard_row("school-18")["enrolled"], 2)
        self.assertEqual(self._units_row("school-18")["enrolled"], 2)
        self.assertEqual(by_unit["school-18"]["enrolled"], units["school-18"]["enrolled"])
        self.assertEqual(by_unit["school-26"]["enrolled"], units["school-26"]["enrolled"])
        self.assertEqual(by_unit["school-18"]["capacity"], 75)
        self.assertEqual(units["school-18"]["capacity"], 75)
        self.assertEqual(dashboard["total_enrolled"], totals["total_enrolled"])
        self.assertEqual(dashboard["total_enrolled"], 3)
        self.assertEqual(dashboard["total_enrolled"], sum(row["enrolled"] for row in totals["by_unit"]))

    def test_waitlist_only_child_is_excluded(self):
        _enrolled_child(self.family, "Ada Rivera", self.school_18)
        _enrolled_child(self.family, "Leo Rivera", self.school_18, status="waitlist")

        self.assertEqual(unit_enrollment_count(self.school_18), 1)
        self.assertEqual(self._dashboard_row("school-18")["enrolled"], 1)
        self.assertEqual(self._units_row("school-18")["enrolled"], 1)
        self.assertEqual(dashboard_enrollment_totals()["total_enrolled"], 1)

    def test_multi_unit_child_counts_once_at_their_unit(self):
        _enrolled_child(self.family, "Ada Rivera", self.school_18)
        _enrolled_child(self.family, "Nia Rivera", self.school_26, location="school_26")

        self.assertEqual(unit_enrollment_count(self.school_18), 1)
        self.assertEqual(unit_enrollment_count(self.school_26), 1)
        self.assertEqual(self._units_row("school-18")["enrolled"], 1)
        self.assertEqual(self._units_row("school-26")["enrolled"], 1)
        self.assertEqual(self._dashboard_row("school-18")["enrolled"], 1)
        self.assertEqual(self._dashboard_row("school-26")["enrolled"], 1)
        self.assertEqual(dashboard_enrollment_totals()["total_enrolled"], 2)

    def test_inactive_placeholder_shows_stored_capacity(self):
        snapshot_main = self._units_row("main-location")
        self.assertEqual(snapshot_main["enrolled"], 0)
        self.assertEqual(snapshot_main["capacity"], 0)
        self.assertEqual(unit_capacity(self.main), 0)
        slugs = [row["slug"] for row in dashboard_enrollment_totals()["by_unit"]]
        self.assertNotIn("main-location", slugs)

    def test_roster_child_without_application_still_counts(self):
        PortalChild.objects.create(
            family=self.family,
            unit=self.school_18,
            name="Sam Rivera",
            is_active=True,
        )
        self.assertEqual(unit_enrollment_count(self.school_18), 1)

    def test_program_tiles_use_the_same_unit_count(self):
        _enrolled_child(self.family, "Ada Rivera", self.school_18)
        PortalProgram.objects.create(
            unit=self.school_18,
            name="After-School 2026–27",
            start_time=time(15, 0),
            end_time=time(18, 0),
            is_active=True,
        )
        programs = get_programs_admin()
        staff_programs = get_programs_for_unit(self.school_18)
        self.assertEqual(programs[0]["enrolled_count"], 1)
        self.assertEqual(staff_programs[0]["enrolled"], 1)
        self.assertEqual(programs[0]["enrolled_count"], unit_enrollment_count(self.school_18))
