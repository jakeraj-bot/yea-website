from django.test import SimpleTestCase, TestCase

from portal.medical import alerts_from_medical_dict, medical_from_application, medical_value_is_positive
from portal.models import PortalFamily, PortalUnit
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
