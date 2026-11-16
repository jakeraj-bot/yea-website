from django.db import migrations, models
from django.db.models import Q


def grant_existing_editors(apps, schema_editor):
    PortalStaffAccount = apps.get_model("portal", "PortalStaffAccount")
    PortalBillingDefaultRule = apps.get_model("portal", "PortalBillingDefaultRule")
    PortalStaffAccount.objects.filter(
        Q(role="Portal admin") | Q(role="Program director") | Q(all_units_access=True)
    ).update(can_edit_applications=True)
    PortalBillingDefaultRule.objects.filter(
        role_name__in=["Portal admin", "Program director"]
    ).update(can_edit_applications=True)


class Migration(migrations.Migration):
    dependencies = [
        ("portal", "0048_agency_profile_multiple_contracts"),
    ]

    operations = [
        migrations.AddField(
            model_name="portalbillingdefaultrule",
            name="can_edit_applications",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="portalstaffaccount",
            name="can_edit_applications",
            field=models.BooleanField(
                default=False,
                help_text="Allow this person to edit a family's application (names, school, contacts, program). Portal admin can always edit applications.",
            ),
        ),
        migrations.RunPython(grant_existing_editors, migrations.RunPython.noop),
    ]
