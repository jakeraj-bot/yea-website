from datetime import date, time

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from enrollment.application_review import (
    approve_application,
    repair_family_units_from_applications,
)
from enrollment.models import EnrollmentApplication
from portal.admin_reports import billing_plan_rows
from portal.admin_services import get_admin_families_live
from portal.attendance_service import build_roster, families_for_staff
from portal.billing_services import prepare_billing_for_staff
from portal.family_list import child_balance_map, expand_demo_families
from portal.live_services import family_profile_live
from portal.models import (
    PortalFamily,
    PortalLedgerEntry,
    PortalParentAccount,
    PortalProgram,
    PortalStaffAccount,
    PortalUnit,
)
from portal.parent_services import get_profile_live
from portal.staff_auth import PORTAL_AUTH_SESSION_KEY
from portal.staff_services import (
    build_medical_report_rows,
    build_school_bus_roster,
    filter_school_bus_roster,
    get_program_roster,
    emergency_contact_report_for_unit,
    pickup_report_for_unit,
    weekly_attendance_report_data,
)


def _make_application(family, *, location="school_18", status="approved", payment_plan="weekly", payment_method="private_pay"):
    return EnrollmentApplication.objects.create(
        program="after_school",
        program_location=location,
        family_name=family.name,
        primary_email="parent@example.com",
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
        primary_email_address="parent@example.com",
        primary_authorized_pickup="yes",
        student_first_name="Ada",
        student_last_name=family.name,
        student_gender="female",
        student_dob=date(2016, 1, 1),
        student_language="english",
        student_ethnicity="unknown",
        student_race="unknown",
        student_grade="3",
        student_school="School 18",
        health_statement="good_health",
        membership_fee_agreed="no",
        payment_method=payment_method,
        payment_plan=payment_plan,
        payment_plan_signature="Pat",
        payment_plan_signed_date=date(2026, 8, 1),
        status=status,
        portal_family=family,
    )


class FamilyUnitSyncTests(TestCase):
    def setUp(self):
        self.main = PortalUnit.objects.create(slug="main-location", name="Main location")
        self.school_18 = PortalUnit.objects.create(
            slug="school-18",
            name="School 18",
            program_type="after_school",
            is_active=True,
        )

    def test_repair_moves_placeholder_family_to_application_site(self):
        family = PortalFamily.objects.create(unit=self.main, slug="rivera", name="Rivera")
        _make_application(family, location="school_18", status="approved")

        moved = repair_family_units_from_applications()
        family.refresh_from_db()

        self.assertEqual(moved, 1)
        self.assertEqual(family.unit_id, self.school_18.id)

    def test_all_families_list_shows_application_unit(self):
        family = PortalFamily.objects.create(unit=self.main, slug="chen", name="Chen")
        _make_application(family, location="school_18", status="approved")

        rows = get_admin_families_live()
        row = next(item for item in rows if item["slug"] == "chen")
        self.assertEqual(row["unit"], "School 18")
        self.assertEqual(row["unit_slug"], "school-18")

    def test_approve_moves_family_even_when_location_already_matches(self):
        family = PortalFamily.objects.create(unit=self.main, slug="patel", name="Patel")
        app = _make_application(family, location="school_18", status="under_review")

        approve_application(app, program_location="school_18")
        family.refresh_from_db()

        self.assertEqual(family.unit_id, self.school_18.id)
        app.refresh_from_db()
        self.assertEqual(app.status, "approved")


