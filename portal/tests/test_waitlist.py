from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse

from datetime import date

from enrollment.add_program import (
    can_add_after_school_for_application,
    create_after_school_from_application,
    create_before_care_from_application,
)
from enrollment.application_review import approve_application, place_on_waitlist
from enrollment.models import EnrollmentApplication, PolicySignature
from enrollment.portal_integration import (
    applications_for_admin,
    create_portal_account_from_enrollment,
    find_existing_family_for_parent,
    link_applications_by_email,
    link_applications_to_family,
    parent_application_list_items,
    waitlist_for_admin,
)
from enrollment.views import _create_application
from portal.admin_services import get_admin_families_live
from portal.attendance_service import families_for_staff
from portal.email_templates import parent_pay_now_url
from portal.member_admin import families_without_parent_login
from portal.models import (
    PortalChild,
    PortalFamily,
    PortalLedgerEntry,
    PortalParentAccount,
    PortalProgramCalendar,
    PortalStaffAccount,
    PortalUnit,
)
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
        help_page = self.client.get(reverse("portal_parent_page", kwargs={"page": "help"}))
        self.assertContains(help_page, "Click + After-care")
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
        self.assertEqual(names, ["Ada Siblings"])
        self.assertEqual(len([row for row in rows if row["slug"] == "siblings"]), 1)
        ada = next(row for row in rows if row["child_name"] == "Ada Siblings")
        self.assertEqual(ada.get("child_id"), family.children.get(name="Ada Siblings").pk)
        self.assertIsNone(ada.get("application_id"))
        self.assertTrue(any(item["child"] == "Ben Siblings" for item in waitlist_for_admin()))
        self.assertEqual(approved.status, "approved")
        self.assertEqual(family.enrollment_applications.filter(status="waitlist").count(), 1)

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
        self.assertNotContains(admin_page, "Pia Mixed")
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


