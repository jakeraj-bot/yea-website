"""Shared printable report header repeats on every page."""

from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from portal.models import PortalChild, PortalFamily, PortalStaffAccount, PortalUnit
from portal.staff_auth import PORTAL_AUTH_SESSION_KEY

REPO_ROOT = Path(__file__).resolve().parents[2]
PORTAL_CSS = REPO_ROOT / "static" / "css" / "portal.css"
REPORT_PRINT_JS = REPO_ROOT / "static" / "js" / "portal-report-print.js"
REPORT_PRINT_CHROME = REPO_ROOT / "templates" / "portal" / "includes" / "report_print_chrome.html"
BASE_TEMPLATE = REPO_ROOT / "templates" / "portal" / "base.html"
ATTENDANCE_PRINT_HEADER = REPO_ROOT / "templates" / "portal" / "staff" / "includes" / "attendance_sheet_print_header.html"


class ReportPrintHeaderSourceTests(SimpleTestCase):
    def test_shared_print_css_repeats_logo_header_and_page_chrome(self):
        css = PORTAL_CSS.read_text()
        print_start = css.find("@media print {\n  @page")
        self.assertGreaterEqual(print_start, 0)
        print_css = css[print_start:]
        self.assertIn("@page report-print", print_css)
        self.assertIn("page: report-print", print_css)
        self.assertIn("page: attendance-print", print_css)
        self.assertIn('content: "Page " counter(page)', print_css)
        self.assertIn('content: "Printed"', print_css)
        self.assertIn("display: table-header-group", print_css)
        self.assertIn(".portal-report-print-frame", print_css)
        self.assertIn(".portal-print-title-row", print_css)
        self.assertIn(".portal-medical-report-sheet:has(.portal-print-title-row) > .portal-medical-report-header", print_css)
        self.assertIn("display: none !important", print_css)

        screen = css.split("@media print {\n  @page", 1)[0]
        self.assertIn(".portal-print-title-row {\n  display: none;\n}", screen)
        self.assertIn(".portal-report-print-frame", screen)

    def test_shared_print_template_and_script_are_wired(self):
        chrome = REPORT_PRINT_CHROME.read_text()
        self.assertIn("@page report-print", chrome)
        self.assertIn("counter(page)", chrome)
        self.assertIn("Printed", chrome)
        self.assertIn("portal-report-print.js", chrome)

        base = BASE_TEMPLATE.read_text()
        self.assertIn("portal/includes/report_print_chrome.html", base)

        js = REPORT_PRINT_JS.read_text()
        self.assertIn("portal-print-title-row", js)
        self.assertIn("portal-attendance-print-sheet", js)
        self.assertIn("portalWrapReportSheetsForPrint", js)
        self.assertIn("insertBefore", js)
        self.assertIn("beforeprint", js)

        attendance = ATTENDANCE_PRINT_HEADER.read_text()
        self.assertIn("portal-print-title-row", attendance)
        self.assertIn("yea-logo.png", attendance)


class ReportPrintHeaderPageTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.unit = PortalUnit.objects.create(slug="school-18", name="School 18", is_active=True)
        self.family = PortalFamily.objects.create(
            unit=self.unit,
            slug="jacobs",
            name="Jacobs",
            billing_type="Private pay",
            status="Active",
        )
        PortalChild.objects.create(
            family=self.family,
            name="Jordan Jacobs",
            school="Lincoln Elementary",
            is_active=True,
        )
        self.staff = User.objects.create_user(username="staff:print-header", password="StaffPass123!")
        PortalStaffAccount.objects.create(
            user=self.staff,
            unit=self.unit,
            display_name="Print Staff",
            role="Unit director",
            is_active=True,
        )
        self.admin = User.objects.create_user(username="admin:print-header", password="AdminPass123!")
        PortalStaffAccount.objects.create(
            user=self.admin,
            unit=self.unit,
            display_name="Print Admin",
            role="Organization admin",
            all_units_access=True,
            is_active=True,
        )

    def _login(self, user, area):
        self.client.force_login(user)
        session = self.client.session
        session[PORTAL_AUTH_SESSION_KEY] = area
        session.save()

    def _assert_shared_chrome(self, response, *, attendance=False):
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn("report-print-page-style", html)
        self.assertIn("portal-report-print.js", html)
        self.assertIn("counter(page)", html)
        self.assertIn("yea-logo.png", html)
        self.assertEqual(html.count("portal-medical-report-header"), 1)
        if attendance:
            self.assertIn("portal-print-title-row", html)
            self.assertIn("attendance-print", html)
            self.assertIn("portal-attendance-print-sheet", html)
        else:
            self.assertNotIn("portal-print-title-row", html)

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_staff_reports_include_shared_print_chrome_once(self):
        self._login(self.staff, "staff")
        pages = [
            (reverse("portal_staff_member_information_report"), False),
            (reverse("portal_staff_emergency_contact_report"), False),
            (reverse("portal_staff_medical_report"), False),
            (reverse("portal_staff_pickup_report"), False),
            (reverse("portal_staff_weekly_attendance_report"), True),
            (reverse("portal_staff_signout_blank"), False),
        ]
        for url, attendance in pages:
            with self.subTest(url=url):
                self._assert_shared_chrome(self.client.get(url), attendance=attendance)

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_admin_reports_include_shared_print_chrome_once(self):
        self._login(self.admin, "admin")
        printable = [
            reverse("portal_admin_member_information_report"),
            reverse("portal_admin_emergency_contact_report"),
            reverse("portal_admin_financial_report"),
            reverse("portal_admin_data_report", kwargs={"report_slug": "payments"}),
        ]
        for url in printable:
            with self.subTest(url=url):
                self._assert_shared_chrome(self.client.get(url), attendance=False)

        hub = self.client.get(reverse("portal_admin_page", kwargs={"page": "reports"}))
        self.assertEqual(hub.status_code, 200)
        self.assertContains(hub, "report-print-page-style")
        self.assertContains(hub, "portal-report-print.js")
        self.assertNotContains(hub, "portal-medical-report-header")
