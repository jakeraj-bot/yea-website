from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from enrollment.application_review import approve_application
from enrollment.forms import ProgramStepForm
from portal.drop_off_services import (
    create_drop_off_request,
    family_has_drop_off,
    save_settings,
    save_slot,
    set_child_drop_off,
)
from portal.models import (
    PortalChild,
    PortalDropOffBooking,
    PortalFamily,
    PortalParentAccount,
    PortalStaffAccount,
    PortalUnit,
)
from portal.staff_auth import PORTAL_AUTH_SESSION_KEY
from portal.tests.test_family_units import _make_application


class DropOffProgramTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.unit = PortalUnit.objects.create(slug="school-18", name="School 18", is_active=True)
        self.family = PortalFamily.objects.create(unit=self.unit, slug="jacobs", name="Jacobs")
        self.child = PortalChild.objects.create(family=self.family, name="Jordan Jacobs", is_active=True)
        parent_user = User.objects.create_user(
            username="parent:jacobs",
            password="ParentPass123",
            email="parent@example.com",
        )
        self.parent = PortalParentAccount.objects.create(user=parent_user, family=self.family)
        self.admin_user = User.objects.create_user(username="staff:portaladmin", password="AdminPass123")
        PortalStaffAccount.objects.create(
            user=self.admin_user,
            unit=self.unit,
            display_name="Portal Admin",
            role="Portal admin",
            all_units_access=True,
            is_active=True,
        )
        self.staff_user = User.objects.create_user(username="staff:unitstaff", password="StaffPass123")
        PortalStaffAccount.objects.create(
            user=self.staff_user,
            unit=self.unit,
            display_name="Unit Staff",
            role="Unit director",
            all_units_access=False,
            is_active=True,
        )
        self.slot = save_slot(
            {
                "unit_id": self.unit.pk,
                "weekday": timezone.localdate().weekday() if timezone.localdate().weekday() < 5 else 0,
                "start_time": "15:00",
                "label": "Regular 3:00 PM",
                "capacity": 2,
                "price": "25.00",
                "school_note": "School 18 regular dismissal",
            }
        )
        save_settings({"request_cutoff_time": "23:59", "book_ahead_days": "14", "booking_open": "on"})

    def _login(self, user, area):
        self.client.force_login(user)
        session = self.client.session
        session[PORTAL_AUTH_SESSION_KEY] = area
        session.save()

    def _care_date(self):
        today = timezone.localdate()
        if today.weekday() == self.slot.weekday:
            return today
        delta = (self.slot.weekday - today.weekday()) % 7
        if delta == 0:
            delta = 7
        return today + timedelta(days=delta)

    def test_apply_form_offers_drop_off_and_blocks_regular_combo(self):
        form = ProgramStepForm(
            data={"programs": ["drop_off", "after_school"], "program_location": "school_18"}
        )
        self.assertFalse(form.is_valid())
        self.assertIn("drop-off or regular", str(form.errors))

        ok = ProgramStepForm(data={"programs": ["drop_off"], "program_location": "school_18"})
        self.assertTrue(ok.is_valid(), ok.errors)
        self.assertEqual(ok.cleaned_data["program"], "drop_off")

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_approving_drop_off_application_sets_child_flag(self):
        app = _make_application(self.family)
        app.program = "drop_off"
        app.status = "under_review"
        app.save(update_fields=["program", "status"])
        approve_application(app)
        ada = self.family.children.get(name="Ada Jacobs")
        self.family.refresh_from_db()
        self.assertTrue(ada.is_drop_off)
        self.assertTrue(family_has_drop_off(self.family))
        self.assertIn("drop-off", self.family.program_label.lower())

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_parent_tab_only_for_drop_off_members(self):
        self._login(self.parent.user, "parent")
        hidden = self.client.get(reverse("portal_parent_page", kwargs={"page": "dashboard"}))
        self.assertEqual(hidden.status_code, 200)
        self.assertNotContains(hidden, ">Drop-off</a>")
        missing = self.client.get(reverse("portal_parent_page", kwargs={"page": "drop-off"}))
        self.assertEqual(missing.status_code, 404)

        set_child_drop_off(self.child, True)
        shown = self.client.get(reverse("portal_parent_page", kwargs={"page": "dashboard"}))
        self.assertContains(shown, ">Drop-off</a>")
        page = self.client.get(reverse("portal_parent_page", kwargs={"page": "drop-off"}))
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, "Book a drop-off day")

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_admin_can_switch_member_to_drop_off(self):
        self._login(self.admin_user, "admin")
        response = self.client.post(
            reverse("portal_staff_billing_action", kwargs={"family_slug": "jacobs"}),
            {
                "portal_area": "admin",
                "action": "update_program",
                "child_name": "Jordan Jacobs",
                "program": "drop_off",
                "next": reverse("portal_admin_family_plans", kwargs={"family_slug": "jacobs"}),
            },
        )
        self.assertEqual(response.status_code, 302)
        self.child.refresh_from_db()
        self.assertTrue(self.child.is_drop_off)

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_parent_request_shows_on_staff_and_admin_lists(self):
        set_child_drop_off(self.child, True)
        care_date = self._care_date()
        self._login(self.parent.user, "parent")
        book = self.client.post(
            reverse("portal_parent_drop_off_book"),
            {
                "child_id": str(self.child.pk),
                "slot_id": str(self.slot.pk),
                "care_date": care_date.isoformat(),
            },
        )
        self.assertEqual(book.status_code, 302)
        booking = PortalDropOffBooking.objects.get(child=self.child, care_date=care_date)
        self.assertEqual(booking.status, PortalDropOffBooking.STATUS_REQUESTED)
        self.assertEqual(booking.amount, Decimal("25.00"))

        parent_page = self.client.get(
            reverse("portal_parent_page", kwargs={"page": "drop-off"}),
            {"date": care_date.isoformat()},
        )
        self.assertContains(parent_page, "We have these requests")
        self.assertContains(parent_page, "Jordan Jacobs")

        self._login(self.staff_user, "staff")
        staff = self.client.get(
            reverse("portal_staff_page", kwargs={"page": "drop-off-pickup"}),
            {"date": care_date.isoformat()},
        )
        self.assertContains(staff, "Jordan Jacobs")
        self.assertContains(staff, "waiting for payment")

        self._login(self.admin_user, "admin")
        admin = self.client.get(
            reverse("portal_admin_page", kwargs={"page": "drop-off-pickup"}),
            {"date": care_date.isoformat()},
        )
        self.assertContains(admin, "Jordan Jacobs")
        settings_page = self.client.get(reverse("portal_admin_page", kwargs={"page": "drop-off"}))
        self.assertContains(settings_page, "Request cutoff")
        self.assertContains(settings_page, "Regular 3:00 PM")

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_full_slot_and_cutoff_block_booking(self):
        set_child_drop_off(self.child, True)
        care_date = self._care_date()
        extra_family = PortalFamily.objects.create(unit=self.unit, slug="lee", name="Lee")
        extra_child = PortalChild.objects.create(
            family=extra_family, name="Ada Lee", is_active=True, is_drop_off=True
        )
        sibling = PortalChild.objects.create(
            family=extra_family, name="Bea Lee", is_active=True, is_drop_off=True
        )
        create_drop_off_request(extra_family, extra_child.pk, self.slot.pk, care_date)
        create_drop_off_request(extra_family, sibling.pk, self.slot.pk, care_date)
        with self.assertRaises(ValueError):
            create_drop_off_request(self.family, self.child.pk, self.slot.pk, care_date)

        save_settings({"request_cutoff_time": "23:59", "book_ahead_days": "14", "booking_open": ""})
        later = PortalFamily.objects.create(unit=self.unit, slug="chen", name="Chen")
        later_child = PortalChild.objects.create(
            family=later, name="Ada Chen", is_active=True, is_drop_off=True
        )
        other_slot = save_slot(
            {
                "unit_id": self.unit.pk,
                "weekday": care_date.weekday(),
                "start_time": "13:00",
                "label": "Early Wednesday 1:00 PM",
                "capacity": 8,
                "price": "20.00",
            }
        )
        with self.assertRaises(ValueError):
            create_drop_off_request(later, later_child.pk, other_slot.pk, care_date)
        save_settings({"request_cutoff_time": "00:00", "book_ahead_days": "14", "booking_open": "on"})
        with self.assertRaises(ValueError):
            create_drop_off_request(later, later_child.pk, other_slot.pk, timezone.localdate())

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_admin_can_save_cutoff_and_early_slot(self):
        self._login(self.admin_user, "admin")
        response = self.client.post(
            reverse("portal_admin_drop_off_save"),
            {"request_cutoff_time": "10:00", "book_ahead_days": "7", "booking_open": "on", "parent_note": "Pay when you book."},
        )
        self.assertEqual(response.status_code, 302)
        slot = self.client.post(
            reverse("portal_admin_drop_off_slot_save"),
            {
                "unit_id": self.unit.pk,
                "weekday": "2",
                "start_time": "13:00",
                "label": "Early Wednesday 1:00 PM",
                "capacity": "6",
                "price": "20.00",
                "school_note": "School 18 dismisses at 1:00 on Wednesdays",
            },
        )
        self.assertEqual(slot.status_code, 302)
        settings_page = self.client.get(reverse("portal_admin_page", kwargs={"page": "drop-off"}))
        self.assertContains(settings_page, "Early Wednesday 1:00 PM")
        self.assertContains(settings_page, "Pay when you book.")