class SameChildWaitlistFamilyTests(TestCase):
    def setUp(self):
        self.unit = PortalUnit.objects.create(
            slug="school-18",
            name="School 18",
            program_type="both",
            is_active=True,
        )
        self.family, self.user, created = create_portal_account_from_enrollment(
            {
                "family_name": "Montoya Cuenca",
                "primary_email": "parent@example.com",
                "primary_email_address": "parent@example.com",
                "primary_first_name": "Jakera",
                "primary_last_name": "Montoya",
                "children": [
                    {
                        "student_first_name": "Danuska",
                        "student_last_name": "Montoya Cuenca",
                        "student_dob": date(2016, 5, 1),
                        "program": "after_school",
                        "program_location": "school_18",
                    }
                ],
            },
            "jakera",
            "ParentPass123",
        )
        self.assertTrue(created)
        self.app = _make_application(self.family, location="school_18", status="under_review")
        self.app.student_first_name = "Danuska"
        self.app.student_last_name = "Montoya Cuenca"
        self.app.student_dob = date(2016, 5, 1)
        self.app.primary_email = "parent@example.com"
        self.app.membership_fee_agreed = "yes"
        self.app.save()
        approve_application(self.app)

    def test_before_care_waitlist_reuses_family_and_one_all_families_row(self):
        waitlist = create_before_care_from_application(self.app)
        waitlist.student_first_name = "Danuska Daenerys"
        waitlist.student_last_name = "Montoya Cuenca"
        waitlist.save(update_fields=["student_first_name", "student_last_name"])

        self.assertEqual(waitlist.portal_family_id, self.family.pk)
        self.assertEqual(PortalFamily.objects.count(), 1)

        rows = [row for row in get_admin_families_live() if row["id"] == self.family.pk]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["child_name"], "Danuska Montoya Cuenca")
        self.assertTrue(any(item["child"] == "Danuska Daenerys Montoya Cuenca" for item in waitlist_for_admin()))

    def test_new_waitlist_apply_with_middle_name_does_not_create_second_family(self):
        family, user, created = create_portal_account_from_enrollment(
            {
                "family_name": "Montoya Cuenca",
                "primary_email": "other-parent@example.com",
                "primary_email_address": "other-parent@example.com",
                "primary_first_name": "Jakera",
                "primary_last_name": "Montoya",
                "children": [
                    {
                        "student_first_name": "Danuska Daenerys",
                        "student_last_name": "Montoya Cuenca",
                        "student_dob": date(2016, 5, 1),
                        "program": "before_care",
                        "program_location": "school_18",
                    }
                ],
            },
            "jakera2",
            "ParentPass123",
        )
        self.assertFalse(created)
        self.assertEqual(family.pk, self.family.pk)
        self.assertEqual(user.pk, self.user.pk)
        self.assertEqual(PortalFamily.objects.count(), 1)
        self.assertEqual(
            find_existing_family_for_parent(
                child_first="Danuska Daenerys",
                child_last="Montoya Cuenca",
                child_dob=date(2016, 5, 1),
            ).pk,
            self.family.pk,
        )

    def test_membership_fee_posts_once_for_same_child_with_middle_name(self):
        fees = PortalLedgerEntry.objects.filter(family=self.family, entry_type="membership")
        self.assertEqual(fees.count(), 1)
        extra = _make_application(self.family, location="school_18", status="under_review")
        extra.student_first_name = "Danuska Daenerys"
        extra.student_last_name = "Montoya Cuenca"
        extra.student_dob = date(2016, 5, 1)
        extra.membership_fee_agreed = "yes"
        extra.save()
        approve_application(extra)
        self.assertEqual(PortalLedgerEntry.objects.filter(family=self.family, entry_type="membership").count(), 1)
        self.assertEqual(self.family.children.filter(is_active=True).count(), 1)

    def test_link_by_email_keeps_waitlist_status(self):
        orphan = _make_application(self.family, location="school_18", status="waitlist")
        orphan.program = "before_care"
        orphan.portal_family = None
        orphan.primary_email = "parent@example.com"
        orphan.save()
        linked = link_applications_by_email(self.family, "parent@example.com")
        orphan.refresh_from_db()
        self.assertEqual(linked, 1)
        self.assertEqual(orphan.portal_family_id, self.family.pk)
        self.assertEqual(orphan.status, "waitlist")
        self.assertEqual(PortalFamily.objects.count(), 1)

    def test_duplicate_before_care_application_is_not_kept(self):
        first = create_before_care_from_application(self.app)
        clone = _make_application(self.family, location="school_18", status="waitlist")
        clone.program = "before_care"
        clone.student_first_name = "Danuska Daenerys"
        clone.student_last_name = "Montoya Cuenca"
        clone.student_dob = date(2016, 5, 1)
        clone.portal_family = None
        clone.save()
        link_applications_to_family([clone], self.family)
        self.assertFalse(EnrollmentApplication.objects.filter(pk=clone.pk).exists())
        self.assertEqual(
            EnrollmentApplication.objects.filter(
                portal_family=self.family, program="before_care", status="waitlist"
            ).count(),
            1,
        )
        self.assertEqual(first.portal_family_id, self.family.pk)


