"""Smoke-test named GET routes so portal and public pages do not 500."""

from datetime import date, time, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import URLPattern, URLResolver, get_resolver, reverse
from django.utils import timezone

from portal.admin_reports import ADMIN_DATA_REPORTS
from portal.models import (
    PortalCalendarActivity,
    PortalChild,
    PortalChildBillingPlan,
    PortalFamily,
    PortalMemberGroup,
    PortalParentAccount,
    PortalProgram,
    PortalStaffAccount,
    PortalUnit,
)
from portal.staff_auth import PORTAL_AUTH_SESSION_KEY
from portal.tests.test_family_units import _make_application

PUBLIC_NAMES = [
    "home",
    "our_story",
    "meet_the_staff",
    "contact",
    "safety",
    "after_school",
    "summer_camp",
    "school_18",
    "school_26",
    "dale_ave",
    "caldwell",
    "partnerships",
    "donate",
    "apply",
    "enrollment_help",
    "dropin_index",
    "dropin_login",
    "dropin_register",
    "portal_home",
    "portal_parent_login",
    "portal_staff_login",
    "portal_admin_login",
    "portal_parent_signup",
    "portal_parent_password_reset",
    "portal_staff_password_reset",
    "portal_admin_password_reset",
    "robots_txt",
    "django.contrib.sitemaps.views.sitemap",
]

PARENT_PAGES = [
    "dashboard",
    "profile",
    "emergency-contacts",
    "applications",
    "policies",
    "billing",
    "tax-statements",
    "receipts",
    "drop-in",
    "drop-off",
    "field-trips",
    "help",
    "support",
    "contact-us",
    "account",
]

STAFF_PAGES = [
    "dashboard",
    "programs",
    "attendance",
    "applications",
    "waitlist",
    "create-application",
    "families",
    "member-policies",
    "agency",
    "reports",
    "drop-off-pickup",
    "messages",
    "incidents",
    "support",
    "emails-sent",
    "member-billing",
]

ADMIN_PAGES = [
    "dashboard",
    "units",
    "programs",
    "staff",
    "families",
    "applications",
    "waitlist",
    "agencies",
    "fees",
    "member-billing",
    "billing-settings",
    "billing-permissions",
    "email-settings",
    "scholarships",
    "discounts",
    "collections",
    "member-policies",
    "field-trips",
    "drop-off",
    "drop-off-pickup",
    "attendance",
    "checkin-settings",
    "program-calendar",
    "reports",
    "messages",
    "communications",
    "parent-emails",
    "emails-sent",
    "lesson-planner",
    "staff-compliance",
    "licensing",
    "support",
    "activity",
]

FAMILY_TABS = (
    ("portal_admin_family_detail", "portal_staff_family_detail"),
    ("portal_admin_family_billing", "portal_staff_family_billing"),
    ("portal_admin_family_plans", "portal_staff_family_plans"),
    ("portal_admin_family_agency", "portal_staff_family_agency"),
    ("portal_admin_family_applications", "portal_staff_family_applications"),
    ("portal_admin_family_policies", "portal_staff_family_policies"),
    ("portal_admin_family_email", "portal_staff_family_email"),
    ("portal_admin_family_notes", "portal_staff_family_notes"),
    ("portal_admin_family_attendance", "portal_staff_family_attendance"),
    ("portal_admin_family_pickup", "portal_staff_family_pickup"),
    ("portal_admin_family_incidents", "portal_staff_family_incidents"),
)

STAFF_REPORTS = [
    "portal_staff_pickup_report",
    "portal_staff_member_information_report",
    "portal_staff_attendance_grade_report",
    "portal_staff_emergency_contact_report",
    "portal_staff_medical_report",
    "portal_staff_school_bus_report",
    "portal_staff_attendance_report",
    "portal_staff_weekly_attendance_report",
    "portal_staff_attendance_blank_daily",
    "portal_staff_attendance_blank_weekly",
    "portal_staff_signout_blank",
    "portal_staff_owed_weeks_report",
    "portal_staff_four_cs_payout_report",
    "portal_staff_balances_export",
    "portal_staff_agency_copay_export",
    "portal_staff_member_policies_print",
    "portal_staff_incidents_print",
    "portal_staff_outside_programs",
    "portal_staff_outside_programs_print",
    "portal_staff_activity_calendar",
    "portal_staff_groups",
    "portal_staff_review_all",
]

