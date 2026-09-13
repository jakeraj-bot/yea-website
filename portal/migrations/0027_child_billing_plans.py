from django.db import migrations, models
import django.db.models.deletion


def copy_primary_plans(apps, schema_editor):
    PortalChild = apps.get_model("portal", "PortalChild")
    PortalChildBillingPlan = apps.get_model("portal", "PortalChildBillingPlan")
    for child in PortalChild.objects.all().iterator():
        PortalChildBillingPlan.objects.create(
            child=child,
            description="",
            billing_plan=child.billing_plan or "Weekly",
            billing_amount=child.billing_amount,
            auto_charge=child.auto_charge,
            next_charge_date=child.next_charge_date,
            last_auto_charge_date=child.last_auto_charge_date,
            charge_weekday=child.charge_weekday,
            charge_month_day=child.charge_month_day,
            billing_kind="",
            sort_order=1,
        )


def uncopy_primary_plans(apps, schema_editor):
    PortalChildBillingPlan = apps.get_model("portal", "PortalChildBillingPlan")
    PortalChildBillingPlan.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ("portal", "0026_portal_activity_event"),
    ]

    operations = [
        migrations.CreateModel(
            name="PortalChildBillingPlan",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("description", models.CharField(blank=True, max_length=120)),
                ("billing_plan", models.CharField(default="Weekly", max_length=64)),
                (
                    "billing_amount",
                    models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True),
                ),
                ("auto_charge", models.BooleanField(default=False)),
                ("next_charge_date", models.DateField(blank=True, null=True)),
                ("last_auto_charge_date", models.DateField(blank=True, null=True)),
                ("charge_weekday", models.PositiveSmallIntegerField(blank=True, null=True)),
                ("charge_month_day", models.PositiveSmallIntegerField(blank=True, null=True)),
                ("billing_kind", models.CharField(blank=True, max_length=32)),
                ("sort_order", models.PositiveSmallIntegerField(default=1)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "child",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="billing_plans",
                        to="portal.portalchild",
                    ),
                ),
            ],
            options={"ordering": ["sort_order", "pk"]},
        ),
        migrations.RunPython(copy_primary_plans, uncopy_primary_plans),
    ]