def _before_care_apply_payload(family, *, first="Ada", last=None, dob=None):
    last = last or family.name
    dob_iso = (dob or date(2016, 1, 1)).isoformat()
    return {
        "program": "before_care",
        "program_location": "school_18",
        "family_name": family.name,
        "primary_email": "parent@example.com",
        "home_address": "1 Main St",
        "primary_first_name": "Pat",
        "primary_last_name": family.name,
        "primary_gender": "female",
        "primary_language": "english",
        "primary_relationship": "mother",
        "primary_phone": "555-0100",
        "primary_phone_type": "cell",
        "primary_text_subscription": "yes",
        "primary_email_subscription": "yes",
        "primary_email_address": "parent@example.com",
        "primary_authorized_pickup": "yes",
        "student_first_name": first,
        "student_last_name": last,
        "student_gender": "female",
        "student_dob": dob_iso,
        "student_language": "english",
        "student_ethnicity": "unknown",
        "student_race": "unknown",
        "student_grade": "3",
        "student_school": "School 18",
        "health_statement": "good_health",
        "membership_fee_agreed": "yes",
        "payment_method": "private_pay",
        "payment_plan": "weekly",
        "payment_plan_signature": "Pat",
        "payment_plan_signed_date": date(2026, 8, 1).isoformat(),
        "portal_family": family,
        "emergency_contacts": [],
        "policies": {},
    }


