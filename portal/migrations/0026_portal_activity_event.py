from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("portal", "0025_program_calendar_and_week_includes"),
    ]

    operations = [
        migrations.CreateModel(
            name="PortalActivityEvent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("actor_username", models.CharField(max_length=150)),
                ("actor_name", models.CharField(blank=True, max_length=200)),
                ("actor_role", models.CharField(blank=True, max_length=32)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                (
                    "action",
                    models.CharField(
                        choices=[
                            ("login", "Signed in"),
                            ("save", "Saved"),
                            ("delete", "Deleted"),
                            ("charge", "Posted a charge"),
                            ("payment", "Recorded a payment"),
                            ("email", "Sent email"),
                            ("password_reset", "Reset password"),
                            ("attendance", "Attendance"),
                            ("application", "Application review"),
                            ("plan", "Saved a plan"),
                            ("agency", "Saved 4Cs"),
                            ("other", "Other"),
                        ],
                        default="other",
                        max_length=32,
                    ),
                ),
                ("action_label", models.CharField(max_length=120)),
                ("object_type", models.CharField(blank=True, max_length=64)),
                ("object_label", models.CharField(blank=True, max_length=255)),
                ("page_path", models.CharField(blank=True, max_length=255)),
                ("details", models.TextField(blank=True)),
                ("delete_reason", models.TextField(blank=True)),
                (
                    "actor",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="portal_activity_events",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "unit",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="activity_events",
                        to="portal.portalunit",
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="portalactivityevent",
            index=models.Index(fields=["actor", "-created_at"], name="portal_port_actor_i_8c4a21_idx"),
        ),
        migrations.AddIndex(
            model_name="portalactivityevent",
            index=models.Index(fields=["action", "-created_at"], name="portal_port_action_7e1c4b_idx"),
        ),
    ]
