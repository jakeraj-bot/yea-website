from pathlib import Path

from django.test import SimpleTestCase


class MobileCssTests(SimpleTestCase):
    def test_site_css_phone_rules_live_inside_media_queries(self):
        css = Path("static/css/site.css").read_text()
        self.assertIn("@media (max-width: 640px)", css)
        self.assertIn("@media (min-width: 640px)", css)
        desktop_grid = css.split("@media (min-width: 640px)")[1].split("@media")[0]
        self.assertIn("grid-template-columns: repeat(2, minmax(0, 1fr))", desktop_grid)
        phone = css.split("@media (max-width: 640px)")[-1]
        self.assertIn(".card-grid-2", phone)
        self.assertIn("grid-template-columns: 1fr", phone)
        self.assertIn("max-width: 100%", phone)
        self.assertIn("font-size: 16px", phone)
        self.assertIn(".apply-form .form-group input", phone)
        self.assertIn("min-height: 2.75rem", phone)

    def test_portal_css_phone_rules_do_not_replace_desktop_grids(self):
        css = Path("static/css/portal.css").read_text()
        desktop = css.split("@media (max-width: 640px)")[0]
        self.assertIn("grid-template-columns: repeat(2, minmax(0, 1fr))", desktop)
        self.assertIn(".portal-reports-grid", desktop)
        phone = css.split("@media (max-width: 640px)")[-1]
        self.assertIn("font-size: 16px", phone)
        self.assertIn(".portal-table-wrap", phone)
        self.assertIn("overflow-x: auto", phone)
        self.assertIn("min-height: 2.75rem", phone)
