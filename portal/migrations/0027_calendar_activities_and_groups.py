from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("portal", "0026_portal_activity_event"),
    ]

    operations = [
        migrations.CreateModel(
            name="PortalCalendarActivity",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=160)),
                ("activity_date", models.DateField()),
                ("start_time", models.TimeField()),
                ("series_id", models.UUIDField(blank=True, db_index=True, null=True)),
                ("lesson_plan", models.FileField(blank=True, upload_to="portal/activity-lesson-plans/%Y/%m/")),
                ("lesson_plan_name", models.CharField(blank=True, max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="created_calendar_activities",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "unit",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="calendar_activities",
                        to="portal.portalunit",
                    ),
                ),
            ],
            options={
                "ordering": ["activity_date", "start_time", "name"],
            },
        ),
        migrations.CreateModel(
            name="PortalMemberGroup",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=160)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="created_member_groups",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "unit",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="member_groups",
                        to="portal.portalunit",
                    ),
                ),
            ],
            options={
                "ordering": ["name"],
            },
        ),
        migrations.CreateModel(
            name="PortalCalendarActivityMember",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("added_at", models.DateTimeField(auto_now_add=True)),
                (
                    "activity",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="memberships",
                        to="portal.portalcalendaractivity",
                    ),
                ),
                (
                    "added_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="added_calendar_activity_members",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "child",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="calendar_activity_memberships",
                        to="portal.portalchild",
                    ),
                ),
            ],
            options={
                "ordering": ["child__name"],
                "unique_together": {("activity", "child")},
            },
        ),
        migrations.CreateModel(
            name="PortalMemberGroupMember",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("added_at", models.DateTimeField(auto_now_add=True)),
                (
                    "added_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="added_member_group_members",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "child",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="group_memberships",
                        to="portal.portalchild",
                    ),
                ),
                (
                    "group",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="memberships",
                        to="portal.portalmembergroup",
                    ),
                ),
            ],
            options={
                "ordering": ["child__name"],
                "unique_together": {("group", "child")},
            },
        ),
        migrations.AddField(
            model_name="portalcalendaractivity",
            name="members",
            field=models.ManyToManyField(
                blank=True,
                related_name="calendar_activities",
                through="portal.PortalCalendarActivityMember",
                to="portal.portalchild",
            ),
        ),
        migrations.AddField(
            model_name="portalmembergroup",
            name="members",
            field=models.ManyToManyField(
                blank=True,
                related_name="member_groups",
                through="portal.PortalMemberGroupMember",
                to="portal.portalchild",
            ),
        ),
    ]
