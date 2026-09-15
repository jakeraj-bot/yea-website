from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("portal", "0033_family_staff_notes"),
    ]

    operations = [
        migrations.AddField(
            model_name="portalorgsetting",
            name="portal_sending_email",
            field=models.EmailField(
                blank=True,
                help_text="From address for automated portal mail. Leave blank to keep the current server default.",
                max_length=254,
            ),
        ),
        migrations.AddField(
            model_name="portalorgsetting",
            name="portal_bcc_email",
            field=models.EmailField(
                blank=True,
                help_text="Always BCC this address on mail to parents. Leave blank to use the portal sending email.",
                max_length=254,
            ),
        ),
    ]
