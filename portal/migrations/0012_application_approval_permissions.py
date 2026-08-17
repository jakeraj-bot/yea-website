from django.db import migrations, models


def grant_portal_admin_defaults(apps, schema_editor):
    Rule = apps.get_model("portal", "PortalBillingDefaultRule")
    Rule.objects.filter(role_name="Portal admin").update(
        can_approve_applications=True,
        can_approve_waitlist=True,
    )


class Migration(migrations.Migration):

    dependencies = [
        ("portal", "0011_field_trips"),
    ]

    operations = [
        migrations.AddField(
            model_name="portalbillingdefaultrule",
            name="can_approve_applications",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="portalbillingdefaultrule",
            name="can_approve_waitlist",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="portalstaffaccount",
            name="can_approve_applications",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="portalstaffaccount",
            name="can_approve_waitlist",
            field=models.BooleanField(default=False),
        ),
        migrations.RunPython(grant_portal_admin_defaults, migrations.RunPython.noop),
    ]
