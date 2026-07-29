from django.test import TestCase

from portal.admin_config import delete_unit, save_unit, unit_delete_blockers
from portal.models import PortalFamily, PortalUnit


class AdminUnitTests(TestCase):
    def test_delete_empty_unit(self):
        unit = PortalUnit.objects.create(slug="test-empty", name="Test Empty", capacity=10)
        self.assertEqual(unit_delete_blockers(unit), [])
        delete_unit(unit.pk)
        self.assertFalse(PortalUnit.objects.filter(pk=unit.pk).exists())

    def test_delete_blocked_when_families_exist(self):
        unit = PortalUnit.objects.create(slug="test-busy", name="Test Busy", capacity=10)
        PortalFamily.objects.create(unit=unit, slug="fam1", name="Family One")
        blockers = unit_delete_blockers(unit)
        self.assertTrue(blockers)
        with self.assertRaises(ValueError):
            delete_unit(unit.pk)
        self.assertTrue(PortalUnit.objects.filter(pk=unit.pk).exists())

    def test_save_unit_updates_capacity(self):
        unit = PortalUnit.objects.create(slug="cap-test", name="Cap Test", capacity=50)
        class Data:
            def get(self, key, default=""):
                data = {
                    "name": "Cap Test",
                    "capacity": "99",
                    "program_type": "after_school",
                    "address": "",
                    "city": "",
                    "phone": "",
                    "manager": "",
                }
                return data.get(key, default)

        save_unit(Data(), unit_pk=unit.pk)
        unit.refresh_from_db()
        self.assertEqual(unit.capacity, 99)
