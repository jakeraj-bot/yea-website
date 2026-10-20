from datetime import date, time

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from enrollment.models import EnrollmentApplication
from portal.attendance_calendar import child_attendance_month
from portal.models import (
    AttendanceRecord,
    PortalActivityEvent,
    PortalChild,
    PortalFamily,
    PortalParentAccount,
    PortalProgram,
    PortalStaffAccount,
    PortalUnit,
)
from portal.staff_auth import PORTAL_AUTH_SESSION_KEY, can_delete_attendance
from portal.staff_services import weekly_attendance_report_data


def _make_app(family, child, *, program="after_school"):
    first, _, last = child.name.partition(" ")
    return EnrollmentApplication.objects.create(
        program=program,
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
        student_last_name=last or family.name,
        student_gender="female",
        student_dob=date(2016, 1, 1),
        student_language="english",
        student_ethnicity="unknown",
        student_race="unknown",
        student_grade="3",
        student_school=child.school or "Lincoln Elementary",
        health_statement="good_health",
        membership_fee_agreed="no",
        payment_method="private_pay",
        payment_plan="weekly",
        payment_plan_signature="Pat",
        payment_plan_signed_date=date(2026, 8, 1),
        status="approved",
        is_active=True,
        portal_family=family,
    )


@override_settings(PORTAL_PREVIEW_MODE=False)
class DeleteAttendancePermissionTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.unit = PortalUnit.objects.create(slug="school-18", name="School 18", is_active=True)
        self.other_unit = PortalUnit.objects.create(slug="school-26", name="School 26", is_active=True)
        self.program = PortalProgram.objects.create(
            unit=self.unit,
            name="After-School 2026–27",
            start_time=time(15, 0),
            end_time=time(18, 0),
            is_active=True,
        )
        self.other_program = PortalProgram.objects.create(
            unit=self.other_unit,
            name="After-School 26",
            start_time=time(15, 0),
            end_time=time(18, 0),
            is_active=True,
        )
        self.family = PortalFamily.objects.create(unit=self.unit, slug="jacobs", name="Jacobs")
        self.child = PortalChild.objects.create(
            family=self.family,
            name="Sam Jacobs",
            grade="3rd",
            school="Lincoln Elementary",
            unit=self.unit,
            is_active=True,
        )
        _make_app(self.family, self.child, program="after_school")
        _make_app(self.family, self.child, program="before_care")
        self.today = timezone.localdate()

        self.admin = User.objects.create_user(
            username="staff:yeaadmin", password="AdminPass123", is_staff=True, is_superuser=True
        )
        PortalStaffAccount.objects.create(
            user=self.admin,
            unit=self.unit,
            display_name="Jakera",
            role="Portal admin",
            all_units_access=True,
            is_active=True,
        )
        self.staff = User.objects.create_user(username="staff:unitone", password="StaffPass123")
        self.staff_account = PortalStaffAccount.objects.create(
            user=self.staff,
            unit=self.unit,
            display_name="Unit Staff",
            role="Unit staff",
            is_active=True,
            can_delete_attendance=False,
        )
        self.front_desk = User.objects.create_user(username="staff:frontdesk", password="StaffPass123")
        PortalStaffAccount.objects.create(
            user=self.front_desk,
            unit=self.unit,
            display_name="Front Desk",
            role="Front desk staff",
            is_active=True,
            can_delete_attendance=False,
        )
        self.parent_user = User.objects.create_user(username="parent:jacobs", password="ParentPass123")
        PortalParentAccount.objects.create(user=self.parent_user, family=self.family)

    def _login(self, user, area):
        self.client.force_login(user)
        session = self.client.session
        session[PORTAL_AUTH_SESSION_KEY] = area
        if area == "staff":
            session["staff_unit_slug"] = self.unit.slug
        session.save()

    def _add_sessions(self, child=None, day=None):
        child = child or self.child
        day = day or self.today
        before = AttendanceRecord.objects.create(
            child=child,
            program=self.program,
            date=day,
            status=AttendanceRecord.STATUS_PRESENT,
            care=AttendanceRecord.CARE_BEFORE,
            method="Staff",
        )
        after = AttendanceRecord.objects.create(
            child=child,
            program=self.program,
            date=day,
            status=AttendanceRecord.STATUS_PRESENT,
            care=AttendanceRecord.CARE_AFTER,
            method="Staff",
        )
        return before, after

    def _delete(self, *, child=None, day=None, care="after", reason="Wrong child marked"):
        child = child or self.child
        day = day or self.today
        return self.client.post(
            reverse("portal_staff_attendance_delete"),
            {
                "child_id": str(child.pk),
                "date": day.isoformat(),
                "care": care,
                "delete_reason": reason,
                "next": reverse("portal_staff_family_attendance", kwargs={"family_slug": child.family.slug}),
            },
        )

    def test_org_admin_always_has_permission(self):
        account = self.admin.portal_staff_account
        self.assertTrue(can_delete_attendance(account, portal_area="admin", user=self.admin))
        self.assertTrue(can_delete_attendance(account, portal_area="staff", user=self.admin))

    def test_staff_without_flag_does_not_have_permission(self):
        self.assertFalse(can_delete_attendance(self.staff_account, portal_area="staff", user=self.staff))
        desk = self.front_desk.portal_staff_account
        self.assertFalse(can_delete_attendance(desk, portal_area="staff", user=self.front_desk))

    def test_staff_with_flag_has_permission(self):
        self.staff_account.can_delete_attendance = True
        self.staff_account.save(update_fields=["can_delete_attendance"])
        self.assertTrue(can_delete_attendance(self.staff_account, portal_area="staff", user=self.staff))

    def test_super_admin_can_delete_and_activity_log_is_written(self):
        before, after = self._add_sessions()
        self._login(self.admin, "admin")
        response = self._delete(care="after", reason="Checked the wrong afternoon")
        self.assertEqual(response.status_code, 302)
        self.assertFalse(AttendanceRecord.objects.filter(pk=after.pk).exists())
        self.assertTrue(AttendanceRecord.objects.filter(pk=before.pk).exists())
        event = PortalActivityEvent.objects.get(action=PortalActivityEvent.ACTION_DELETE, actor=self.admin)
        self.assertEqual(event.object_label, "Sam Jacobs")
        self.assertIn(self.today.isoformat(), event.details)
        self.assertIn("After-care", event.details)
        self.assertEqual(event.delete_reason, "Checked the wrong afternoon")
        self.assertEqual(event.actor_name, "Jakera")

    def test_staff_without_permission_gets_403_and_record_remains(self):
        before, after = self._add_sessions()
        self._login(self.staff, "staff")
        response = self._delete(care="after")
        self.assertEqual(response.status_code, 403)
        self.assertTrue(AttendanceRecord.objects.filter(pk=after.pk).exists())
        self.assertTrue(AttendanceRecord.objects.filter(pk=before.pk).exists())
        self.assertFalse(
            PortalActivityEvent.objects.filter(action=PortalActivityEvent.ACTION_DELETE, actor=self.staff).exists()
        )

    def test_staff_with_permission_can_delete(self):
        _before, after = self._add_sessions()
        self.staff_account.can_delete_attendance = True
        self.staff_account.save(update_fields=["can_delete_attendance"])
        self._login(self.staff, "staff")
        response = self._delete(care="after", reason="Afternoon was a mistake")
        self.assertEqual(response.status_code, 302)
        self.assertFalse(AttendanceRecord.objects.filter(pk=after.pk).exists())
        event = PortalActivityEvent.objects.get(action=PortalActivityEvent.ACTION_DELETE, actor=self.staff)
        self.assertEqual(event.delete_reason, "Afternoon was a mistake")
        self.assertEqual(event.object_label, "Sam Jacobs")

    def test_parent_cannot_delete(self):
        before, after = self._add_sessions()
        self._login(self.parent_user, "parent")
        response = self._delete(care="after")
        self.assertIn(response.status_code, {302, 403})
        self.assertTrue(AttendanceRecord.objects.filter(pk=after.pk).exists())
        self.assertTrue(AttendanceRecord.objects.filter(pk=before.pk).exists())
        self.assertFalse(
            PortalActivityEvent.objects.filter(
                action=PortalActivityEvent.ACTION_DELETE, actor=self.parent_user
            ).exists()
        )

    def test_before_delete_does_not_wipe_after(self):
        before, after = self._add_sessions()
        self._login(self.admin, "admin")
        response = self._delete(care="before", reason="Morning was wrong")
        self.assertEqual(response.status_code, 302)
        self.assertFalse(AttendanceRecord.objects.filter(pk=before.pk).exists())
        self.assertTrue(AttendanceRecord.objects.filter(pk=after.pk).exists())
        self.assertEqual(AttendanceRecord.objects.get(pk=after.pk).care, AttendanceRecord.CARE_AFTER)

    def test_delete_both_sessions(self):
        before, after = self._add_sessions()
        self._login(self.admin, "admin")
        response = self._delete(care="both", reason="Whole day was a duplicate")
        self.assertEqual(response.status_code, 302)
        self.assertFalse(AttendanceRecord.objects.filter(pk=before.pk).exists())
        self.assertFalse(AttendanceRecord.objects.filter(pk=after.pk).exists())

    def test_missing_reason_does_not_delete(self):
        _before, after = self._add_sessions()
        self._login(self.admin, "admin")
        response = self.client.post(
            reverse("portal_staff_attendance_delete"),
            {
                "child_id": str(self.child.pk),
                "date": self.today.isoformat(),
                "care": "after",
                "delete_reason": "   ",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(AttendanceRecord.objects.filter(pk=after.pk).exists())
        self.assertFalse(
            PortalActivityEvent.objects.filter(action=PortalActivityEvent.ACTION_DELETE, actor=self.admin).exists()
        )

    def test_calendar_and_weekly_no_longer_list_deleted_mark(self):
        self._add_sessions()
        self._login(self.admin, "admin")
        self._delete(care="before", reason="Morning correction")
        month_start = date(self.today.year, self.today.month, 1)
        calendar = child_attendance_month(self.child, month_start, selected_day=self.today)
        selected = calendar["selected"]
        self.assertTrue(selected["has_record"])
        cares = {record["care"] for record in selected["records"]}
        self.assertNotIn("before", cares)
        self.assertIn("after", cares)
        self.assertTrue(selected["sessions"]["after"]["present"])
        self.assertFalse(selected["sessions"]["before"]["present"])

        after_sheet = weekly_attendance_report_data(
            self.unit, self.program, self.today, filters={"care": "after"}
        )
        before_sheet = weekly_attendance_report_data(
            self.unit, self.program, self.today, filters={"care": "before"}
        )
        after_row = next(row for row in after_sheet["weekly_rows"] if row["child"] == "Sam Jacobs")
        before_row = next(row for row in before_sheet["weekly_rows"] if row["child"] == "Sam Jacobs")
        idx = min(self.today.weekday(), 4)
        self.assertTrue(after_row["days"][idx])
        self.assertFalse(before_row["days"][idx])

    def test_calendar_hides_delete_without_permission_and_shows_it_for_admin(self):
        self._add_sessions()
        url = reverse("portal_staff_family_attendance", kwargs={"family_slug": "jacobs"})
        params = {
            "id": self.family.pk,
            "child_id": self.child.pk,
            "child": "Sam Jacobs",
            "month": self.today.strftime("%Y-%m"),
            "day": self.today.isoformat(),
        }
        self._login(self.staff, "staff")
        denied = self.client.get(url, params)
        self.assertEqual(denied.status_code, 200)
        self.assertNotContains(denied, "Delete this mark")
        self.assertNotContains(denied, "/portal/staff/attendance/delete/")

        self._login(self.admin, "admin")
        allowed = self.client.get(
            reverse("portal_admin_family_attendance", kwargs={"family_slug": "jacobs"}),
            params,
        )
        self.assertEqual(allowed.status_code, 200)
        self.assertContains(allowed, "Delete this mark")
        self.assertContains(allowed, "/portal/staff/attendance/delete/")
        self.assertContains(allowed, "Delete both sessions")

        self.staff_account.can_delete_attendance = True
        self.staff_account.save(update_fields=["can_delete_attendance"])
        self._login(self.staff, "staff")
        granted = self.client.get(url, params)
        self.assertEqual(granted.status_code, 200)
        self.assertContains(granted, "Delete this mark")

    def test_weekly_mark_still_works_without_delete_permission(self):
        self._login(self.staff, "staff")
        response = self.client.post(
            reverse("portal_staff_attendance_mark"),
            {
                "child_id": str(self.child.pk),
                "date": self.today.isoformat(),
                "care": "after",
                "present": "1",
                "next": reverse("portal_staff_weekly_attendance_report"),
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            AttendanceRecord.objects.filter(
                child=self.child, date=self.today, care=AttendanceRecord.CARE_AFTER
            ).exists()
        )

    def test_staff_cannot_delete_child_at_another_unit(self):
        other_family = PortalFamily.objects.create(unit=self.other_unit, slug="rivera", name="Rivera")
        other_child = PortalChild.objects.create(
            family=other_family,
            name="Ada Rivera",
            unit=self.other_unit,
            is_active=True,
        )
        record = AttendanceRecord.objects.create(
            child=other_child,
            program=self.other_program,
            date=self.today,
            status=AttendanceRecord.STATUS_PRESENT,
            care=AttendanceRecord.CARE_AFTER,
        )
        self.staff_account.can_delete_attendance = True
        self.staff_account.save(update_fields=["can_delete_attendance"])
        self._login(self.staff, "staff")
        response = self._delete(child=other_child, care="after", reason="Should not work")
        self.assertEqual(response.status_code, 403)
        self.assertTrue(AttendanceRecord.objects.filter(pk=record.pk).exists())

    def test_grant_flag_on_staff_edit(self):
        self._login(self.admin, "admin")
        response = self.client.post(
            reverse("portal_admin_staff_edit"),
            {
                "staff_id": str(self.staff_account.pk),
                "name": "Unit Staff",
                "email": "unitone@example.com",
                "role": "Unit staff",
                "can_delete_attendance": "on",
                "is_active": "1",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.staff_account.refresh_from_db()
        self.assertTrue(self.staff_account.can_delete_attendance)

    def test_child_and_family_remain_after_delete(self):
        self._add_sessions()
        self._login(self.admin, "admin")
        self._delete(care="both", reason="Clear the day")
        self.assertTrue(PortalChild.objects.filter(pk=self.child.pk).exists())
        self.assertTrue(PortalFamily.objects.filter(pk=self.family.pk).exists())
        self.assertEqual(AttendanceRecord.objects.filter(child=self.child, date=self.today).count(), 0)
