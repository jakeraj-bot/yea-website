"""Regression tests for portal section collapse.

Member-information and emergency-contact CSS were mashed together and dropped the
closing brace on `.portal-member-info-table td`. That swallowed the rest of
portal.css, so `.portal-collapse.is-collapsed .portal-collapse-body { display: none }`
never applied and every portal section stayed open.
"""

from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from portal.models import PortalFamily, PortalStaffAccount, PortalUnit
from portal.staff_auth import PORTAL_AUTH_SESSION_KEY

REPO_ROOT = Path(__file__).resolve().parents[2]
PORTAL_CSS = REPO_ROOT / "static" / "css" / "portal.css"
PORTAL_COLLAPSE_JS = REPO_ROOT / "static" / "js" / "portal-collapse.js"
ADMIN_REPORTS_TEMPLATE = REPO_ROOT / "templates" / "portal" / "admin" / "reports.html"


def _css_rule_depths(css: str):
    """Return (selector, depth, line) for each `{` that opens a rule or at-rule."""
    stack = []
    rules = []
    line = 1
    i = 0
    in_s = in_d = in_c = False
    while i < len(css):
        ch = css[i]
        nxt = css[i + 1] if i + 1 < len(css) else ""
        if ch == "\n":
            line += 1
        if in_c:
            if ch == "*" and nxt == "/":
                in_c = False
                i += 2
                continue
            i += 1
            continue
        if in_s:
            if ch == "\\":
                i += 2
                continue
            if ch == "'":
                in_s = False
            i += 1
            continue
        if in_d:
            if ch == "\\":
                i += 2
                continue
            if ch == '"':
                in_d = False
            i += 1
            continue
        if ch == "/" and nxt == "*":
            in_c = True
            i += 2
            continue
        if ch == "'":
            in_s = True
            i += 1
            continue
        if ch == '"':
            in_d = True
            i += 1
            continue
        if ch == "{":
            start = css.rfind("\n", 0, i)
            header = css[start + 1 : i].strip()
            rules.append((header, len(stack), line))
            stack.append(line)
            i += 1
            continue
        if ch == "}":
            if not stack:
                raise AssertionError(f"Extra closing brace in portal.css at line {line}")
            stack.pop()
            i += 1
            continue
        i += 1
    if stack:
        raise AssertionError(f"Unclosed CSS block(s) in portal.css starting at line(s) {stack}")
    return rules


class PortalCollapseCssTests(SimpleTestCase):
    def test_portal_css_braces_are_balanced(self):
        css = PORTAL_CSS.read_text()
        rules = _css_rule_depths(css)
        self.assertTrue(rules)
        member_info = [
            rule
            for rule in rules
            if ".portal-member-info-table td" in rule[0] or rule[0].endswith(".portal-member-info-table td")
        ]
        self.assertTrue(member_info, "member-info table cells must be a closed CSS rule")
        self.assertEqual(member_info[0][1], 0)

    def test_collapsed_body_is_hidden_on_screen_not_only_in_print(self):
        css = PORTAL_CSS.read_text()
        rules = _css_rule_depths(css)
        hide_rules = [
            rule
            for rule in rules
            if ".portal-collapse.is-collapsed .portal-collapse-body" in rule[0]
        ]
        self.assertTrue(hide_rules)
        screen_hide = [rule for rule in hide_rules if rule[1] == 0]
        self.assertEqual(
            len(screen_hide),
            1,
            "collapse hide must be a top-level screen rule so sections can close",
        )
        print_show = [rule for rule in hide_rules if rule[1] == 1 and "@media print" in css]
        self.assertTrue(print_show)

        hide_line = screen_hide[0][2]
        snippet = "\n".join(css.splitlines()[hide_line - 1 : hide_line + 3])
        self.assertIn("display: none", snippet)


