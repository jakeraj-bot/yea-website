from django.db import migrations, models


APPLICATION_TEMPLATES = {
    "application_submitted": {
        "name": "Application submitted",
        "subject": "[YEA] Application received — {child_name}",
        "body": (
            "Hello {parent_name},\n\n"
            "Thank you for submitting your enrollment application for {child_name}.\n\n"
            "Reference: {reference}\n"
            "Program: {program} — {unit}\n\n"
            "We'll review your application and contact you if we need anything else. "
            "Track status anytime in the parent portal:\n"
            "{portal_url}\n\n"
            "Youth Education Academy\n"
        ),
    },
    "application_submitted_waitlist": {
        "name": "Waitlist application submitted",
        "subject": "[YEA] You're on the before care waitlist — {child_name}",
        "body": (
            "Hello {parent_name},\n\n"
            "Thank you for joining the before care waitlist at {unit} for {child_name}.\n\n"
            "Reference: {reference}\n"
            "Program: {program} — {unit}\n\n"
            "Families on the waitlist are contacted in the order requests were received when a spot opens. "
            "Track status anytime in the parent portal:\n"
            "{portal_url}\n\n"
            "Youth Education Academy\n"
        ),
    },
    "application_approved": {
        "name": "Application approved",
        "subject": "Enrollment approved — {child_name}",
        "body": (
            "Hi {parent_name},\n\n"
            "Great news — {child_name}'s enrollment application for {program} "
            "at {unit} has been approved. They are on the active roster.\n\n"
            "{child_name} can start on {start_date}. Payment is due before the program start. "
            "You can pay in the parent portal.\n\n"
            "Pay now (this link opens your payment page after you sign in):\n"
            "{payment_url}\n\n"
            "{payment_steps}\n\n"
            "Youth Education Academy\n"
        ),
    },
    "application_approved_waitlist": {
        "name": "Waitlist application approved",
        "subject": "Waitlist approved — {child_name} can start {start_date}",
        "body": (
            "Hi {parent_name},\n\n"
            "A spot opened — {child_name}'s waitlist request for {program} "
            "at {unit} has been approved. They are on the active roster.\n\n"
            "{child_name} can start on {start_date}. Payment is due before the program start. "
            "You can pay in the parent portal.\n\n"
            "Pay now (this link opens your payment page after you sign in):\n"
            "{payment_url}\n\n"
            "{payment_steps}\n\n"
            "Youth Education Academy\n"
        ),
    },
}

KEY_CHOICES = [
    ("staff_welcome", "Staff / admin welcome"),
    ("charge_notice", "Charge posted"),
    ("first_day_reminder", "First-day payment reminder"),
    ("balance_updated", "Balance updated"),
    ("late_payment", "Late payment reminder"),
    ("application_submitted", "Application submitted"),
    ("application_submitted_waitlist", "Waitlist application submitted"),
    ("application_approved", "Application approved"),
    ("application_approved_waitlist", "Waitlist application approved"),
]


def seed_application_templates(apps, schema_editor):
    Template = apps.get_model("portal", "PortalEmailTemplate")
    for key, defaults in APPLICATION_TEMPLATES.items():
        Template.objects.get_or_create(key=key, defaults=defaults)


class Migration(migrations.Migration):

    dependencies = [
        ("portal", "0035_pay_now_email_links"),
    ]

    operations = [
        migrations.AlterField(
            model_name="portalemailtemplate",
            name="key",
            field=models.SlugField(choices=KEY_CHOICES, unique=True),
        ),
        migrations.RunPython(seed_application_templates, migrations.RunPython.noop),
    ]
