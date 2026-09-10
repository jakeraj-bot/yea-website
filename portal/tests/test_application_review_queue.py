from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from enrollment.models import EnrollmentApplication
from enrollment.portal_integration import applications_for_admin, applications_for_staff, first_reviewable_application
from portal.models import PortalFamily, PortalStaffAccount, PortalUnit
from portal.staff_auth import PORTAL_AUTH_SESSION_KEY
from portal.tests.test_family_units import _make_application


class ApplicationReviewQueueTests(TestCase):
    def setUp(self):
        self.unit = PortalUnit.objects.create(
            slug="school-18",
            name="School 18",
            program_type="after_school",
            is_active=True,
        )
        self.family = PortalFamily.objects.create(unit=self.unit, slug="rivera", name="Rivera")
        self.older = _make_application(self.family, status="under_review")
        self.older.student_first_name = "Ada"
        self.older.save(update_fields=["student_first_name"])
        self.newer = _make_application(self.family, status="pending_documents")
        self.newer.student_first_name = "Ben"
        self.newer.save(update_fields=["student_first_name"])
        self.approved = _make_application(self.family, status="approved")
        self.approved.student_first_name = "Cara"
        self.approved.save(update_fields=["student_first_name"])
        now = timezone.now()
        EnrollmentApplication.objects.filter(pk=self.older.pk).update(submitted_at=now - timedelta(days=3))
        EnrollmentApplication.objects.filter(pk=self.newer.pk).update(submitted_at=now - timedelta(days=1))
        EnrollmentApplication.objects.filter(pk=self.approved.pk).update(submitted_at=now - timedelta(days=10))
        self.older.refresh_from_db()
        self.newer.refresh_from_db()

        User = get_user_model()
        self.staff_user = User.objects.create_user(username="staff:queue", password="StaffPass123!")
        PortalStaffAccount.objects.create(
            user=self.staff_user,
            unit=self.unit,
            display_name="Queue Staff",
            role="Unit director",
            is_active=True,
        )
        self.admin_user = User.objects.create_user(username="staff:yeaadmin", password="AdminPass123")
        PortalStaffAccount.objects.create(
            user=self.admin_user,
            unit=self.unit,
            display_name="Portal Admin",
            role="Portal admin",
            all_units_access=True,
            is_active=True,
        )

    def _login(self, user, area):
        self.client.force_login(user)
        session = self.client.session
        session[PORTAL_AUTH_SESSION_KEY] = area
        session.save()

    def test_applications_ordered_by_submitted_at_ascending(self):
        admin_rows = applications_for_admin()
        self.assertEqual([row["child"] for row in admin_rows], ["Ada Rivera", "Ben Rivera"])
        staff_rows = applications_for_staff(self.unit)
        self.assertEqual([row["child"] for row in staff_rows], ["Ada Rivera", "Ben Rivera"])
        self.assertEqual(str(first_reviewable_application().reference), str(self.older.reference))
        self.assertEqual(str(first_reviewable_application(unit=self.unit).reference), str(self.older.reference))

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_review_all_lands_on_oldest_pending(self):
        self._login(self.staff_user, "staff")
        staff_list = self.client.get(reverse("portal_staff_page", kwargs={"page": "applications"}))
        self.assertEqual(staff_list.status_code, 200)
        self.assertContains(staff_list, "Review all")
        self.assertContains(staff_list, "Submitted (oldest first)")
        html = staff_list.content.decode()
        self.assertLess(html.index("Ada Rivera"), html.index("Ben Rivera"))
        self.assertNotContains(staff_list, "Cara Rivera")

        review_all = self.client.get(reverse("portal_staff_review_all"))
        self.assertEqual(review_all.status_code, 302)
        self.assertEqual(
            review_all.url,
            reverse("portal_staff_application_detail", kwargs={"app_slug": str(self.older.reference)}),
        )
        detail = self.client.get(review_all.url)
        self.assertEqual(detail.status_code, 200)
        self.assertContains(detail, "Ada Rivera")
        self.assertContains(detail, "Next application")
        self.assertEqual(detail.context["application"]["next_slug"], str(self.newer.reference))

    @override_settings(PORTAL_PREVIEW_MODE=False)
    def test_admin_review_all_uses_same_oldest_queue(self):
        self._login(self.admin_user, "admin")
        admin_list = self.client.get(reverse("portal_admin_page", kwargs={"page": "applications"}))
        self.assertEqual(admin_list.status_code, 200)
        self.assertContains(admin_list, "Review all")
        review_all = self.client.get(reverse("portal_admin_review_all"))
        self.assertEqual(review_all.status_code, 302)
        self.assertEqual(
            review_all.url,
            reverse("portal_admin_application_detail", kwargs={"app_slug": str(self.older.reference)}),
        )
