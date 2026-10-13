from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("portal", "0033_family_staff_notes"),
    ]

    operations = [
        migrations.AddField(
            model_name="portalorgsetting",
            name="practice_parent_enabled",
            field=models.BooleanField(
                default=False,
                help_text="Show Open practice parent. Off on production unless an admin turns this on.",
            ),
        ),
    ]
