import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("dropin", "0003_dropinwaitlistentry"),
        ("portal", "0006_agency_billing_and_child_plans"),
    ]

    operations = [
        migrations.CreateModel(
            name="PortalProfileChangeRequest",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("changes", models.JSONField(default=dict)),
                (
                    "status",
                    models.CharField(
                        choices=[("pending", "Pending review"), ("approved", "Approved"), ("rejected", "Rejected")],
                        default="pending",
                        max_length=16,
                    ),
                ),
                ("submitted_at", models.DateTimeField(auto_now_add=True)),
                ("reviewed_at", models.DateTimeField(blank=True, null=True)),
                ("reviewed_by", models.CharField(blank=True, max_length=120)),
                ("notes", models.TextField(blank=True)),
                (
                    "account",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="change_requests",
                        to="portal.portalparentaccount",
                    ),
                ),
            ],
            options={
                "ordering": ["-submitted_at"],
            },
        ),
        migrations.AddField(
            model_name="portalpayment",
            name="dropin_booking",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="portal_payments",
                to="dropin.dropinbooking",
            ),
        ),
    ]