class FamilyListRowTests(TestCase):
    def setUp(self):
        self.unit = PortalUnit.objects.create(slug="school-18", name="School 18", is_active=True)

    def test_families_for_staff_expands_children_into_separate_rows(self):
        family = PortalFamily.objects.create(unit=self.unit, slug="jacobs", name="Jacobs", balance=Decimal("80.00"))
        child_one = family.children.create(name="Jordan Jacobs", school="Lincoln Elementary", is_active=True)
        child_two = family.children.create(name="Maya Jacobs", school="Lincoln Elementary", is_active=True)
        PortalLedgerEntry.objects.create(
            family=family,
            child_name=child_one.name,
            date="2026-09-01",
            entry_type="charge",
            description="Weekly tuition",
            amount=Decimal("35.00"),
        )
        PortalLedgerEntry.objects.create(
            family=family,
            child_name=child_two.name,
            date="2026-09-01",
            entry_type="charge",
            description="Weekly tuition",
            amount=Decimal("45.00"),
        )

        rows = families_for_staff(self.unit)
        jacobs_rows = [row for row in rows if row["slug"] == "jacobs"]

        self.assertEqual(len(jacobs_rows), 2)
        self.assertEqual(jacobs_rows[0]["child_name"], "Jordan Jacobs")
        self.assertEqual(jacobs_rows[1]["child_name"], "Maya Jacobs")
        self.assertEqual(jacobs_rows[0]["child_balance"], "35.00")
        self.assertEqual(jacobs_rows[1]["child_balance"], "45.00")
        self.assertEqual(jacobs_rows[0]["family_balance"], "80.00")
        self.assertTrue(jacobs_rows[0]["is_first_child"])
        self.assertFalse(jacobs_rows[1]["is_first_child"])

    def test_child_balance_map_sums_ledger_entries_per_child(self):
        family = PortalFamily.objects.create(unit=self.unit, slug="nguyen", name="Nguyen")
        PortalLedgerEntry.objects.create(
            family=family,
            child_name="An Nguyen",
            date="2026-09-01",
            entry_type="charge",
            description="Weekly tuition",
            amount=Decimal("25.00"),
        )
        PortalLedgerEntry.objects.create(
            family=family,
            child_name="An Nguyen",
            date="2026-09-02",
            entry_type="payment",
            description="Card payment",
            amount=Decimal("-10.00"),
        )

        balances = child_balance_map(family)
        self.assertEqual(balances["An Nguyen"], Decimal("15.00"))

    def test_expand_demo_families_splits_multi_child_family(self):
        from portal.demo_data import FAMILIES

        rows = expand_demo_families(FAMILIES)
        jacobs_rows = [row for row in rows if row["slug"] == "jacobs"]
        self.assertEqual(len(jacobs_rows), 2)
        self.assertEqual({row["child_name"] for row in jacobs_rows}, {"Jordan Jacobs", "Maya Jacobs"})

    def test_unique_households_follow_list_order_and_skip_extra_children(self):
        from portal.family_list import adjacent_households, unique_households_from_rows

        family_a = PortalFamily.objects.create(unit=self.unit, slug="chen", name="Chen")
        family_b = PortalFamily.objects.create(unit=self.unit, slug="jacobs", name="Jacobs")
        family_a.children.create(name="Ethan Chen", is_active=True)
        family_b.children.create(name="Jordan Jacobs", is_active=True)
        family_b.children.create(name="Maya Jacobs", is_active=True)

        households = unique_households_from_rows(families_for_staff(self.unit))
        self.assertEqual([row["slug"] for row in households], ["chen", "jacobs"])
        previous, nxt = adjacent_households(households, slug="chen")
        self.assertIsNone(previous)
        self.assertEqual(nxt["slug"], "jacobs")
        previous, nxt = adjacent_households(households, slug="jacobs", family_id=family_b.pk)
        self.assertEqual(previous["slug"], "chen")
        self.assertIsNone(nxt)


