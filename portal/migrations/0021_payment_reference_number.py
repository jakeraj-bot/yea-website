from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("portal", "0020_merge_agency_weeks_and_child_unit"),
    ]

    operations = [
        migrations.AddField(
            model_name="portalledgerentry",
            name="reference_number",
            field=models.CharField(blank=True, max_length=64),
        ),
        migrations.AddField(
            model_name="portalpayment",
            name="reference_number",
            field=models.CharField(blank=True, max_length=64),
        ),
    ]
