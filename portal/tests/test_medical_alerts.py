from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from portal.medical import alerts_from_medical_dict, medical_from_application, medical_value_is_positive
from portal.models import PortalChild, PortalFamily, PortalUnit
from portal.staff_services import get_medical_data_for_child
from portal.tests.test_family_units import _make_application


class MedicalValueTests(SimpleTestCase):
    def test_negative_phrases_are_not_alerts(self):
        for value in (
            "",
            "—",
            "None",
            "none reported",
            "No known allergies",
            "no allergy",
            "N/A",
            "no medications",
            "no",
        ):
            with self.subTest(value=value):
                self.assertFalse(medical_value_is_positive(value))

    def test_real_conditions_are_alerts(self):
        self.assertTrue(medical_value_is_positive("Peanuts"))
        self.assertTrue(medical_value_is_positive("Albuterol inhaler"))


class ApplicationMedicalAlertTests(TestCase):
    def setUp(self):
        self.unit = PortalUnit.objects.create(slug="school-18", name="School 18", is_active=True)
        self.family = PortalFamily.objects.create(unit=self.unit, slug="rivera", name="Rivera")

    def test_no_known_allergies_does_not_show_allergy_icon(self):
        app = _make_application(self.family, status="under_review")
        app.no_known_allergies = True
        app.allergies = "none"
        app.requires_medication = "no"
        app.requires_allergy_plan = False
        app.save()
        medical = medical_from_application(app)
        alerts = alerts_from_medical_dict(medical)
        self.assertFalse(medical["has_allergies"])
        self.assertFalse(medical["has_medications"])
        self.assertEqual(alerts, [])
        badges = get_medical_data_for_child("Ada Rivera")
        self.assertEqual(badges["alerts"], [])

    def test_typed_no_allergy_does_not_show_icon(self):
        app = _make_application(self.family, status="under_review")
        app.no_known_allergies = False
        app.allergies = "No allergies"
        app.requires_medication = "no"
        app.save()
        self.assertEqual(alerts_from_medical_dict(medical_from_application(app)), [])

    def test_real_allergy_and_medication_show_icons(self):
        app = _make_application(self.family, status="under_review")
        app.no_known_allergies = False
        app.allergies = "Peanuts"
        app.requires_medication = "yes"
        app.requires_epipen_plan = True
        app.save()
        keys = {item["key"] for item in alerts_from_medical_dict(medical_from_application(app))}
        self.assertIn("allergy", keys)
        self.assertIn("medication", keys)
        self.assertIn("epipen", keys)


class FamilyScopedMedicalTests(TestCase):
    def setUp(self):
        self.unit = PortalUnit.objects.create(slug="school-18", name="School 18", is_active=True)
        self.patel = PortalFamily.objects.create(unit=self.unit, slug="patel", name="Patel")
        self.nguyen = PortalFamily.objects.create(unit=self.unit, slug="nguyen", name="Nguyen")
        PortalChild.objects.create(family=self.patel, name="Jordan Lee", grade="2")
        PortalChild.objects.create(family=self.nguyen, name="Jordan Lee", grade="2")

        allergic = _make_application(self.patel, status="under_review")
        allergic.student_first_name = "Jordan"
        allergic.student_last_name = "Lee"
        allergic.no_known_allergies = False
        allergic.allergies = "Peanuts"
        allergic.requires_medication = "no"
        allergic.save()

        clear = _make_application(self.nguyen, status="under_review")
        clear.student_first_name = "Jordan"
        clear.student_last_name = "Lee"
        clear.no_known_allergies = True
        clear.allergies = ""
        clear.requires_medication = "no"
        clear.save()

    def test_family_slug_keeps_same_child_names_separate(self):
        patel_keys = {
            item["key"] for item in get_medical_data_for_child("Jordan Lee", "patel")["alerts"]
        }
        nguyen_alerts = get_medical_data_for_child("Jordan Lee", "nguyen")["alerts"]
        self.assertIn("allergy", patel_keys)
        self.assertEqual(nguyen_alerts, [])


class FamiliesAndRosterDisplayTests(TestCase):
    @override_settings(PORTAL_PREVIEW_MODE=True)
    def test_families_page_shows_medical_column_by_default(self):
        response = self.client.get(reverse("portal_staff_page", kwargs={"page": "families"}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-col-toggle="medical" checked')
        self.assertContains(response, 'data-col="medical"')

    @override_settings(PORTAL_PREVIEW_MODE=True)
    def test_report_roster_numbers_each_child(self):
        response = self.client.get(
            reverse("portal_staff_program_roster", kwargs={"program_slug": "after-school-2026-27"})
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'class="portal-row-num"')
        self.assertContains(response, "children shown")
        self.assertContains(response, 'class="portal-row-num">1</td>')