class SchoolBusRosterTests(TestCase):
    def setUp(self):
        self.unit = PortalUnit.objects.create(slug="school-18", name="School 18", is_active=True)

    def test_build_school_bus_roster_groups_by_school_attending(self):
        family_a = PortalFamily.objects.create(unit=self.unit, slug="williams", name="Williams")
        family_b = PortalFamily.objects.create(unit=self.unit, slug="jacobs", name="Jacobs")
        family_a.children.create(name="Aiden Williams", grade="3rd", school="Roosevelt Elementary", is_active=True)
        family_b.children.create(name="Jordan Jacobs", grade="4th", school="Lincoln Elementary", is_active=True)
        family_b.children.create(name="Maya Jacobs", grade="1st", school="Lincoln Elementary", is_active=True)

        sections = build_school_bus_roster(self.unit)
        schools = {section["school"]: section["children"] for section in sections}

        self.assertEqual(len(sections), 2)
        self.assertEqual(len(schools["Lincoln Elementary"]), 2)
        self.assertEqual(len(schools["Roosevelt Elementary"]), 1)
        self.assertEqual(schools["Lincoln Elementary"][0]["child"], "Jordan Jacobs")
        self.assertTrue(schools["Lincoln Elementary"][0]["child_id"])

    def test_filter_school_bus_roster_keeps_chosen_schools(self):
        family_a = PortalFamily.objects.create(unit=self.unit, slug="williams", name="Williams")
        family_b = PortalFamily.objects.create(unit=self.unit, slug="jacobs", name="Jacobs")
        family_a.children.create(name="Aiden Williams", grade="3rd", school="Roosevelt Elementary", is_active=True)
        family_b.children.create(name="Jordan Jacobs", grade="4th", school="Lincoln Elementary", is_active=True)
        sections = build_school_bus_roster(self.unit)
        filtered = filter_school_bus_roster(sections, ["Lincoln Elementary"])
        self.assertEqual([section["school"] for section in filtered], ["Lincoln Elementary"])
        self.assertEqual(filter_school_bus_roster(sections, []), sections)

    def test_staff_report_can_filter_schools_to_print(self):
        from django.contrib.auth import get_user_model
        from django.test import override_settings
        from django.urls import reverse

        from portal.models import PortalStaffAccount
        from portal.staff_auth import PORTAL_AUTH_SESSION_KEY

        family_a = PortalFamily.objects.create(unit=self.unit, slug="williams", name="Williams")
        family_b = PortalFamily.objects.create(unit=self.unit, slug="jacobs", name="Jacobs")
        family_a.children.create(name="Aiden Williams", grade="3rd", school="Roosevelt Elementary", is_active=True)
        family_b.children.create(name="Jordan Jacobs", grade="4th", school="Lincoln Elementary", is_active=True)
        user = get_user_model().objects.create_user(username="staff:bus", password="StaffPass123!")
        PortalStaffAccount.objects.create(
            user=user,
            unit=self.unit,
            display_name="Bus Staff",
            role="Unit director",
            is_active=True,
        )
        self.client.force_login(user)
        session = self.client.session
        session[PORTAL_AUTH_SESSION_KEY] = "staff"
        session.save()
        with override_settings(PORTAL_PREVIEW_MODE=False):
            all_schools = self.client.get(reverse("portal_staff_school_bus_report"))
            filtered = self.client.get(
                reverse("portal_staff_school_bus_report"),
                {"school": "Lincoln Elementary"},
            )
        self.assertEqual(all_schools.status_code, 200)
        self.assertContains(all_schools, "Schools to print")
        self.assertContains(all_schools, "portal-collapse-skip")
        self.assertContains(all_schools, "Lincoln Elementary")
        self.assertContains(all_schools, "Roosevelt Elementary")
        self.assertEqual(filtered.status_code, 200)
        self.assertContains(filtered, "Jordan Jacobs")
        self.assertContains(filtered, "Aiden Williams")
        self.assertEqual(filtered.context["selected_schools"], {"Lincoln Elementary"})
        self.assertContains(filtered, "Schools to print")


