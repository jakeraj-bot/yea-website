from datetime import date, time
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from portal.models import (
    PortalCalendarActivity,
    PortalChild,
    PortalFamily,
    PortalOrgSetting,
    PortalOutsideProgram,
    PortalStaffAccount,
    PortalUnit,
)
from portal.staff_auth import (
    PORTAL_AUTH_SESSION_KEY,
    is_portal_admin,
    staff_accessible_units,
    staff_can_see_billing,
)


@override_settings(PORTAL_PREVIEW_MODE=False)
class ProgramDirectorFrontDeskTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.school_18 = PortalUnit.objects.create(slug="school-18", name="School 18", is_active=True)
        self.school_26 = PortalUnit.objects.create(slug="school-26", name="School 26", is_active=True)
        self.family = PortalFamily.objects.create(unit=self.school_18, slug="jacobs", name="Jacobs")
        PortalChild.objects.create(
            family=self.family,
            name="Jamie Jacobs",
            unit=self.school_18,
            is_active=True,
            grade="3",
        )
        self.pd_user = User.objects.create_user(username="staff:pduser", password="StaffPass123")
        self.pd_account = PortalStaffAccount.objects.create(
            user=self.pd_user,
            unit=self.school_18,
            display_name="Program Director",
            role="Program director",
            is_active=True,
        )
        self.desk_user = User.objects.create_user(username="staff:frontdesk", password="StaffPass123")
        self.desk_account = PortalStaffAccount.objects.create(
            user=self.desk_user,
            unit=self.school_18,
            display_name="Front Desk",
            role="Front desk staff",
            is_active=True,
        )
        self.staff_user = User.objects.create_user(username="staff:unitstaff", password="StaffPass123")
        PortalStaffAccount.objects.create(
            user=self.staff_user,
            unit=self.school_18,
            display_name="Unit Staff",
            role="Unit director",
            is_active=True,
        )
        self.admin_user = User.objects.create_user(username="staff:yeaadmin", password="AdminPass123")
        PortalStaffAccount.objects.create(
            user=self.admin_user,
            unit=self.school_18,
            display_name="Portal Admin",
            role="Portal admin",
            all_units_access=True,
            is_active=True,
        )
        setting = PortalOrgSetting.load()
        setting.program_director_can_see_billing = False
        setting.save()

    def _login(self, user, area="staff", unit_slug="school-18"):
        self.client.force_login(user)
        session = self.client.session
        session[PORTAL_AUTH_SESSION_KEY] = area
        if area == "staff":
            session["staff_unit_slug"] = unit_slug
        session.save()

    def test_program_director_is_not_admin(self):
        self.assertFalse(is_portal_admin(self.pd_user))
        self.assertTrue(is_portal_admin(self.admin_user))

    def test_program_director_sees_all_units_staff_does_not(self):
        pd_units = [unit.slug for unit in staff_accessible_units(self.pd_user)]
        staff_units = [unit.slug for unit in staff_accessible_units(self.staff_user)]
        self.assertEqual(pd_units, ["school-18", "school-26"])
        self.assertEqual(staff_units, ["school-18"])

    def test_front_desk_stays_unit_scoped(self):
        units = [unit.slug for unit in staff_accessible_units(self.desk_user)]
        self.assertEqual(units, ["school-18"])

    def test_pd_cannot_open_billing_when_toggle_off(self):
        self.assertFalse(staff_can_see_billing(self.pd_account))
        self._login(self.pd_user)
        urls = [
            reverse("portal_staff_family_billing", kwargs={"family_slug": "jacobs"}),
            reverse("portal_staff_family_plans", kwargs={"family_slug": "jacobs"}),
            reverse("portal_staff_family_agency", kwargs={"family_slug": "jacobs"}),
            reverse("portal_staff_page", kwargs={"page": "member-billing"}),
            reverse("portal_staff_page", kwargs={"page": "agency"}),
            reverse("portal_staff_balances_export"),
        ]
        for url in urls:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 403)

    def test_pd_can_open_billing_when_org_toggle_on(self):
        setting = PortalOrgSetting.load()
        setting.program_director_can_see_billing = True
        setting.save()
        self.assertTrue(staff_can_see_billing(PortalStaffAccount.objects.get(pk=self.pd_account.pk)))
        self._login(self.pd_user)
        response = self.client.get(reverse("portal_staff_family_billing", kwargs={"family_slug": "jacobs"}))
        self.assertEqual(response.status_code, 200)
        dashboard = self.client.get(reverse("portal_staff_page", kwargs={"page": "dashboard"}))
        self.assertContains(dashboard, "Member billing")
        self.assertContains(dashboard, "4Cs / Agency")

    def test_pd_can_open_billing_when_account_toggle_on(self):
        self.pd_account.can_see_billing = True
        self.pd_account.save(update_fields=["can_see_billing"])
        self._login(self.pd_user)
        response = self.client.get(reverse("portal_staff_family_plans", kwargs={"family_slug": "jacobs"}))
        self.assertEqual(response.status_code, 200)

    def test_pd_sees_operations_not_admin_settings(self):
        self._login(self.pd_user)
        dashboard = self.client.get(reverse("portal_staff_page", kwargs={"page": "dashboard"}))
        self.assertEqual(dashboard.status_code, 200)
        self.assertContains(dashboard, "Activity calendar")
        self.assertContains(dashboard, "Groups")
        self.assertContains(dashboard, "Families")
        self.assertContains(dashboard, "Waitlist")
        self.assertContains(dashboard, "Outside programs")
        self.assertNotContains(dashboard, "Member billing")
        self.assertNotContains(dashboard, "4Cs / Agency")
        self.assertNotContains(dashboard, "Units &amp; locations")
        admin_page = self.client.get(reverse("portal_admin_page", kwargs={"page": "units"}))
        self.assertEqual(admin_page.status_code, 302)
        self.assertIn("/portal/admin/login/", admin_page.url)

    def test_front_desk_opens_billing_and_activities(self):
        self._login(self.desk_user)
        billing = self.client.get(reverse("portal_staff_family_billing", kwargs={"family_slug": "jacobs"}))
        self.assertEqual(billing.status_code, 200)
        calendar = self.client.get(reverse("portal_staff_activity_calendar"))
        self.assertEqual(calendar.status_code, 200)
        groups = self.client.get(reverse("portal_staff_groups"))
        self.assertEqual(groups.status_code, 200)
        dashboard = self.client.get(reverse("portal_staff_page", kwargs={"page": "dashboard"}))
        self.assertContains(dashboard, "Member billing")
        self.assertContains(dashboard, "Activity calendar")
        self.assertContains(dashboard, "Groups")
        self.assertNotContains(dashboard, "Outside programs")
        admin_page = self.client.get(reverse("portal_admin_page", kwargs={"page": "staff"}))
        self.assertEqual(admin_page.status_code, 302)

    def test_staff_still_unit_scoped_on_calendar(self):
        PortalCalendarActivity.objects.create(
            name="Art 26",
            activity_date=date(2026, 9, 14),
            start_time=time(15, 0),
            unit=self.school_26,
        )
        PortalCalendarActivity.objects.create(
            name="Art 18",
            activity_date=date(2026, 9, 14),
            start_time=time(15, 0),
            unit=self.school_18,
        )
        self._login(self.staff_user)
        page = self.client.get(reverse("portal_staff_activity_calendar") + "?month=2026-09")
        self.assertContains(page, "Art 18")
        self.assertNotContains(page, "Art 26")

    def test_program_director_sees_all_unit_activities(self):
        PortalCalendarActivity.objects.create(
            name="Art 26",
            activity_date=date(2026, 9, 14),
            start_time=time(15, 0),
            unit=self.school_26,
        )
        self._login(self.pd_user)
        page = self.client.get(reverse("portal_staff_activity_calendar") + "?month=2026-09")
        self.assertContains(page, "Art 26")
        self.assertContains(page, "All units")

    def test_outside_program_crud(self):
        self._login(self.pd_user)
        create = self.client.post(
            reverse("portal_staff_outside_programs"),
            {
                "name": "Soccer Stars",
                "email": "soccer@example.com",
                "phone": "555-0100",
                "description": "Weekly soccer clinic",
                "charge_amount": "250.00",
                "category": "vendor",
                "notes": "Needs gym",
            },
        )
        self.assertEqual(create.status_code, 302)
        program = PortalOutsideProgram.objects.get(name="Soccer Stars")
        self.assertEqual(program.email, "soccer@example.com")
        self.assertEqual(program.charge_amount, Decimal("250.00"))

        listing = self.client.get(reverse("portal_staff_outside_programs") + "?q=Soccer")
        self.assertContains(listing, "Soccer Stars")
        self.assertContains(listing, "soccer@example.com")

        save = self.client.post(
            reverse("portal_staff_outside_program_save", kwargs={"program_id": program.pk}),
            {
                "name": "Soccer Stars",
                "email": "clinic@example.com",
                "phone": "555-0100",
                "description": "Weekly soccer clinic",
                "charge_amount": "275.00",
                "category": "partner",
                "notes": "Updated",
            },
        )
        self.assertEqual(save.status_code, 302)
        program.refresh_from_db()
        self.assertEqual(program.email, "clinic@example.com")
        self.assertEqual(program.charge_amount, Decimal("275.00"))

        blocked = self.client.post(
            reverse("portal_staff_outside_program_delete", kwargs={"program_id": program.pk})
        )
        self.assertEqual(blocked.status_code, 302)
        self.assertTrue(PortalOutsideProgram.objects.filter(pk=program.pk).exists())

        deleted = self.client.post(
            reverse("portal_staff_outside_program_delete", kwargs={"program_id": program.pk}),
            {"delete_reason": "Vendor closed"},
        )
        self.assertEqual(deleted.status_code, 302)
        self.assertFalse(PortalOutsideProgram.objects.filter(pk=program.pk).exists())

        export = self.client.get(reverse("portal_staff_outside_programs_export"))
        self.assertEqual(export.status_code, 200)
        self.assertEqual(export["Content-Type"], "text/csv")

    def test_front_desk_cannot_open_outside_programs(self):
        self._login(self.desk_user)
        response = self.client.get(reverse("portal_staff_outside_programs"))
        self.assertEqual(response.status_code, 403)

    def test_unit_staff_cannot_open_outside_programs(self):
        self._login(self.staff_user)
        response = self.client.get(reverse("portal_staff_outside_programs"))
        self.assertEqual(response.status_code, 403)

    def test_staff_reports_hide_payment_ledgers_for_pd(self):
        self._login(self.pd_user)
        reports = self.client.get(reverse("portal_staff_page", kwargs={"page": "reports"}))
        self.assertEqual(reports.status_code, 200)
        self.assertNotContains(reports, reverse("portal_staff_balances_export"))
        self.assertNotContains(reports, reverse("portal_staff_agency_copay_export"))
        self.assertContains(reports, "Attendance")
