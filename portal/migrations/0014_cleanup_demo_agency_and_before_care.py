from django.db import migrations

DEMO_AGENCY_AUTH_NUMBERS = {"4CS-DEMO-001", "4CS-DEMO-002"}
DEMO_AGENCY_CHILDREN = {("martinez", "sofia martinez"), ("chen", "ethan chen")}


def apply_cleanup(apps, schema_editor):
    from enrollment.application_review import revert_approved_before_care_to_waitlist

    revert_approved_before_care_to_waitlist()

    PortalAgencyProfile = apps.get_model("portal", "PortalAgencyProfile")
    PortalFamily = apps.get_model("portal", "PortalFamily")
    for profile in PortalAgencyProfile.objects.select_related("child", "family"):
        slug = (profile.family.slug or "").lower()
        child_name = (profile.child.name or "").strip().lower()
        if profile.auth_number in DEMO_AGENCY_AUTH_NUMBERS or (slug, child_name) in DEMO_AGENCY_CHILDREN:
            profile.delete()

    demo_slugs = {slug for slug, _name in DEMO_AGENCY_CHILDREN}
    for family in PortalFamily.objects.filter(slug__in=demo_slugs):
        has_real_app = family.enrollment_applications.exists()
        kids = list(family.children.all())
        only_demo_kids = kids and all(
            (family.slug.lower(), kid.name.strip().lower()) in DEMO_AGENCY_CHILDREN for kid in kids
        )
        if has_real_app and not only_demo_kids:
            continue
        if has_real_app:
            if family.billing_type == "4Cs":
                family.billing_type = "Private pay"
                family.save(update_fields=["billing_type"])
            continue
        family.delete()


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
