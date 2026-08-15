from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("portal", "0008_admin_config"),
    ]

    operations = [
        migrations.AddField(
            model_name="portalchild",
            name="auto_charge",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="portalchild",
            name="next_charge_date",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="portalchild",
            name="last_auto_charge_date",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="portalchild",
            name="charge_weekday",
            field=models.PositiveSmallIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="portalchild",
            name="charge_month_day",
            field=models.PositiveSmallIntegerField(blank=True, null=True),
        ),
    ]
