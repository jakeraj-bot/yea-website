from django.db import migrations, models
import django.db.models.deletion


def copy_family_unit_to_children(apps, schema_editor):
    PortalChild = apps.get_model("portal", "PortalChild")
    for child in PortalChild.objects.select_related("family").all():
        family_unit_id = getattr(child.family, "unit_id", None)
        if family_unit_id and child.unit_id != family_unit_id:
            child.unit_id = family_unit_id
            child.save(update_fields=["unit_id"])


class Migration(migrations.Migration):

    dependencies = [
        ("portal", "0018_email_templates"),
    ]

    operations = [
        migrations.AddField(
            model_name="portalchild",
            name="unit",
            field=models.ForeignKey(
                blank=True,
                help_text="Program site this child attends. One family account can have children in different units.",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="enrolled_children",
                to="portal.portalunit",
            ),
        ),
        migrations.RunPython(copy_family_unit_to_children, migrations.RunPython.noop),
    ]
