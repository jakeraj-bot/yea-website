from datetime import datetime
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from django.utils.dateparse import parse_date, parse_time

from portal.demo_data import AGENCY_UNIT_DATA, ATTENDANCE_ROSTER, ATTENDANCE_SESSION, FAMILIES, UNITS
from portal.models import (
    AttendanceRecord,
    PortalAgencyProfile,
    PortalChild,
    PortalFamily,
    PortalProgram,
    PortalUnit,
)


class Command(BaseCommand):
    help = "Load sample portal members and attendance from demo data. Local/design only."

    def handle(self, *args, **options):
        from django.conf import settings

        if not getattr(settings, "ALLOW_PORTAL_DEMO_SEED", False):
            raise CommandError(
                "Refusing to load demo families on this environment. "
                "Set ALLOW_PORTAL_DEMO_SEED=True only on a local design machine — never on yeanj.org."
            )
        unit_data = next((u for u in UNITS if u["slug"] == "school-18"), UNITS[0])
        unit, _ = PortalUnit.objects.update_or_create(
            slug=unit_data["slug"],
            defaults={"name": unit_data["name"], "is_active": True},
        )

        for extra_unit in UNITS:
            if extra_unit["slug"] == unit_data["slug"]:
                continue
            PortalUnit.objects.update_or_create(
                slug=extra_unit["slug"],
                defaults={"name": extra_unit["name"], "is_active": extra_unit.get("active", True)},
            )

        program, _ = PortalProgram.objects.update_or_create(
            unit=unit,
            name=ATTENDANCE_SESSION["program"],
            defaults={
                "start_time": parse_time(ATTENDANCE_SESSION["program_start_time"]),
                "end_time": parse_time(ATTENDANCE_SESSION["program_end_time"]),
                "is_active": True,
            },
        )

        roster_by_name = {row["child"]: row for row in ATTENDANCE_ROSTER}
        family_by_name = {row["name"]: row for row in FAMILIES}

        for family_data in FAMILIES:
            family, _ = PortalFamily.objects.update_or_create(
                unit=unit,
                slug=family_data["slug"],
                defaults={
                    "name": family_data["name"],
                    "primary_contact": family_data.get("primary_contact", ""),
                    "balance": Decimal(family_data.get("balance", "0") or "0"),
                    "billing_type": family_data.get("billing_type", ""),
                    "program_label": family_data.get("program", ""),
                    "status": family_data.get("status", "Active"),
                },
            )
            for child_name in family_data.get("children", []):
                roster_row = roster_by_name.get(child_name, {})
                PortalChild.objects.update_or_create(
                    family=family,
                    name=child_name,
                    defaults={
                        "grade": roster_row.get("grade", ""),
                        "note": roster_row.get("note", ""),
                        "is_active": True,
                    },
                )

        seed_date = parse_date(ATTENDANCE_SESSION["date_value"])
        for roster_row in ATTENDANCE_ROSTER:
            family_name = roster_row["family"]
            family_slug = next(
                (f["slug"] for f in FAMILIES if f["name"] == family_name),
                family_name.lower(),
            )
            family, _ = PortalFamily.objects.get_or_create(
                unit=unit,
                slug=family_slug,
                defaults={
                    "name": family_name,
                    "primary_contact": family_by_name.get(family_name, {}).get("primary_contact", ""),
                    "program_label": ATTENDANCE_SESSION["program"],
                    "status": "Active",
                },
            )
            child, _ = PortalChild.objects.get_or_create(
                family=family,
                name=roster_row["child"],
                defaults={
                    "grade": roster_row.get("grade", ""),
                    "note": roster_row.get("note", ""),
                    "is_active": True,
                },
            )

            check_in = None
            check_out = None
            if roster_row.get("check_in"):
                check_in = _parse_display_time(roster_row["check_in"])
            if roster_row.get("check_out"):
                check_out = _parse_display_time(roster_row["check_out"])

            AttendanceRecord.objects.update_or_create(
                child=child,
                program=program,
                date=seed_date,
                defaults={
                    "status": roster_row.get("status", AttendanceRecord.STATUS_EXPECTED),
                    "check_in_time": check_in,
                    "check_out_time": check_out,
                    "method": roster_row.get("method", ""),
                    "note": roster_row.get("note", ""),
                },
            )

        child_count = PortalChild.objects.filter(family__unit=unit).count()
        family_count = PortalFamily.objects.filter(unit=unit).count()
        from portal.live_services import seed_partial_live_data

        seed_partial_live_data(unit, program)
        from portal.admin_config import ensure_admin_config_seeded, ensure_demo_admin_content

        ensure_admin_config_seeded()
        ensure_demo_admin_content()
        _seed_agency_profiles(unit)
        from portal.parent_services import seed_dropin_profiles

        seed_dropin_profiles(unit)
        from portal.parent_services import seed_parent_accounts

        parent_logins = seed_parent_accounts(unit)
        from portal.models import PortalStaffAccount

        from portal.usernames import portal_username

        User = get_user_model()
        staff_user, staff_created = User.objects.get_or_create(
            username=portal_username("staff", "staff18"),
            defaults={"email": "staff18@yeanj.org", "first_name": "School 18 Staff"},
        )
        if staff_created:
            staff_user.set_password("StaffSchool18!")
            staff_user.save()
        PortalStaffAccount.objects.get_or_create(
            user=staff_user,
            defaults={
                "unit": unit,
                "display_name": "School 18 Staff",
                "role": "Unit director",
                "can_add_charge": True,
                "can_delete_charge": False,
                "can_add_credit": False,
            },
        )
        PortalStaffAccount.objects.filter(user=staff_user).update(role="Unit director")
        login_lines = ", ".join(f"{username}/{password}" for username, password, _ in parent_logins)
        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded {family_count} families, {child_count} children, incidents, tickets, messages, and comms."
            )
        )
        if parent_logins:
            self.stdout.write(self.style.SUCCESS(f"Parent portal logins: {login_lines}"))
        self.stdout.write(self.style.SUCCESS("Staff portal login: staff18 / StaffSchool18!"))


def _parse_display_time(value):
    value = value.strip()
    try:
        return datetime.strptime(value, "%I:%M %p").time()
    except ValueError:
        return parse_time(value)


def _seed_agency_profiles(unit):
    for row in AGENCY_UNIT_DATA.get("children", []):
        family = PortalFamily.objects.filter(unit=unit, slug=row["family_slug"]).first()
        if not family:
            continue
        child = PortalChild.objects.filter(family=family, name=row["child"]).first()
        if not child:
            continue
        family.billing_type = "4Cs"
        family.program_label = row.get("program") or family.program_label
        family.balance = Decimal(row.get("copay_balance", family.balance))
        family.save(update_fields=["billing_type", "program_label", "balance"])
        child.billing_plan = row.get("plan", "Weekly copay")
        child.billing_amount = Decimal(row.get("weekly_copay", "0"))
        child.save(update_fields=["billing_plan", "billing_amount"])
        PortalAgencyProfile.objects.update_or_create(
            child=child,
            defaults={
                "unit": unit,
                "family": family,
                "auth_number": row["auth_number"],
                "auth_start": parse_date(row.get("auth_start") or "") if row.get("auth_start") else None,
                "auth_end": parse_date(row.get("auth_end") or "") if row.get("auth_end") else None,
                "weekly_copay": Decimal(row["weekly_copay"]),
                "weekly_agency_rate": Decimal(row["agency_rate"]),
                "agency_balance": Decimal(row.get("agency_balance", "0")),
            },
        )
