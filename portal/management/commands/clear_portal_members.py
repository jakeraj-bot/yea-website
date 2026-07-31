from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from portal.models import (
    AttendanceRecord,
    MessageThread,
    PortalAgencyProfile,
    PortalAgencyRemittance,
    PortalChild,
    PortalFamily,
    PortalIncident,
    PortalLedgerEntry,
    PortalParentAccount,
    PortalPayment,
    PortalPolicySignatureRequest,
    PortalProfileChangeRequest,
    PortalScholarshipAssignment,
    PortalStaffAccount,
    SupportTicket,
)


class Command(BaseCommand):
    help = (
        "Remove member/family data for a fresh partner staging start. "
        "Keeps portal admin, units, org settings, and fee rules."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--include-staff",
            action="store_true",
            help="Also remove non-admin staff portal accounts.",
        )
        parser.add_argument(
            "--yes",
            action="store_true",
            help="Skip confirmation prompt (for deploy scripts).",
        )

    def handle(self, *args, **options):
        if not options["yes"]:
            self.stdout.write(
                "This deletes all families, parent accounts, children, enrollment links, "
                "attendance, billing entries, and related member data."
            )
            confirm = input("Type CLEAR to continue: ")
            if confirm.strip() != "CLEAR":
                self.stdout.write(self.style.WARNING("Cancelled."))
                return

        with transaction.atomic():
            counts = self._clear_members(include_staff=options["include_staff"])

        self.stdout.write(self.style.SUCCESS("Member data cleared:"))
        for label, count in counts.items():
            if count:
                self.stdout.write(f"  {label}: {count}")

    def _clear_members(self, include_staff=False):
        from enrollment.models import EnrollmentApplication

        User = get_user_model()
        counts = {}

        parent_user_ids = list(PortalParentAccount.objects.values_list("user_id", flat=True))
        counts["parent accounts"] = PortalParentAccount.objects.count()
        PortalParentAccount.objects.all().delete()

        counts["profile change requests"] = PortalProfileChangeRequest.objects.count()
        PortalProfileChangeRequest.objects.all().delete()

        counts["enrollment applications"] = EnrollmentApplication.objects.count()
        EnrollmentApplication.objects.all().delete()

        counts["policy signature requests"] = PortalPolicySignatureRequest.objects.count()
        PortalPolicySignatureRequest.objects.all().delete()

        counts["scholarship assignments"] = PortalScholarshipAssignment.objects.count()
        PortalScholarshipAssignment.objects.all().delete()

        counts["agency profiles"] = PortalAgencyProfile.objects.count()
        PortalAgencyProfile.objects.all().delete()

        counts["agency remittances"] = PortalAgencyRemittance.objects.count()
        PortalAgencyRemittance.objects.all().delete()

        counts["payments"] = PortalPayment.objects.count()
        PortalPayment.objects.all().delete()

        counts["ledger entries"] = PortalLedgerEntry.objects.count()
        PortalLedgerEntry.objects.all().delete()

        counts["attendance records"] = AttendanceRecord.objects.count()
        AttendanceRecord.objects.all().delete()

        counts["incidents"] = PortalIncident.objects.count()
        PortalIncident.objects.all().delete()

        counts["support tickets"] = SupportTicket.objects.count()
        SupportTicket.objects.all().delete()

        counts["message threads"] = MessageThread.objects.count()
        MessageThread.objects.all().delete()

        counts["families"] = PortalFamily.objects.count()
        PortalFamily.objects.all().delete()

        if include_staff:
            staff_user_ids = list(
                PortalStaffAccount.objects.exclude(role="Portal admin").values_list("user_id", flat=True)
            )
            counts["staff accounts"] = PortalStaffAccount.objects.exclude(role="Portal admin").count()
            PortalStaffAccount.objects.exclude(role="Portal admin").delete()
            deleted_users, _ = User.objects.filter(id__in=staff_user_ids).delete()
            counts["staff users removed"] = deleted_users

        deleted_parent_users, _ = User.objects.filter(id__in=parent_user_ids).delete()
        counts["parent users removed"] = deleted_parent_users

        demo_usernames = ["jakeraj", "mmartinez", "dwilliams", "staff18"]
        demo_deleted, _ = User.objects.filter(username__in=demo_usernames).exclude(
            portalstaffaccount__role="Portal admin"
        ).delete()
        counts["demo login users removed"] = demo_deleted

        return counts
