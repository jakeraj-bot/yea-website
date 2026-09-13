from datetime import datetime, timedelta

from django.db import migrations, models


def backfill_end_time(apps, schema_editor):
    Activity = apps.get_model("portal", "PortalCalendarActivity")
    for activity in Activity.objects.filter(end_time__isnull=True).iterator():
        if not activity.start_time:
            continue
        activity.end_time = (datetime.combine(activity.activity_date, activity.start_time) + timedelta(hours=1)).time()
        activity.save(update_fields=["end_time"])


class Migration(migrations.Migration):

    dependencies = [
        ("portal", "0028_merge_calendar_and_child_billing"),
    ]

    operations = [
        migrations.AddField(
            model_name="portalcalendaractivity",
            name="end_time",
            field=models.TimeField(blank=True, null=True),
        ),
        migrations.RunPython(backfill_end_time, migrations.RunPython.noop),
    ]
