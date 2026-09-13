from datetime import date, time

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from portal.member_sets import weekday_dates_for_repeat
from portal.models import (
    PortalCalendarActivity,
    PortalCalendarActivityMember,
    PortalChild,
    PortalFamily,
    PortalMemberGroup,
    PortalMemberGroupMember,
    PortalStaffAccount,
    PortalUnit,
)
from portal.staff_auth import PORTAL_AUTH_SESSION_KEY


@override_settings(PORTAL_PREVIEW_MODE=False)
class ActivityCalendarAndGroupsTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.school_18 = PortalUnit.objects.create(slug="school-18", name="School 18", is_active=True)
        self.school_26 = PortalUnit.objects.create(slug="school-26", name="School 26", is_active=True)
        self.family_18 = PortalFamily.objects.create(unit=self.school_18, slug="rivera", name="Rivera")
        self.family_26 = PortalFamily.objects.create(unit=self.school_26, slug="chen", name="Chen")
        self.ada = PortalChild.objects.create(
            family=self.family_18, name="Ada Rivera", unit=self.school_18, is_active=True, grade="3"
        )
        self.ben = PortalChild.objects.create(
            family=self.family_18, name="Ben Rivera", unit=self.school_18, is_active=True, grade="4"
        )
        self.cara = PortalChild.objects.create(
            family=self.family_26, name="Cara Chen", unit=self.school_26, is_active=True, grade="2"
        )
        self.admin = User.objects.create_user(username="staff:yeaadmin", password="AdminPass123")
        PortalStaffAccount.objects.create(
            user=self.admin,
            unit=self.school_18,
            display_name="Portal Admin",
            role="Portal admin",
            all_units_access=True,
            is_active=True,
        )
        self.staff = User.objects.create_user(username="staff:unit18", password="StaffPass123")
        PortalStaffAccount.objects.create(
            user=self.staff,
            unit=self.school_18,
            display_name="School 18 Staff",
            role="Unit director",
            all_units_access=False,
            is_active=True,
        )
        self.staff_26 = User.objects.create_user(username="staff:unit26", password="StaffPass123")
        PortalStaffAccount.objects.create(
            user=self.staff_26,
            unit=self.school_26,
            display_name="School 26 Staff",
            role="Unit director",
            all_units_access=False,
            is_active=True,
        )

    def _login(self, user, area, unit_slug="school-18"):
        self.client.force_login(user)
        session = self.client.session
        session[PORTAL_AUTH_SESSION_KEY] = area
        if area == "staff":
            session["staff_unit_slug"] = unit_slug
        session.save()

    def test_weekday_helper_builds_a_school_week(self):
        days = weekday_dates_for_repeat(date(2026, 9, 16), "week")
        self.assertEqual(days[0], date(2026, 9, 14))
        self.assertEqual(days[-1], date(2026, 9, 18))
        self.assertEqual(len(days), 5)

    def test_staff_can_create_a_week_of_activities(self):
        self._login(self.staff, "staff")
        response = self.client.post(
            reverse("portal_staff_activity_calendar"),
            {
                "name": "Art",
                "date": "2026-09-16",
                "time": "15:30",
                "repeat": "week",
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        created = PortalCalendarActivity.objects.filter(name="Art", unit=self.school_18)
        self.assertEqual(created.count(), 5)
        self.assertEqual(
            set(created.values_list("activity_date", flat=True)),
            {date(2026, 9, 14), date(2026, 9, 15), date(2026, 9, 16), date(2026, 9, 17), date(2026, 9, 18)},
        )
        self.assertEqual(created.values("series_id").distinct().count(), 1)
        self.assertContains(response, "Art")
        self.assertContains(response, "How to use the activity calendar")

    def test_staff_can_add_a_member_to_an_activity(self):
        self._login(self.staff, "staff")
        activity = PortalCalendarActivity.objects.create(
            name="Gym",
            activity_date=date(2026, 9, 14),
            start_time=time(15, 0),
            unit=self.school_18,
            created_by=self.staff,
        )
        page = self.client.get(reverse("portal_staff_activity_detail", kwargs={"activity_id": activity.pk}))
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, "Ada Rivera")
        self.assertContains(page, "Kids to add")
        self.assertContains(page, "In this activity")
        added = self.client.post(
            reverse("portal_staff_activity_detail", kwargs={"activity_id": activity.pk}),
            {"action": "add", "child_id": str(self.ada.pk)},
            follow=True,
        )
        self.assertEqual(added.status_code, 200)
        self.assertTrue(
            PortalCalendarActivityMember.objects.filter(activity=activity, child=self.ada).exists()
        )
        self.assertContains(added, "In this activity")
        self.assertContains(added, "Ada Rivera")

    def test_staff_cannot_see_other_unit_kids_or_activities(self):
        self._login(self.staff, "staff")
        other_activity = PortalCalendarActivity.objects.create(
            name="Other unit gym",
            activity_date=date(2026, 9, 14),
            start_time=time(15, 0),
            unit=self.school_26,
            created_by=self.staff_26,
        )
        calendar = self.client.get(
            reverse("portal_staff_activity_calendar"),
            {"month": "2026-09"},
        )
        self.assertEqual(calendar.status_code, 200)
        self.assertNotContains(calendar, "Other unit gym")
        self.assertNotContains(calendar, "Cara Chen")
        hidden = self.client.get(
            reverse("portal_staff_activity_detail", kwargs={"activity_id": other_activity.pk})
        )
        self.assertRedirects(hidden, reverse("portal_staff_activity_calendar"))
        own = PortalCalendarActivity.objects.create(
            name="Our gym",
            activity_date=date(2026, 9, 14),
            start_time=time(16, 0),
            unit=self.school_18,
            created_by=self.staff,
        )
        detail = self.client.get(reverse("portal_staff_activity_detail", kwargs={"activity_id": own.pk}))
        self.assertEqual(detail.status_code, 200)
        self.assertContains(detail, "Ada Rivera")
        self.assertNotContains(detail, "Cara Chen")
        sneak = self.client.post(
            reverse("portal_staff_activity_detail", kwargs={"activity_id": own.pk}),
            {"action": "add", "child_id": str(self.cara.pk)},
        )
        self.assertEqual(sneak.status_code, 302)
        self.assertFalse(
            PortalCalendarActivityMember.objects.filter(activity=own, child=self.cara).exists()
        )

    def test_group_print_pages_load(self):
        self._login(self.staff, "staff")
        group = PortalMemberGroup.objects.create(name="Bus run", unit=self.school_18, created_by=self.staff)
        PortalMemberGroupMember.objects.create(group=group, child=self.ada, added_by=self.staff)
        for kind, title in (
            ("attendance", "Attendance sheet"),
            ("members", "Member list"),
            ("contacts", "Contact list"),
            ("emergency", "Emergency contacts"),
        ):
            page = self.client.get(
                reverse("portal_staff_group_print", kwargs={"group_id": group.pk, "kind": kind})
            )
            self.assertEqual(page.status_code, 200, kind)
            self.assertContains(page, title)
            self.assertContains(page, "Ada Rivera")
            self.assertContains(page, "Youth Education Academy")
            self.assertContains(page, "yea-logo")

    def test_group_is_used_as_activity_filter(self):
        self._login(self.staff, "staff")
        group = PortalMemberGroup.objects.create(name="Bus run", unit=self.school_18, created_by=self.staff)
        PortalMemberGroupMember.objects.create(group=group, child=self.ada, added_by=self.staff)
        activity = PortalCalendarActivity.objects.create(
            name="Homework",
            activity_date=date(2026, 9, 15),
            start_time=time(16, 0),
            unit=self.school_18,
            created_by=self.staff,
        )
        page = self.client.get(
            reverse("portal_staff_activity_detail", kwargs={"activity_id": activity.pk}),
            {"group": str(group.pk)},
        )
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, "Ada Rivera")
        self.assertNotContains(page, "Ben Rivera")
        self.assertContains(page, "Bus run")

    def test_admin_sees_all_units_and_can_filter(self):
        self._login(self.admin, "admin")
        PortalCalendarActivity.objects.create(
            name="School 18 art",
            activity_date=date(2026, 9, 14),
            start_time=time(15, 0),
            unit=self.school_18,
        )
        PortalCalendarActivity.objects.create(
            name="School 26 art",
            activity_date=date(2026, 9, 14),
            start_time=time(15, 0),
            unit=self.school_26,
        )
        all_units = self.client.get(
            reverse("portal_admin_activity_calendar"),
            {"month": "2026-09"},
        )
        self.assertEqual(all_units.status_code, 200)
        self.assertContains(all_units, "School 18 art")
        self.assertContains(all_units, "School 26 art")
        filtered = self.client.get(
            reverse("portal_admin_activity_calendar"),
            {"month": "2026-09", "unit": "school-26"},
        )
        self.assertContains(filtered, "School 26 art")
        self.assertNotContains(filtered, "School 18 art")

    def test_staff_and_admin_group_pages_and_how_tos(self):
        self._login(self.staff, "staff")
        created = self.client.post(
            reverse("portal_staff_groups"),
            {"name": "Homework club"},
            follow=True,
        )
        self.assertEqual(created.status_code, 200)
        group = PortalMemberGroup.objects.get(name="Homework club", unit=self.school_18)
        self.assertContains(created, "Kids to add")
        self.assertContains(created, "How to add kids to a group")
        self.client.post(
            reverse("portal_staff_group_detail", kwargs={"group_id": group.pk}),
            {"action": "add", "child_id": str(self.ben.pk)},
        )
        self.assertTrue(PortalMemberGroupMember.objects.filter(group=group, child=self.ben).exists())
        listing = self.client.get(reverse("portal_staff_groups"))
        self.assertContains(listing, "How to use groups")
        self.assertContains(listing, "Homework club")

        self._login(self.admin, "admin")
        admin_list = self.client.get(reverse("portal_admin_groups"))
        self.assertContains(admin_list, "Homework club")
        other = self.client.post(
            reverse("portal_admin_groups"),
            {"name": "School 26 bus", "unit": "school-26"},
            follow=True,
        )
        self.assertEqual(other.status_code, 200)
        self.assertTrue(PortalMemberGroup.objects.filter(name="School 26 bus", unit=self.school_26).exists())

    def test_single_day_lesson_plan_upload(self):
        self._login(self.staff, "staff")
        pdf = SimpleUploadedFile("plan.pdf", b"%PDF-1.4 lesson", content_type="application/pdf")
        response = self.client.post(
            reverse("portal_staff_activity_calendar"),
            {
                "name": "Science",
                "date": "2026-09-18",
                "time": "15:00",
                "repeat": "once",
                "lesson_plan": pdf,
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        activity = PortalCalendarActivity.objects.get(name="Science", activity_date=date(2026, 9, 18))
        self.assertTrue(activity.has_lesson_plan)
        self.assertEqual(activity.lesson_plan_name, "plan.pdf")
        self.assertContains(response, "plan.pdf")