class WaitlistApprovePayEmailTests(TestCase):
    def setUp(self):
        self.unit = PortalUnit.objects.create(
            slug="school-18",
            name="School 18",
            program_type="both",
            is_active=True,
        )
        PortalProgramCalendar.objects.create(program_start=date(2026, 9, 8))

    @override_settings(SITE_URL="https://yeanj.org")
    def test_before_care_apply_goes_to_waitlist_not_active(self):
        family = PortalFamily.objects.create(
            unit=self.unit,
            slug="wait-apply",
            name="Waitapply",
            status="Pending enrollment",
        )
        app = _create_application(_before_care_apply_payload(family, first="Nia"))
        self.assertEqual(app.status, "waitlist")
        self.assertEqual(app.program, "before_care")
        self.assertEqual(waitlist_for_admin()[0]["slug"], str(app.reference))
        self.assertNotIn("wait-apply", {row["slug"] for row in get_admin_families_live()})
        self.assertFalse(PortalChild.objects.filter(family=family, is_active=True).exists())

    @override_settings(SITE_URL="https://yeanj.org")
    def test_waitlist_approve_moves_to_active_families(self):
        family = PortalFamily.objects.create(
            unit=self.unit,
            slug="wait-approve",
            name="Waitapprove",
            status="Pending enrollment",
        )
        app = _create_application(_before_care_apply_payload(family, first="Nia"))
        mail.outbox.clear()
        approve_application(app)
        app.refresh_from_db()
        family.refresh_from_db()

        self.assertEqual(app.status, "approved")
        self.assertEqual(family.status, "Active")
        self.assertEqual(waitlist_for_admin(), [])
        rows = [row for row in get_admin_families_live() if row["id"] == family.pk]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["child_name"], "Nia Waitapprove")
        self.assertEqual(rows[0]["status"], "Active")
        self.assertTrue(family.children.filter(name="Nia Waitapprove", is_active=True).exists())

    @override_settings(SITE_URL="https://yeanj.org")
    def test_second_before_care_approve_reuses_family_and_membership(self):
        family, user, created = create_portal_account_from_enrollment(
            {
                "family_name": "Montoya Cuenca",
                "primary_email": "parent@example.com",
                "primary_email_address": "parent@example.com",
                "primary_first_name": "Jakera",
                "primary_last_name": "Montoya",
                "children": [
                    {
                        "student_first_name": "Danuska",
                        "student_last_name": "Montoya Cuenca",
                        "student_dob": date(2016, 5, 1),
                        "program": "after_school",
                        "program_location": "school_18",
                    }
                ],
            },
            "jakera",
            "ParentPass123",
        )
        after = _make_application(family, location="school_18", status="under_review")
        after.student_first_name = "Danuska"
        after.student_last_name = "Montoya Cuenca"
        after.student_dob = date(2016, 5, 1)
        after.membership_fee_agreed = "yes"
        after.save()
        approve_application(after)
        child = family.children.get()
        child.unit = self.unit
        child.save(update_fields=["unit"])
        waitlist = create_before_care_from_application(after)
        waitlist.student_first_name = "Danuska Daenerys"
        waitlist.student_last_name = "Montoya Cuenca"
        waitlist.save(update_fields=["student_first_name", "student_last_name"])

        family_pk = family.pk
        membership_count = PortalLedgerEntry.objects.filter(family=family, entry_type="membership").count()
        self.assertEqual(membership_count, 1)
        self.assertEqual(waitlist.portal_family_id, family_pk)
        self.assertTrue(any(item["child"] == "Danuska Daenerys Montoya Cuenca" for item in waitlist_for_admin()))

        mail.outbox.clear()
        approve_application(waitlist)
        waitlist.refresh_from_db()
        family.refresh_from_db()

        self.assertEqual(waitlist.status, "approved")
        self.assertEqual(waitlist.portal_family_id, family_pk)
        self.assertEqual(PortalFamily.objects.count(), 1)
        self.assertEqual(
            PortalLedgerEntry.objects.filter(family=family, entry_type="membership").count(),
            1,
        )
        self.assertEqual(family.children.filter(is_active=True).count(), 1)
        self.assertEqual(family.children.get().unit_id, self.unit.id)
        self.assertEqual(waitlist_for_admin(), [])
        items = parent_application_list_items(family)
        self.assertTrue(any("before care approved" in item["program"] for item in items))

    @override_settings(SITE_URL="https://yeanj.org")
    def test_approve_email_has_payment_steps_and_url(self):
        family = PortalFamily.objects.create(
            unit=self.unit,
            slug="pay-email",
            name="Payemail",
            status="Pending enrollment",
        )
        app = _create_application(_before_care_apply_payload(family, first="Nia"))
        mail.outbox.clear()
        approve_application(app)
        self.assertEqual(len(mail.outbox), 1)
        body = mail.outbox[0].body
        payment_url = parent_pay_now_url()
        self.assertTrue(payment_url.endswith("/portal/parent/payment/"))
        self.assertIn("https://yeanj.org/portal/parent/payment/", body)
        self.assertIn("Payment is due before the program start", body)
        self.assertIn("September 8, 2026", body)
        self.assertIn("parent portal", body.lower())
        self.assertIn("1. Open Parent login", body)
        self.assertIn("Pay now / Billing", body)
        self.assertIn("Continue to review", body)
        self.assertIn("Pay with Stripe", body)
        self.assertIn("check or money order", body)
        self.assertIn(reverse("portal_parent_payment"), body)

    @override_settings(SITE_URL="https://yeanj.org", PORTAL_PREVIEW_MODE=False)
    def test_family_applications_show_before_care_approved(self):
        User = get_user_model()
        family = PortalFamily.objects.create(unit=self.unit, slug="shown", name="Shown", status="Active")
        after = _make_application(family, status="approved")
        family.children.create(name="Ada Shown", is_active=True, unit=self.unit)
        waitlist = create_before_care_from_application(after)
        approve_application(waitlist)
        admin = User.objects.create_user(username="staff:yeaadmin", password="AdminPass123")
        PortalStaffAccount.objects.create(
            user=admin,
            unit=self.unit,
            display_name="Portal Admin",
            role="Portal admin",
            all_units_access=True,
            is_active=True,
        )
        _staff_login(self.client, admin, "admin")
        page = self.client.get(reverse("portal_admin_family_applications", kwargs={"family_slug": "shown"}))
        self.assertContains(page, "Ada Shown")
        self.assertContains(page, "<dd>Before care</dd>")
        self.assertContains(page, "Approved")
        self.assertNotContains(page, "<dd>Before care (waitlist)</dd>")
        waitlist_page = self.client.get(reverse("portal_admin_page", kwargs={"page": "waitlist"}))
        self.assertNotContains(waitlist_page, "Ada Shown")
        waitlist_page = self.client.get(reverse("portal_admin_page", kwargs={"page": "waitlist"}))
        self.assertContains(waitlist_page, "no duplicate")
        self.assertContains(waitlist_page, "Pay now")

