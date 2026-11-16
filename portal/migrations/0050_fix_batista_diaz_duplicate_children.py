from django.db import migrations


def collapse_batista_diaz_children(apps, schema_editor):
    from portal.family_merge import fix_batista_diaz_duplicate_children

    fix_batista_diaz_duplicate_children()


def noop_reverse(apps, schema_editor):
    return None


class Migration(migrations.Migration):
    dependencies = [
        ("portal", "0049_can_edit_applications"),
    ]

    operations = [
        migrations.RunPython(collapse_batista_diaz_children, noop_reverse),
    ]
