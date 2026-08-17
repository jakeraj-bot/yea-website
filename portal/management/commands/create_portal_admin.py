from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from portal.models import PortalStaffAccount, PortalUnit
from portal.usernames import display_username, migrate_user_username, portal_username


class Command(BaseCommand):
    help = "Create a portal admin login (role: Portal admin, all units)."

    def add_arguments(self, parser):
        parser.add_argument("--username", required=True, help="Login username")
        parser.add_argument("--password", required=True, help="Login password")
        parser.add_argument("--name", default="", help="Display name (defaults to username)")
        parser.add_argument("--email", default="", help="Email address")
        parser.add_argument(
            "--unit-name",
            default="Main location",
            help="Unit name if no unit exists yet (admin accounts require a home unit)",
        )

    def handle(self, *args, **options):
        login_name = options["username"].strip()
        password = options["password"]
        display_name = (options["name"] or login_name).strip()
        email = (options["email"] or f"{login_name}@yeanj.org").strip()
        stored_username = portal_username("admin", login_name)

        if len(password) < 8:
            raise CommandError("Password must be at least 8 characters.")

        User = get_user_model()
        unit = PortalUnit.objects.filter(is_active=True).order_by("id").first()
        if not unit:
            unit = PortalUnit.objects.create(
                slug="main-location",
                name=options["unit_name"],
                is_active=True,
            )
            self.stdout.write(f"Created placeholder unit: {unit.name}")

        user = User.objects.filter(username__iexact=stored_username).first()
        created = False
        if not user:
            legacy = User.objects.filter(username__iexact=login_name).first()
            if legacy:
                user = legacy
                migrate_user_username(user, "admin")
            else:
                user = User.objects.create_user(
                    username=stored_username,
                    email=email,
                    password=password,
                    first_name=display_name,
                )
                created = True
        user.email = email
        user.first_name = display_name
        user.set_password(password)
        user.is_staff = True
        user.save()

        account, account_created = PortalStaffAccount.objects.update_or_create(
            user=user,
            defaults={
                "unit": unit,
                "display_name": display_name,
                "role": "Portal admin",
                "all_units_access": True,
                "can_add_charge": True,
                "can_delete_charge": True,
                "can_add_credit": True,
                "can_edit_family_plans": True,
                "can_approve_applications": True,
                "can_approve_waitlist": True,
                "is_active": True,
            },
        )

        verb = "Created" if created or account_created else "Updated"
        self.stdout.write(
            self.style.SUCCESS(
                f"{verb} portal admin: {display_username(user.username)}\n"
                f"Sign in at /portal/admin/login/"
            )
        )
