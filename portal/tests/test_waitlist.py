from django.test import TestCase

from enrollment.application_review import approve_application, place_on_waitlist
from enrollment.portal_integration import applications_for_admin, waitlist_for_admin
from portal.models import PortalChild, PortalFamily, PortalUnit
from portal.tests.test_family_units import _make_application


class WaitlistWorkflowTests(TestCase):
    def setUp(self):
        self.unit = PortalUnit.objects.create(
            slug="school-18",
            name="School 18",
            program_type="after_school",
            is_active=True,
        )
        self.family = PortalFamily.objects.create(unit=self.unit, slug="rivera", name="Rivera")

    def test_place_on_waitlist_leaves_applications_queue(self):
        app = _make_application(self.family, status="under_review")
        place_on_waitlist(app)
        app.refresh_from_db()

        self.assertEqual(app.status, "waitlist")
        self.assertEqual(applications_for_admin(), [])
        rows = waitlist_for_admin()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["slug"], str(app.reference))
        self.assertFalse(PortalChild.objects.filter(family=self.family).exists())

    def test_waitlist_approve_adds_to_roster_and_leaves_waitlist(self):
        app = _make_application(self.family, status="waitlist")
        approve_application(app)
        app.refresh_from_db()

        self.assertEqual(app.status, "approved")
        self.assertEqual(waitlist_for_admin(), [])
        self.assertTrue(PortalChild.objects.filter(family=self.family, is_active=True).exists())
