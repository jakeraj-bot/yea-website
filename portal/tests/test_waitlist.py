from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from enrollment.add_program import (
    can_add_after_school_for_application,
    create_after_school_from_application,
)
from enrollment.application_review import approve_application, place_on_waitlist
from enrollment.models import EnrollmentApplication, PolicySignature
from enrollment.portal_integration import (
    applications_for_admin,
    parent_application_list_items,
    waitlist_for_admin,
)
from portal.models import PortalChild, PortalFamily, PortalParentAccount, PortalStaffAccount, PortalUnit
from portal.staff_auth import PORTAL_AUTH_SESSION_KEY
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


class WaitlistAddAfterCareTests(TestCase):
    def setUp(self):
        self.unit = PortalUnit.objects.create(
            slug="school-18",
            name="School 18",
            program_type="both",
            is_active=True,
        )
        self.family = PortalFamily.objects.create(unit=self.unit, slug="rivera", name="Rivera")
        self.before = _make_application(self.family, status="waitlist")
        self.before.program = "before_care"
        self.before.save(update_fields=["program"])
        PolicySignature.objects.create(
            application=self.before,
            policy_slug="medication",
            policy_title="Medication",
            signature_name="Pat Rivera",
            signed_date=self.before.payment_plan_signed_date,
        )

    def test_waitlisted_before_care_can_add_after_care_without_new_application(self):
        self.assertTrue(can_add_after_school_for_application(self.before))
        family_count = PortalFamily.objects.count()
        app_count = EnrollmentApplication.objects.count()

        after = create_after_school_from_application(self.before)
        self.before.refresh_from_db()

        self.assertEqual(self.before.status, "waitlist")
        self.assertEqual(self.before.program, "before_care")
        self.assertEqual(after.program, "after_school")
        self.assertEqual(after.status, "under_review")
        self.assertEqual(after.portal_family_id, self.family.pk)
        self.assertEqual(after.student_first_name, self.before.student_first_name)
        self.assertEqual(after.student_last_name, self.before.student_last_name)
        self.assertEqual(after.family_group, self.before.family_group)
        self.assertEqual(after.primary_email, self.before.primary_email)
        self.assertTrue(after.policy_signatures.filter(policy_slug="medication").exists())
        self.assertEqual(PortalFamily.objects.count(), family_count)
        self.assertEqual(EnrollmentApplication.objects.filter(portal_family=self.family).count(), app_count + 1)
        self.assertFalse(can_add_after_school_for_application(self.before))

        waitlist = waitlist_for_admin()
        self.assertEqual(len(waitlist), 1)
        self.assertEqual(waitlist[0]["slug"], str(self.before.reference))
        self.assertTrue(waitlist[0]["can_add_after_school"] is False)

        queue = applications_for_admin()
        self.assertEqual(len(queue), 1)
        self.assertEqual(queue[0]["slug"], str(after.reference))
        self.assertIn("After-school", queue[0]["program"])

    def test_parent_list_offers_after_care_on_waitlisted_before_care_only(self):
        items = parent_application_list_items(self.family)
        self.assertEqual(len(items), 1)
        self.assertTrue(items[0]["can_add_after_school"])
        self.assertFalse(items[0]["can_add_before_care"])

        create_after_school_from_application(self.before)
        items = parent_application_list_items(self.family)
        self.assertEqual(len(items), 1)
        self.assertFalse(items[0]["can_add_after_school"])
        self.assertIn("before care waitlist", items[0]["program"])

    def test_duplicate_after_care_is_blocked(self):
        create_after_school_from_application(self.before)
        with self.assertRaises(ValueError):
            create_after_school_from_application(self.before)


class WaitlistAddAfterCareViewTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.unit = PortalUnit.objects.create(
            slug="school-18",
            name="School 18",
            program_type="both",
            is_active=True,
        )
        self.family = PortalFamily.objects.create(unit=self.unit, slug="rivera", name="Rivera")
        self.before = _make_application(self.family, status="waitlist")
        self.before.program = "before_care"
        self.before.save(update_fields=["program"])
        self.admin_user = User.objects.create_user(username="admin:yeaadmin", password="AdminPass123")
        PortalStaffAccount.objects.create(
            user=self.admin_user,
            unit=self.unit,
            display_name="YEA Admin",
            role="Portal admin",
            all_units_access=True,
            is_active=True,
        )
        self.staff_user = User.objects.create_user(username="staff:unitstaff", password="StaffPass123")
        PortalStaffAccount.objects.create(
            user=self.staff_user,
            unit=self.unit,
            display_name="Unit Staff",
            role="Unit staff",
            all_units_access=False,
            is_active=True,
        )
        self.parent_user = User.objects.create_user(username="parent:rivera", password="ParentPass123")
        PortalParentAccount.objects.create(user=self.parent_user, family=self.family)

    def _login(self, user, area):
        self.client.force_login(user)
        session = self.client.session
        session[PORTAL_AUTH_SESSION_KEY] = area
        session.save()

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_staff_waitlist_page_has_after_care_action_and_walkthrough(self):
        self._login(self.staff_user, "staff")
        page = self.client.get(reverse("portal_staff_page", kwargs={"page": "waitlist"}))
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, "+ After-care")
        self.assertContains(page, "How to use this page")
        self.assertContains(page, "Find the waitlisted child")
        self.assertContains(page, "Add After-care")
        self.assertContains(page, "Confirm to save")
        self.assertContains(page, "new enrollment form")
        self.assertContains(page, "portal-page-guide.js")

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_admin_can_add_after_care_from_waitlist_without_new_application(self):
        self._login(self.admin_user, "admin")
        family_count = PortalFamily.objects.count()
        url = reverse("portal_admin_application_review", kwargs={"app_slug": str(self.before.reference)})
        response = self.client.post(
            url,
            {"action": "add_after_school", "next": reverse("portal_admin_page", kwargs={"page": "waitlist"})},
        )
        self.assertEqual(response.status_code, 302)
        self.before.refresh_from_db()
        self.assertEqual(self.before.status, "waitlist")
        after = EnrollmentApplication.objects.exclude(pk=self.before.pk).get(portal_family=self.family)
        self.assertEqual(after.program, "after_school")
        self.assertEqual(after.status, "under_review")
        self.assertEqual(PortalFamily.objects.count(), family_count)
        waitlist = self.client.get(reverse("portal_admin_page", kwargs={"page": "waitlist"}))
        self.assertContains(waitlist, "Ada Rivera")
        self.assertContains(waitlist, "Before care")
        apps = self.client.get(reverse("portal_admin_page", kwargs={"page": "applications"}))
        self.assertContains(apps, "Ada Rivera")
        self.assertContains(apps, "After-school")
        family_apps = self.client.get(
            reverse("portal_admin_family_applications", kwargs={"family_slug": "rivera"})
        )
        self.assertContains(family_apps, "How to use this page")
        self.assertContains(family_apps, "Add After-care for a waitlisted before-care child")
        self.assertContains(family_apps, "After-school")
        self.assertContains(family_apps, "Before care")

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_parent_can_add_after_care_from_applications(self):
        self._login(self.parent_user, "parent")
        list_page = self.client.get(reverse("portal_parent_page", kwargs={"page": "applications"}))
        self.assertContains(list_page, "+ After-care")
        self.assertContains(list_page, "How to use this page")
        self.assertContains(list_page, "Click + After-care")
        self.assertContains(list_page, "portal-page-guide.js")
        confirm = self.client.get(
            reverse("enrollment_apply_add_after_care", kwargs={"reference": self.before.reference})
        )
        self.assertEqual(confirm.status_code, 200)
        self.assertContains(confirm, "no need to fill everything out again")
        posted = self.client.post(
            reverse("enrollment_apply_add_after_care", kwargs={"reference": self.before.reference})
        )
        self.assertEqual(posted.status_code, 302)
        self.before.refresh_from_db()
        self.assertEqual(self.before.status, "waitlist")
        after = EnrollmentApplication.objects.exclude(pk=self.before.pk).get(portal_family=self.family)
        self.assertEqual(after.program, "after_school")
        self.assertEqual(after.status, "under_review")
        again = self.client.get(reverse("portal_parent_page", kwargs={"page": "applications"}))
        self.assertContains(again, "before care waitlist")
        self.assertNotContains(
            again,
            reverse("enrollment_apply_add_after_care", kwargs={"reference": self.before.reference}),
        )

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_staff_can_add_after_care_from_waitlist_without_new_application(self):
        self._login(self.staff_user, "staff")
        family_count = PortalFamily.objects.count()
        url = reverse("portal_staff_application_review", kwargs={"app_slug": str(self.before.reference)})
        response = self.client.post(
            url,
            {"action": "add_after_school", "next": reverse("portal_staff_page", kwargs={"page": "waitlist"})},
        )
        self.assertEqual(response.status_code, 302)
        self.before.refresh_from_db()
        self.assertEqual(self.before.status, "waitlist")
        after = EnrollmentApplication.objects.exclude(pk=self.before.pk).get(portal_family=self.family)
        self.assertEqual(after.program, "after_school")
        self.assertEqual(after.status, "under_review")
        self.assertEqual(PortalFamily.objects.count(), family_count)
        waitlist = self.client.get(reverse("portal_staff_page", kwargs={"page": "waitlist"}))
        self.assertContains(waitlist, "Ada Rivera")
        self.assertContains(waitlist, "Before care")
        self.assertNotContains(waitlist, 'value="add_after_school"')
