from unittest.mock import patch

from django.core.cache import cache
from django.test import Client, TestCase
from django.urls import reverse

from core.models import ContactMessage
from core.spam_protection import CONTACT_FORM_SESSION_KEY


class ContactSpamProtectionTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = Client()
        self.url = reverse("contact")
        self.payload = {
            "name": "Test Parent",
            "email": "parent@example.com",
            "topic": "general",
            "message": "Hello from a real family.",
            "company": "",
        }

    def _open_form(self):
        self.client.get(self.url)

    @patch("core.views.send_site_email")
    def test_valid_contact_submission(self, mock_send):
        self._open_form()
        with self.settings(CONTACT_FORM_MIN_SECONDS=0):
            response = self.client.post(self.url, self.payload)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(ContactMessage.objects.count(), 1)
        mock_send.assert_called_once()

    @patch("core.views.send_site_email")
    def test_honeypot_is_silently_rejected(self, mock_send):
        self._open_form()
        payload = self.payload.copy()
        payload["company"] = "Acme SEO Services"
        with self.settings(CONTACT_FORM_MIN_SECONDS=0):
            response = self.client.post(self.url, payload)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(ContactMessage.objects.count(), 0)
        mock_send.assert_not_called()

    @patch("core.views.send_site_email")
    def test_too_fast_submission_is_silently_rejected(self, mock_send):
        self._open_form()
        with self.settings(CONTACT_FORM_MIN_SECONDS=60):
            response = self.client.post(self.url, self.payload)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(ContactMessage.objects.count(), 0)
        mock_send.assert_not_called()

    def test_rate_limit_helpers(self):
        from django.contrib.sessions.middleware import SessionMiddleware
        from django.test import RequestFactory

        from core.spam_protection import is_contact_rate_limited, record_contact_submission

        factory = RequestFactory()
        request = factory.post("/contact/")
        request.META["REMOTE_ADDR"] = "127.0.0.1"
        middleware = SessionMiddleware(lambda req: None)
        middleware.process_request(request)
        request.session.save()

        with self.settings(CONTACT_FORM_RATE_LIMIT=2):
            self.assertFalse(is_contact_rate_limited(request))
            record_contact_submission(request)
            self.assertFalse(is_contact_rate_limited(request))
            record_contact_submission(request)
            self.assertTrue(is_contact_rate_limited(request))

    @patch("core.views.send_site_email")
    def test_rate_limit_blocks_repeated_submissions(self, mock_send):
        with self.settings(CONTACT_FORM_MIN_SECONDS=0, CONTACT_FORM_RATE_LIMIT=2):
            self.client.get(self.url)
            for index in range(2):
                response = self.client.post(self.url, self.payload)
                self.assertEqual(response.status_code, 302, msg=f"submission {index + 1}")
            self.assertEqual(ContactMessage.objects.count(), 2)
            response = self.client.post(self.url, self.payload)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Too many messages")
        self.assertEqual(ContactMessage.objects.count(), 2)
        self.assertEqual(mock_send.call_count, 2)

    @patch("core.views.verify_turnstile", return_value=False)
    @patch("core.views.send_site_email")
    def test_turnstile_failure_shows_error(self, mock_send, _mock_turnstile):
        self._open_form()
        with self.settings(
            CONTACT_FORM_MIN_SECONDS=0,
            TURNSTILE_SITE_KEY="site-key",
            TURNSTILE_SECRET_KEY="secret-key",
        ):
            response = self.client.post(self.url, self.payload)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "security check")
        self.assertEqual(ContactMessage.objects.count(), 0)
        mock_send.assert_not_called()

    def test_contact_get_starts_session_timer(self):
        self.client.get(self.url)
        self.assertIn(CONTACT_FORM_SESSION_KEY, self.client.session)