ADMIN_REPORTS = [
    "portal_admin_member_type_report",
    "portal_admin_enrollment_report",
    "portal_admin_member_information_report",
    "portal_admin_weekly_attendance_report",
    "portal_admin_attendance_report",
    "portal_admin_attendance_blank_daily",
    "portal_admin_attendance_blank_weekly",
    "portal_admin_attendance_grade_report",
    "portal_admin_emergency_contact_report",
    "portal_admin_owed_weeks_report",
    "portal_admin_four_cs_payout_report",
    "portal_admin_financial_report",
    "portal_admin_member_policies_print",
    "portal_admin_activity_calendar",
    "portal_admin_groups",
    "portal_admin_outside_programs",
    "portal_admin_outside_programs_print",
    "portal_admin_review_all",
    "portal_admin_parent_preview_sample",
]

SKIP_WALK_NAMES = {
    "portal_member_stripe_webhook",
    "portal_parent_password_reset_confirm",
    "portal_staff_password_reset_confirm",
    "portal_admin_password_reset_confirm",
    "portal_parent_logout",
    "portal_staff_logout",
    "portal_admin_logout",
    "dropin_logout",
}


def _named_patterns(resolver=None, prefix=""):
    resolver = resolver or get_resolver()
    for pattern in resolver.url_patterns:
        if isinstance(pattern, URLResolver):
            yield from _named_patterns(pattern, prefix + str(pattern.pattern))
            continue
        if isinstance(pattern, URLPattern) and pattern.name:
            yield pattern.name, prefix + str(pattern.pattern)


