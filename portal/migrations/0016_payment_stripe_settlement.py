from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("portal", "0015_support_view_session"),
    ]

    operations = [
        migrations.AddField(
            model_name="portalpayment",
            name="stripe_charge_id",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name="portalpayment",
            name="stripe_bank_status",
            field=models.CharField(blank=True, max_length=64),
        ),
        migrations.AddField(
            model_name="portalpayment",
            name="stripe_bank_date",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="portalpayment",
            name="stripe_settlement_checked_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
