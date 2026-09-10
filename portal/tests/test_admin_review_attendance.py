from datetime import time

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from portal.models import (
    AttendanceRecord,
    PortalChild,
    PortalFamily,
    PortalProgram,
    PortalStaffAccount,
    PortalUnit,
)
from portal.staff_auth import PORTAL_AUTH_SESSION_KEY


class AdminReviewAttendanceTests(TestCase):
    def setUp(self):
        self.school_18 = PortalUnit.objects.create(slug="school-18", name="School 18", is_active=True)
        self.school_26 = PortalUnit.objects.create(slug="school-26", name="School 26", is_active=True)
        self.program_18 = PortalProgram.objects.create(
            unit=self.school_18,
            name="After-School 2026–27",
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
        family_18 = PortalFamily.objects.create(unit=self.school_18, slug="jacobs", name="Jacobs")
        family_26 = PortalFamily.objects.create(unit=self.school_26, slug="lee", name="Lee")
        self.jordan = PortalChild.objects.create(
            family=family_18, name="Jordan Jacobs", grade="4th", is_active=True
        )
        self.nia = PortalChild.objects.create(
            family=family_26, name="Nia Lee", grade="4th", is_active=True
        )
        User = get_user_model()
        self.staff_user = User.objects.create_user(username="staff:weekly", password="StaffPass123!")
        PortalStaffAccount.objects.create(
            user=self.staff_user,
            unit=self.school_18,
            display_name="Weekly Staff",
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

    def _login(self, user, area):
        self.client.force_login(user)
        session = self.client.session
        session[PORTAL_AUTH_SESSION_KEY] = area
        session.save()

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_admin_review_attendance_lists_all_units_or_one_unit(self):
        self._login(self.admin_user, "admin")
        page = self.client.get(reverse("portal_admin_page", kwargs={"page": "attendance"}))
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, "Review attendance")
        self.assertContains(page, "How to review attendance")
        self.assertContains(page, "How to use this page")
        self.assertContains(page, "All units")
        self.assertContains(page, "Jordan Jacobs")
        self.assertContains(page, "Nia Lee")
        self.assertContains(page, 'name="unit"')
        self.assertContains(page, reverse("portal_admin_page", kwargs={"page": "attendance"}))

        school_26 = self.client.get(
            reverse("portal_admin_page", kwargs={"page": "attendance"}),
            {"unit": "school-26"},
        )
        self.assertContains(school_26, "Nia Lee")
        self.assertNotContains(school_26, "Jordan Jacobs")
        self.assertIn('value="school-26" selected', school_26.content.decode())

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_admin_can_mark_present_at_another_unit(self):
        self._login(self.admin_user, "admin")
        today = timezone.localdate()
        response = self.client.post(
            reverse("portal_staff_attendance_checkin"),
            {"child_id": str(self.nia.pk), "unit": "school-26", "date": today.isoformat()},
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("portal_admin_page", kwargs={"page": "attendance"}), response["Location"])
        record = AttendanceRecord.objects.get(child=self.nia, date=today)
        self.assertEqual(record.status, AttendanceRecord.STATUS_PRESENT)
        self.assertEqual(record.program_id, self.program_26.pk)

        absent = self.client.post(
            reverse("portal_staff_attendance_absent"),
            {"child_id": str(self.jordan.pk), "unit": "school-18", "date": today.isoformat()},
        )
        self.assertEqual(absent.status_code, 302)
        jordan_record = AttendanceRecord.objects.get(child=self.jordan, date=today)
        self.assertEqual(jordan_record.status, AttendanceRecord.STATUS_ABSENT)

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_staff_review_attendance_still_works_and_stays_on_staff_unit(self):
        self._login(self.staff_user, "staff")
        page = self.client.get(reverse("portal_staff_page", kwargs={"page": "attendance"}))
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, "Attendance")
        self.assertContains(page, "How to take attendance")
        self.assertContains(page, "Jordan Jacobs")
        self.assertNotContains(page, "Nia Lee")
        self.assertNotContains(page, "Review attendance")
        self.assertContains(page, reverse("portal_staff_page", kwargs={"page": "attendance"}))

        today = timezone.localdate()
        response = self.client.post(
            reverse("portal_staff_attendance_checkin"),
            {"child_id": str(self.jordan.pk), "date": today.isoformat()},
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("portal_staff_page", kwargs={"page": "attendance"}), response["Location"])
        record = AttendanceRecord.objects.get(child=self.jordan, date=today)
        self.assertEqual(record.status, AttendanceRecord.STATUS_PRESENT)
