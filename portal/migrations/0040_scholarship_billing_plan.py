from django.db import migrations, models
import django.db.models.deletion


def attach_legacy_scholarships_to_primary_plan(apps, schema_editor):
    Assignment = apps.get_model("portal", "PortalScholarshipAssignment")
    Plan = apps.get_model("portal", "PortalChildBillingPlan")
    for row in Assignment.objects.filter(billing_plan__isnull=True):
        plan = (
            Plan.objects.filter(child_id=row.child_id, sort_order=1).first()
            or Plan.objects.filter(child_id=row.child_id).order_by("sort_order", "pk").first()
        )
        if plan:
            row.billing_plan_id = plan.pk
            row.save(update_fields=["billing_plan"])


def noop_reverse(apps, schema_editor):
    return None


class Migration(migrations.Migration):

    dependencies = [
        ("portal", "0039_monthly_plan_weekly_rate"),
    ]

    operations = [
        migrations.AddField(
            model_name="portalscholarshipassignment",
            name="billing_plan",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="scholarships",
                to="portal.portalchildbillingplan",
            ),
        ),
        migrations.RunPython(attach_legacy_scholarships_to_primary_plan, noop_reverse),
    ]
