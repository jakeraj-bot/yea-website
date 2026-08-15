from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("portal", "0009_child_auto_charge"),
    ]

    operations = [
        migrations.AddField(
            model_name="portalpayment",
            name="stripe_payment_intent_id",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name="portalpayment",
            name="refunded_amount",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=10),
        ),
    ]