class PortalCollapseScriptTests(SimpleTestCase):
    def test_script_skips_report_filters_without_skipping_every_card(self):
        source = PORTAL_COLLAPSE_JS.read_text()
        self.assertIn('card.classList.contains("portal-collapse-skip")', source)
        self.assertIn('card.classList.contains("portal-report-filter-card")', source)
        self.assertIn('card.classList.contains("portal-school-bus-picker")', source)
        self.assertIn('content.querySelectorAll(".card")', source)
        self.assertIn("pageState[key] : true", source)
        self.assertIn("Expand all", source)
        self.assertIn("Collapse all", source)

    def test_admin_reports_hub_does_not_mash_member_and_emergency_ifs(self):
        template = ADMIN_REPORTS_TEMPLATE.read_text()
        self.assertIn("{% if report.slug == 'member-information' %}", template)
        self.assertIn("{% elif report.slug == 'emergency-contacts' %}", template)
        self.assertNotIn(
            "{% if report.slug == 'member-information' %}\n        "
            "<a class=\"btn btn-primary btn-sm\" href=\"{% url 'portal_admin_member_information_report' %}\">"
            "Preview &amp; print</a>\n        {% if report.slug == 'emergency-contacts' %}",
            template,
        )


class PortalCollapsePageTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.unit = PortalUnit.objects.create(slug="school-18", name="School 18", is_active=True)
        self.family = PortalFamily.objects.create(
            unit=self.unit,
            slug="jacobs",
            name="Jacobs",
            primary_contact="Pat Jacobs",
            status="Active",
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
        self.client.force_login(self.admin)
        session = self.client.session
        session[PORTAL_AUTH_SESSION_KEY] = "admin"
        session.save()

    def _assert_collapse_ready(self, response, *, skip_snippets=(), must_not_skip=()):
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "portal-collapse.js")
        self.assertContains(response, "portal.css?v=")
        html = response.content.decode()
        for snippet in skip_snippets:
            self.assertIn(snippet, html)
        for snippet in must_not_skip:
            self.assertNotIn(snippet, html)

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_hub_family_and_settings_pages_load_collapse_script(self):
        reports = self.client.get(reverse("portal_admin_page", kwargs={"page": "reports"}))
        self._assert_collapse_ready(reports)
        self.assertContains(reports, reverse("portal_admin_member_information_report"))
        self.assertContains(reports, reverse("portal_admin_emergency_contact_report"))
        self.assertContains(reports, 'class="card portal-report-card"')
        self.assertNotContains(reports, "portal-collapse-skip")

        family = self.client.get(reverse("portal_admin_family_detail", kwargs={"family_slug": "jacobs"}))
        self._assert_collapse_ready(family)
        self.assertContains(family, "<h2>Emergency contacts</h2>")
        self.assertContains(family, "<h2>Email parent</h2>")
        self.assertContains(family, "portal-profile-full portal-collapse-skip")
        self.assertNotContains(family, "portal-report-filter-card")

        dashboard = self.client.get(reverse("portal_admin_page", kwargs={"page": "dashboard"}))
        self._assert_collapse_ready(dashboard)
        self.assertContains(dashboard, "<h2>Enrollment by unit</h2>")

        settings_page = self.client.get(reverse("portal_admin_page", kwargs={"page": "fees"}))
        self._assert_collapse_ready(settings_page)

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_report_filter_skip_is_scoped_to_the_filter_card(self):
        session = self.client.session
        session[PORTAL_AUTH_SESSION_KEY] = "staff"
        session.save()
        families = self.client.get(reverse("portal_staff_page", kwargs={"page": "families"}))
        self._assert_collapse_ready(families)
        self.assertContains(families, "portal-families-toolbar card")
        self.assertNotContains(families, "portal-collapse-skip")

        member = self.client.get(reverse("portal_staff_member_information_report"))
        self._assert_collapse_ready(
            member,
            skip_snippets=("portal-report-filter-card portal-collapse-skip portal-no-print",),
        )
        self.assertEqual(member.content.decode().count("portal-collapse-skip"), 1)

        contacts = self.client.get(reverse("portal_staff_emergency_contact_report"))
        self._assert_collapse_ready(
            contacts,
            skip_snippets=("portal-report-filter-card portal-collapse-skip portal-no-print",),
        )
        self.assertEqual(contacts.content.decode().count("portal-collapse-skip"), 1)
