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
from portal.admin_services import get_admin_families_live
from portal.attendance_service import families_for_staff
from portal.member_admin import families_without_parent_login
from portal.models import PortalChild, PortalFamily, PortalParentAccount, PortalStaffAccount, PortalUnit
from portal.staff_auth import PORTAL_AUTH_SESSION_KEY
from portal.tests.test_family_units import _make_application, _staff_login


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


def _named_application(family, *, first, last=None, status="waitlist", location="school_18"):
    app = _make_application(family, location=location, status=status)
    app.student_first_name = first
    app.student_last_name = last or family.name
    app.save(update_fields=["student_first_name", "student_last_name"])
    return app


def _child_names(rows, slug):
    return [row["child_name"] for row in rows if row["slug"] == slug]


class WaitlistHiddenFromFamiliesTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.unit = PortalUnit.objects.create(
            slug="school-18",
            name="School 18",
            program_type="after_school",
            is_active=True,
        )
        self.admin = User.objects.create_user(username="staff:yeaadmin", password="AdminPass123")
        PortalStaffAccount.objects.create(
            user=self.admin,
            unit=self.unit,
            display_name="Portal Admin",
            role="Portal admin",
            all_units_access=True,
            is_active=True,
        )
        self.staff = User.objects.create_user(username="staff:unit18", password="StaffPass123")
        PortalStaffAccount.objects.create(
            user=self.staff,
            unit=self.unit,
            display_name="School 18 Staff",
            role="Unit director",
            is_active=True,
        )

    def test_waitlist_only_child_is_hidden_from_all_families(self):
        family = PortalFamily.objects.create(unit=self.unit, slug="wait-only", name="Waitonly")
        _named_application(family, first="Ada", status="waitlist")

        admin_rows = get_admin_families_live()
        staff_rows = families_for_staff(self.unit)
        self.assertEqual(_child_names(admin_rows, "wait-only"), [])
        self.assertEqual(_child_names(staff_rows, "wait-only"), [])
        self.assertNotIn("wait-only", {row["slug"] for row in admin_rows})
        self.assertNotIn("wait-only", {row["slug"] for row in staff_rows})
        self.assertEqual(waitlist_for_admin()[0]["child"], "Ada Waitonly")

    def test_approved_sibling_keeps_household_on_all_families(self):
        family = PortalFamily.objects.create(unit=self.unit, slug="siblings", name="Siblings")
        approved = _named_application(family, first="Ada", status="approved")
        _named_application(family, first="Ben", status="waitlist")
        family.children.create(name="Ada Siblings", school="School 18", is_active=True)

        rows = get_admin_families_live()
        names = _child_names(rows, "siblings")
        self.assertIn("Ada Siblings", names)
        self.assertIn("Ben Siblings", names)
        self.assertEqual(len([row for row in rows if row["slug"] == "siblings"]), 2)
        ada = next(row for row in rows if row["child_name"] == "Ada Siblings")
        self.assertEqual(ada.get("child_id"), family.children.get(name="Ada Siblings").pk)
        self.assertIsNone(ada.get("application_id"))
        ben = next(row for row in rows if row["child_name"] == "Ben Siblings")
        self.assertEqual(ben.get("application_id"), EnrollmentApplication.objects.get(student_first_name="Ben").pk)
        self.assertTrue(any(item["child"] == "Ben Siblings" for item in waitlist_for_admin()))
        self.assertEqual(approved.status, "approved")

    def test_two_waitlist_apps_without_approval_stay_hidden(self):
        family = PortalFamily.objects.create(unit=self.unit, slug="two-wait", name="Twowait")
        _named_application(family, first="Ada", status="waitlist")
        _named_application(family, first="Ben", status="waitlist")
        family.children.create(name="Ada Twowait", is_active=True)

        rows = get_admin_families_live()
        self.assertNotIn("two-wait", {row["slug"] for row in rows})
        self.assertEqual(_child_names(rows, "two-wait"), [])
        waitlist_names = {item["child"] for item in waitlist_for_admin()}
        self.assertEqual(waitlist_names, {"Ada Twowait", "Ben Twowait"})
        self.assertEqual(list(families_without_parent_login()), [])

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_admin_and_staff_all_families_pages_hide_waitlist_only(self):
        wait_family = PortalFamily.objects.create(unit=self.unit, slug="hidden-wait", name="Hiddenwait")
        _named_application(wait_family, first="Nia", status="waitlist")
        listed = PortalFamily.objects.create(unit=self.unit, slug="listed", name="Listed")
        _named_application(listed, first="Mia", status="approved")
        listed.children.create(name="Mia Listed", is_active=True)
        sibling_family = PortalFamily.objects.create(unit=self.unit, slug="mixed", name="Mixed")
        _named_application(sibling_family, first="Owen", status="approved")
        _named_application(sibling_family, first="Pia", status="waitlist")
        sibling_family.children.create(name="Owen Mixed", is_active=True)

        _staff_login(self.client, self.admin, "admin")
        admin_page = self.client.get(reverse("portal_admin_page", kwargs={"page": "families"}))
        self.assertEqual(admin_page.status_code, 200)
        self.assertContains(admin_page, "All families")
        self.assertContains(admin_page, "Mia Listed")
        self.assertContains(admin_page, "Owen Mixed")
        self.assertNotContains(admin_page, "Nia Hiddenwait")
        self.assertNotContains(admin_page, "hidden-wait")

        waitlist_page = self.client.get(reverse("portal_admin_page", kwargs={"page": "waitlist"}))
        self.assertContains(waitlist_page, "Nia Hiddenwait")
        self.assertContains(waitlist_page, "Pia Mixed")

        _staff_login(self.client, self.staff, "staff")
        session = self.client.session
        session["staff_unit_slug"] = "school-18"
        session.save()
        staff_page = self.client.get(reverse("portal_staff_page", kwargs={"page": "families"}))
        self.assertEqual(staff_page.status_code, 200)
        self.assertContains(staff_page, "Mia Listed")
        self.assertContains(staff_page, "Owen Mixed")
        self.assertNotContains(staff_page, "Nia Hiddenwait")
        staff_waitlist = self.client.get(reverse("portal_staff_page", kwargs={"page": "waitlist"}))
        self.assertContains(staff_waitlist, "Nia Hiddenwait")
