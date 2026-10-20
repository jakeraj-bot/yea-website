from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("portal", "0044_rewrite_oct15_charge_descriptions"),
    ]

    operations = [
        migrations.AddField(
            model_name="attendancerecord",
            name="care",
            field=models.CharField(
                blank=True,
                choices=[
                    ("", "After-care"),
                    ("after", "After-care"),
                    ("before", "Before-care"),
                ],
                db_index=True,
                default="",
                max_length=16,
            ),
        ),
        migrations.AlterUniqueTogether(
            name="attendancerecord",
            unique_together={("child", "program", "date", "care")},
        ),
    ]
