from django.db import migrations


OLD_PAY_SNIPPETS = (
    "You can review and pay now in the parent portal:\n{portal_url}",
    "You can review and pay in the parent portal:\n{portal_url}",
)

NEW_PAY_SNIPPET = "You can pay in the parent portal. Pay now:\n{payment_url}"


def upgrade_pay_now_links(apps, schema_editor):
    Template = apps.get_model("portal", "PortalEmailTemplate")
    for key in ("charge_notice", "balance_updated"):
        row = Template.objects.filter(key=key).first()
        if not row:
            continue
        body = row.body or ""
        updated = body
        for old in OLD_PAY_SNIPPETS:
            if old in updated:
                updated = updated.replace(old, NEW_PAY_SNIPPET)
        if "{payment_url}" not in updated and "/portal/parent/payment/" not in updated:
            block = f"\n\n{NEW_PAY_SNIPPET}\n"
            marker = "Youth Education Academy"
            idx = updated.rfind(marker)
            if idx >= 0:
                updated = updated[:idx].rstrip() + block + "\n" + updated[idx:]
            else:
                updated = updated.rstrip() + block
        if updated != body:
            row.body = updated
            row.save(update_fields=["body"])


class Migration(migrations.Migration):

    dependencies = [
        ("portal", "0034_practice_parent"),
    ]

    operations = [
        migrations.RunPython(upgrade_pay_now_links, migrations.RunPython.noop),
    ]
