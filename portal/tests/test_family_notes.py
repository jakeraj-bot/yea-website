from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from portal.family_notes import add_family_note
from portal.models import PortalChild, PortalFamily, PortalFamilyNote, PortalParentAccount, PortalStaffAccount, PortalUnit
from portal.staff_auth import PORTAL_AUTH_SESSION_KEY


@override_settings(PORTAL_PREVIEW_MODE=False)
class FamilyAccountNotesTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.unit = PortalUnit.objects.create(slug="school-18", name="School 18", is_active=True)
        self.other_unit = PortalUnit.objects.create(slug="school-26", name="School 26", is_active=True)
        self.family = PortalFamily.objects.create(unit=self.unit, slug="jacobs", name="Jacobs")
        self.child = PortalChild.objects.create(
            family=self.family,
            name="Jordan Jacobs",
            unit=self.unit,
            is_active=True,
        )
        self.other_family = PortalFamily.objects.create(unit=self.other_unit, slug="lee", name="Lee")
        self.other_child = PortalChild.objects.create(
            family=self.other_family,
            name="Nia Lee",
            unit=self.other_unit,
            is_active=True,
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
        self.staff = User.objects.create_user(username="staff:unitstaff", password="StaffPass123")
        PortalStaffAccount.objects.create(
            user=self.staff,
            unit=self.unit,
            display_name="Unit Staff",
            role="Unit director",
            is_active=True,
        )
        self.other_staff = User.objects.create_user(username="staff:school26", password="StaffPass123")
        PortalStaffAccount.objects.create(
            user=self.other_staff,
            unit=self.other_unit,
            display_name="School 26 Staff",
            role="Unit director",
            is_active=True,
        )
        self.pd = User.objects.create_user(username="staff:pduser", password="StaffPass123")
        PortalStaffAccount.objects.create(
            user=self.pd,
            unit=self.unit,
            display_name="Program Director",
            role="Program director",
            is_active=True,
        )
        self.desk = User.objects.create_user(username="staff:frontdesk", password="StaffPass123")
        PortalStaffAccount.objects.create(
            user=self.desk,
            unit=self.unit,
            display_name="Front Desk",
            role="Front desk staff",
            is_active=True,
        )
        parent_user = User.objects.create_user(
            username="parent:jacobs",
            password="ParentPass123",
            email="parent@example.com",
        )
        PortalParentAccount.objects.create(user=parent_user, family=self.family)
        self.parent = parent_user

    def _login(self, user, area, unit_slug=None):
        self.client.force_login(user)
        session = self.client.session
        session[PORTAL_AUTH_SESSION_KEY] = area
        if area == "staff" and unit_slug:
            session["staff_unit_slug"] = unit_slug
        session.save()

    def test_admin_can_add_two_notes_with_author_and_date(self):
        self._login(self.admin, "admin")
        first = self.client.post(
            reverse("portal_admin_family_note_add", kwargs={"family_slug": "jacobs"}),
            {"body": "Called mom about late pickup.", "family_id": self.family.pk},
        )
        self.assertEqual(first.status_code, 302)
        second = self.client.post(
            reverse("portal_admin_family_note_add", kwargs={"family_slug": "jacobs"}),
            {"body": "Left a reminder about the field trip form.", "family_id": self.family.pk},
        )
        self.assertEqual(second.status_code, 302)
        page = self.client.get(reverse("portal_admin_family_notes", kwargs={"family_slug": "jacobs"}))
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, "Called mom about late pickup.")
        self.assertContains(page, "Left a reminder about the field trip form.")
        self.assertContains(page, "Portal Admin")
        today = timezone.localtime().strftime("%b")
        self.assertContains(page, today)
        self.assertContains(page, "How to use this page")
        self.assertContains(page, "portal-family-tab--notes")
        bodies = list(page.context["family_notes"])
        self.assertEqual(bodies[0].body, "Left a reminder about the field trip form.")
        self.assertEqual(bodies[1].body, "Called mom about late pickup.")
        self.assertTrue(bodies[0].created_at)
        self.assertTrue(bodies[0].author_name)

    def test_staff_cannot_open_other_unit_notes(self):
        add_family_note(
            self.other_family,
            body="School 26 only.",
            user=self.other_staff,
            child=self.other_child,
            unit=self.other_unit,
        )
        self._login(self.staff, "staff", unit_slug="school-18")
        page = self.client.get(reverse("portal_staff_family_notes", kwargs={"family_slug": "lee"}))
        self.assertEqual(page.status_code, 404)
        post = self.client.post(
            reverse("portal_staff_family_note_add", kwargs={"family_slug": "lee"}),
            {"body": "Should not save."},
        )
        self.assertEqual(post.status_code, 302)
        self.assertIn("/portal/staff/families/", post.url)
        self.assertFalse(PortalFamilyNote.objects.filter(family=self.other_family, body="Should not save.").exists())

    def test_parent_preview_has_no_notes_tab(self):
        self._login(self.admin, "admin")
        preview = self.client.get(reverse("portal_admin_parent_preview", kwargs={"family_slug": "jacobs"}))
        self.assertEqual(preview.status_code, 200)
        self.assertNotContains(preview, "portal-family-tab--notes")
        self.assertNotContains(
            preview,
            reverse("portal_admin_family_notes", kwargs={"family_slug": "jacobs"}),
        )
        self.assertNotContains(preview, "Notes already written")

    def test_parent_cannot_open_notes(self):
        self.client.force_login(self.parent)
        session = self.client.session
        session[PORTAL_AUTH_SESSION_KEY] = "parent"
        session.save()
        page = self.client.get(reverse("portal_staff_family_notes", kwargs={"family_slug": "jacobs"}))
        self.assertEqual(page.status_code, 302)
        self.assertIn("/portal/staff/login/", page.url)

    def test_program_director_and_front_desk_can_add_notes(self):
        self._login(self.pd, "staff", unit_slug="school-18")
        pd_post = self.client.post(
            reverse("portal_staff_family_note_add", kwargs={"family_slug": "jacobs"}),
            {"body": "PD noted the schedule change.", "child_id": self.child.pk},
        )
        self.assertEqual(pd_post.status_code, 302)
        self._login(self.desk, "staff", unit_slug="school-18")
        desk_post = self.client.post(
            reverse("portal_staff_family_note_add", kwargs={"family_slug": "jacobs"}),
            {"body": "Front desk called the parent."},
        )
        self.assertEqual(desk_post.status_code, 302)
        page = self.client.get(reverse("portal_staff_family_notes", kwargs={"family_slug": "jacobs"}))
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, "PD noted the schedule change.")
        self.assertContains(page, "Front desk called the parent.")
        self.assertContains(page, "Program Director")
        self.assertContains(page, "Front Desk")
        self.assertContains(page, "Jordan Jacobs")

    def test_delete_requires_a_reason(self):
        self._login(self.admin, "admin")
        self.client.post(
            reverse("portal_admin_family_note_add", kwargs={"family_slug": "jacobs"}),
            {"body": "Typed in the wrong account.", "family_id": self.family.pk},
        )
        note = PortalFamilyNote.objects.get(family=self.family)
        missing = self.client.post(
            reverse(
                "portal_admin_family_note_delete",
                kwargs={"family_slug": "jacobs", "note_id": note.pk},
            ),
            {"family_id": self.family.pk},
        )
        self.assertEqual(missing.status_code, 302)
        self.assertTrue(PortalFamilyNote.objects.filter(pk=note.pk).exists())
        deleted = self.client.post(
            reverse(
                "portal_admin_family_note_delete",
                kwargs={"family_slug": "jacobs", "note_id": note.pk},
            ),
            {"family_id": self.family.pk, "delete_reason": "Wrong child"},
        )
        self.assertEqual(deleted.status_code, 302)
        self.assertFalse(PortalFamilyNote.objects.filter(pk=note.pk).exists())
