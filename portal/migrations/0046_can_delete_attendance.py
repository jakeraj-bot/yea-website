from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("portal", "0045_attendance_record_care"),
    ]

    operations = [
        migrations.AddField(
            model_name="portalbillingdefaultrule",
            name="can_delete_attendance",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="portalstaffaccount",
            name="can_delete_attendance",
            field=models.BooleanField(
                default=False,
                help_text="Allow this person to delete a mistaken attendance mark. Portal admin can always delete attendance.",
            ),
        ),
    ]
