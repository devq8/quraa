from unittest import mock

from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import SiteSettings


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    SITE_EMAIL="trajemqurraa@gmail.com",
    DEFAULT_FROM_EMAIL="trajemqurraa@gmail.com",
)
class ContactFormTests(TestCase):
    """The contact form sends mail from the site address to the site inbox."""

    def setUp(self):
        self.url = reverse("landing:contact_form")
        self.data = {
            "name": "Visitor",
            "email": "visitor@example.com",
            "subject": "Hello",
            "comments": "A message",
        }

    def test_sends_to_site_email_with_visitor_reply_to(self):
        response = self.client.post(self.url, self.data)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])
        self.assertEqual(len(mail.outbox), 1)
        sent = mail.outbox[0]
        self.assertEqual(sent.to, ["trajemqurraa@gmail.com"])
        self.assertEqual(sent.from_email, "trajemqurraa@gmail.com")
        self.assertEqual(sent.reply_to, ["visitor@example.com"])
        self.assertIn("A message", sent.body)

    def test_uses_site_settings_contact_email_when_set(self):
        SiteSettings.objects.create(contact_email="inbox@example.com")
        self.client.post(self.url, self.data)
        self.assertEqual(mail.outbox[0].to, ["inbox@example.com"])

    def test_missing_field_is_rejected(self):
        response = self.client.post(self.url, {**self.data, "comments": ""})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(len(mail.outbox), 0)

    def test_invalid_email_is_rejected(self):
        response = self.client.post(self.url, {**self.data, "email": "bad"})
        self.assertEqual(response.status_code, 400)

    def test_smtp_failure_returns_json_error(self):
        with mock.patch(
            "django.core.mail.EmailMessage.send", side_effect=OSError("smtp down")
        ), self.assertLogs("landing.views", level="ERROR"):
            response = self.client.post(self.url, self.data)
        self.assertEqual(response.status_code, 500)
        self.assertFalse(response.json()["success"])

    def test_get_not_allowed(self):
        self.assertEqual(self.client.get(self.url).status_code, 405)