@override_settings(PORTAL_PREVIEW_MODE=False)
class NamedUrlSmokeTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.unit = PortalUnit.objects.create(slug="school-18", name="School 18", is_active=True)
        self.program = PortalProgram.objects.create(
            unit=self.unit,
            name="After-School 2026–27",
            start_time=time(15, 0),
            end_time=time(18, 0),
            is_active=True,
        )
        self.family = PortalFamily.objects.create(
            unit=self.unit,
            slug="jacobs",
            name="Jacobs",
            billing_type="Private pay",
            status="Active",
            program_label="After-School 2026–27",
        )
        self.child = PortalChild.objects.create(
            family=self.family,
            name="Jordan Jacobs",
            school="School 18",
            grade="4th",
            billing_plan="Weekly",
            billing_amount=Decimal("50.00"),
            auto_charge=True,
            next_charge_date=timezone.localdate() + timedelta(days=7),
            is_active=True,
        )
        PortalChildBillingPlan.objects.create(
            child=self.child,
            description="After-care",
            billing_plan="Weekly",
            billing_amount=Decimal("50.00"),
            auto_charge=True,
            next_charge_date=self.child.next_charge_date,
            sort_order=1,
        )
        self.application = _make_application(self.family)
        self.activity = PortalCalendarActivity.objects.create(
            name="Homework club",
            activity_date=date(2026, 9, 16),
            start_time=time(15, 30),
            end_time=time(16, 30),
            unit=self.unit,
        )
        self.group = PortalMemberGroup.objects.create(name="Room A", unit=self.unit)
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
            all_units_access=False,
            is_active=True,
        )
        self.parent_user = User.objects.create_user(username="parent:jacobs", password="ParentPass123")
        PortalParentAccount.objects.create(user=self.parent_user, family=self.family)

    def _login(self, user, area, unit_slug="school-18"):
        self.client.force_login(user)
        session = self.client.session
        session[PORTAL_AUTH_SESSION_KEY] = area
        if area == "staff":
            session["staff_unit_slug"] = unit_slug
        session.save()

    def _assert_ok(self, url, *, client=None, allow=(200, 302, 303, 400, 403, 404, 405)):
        client = client or self.client
        response = client.get(url)
        self.assertNotEqual(
            response.status_code,
            500,
            f"{url} returned {response.status_code}",
        )
        self.assertIn(
            response.status_code,
            allow,
            f"{url} returned unexpected {response.status_code}",
        )
        return response

    def test_public_marketing_and_login_pages(self):
        for name in PUBLIC_NAMES:
            self._assert_ok(reverse(name), client=self.client)
        self._assert_ok(reverse("enrollment_apply", kwargs={"step": "family"}))
        self._assert_ok(reverse("enrollment_policy", kwargs={"slug": "pickup-policy"}))
        self._assert_ok(reverse("dropin_register", kwargs={"step": "account"}))

    def test_parent_portal_pages(self):
        self._login(self.parent_user, "parent")
        for page in PARENT_PAGES:
            self._assert_ok(reverse("portal_parent_page", kwargs={"page": page}))
        for name in (
            "portal_parent_payment",
            "portal_parent_payment_preview",
            "portal_parent_payment_success",
            "portal_parent_application_print",
            "portal_parent_policies_print",
            "portal_parent_receipts_print",
            "portal_parent_tax_statement_print",
        ):
            self._assert_ok(reverse(name))
        self._assert_ok(reverse("portal_parent_policy_print", kwargs={"policy_slug": "pickup-policy"}))

    def test_staff_sidebar_reports_and_family(self):
        self._login(self.staff, "staff")
        for page in STAFF_PAGES:
            self._assert_ok(reverse("portal_staff_page", kwargs={"page": page}))
        for name in STAFF_REPORTS:
            self._assert_ok(reverse(name))
        family_kwargs = {"family_slug": self.family.slug}
        for _admin_name, staff_name in FAMILY_TABS:
            self._assert_ok(reverse(staff_name, kwargs=family_kwargs))
        self._assert_ok(reverse("portal_staff_family_search"))
        self._assert_ok(reverse("portal_staff_activity_detail", kwargs={"activity_id": self.activity.pk}))
        self._assert_ok(reverse("portal_staff_group_detail", kwargs={"group_id": self.group.pk}))
        self._assert_ok(
            reverse("portal_staff_group_print", kwargs={"group_id": self.group.pk, "kind": "members"})
        )
        self._assert_ok(
            reverse("portal_staff_program_roster", kwargs={"program_slug": "after-school-2026-27"})
        )
        app_slug = str(self.application.reference)
        self._assert_ok(reverse("portal_staff_application_detail", kwargs={"app_slug": app_slug}))
        self._assert_ok(reverse("portal_staff_application_print", kwargs={"app_slug": app_slug}))

    def test_admin_sidebar_reports_and_family(self):
        self._login(self.admin, "admin")
        for page in ADMIN_PAGES:
            self._assert_ok(reverse("portal_admin_page", kwargs={"page": page}))
        for name in ADMIN_REPORTS:
            self._assert_ok(reverse(name))
        for slug in ADMIN_DATA_REPORTS:
            self._assert_ok(reverse("portal_admin_data_report", kwargs={"report_slug": slug}))
        family_kwargs = {"family_slug": self.family.slug}
        for admin_name, _staff_name in FAMILY_TABS:
            self._assert_ok(reverse(admin_name, kwargs=family_kwargs))
        self._assert_ok(reverse("portal_admin_family_search"))
        self._assert_ok(reverse("portal_admin_activity_detail", kwargs={"activity_id": self.activity.pk}))
        self._assert_ok(reverse("portal_admin_group_detail", kwargs={"group_id": self.group.pk}))
        self._assert_ok(
            reverse("portal_admin_group_print", kwargs={"group_id": self.group.pk, "kind": "members"})
        )
        self._assert_ok(reverse("portal_admin_parent_preview", kwargs={"family_slug": self.family.slug}))
        for page in PARENT_PAGES:
            self._assert_ok(
                reverse(
                    "portal_admin_parent_preview_page",
                    kwargs={"family_slug": self.family.slug, "page": page},
                )
            )
            self._assert_ok(reverse("portal_admin_parent_preview_sample_page", kwargs={"page": page}))
        app_slug = str(self.application.reference)
        self._assert_ok(reverse("portal_admin_application_detail", kwargs={"app_slug": app_slug}))
        self._assert_ok(reverse("portal_admin_application_print", kwargs={"app_slug": app_slug}))
        self._assert_ok(reverse("portal_area_switch", kwargs={"area": "staff"}))

    def test_named_get_routes_without_kwargs_do_not_500(self):
        self._login(self.admin, "admin")
        failures = []
        for name, pattern in _named_patterns():
            if name in SKIP_WALK_NAMES or name.startswith("admin:"):
                continue
            if "<" in pattern or name.startswith("django.contrib.admin"):
                continue
            try:
                url = reverse(name)
            except Exception:
                continue
            response = self.client.get(url)
            if response.status_code == 500:
                failures.append(f"{name} {url}")
        self.assertEqual(failures, [], "Named GET routes returned 500: " + ", ".join(failures))
