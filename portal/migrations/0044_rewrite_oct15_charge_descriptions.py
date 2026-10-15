from datetime import date

from django.db import migrations


def rewrite_oct15_descriptions(apps, schema_editor):
    from portal.billing_services import rewrite_auto_charge_descriptions

    rewrite_auto_charge_descriptions(on_date=date(2026, 10, 15))


def noop_reverse(apps, schema_editor):
    return None


class Migration(migrations.Migration):
    dependencies = [
        ("portal", "0043_program_months"),
    ]

    operations = [
        migrations.RunPython(rewrite_oct15_descriptions, noop_reverse),
    ]
