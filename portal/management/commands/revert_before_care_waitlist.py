from django.core.management.base import BaseCommand

from enrollment.application_review import revert_approved_before_care_to_waitlist
from portal.agency_services import purge_demo_agency_members


class Command(BaseCommand):
    help = (
        "Move approved before-care applications back to the waitlist, and remove "
        "seeded Sofia Martinez / Ethan Chen 4Cs demo profiles."
    )

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        from enrollment.models import EnrollmentApplication
        from portal.models import PortalAgencyProfile

        dry_run = options["dry_run"]
        before_care = EnrollmentApplication.objects.filter(
            program="before_care",
            status__in=("approved", "enrolled"),
        )
        self.stdout.write(f"Approved before-care applications: {before_care.count()}")
        for app in before_care:
            self.stdout.write(
                f"  {app.student_first_name} {app.student_last_name} ({app.get_status_display()})"
            )

        if dry_run:
            self.stdout.write("Dry run — no changes saved.")
            return

        reverted = revert_approved_before_care_to_waitlist()
        profiles, families = purge_demo_agency_members()
        leftover = PortalAgencyProfile.objects.filter(
            auth_number__in=("4CS-2026-8841", "4CS-2026-9012")
        ).count()
        self.stdout.write(
            self.style.SUCCESS(
                f"Moved {reverted} before-care application(s) to the waitlist. "
                f"Removed {profiles} demo 4Cs profile(s) and {families} leftover demo family(ies). "
                f"Demo auth numbers remaining: {leftover}."
            )
        )
