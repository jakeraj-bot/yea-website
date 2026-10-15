from datetime import date

from django.core.management.base import BaseCommand

from portal.billing_services import rewrite_auto_charge_descriptions


class Command(BaseCommand):
    help = "Rewrite 10/15/2026 auto plan charge descriptions to the CC WK templates (amounts unchanged)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--date",
            default="2026-10-15",
            help="Charge date to rewrite (YYYY-MM-DD). Default 2026-10-15.",
        )

    def handle(self, *args, **options):
        raw = (options.get("date") or "2026-10-15").strip()
        year, month, day = (int(part) for part in raw.split("-"))
        on_date = date(year, month, day)
        updated = rewrite_auto_charge_descriptions(on_date=on_date)
        if not updated:
            self.stdout.write(f"No auto plan charges needed a description rewrite on {on_date.isoformat()}.")
            return
        self.stdout.write(
            self.style.SUCCESS(f"Rewrote {len(updated)} charge description(s) on {on_date.isoformat()}.")
        )
        for entry in updated:
            self.stdout.write(f"  {entry.family.slug} · {entry.child_name}: {entry.description}")
