from decimal import Decimal, ROUND_HALF_UP

from django.db import migrations, models


FOUR = Decimal("4")
MONEY = Decimal("0.01")


def _is_monthly(plan):
    return "month" in (plan or "").lower()


def backfill_weekly_rate(apps, schema_editor):
    """Old monthly plans stored a flat 4-week amount. Convert that to a weekly rate."""
    Child = apps.get_model("portal", "PortalChild")
    Plan = apps.get_model("portal", "PortalChildBillingPlan")
    for child in Child.objects.all():
        if not _is_monthly(child.billing_plan) or child.weekly_rate is not None:
            continue
        if child.billing_amount is None:
            continue
        weekly = (child.billing_amount / FOUR).quantize(MONEY, rounding=ROUND_HALF_UP)
        child.weekly_rate = weekly
        child.billing_amount = weekly
        child.save(update_fields=["weekly_rate", "billing_amount"])
    for row in Plan.objects.all():
        if not _is_monthly(row.billing_plan) or row.weekly_rate is not None:
            continue
        if row.billing_amount is None:
            continue
        weekly = (row.billing_amount / FOUR).quantize(MONEY, rounding=ROUND_HALF_UP)
        row.weekly_rate = weekly
        row.billing_amount = weekly
        row.save(update_fields=["weekly_rate", "billing_amount"])


def noop_reverse(apps, schema_editor):
    return None


class Migration(migrations.Migration):

    dependencies = [
        ("portal", "0038_portal_admin_django_superuser"),
    ]

    operations = [
        migrations.AddField(
            model_name="portalchild",
            name="weekly_rate",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True),
        ),
        migrations.AddField(
            model_name="portalchildbillingplan",
            name="weekly_rate",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True),
        ),
        migrations.RunPython(backfill_weekly_rate, noop_reverse),
    ]
