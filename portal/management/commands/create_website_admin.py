from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Create a Django website admin superuser for /admin/ (site pages, photos — not portal admin)."

    def add_arguments(self, parser):
        parser.add_argument("--username", required=True, help="Login username")
        parser.add_argument("--password", required=True, help="Login password")
        parser.add_argument("--email", default="", help="Email address")

    def handle(self, *args, **options):
        username = options["username"].strip()
        password = options["password"]
        email = (options["email"] or f"{username}@yeanj.org").strip()

        if len(password) < 8:
            raise CommandError("Password must be at least 8 characters.")

        User = get_user_model()
        user, created = User.objects.get_or_create(
            username=username,
            defaults={"email": email, "is_staff": True, "is_superuser": True},
        )
        user.email = email
        user.is_staff = True
        user.is_superuser = True
        user.set_password(password)
        user.save()

        verb = "Created" if created else "Updated"
        self.stdout.write(
            self.style.SUCCESS(
                f"{verb} website admin superuser: {username}\n"
                f"Sign in at /admin/ to edit public site pages and photos."
            )
        )
