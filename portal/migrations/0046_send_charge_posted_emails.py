from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("portal", "0045_attendance_record_care"),
    ]

    operations = [
        migrations.AddField(
            model_name="portalorgsetting",
            name="send_charge_posted_emails",
            field=models.BooleanField(
                default=False,
                help_text=(
                    "When on, parents get an automatic email every time a charge is posted "
                    "(weekly plans, 4Cs copay, bulk Post today, and staff charges). Off until "
                    "those emails show trustworthy amounts. Staff Email parent and Send updated "
                    "balance still work."
                ),
            ),
        ),
    ]
