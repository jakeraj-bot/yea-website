from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("portal", "0020_merge_agency_weeks_and_child_unit"),
    ]

    operations = [
        migrations.AddField(
            model_name="portalpayment",
            name="stripe_payout_id",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name="portalpayment",
            name="stripe_payout_descriptor",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name="portalpayment",
            name="stripe_payout_amount",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True),
        ),
    ]
