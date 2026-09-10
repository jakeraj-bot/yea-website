from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("portal", "0022_payment_stripe_payout_id"),
    ]

    operations = [
        migrations.AddField(
            model_name="portalledgerentry",
            name="fee_amount",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=10),
        ),
    ]
