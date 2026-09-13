from django.core.management.base import BaseCommand
from django.utils import timezone

from portal.email_templates import send_late_payment_notices


class Command(BaseCommand):
    help = (
        "Email families who still owe the Friday late-payment reminder. "
        "Run on Fridays (due Friday; $15 late fee as of Tuesday). Use --force any day."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Send even if today is not Friday.",
        )

    def handle(self, *args, **options):
        today = timezone.localdate()
        if today.weekday() != 4 and not options["force"]:
            self.stdout.write("Skipped — late-payment notices send on Friday. Use --force to send today.")
            return
        try:
            sent, total = send_late_payment_notices()
        except ValueError as exc:
            self.stdout.write(str(exc))
            return
        self.stdout.write(self.style.SUCCESS(f"Sent {sent} of {total} late-payment reminder(s)."))
