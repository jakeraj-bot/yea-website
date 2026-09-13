from datetime import date
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse

from enrollment.models import EmergencyContact, EnrollmentApplication
from portal.models import PortalChild, PortalFamily, PortalFamilyNote, PortalParentAccount, PortalUnit
from portal.staff_auth import PORTAL_AUTH_SESSION_KEY
from portal.views import PARENT_CONTACT_EMAIL


def _enrollment_application(family, *, first, last, location="school_18"):
    return EnrollmentApplication.objects.create(
        program="after_school",
        program_location=location,
        family_name=family.name,
        primary_email="parent@example.com",
        home_address="1 Main St",
        primary_first_name="Ada",
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
        student_first_name=first,
        student_last_name=last,
        student_gender="female",
        student_dob=date(2016, 1, 1),
        student_language="english",
        student_ethnicity="unknown",
        student_race="unknown",
        student_grade="4",
        student_school="Lincoln Elementary",
        health_statement="good_health",
        membership_fee_agreed="no",
        payment_method="private_pay",
        payment_plan="weekly",
        payment_plan_signature="Ada",
        payment_plan_signed_date=date(2026, 8, 1),
        status="enrolled",
        portal_family=family,
    )


class ParentEmergencyContactTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.unit = PortalUnit.objects.create(slug="school-18", name="School 18", is_active=True)
        self.family = PortalFamily.objects.create(
            unit=self.unit,
            slug="rivera",
            name="Rivera",
            primary_contact="Ada Rivera",
            status="Active",
        )
        self.child = PortalChild.objects.create(
            family=self.family,
            name="Jordan Rivera",
            grade="4th",
            is_active=True,
            unit=self.unit,
            note="Staff only: pickup code 4411",
        )
        self.app = _enrollment_application(self.family, first="Jordan", last="Rivera")
        self.existing = EmergencyContact.objects.create(
            application=self.app,
            order=1,
            first_name="Rosa",
            last_name="Rivera",
            phone="555-0199",
            relationship="Grandmother",
            authorized_pickup=True,
        )
        PortalFamilyNote.objects.create(
            family=self.family,
            body="Do not show this staff note to parents.",
            author_name="Director",
        )
        self.parent_user = User.objects.create_user(
            username="parent:rivera",
            password="ParentPass123",
            email="ada.rivera@example.com",
            first_name="Ada",
            last_name="Rivera",
        )
        PortalParentAccount.objects.create(user=self.parent_user, family=self.family)

        self.other_family = PortalFamily.objects.create(
            unit=self.unit,
            slug="lee",
            name="Lee",
            primary_contact="Sam Lee",
            status="Active",
        )
        self.other_child = PortalChild.objects.create(
            family=self.other_family,
            name="Maya Lee",
            grade="2nd",
            is_active=True,
            unit=self.unit,
        )
        other_app = _enrollment_application(self.other_family, first="Maya", last="Lee")
        self.other_contact = EmergencyContact.objects.create(
            application=other_app,
            order=1,
            first_name="Tom",
            last_name="Lee",
            phone="555-0178",
            relationship="Uncle",
            authorized_pickup=False,
        )
        other_parent = User.objects.create_user(
            username="parent:lee",
            password="ParentPass123",
            email="sam.lee@example.com",
        )
        PortalParentAccount.objects.create(user=other_parent, family=self.other_family)

    def _login_parent(self):
        self.client.force_login(self.parent_user)
        session = self.client.session
        session[PORTAL_AUTH_SESSION_KEY] = "parent"
        session.save()

    def _page_url(self):
        return reverse("portal_parent_page", kwargs={"page": "emergency-contacts"})

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_parent_page_lists_contacts_and_howto_hides_staff_notes(self):
        self._login_parent()
        page = self.client.get(self._page_url())
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, "Emergency contacts")
        self.assertContains(page, "How to use this page")
        self.assertContains(page, "Add a contact for Jordan Rivera")
        self.assertContains(page, "Rosa Rivera")
        self.assertContains(page, "555-0199")
        self.assertContains(page, reverse("portal_parent_emergency_contact_add"))
        self.assertContains(page, reverse("portal_parent_emergency_contact_delete"))
        self.assertContains(page, 'name="confirm_delete"')
        self.assertNotContains(page, "Do not show this staff note to parents.")
        self.assertNotContains(page, "Staff only: pickup code 4411")
        self.assertNotContains(page, "Tom Lee")
        dashboard = self.client.get(reverse("portal_parent_page", kwargs={"page": "dashboard"}))
        self.assertContains(dashboard, self._page_url())

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_parent_adds_contact_and_staff_family_view_matches(self):
        self._login_parent()
        response = self.client.post(
            reverse("portal_parent_emergency_contact_add"),
            {
                "child_id": str(self.child.pk),
                "first_name": "Luis",
                "last_name": "Rivera",
                "phone": "555-0144",
                "relationship": "Father",
                "authorized_pickup": "on",
            },
        )
        self.assertEqual(response.status_code, 302)
        created = EmergencyContact.objects.get(application=self.app, first_name="Luis", last_name="Rivera")
        self.assertEqual(created.phone, "555-0144")
        self.assertTrue(created.authorized_pickup)
        page = self.client.get(self._page_url())
        self.assertContains(page, "Luis Rivera")
        self.assertContains(page, "555-0144")

        from portal.live_services import family_profile_live

        profile = family_profile_live(self.family.slug, unit=self.unit, family_id=self.family.pk)
        child_row = next(row for row in profile["children"] if row["name"] == "Jordan Rivera")
        names = {contact["name"] for contact in child_row["emergency_contacts"]}
        self.assertIn("Luis Rivera", names)
        self.assertIn("Rosa Rivera", names)

    @override_settings(
        PORTAL_PREVIEW_MODE=False,
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    )
    @patch("core.email_service.email_is_configured", return_value=True)
    def test_add_sends_staff_alert_email(self, _configured):
        self._login_parent()
        self.client.post(
            reverse("portal_parent_emergency_contact_add"),
            {
                "child_id": str(self.child.pk),
                "first_name": "Nina",
                "last_name": "Cruz",
                "phone": "555-0110",
                "relationship": "Aunt",
            },
        )
        self.assertEqual(len(mail.outbox), 1)
        sent = mail.outbox[0]
        recipients = {email.lower() for email in sent.to}
        self.assertIn(PARENT_CONTACT_EMAIL.lower(), recipients)
        self.assertIn("added", sent.subject.lower())
        self.assertIn("Jordan Rivera", sent.body)
        self.assertIn("Rivera", sent.body)
        self.assertIn("Ada Rivera", sent.body)
        self.assertIn("Nina Cruz", sent.body)
        self.assertIn("555-0110", sent.body)
        self.assertIn("Aunt", sent.body)

    @override_settings(
        PORTAL_PREVIEW_MODE=False,
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    )
    @patch("core.email_service.email_is_configured", return_value=True)
    def test_parent_deletes_contact_and_email_names_who_was_removed(self, _configured):
        self._login_parent()
        response = self.client.post(
            reverse("portal_parent_emergency_contact_delete"),
            {
                "child_id": str(self.child.pk),
                "contact_id": str(self.existing.pk),
                "confirm_delete": "1",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(EmergencyContact.objects.filter(pk=self.existing.pk).exists())
        page = self.client.get(self._page_url())
        self.assertContains(page, "No emergency contacts on file for Jordan Rivera.")
        self.assertNotContains(page, "555-0199")
        self.assertEqual(len(mail.outbox), 1)
        sent = mail.outbox[0]
        recipients = {email.lower() for email in sent.to}
        self.assertIn(PARENT_CONTACT_EMAIL.lower(), recipients)
        self.assertIn("deleted", sent.subject.lower())
        self.assertIn("Jordan Rivera", sent.body)
        self.assertIn("Rosa Rivera", sent.body)
        self.assertIn("555-0199", sent.body)
        self.assertIn("removed", sent.body.lower())

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_delete_without_confirm_does_not_wipe(self):
        self._login_parent()
        response = self.client.post(
            reverse("portal_parent_emergency_contact_delete"),
            {
                "child_id": str(self.child.pk),
                "contact_id": str(self.existing.pk),
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(EmergencyContact.objects.filter(pk=self.existing.pk).exists())

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_name_and_phone_are_required(self):
        self._login_parent()
        self.client.post(
            reverse("portal_parent_emergency_contact_add"),
            {
                "child_id": str(self.child.pk),
                "first_name": "",
                "last_name": "Rivera",
                "phone": "",
            },
        )
        self.assertFalse(EmergencyContact.objects.filter(application=self.app, last_name="Rivera", first_name="").exists())
        self.assertEqual(EmergencyContact.objects.filter(application=self.app).count(), 1)

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_parent_cannot_edit_another_family_contacts(self):
        self._login_parent()
        add = self.client.post(
            reverse("portal_parent_emergency_contact_add"),
            {
                "child_id": str(self.other_child.pk),
                "first_name": "Intruder",
                "last_name": "Person",
                "phone": "555-0000",
                "relationship": "Neighbor",
            },
        )
        self.assertEqual(add.status_code, 302)
        self.assertFalse(
            EmergencyContact.objects.filter(first_name="Intruder", last_name="Person").exists()
        )
        delete = self.client.post(
            reverse("portal_parent_emergency_contact_delete"),
            {
                "child_id": str(self.other_child.pk),
                "contact_id": str(self.other_contact.pk),
                "confirm_delete": "1",
            },
        )
        self.assertEqual(delete.status_code, 302)
        self.assertTrue(EmergencyContact.objects.filter(pk=self.other_contact.pk).exists())
        swap = self.client.post(
            reverse("portal_parent_emergency_contact_delete"),
            {
                "child_id": str(self.child.pk),
                "contact_id": str(self.other_contact.pk),
                "confirm_delete": "1",
            },
        )
        self.assertEqual(swap.status_code, 302)
        self.assertTrue(EmergencyContact.objects.filter(pk=self.other_contact.pk).exists())
