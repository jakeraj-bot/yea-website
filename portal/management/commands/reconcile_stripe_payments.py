from django.core.management.base import BaseCommand

from portal.models import PortalPayment
from portal.stripe_services import confirm_checkout_payment, stripe_configured


class Command(BaseCommand):
    help = "Apply paid Stripe checkout sessions that are still pending in the portal."

    def add_arguments(self, parser):
        parser.add_argument(
            "--family",
            help="Limit to a family slug (optional).",
        )

    def handle(self, *args, **options):
        if not stripe_configured():
            self.stderr.write("Member Stripe is not configured (MEMBER_STRIPE_* keys).")
            return

        pending = PortalPayment.objects.filter(
            status=PortalPayment.STATUS_PENDING,
        ).exclude(stripe_session_id="")
        if options.get("family"):
            pending = pending.filter(family__slug=options["family"])

        if not pending.exists():
            self.stdout.write("No pending Stripe payments to reconcile.")
            return

        for payment in pending.select_related("family"):
            confirmed = confirm_checkout_payment(payment.stripe_session_id)
            if confirmed and confirmed.status == PortalPayment.STATUS_PAID:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"{payment.family.slug}: ${payment.amount} — receipt {confirmed.receipt_no}"
                    )
                )
            else:
                self.stdout.write(f"{payment.family.slug}: session {payment.stripe_session_id} — still pending in Stripe")
