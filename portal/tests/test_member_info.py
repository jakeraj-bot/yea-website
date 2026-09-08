from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from django.contrib.auth import authenticate

from portal.member_admin import parent_email_for_family, reset_parent_portal_password, update_family_member_info
from portal.models import PortalFamily, PortalParentAccount, PortalProfileChangeRequest, PortalStaffAccount, PortalUnit
from portal.staff_auth import PORTAL_AUTH_SESSION_KEY
from portal.tests.test_family_units import _make_application
from portal.usernames import resolve_auth_username


class UpdateFamilyMemberInfoTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.unit = PortalUnit.objects.create(slug="school-18", name="School 18", is_active=True)
        self.family = PortalFamily.objects.create(
            unit=self.unit,
            slug="orengo",
            name="Orengo",
            primary_contact="Alize Parent",
            status="Active",
        )
        self.app = _make_application(self.family)
        self.app.student_first_name = "Alize"
        self.app.student_last_name = "Orengo"
        self.app.primary_email = "wrong@example.com"
        self.app.primary_email_address = "wrong@example.com"
        self.app.status = "approved"
        self.app.save()
        self.parent_user = User.objects.create_user(
            username="parent:orengo",
            password="ParentPass123",
            email="wrong@example.com",
            first_name="Alize",
            last_name="Parent",
        )
        PortalParentAccount.objects.create(user=self.parent_user, family=self.family)

    def test_updates_login_email_and_application_after_approval(self):
        info, changes = update_family_member_info(
            self.family,
            {
                "family_name": "Orengo",
                "home_address": "12 School St",
                "primary_first_name": "Alize",
                "primary_last_name": "Parent",
                "primary_email": "alize.correct@example.com",
                "primary_phone": "555-0199",
            },
            actor="yeaadmin",
        )
        self.parent_user.refresh_from_db()
        self.app.refresh_from_db()
        self.family.refresh_from_db()
        self.assertEqual(self.parent_user.email, "alize.correct@example.com")
        self.assertEqual(self.app.primary_email, "alize.correct@example.com")
        self.assertEqual(self.app.primary_email_address, "alize.correct@example.com")
        self.assertEqual(self.app.primary_phone, "555-0199")
        self.assertEqual(self.family.primary_contact, "Alize Parent")
        self.assertEqual(parent_email_for_family(self.family), "alize.correct@example.com")
        self.assertEqual(info["primary_email"], "alize.correct@example.com")
        self.assertIn("primary_email", changes)
        audit = PortalProfileChangeRequest.objects.get(account__family=self.family)
        self.assertEqual(audit.status, PortalProfileChangeRequest.STATUS_APPROVED)
        self.assertEqual(audit.reviewed_by, "yeaadmin")
        self.assertEqual(audit.changes["primary_email"]["to"], "alize.correct@example.com")

    def test_rejects_duplicate_email(self):
        other = get_user_model().objects.create_user(
            username="parent:other",
            password="OtherPass123",
            email="taken@example.com",
        )
        other_family = PortalFamily.objects.create(unit=self.unit, slug="other", name="Other")
        PortalParentAccount.objects.create(user=other, family=other_family)
        with self.assertRaises(ValueError) as ctx:
            update_family_member_info(
                self.family,
                {
                    "family_name": "Orengo",
                    "primary_first_name": "Alize",
                    "primary_last_name": "Parent",
                    "primary_email": "taken@example.com",
                },
                actor="staff",
            )
        self.assertIn("already used", str(ctx.exception))
        self.parent_user.refresh_from_db()
        self.assertEqual(self.parent_user.email, "wrong@example.com")

    def test_parent_can_sign_in_with_corrected_email(self):
        update_family_member_info(
            self.family,
            {
                "family_name": "Orengo",
                "primary_first_name": "Alize",
                "primary_last_name": "Parent",
                "primary_email": "alize.correct@example.com",
            },
            actor="yeaadmin",
        )
        stored = resolve_auth_username("parent", "alize.correct@example.com")
        self.assertEqual(stored, "parent:orengo")


class ResetParentPortalPasswordTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.unit = PortalUnit.objects.create(slug="school-18", name="School 18", is_active=True)
        self.family = PortalFamily.objects.create(
            unit=self.unit,
            slug="orengo",
            name="Orengo",
            primary_contact="Alize Parent",
            status="Active",
        )
        self.parent_user = User.objects.create_user(
            username="parent:orengo",
            password="ParentPass123",
            email="alize@example.com",
            first_name="Alize",
            last_name="Parent",
        )
        PortalParentAccount.objects.create(user=self.parent_user, family=self.family)

    def test_sets_new_password_and_logs_without_storing_it(self):
        result = reset_parent_portal_password(
            self.family,
            "NewTempPass123!",
            actor="yeaadmin",
        )
        self.assertEqual(result["username"], "orengo")
        self.assertEqual(result["email"], "alize@example.com")
        self.assertEqual(result["password"], "NewTempPass123!")
        self.parent_user.refresh_from_db()
        self.assertTrue(self.parent_user.check_password("NewTempPass123!"))
        self.assertFalse(self.parent_user.check_password("ParentPass123"))
        self.assertNotEqual(self.parent_user.password, "NewTempPass123!")
        self.assertTrue(self.parent_user.password.startswith("pbkdf2_"))
        audit = PortalProfileChangeRequest.objects.get(account__family=self.family)
        self.assertEqual(audit.reviewed_by, "yeaadmin")
        self.assertEqual(audit.changes, {"parent_password_reset": True})
        self.assertNotIn("NewTempPass123!", str(audit.changes))

    def test_rejects_weak_password(self):
        with self.assertRaises(ValueError):
            reset_parent_portal_password(self.family, "123")
        self.parent_user.refresh_from_db()
        self.assertTrue(self.parent_user.check_password("ParentPass123"))

    def test_generates_password_when_requested(self):
        result = reset_parent_portal_password(self.family, "", actor="staff", generate=True)
        self.assertGreaterEqual(len(result["password"]), 8)
        self.parent_user.refresh_from_db()
        self.assertTrue(self.parent_user.check_password(result["password"]))


class MemberInfoViewTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.unit = PortalUnit.objects.create(slug="school-18", name="School 18", is_active=True)
        self.other_unit = PortalUnit.objects.create(slug="school-26", name="School 26", is_active=True)
        self.family = PortalFamily.objects.create(unit=self.unit, slug="orengo", name="Orengo", status="Active")
        _make_application(self.family)
        self.family.enrollment_applications.update(status="approved", primary_email="wrong@example.com")
        self.parent_user = User.objects.create_user(
            username="parent:orengo",
            password="ParentPass123",
            email="wrong@example.com",
        )
        PortalParentAccount.objects.create(user=self.parent_user, family=self.family)
        self.admin = User.objects.create_user(username="staff:portaladmin", password="AdminPass123")
        PortalStaffAccount.objects.create(
            user=self.admin,
            unit=self.unit,
            display_name="Portal Admin",
            role="Portal admin",
            all_units_access=True,
            is_active=True,
        )
        self.staff = User.objects.create_user(username="staff:unitstaff", password="StaffPass123")
        PortalStaffAccount.objects.create(
            user=self.staff,
            unit=self.unit,
            display_name="Unit Staff",
            role="Unit director",
            all_units_access=False,
            is_active=True,
        )

    def _login(self, user, area):
        self.client.force_login(user)
        session = self.client.session
        session[PORTAL_AUTH_SESSION_KEY] = area
        session.save()

    def _payload(self, email="alize.correct@example.com"):
        return {
            "family_name": "Orengo",
            "home_address": "1 Main St",
            "primary_first_name": "Alize",
            "primary_last_name": "Parent",
            "primary_email": email,
            "primary_phone": "555-0100",
            "secondary_first_name": "",
            "secondary_last_name": "",
            "secondary_email": "",
            "secondary_phone": "",
        }

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_admin_profile_shows_edit_form(self):
        self._login(self.admin, "admin")
        response = self.client.get(reverse("portal_admin_family_detail", kwargs={"family_slug": "orengo"}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Edit member info")
        self.assertContains(response, "Parent login email")
        self.assertContains(response, reverse("portal_admin_family_member_update", kwargs={"family_slug": "orengo"}))
        self.assertContains(response, "portal-sidebar-toggle")
        self.assertContains(response, "yea-portal-sidebar-collapsed")

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_staff_profile_shows_edit_form(self):
        self._login(self.staff, "staff")
        response = self.client.get(reverse("portal_staff_family_detail", kwargs={"family_slug": "orengo"}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Edit member info")
        self.assertContains(response, reverse("portal_staff_family_member_update", kwargs={"family_slug": "orengo"}))

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_admin_can_save_corrected_email(self):
        self._login(self.admin, "admin")
        url = reverse("portal_admin_family_member_update", kwargs={"family_slug": "orengo"})
        response = self.client.post(url, self._payload(), follow=True)
        self.assertEqual(response.status_code, 200)
        self.parent_user.refresh_from_db()
        self.assertEqual(self.parent_user.email, "alize.correct@example.com")
        self.assertContains(response, "Member information saved")

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_staff_can_save_corrected_email(self):
        self._login(self.staff, "staff")
        url = reverse("portal_staff_family_member_update", kwargs={"family_slug": "orengo"})
        response = self.client.post(url, self._payload(), follow=True)
        self.assertEqual(response.status_code, 200)
        self.parent_user.refresh_from_db()
        self.assertEqual(self.parent_user.email, "alize.correct@example.com")

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_parent_cannot_post_member_update(self):
        self.client.force_login(self.parent_user)
        session = self.client.session
        session[PORTAL_AUTH_SESSION_KEY] = "parent"
        session.save()
        url = reverse("portal_admin_family_member_update", kwargs={"family_slug": "orengo"})
        response = self.client.post(url, self._payload())
        self.assertEqual(response.status_code, 302)
        self.assertIn("/portal/staff/login/", response.url)
        self.parent_user.refresh_from_db()
        self.assertEqual(self.parent_user.email, "wrong@example.com")

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_staff_cannot_edit_family_in_another_unit(self):
        other_family = PortalFamily.objects.create(unit=self.other_unit, slug="other", name="Other")
        _make_application(other_family)
        self._login(self.staff, "staff")
        url = reverse("portal_staff_family_member_update", kwargs={"family_slug": "other"})
        response = self.client.post(url, {**self._payload(), "family_name": "Other"})
        self.assertEqual(response.status_code, 302)
        self.assertIn("families", response.url)

    def _reset_url(self, area="admin"):
        name = "portal_admin_family_parent_password" if area == "admin" else "portal_staff_family_parent_password"
        return reverse(name, kwargs={"family_slug": "orengo"})

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_admin_profile_shows_reset_form_without_existing_password(self):
        self._login(self.admin, "admin")
        response = self.client.get(reverse("portal_admin_family_detail", kwargs={"family_slug": "orengo"}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Reset parent password")
        self.assertContains(response, "You cannot see the current password")
        self.assertContains(response, reverse("portal_admin_family_parent_password", kwargs={"family_slug": "orengo"}))
        self.assertNotContains(response, self.parent_user.password)
        self.assertNotContains(response, "ParentPass123")
        self.assertNotContains(response, "pbkdf2_")

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_admin_can_set_temporary_password_shown_once(self):
        self._login(self.admin, "admin")
        response = self.client.post(
            self._reset_url("admin"),
            {"password": "NewTempPass123!", "confirm_password": "NewTempPass123!"},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "NewTempPass123!")
        self.assertContains(response, "orengo")
        self.assertContains(response, "wrong@example.com")
        self.assertContains(response, "copy it now")
        self.assertContains(response, 'id="parent-password-once"')
        self.assertContains(response, "portal-password-once portal-profile-full portal-collapse-skip")
        self.parent_user.refresh_from_db()
        self.assertTrue(self.parent_user.check_password("NewTempPass123!"))
        self.assertFalse(self.parent_user.check_password("ParentPass123"))
        self.assertNotContains(response, self.parent_user.password)

        again = self.client.get(reverse("portal_admin_family_detail", kwargs={"family_slug": "orengo"}))
        self.assertEqual(again.status_code, 200)
        self.assertNotContains(again, "NewTempPass123!")
        self.assertNotContains(again, self.parent_user.password)
        self.assertNotContains(again, "pbkdf2_")

        self.client.logout()
        login_ok = self.client.post(
            reverse("portal_parent_login"),
            {"username": "orengo", "password": "NewTempPass123!"},
        )
        self.assertEqual(login_ok.status_code, 302)
        self.client.logout()
        login_old = self.client.post(
            reverse("portal_parent_login"),
            {"username": "orengo", "password": "ParentPass123"},
        )
        self.assertEqual(login_old.status_code, 200)
        self.assertFalse(authenticate(username="parent:orengo", password="ParentPass123"))

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_staff_can_reset_parent_password(self):
        self._login(self.staff, "staff")
        response = self.client.post(
            self._reset_url("staff"),
            {"password": "StaffResetPass123!", "confirm_password": "StaffResetPass123!"},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "StaffResetPass123!")
        self.parent_user.refresh_from_db()
        self.assertTrue(self.parent_user.check_password("StaffResetPass123!"))

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_parent_cannot_reset_password(self):
        self.client.force_login(self.parent_user)
        session = self.client.session
        session[PORTAL_AUTH_SESSION_KEY] = "parent"
        session.save()
        response = self.client.post(
            self._reset_url("admin"),
            {"password": "HackedPass123!", "confirm_password": "HackedPass123!"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn("/portal/staff/login/", response.url)
        self.parent_user.refresh_from_db()
        self.assertTrue(self.parent_user.check_password("ParentPass123"))

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_staff_cannot_reset_family_in_another_unit(self):
        other_family = PortalFamily.objects.create(unit=self.other_unit, slug="other", name="Other")
        other_user = get_user_model().objects.create_user(username="parent:other", password="OtherPass123")
        PortalParentAccount.objects.create(user=other_user, family=other_family)
        self._login(self.staff, "staff")
        response = self.client.post(
            reverse("portal_staff_family_parent_password", kwargs={"family_slug": "other"}),
            {"password": "NopePass123!", "confirm_password": "NopePass123!"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn("families", response.url)
        other_user.refresh_from_db()
        self.assertTrue(other_user.check_password("OtherPass123"))

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_admin_families_table_keeps_school_and_balance_columns(self):
        self._login(self.admin, "admin")
        response = self.client.get(reverse("portal_admin_page", kwargs={"page": "families"}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "data-col=\"school\"")
        self.assertContains(response, "data-col=\"billing\"")
        self.assertContains(response, "data-col=\"child-balance\"")
        self.assertContains(response, "portal-school-edit-form")
        self.assertContains(response, "portal-row-actions")
        self.assertContains(response, "portal-sidebar-toggle")
