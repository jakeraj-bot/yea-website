import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("portal", "0022_payment_stripe_payout_id"),
    ]

    operations = [
        migrations.CreateModel(
            name="PortalParentEmail",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("sender_name", models.CharField(blank=True, max_length=160)),
                ("recipients", models.JSONField(default=list)),
                ("subject", models.CharField(max_length=200)),
                ("body", models.TextField()),
                ("attachment_names", models.JSONField(blank=True, default=list)),
                (
                    "source",
                    models.CharField(
                        choices=[
                            ("family", "Family email"),
                            ("bulk", "Email parents"),
                            ("reminder", "Reminder"),
                        ],
                        default="family",
                        max_length=32,
                    ),
                ),
                ("sent_at", models.DateTimeField(auto_now_add=True)),
                (
                    "family",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="parent_emails",
                        to="portal.portalfamily",
                    ),
                ),
                (
                    "sent_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="sent_parent_emails",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "unit",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="parent_emails",
                        to="portal.portalunit",
                    ),
                ),
            ],
            options={
                "ordering": ["-sent_at"],
            },
        ),
        migrations.CreateModel(
            name="PortalParentEmailAttachment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("file", models.FileField(upload_to="portal/parent-emails/%Y/%m/")),
                ("original_name", models.CharField(max_length=255)),
                ("content_type", models.CharField(blank=True, max_length=120)),
                ("size", models.PositiveIntegerField(default=0)),
                (
                    "email",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="files",
                        to="portal.portalparentemail",
                    ),
                ),
            ],
        ),
    ]
