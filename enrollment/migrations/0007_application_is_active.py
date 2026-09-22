from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("enrollment", "0006_member_start_date"),
    ]

    operations = [
        migrations.AddField(
            model_name="enrollmentapplication",
            name="is_active",
            field=models.BooleanField(
                default=True,
                help_text="When off, this program application is inactive. The child can stay active in another program.",
            ),
        ),
    ]