class ChildSchoolEditTests(TestCase):
    def setUp(self):
        self.unit = PortalUnit.objects.create(slug="school-18", name="School 18", is_active=True)
        self.family = PortalFamily.objects.create(unit=self.unit, slug="jacobs", name="Jacobs")
        self.child = self.family.children.create(
            name="Jordan Jacobs",
            school="PS 18",
            is_active=True,
        )
        self.app = _make_application(self.family, location="school_18", status="approved")
        self.app.student_first_name = "Jordan"
        self.app.student_last_name = "Jacobs"
        self.app.student_school = "PS 18"
        self.app.save()

    def test_update_child_school_syncs_application(self):
        from portal.member_admin import update_child_school

        update_child_school(child=self.child, school="Paterson School 18")
        self.child.refresh_from_db()
        self.app.refresh_from_db()
        self.assertEqual(self.child.school, "Paterson School 18")
        self.assertEqual(self.app.student_school, "Paterson School 18")

    def test_rename_group_collapses_duplicate_school_names(self):
        from portal.member_admin import rename_children_school
        from portal.staff_services import build_school_bus_roster

        sibling = self.family.children.create(
            name="Maya Jacobs",
            school="School 18 Paterson",
            is_active=True,
        )
        self.assertEqual(len(build_school_bus_roster(self.unit)), 2)

        count = rename_children_school([self.child.pk, sibling.pk], "Paterson School 18", unit=self.unit)
        self.assertEqual(count, 2)
        sections = build_school_bus_roster(self.unit)
        self.assertEqual(len(sections), 1)
        self.assertEqual(sections[0]["school"], "Paterson School 18")
        self.assertEqual(len(sections[0]["children"]), 2)

    def test_staff_can_post_school_update(self):
        from django.contrib.auth import get_user_model
        from django.test import override_settings
        from django.urls import reverse

        from portal.models import PortalStaffAccount
        from portal.staff_auth import PORTAL_AUTH_SESSION_KEY

        user = get_user_model().objects.create_user(username="staff:tester", password="StaffPass123!")
        PortalStaffAccount.objects.create(
            user=user,
            unit=self.unit,
            display_name="Tester",
            role="Unit director",
            is_active=True,
        )
        self.client.force_login(user)
        session = self.client.session
        session[PORTAL_AUTH_SESSION_KEY] = "staff"
        session.save()

        with override_settings(PORTAL_PREVIEW_MODE=False):
            response = self.client.post(
                reverse("portal_staff_update_child_school"),
                {
                    "child_id": str(self.child.pk),
                    "school": "Paterson School 18",
                    "next": "/portal/staff/families/",
                },
            )
        self.assertEqual(response.status_code, 302)
        self.child.refresh_from_db()
        self.assertEqual(self.child.school, "Paterson School 18")


def _staff_login(client, user, area="staff"):
    client.force_login(user)
    session = client.session
    session[PORTAL_AUTH_SESSION_KEY] = area
    session.save()


class MultiUnitFamilyVisibilityTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.school_18 = PortalUnit.objects.create(
            slug="school-18", name="School 18", program_type="after_school", is_active=True
        )
        self.school_26 = PortalUnit.objects.create(
            slug="school-26", name="School 26", program_type="after_school", is_active=True
        )
        self.program_18 = PortalProgram.objects.create(
            unit=self.school_18,
            name="After-School 18",
            start_time=time(15, 0),
            end_time=time(18, 0),
            is_active=True,
        )
        self.program_26 = PortalProgram.objects.create(
            unit=self.school_26,
            name="After-School 26",
            start_time=time(15, 0),
            end_time=time(18, 0),
            is_active=True,
        )
        self.family = PortalFamily.objects.create(
            unit=self.school_18,
            slug="rivera",
            name="Rivera",
            primary_contact="Pat Rivera",
            balance=Decimal("80.00"),
            status="Active",
            program_label="After-School",
        )
        self.child_a = self.family.children.create(
            name="Child A Rivera",
            school="School 18",
            grade="3rd",
            is_active=True,
            unit=self.school_18,
        )
        self.child_b = self.family.children.create(
            name="Child B Rivera",
            school="School 26",
            grade="1st",
            is_active=True,
            unit=self.school_26,
        )
        PortalLedgerEntry.objects.create(
            family=self.family,
            child_name=self.child_a.name,
            date="2026-09-01",
            entry_type="charge",
            description="School 18 tuition",
            amount=Decimal("35.00"),
        )
        PortalLedgerEntry.objects.create(
            family=self.family,
            child_name=self.child_b.name,
            date="2026-09-01",
            entry_type="charge",
            description="School 26 tuition",
            amount=Decimal("45.00"),
        )
        self.parent_user = User.objects.create_user(
            username="parent:rivera",
            password="ParentPass123",
            email="pat.rivera@example.com",
        )
        PortalParentAccount.objects.create(user=self.parent_user, family=self.family)
        self.staff_18 = User.objects.create_user(username="staff:s18", password="StaffPass123!")
        PortalStaffAccount.objects.create(
            user=self.staff_18,
            unit=self.school_18,
            display_name="School 18 Staff",
            role="Unit director",
            is_active=True,
        )
        self.staff_26 = User.objects.create_user(username="staff:s26", password="StaffPass123!")
        PortalStaffAccount.objects.create(
            user=self.staff_26,
            unit=self.school_26,
            display_name="School 26 Staff",
            role="Unit director",
            is_active=True,
        )
        self.admin = User.objects.create_user(username="staff:admin", password="AdminPass123!")
        PortalStaffAccount.objects.create(
            user=self.admin,
            unit=self.school_18,
            display_name="Portal Admin",
            role="Portal admin",
            all_units_access=True,
            is_active=True,
        )

    def test_staff_family_list_only_shows_children_in_their_unit(self):
        school_18_rows = families_for_staff(self.school_18)
        school_26_rows = families_for_staff(self.school_26)
        self.assertEqual({row["child_name"] for row in school_18_rows}, {"Child A Rivera"})
        self.assertEqual({row["child_name"] for row in school_26_rows}, {"Child B Rivera"})
        self.assertNotIn("Child B Rivera", [row["child_name"] for row in school_18_rows])
        self.assertNotIn("Child A Rivera", [row["child_name"] for row in school_26_rows])

    def test_admin_sees_both_children_on_one_family_account(self):
        rows = get_admin_families_live()
        rivera = [row for row in rows if row["slug"] == "rivera"]
        self.assertEqual({row["child_name"] for row in rivera}, {"Child A Rivera", "Child B Rivera"})
        by_child = {row["child_name"]: row["unit"] for row in rivera}
        self.assertEqual(by_child["Child A Rivera"], "School 18")
        self.assertEqual(by_child["Child B Rivera"], "School 26")

    def test_staff_family_profile_hides_the_other_unit_child(self):
        profile_18 = family_profile_live("rivera", unit=self.school_18, family_id=self.family.pk)
        profile_26 = family_profile_live("rivera", unit=self.school_26, family_id=self.family.pk)
        admin_profile = family_profile_live("rivera", family_id=self.family.pk)
        self.assertEqual({child["name"] for child in profile_18["children"]}, {"Child A Rivera"})
        self.assertEqual({child["name"] for child in profile_26["children"]}, {"Child B Rivera"})
        self.assertEqual({child["name"] for child in admin_profile["children"]}, {"Child A Rivera", "Child B Rivera"})

    def test_reports_stay_unit_scoped(self):
        roster_18 = build_roster(self.school_18, self.program_18, date(2026, 9, 8))
        roster_26 = build_roster(self.school_26, self.program_26, date(2026, 9, 8))
        self.assertEqual({row["child"] for row in roster_18}, {"Child A Rivera"})
        self.assertEqual({row["child"] for row in roster_26}, {"Child B Rivera"})

        medical_18 = {row["child"] for row in build_medical_report_rows(self.school_18)}
        self.assertEqual(medical_18, {"Child A Rivera"})
        self.assertNotIn("Child B Rivera", medical_18)

        bus_18_names = [
            child["child"]
            for section in build_school_bus_roster(self.school_18)
            for child in section["children"]
        ]
        self.assertEqual(bus_18_names, ["Child A Rivera"])
        self.assertNotIn("Child B Rivera", bus_18_names)

        program_roster = {row["child"] for row in get_program_roster(self.school_18)}
        self.assertEqual(program_roster, {"Child A Rivera"})

        _programs, pickup_rows = pickup_report_for_unit(self.school_18)
        pickup_names = {row["child"] for row in pickup_rows}
        self.assertIn("Child A Rivera", pickup_names)
        self.assertNotIn("Child B Rivera", pickup_names)

        contact_names = {row["child"] for row in emergency_contact_report_for_unit(self.school_18)}
        self.assertEqual(contact_names, {"Child A Rivera"})
        self.assertNotIn("Child B Rivera", contact_names)

        weekly = weekly_attendance_report_data(self.school_18, self.program_18, date(2026, 9, 7))
        self.assertEqual({row["child"] for row in weekly["weekly_rows"]}, {"Child A Rivera"})

        plan_rows = billing_plan_rows({"unit": "school-18"})
        self.assertEqual({row["child"] for row in plan_rows["rows"]}, {"Child A Rivera"})
        self.assertNotIn("Child B Rivera", {row["child"] for row in plan_rows["rows"]})

    def test_staff_billing_hides_other_unit_child_names(self):
        billing = prepare_billing_for_staff(self.family, {"can_add_charge": True}, unit=self.school_18)
        child_names = {child["name"] for child in billing.get("children") or []}
        ledger_children = {row.get("child") for row in billing.get("ledger") or []}
        self.assertEqual(child_names, {"Child A Rivera"})
        self.assertNotIn("Child B Rivera", child_names)
        self.assertNotIn("Child B Rivera", ledger_children)
        self.assertIn("Child A Rivera", ledger_children)

    def test_parent_portal_lists_both_children(self):
        profile = get_profile_live(self.family, self.family.parent_account)
        names = {child["name"] for child in profile["children"]}
        self.assertIn("Child A Rivera", names)
        self.assertIn("Child B Rivera", names)

    def test_approving_sibling_at_another_school_does_not_move_the_family(self):
        app = _make_application(self.family, location="school_26", status="under_review")
        app.student_first_name = "Child C"
        app.student_last_name = "Rivera"
        app.student_school = "School 26"
        app.save()
        approve_application(app, program_location="school_26")
        self.family.refresh_from_db()
        self.assertEqual(self.family.unit_id, self.school_18.id)
        child_c = self.family.children.get(name="Child C Rivera")
        self.assertEqual(child_c.unit_id, self.school_26.id)
        self.assertEqual(repair_family_units_from_applications(), 0)
        self.family.refresh_from_db()
        self.assertEqual(self.family.unit_id, self.school_18.id)

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_staff_and_admin_and_parent_pages(self):
        _staff_login(self.client, self.staff_18, "staff")
        session = self.client.session
        session["staff_unit_slug"] = "school-18"
        session.save()
        families = self.client.get(reverse("portal_staff_page", kwargs={"page": "families"}))
        self.assertEqual(families.status_code, 200)
        self.assertContains(families, "Child A Rivera")
        self.assertNotContains(families, "Child B Rivera")
        self.assertContains(families, "School 18 — 1 families · 1 children listed")
        profile = self.client.get(reverse("portal_staff_family_detail", kwargs={"family_slug": "rivera"}))
        self.assertEqual(profile.status_code, 200)
        self.assertContains(profile, "Child A Rivera")
        self.assertNotContains(profile, "Child B Rivera")
        attendance = self.client.get(reverse("portal_staff_page", kwargs={"page": "attendance"}))
        self.assertEqual(attendance.status_code, 200)
        self.assertContains(attendance, "Child A Rivera")
        self.assertNotContains(attendance, "Child B Rivera")
        medical = self.client.get(reverse("portal_staff_medical_report"))
        self.assertEqual(medical.status_code, 200)
        self.assertContains(medical, "Child A Rivera")
        self.assertNotContains(medical, "Child B Rivera")

        _staff_login(self.client, self.staff_26, "staff")
        session = self.client.session
        session["staff_unit_slug"] = "school-26"
        session.save()
        families_26 = self.client.get(reverse("portal_staff_page", kwargs={"page": "families"}))
        self.assertEqual(families_26.status_code, 200)
        self.assertContains(families_26, "Child B Rivera")
        self.assertNotContains(families_26, "Child A Rivera")

        _staff_login(self.client, self.admin, "admin")
        admin_families = self.client.get(reverse("portal_admin_page", kwargs={"page": "families"}))
        self.assertEqual(admin_families.status_code, 200)
        self.assertContains(admin_families, "Child A Rivera")
        self.assertContains(admin_families, "Child B Rivera")
        admin_account = self.client.get(reverse("portal_admin_family_detail", kwargs={"family_slug": "rivera"}))
        self.assertEqual(admin_account.status_code, 200)
        self.assertContains(admin_account, "Child A Rivera")
        self.assertContains(admin_account, "Child B Rivera")

        self.client.force_login(self.parent_user)
        session = self.client.session
        session[PORTAL_AUTH_SESSION_KEY] = "parent"
        session.save()
        parent_profile = self.client.get(reverse("portal_parent_page", kwargs={"page": "profile"}))
        self.assertEqual(parent_profile.status_code, 200)
        self.assertContains(parent_profile, "Child A Rivera")
        self.assertContains(parent_profile, "Child B Rivera")
