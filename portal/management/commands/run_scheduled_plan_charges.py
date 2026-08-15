from django.core.management.base import BaseCommand

from portal.billing_services import run_due_plan_charges


class Command(BaseCommand):
    help = "Post child billing-plan charges that are due today and advance the next date."

    def handle(self, *args, **options):
        posted = run_due_plan_charges()
        if not posted:
            self.stdout.write("No scheduled plan charges were due.")
            return
        for child in posted:
            self.stdout.write(
                self.style.SUCCESS(
                    f"{child.family.slug} · {child.name}: ${child.billing_amount} posted, next {child.next_charge_date}"
                )
            )
