"""Regression tests: Families list and family account stay off the N+1 path."""

from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from enrollment.models import EnrollmentApplication
from portal.admin_services import get_admin_families_live
from portal.attendance_service import families_for_staff
from portal.models import (
    PortalChild,
    PortalFamily,
    PortalLedgerEntry,
    PortalParentAccount,
    PortalStaffAccount,
    PortalUnit,
)
from portal.staff_auth import PORTAL_AUTH_SESSION_KEY


def _make_application(family, *, first="Ada", last=None, status="approved"):
    last = last or family.name
    return EnrollmentApplication.objects.create(
        program="after_school",
        program_location="school_18",
        family_name=family.name,
        primary_email=f"{family.slug}@example.com",
        home_address="1 Main St",
        primary_first_name="Pat",
        primary_last_name=family.name,
        primary_gender="female",
        primary_language="english",
        primary_relationship="mother",
        primary_phone="555-0100",
        primary_phone_type="cell",
        primary_text_subscription="yes",
        primary_email_subscription="yes",
        primary_email_address=f"{family.slug}@example.com",
        primary_authorized_pickup="yes",
        student_first_name=first,
        student_last_name=last,
        student_gender="female",
        student_dob=date(2016, 1, 1),
        student_language="english",
        student_ethnicity="unknown",
        student_race="unknown",
        student_grade="3",
        student_school="School 18",
        health_statement="good_health",
        membership_fee_agreed="no",
        payment_method="private_pay",
        payment_plan="weekly",
        payment_plan_signature="Pat",
        payment_plan_signed_date=date(2026, 8, 1),
        status=status,
        portal_family=family,
    )


class FamilyListQueryCountTests(TestCase):
    FAMILY_COUNT = 12

    def setUp(self):
        User = get_user_model()
        self.unit = PortalUnit.objects.create(slug="school-18", name="School 18", is_active=True)
        self.admin = User.objects.create_user(username="staff:speedadmin", password="AdminPass123")
        PortalStaffAccount.objects.create(
            user=self.admin,
            unit=self.unit,
            display_name="Portal Admin",
            role="Portal admin",
            all_units_access=True,
            is_active=True,
        )
        for index in range(self.FAMILY_COUNT):
            family = PortalFamily.objects.create(
                unit=self.unit,
                slug=f"speed-{index}",
                name=f"Speed{index}",
                primary_contact=f"Parent {index}",
                balance=Decimal("20.00"),
                billing_type="Private pay",
                status="Active",
            )
            child = PortalChild.objects.create(
                family=family,
                name=f"Child {index}",
                school="School 18",
                is_active=True,
            )
            PortalLedgerEntry.objects.create(
                family=family,
                child_name=child.name,
                date=date(2026, 9, 1),
                entry_type="charge",
                description="Weekly tuition",
                amount=Decimal("20.00"),
            )
            _make_application(family, first="Ada", last=f"Speed{index}", status="under_review")
            if index % 3 == 0:
                parent = User.objects.create_user(
                    username=f"parent:speed{index}",
                    password="ParentPass123",
                    email=f"speed{index}@example.com",
                )
                PortalParentAccount.objects.create(user=parent, family=family)

    def test_admin_families_query_count_stays_flat(self):
        # Warm caches used by location helpers, then assert a small constant budget.
        get_admin_families_live()
        with self.assertNumQueries(6):
            rows = get_admin_families_live()
        self.assertGreaterEqual(len(rows), self.FAMILY_COUNT)
        self.assertTrue(any(row.get("has_parent_login") for row in rows))
        self.assertTrue(any(row.get("child_name", "").startswith("Child") for row in rows))

    def test_staff_families_query_count_stays_flat(self):
        families_for_staff(self.unit)
        with self.assertNumQueries(8):
            rows = families_for_staff(self.unit)
        self.assertGreaterEqual(len(rows), self.FAMILY_COUNT)

    def test_more_families_do_not_add_queries(self):
        extra = 8
        for index in range(extra):
            family = PortalFamily.objects.create(
                unit=self.unit,
                slug=f"extra-{index}",
                name=f"Extra{index}",
                primary_contact=f"Extra Parent {index}",
                balance=Decimal("10.00"),
                status="Active",
            )
            PortalChild.objects.create(family=family, name=f"Extra Child {index}", is_active=True)
            PortalLedgerEntry.objects.create(
                family=family,
                child_name=f"Extra Child {index}",
                date=date(2026, 9, 1),
                entry_type="charge",
                description="Weekly tuition",
                amount=Decimal("10.00"),
            )
            _make_application(family, first="Bea", last=f"Extra{index}", status="under_review")

        get_admin_families_live()
        with CaptureQueriesContext(connection) as ctx:
            rows = get_admin_families_live()
        self.assertGreaterEqual(len(rows), self.FAMILY_COUNT + extra)
        self.assertLessEqual(len(ctx), 8)

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_admin_families_page_and_account_stay_off_n_plus_one(self):
        self.client.force_login(self.admin)
        session = self.client.session
        session[PORTAL_AUTH_SESSION_KEY] = "admin"
        session.save()

        self.client.get(reverse("portal_admin_page", kwargs={"page": "families"}))
        with CaptureQueriesContext(connection) as list_ctx:
            response = self.client.get(reverse("portal_admin_page", kwargs={"page": "families"}))
        self.assertEqual(response.status_code, 200)
        self.assertLessEqual(len(list_ctx), 40)

        first = PortalFamily.objects.get(slug="speed-0")
        self.client.get(reverse("portal_admin_family_detail", kwargs={"family_slug": first.slug}), {"id": first.pk})
        with CaptureQueriesContext(connection) as account_ctx:
            account = self.client.get(
                reverse("portal_admin_family_detail", kwargs={"family_slug": first.slug}),
                {"id": first.pk},
            )
        self.assertEqual(account.status_code, 200)
        self.assertContains(account, "Family account")
        self.assertLessEqual(len(account_ctx), 80)
