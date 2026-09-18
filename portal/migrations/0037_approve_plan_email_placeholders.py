from django.db import migrations


APPROVED_KEYS = ("application_approved", "application_approved_waitlist")

NEW_BODIES = {
    "application_approved": (
        "Hi {parent_name},\n\n"
        "Great news — {child_name}'s enrollment application for {program} "
        "at {unit} has been approved. They are on the active roster.\n\n"
        "{child_name} can start on {start_date}. Payment is due before the program start. "
        "You can pay in the parent portal.\n\n"
        "{amount_due}\n"
        "{membership_fee}\n"
        "{four_cs_contract}\n\n"
        "Pay now (this link opens your payment page after you sign in):\n"
        "{payment_url}\n\n"
        "{payment_steps}\n\n"
        "Youth Education Academy\n"
    ),
    "application_approved_waitlist": (
        "Hi {parent_name},\n\n"
        "A spot opened — {child_name}'s waitlist request for {program} "
        "at {unit} has been approved. They are on the active roster.\n\n"
        "{child_name} can start on {start_date}. Payment is due before the program start. "
        "You can pay in the parent portal.\n\n"
        "{amount_due}\n"
        "{membership_fee}\n"
        "{four_cs_contract}\n\n"
        "Pay now (this link opens your payment page after you sign in):\n"
        "{payment_url}\n\n"
        "{payment_steps}\n\n"
        "Youth Education Academy\n"
    ),
}

PLACEHOLDER_BLOCK = (
    "{amount_due}\n"
    "{membership_fee}\n"
    "{four_cs_contract}\n"
)


def add_approve_plan_placeholders(apps, schema_editor):
    Template = apps.get_model("portal", "PortalEmailTemplate")
    for key in APPROVED_KEYS:
        template = Template.objects.filter(key=key).first()
        if not template:
            Template.objects.create(
                key=key,
                name="Application approved" if key == "application_approved" else "Waitlist application approved",
                subject=(
                    "Enrollment approved — {child_name}"
                    if key == "application_approved"
                    else "Waitlist approved — {child_name} can start {start_date}"
                ),
                body=NEW_BODIES[key],
                is_enabled=True,
            )
            continue
        body = template.body or ""
        if "{amount_due}" in body and "{membership_fee}" in body and "{four_cs_contract}" in body:
            continue
        marker = "Pay now (this link opens your payment page after you sign in):"
        if marker in body:
            template.body = body.replace(marker, PLACEHOLDER_BLOCK + "\n" + marker, 1)
        else:
            insert_at = body.rfind("Youth Education Academy")
            block = "\n" + PLACEHOLDER_BLOCK + "\n"
            if insert_at >= 0:
                template.body = body[:insert_at].rstrip() + "\n" + block + body[insert_at:]
            else:
                template.body = NEW_BODIES[key]
        template.save(update_fields=["body", "updated_at"])


def noop_reverse(apps, schema_editor):
    return None


class Migration(migrations.Migration):

    dependencies = [
        ("portal", "0036_application_email_templates"),
    ]

    operations = [
        migrations.RunPython(add_approve_plan_placeholders, noop_reverse),
    ]
