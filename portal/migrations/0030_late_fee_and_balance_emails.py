from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("portal", "0029_calendar_activity_end_time"),
    ]

    operations = [
        migrations.AlterField(
            model_name="portalemailtemplate",
            name="key",
            field=models.SlugField(
                choices=[
                    ("staff_welcome", "Staff / admin welcome"),
                    ("charge_notice", "Charge posted"),
                    ("first_day_reminder", "First-day payment reminder"),
                    ("balance_updated", "Balance updated"),
                    ("late_payment", "Late payment reminder"),
                ],
                unique=True,
            ),
        ),
        migrations.CreateModel(
            name="PortalLateFeeSetting",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("amount", models.DecimalField(decimal_places=2, default=15, max_digits=10)),
                ("notify_on_charge_change", models.BooleanField(default=True)),
            ],
        ),
    ]
