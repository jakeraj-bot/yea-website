from datetime import timedelta
from decimal import Decimal
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from portal.billing_services import get_scheduled_plan_charges
from portal.models import (
    PortalChild,
    PortalChildBillingPlan,
    PortalFamily,
    PortalLedgerEntry,
    PortalStaffAccount,
    PortalUnit,
)
from portal.staff_auth import PORTAL_AUTH_SESSION_KEY


def _css_brace_balance(text):
    depth = 0
    in_string = None
    i = 0
    while i < len(text):
        char = text[i]
        if in_string:
            if char == "\\" and i + 1 < len(text):
                i += 2
                continue
            if char == in_string:
                in_string = None
            i += 1
            continue
        if char in ('"', "'"):
            in_string = char
        elif char == "/" and i + 1 < len(text) and text[i + 1] == "*":
            end = text.find("*/", i + 2)
            i = len(text) if end == -1 else end + 2
            continue
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth < 0:
                return depth
        i += 1
    return depth


class PortalCssBraceTests(SimpleTestCase):
    def test_portal_css_braces_are_balanced(self):
        css = Path("static/css/portal.css").read_text()
        self.assertEqual(_css_brace_balance(css), 0)


class MemberBillingPageTests(TestCase):
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
        self.child = PortalChild.objects.create(
            family=self.family,
            name="Jordan Jacobs",
            school="School 18",
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
        PortalChildBillingPlan.objects.create(
            child=self.child,
            description="Before-care",
            billing_plan="Weekly",
            billing_amount=Decimal("20.00"),
            auto_charge=True,
            next_charge_date=self.child.next_charge_date,
            sort_order=2,
        )
        PortalLedgerEntry.objects.create(
            family=self.family,
            child_name=self.child.name,
            entry_type="charge",
            amount=Decimal("50.00"),
            description="Weekly tuition — Jordan Jacobs",
            date=timezone.localdate(),
            is_manual=True,
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

    def _login_admin(self):
        self.client.force_login(self.admin)
        session = self.client.session
        session[PORTAL_AUTH_SESSION_KEY] = "admin"
        session.save()

    def test_scheduled_plan_charges_include_primary_and_extra_plans(self):
        rows = get_scheduled_plan_charges()
        labels = [row["plan"] for row in rows]
        self.assertTrue(any("After-care" in label for label in labels), labels)
        self.assertTrue(any("Before-care" in label for label in labels), labels)
        self.assertEqual(rows[0]["child_name"], "Jordan Jacobs")
        self.assertEqual(rows[0]["family_slug"], "jacobs")

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_admin_member_billing_loads_with_scheduled_plans(self):
        self._login_admin()
        response = self.client.get(reverse("portal_admin_page", kwargs={"page": "member-billing"}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Member billing")
        self.assertContains(response, "Post bulk charges")
        self.assertContains(response, "Scheduled automatic charges")
        self.assertContains(response, "Jordan Jacobs")
        self.assertContains(response, "Before-care")
        self.assertContains(response, "Recent charges")
        self.assertContains(response, "Weekly tuition — Jordan Jacobs")
        preview = self.client.get(
            reverse("portal_admin_page", kwargs={"page": "member-billing"}),
            {"preview": "1", "mode": "weekly_tuition"},
        )
        self.assertEqual(preview.status_code, 200)
        self.assertContains(preview, "charge(s) ready to post")
