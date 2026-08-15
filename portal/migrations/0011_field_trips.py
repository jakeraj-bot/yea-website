import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("portal", "0010_payment_refunds"),
    ]

    operations = [
        migrations.CreateModel(
            name="PortalFieldTrip",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=180)),
                ("slug", models.SlugField(unique=True)),
                ("trip_date", models.DateField()),
                ("location", models.CharField(blank=True, max_length=255)),
                ("description", models.TextField(blank=True)),
                ("fee_amount", models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ("permission_slip", models.TextField()),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "unit",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="field_trips",
                        to="portal.portalunit",
                    ),
                ),
            ],
            options={"ordering": ["-trip_date", "-created_at"]},
        ),
        migrations.CreateModel(
            name="PortalFieldTripSignup",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Needs signature"),
                            ("signed", "Signed — pay now"),
                            ("paid", "Paid"),
                        ],
                        default="pending",
                        max_length=16,
                    ),
                ),
                ("signature_name", models.CharField(blank=True, max_length=120)),
                ("signed_at", models.DateTimeField(blank=True, null=True)),
                (
                    "child",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="field_trip_signups",
                        to="portal.portalchild",
                    ),
                ),
                (
                    "family",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="field_trip_signups",
                        to="portal.portalfamily",
                    ),
                ),
                (
                    "payment",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="field_trip_signups",
                        to="portal.portalpayment",
                    ),
                ),
                (
                    "trip",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="signups",
                        to="portal.portalfieldtrip",
                    ),
                ),
            ],
            options={"ordering": ["child__name"], "unique_together": {("trip", "child")}},
        ),
    ]
