from django.db import migrations, models


def seed_program_director_role(apps, schema_editor):
    PortalStaffRole = apps.get_model("portal", "PortalStaffRole")
    PortalBillingDefaultRule = apps.get_model("portal", "PortalBillingDefaultRule")
    PortalOrgSetting = apps.get_model("portal", "PortalOrgSetting")
    PortalStaffRole.objects.update_or_create(name="Program director", defaults={"is_system": True})
    PortalStaffRole.objects.update_or_create(name="Front desk staff", defaults={"is_system": True})
    PortalBillingDefaultRule.objects.get_or_create(
        role_name="Program director",
        defaults={
            "can_add_charge": False,
            "can_delete_charge": False,
            "can_add_credit": False,
            "can_edit_family_plans": False,
            "can_approve_applications": True,
            "can_approve_waitlist": True,
            "is_custom": False,
        },
    )
    PortalBillingDefaultRule.objects.get_or_create(
        role_name="Front desk staff",
        defaults={
            "can_add_charge": True,
            "can_delete_charge": False,
            "can_add_credit": True,
            "can_edit_family_plans": True,
            "can_approve_applications": True,
            "can_approve_waitlist": True,
            "is_custom": False,
        },
    )
    PortalOrgSetting.objects.get_or_create(pk=1, defaults={"program_director_can_see_billing": False})


class Migration(migrations.Migration):

    dependencies = [
        ("portal", "0029_calendar_activity_end_time"),
    ]

    operations = [
        migrations.AddField(
            model_name="portalstaffaccount",
            name="can_see_billing",
            field=models.BooleanField(
                default=False,
                help_text="When this person is a Program director, allow billing even if the org toggle is off.",
            ),
        ),
        migrations.CreateModel(
            name="PortalOrgSetting",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("program_director_can_see_billing", models.BooleanField(default=False)),
            ],
            options={
                "verbose_name": "Portal organization setting",
            },
        ),
        migrations.CreateModel(
            name="PortalOutsideProgram",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=180)),
                ("email", models.EmailField(blank=True, max_length=254)),
                ("phone", models.CharField(blank=True, max_length=40)),
                ("description", models.TextField(blank=True, help_text="What they will be doing.")),
                (
                    "charge_amount",
                    models.DecimalField(
                        blank=True,
                        decimal_places=2,
                        help_text="How much they want to charge YEA.",
                        max_digits=10,
                        null=True,
                    ),
                ),
                ("notes", models.TextField(blank=True)),
                (
                    "category",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("vendor", "Vendor"),
                            ("partner", "Partner"),
                            ("contractor", "Contractor"),
                            ("other", "Other"),
                        ],
                        default="vendor",
                        max_length=32,
                    ),
                ),
                ("last_used_on", models.DateField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "ordering": ["name"],
            },
        ),
        migrations.RunPython(seed_program_director_role, migrations.RunPython.noop),
    ]
