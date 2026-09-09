from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from enrollment.application_review import approve_application
from portal.agency_weeks import cadence_key
from portal.models import PortalChild, PortalFamily, PortalUnit
from portal.tests.test_family_units import _make_application


class ApproveApplicationBillingPlanTests(TestCase):
    def setUp(self):
        self.unit = PortalUnit.objects.create(
            slug="school-18",
            name="School 18",
            program_type="after_school",
            is_active=True,
        )
        self.family = PortalFamily.objects.create(unit=self.unit, slug="rivera", name="Rivera")

    def test_approve_monthly_application_sets_monthly_billing_plan(self):
        app = _make_application(self.family, status="under_review", payment_plan="monthly")
        approve_application(app)

        child = PortalChild.objects.get(family=self.family)
        today = timezone.localdate()
        self.assertEqual(child.billing_plan, "Monthly")
        self.assertEqual(child.charge_month_day, today.day)
        self.assertIsNone(child.charge_weekday)

    def test_approve_weekly_application_sets_weekly_billing_plan(self):
        app = _make_application(self.family, status="under_review", payment_plan="weekly")
        approve_application(app)

        child = PortalChild.objects.get(family=self.family)
        self.assertEqual(child.billing_plan, "Weekly")
        self.assertEqual(child.charge_weekday, timezone.localdate().weekday())
        self.assertIsNone(child.charge_month_day)

    def test_approve_biweekly_application_sets_biweekly_billing_plan(self):
        app = _make_application(self.family, status="under_review", payment_plan="biweekly")
        approve_application(app)

        child = PortalChild.objects.get(family=self.family)
        self.assertEqual(child.billing_plan, "Bi-weekly")
        self.assertEqual(cadence_key(child.billing_plan), "biweekly")
        self.assertEqual(child.charge_weekday, timezone.localdate().weekday())

    def test_approve_does_not_overwrite_staff_set_plan(self):
        child = PortalChild.objects.create(
            family=self.family,
            name="Ada Rivera",
            is_active=True,
            billing_plan="Weekly",
            billing_amount=Decimal("40.00"),
        )
        app = _make_application(self.family, status="under_review", payment_plan="monthly")
        approve_application(app)
        child.refresh_from_db()

        self.assertEqual(child.billing_plan, "Weekly")
        self.assertEqual(child.billing_amount, Decimal("40.00"))

    def test_approve_fills_default_weekly_from_application(self):
        child = PortalChild.objects.create(
            family=self.family,
            name="Ada Rivera",
            is_active=True,
        )
        self.assertEqual(child.billing_plan, "Weekly")
        app = _make_application(self.family, status="under_review", payment_plan="monthly")
        approve_application(app)
        child.refresh_from_db()

        self.assertEqual(child.billing_plan, "Monthly")
        self.assertEqual(child.charge_month_day, timezone.localdate().day)

    def test_four_cs_approve_uses_application_cadence(self):
        app = _make_application(
            self.family,
            status="under_review",
            payment_plan="monthly",
            payment_method="4cs",
        )
        approve_application(app)
        child = PortalChild.objects.get(family=self.family)
        self.assertEqual(child.billing_plan, "Monthly")
        self.assertEqual(cadence_key(child.billing_plan), "monthly")
        self.family.refresh_from_db()
        self.assertEqual(self.family.billing_type, "4Cs")