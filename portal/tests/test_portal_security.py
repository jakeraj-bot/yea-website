from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.management import CommandError, call_command
from django.test import TestCase, override_settings
from django.urls import reverse

from enrollment.models import EnrollmentApplication
from portal.member_admin import resolve_family
from portal.models import PortalFamily, PortalParentAccount, PortalStaffAccount, PortalUnit
from portal.staff_auth import staff_accessible_units
from portal.tests.test_family_units import _make_application
from portal.views import _staff_family_profile


class PortalSignupSecurityTests(TestCase):
    def setUp(self):
        cache.clear()
        self.unit = PortalUnit.objects.create(slug="school-18", name="School 18", is_active=True)

    def _payload(self, **overrides):
        data = {
            "family_name": "Spam",
            "your_name": "Bot User",
            "email": "bot@example.com",
            "username": "spamuser",
            "password1": "SecurePass123",
            "password2": "SecurePass123",
            "website": "",
        }
        data.update(overrides)
        return data

    def test_signup_without_application_is_rejected(self):
        response = self.client.post(reverse("portal_parent_signup"), self._payload())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "enrollment application")
        self.assertFalse(PortalFamily.objects.filter(name="Spam").exists())
        self.assertFalse(get_user_model().objects.filter(username__contains="spamuser").exists())

    def test_signup_honeypot_creates_nothing(self):
        family = PortalFamily.objects.create(unit=self.unit, slug="real", name="Real")
        _make_application(family, status="under_review")
        EnrollmentApplication.objects.filter(portal_family=family).update(primary_email="bot@example.com")
        response = self.client.post(
            reverse("portal_parent_signup"),
            self._payload(website="http://spam.test"),
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(get_user_model().objects.filter(username__contains="spamuser").exists())

    def test_signup_with_application_email_succeeds(self):
        family = PortalFamily.objects.create(unit=self.unit, slug="lopez", name="Lopez")
        app = _make_application(family, status="under_review")
        app.primary_email = "parent@example.com"
        app.save(update_fields=["primary_email"])
        response = self.client.post(
            reverse("portal_parent_signup"),
            self._payload(email="parent@example.com", username="lopezparent", family_name="Lopez"),
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(PortalFamily.objects.filter(name="Lopez").count(), 1)
        self.assertTrue(PortalParentAccount.objects.filter(family=family).exists())


class StaffAccessSecurityTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.school_18 = PortalUnit.objects.create(slug="school-18", name="School 18", is_active=True)
        self.school_26 = PortalUnit.objects.create(slug="school-26", name="School 26", is_active=True)
        self.user = User.objects.create_user(username="staff:unitstaff", password="StaffPass123")
        self.account = PortalStaffAccount.objects.create(
            user=self.user,
            unit=self.school_18,
            display_name="Unit Staff",
            role="Unit director",
            is_active=True,
        )

    def test_unit_director_sees_only_assigned_unit(self):
        units = list(staff_accessible_units(self.user))
        self.assertEqual([unit.slug for unit in units], ["school-18"])

    def test_family_lookup_does_not_cross_units(self):
        other = PortalFamily.objects.create(unit=self.school_26, slug="other", name="Other")
        self.assertIsNone(resolve_family(family_id=other.pk, unit=self.school_18))
        self.assertIsNone(resolve_family(family_slug="other", unit=self.school_18))

    def test_live_family_profile_does_not_fall_back_to_demo(self):
        profile = _staff_family_profile("jacobs", unit=self.school_18)
        self.assertIsNone(profile)

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_unauthenticated_parent_post_redirects_to_login(self):
        response = self.client.post(reverse("portal_parent_profile_save"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/portal/login/", response.url)

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_unauthenticated_staff_pages_redirect_to_login(self):
        urls = [
            reverse("portal_staff_page", kwargs={"page": "dashboard"}),
            reverse("portal_staff_page", kwargs={"page": "families"}),
            reverse("portal_staff_family_detail", kwargs={"family_slug": "jacobs"}),
            reverse("portal_staff_medical_report"),
            reverse("portal_staff_incidents_print"),
            reverse("portal_staff_school_bus_report"),
            reverse("portal_staff_family_email", kwargs={"family_slug": "jacobs"}),
        ]
        for url in urls:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 302)
                self.assertIn("/portal/staff/login/", response.url)

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_unauthenticated_school_edit_redirects_to_login(self):
        response = self.client.post(reverse("portal_staff_update_child_school"), {"school": "Lincoln"})
        self.assertEqual(response.status_code, 302)
        self.assertIn("/portal/staff/login/", response.url)

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_unauthenticated_family_email_redirects_to_login(self):
        response = self.client.post(
            reverse("portal_staff_family_email_send", kwargs={"family_slug": "jacobs"}),
            {"subject": "Hi", "body": "Hello"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn("/portal/staff/login/", response.url)


class LoginLockoutTests(TestCase):
    def setUp(self):
        cache.clear()

    @override_settings(PORTAL_LOGIN_RATE_LIMIT=2, PORTAL_LOGIN_RATE_WINDOW_SECONDS=900)
    def test_staff_login_locks_after_repeated_failures(self):
        url = reverse("portal_staff_login")
        self.client.post(url, {"username": "nope", "password": "wrong"})
        self.client.post(url, {"username": "nope", "password": "wrong"})
        response = self.client.post(url, {"username": "nope", "password": "wrong"})
        self.assertContains(response, "Too many sign-in attempts")


class DemoSeedGuardTests(TestCase):
    def test_seed_portal_refuses_without_flag(self):
        with self.assertRaises(CommandError):
            call_command("seed_portal")


class AdminLoginLayoutTests(TestCase):
    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_admin_login_uses_centered_auth_shell(self):
        response = self.client.get(reverse("portal_admin_login"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "portal-shell--auth")
        self.assertContains(response, "portal-auth-card")
        self.assertContains(response, "portal-auth-heading")
        self.assertContains(response, "Portal admin login")
        self.assertNotContains(response, "portal-sidebar")

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_admin_password_reset_uses_centered_auth_shell(self):
        response = self.client.get(reverse("portal_admin_password_reset"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "portal-shell--auth")
        self.assertContains(response, "portal-auth-card")

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_staff_dashboard_keeps_sidebar_shell(self):
        User = get_user_model()
        unit = PortalUnit.objects.create(slug="school-18", name="School 18", is_active=True)
        user = User.objects.create_user(username="staff:layout", password="StaffPass123")
        PortalStaffAccount.objects.create(
            user=user,
            unit=unit,
            display_name="Layout Staff",
            role="Unit director",
            is_active=True,
        )
        self.client.force_login(user)
        session = self.client.session
        session["portal_auth_area"] = "staff"
        session.save()
        response = self.client.get(reverse("portal_staff_page", kwargs={"page": "dashboard"}))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "portal-shell--auth")
        self.assertContains(response, "portal-sidebar")


class PortalAreaSwitchTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.unit = PortalUnit.objects.create(slug="school-18", name="School 18", is_active=True)
        self.admin_user = User.objects.create_user(username="staff:portaladmin", password="AdminPass123")
        PortalStaffAccount.objects.create(
            user=self.admin_user,
            unit=self.unit,
            display_name="Portal Admin",
            role="Portal admin",
            all_units_access=True,
            is_active=True,
        )
        self.staff_user = User.objects.create_user(username="staff:unitstaff", password="StaffPass123")
        PortalStaffAccount.objects.create(
            user=self.staff_user,
            unit=self.unit,
            display_name="Unit Staff",
            role="Unit director",
            all_units_access=False,
            is_active=True,
        )

    def _login_as(self, user, area):
        self.client.force_login(user)
        session = self.client.session
        session["portal_auth_area"] = area
        session.save()

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_portal_admin_opens_staff_without_relogin(self):
        self._login_as(self.admin_user, "admin")
        response = self.client.get(reverse("portal_staff_page", kwargs={"page": "dashboard"}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Staff menu")
        self.assertContains(response, "Admin portal")
        self.assertContains(response, "Switch to admin")
        self.assertContains(response, reverse("portal_area_switch", kwargs={"area": "admin"}))

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_portal_admin_opens_admin_from_staff_session(self):
        self._login_as(self.admin_user, "staff")
        response = self.client.get(reverse("portal_admin_page", kwargs={"page": "dashboard"}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Organization admin")
        self.assertContains(response, "Switch to staff")
        self.assertContains(response, reverse("portal_area_switch", kwargs={"area": "staff"}))

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_portal_admin_switch_links_flip_areas(self):
        self._login_as(self.admin_user, "admin")
        to_staff = self.client.get(reverse("portal_area_switch", kwargs={"area": "staff"}))
        self.assertEqual(to_staff.status_code, 302)
        self.assertEqual(to_staff.url, reverse("portal_staff_page", kwargs={"page": "dashboard"}))
        self.assertEqual(self.client.session["portal_auth_area"], "staff")

        staff_page = self.client.get(to_staff.url)
        self.assertEqual(staff_page.status_code, 200)
        self.assertContains(staff_page, "Staff menu")

        to_admin = self.client.get(reverse("portal_area_switch", kwargs={"area": "admin"}))
        self.assertEqual(to_admin.status_code, 302)
        self.assertEqual(to_admin.url, reverse("portal_admin_page", kwargs={"page": "dashboard"}))
        self.assertEqual(self.client.session["portal_auth_area"], "admin")

        admin_page = self.client.get(to_admin.url)
        self.assertEqual(admin_page.status_code, 200)
        self.assertContains(admin_page, "Admin menu")

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_unit_staff_cannot_open_admin(self):
        self._login_as(self.staff_user, "staff")
        response = self.client.get(reverse("portal_admin_page", kwargs={"page": "dashboard"}))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/portal/admin/login/", response.url)
        switch = self.client.get(reverse("portal_area_switch", kwargs={"area": "admin"}))
        self.assertEqual(switch.status_code, 302)
        self.assertIn("/portal/admin/login/", switch.url)
        staff_page = self.client.get(reverse("portal_staff_page", kwargs={"page": "dashboard"}))
        self.assertEqual(staff_page.status_code, 200)
        self.assertNotContains(staff_page, "Switch to admin")
        self.assertNotContains(staff_page, reverse("portal_area_switch", kwargs={"area": "admin"}))

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_unauthenticated_switch_goes_to_login(self):
        response = self.client.get(reverse("portal_area_switch", kwargs={"area": "staff"}))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/portal/staff/login/", response.url)

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_admin_login_page_switches_signed_in_portal_admin(self):
        self._login_as(self.admin_user, "staff")
        response = self.client.get(reverse("portal_admin_login"))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("portal_admin_page", kwargs={"page": "dashboard"}))
        self.assertEqual(self.client.session["portal_auth_area"], "admin")

    def test_staff_login_resolves_admin_prefixed_portal_admin(self):
        from portal.usernames import resolve_auth_username

        User = get_user_model()
        user = User.objects.create_user(username="admin:yeaadmin", password="AdminPass123")
        PortalStaffAccount.objects.create(
            user=user,
            unit=self.unit,
            display_name="YEA Admin",
            role="Portal admin",
            all_units_access=True,
            is_active=True,
        )
        self.assertEqual(resolve_auth_username("staff", "yeaadmin"), "admin:yeaadmin")
        self.assertEqual(resolve_auth_username("admin", "yeaadmin"), "admin:yeaadmin")
