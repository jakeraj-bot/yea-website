from datetime import date, time
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse

from enrollment.application_review import approve_application
from enrollment.portal_integration import create_portal_account_from_enrollment, find_existing_family_for_parent
from enrollment.staff_application import create_staff_application
from portal.family_merge import (
    children_are_same_person,
    merge_families,
    pick_survivor_family,
    search_families_for_merge,
    suggested_merge_families,
)
from portal.member_admin import create_account_from_application
from portal.models import (
    AttendanceRecord,
    PortalChild,
    PortalFamily,
    PortalLedgerEntry,
    PortalParentAccount,
    PortalPayment,
    PortalProgram,
    PortalStaffAccount,
    PortalUnit,
)
from portal.staff_auth import PORTAL_AUTH_SESSION_KEY
from portal.tests.test_family_units import _make_application
from portal.usernames import portal_username


def _session(email, first, last, location="school_18", dob=date(2016, 5, 1), family_name="Rivera"):
    return {
        "family_name": family_name,
        "primary_email": email,
        "primary_email_address": email,
        "primary_first_name": "Jakera",
        "primary_last_name": family_name,
        "children": [
            {
                "student_first_name": first,
                "student_last_name": last,
                "student_dob": dob,
                "program": "after_school",
                "program_location": location,
            }
        ],
    }


class FindExistingFamilyTests(TestCase):
    def setUp(self):
        self.school_18 = PortalUnit.objects.create(slug="school-18", name="School 18", is_active=True)
        self.school_26 = PortalUnit.objects.create(slug="school-26", name="School 26", is_active=True)
        self.family = PortalFamily.objects.create(
            unit=self.school_18, slug="rivera", name="Rivera", primary_contact="Jakera Rivera"
        )
        User = get_user_model()
        self.parent = User.objects.create_user(
            username=portal_username("parent", "jakera"),
            email="jakera@example.com",
            password="ParentPass123",
        )
        PortalParentAccount.objects.create(user=self.parent, family=self.family)

    def test_finds_family_by_parent_email_across_units(self):
        found = find_existing_family_for_parent(email="jakera@example.com")
        self.assertEqual(found.pk, self.family.pk)

    def test_finds_family_by_child_name_and_dob(self):
        child = self.family.children.create(name="Danuska Rivera", is_active=True, unit=self.school_18)
        app = _make_application(self.family, location="school_18", status="approved")
        app.student_first_name = "Danuska"
        app.student_last_name = "Rivera"
        app.student_dob = date(2016, 5, 1)
        app.primary_email = "other@example.com"
        app.save()
        found = find_existing_family_for_parent(
            child_first="Danuska",
            child_last="Rivera",
            child_dob=date(2016, 5, 1),
        )
        self.assertEqual(found.pk, self.family.pk)
        self.assertEqual(child.family_id, self.family.pk)

    def test_does_not_match_a_different_child_who_shares_a_first_name(self):
        self.family.children.create(name="Danuska Rivera", is_active=True)
        other = PortalFamily.objects.create(unit=self.school_26, slug="lee", name="Lee")
        other.children.create(name="Danuska Lee", is_active=True)
        app = _make_application(other, location="school_26", status="approved")
        app.student_first_name = "Danuska"
        app.student_last_name = "Lee"
        app.student_dob = date(2015, 1, 1)
        app.primary_email = "lee@example.com"
        app.save()
        found = find_existing_family_for_parent(
            email="nobody@example.com",
            child_first="Danuska",
            child_last="Lee",
            child_dob=date(2015, 1, 1),
        )
        self.assertEqual(found.pk, other.pk)
        not_rivera = find_existing_family_for_parent(
            child_first="Danuska",
            child_last="Rivera",
            child_dob=date(2016, 5, 1),
        )
        self.assertNotEqual(getattr(not_rivera, "pk", None), other.pk)


