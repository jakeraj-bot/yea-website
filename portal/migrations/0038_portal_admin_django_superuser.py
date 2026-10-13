from django.db import migrations


PORTAL_ADMIN = "Portal admin"
EXCLUDED_ROLES = {"Program director", "Front desk staff", "Front desk"}


def grant_portal_admins_django_backend(apps, schema_editor):
    Account = apps.get_model("portal", "PortalStaffAccount")
    for account in Account.objects.filter(is_active=True).select_related("user"):
        if account.role in EXCLUDED_ROLES:
            continue
        if account.role != PORTAL_ADMIN and not account.all_units_access:
            continue
        user = account.user
        if user.is_staff and user.is_superuser:
            continue
        user.is_staff = True
        user.is_superuser = True
        user.save(update_fields=["is_staff", "is_superuser"])


def noop_reverse(apps, schema_editor):
    return None


class Migration(migrations.Migration):

    dependencies = [
        ("portal", "0037_approve_plan_email_placeholders"),
    ]

    operations = [
        migrations.RunPython(grant_portal_admins_django_backend, noop_reverse),
    ]
