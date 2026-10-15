from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from enrollment.policies_data import POLICIES
from portal.models import PortalStaffAccount, PortalUnit
from portal.staff_auth import PORTAL_AUTH_SESSION_KEY

REPO_ROOT = Path(__file__).resolve().parents[2]
STAFF_REPORTS_TEMPLATE = REPO_ROOT / "templates" / "portal" / "staff" / "reports.html"
ADMIN_REPORTS_TEMPLATE = REPO_ROOT / "templates" / "portal" / "admin" / "reports.html"


class ApplicationBlankReportTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.unit = PortalUnit.objects.create(slug="school-18", name="School 18", is_active=True)
        self.staff = User.objects.create_user(username="staff:blank-app", password="StaffPass123!")
        PortalStaffAccount.objects.create(
            user=self.staff,
            unit=self.unit,
            display_name="Blank App Staff",
            role="Unit director",
            is_active=True,
        )
        self.admin = User.objects.create_user(username="admin:blank-app", password="AdminPass123!")
        PortalStaffAccount.objects.create(
            user=self.admin,
            unit=self.unit,
            display_name="Blank App Admin",
            role="Organization admin",
            all_units_access=True,
            is_active=True,
        )

    def _login(self, user, area):
        self.client.force_login(user)
        session = self.client.session
        session[PORTAL_AUTH_SESSION_KEY] = area
        session.save()

    def _assert_blank_packet(self, response):
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.get("Location"))
        self.assertContains(response, "Enrollment application")
        self.assertContains(response, "Program &amp; location")
        self.assertContains(response, "Family information")
        self.assertContains(response, "Primary parent/guardian")
        self.assertContains(response, "Student information")
        self.assertContains(response, "Medical information")
        self.assertContains(response, "Emergency contacts")
        self.assertContains(response, "Policies &amp; signatures")
        self.assertContains(response, "Print / Save PDF")
        self.assertContains(response, "portal-no-print")
        self.assertContains(response, "yea-logo.png")
        self.assertContains(response, "portal-application-blank-sheet")
        self.assertNotContains(response, "Submit application")
        self.assertNotContains(response, reverse("apply"))
        self.assertNotContains(response, "Jordan Jacobs")
        self.assertNotContains(response, 'id="apply-policies"')
        for policy in POLICIES:
            self.assertContains(response, policy["title"])

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_staff_blank_application_is_printable_packet_not_apply(self):
        self._login(self.staff, "staff")
        url = reverse("portal_staff_application_blank")
        self.assertEqual(url, "/portal/staff/reports/application-blank/")
        response = self.client.get(url)
        self._assert_blank_packet(response)
        self.assertContains(response, reverse("portal_staff_page", kwargs={"page": "reports"}))

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_admin_blank_application_is_printable_packet_not_apply(self):
        self._login(self.admin, "admin")
        url = reverse("portal_admin_application_blank")
        self.assertEqual(url, "/portal/admin/reports/print/application-blank/")
        response = self.client.get(url)
        self._assert_blank_packet(response)
        self.assertContains(response, reverse("portal_admin_page", kwargs={"page": "reports"}))

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_staff_reports_hub_opens_blank_application_not_apply(self):
        self._login(self.staff, "staff")
        hub = self.client.get(reverse("portal_staff_page", kwargs={"page": "reports"}))
        self.assertEqual(hub.status_code, 200)
        self.assertContains(hub, "Application (blank)")
        self.assertContains(hub, reverse("portal_staff_application_blank"))
        self.assertNotContains(hub, reverse("apply"))
        self.assertNotContains(hub, "Open enrollment form")
        template = STAFF_REPORTS_TEMPLATE.read_text()
        self.assertIn("portal_staff_application_blank", template)
        self.assertNotIn("{% url 'apply' %}", template)

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_admin_reports_hub_opens_blank_application(self):
        self._login(self.admin, "admin")
        hub = self.client.get(reverse("portal_admin_page", kwargs={"page": "reports"}))
        self.assertEqual(hub.status_code, 200)
        self.assertContains(hub, "Application (blank)")
        self.assertContains(hub, reverse("portal_admin_application_blank"))
        self.assertNotContains(hub, reverse("apply"))
        template = ADMIN_REPORTS_TEMPLATE.read_text()
        self.assertIn("{% elif report.slug == 'application-blank' %}", template)
        self.assertIn("portal_admin_application_blank", template)

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_public_apply_flow_still_opens(self):
        apply_page = self.client.get(reverse("apply"))
        self.assertEqual(apply_page.status_code, 200)
        self.assertContains(apply_page, "Apply")
        family_step = self.client.get(reverse("enrollment_apply", kwargs={"step": "family"}))
        self.assertEqual(family_step.status_code, 200)