class DuplicateAccountPreventionTests(TestCase):
    def setUp(self):
        self.school_18 = PortalUnit.objects.create(slug="school-18", name="School 18", is_active=True)
        self.school_26 = PortalUnit.objects.create(slug="school-26", name="School 26", is_active=True)

    def test_second_apply_with_same_email_reuses_family(self):
        family, user, created = create_portal_account_from_enrollment(
            _session("jakera@example.com", "Danuska", "Rivera", "school_18"),
            "jakera",
            "ParentPass123",
        )
        self.assertTrue(created)
        family2, user2, created2 = create_portal_account_from_enrollment(
            _session("jakera@example.com", "Danuska", "Rivera", "school_26"),
            "jakera2",
            "ParentPass123",
        )
        self.assertFalse(created2)
        self.assertEqual(family2.pk, family.pk)
        self.assertEqual(user2.pk, user.pk)
        self.assertEqual(PortalFamily.objects.count(), 1)
        self.assertEqual(PortalParentAccount.objects.count(), 1)

    def test_create_account_from_application_does_not_make_a_second_family(self):
        family, _user, _created = create_portal_account_from_enrollment(
            _session("jakera@example.com", "Danuska", "Rivera"),
            "jakera",
            "ParentPass123",
        )
        app = _make_application(family, location="school_26", status="under_review")
        app.portal_family = None
        app.primary_email = "jakera@example.com"
        app.student_first_name = "Danuska"
        app.student_last_name = "Rivera"
        app.save()
        reused, username = create_account_from_application(app, "newlogin", "ParentPass123")
        app.refresh_from_db()
        self.assertEqual(reused.pk, family.pk)
        self.assertEqual(app.portal_family_id, family.pk)
        self.assertEqual(username, "jakera")
        self.assertEqual(PortalFamily.objects.count(), 1)
        self.assertEqual(PortalParentAccount.objects.count(), 1)

    def test_staff_add_at_second_unit_stays_one_family(self):
        first = create_staff_application(
            {
                "family_name": "Rivera",
                "primary_parent_name": "Jakera Rivera",
                "email": "jakera@example.com",
                "phone": "555-0100",
                "home_address": "1 Main St",
                "student_first_name": "Danuska",
                "student_last_name": "Rivera",
                "grade": "3rd",
                "payment_method": "private_pay",
                "student_dob": date(2016, 5, 1),
            },
            self.school_18,
        )
        second = create_staff_application(
            {
                "family_name": "Rivera",
                "primary_parent_name": "Jakera Rivera",
                "email": "jakera@example.com",
                "phone": "555-0100",
                "home_address": "1 Main St",
                "student_first_name": "Danuska",
                "student_last_name": "Rivera",
                "grade": "3rd",
                "payment_method": "private_pay",
                "student_dob": date(2016, 5, 1),
            },
            self.school_26,
        )
        self.assertEqual(first.portal_family_id, second.portal_family_id)
        self.assertEqual(PortalFamily.objects.count(), 1)

    def test_approve_second_application_does_not_create_a_family(self):
        family, _user, _created = create_portal_account_from_enrollment(
            _session("jakera@example.com", "Danuska", "Rivera"),
            "jakera",
            "ParentPass123",
        )
        app = _make_application(family, location="school_18", status="under_review")
        app.student_first_name = "Danuska"
        app.student_last_name = "Rivera"
        app.primary_email = "jakera@example.com"
        app.save()
        approve_application(app)
        sibling = _make_application(family, location="school_26", status="under_review")
        sibling.student_first_name = "Jordan"
        sibling.student_last_name = "Rivera"
        sibling.student_dob = date(2014, 3, 2)
        sibling.primary_email = "jakera@example.com"
        sibling.save()
        approve_application(sibling)
        self.assertEqual(PortalFamily.objects.count(), 1)
        names = set(family.children.values_list("name", flat=True))
        self.assertEqual(names, {"Danuska Rivera", "Jordan Rivera"})
        jordan = family.children.get(name="Jordan Rivera")
        self.assertEqual(jordan.unit_id, self.school_26.id)

    def test_logged_in_add_child_keeps_one_family(self):
        family, user, _created = create_portal_account_from_enrollment(
            _session("jakera@example.com", "Danuska", "Rivera"),
            "jakera",
            "ParentPass123",
        )
        from enrollment.portal_integration import link_applications_to_family

        extra = _make_application(family, location="school_26", status="under_review")
        extra.portal_family = None
        extra.student_first_name = "Maya"
        extra.student_last_name = "Rivera"
        extra.primary_email = "jakera@example.com"
        extra.save()
        link_applications_to_family([extra], family)
        extra.refresh_from_db()
        self.assertEqual(extra.portal_family_id, family.pk)
        self.assertEqual(PortalFamily.objects.filter(parent_account__user=user).count(), 1)


class FamilyMergeTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.school_18 = PortalUnit.objects.create(slug="school-18", name="School 18", is_active=True)
        self.school_26 = PortalUnit.objects.create(slug="school-26", name="School 26", is_active=True)
        self.program = PortalProgram.objects.create(
            unit=self.school_18,
            name="After-School 18",
            start_time=time(15, 0),
            end_time=time(18, 0),
            is_active=True,
        )
        self.keep = PortalFamily.objects.create(
            unit=self.school_18,
            slug="rivera",
            name="Rivera",
            primary_contact="Jakera Rivera",
            balance=Decimal("80.00"),
            status="Active",
        )
        self.drop = PortalFamily.objects.create(
            unit=self.school_26,
            slug="rivera-2",
            name="Rivera",
            primary_contact="Jakera Rivera",
            balance=Decimal("25.00"),
            status="Pending enrollment",
        )
        self.child = self.keep.children.create(
            name="Danuska Rivera", is_active=True, unit=self.school_18, grade="3rd"
        )
        self.dup_child = self.drop.children.create(
            name="Danuska Rivera", is_active=True, unit=self.school_26, grade="3rd"
        )
        keep_user = User.objects.create_user(
            username=portal_username("parent", "jakera"),
            email="jakera@example.com",
            password="ParentPass123",
        )
        drop_user = User.objects.create_user(
            username=portal_username("parent", "jakera2"),
            email="jakera@example.com",
            password="ParentPass123",
        )
        PortalParentAccount.objects.create(user=keep_user, family=self.keep)
        PortalParentAccount.objects.create(user=drop_user, family=self.drop)
        self.keep_app = _make_application(self.keep, location="school_18", status="approved")
        self.keep_app.student_first_name = "Danuska"
        self.keep_app.student_last_name = "Rivera"
        self.keep_app.student_dob = date(2016, 5, 1)
        self.keep_app.primary_email = "jakera@example.com"
        self.keep_app.save()
        self.drop_app = _make_application(self.drop, location="school_26", status="under_review")
        self.drop_app.student_first_name = "Danuska"
        self.drop_app.student_last_name = "Rivera"
        self.drop_app.student_dob = date(2016, 5, 1)
        self.drop_app.primary_email = "jakera@example.com"
        self.drop_app.save()
        PortalLedgerEntry.objects.create(
            family=self.keep,
            child_name="Danuska Rivera",
            date=date(2026, 9, 1),
            entry_type="charge",
            description="Weekly tuition",
            amount=Decimal("50.00"),
        )
        PortalLedgerEntry.objects.create(
            family=self.drop,
            child_name="Danuska Rivera",
            date=date(2026, 9, 2),
            entry_type="payment",
            description="Card payment",
            amount=Decimal("-25.00"),
        )
        PortalPayment.objects.create(
            family=self.drop,
            amount=Decimal("25.00"),
            status=PortalPayment.STATUS_PAID,
            payment_kind="balance",
        )
        AttendanceRecord.objects.create(
            child=self.child,
            program=self.program,
            date=date(2026, 9, 8),
            status=AttendanceRecord.STATUS_PRESENT,
        )

    def test_merge_keeps_one_family_and_payment_history(self):
        keep, dropped = merge_families(self.keep, self.drop)
        self.assertEqual(dropped, "Rivera")
        self.assertEqual(PortalFamily.objects.count(), 1)
        keep.refresh_from_db()
        self.assertEqual(keep.pk, self.keep.pk)
        self.assertEqual(keep.children.filter(name="Danuska Rivera").count(), 1)
        self.assertEqual(keep.ledger_entries.count(), 2)
        self.assertEqual(keep.payments.count(), 1)
        self.assertEqual(keep.enrollment_applications.count(), 2)
        self.assertEqual(keep.balance, Decimal("105.00"))
        self.assertEqual(PortalParentAccount.objects.filter(family=keep).count(), 1)
        self.assertFalse(get_user_model().objects.filter(username=portal_username("parent", "jakera2")).exists())
        self.assertTrue(AttendanceRecord.objects.filter(child__family=keep).exists())

    def test_does_not_merge_two_different_children_who_share_a_first_name(self):
        other = PortalFamily.objects.create(unit=self.school_18, slug="lee", name="Lee")
        other_child = other.children.create(name="Danuska Lee", is_active=True)
        other_app = _make_application(other, location="school_18", status="approved")
        other_app.student_first_name = "Danuska"
        other_app.student_last_name = "Lee"
        other_app.student_dob = date(2014, 1, 1)
        other_app.save()
        self.assertFalse(children_are_same_person(self.child, other_child))

    def test_pick_survivor_prefers_history(self):
        self.assertEqual(pick_survivor_family([self.keep, self.drop]).pk, self.keep.pk)

    def test_search_finds_danuska(self):
        children, families, apps = search_families_for_merge("Danuska")
        self.assertGreaterEqual(len(children), 2)
        self.assertEqual({child.family_id for child in children}, {self.keep.pk, self.drop.pk})
        self.assertGreaterEqual(len(apps), 2)

    def test_suggested_merge_finds_the_duplicate(self):
        matches = suggested_merge_families(self.keep)
        self.assertEqual({family.pk for family in matches}, {self.drop.pk})

    def test_management_command_merges_danuska_duplicates(self):
        call_command("merge_duplicate_families", search="Danuska", apply=True)
        self.assertEqual(PortalFamily.objects.count(), 1)
        family = PortalFamily.objects.get()
        self.assertEqual(family.children.filter(name="Danuska Rivera").count(), 1)
        self.assertEqual(family.payments.count(), 1)
        self.assertEqual(family.ledger_entries.count(), 2)

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_admin_merge_form_keeps_one_account(self):
        User = get_user_model()
        admin = User.objects.create_user(username="staff:yeaadmin", password="AdminPass123")
        PortalStaffAccount.objects.create(
            user=admin,
            unit=self.school_18,
            display_name="YEA Admin",
            role="Portal admin",
            all_units_access=True,
            is_active=True,
        )
        self.client.force_login(admin)
        session = self.client.session
        session[PORTAL_AUTH_SESSION_KEY] = "admin"
        session.save()
        response = self.client.post(
            reverse("portal_admin_member_ops"),
            {
                "action": "merge_family",
                "family_id": str(self.keep.pk),
                "family_slug": self.keep.slug,
                "source_family_id": str(self.drop.pk),
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(PortalFamily.objects.count(), 1)
        self.assertEqual(PortalFamily.objects.get().pk, self.keep.pk)

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_admin_family_page_shows_merge_box(self):
        User = get_user_model()
        admin = User.objects.create_user(username="staff:yeaadmin", password="AdminPass123")
        PortalStaffAccount.objects.create(
            user=admin,
            unit=self.school_18,
            display_name="YEA Admin",
            role="Portal admin",
            all_units_access=True,
            is_active=True,
        )
        self.client.force_login(admin)
        session = self.client.session
        session[PORTAL_AUTH_SESSION_KEY] = "admin"
        session.save()
        page = self.client.get(
            reverse("portal_admin_family_detail", kwargs={"family_slug": "rivera"}),
            {"id": self.keep.pk},
        )
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, "Merge a duplicate account")
        self.assertContains(page, str(self.drop.pk))
