from django.test import TestCase
from django.urls import resolve, reverse

from enrollment import views


class ApplyHelpTests(TestCase):
    def test_help_url_is_not_a_wizard_step(self):
        match = resolve("/apply/help/")
        self.assertEqual(match.func, views.apply_help)
        self.assertEqual(reverse("enrollment_help"), "/apply/help/")

    def test_help_page_english(self):
        response = self.client.get("/apply/help/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "How to apply")
        self.assertContains(response, "extra tabs")

    def test_help_page_spanish(self):
        session = self.client.session
        session["enrollment_lang"] = "es"
        session.save()
        response = self.client.get("/apply/help/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Cómo solicitar")
        self.assertContains(response, "pestañas extra")

    def test_apply_gate_includes_help(self):
        response = self.client.get("/apply/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Watch how to apply")
        self.assertContains(response, 'id="apply-help-modal"')

    def test_family_step_has_section_help(self):
        response = self.client.get("/apply/family/?new=1")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="apply-ui-strings"')
        self.assertContains(response, "Next section")
        self.assertContains(response, "Primary guardian")
        self.assertContains(response, "Watch how to apply")
