from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from core.email_service import email_is_configured, send_site_email


class Command(BaseCommand):
    help = "Send a test email to verify SMTP settings (e.g. on Render)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--to",
            default=settings.CONTACT_EMAIL,
            help=f"Recipient address (default: CONTACT_EMAIL = {settings.CONTACT_EMAIL})",
        )

    def handle(self, *args, **options):
        recipient = options["to"].strip()
        if not recipient:
            raise CommandError("Provide --to or set CONTACT_EMAIL.")

        self.stdout.write(f"EMAIL_BACKEND: {settings.EMAIL_BACKEND}")
        self.stdout.write(f"EMAIL_HOST: {settings.EMAIL_HOST or '(not set)'}")
        self.stdout.write(f"EMAIL_HOST_USER: {settings.EMAIL_HOST_USER or '(not set)'}")
        self.stdout.write(f"DEFAULT_FROM_EMAIL: {settings.DEFAULT_FROM_EMAIL}")
        self.stdout.write(f"Configured: {email_is_configured()}")

        if not email_is_configured():
            raise CommandError(
                "SMTP is not configured. Set EMAIL_HOST, EMAIL_HOST_USER, and EMAIL_HOST_PASSWORD "
                "in Render → Environment, then redeploy."
            )

        sent = send_site_email(
            subject="[YEA] Test email from yea-website",
            message=(
                "This is a test message from your YEA website on Render.\n\n"
                "If you received this, enrollment and contact form emails should work.\n"
            ),
            recipient_list=[recipient],
            fail_silently=False,
        )
        if sent:
            self.stdout.write(self.style.SUCCESS(f"Test email sent to {recipient}."))
        else:
            raise CommandError("send_site_email returned 0 — check server logs.")
