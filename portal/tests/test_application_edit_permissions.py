from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from portal.models import PortalFamily, PortalStaffAccount, PortalUnit
from portal.staff_auth import (
    PORTAL_AUTH_SESSION_KEY,
    application_permissions_for_staff,
    can_edit_enrollment_application,
    is_portal_admin,
)
from portal.tests.test_family_units import _make_application


@override_settings(PORTAL_PREVIEW_MODE=False)
class ApplicationEditPermissionTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.unit = PortalUnit.objects.create(
            slug="school-18",
            name="School 18",
            program_type="after_school",
            is_active=True,
        )
        self.family = PortalFamily.objects.create(unit=self.unit, slug="rivera", name="Rivera")
        self.app = _make_application(self.family, status="under_review")
        self.app_slug = str(self.app.reference)

        self.admin_user = User.objects.create_user(
            username="staff:partneradmin",
            password="AdminPass123",
            is_staff=True,
            is_superuser=False,
        )
        self.admin_account = PortalStaffAccount.objects.create(
            user=self.admin_user,
            unit=self.unit,
            display_name="Partner Admin",
            role="Portal admin",
            all_units_access=True,
            is_active=True,
        )
        self.pd_user = User.objects.create_user(username="staff:pduser", password="StaffPass123")
        self.pd_account = PortalStaffAccount.objects.create(
            user=self.pd_user,
            unit=self.unit,
            display_name="Program Director",
            role="Program director",
            can_approve_applications=True,
            can_approve_waitlist=True,
            is_active=True,
        )
        self.desk_user = User.objects.create_user(username="staff:frontdesk", password="StaffPass123")
        self.desk_account = PortalStaffAccount.objects.create(
            user=self.desk_user,
            unit=self.unit,
            display_name="Front Desk",
            role="Front desk staff",
            can_approve_applications=True,
            can_approve_waitlist=True,
            is_active=True,
        )
        self.staff_user = User.objects.create_user(username="staff:unitstaff", password="StaffPass123")
        self.staff_account = PortalStaffAccount.objects.create(
            user=self.staff_user,
            unit=self.unit,
            display_name="Unit Staff",
            role="Unit staff",
            can_approve_applications=False,
            is_active=True,
        )
        self.super_user = User.objects.create_user(
            username="staff:yeaadmin",
            password="AdminPass123",
            is_staff=True,
            is_superuser=True,
        )
        PortalStaffAccount.objects.create(
            user=self.super_user,
            unit=self.unit,
            display_name="YEA Super Admin",
            role="Portal admin",
            all_units_access=True,
            is_active=True,
        )

    def _login(self, user, area):
        self.client.force_login(user)
        session = self.client.session
        session[PORTAL_AUTH_SESSION_KEY] = area
        if area == "staff":
            session["staff_unit_slug"] = self.unit.slug
        session.save()

    def _edit_post(self, first_name="Edited"):
        return {
            "action": "update_application",
            "app_slug": self.app_slug,
            "student_first_name": first_name,
            "student_last_name": self.app.student_last_name,
            "student_school": self.app.student_school,
            "student_grade": self.app.student_grade,
            "family_name": self.app.family_name,
            "primary_first_name": self.app.primary_first_name,
            "primary_last_name": self.app.primary_last_name,
            "primary_email": self.app.primary_email,
            "primary_phone": self.app.primary_phone,
            "home_address": self.app.home_address,
            "program": self.app.program,
            "payment_method": self.app.payment_method,
            "payment_plan": self.app.payment_plan,
        }

    def test_helper_grants_portal_admin_and_program_director_not_front_desk(self):
        self.assertFalse(self.admin_user.is_superuser)
        self.assertTrue(is_portal_admin(self.admin_user))
        self.assertTrue(can_edit_enrollment_application(self.admin_account, "admin"))
        self.assertTrue(can_edit_enrollment_application(self.admin_account, "staff"))
        self.assertTrue(can_edit_enrollment_application(self.pd_account, "staff"))
        self.assertFalse(can_edit_enrollment_application(self.desk_account, "staff"))
        self.assertFalse(can_edit_enrollment_application(self.staff_account, "staff"))
        self.assertTrue(application_permissions_for_staff(self.admin_account, "staff")["can_edit_applications"])
        self.assertTrue(application_permissions_for_staff(self.pd_account, "staff")["can_edit_applications"])
        self.assertFalse(application_permissions_for_staff(self.desk_account, "staff")["can_edit_applications"])
        self.assertFalse(application_permissions_for_staff(self.staff_account, "staff")["can_edit_applications"])

    def test_portal_admin_sees_edit_on_admin_approve_page(self):
        self._login(self.admin_user, "admin")
        page = self.client.get(
            reverse("portal_admin_application_detail", kwargs={"app_slug": self.app_slug})
        )
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, "Edit application")
        self.assertContains(page, 'id="edit-application-panel-')
        self.assertContains(page, "Save application changes")
        self.assertContains(page, "Approve details")
        self.assertContains(page, "Member start date")
        self.assertTrue(page.context["can_edit_applications"])

    def test_portal_admin_sees_edit_on_staff_approve_page(self):
        self._login(self.admin_user, "staff")
        page = self.client.get(
            reverse("portal_staff_application_detail", kwargs={"app_slug": self.app_slug})
        )
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, "Edit application")
        self.assertContains(page, "Save application changes")
        self.assertContains(page, reverse("portal_staff_application_review", kwargs={"app_slug": self.app_slug}))
        self.assertNotContains(page, "Delete this application from the portal?")
        self.assertTrue(page.context["can_edit_applications"])

    def test_program_director_sees_edit_on_staff_approve_page(self):
        self._login(self.pd_user, "staff")
        page = self.client.get(
            reverse("portal_staff_application_detail", kwargs={"app_slug": self.app_slug})
        )
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, "Edit application")
        self.assertContains(page, "Save application changes")
        self.assertTrue(page.context["can_edit_applications"])

    def test_front_desk_and_unit_staff_do_not_see_edit(self):
        for user in (self.desk_user, self.staff_user):
            with self.subTest(user=user.username):
                self._login(user, "staff")
                page = self.client.get(
                    reverse("portal_staff_application_detail", kwargs={"app_slug": self.app_slug})
                )
                self.assertEqual(page.status_code, 200)
                self.assertNotContains(page, 'href="#edit-application-panel-')
                self.assertNotContains(page, 'id="edit-application-panel-')
                self.assertNotContains(page, "Save application changes")
                self.assertFalse(page.context["can_edit_applications"])

    def test_superuser_still_sees_edit_on_admin_approve_page(self):
        self._login(self.super_user, "admin")
        page = self.client.get(
            reverse("portal_admin_application_detail", kwargs={"app_slug": self.app_slug})
        )
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, "Edit application")
        self.assertTrue(self.super_user.is_superuser)

    def test_portal_admin_can_save_edit_from_staff_approve(self):
        self._login(self.admin_user, "staff")
        response = self.client.post(
            reverse("portal_staff_application_review", kwargs={"app_slug": self.app_slug}),
            self._edit_post("PartnerEdit"),
        )
        self.assertEqual(response.status_code, 302)
        self.app.refresh_from_db()
        self.assertEqual(self.app.student_first_name, "PartnerEdit")

    def test_program_director_can_save_edit_from_staff_approve(self):
        self._login(self.pd_user, "staff")
        response = self.client.post(
            reverse("portal_staff_application_review", kwargs={"app_slug": self.app_slug}),
            self._edit_post("DirectorEdit"),
        )
        self.assertEqual(response.status_code, 302)
        self.app.refresh_from_db()
        self.assertEqual(self.app.student_first_name, "DirectorEdit")

    def test_front_desk_cannot_post_application_edit(self):
        self._login(self.desk_user, "staff")
        response = self.client.post(
            reverse("portal_staff_application_review", kwargs={"app_slug": self.app_slug}),
            self._edit_post("DeskEdit"),
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "You don't have permission to edit this application.")
        self.app.refresh_from_db()
        self.assertEqual(self.app.student_first_name, "Ada")

    def test_unit_staff_cannot_post_application_edit(self):
        self._login(self.staff_user, "staff")
        self.client.post(
            reverse("portal_staff_application_review", kwargs={"app_slug": self.app_slug}),
            self._edit_post("StaffEdit"),
        )
        self.app.refresh_from_db()
        self.assertEqual(self.app.student_first_name, "Ada")

    def test_portal_admin_can_save_edit_from_admin_member_ops(self):
        self._login(self.admin_user, "admin")
        response = self.client.post(reverse("portal_admin_member_ops"), self._edit_post("AdminOpsEdit"))
        self.assertEqual(response.status_code, 302)
        self.app.refresh_from_db()
        self.assertEqual(self.app.student_first_name, "AdminOpsEdit")

    def test_family_applications_tab_follows_same_edit_rule(self):
        self._login(self.admin_user, "staff")
        page = self.client.get(
            reverse("portal_staff_family_applications", kwargs={"family_slug": self.family.slug})
        )
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, 'href="#edit-application-panel-')
        self.assertContains(page, "Save application changes")

        self._login(self.desk_user, "staff")
        desk = self.client.get(
            reverse("portal_staff_family_applications", kwargs={"family_slug": self.family.slug})
        )
        self.assertEqual(desk.status_code, 200)
        self.assertNotContains(desk, "Save application changes")

    def test_program_director_does_not_gain_django_admin(self):
        self.assertFalse(is_portal_admin(self.pd_user))
        self.assertFalse(self.pd_user.is_staff)
        self.assertFalse(self.pd_user.is_superuser)
        self._login(self.pd_user, "staff")
        home = self.client.get("/admin/")
        self.assertEqual(home.status_code, 302)
        self.assertIn("/admin/login/", home.url)
        admin_portal = self.client.get(reverse("portal_admin_page", kwargs={"page": "dashboard"}))
        self.assertEqual(admin_portal.status_code, 302)
        self.assertIn("/portal/admin/login/", admin_portal.url)

    def test_front_desk_does_not_gain_django_admin(self):
        self.assertFalse(self.desk_user.is_staff)
        self.assertFalse(self.desk_user.is_superuser)
        self._login(self.desk_user, "staff")
        home = self.client.get("/admin/")
        self.assertEqual(home.status_code, 302)
        self.assertIn("/admin/login/", home.url)

    def test_opening_edit_application_does_not_grant_django_superuser(self):
        self.assertFalse(self.admin_user.is_superuser)
        self._login(self.admin_user, "admin")
        page = self.client.get(
            reverse("portal_admin_application_detail", kwargs={"app_slug": self.app_slug})
        )
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, "Edit application")
        self.admin_user.refresh_from_db()
        self.assertFalse(self.admin_user.is_superuser)
