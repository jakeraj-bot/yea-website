from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from portal.models import PortalParentAccount, PortalStaffAccount
from portal.usernames import migrate_user_username


class Command(BaseCommand):
    help = "Move legacy portal logins to separate parent/staff/admin username namespaces."

    def add_arguments(self, parser):
        parser.add_argument(
            "--yes",
            action="store_true",
            help="Skip confirmation prompt (for deploy scripts).",
        )

    def handle(self, *args, **options):
        if not options["yes"]:
            self.stdout.write(
                "This prefixes stored usernames as parent:, staff:, or admin: "
                "so the same login name can exist in each portal separately."
            )
            confirm = input("Type MIGRATE to continue: ")
            if confirm.strip() != "MIGRATE":
                self.stdout.write(self.style.WARNING("Cancelled."))
                return

        migrated = 0
        with transaction.atomic():
            for account in PortalParentAccount.objects.select_related("user"):
                _, changed = migrate_user_username(account.user, "parent")
                if changed:
                    migrated += 1

            for account in PortalStaffAccount.objects.select_related("user"):
                portal_type = "admin" if account.role == "Portal admin" else "staff"
                _, changed = migrate_user_username(account.user, portal_type)
                if changed:
                    migrated += 1

        self.stdout.write(self.style.SUCCESS(f"Migrated {migrated} portal login(s)."))
        if migrated:
            self.stdout.write("Users still sign in with the same name they see — prefixes are internal only.")
