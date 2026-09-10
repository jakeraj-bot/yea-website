from django.core.management.base import BaseCommand, CommandError

from portal.family_merge import (
    describe_family,
    merge_families,
    pick_survivor_family,
    search_families_for_merge,
    suggested_merge_families,
)
from portal.models import PortalFamily


class Command(BaseCommand):
    help = (
        "Find and merge duplicate family accounts (same parent email or the same "
        "child name + date of birth). Dry-run unless --apply is passed. "
        "Use this in production when a child such as Danuska has two logins."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--search",
            default="",
            help="Child, family, or parent name/email to look up (example: Danuska).",
        )
        parser.add_argument("--keep-id", type=int, help="Family id to keep.")
        parser.add_argument("--from-id", type=int, help="Family id to merge into --keep-id.")
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Write the merge. Without this flag, only print what would happen.",
        )

    def handle(self, *args, **options):
        search = (options.get("search") or "").strip()
        keep_id = options.get("keep_id")
        from_id = options.get("from_id")
        apply_merge = options.get("apply")

        if keep_id and from_id:
            keep = PortalFamily.objects.filter(pk=keep_id).first()
            drop = PortalFamily.objects.filter(pk=from_id).first()
            if not keep or not drop:
                raise CommandError("Both --keep-id and --from-id must be existing family ids.")
            self.stdout.write(f"Keep: {describe_family(keep)}")
            self.stdout.write(f"Merge in: {describe_family(drop)}")
            if not apply_merge:
                self.stdout.write(self.style.WARNING("Dry run. Pass --apply to merge."))
                return
            keep, dropped_name = merge_families(keep, drop)
            self.stdout.write(self.style.SUCCESS(f"Merged {dropped_name} into #{keep.pk} {keep.name}."))
            self.stdout.write(describe_family(keep))
            return

        if not search:
            raise CommandError("Pass --search NAME (for example Danuska) or --keep-id and --from-id.")

        children, families, apps = search_families_for_merge(search)
        self.stdout.write(f"Search: {search!r}")
        self.stdout.write(f"Children ({len(children)}):")
        for child in children:
            unit = child.unit.name if child.unit_id else (child.family.unit.name if child.family.unit_id else "—")
            self.stdout.write(f"  child #{child.pk} {child.name} · family #{child.family_id} {child.family.name} · {unit}")
        family_map = {family.pk: family for family in families}
        for child in children:
            family_map[child.family_id] = child.family
        for app in apps:
            if app.portal_family_id:
                family_map[app.portal_family_id] = app.portal_family
        families = list(family_map.values())
        self.stdout.write(f"Families ({len(families)}):")
        for family in families:
            self.stdout.write(f"  {describe_family(family)}")
        self.stdout.write(f"Applications ({len(apps)}):")
        for app in apps:
            family_label = f"family #{app.portal_family_id}" if app.portal_family_id else "unlinked"
            self.stdout.write(
                f"  {app.student_first_name} {app.student_last_name} · {app.program_location} · "
                f"{app.status} · {app.primary_email} · {family_label}"
            )

        groups = []
        seen = set()
        for family in families:
            if family.pk in seen:
                continue
            related = [family] + list(suggested_merge_families(family))
            ids = tuple(sorted({row.pk for row in related}))
            if len(ids) < 2:
                continue
            if ids in seen:
                continue
            seen.update(ids)
            groups.append(related)

        if not groups:
            self.stdout.write(self.style.WARNING("No duplicate family groups found for that search."))
            return

        for related in groups:
            survivor = pick_survivor_family(related)
            others = [row for row in related if row.pk != survivor.pk]
            self.stdout.write("")
            self.stdout.write(f"Suggested survivor: {describe_family(survivor)}")
            for other in others:
                self.stdout.write(f"  merge in: {describe_family(other)}")
            if not apply_merge:
                continue
            for other in others:
                other = PortalFamily.objects.filter(pk=other.pk).first()
                survivor = PortalFamily.objects.filter(pk=survivor.pk).first()
                if not other or not survivor:
                    continue
                survivor, dropped_name = merge_families(survivor, other)
                self.stdout.write(self.style.SUCCESS(f"Merged {dropped_name} into #{survivor.pk} {survivor.name}."))

        if not apply_merge:
            self.stdout.write("")
            self.stdout.write(self.style.WARNING("Dry run. Pass --apply to merge the suggested groups."))
