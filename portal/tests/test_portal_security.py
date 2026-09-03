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
        ]
        for url in urls:
            with self.subTest(url=url):
                response = self.client.get(url)
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
