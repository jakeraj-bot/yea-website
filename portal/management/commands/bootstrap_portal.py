from django.core.management.base import BaseCommand, CommandError

from portal.admin_config import ensure_admin_config_minimal


class Command(BaseCommand):
    help = "Prepare an empty staging portal — org defaults only, no demo families or units."

    def handle(self, *args, **options):
        ensure_admin_config_minimal()
        self.stdout.write(
            self.style.SUCCESS(
                "Empty portal ready — fee rules, check-in toggles, and billing defaults are set.\n"
                "No units, families, or staff yet.\n"
                "Next: python manage.py create_portal_admin --username YOURUSER --password 'YourPass123!'"
            )
        )
