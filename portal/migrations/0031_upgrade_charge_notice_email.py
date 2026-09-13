from django.db import migrations

OLD_CHARGE_BODY = (
    "Hello {family_name},\n\n"
    "A charge has been posted to your account:\n\n"
    "Child: {child_name}\n"
    "Description: {description}\n"
    "Amount: ${amount}\n"
    "Date: {date}\n\n"
    "Your current balance is ${balance}.\n\n"
    "You can review and pay in the parent portal:\n"
    "{portal_url}\n\n"
    "Youth Education Academy\n"
)

NEW_CHARGE_BODY = (
    "Hello {family_name},\n\n"
    "A charge has been posted to your account.\n\n"
    "What you owe for: {owe_for}\n"
    "Child: {child_name}\n"
    "Week: {week}\n"
    "This charge: ${amount}\n"
    "Date: {date}\n\n"
    "Current balance for {child_name}: ${child_balance}\n"
    "Family balance (what the household owes): ${family_balance}\n\n"
    "You can review and pay in the parent portal:\n"
    "{portal_url}\n\n"
    "Youth Education Academy\n"
)


def upgrade_charge_notice(apps, schema_editor):
    Template = apps.get_model("portal", "PortalEmailTemplate")
    row = Template.objects.filter(key="charge_notice").first()
    if not row:
        return
    if (row.body or "").strip() == OLD_CHARGE_BODY.strip():
        row.body = NEW_CHARGE_BODY
        row.save(update_fields=["body"])


class Migration(migrations.Migration):

    dependencies = [
        ("portal", "0030_late_fee_and_balance_emails"),
    ]

    operations = [
        migrations.RunPython(upgrade_charge_notice, migrations.RunPython.noop),
    ]
