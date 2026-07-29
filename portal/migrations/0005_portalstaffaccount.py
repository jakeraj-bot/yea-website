from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("portal", "0004_parent_profile_photo"),
    ]

    operations = [
        migrations.CreateModel(
            name="PortalStaffAccount",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("display_name", models.CharField(max_length=120)),
                ("role", models.CharField(default="Unit staff", max_length=64)),
                ("can_add_charge", models.BooleanField(default=True)),
                ("can_delete_charge", models.BooleanField(default=False)),
                ("can_add_credit", models.BooleanField(default=False)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "unit",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="staff_accounts", to="portal.portalunit"),
                ),
                (
                    "user",
                    models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="portal_staff_account", to=settings.AUTH_USER_MODEL),
                ),
            ],
            options={
                "ordering": ["display_name"],
            },
        ),
    ]
