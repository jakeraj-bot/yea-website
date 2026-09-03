from django.db import migrations


def apply_cleanup(apps, schema_editor):
    from enrollment.application_review import revert_approved_before_care_to_waitlist
    from portal.agency_services import purge_demo_agency_members

    revert_approved_before_care_to_waitlist()
    purge_demo_agency_members()


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("portal", "0013_member_ops"),
        ("enrollment", "0005_application_review_fields"),
    ]

    operations = [
        migrations.RunPython(apply_cleanup, noop),
    ]
