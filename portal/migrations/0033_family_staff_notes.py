from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("portal", "0032_merge_late_fee_and_program_director"),
    ]

    operations = [
        migrations.CreateModel(
            name="PortalFamilyNote",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("author_name", models.CharField(max_length=200)),
                ("author_role", models.CharField(blank=True, max_length=64)),
                ("body", models.TextField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "author",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="family_notes_authored",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "child",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="staff_notes",
                        to="portal.portalchild",
                    ),
                ),
                (
                    "family",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="staff_notes",
                        to="portal.portalfamily",
                    ),
                ),
                (
                    "unit",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="family_notes",
                        to="portal.portalunit",
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at", "-pk"],
            },
        ),
    ]
