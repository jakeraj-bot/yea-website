from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from portal.models import PortalFamily, PortalParentAccount, PortalStaffAccount
from portal.usernames import portal_username

DEMO_FAMILY_SLUGS = ("jacobs", "martinez", "williams", "chen")
DEMO_PARENT_USERNAMES = ("jakeraj", "mmartinez", "dwilliams")
DEMO_STAFF_USERNAMES = ("staff18",)


class Command(BaseCommand):
    help = (
        "Remove leftover demo seed families/logins and parent accounts that have "
        "no enrollment application. Does not delete families with real applications."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--demo-only",
            action="store_true",
            help="Only remove known demo seed families (Jacobs, Martinez, Williams) and demo logins.",
        )
        parser.add_argument("--dry-run", action="store_true", help="Show what would be deleted.")

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        demo_only = options["demo_only"]
        User = get_user_model()
        deleted_families = 0
        deleted_users = 0

        families = PortalFamily.objects.all()
        deleted_families = 0
        deleted_users = 0

        for family in families:
            is_demo = family.slug in DEMO_FAMILY_SLUGS
            if demo_only and not is_demo:
                continue
            has_app = family.enrollment_applications.exists()
            has_kids = family.children.filter(is_active=True).exists()
            if not is_demo and (has_app or has_kids):
                continue
            accounts = list(PortalParentAccount.objects.filter(family=family).select_related("user"))
            self.stdout.write(f"Family {family.name} ({family.slug})")
            if dry_run:
                deleted_families += 1
                deleted_users += len(accounts)
                continue
            for account in accounts:
                user = account.user
                account.delete()
                if user and not user.is_superuser:
                    user.delete()
                    deleted_users += 1
            family.delete()
            deleted_families += 1

        if demo_only or True:
            demo_usernames = [portal_username("parent", name) for name in DEMO_PARENT_USERNAMES]
            demo_usernames += [portal_username("staff", name) for name in DEMO_STAFF_USERNAMES]
            leftover = User.objects.filter(username__in=demo_usernames, is_superuser=False)
            for user in leftover:
                if PortalStaffAccount.objects.filter(user=user, role="Portal admin").exists():
                    continue
                self.stdout.write(f"Demo user {user.username}")
                if dry_run:
                    deleted_users += 1
                    continue
                PortalStaffAccount.objects.filter(user=user).delete()
                PortalParentAccount.objects.filter(user=user).delete()
                user.delete()
                deleted_users += 1

        prefix = "Would delete" if dry_run else "Deleted"
        self.stdout.write(self.style.SUCCESS(f"{prefix} {deleted_families} families and {deleted_users} logins."))
