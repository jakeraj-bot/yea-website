from datetime import date

from django.test import TestCase, override_settings

from enrollment.add_program import primary_applications_by_child
from enrollment.application_review import approve_application, revert_approved_before_care_to_waitlist
from enrollment.models import EnrollmentApplication, PolicySignature
from enrollment.portal_integration import parent_application_list_items
from portal.agency_services import agency_page_data, purge_demo_agency_members
from portal.models import PortalAgencyProfile, PortalChild, PortalFamily, PortalUnit
from portal.parent_services import get_parent_policy_data_live
from portal.tests.test_family_units import _make_application


class BeforeCareWaitlistCorrectionTests(TestCase):
    def setUp(self):
        self.unit = PortalUnit.objects.create(slug="school-18", name="School 18", is_active=True)
        self.family = PortalFamily.objects.create(unit=self.unit, slug="rivera", name="Rivera")

    def test_revert_moves_before_care_only_and_keeps_after_school(self):
        after = _make_application(self.family, status="approved")
        after.program = "after_school"
        after.save(update_fields=["program"])
        before = _make_application(self.family, status="approved")
        before.program = "before_care"
        before.save(update_fields=["program"])
        child = PortalChild.objects.create(family=self.family, name="Ada Rivera", grade="3", is_active=True)

        count = revert_approved_before_care_to_waitlist()
        before.refresh_from_db()
        after.refresh_from_db()
        child.refresh_from_db()

        self.assertEqual(count, 1)
        self.assertEqual(before.status, "waitlist")
        self.assertEqual(after.status, "approved")
        self.assertTrue(child.is_active)

    def test_revert_removes_roster_child_when_only_before_care_was_approved(self):
        before = _make_application(self.family, status="approved")
        before.program = "before_care"
        before.save(update_fields=["program"])
        child = PortalChild.objects.create(family=self.family, name="Ada Rivera", grade="3", is_active=True)

        revert_approved_before_care_to_waitlist()
        before.refresh_from_db()
        child.refresh_from_db()
        self.assertEqual(before.status, "waitlist")
        self.assertFalse(child.is_active)

    def test_parent_application_list_folds_before_care_waitlist(self):
        after = _make_application(self.family, status="under_review")
        before = _make_application(self.family, status="waitlist")
        before.program = "before_care"
        before.save(update_fields=["program"])

        items = parent_application_list_items(self.family)
        self.assertEqual(len(items), 1)
        self.assertIn("before care waitlist", items[0]["program"])
        self.assertEqual(items[0]["reference"], str(after.reference))

    def test_policies_count_one_packet_per_child(self):
        after = _make_application(self.family, status="under_review")
        before = _make_application(self.family, status="waitlist")
        before.program = "before_care"
        before.save(update_fields=["program"])
        PolicySignature.objects.create(
            application=after,
            policy_slug="medication",
            policy_title="Medication",
            signature_name="Pat Rivera",
            signed_date=date(2026, 9, 1),
        )

        primaries = primary_applications_by_child([after, before])
        self.assertEqual(len(primaries), 1)
        self.assertEqual(primaries[0].pk, after.pk)

        data = get_parent_policy_data_live(self.family)
        self.assertEqual(data["child_count"], 1)
        self.assertEqual(data["children"][0]["child_name"], "Ada Rivera")


class DemoAgencyCleanupTests(TestCase):
    def setUp(self):
        self.unit = PortalUnit.objects.create(slug="school-18", name="School 18", is_active=True)

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_live_agency_page_does_not_show_sofia_or_ethan(self):
        data = agency_page_data(self.unit)
        names = [row["child"] for row in data["children"]]
        self.assertNotIn("Sofia Martinez", names)
        self.assertNotIn("Ethan Chen", names)
        self.assertEqual(data["children"], [])

    def test_purge_removes_seeded_4cs_profiles(self):
        family = PortalFamily.objects.create(
            unit=self.unit, slug="chen", name="Chen", billing_type="4Cs"
        )
        child = PortalChild.objects.create(family=family, name="Ethan Chen", grade="5")
        PortalAgencyProfile.objects.create(
            unit=self.unit,
            family=family,
            child=child,
            auth_number="4CS-2026-9012",
        )

        profiles, families = purge_demo_agency_members()
        self.assertEqual(profiles, 1)
        self.assertEqual(families, 1)
        self.assertFalse(PortalAgencyProfile.objects.exists())
        self.assertFalse(PortalFamily.objects.filter(slug="chen").exists())


class BeforeCareApproveThenRevertTests(TestCase):
    def setUp(self):
        self.unit = PortalUnit.objects.create(
            slug="school-18",
            name="School 18",
            program_type="both",
            is_active=True,
        )
        self.family = PortalFamily.objects.create(unit=self.unit, slug="lee", name="Lee")

    def test_waitlist_approve_then_bulk_revert(self):
        app = _make_application(self.family, status="waitlist")
        app.program = "before_care"
        app.save(update_fields=["program"])
        approve_application(app)
        app.refresh_from_db()
        self.assertEqual(app.status, "approved")
        self.assertTrue(PortalChild.objects.filter(family=self.family, is_active=True).exists())

        revert_approved_before_care_to_waitlist()
        app.refresh_from_db()
        self.assertEqual(app.status, "waitlist")
        self.assertFalse(PortalChild.objects.filter(family=self.family, is_active=True).exists())
