from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("enrollment", "0005_application_review_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="enrollmentapplication",
            name="member_start_date",
            field=models.DateField(
                blank=True,
                help_text="Date this child can start. Entered when staff approve the application.",
                null=True,
            ),
        ),
    ]
