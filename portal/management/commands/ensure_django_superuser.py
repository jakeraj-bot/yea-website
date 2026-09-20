from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from portal.parent_auth import get_parent_account
from portal.staff_auth import is_portal_admin, sync_django_backend_access
from portal.usernames import display_username, resolve_auth_username


class Command(BaseCommand):
    help = (
        "Mark a portal org admin as Django /admin/ staff+superuser. "
        "Looks up yeaadmin even when the stored username is admin:yeaadmin. "
        "Does not print password hashes. Omit --password to leave the password alone."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--username",
            default="yeaadmin",
            help="Name typed at /admin/ (default: yeaadmin)",
        )
        parser.add_argument(
            "--password",
            default="",
            help="Optional new password (8+ characters). Leave off to keep the current one.",
        )
        parser.add_argument("--name", default="", help="Optional display first name")

    def handle(self, *args, **options):
        login_name = (options["username"] or "").strip()
        if not login_name:
            raise CommandError("Username is required.")

        User = get_user_model()
        stored = resolve_auth_username("admin", login_name)
        user = User.objects.filter(username__iexact=stored).first()
        if not user:
            user = User.objects.filter(username__iexact=login_name).first()
        if not user:
            raise CommandError(
                f"No user found for {login_name}. Create one with:\n"
                f"  python manage.py create_portal_admin --username {login_name} "
                f"--password 'YourNewPass123!'"
            )

        if get_parent_account(user) and not is_portal_admin(user):
            raise CommandError("Refusing to grant Django /admin/ access to a parent-only account.")

        password = (options["password"] or "").strip()
        if password:
            if len(password) < 8:
                raise CommandError("Password must be at least 8 characters.")
            user.set_password(password)

        name = (options["name"] or "").strip()
        if name:
            user.first_name = name

        user.is_staff = True
        user.is_superuser = True
        user.is_active = True
        user.save()
        sync_django_backend_access(user)
        user.refresh_from_db()

        typed = display_username(user.username)
        self.stdout.write(
            self.style.SUCCESS(
                f"Django backend ready.\n"
                f"  Type at /admin/: {typed}\n"
                f"  is_staff: {user.is_staff}\n"
                f"  is_superuser: {user.is_superuser}\n"
                f"  password: {'updated' if password else 'unchanged'}\n"
                f"Sign in at /admin/ — this is not /portal/admin/login/."
            )
        )
