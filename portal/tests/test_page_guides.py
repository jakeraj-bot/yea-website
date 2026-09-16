from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from portal.models import PortalFamily, PortalStaffAccount, PortalUnit
from portal.page_guides import GUIDES, guide_for, page_guide_from_context
from portal.staff_auth import PORTAL_AUTH_SESSION_KEY, application_permissions_for_staff, billing_permissions_for_staff


class PageGuideCatalogTests(TestCase):
    def test_staff_menu_pages_have_guides(self):
        for key in (
            "dashboard",
            "programs",
            "attendance",
            "drop-off-pickup",
            "applications",
            "waitlist",
            "create-application",
            "families",
            "member-policies",
            "agency",
            "agencies",
            "messages",
            "incidents",
            "support",
            "reports",
            "owed-weeks",
            "four-cs-payout",
            "inactive-children",
            "member-information",
            "emergency-contacts",
            "weekly-attendance",
            "weekly-attendance-blank",
            "daily-attendance",
            "daily-attendance-blank",
            "admin-attendance",
            "emails-sent",
            "parent-emails",
            "activity",
            "activity-calendar",
            "groups",
            "staff",
            "outside-programs",
            "member-billing",
        ):
            self.assertIsNotNone(guide_for(key), key)
            self.assertGreaterEqual(GUIDES[key]["steps"].__len__(), 2)

    def test_family_tabs_have_guides(self):
        for tab in (
            "profile",
            "pickup",
            "attendance",
            "incidents",
            "billing",
            "plans",
            "agency",
            "applications",
            "policies",
            "email",
            "notes",
        ):
            self.assertIsNotNone(guide_for(f"family-{tab}"), tab)

    def test_family_attendance_guide_explains_switching_children(self):
        guide = guide_for("family-attendance")
        titles = [step["title"] for step in guide["steps"]]
        self.assertIn("Switch children", titles)
        bodies = " ".join(step["body"] for step in guide["steps"])
        self.assertIn("two children", bodies)
        self.assertIn("names", bodies)
        self.assertIn("Inactive", bodies)

    def test_waitlist_guide_explains_adding_after_care(self):
        guide = guide_for("waitlist")
        titles = [step["title"] for step in guide["steps"]]
        self.assertEqual(titles[0], "Find the waitlisted child")
        self.assertEqual(titles[1], "Add After-care")
        self.assertEqual(titles[2], "Save")
        self.assertIn("new enrollment form", guide["steps"][1]["body"])
        self.assertIn("Confirm to save", guide["steps"][2]["body"])

    def test_application_detail_guide_explains_editable_membership_amount(self):
        guide = guide_for("application-detail")
        titles = [step["title"] for step in guide["steps"]]
        self.assertIn("Change the membership amount before you approve", titles)
        bodies = " ".join(step["body"] for step in guide["steps"])
        self.assertIn("Type 0 to waive", bodies)
        self.assertIn("family ledger", bodies.lower())

    def test_family_billing_guide_explains_editing_membership_amount(self):
        guide = guide_for("family-billing")
        titles = [step["title"] for step in guide["steps"]]
        self.assertIn("Edit a membership charge", titles)
        bodies = " ".join(step["body"] for step in guide["steps"])
        self.assertIn("amount", bodies.lower())

    def test_family_plans_guide_explains_4cs_and_regular_scholarships(self):
        guide = guide_for("family-plans")
        titles = [step["title"] for step in guide["steps"]]
        self.assertIn("Add a scholarship on a regular plan", titles)
        self.assertIn("Add a scholarship on a 4Cs plan", titles)
        bodies = " ".join(step["body"] for step in guide["steps"])
        self.assertIn("parent copay", bodies.lower())
        self.assertIn("agency week amounts stay the same", bodies.lower())
        self.assertIn("private-pay", bodies.lower())
        self.assertIn("family-pays", bodies.lower())
        self.assertIn("plan amount", bodies.lower())

    def test_family_profile_guide_explains_password_reset(self):
        guide = guide_for("family-profile")
        titles = [step["title"] for step in guide["steps"]]
        self.assertIn("Reset parent password", titles)
        bodies = " ".join(step["body"] for step in guide["steps"])
        self.assertIn("cannot look up the current password", bodies)
        self.assertIn("one-time link to create a new password", bodies)
        self.assertIn("Email create-password link", bodies)
        self.assertIn("temporary password", bodies)
        self.assertIn("Forgot password", bodies)

    def test_reports_exports_keep_owed_weeks_and_program_director_note(self):
        reports = guide_for("reports")
        exports = next(step for step in reports["steps"] if step["title"] == "Exports")
        self.assertIn("Program director", exports["body"])
        self.assertIn("Who still owes", exports["body"])
        owed = guide_for("owed-weeks")
        self.assertIsNotNone(owed)
        titles = [step["title"] for step in owed["steps"]]
        self.assertIn("Read the weeks", titles)
        self.assertIn("Charge a late fee only if you pick them", titles)

    def test_outstanding_balances_guide_explains_child_names_and_status_filter(self):
        guide = guide_for("outstanding-balances")
        self.assertIsNotNone(guide)
        bodies = " ".join(step["body"] for step in guide["steps"])
        self.assertIn("child", bodies.lower())
        self.assertIn("status", bodies.lower())
        self.assertIn("filter", bodies.lower())
        self.assertIn("payment", bodies.lower())
        self.assertIn("fee", bodies.lower())
        self.assertIn("inactive", bodies.lower())

    def test_families_guide_explains_inactive_tab_and_phone_search(self):
        guide = guide_for("families")
        titles = [step["title"] for step in guide["steps"]]
        self.assertIn("Inactive tab", titles)
        self.assertIn("Make them active again", titles)
        self.assertIn("Parents can still pay and get tax forms", titles)
        bodies = " ".join(step["body"] for step in guide["steps"])
        self.assertIn("phone", bodies.lower())
        self.assertIn("Pay now", bodies)
        self.assertIn("tax statements", bodies.lower())
        self.assertIn("not a copy", bodies)
        self.assertIn("will not see that child on both tabs", bodies)
        profile = guide_for("family-profile")
        titles = [step["title"] for step in profile["steps"]]
        self.assertIn("Make a child inactive or active", titles)
        self.assertIn("Fold profile sections", titles)
        self.assertIn("Program status", " ".join(step["body"] for step in profile["steps"]))
        self.assertIn("Make inactive", " ".join(step["body"] for step in profile["steps"]))
        self.assertIn("does not copy", " ".join(step["body"] for step in profile["steps"]))
        inactive = guide_for("inactive-children")
        self.assertIsNotNone(inactive)
        self.assertIn("remaining balance", inactive["intro"].lower())
        self.assertIn("not a second copy", " ".join(step["body"] for step in inactive["steps"]))

    def test_program_calendar_guide_explains_two_calendars(self):
        guide = guide_for("program-calendar")
        self.assertIsNotNone(guide)
        bodies = " ".join(step["body"] for step in guide["steps"])
        self.assertIn("9/8/2026", bodies)
        self.assertIn("4Cs", bodies)
        self.assertIn("half days", bodies.lower())

    def test_member_accounts_guide_explains_password_reset(self):
        guide = guide_for("billing-settings")
        self.assertIsNotNone(guide)
        bodies = " ".join(step["body"] for step in guide["steps"])
        self.assertIn("cannot look up the old password", bodies)
        self.assertIn("one-time link to create a new password", bodies)
        self.assertIn("Email create-password link", bodies)
        self.assertIn("temporary password", bodies)

    def test_email_guides_explain_collapsing_sections(self):
        family = guide_for("family-email")
        bulk = guide_for("parent-emails")
        self.assertIn("Collapse sections", [step["title"] for step in family["steps"]])
        self.assertIn("Collapse sections", [step["title"] for step in bulk["steps"]])
        family_text = family["intro"] + " " + " ".join(step["body"] for step in family["steps"])
        bulk_text = bulk["intro"] + " " + " ".join(step["body"] for step in bulk["steps"])
        self.assertIn("fold it up", family_text)
        self.assertIn("Compose starts open", family_text)
        self.assertIn("Recipients start open", bulk_text)
        self.assertIn("Expand all", bulk_text)

    def test_family_applications_guide_covers_after_care_add(self):
        guide = guide_for("family-applications")
        bodies = " ".join(step["body"] for step in guide["steps"])
        self.assertIn("+ After-care", bodies)
        self.assertIn("No new enrollment application", bodies)

    def test_parent_applications_guide_explains_after_care(self):
        guide = guide_for("parent-applications")
        titles = [step["title"] for step in guide["steps"]]
        self.assertEqual(titles[0], "Find your child")
        self.assertEqual(titles[1], "Click + After-care")
        self.assertEqual(titles[2], "Confirm")
        bodies = " ".join(step["body"] for step in guide["steps"])
        self.assertIn("before-care waitlist", bodies)
        self.assertIn("does not change", bodies)

    def test_parent_context_does_not_use_staff_dashboard_guide(self):
        guide = page_guide_from_context({"portal_area": "parent", "parent_page_slug": "dashboard"})
        self.assertIsNone(guide)
        apps = page_guide_from_context({"portal_area": "parent", "parent_page_slug": "applications"})
        self.assertEqual(apps["key"], "parent-applications")
        contacts = page_guide_from_context(
            {"portal_area": "parent", "parent_page_slug": "emergency-contacts"}
        )
        self.assertEqual(contacts["key"], "parent-emergency-contacts")
        bodies = " ".join(step["body"] for step in contacts["steps"])
        self.assertIn("Staff gets an email", contacts["steps"][2]["title"])
        self.assertIn("add or delete", bodies.lower())

    def test_context_picks_family_tab_over_families_slug(self):
        guide = page_guide_from_context(
            {"staff_page_slug": "families", "family_tab": "billing", "portal_area": "staff"}
        )
        self.assertEqual(guide["key"], "family-billing")
        self.assertIn("+ Add charge", guide["steps"][1]["body"])


class StaffPageGuideViewTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.unit = PortalUnit.objects.create(slug="school-18", name="School 18", is_active=True)
        self.family = PortalFamily.objects.create(unit=self.unit, slug="jacobs", name="Jacobs")
        self.admin_user = User.objects.create_user(username="admin:yeaadmin", password="AdminPass123")
        self.admin_account = PortalStaffAccount.objects.create(
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

    def _login(self, user, area):
        self.client.force_login(user)
        session = self.client.session
        session[PORTAL_AUTH_SESSION_KEY] = area
        session.save()

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_attendance_page_has_clickable_how_to(self):
        self._login(self.staff_user, "staff")
        page = self.client.get(reverse("portal_staff_page", kwargs={"page": "attendance"}))
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, "How to use this page")
        self.assertContains(page, "How to take attendance")
        self.assertContains(page, "Check one child in")
        self.assertContains(page, "Check a group in")
        self.assertContains(page, "Check out or mark absent")
        self.assertContains(page, "Read medical icons")
        self.assertContains(page, 'data-open-page-guide')
        self.assertContains(page, "portal-page-guide.js")

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_waitlist_page_has_after_care_walkthrough(self):
        self._login(self.staff_user, "staff")
        page = self.client.get(reverse("portal_staff_page", kwargs={"page": "waitlist"}))
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, "How to use this page")
        self.assertContains(page, "Find the waitlisted child")
        self.assertContains(page, "Add After-care")
        self.assertContains(page, "Confirm to save")
        self.assertContains(page, 'data-open-page-guide')
        self.assertContains(page, "portal-page-guide.js")

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_admin_can_open_staff_attendance_with_same_login(self):
        self._login(self.admin_user, "admin")
        switch = self.client.get(reverse("portal_area_switch", kwargs={"area": "staff"}))
        self.assertEqual(switch.status_code, 302)
        attendance = self.client.get(reverse("portal_staff_page", kwargs={"page": "attendance"}))
        self.assertEqual(attendance.status_code, 200)
        self.assertContains(attendance, "How to take attendance")
        self.assertContains(attendance, "Staff menu")

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_admin_dashboard_explains_staff_switch(self):
        self._login(self.admin_user, "admin")
        page = self.client.get(reverse("portal_admin_page", kwargs={"page": "dashboard"}))
        self.assertContains(page, "no extra staff account")
        self.assertContains(page, reverse("portal_area_switch", kwargs={"area": "staff"}))
        self.assertContains(page, "How to use this page")
        self.assertContains(page, "Open staff without a second account")

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_staff_access_page_says_not_to_create_second_account(self):
        self._login(self.admin_user, "admin")
        page = self.client.get(reverse("portal_admin_page", kwargs={"page": "staff"}))
        self.assertContains(page, "Do not create a second staff account")
        self.assertNotContains(page, "they are separate accounts even if the same person uses both")

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_family_billing_has_its_own_guide(self):
        self._login(self.staff_user, "staff")
        page = self.client.get(
            reverse("portal_staff_family_billing", kwargs={"family_slug": "jacobs"})
        )
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, "How to use family billing")
        self.assertNotContains(page, "How to use the families list")

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_parent_portal_does_not_show_staff_how_to(self):
        User = get_user_model()
        from portal.models import PortalParentAccount

        parent_user = User.objects.create_user(username="parent:jacobs", password="ParentPass123")
        PortalParentAccount.objects.create(user=parent_user, family=self.family)
        self._login(parent_user, "parent")
        page = self.client.get(reverse("portal_parent_page", kwargs={"page": "dashboard"}))
        self.assertEqual(page.status_code, 200)
        self.assertNotContains(page, "How to use this page")
        self.assertNotContains(page, "portal-page-guide.js")
        self.assertNotContains(page, "How to start the day")

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_parent_applications_page_has_after_care_walkthrough(self):
        User = get_user_model()
        from portal.models import PortalParentAccount

        parent_user = User.objects.create_user(username="parent:jacobs", password="ParentPass123")
        PortalParentAccount.objects.create(user=parent_user, family=self.family)
        self._login(parent_user, "parent")
        page = self.client.get(reverse("portal_parent_page", kwargs={"page": "help"}))
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, "Click + After-care")
        self.assertContains(page, "does not change")
        self.assertNotContains(page, "How to use this page")
        self.assertNotContains(page, "portal-page-guide.js")
        apps = self.client.get(reverse("portal_parent_page", kwargs={"page": "applications"}))
        self.assertEqual(apps.status_code, 200)
        self.assertNotContains(apps, "How to use this page")
        self.assertNotContains(apps, "data-open-page-guide")

    def test_portal_admin_keeps_full_permissions_in_staff_area(self):
        billing = billing_permissions_for_staff(self.admin_account, portal_area="staff")
        self.assertTrue(billing["can_add_charge"])
        self.assertTrue(billing["can_add_credit"])
        apps = application_permissions_for_staff(self.admin_account, portal_area="staff")
        self.assertTrue(apps["can_approve_applications"])
        self.assertTrue(apps["can_approve_waitlist"])
