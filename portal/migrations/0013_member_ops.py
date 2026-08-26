from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("portal", "0012_application_approval_permissions"),
    ]

    operations = [
        migrations.AddField(
            model_name="portalfamily",
            name="is_suspended",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="portalfamily",
            name="suspend_reason",
            field=models.CharField(blank=True, max_length=64),
        ),
        migrations.AddField(
            model_name="portalfamily",
            name="suspend_note",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="portalfamily",
            name="suspended_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="portalchild",
            name="school",
            field=models.CharField(blank=True, max_length=120),
        ),
        migrations.CreateModel(
            name="PortalPriorBalance",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=160)),
                ("child_name", models.CharField(blank=True, max_length=120)),
                ("amount", models.DecimalField(decimal_places=2, max_digits=10)),
                ("notes", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("linked_at", models.DateTimeField(blank=True, null=True)),
                (
                    "linked_family",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="prior_balances",
                        to="portal.portalfamily",
                    ),
                ),
            ],
            options={"ordering": ["name"]},
        ),
        migrations.CreateModel(
            name="PortalDiscountPlan",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=120)),
                (
                    "kind",
                    models.CharField(
                        choices=[("amount", "Fixed amount"), ("percent", "Percent")],
                        default="amount",
                        max_length=16,
                    ),
                ),
                ("value", models.DecimalField(decimal_places=2, max_digits=10)),
                ("description", models.TextField(blank=True)),
                ("is_active", models.BooleanField(default=True)),
            ],
            options={"ordering": ["name"]},
        ),
        migrations.CreateModel(
            name="PortalDiscountAssignment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("child_name", models.CharField(blank=True, max_length=120)),
                ("notes", models.CharField(blank=True, max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("is_active", models.BooleanField(default=True)),
                (
                    "family",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="discount_assignments",
                        to="portal.portalfamily",
                    ),
                ),
                (
                    "plan",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="assignments",
                        to="portal.portaldiscountplan",
                    ),
                ),
            ],
            options={"ordering": ["-created_at"]},
        ),
    ]
