from django.test import SimpleTestCase

from portal.child_identity import child_name_in_collection, child_names_match


class ChildNameMatchTests(SimpleTestCase):
    def test_middle_name_is_same_child(self):
        self.assertTrue(child_names_match("Danuska Montoya Cuenca", "Danuska Daenerys Montoya Cuenca"))
        self.assertTrue(child_names_match("Danuska Daenerys Montoya Cuenca", "Danuska Montoya Cuenca"))

    def test_different_last_name_is_not_the_same_child(self):
        self.assertFalse(child_names_match("Danuska Rivera", "Danuska Lee"))
        self.assertFalse(child_names_match("Ada Rivera", "Ben Rivera"))

    def test_collection_helper(self):
        self.assertTrue(
            child_name_in_collection(
                "Danuska Daenerys Montoya Cuenca",
                ["Danuska Montoya Cuenca", "Jordan Rivera"],
            )
        )
        self.assertFalse(child_name_in_collection("Danuska Lee", ["Danuska Rivera"]))
