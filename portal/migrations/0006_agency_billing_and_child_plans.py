from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("portal", "0005_portalstaffaccount"),
    ]

    operations = [
        migrations.AddField(
            model_name="portalchild",
            name="billing_amount",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True),
        ),
        migrations.AddField(
            model_name="portalchild",
            name="billing_plan",
            field=models.CharField(default="Weekly", max_length=64),
        ),
        migrations.CreateModel(
            name="PortalAgencyProfile",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("auth_number", models.CharField(max_length=64)),
                ("auth_start", models.DateField(blank=True, null=True)),
                ("auth_end", models.DateField(blank=True, null=True)),
                ("weekly_copay", models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ("weekly_agency_rate", models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ("agency_balance", models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ("notes", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("child", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="agency_profile", to="portal.portalchild")),
                ("family", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="agency_profiles", to="portal.portalfamily")),
                ("unit", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="agency_profiles", to="portal.portalunit")),
            ],
            options={"ordering": ["child__name"]},
        ),
        migrations.CreateModel(
            name="PortalAgencyRemittance",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("date", models.DateField()),
                ("reference", models.CharField(max_length=64)),
                ("total_amount", models.DecimalField(decimal_places=2, max_digits=10)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("unit", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="agency_remittances", to="portal.portalunit")),
            ],
            options={"ordering": ["-date", "-created_at"]},
        ),
        migrations.CreateModel(
            name="PortalAgencyLedgerEntry",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("date", models.DateField()),
                ("entry_type", models.CharField(max_length=32)),
                ("description", models.CharField(max_length=255)),
                ("amount", models.DecimalField(decimal_places=2, max_digits=10)),
                ("is_manual", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("profile", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="ledger_entries", to="portal.portalagencyprofile")),
            ],
            options={"ordering": ["-date", "-created_at"]},
        ),
        migrations.CreateModel(
            name="PortalAgencyRemittanceAllocation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("amount", models.DecimalField(decimal_places=2, max_digits=10)),
                ("profile", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="remittance_allocations", to="portal.portalagencyprofile")),
                ("remittance", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="allocations", to="portal.portalagencyremittance")),
            ],
            options={"ordering": ["profile__child__name"]},
        ),
    ]
