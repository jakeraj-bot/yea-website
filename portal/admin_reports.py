"""Organization-wide admin reports: billing, plans, 4Cs, and scholarships."""

from decimal import Decimal

from django.db.models import Q
from django.utils.dateparse import parse_date

from enrollment.models import EnrollmentApplication

from .member_admin import is_placeholder_unit
from .models import (
    PortalAgencyProfile,
    PortalChild,
    PortalFamily,
    PortalLedgerEntry,
    PortalPayment,
    PortalScholarshipAssignment,
    PortalUnit,
)


def _money(value):
    if value is None:
        return "0.00"
    return f"{Decimal(value).quantize(Decimal('0.01')):.2f}"


def _child_school(child):
    if child.school:
        return child.school
    first = (child.name or "").split()[0]
    app = (
        EnrollmentApplication.objects.filter(portal_family=child.family, student_first_name__iexact=first)
        .order_by("-submitted_at")
        .first()
    )
    return (app.student_school if app else "") or ""


def _active_children():
    return (
        PortalChild.objects.filter(is_active=True)
        .select_related("family", "family__unit")
        .prefetch_related("scholarships__fund")
        .order_by("family__name", "name")
    )


def _visible_units():
    return [unit for unit in PortalUnit.objects.filter(is_active=True).order_by("name") if not is_placeholder_unit(unit)]


def unit_options():
    return [(unit.slug, unit.name) for unit in _visible_units()]


def _filter_unit(queryset, unit_slug, family_field="family__unit"):
    if not unit_slug:
        return queryset
    return queryset.filter(**{f"{family_field}__slug": unit_slug})


def _name_match(row_name, family_name, query):
    if not query:
        return True
    needle = query.lower()
    return needle in (row_name or "").lower() or needle in (family_name or "").lower()


def billing_plan_rows(filters=None):
    filters = filters or {}
    query = (filters.get("q") or "").strip()
    school = (filters.get("school") or "").strip()
    billing = (filters.get("billing") or "").strip()
    plan = (filters.get("plan") or "").strip()
    unit = (filters.get("unit") or "").strip()
    rows = []
    schools = set()
    billings = set()
    plans = set()
    for child in _active_children():
        if is_placeholder_unit(child.family.unit):
            continue
        child_school = _child_school(child)
        billing_type = (child.family.billing_type or "Private pay").strip() or "Private pay"
        plan_name = (child.billing_plan or "").strip() or "—"
        if child_school:
            schools.add(child_school)
        billings.add(billing_type)
        if plan_name != "—":
            plans.add(plan_name)
        if unit and child.family.unit.slug != unit:
            continue
        if query and not _name_match(child.name, child.family.name, query):
            continue
        if school and child_school.lower() != school.lower():
            continue
        if billing and billing_type.lower() != billing.lower():
            continue
        if plan and plan.lower() not in plan_name.lower():
            continue
        assignment = _active_assignment(child)
        rows.append(
            {
                "child": child.name,
                "family": child.family.name,
                "family_slug": child.family.slug,
                "family_id": child.family_id,
                "unit": child.family.unit.name,
                "school": child_school or "—",
                "billing": billing_type,
                "plan": plan_name,
                "amount": _money(child.billing_amount) if child.billing_amount is not None else "—",
                "auto_charge": "On" if child.auto_charge else "Off",
                "next_charge": child.next_charge_date.isoformat() if child.next_charge_date else "—",
                "scholarship": assignment.fund.name if assignment else "—",
                "status": "Suspended" if child.family.is_suspended else child.family.status,
            }
        )
    return {
        "rows": rows,
        "schools": sorted(schools),
        "billing_types": sorted(billings),
        "payment_plans": sorted(plans),
    }


def missing_billing_plan_rows(filters=None):
    filters = filters or {}
    query = (filters.get("q") or "").strip()
    unit = (filters.get("unit") or "").strip()
    rows = []
    for child in _active_children():
        if is_placeholder_unit(child.family.unit):
            continue
        if unit and child.family.unit.slug != unit:
            continue
        if query and not _name_match(child.name, child.family.name, query):
            continue
        plan = (child.billing_plan or "").strip()
        missing_plan = not plan
        missing_amount = child.billing_amount is None or child.billing_amount <= 0
        if not missing_plan and not missing_amount:
            continue
        reasons = []
        if missing_plan:
            reasons.append("No plan")
        if missing_amount:
            reasons.append("No amount")
        rows.append(
            {
                "child": child.name,
                "family": child.family.name,
                "family_slug": child.family.slug,
                "family_id": child.family_id,
                "unit": child.family.unit.name,
                "school": _child_school(child) or "—",
                "billing": (child.family.billing_type or "Private pay").strip() or "Private pay",
                "plan": plan or "—",
                "amount": _money(child.billing_amount) if child.billing_amount is not None else "—",
                "reason": " · ".join(reasons),
                "status": "Suspended" if child.family.is_suspended else child.family.status,
            }
        )
    return rows


def ledger_report_rows(filters=None):
    filters = filters or {}
    query = (filters.get("q") or "").strip()
    unit = (filters.get("unit") or "").strip()
    entry_type = (filters.get("entry_type") or "").strip()
    start = parse_date(filters.get("start") or "")
    end = parse_date(filters.get("end") or "")
    entries = PortalLedgerEntry.objects.select_related("family", "family__unit").order_by("-date", "-created_at")
    if unit:
        entries = entries.filter(family__unit__slug=unit)
    if entry_type:
        entries = entries.filter(entry_type=entry_type)
    if start:
        entries = entries.filter(date__gte=start)
    if end:
        entries = entries.filter(date__lte=end)
    if query:
        entries = entries.filter(
            Q(family__name__icontains=query) | Q(child_name__icontains=query) | Q(description__icontains=query)
        )
    rows = []
    charges = Decimal("0")
    credits = Decimal("0")
    for entry in entries:
        if is_placeholder_unit(entry.family.unit):
            continue
        amount = entry.amount or Decimal("0")
        if entry.entry_type == "charge":
            charges += amount
        elif entry.entry_type in ("payment", "credit", "discount", "refund"):
            credits += abs(amount)
        rows.append(
            {
                "date": entry.date.isoformat(),
                "family": entry.family.name,
                "family_slug": entry.family.slug,
                "family_id": entry.family_id,
                "unit": entry.family.unit.name,
                "child": entry.child_name or "—",
                "type": entry.entry_type,
                "description": entry.description,
                "amount": _money(amount),
            }
        )
    return {
        "rows": rows,
        "total_charges": _money(charges),
        "total_credits": _money(credits),
        "net": _money(charges - credits),
    }


def payment_report_rows(filters=None):
    filters = filters or {}
    query = (filters.get("q") or "").strip()
    unit = (filters.get("unit") or "").strip()
    start = parse_date(filters.get("start") or "")
    end = parse_date(filters.get("end") or "")
    rows = []
    seen_keys = set()

    payments = PortalPayment.objects.select_related("family", "family__unit").order_by("-paid_at", "-created_at")
    if unit:
        payments = payments.filter(family__unit__slug=unit)
    if query:
        payments = payments.filter(
            Q(family__name__icontains=query)
            | Q(family__primary_contact__icontains=query)
            | Q(dropin_child__icontains=query)
            | Q(method_label__icontains=query)
        )
    for payment in payments:
        if is_placeholder_unit(payment.family.unit):
            continue
        paid_on = (payment.paid_at.date() if payment.paid_at else payment.created_at.date()) if payment.paid_at or payment.created_at else None
        if start and paid_on and paid_on < start:
            continue
        if end and paid_on and paid_on > end:
            continue
        children = list(payment.family.children.filter(is_active=True).values_list("name", flat=True))
        child = payment.dropin_child or (" · ".join(children) if children else "—")
        key = (payment.family_id, paid_on.isoformat() if paid_on else "", _money(payment.amount))
        seen_keys.add(key)
        method = payment.method_label or ("Card" if payment.stripe_session_id or payment.stripe_payment_intent_id else "Recorded")
        if payment.status == PortalPayment.STATUS_PENDING:
            status = "Waiting for card payment"
        elif payment.status == PortalPayment.STATUS_FAILED:
            status = "Failed"
        else:
            status = "Paid"
        rows.append(
            {
                "date": paid_on.isoformat() if paid_on else "—",
                "child": child,
                "family": payment.family.name,
                "family_slug": payment.family.slug,
                "family_id": payment.family_id,
                "unit": payment.family.unit.name,
                "paid_by": payment.family.primary_contact or payment.family.name,
                "amount": _money(payment.amount),
                "method": method,
                "status": status,
            }
        )

    ledger = PortalLedgerEntry.objects.filter(entry_type="payment").select_related("family", "family__unit").order_by("-date", "-created_at")
    if unit:
        ledger = ledger.filter(family__unit__slug=unit)
    if start:
        ledger = ledger.filter(date__gte=start)
    if end:
        ledger = ledger.filter(date__lte=end)
    if query:
        ledger = ledger.filter(
            Q(family__name__icontains=query)
            | Q(child_name__icontains=query)
            | Q(description__icontains=query)
            | Q(family__primary_contact__icontains=query)
        )
    for entry in ledger:
        if is_placeholder_unit(entry.family.unit):
            continue
        key = (entry.family_id, entry.date.isoformat(), _money(abs(entry.amount)))
        if key in seen_keys:
            continue
        rows.append(
            {
                "date": entry.date.isoformat(),
                "child": entry.child_name or "—",
                "family": entry.family.name,
                "family_slug": entry.family.slug,
                "family_id": entry.family_id,
                "unit": entry.family.unit.name,
                "paid_by": entry.family.primary_contact or entry.family.name,
                "amount": _money(abs(entry.amount)),
                "method": entry.description or "In-person / ledger",
                "status": "Paid",
            }
        )
    rows.sort(key=lambda row: row["date"], reverse=True)
    total = sum((Decimal(row["amount"]) for row in rows), Decimal("0"))
    return {"rows": rows, "total_payments": _money(total)}


def stripe_settlement_rows(filters=None):
    from .stripe_services import bank_status_label, refresh_stripe_settlements, stripe_configured, stripe_payout_rows

    filters = filters or {}
    query = (filters.get("q") or "").strip()
    unit = (filters.get("unit") or "").strip()
    start = parse_date(filters.get("start") or "")
    end = parse_date(filters.get("end") or "")
    status_filter = (filters.get("status") or "").strip()
    payments = list(
        PortalPayment.objects.select_related("family", "family__unit").order_by("-paid_at", "-created_at")
    )
    refresh_stripe_settlements(payments)
    rows = []
    for payment in payments:
        if is_placeholder_unit(payment.family.unit):
            continue
        if unit and payment.family.unit.slug != unit:
            continue
        paid_on = payment.paid_at.date() if payment.paid_at else payment.created_at.date()
        if start and paid_on < start:
            continue
        if end and paid_on > end:
            continue
        children = list(payment.family.children.filter(is_active=True).values_list("name", flat=True))
        child = payment.dropin_child or (" · ".join(children) if children else "—")
        bank_status = bank_status_label(payment.stripe_bank_status)
        if query:
            haystack = " ".join(
                [
                    payment.family.name,
                    payment.family.primary_contact or "",
                    child,
                    bank_status,
                    payment.method_label or "",
                ]
            ).lower()
            if query.lower() not in haystack:
                continue
        if status_filter and payment.stripe_bank_status != status_filter:
            continue
        if payment.status == PortalPayment.STATUS_PENDING:
            card_status = "Waiting for card"
        elif payment.status == PortalPayment.STATUS_FAILED:
            card_status = "Failed"
        else:
            card_status = "Paid"
        rows.append(
            {
                "date": paid_on.isoformat(),
                "child": child,
                "family": payment.family.name,
                "family_slug": payment.family.slug,
                "family_id": payment.family_id,
                "unit": payment.family.unit.name,
                "paid_by": payment.family.primary_contact or payment.family.name,
                "amount": _money(payment.amount),
                "method": payment.method_label or ("Card" if payment.stripe_session_id else "Recorded"),
                "status": card_status,
                "bank_status": bank_status,
                "bank_date": payment.stripe_bank_date.isoformat() if payment.stripe_bank_date else "—",
            }
        )
    if stripe_configured() and not status_filter:
        rows.extend(stripe_payout_rows())
        rows.sort(key=lambda row: row["date"], reverse=True)
    return {
        "rows": rows,
        "statuses": [
            ("waiting_for_card", "Waiting for card payment"),
            ("received_by_stripe", "Stripe received — waiting to become available"),
            ("waiting_for_bank", "Available in Stripe — waiting for bank payout"),
            ("in_transit", "On the way to the bank"),
            ("in_bank", "Paid out to bank"),
            ("not_stripe", "Not Stripe — recorded in portal"),
            ("unknown", "Bank status unavailable"),
        ],
    }


def balance_report_rows(filters=None):
    filters = filters or {}
    query = (filters.get("q") or "").strip()
    unit = (filters.get("unit") or "").strip()
    families = PortalFamily.objects.select_related("unit").order_by("-balance", "name")
    if unit:
        families = families.filter(unit__slug=unit)
    if query:
        families = families.filter(Q(name__icontains=query) | Q(primary_contact__icontains=query))
    rows = []
    outstanding = Decimal("0")
    credit = Decimal("0")
    for family in families:
        if is_placeholder_unit(family.unit):
            continue
        balance = family.balance or Decimal("0")
        if balance > 0:
            outstanding += balance
        elif balance < 0:
            credit += abs(balance)
        rows.append(
            {
                "family": family.name,
                "family_slug": family.slug,
                "family_id": family.pk,
                "unit": family.unit.name,
                "billing": (family.billing_type or "Private pay").strip() or "Private pay",
                "status": "Suspended" if family.is_suspended else family.status,
                "balance": _money(balance),
            }
        )
    return {
        "rows": rows,
        "outstanding": _money(outstanding),
        "credit": _money(credit),
    }


def four_cs_member_rows(filters=None):
    filters = filters or {}
    query = (filters.get("q") or "").strip()
    unit = (filters.get("unit") or "").strip()
    agency = (filters.get("agency") or "").strip()
    profiles = (
        PortalAgencyProfile.objects.select_related("child", "family", "family__unit", "agency", "unit")
        .order_by("agency__name", "family__name", "child__name")
    )
    if unit:
        profiles = profiles.filter(Q(unit__slug=unit) | Q(family__unit__slug=unit))
    if agency:
        profiles = profiles.filter(agency__slug=agency)
    if query:
        profiles = profiles.filter(
            Q(child__name__icontains=query)
            | Q(family__name__icontains=query)
            | Q(auth_number__icontains=query)
            | Q(agency__name__icontains=query)
        )
    rows = []
    agencies = set()
    for profile in profiles:
        if is_placeholder_unit(profile.family.unit):
            continue
        agency_name = profile.agency.name if profile.agency_id else "—"
        if profile.agency_id:
            agencies.add((profile.agency.slug, profile.agency.name))
        rows.append(
            {
                "child": profile.child.name,
                "family": profile.family.name,
                "family_slug": profile.family.slug,
                "family_id": profile.family_id,
                "unit": profile.family.unit.name,
                "school": _child_school(profile.child) or "—",
                "agency": agency_name,
                "auth_number": profile.auth_number or "—",
                "auth_start": profile.auth_start.isoformat() if profile.auth_start else "—",
                "auth_end": profile.auth_end.isoformat() if profile.auth_end else "—",
                "weekly_copay": _money(profile.weekly_copay),
                "weekly_agency_rate": _money(profile.weekly_agency_rate),
                "agency_balance": _money(profile.agency_balance),
            }
        )
    return {
        "rows": rows,
        "agencies": sorted(agencies, key=lambda item: item[1]),
    }


def scholarship_report_rows(filters=None):
    filters = filters or {}
    query = (filters.get("q") or "").strip()
    fund = (filters.get("fund") or "").strip()
    status = (filters.get("status") or "").strip()
    assignments = PortalScholarshipAssignment.objects.select_related(
        "child", "child__family", "child__family__unit", "fund"
    ).order_by("fund__name", "child__family__name", "child__name")
    if fund:
        assignments = assignments.filter(fund_id=fund)
    if status:
        assignments = assignments.filter(status__iexact=status)
    if query:
        assignments = assignments.filter(
            Q(child__name__icontains=query) | Q(child__family__name__icontains=query) | Q(fund__name__icontains=query)
        )
    rows = []
    for row in assignments:
        if is_placeholder_unit(row.child.family.unit):
            continue
        discount = (row.full_rate or Decimal("0")) - (row.parent_amount or Decimal("0"))
        rows.append(
            {
                "child": row.child.name,
                "family": row.child.family.name,
                "family_slug": row.child.family.slug,
                "family_id": row.child.family_id,
                "unit": row.child.family.unit.name,
                "fund": row.fund.name,
                "full_rate": _money(row.full_rate),
                "discount": _money(discount),
                "family_pays": _money(row.parent_amount),
                "start": row.start_date.isoformat() if row.start_date else "—",
                "end": row.end_date.isoformat() if row.end_date else "—",
                "status": row.status,
            }
        )
    return rows


def scheduled_charge_rows(filters=None):
    filters = filters or {}
    query = (filters.get("q") or "").strip()
    unit = (filters.get("unit") or "").strip()
    from .billing_services import plan_repeat_label

    children = (
        PortalChild.objects.select_related("family", "family__unit")
        .filter(is_active=True, auto_charge=True)
        .order_by("next_charge_date", "family__name", "name")
    )
    if unit:
        children = children.filter(family__unit__slug=unit)
    rows = []
    for child in children:
        if is_placeholder_unit(child.family.unit):
            continue
        if query and not _name_match(child.name, child.family.name, query):
            continue
        rows.append(
            {
                "child": child.name,
                "family": child.family.name,
                "family_slug": child.family.slug,
                "family_id": child.family_id,
                "unit": child.family.unit.name,
                "plan": child.billing_plan or "—",
                "amount": _money(child.billing_amount) if child.billing_amount is not None else "—",
                "repeat": plan_repeat_label(child),
                "next_charge": child.next_charge_date.isoformat() if child.next_charge_date else "—",
            }
        )
    return rows


def application_pipeline_rows(filters=None):
    filters = filters or {}
    query = (filters.get("q") or "").strip()
    status = (filters.get("status") or "").strip()
    apps = EnrollmentApplication.objects.select_related("portal_family", "portal_family__unit").order_by("-submitted_at")
    if status:
        apps = apps.filter(status=status)
    if query:
        apps = apps.filter(
            Q(student_first_name__icontains=query)
            | Q(student_last_name__icontains=query)
            | Q(family_name__icontains=query)
            | Q(primary_email__icontains=query)
        )
    rows = []
    for app in apps:
        unit_name = ""
        if app.portal_family_id and app.portal_family.unit_id:
            unit_name = app.portal_family.unit.name
        rows.append(
            {
                "child": f"{app.student_first_name} {app.student_last_name}".strip(),
                "family": app.family_name or (app.portal_family.name if app.portal_family_id else "—"),
                "family_slug": app.portal_family.slug if app.portal_family_id else "",
                "family_id": app.portal_family_id or "",
                "unit": unit_name or app.program_location or "—",
                "program": app.get_program_display() if hasattr(app, "get_program_display") else (app.program or "—"),
                "payment": app.get_payment_method_display() if hasattr(app, "get_payment_method_display") else "—",
                "status": app.get_status_display() if hasattr(app, "get_status_display") else app.status,
                "submitted": app.submitted_at.date().isoformat() if app.submitted_at else "—",
            }
        )
    return rows


def _active_assignment(child, on_date=None):
    from django.utils import timezone

    on_date = on_date or timezone.localdate()
    for row in child.scholarships.all():
        if (row.status or "").lower() != "active":
            continue
        if row.start_date and row.start_date > on_date:
            continue
        if row.end_date and row.end_date < on_date:
            continue
        return row
    return None


LEDGER_TYPES = [
    ("charge", "Charge"),
    ("payment", "Payment"),
    ("credit", "Credit"),
    ("discount", "Discount"),
    ("refund", "Refund"),
]


ADMIN_DATA_REPORTS = {
    "ledger": {
        "title": "Billing ledger",
        "lead": "Every charge, payment, credit, and discount posted across all units.",
        "columns": [
            ("date", "Date"),
            ("family", "Family"),
            ("unit", "Unit"),
            ("child", "Child"),
            ("type", "Type"),
            ("description", "Description"),
            ("amount", "Amount"),
        ],
        "filename": "billing-ledger.csv",
        "filters": ("q", "unit", "entry_type", "start", "end"),
    },
    "balances": {
        "title": "Outstanding balances",
        "lead": "Family balances across all units, largest first.",
        "columns": [
            ("family", "Family"),
            ("unit", "Unit"),
            ("billing", "Payment type"),
            ("status", "Status"),
            ("balance", "Balance"),
        ],
        "filename": "outstanding-balances.csv",
        "filters": ("q", "unit"),
    },
    "payments": {
        "title": "Who paid what",
        "lead": "Every payment — who paid, which child, how much, and on what day.",
        "columns": [
            ("date", "Date"),
            ("child", "Child"),
            ("family", "Family"),
            ("paid_by", "Paid by"),
            ("unit", "Unit"),
            ("amount", "Amount"),
            ("method", "Method"),
            ("status", "Status"),
        ],
        "filename": "payments-who-paid.csv",
        "filters": ("q", "unit", "start", "end"),
    },
    "stripe-settlement": {
        "title": "Stripe & bank payouts",
        "lead": "Whether Stripe has the payment, or it is still waiting to reach the bank.",
        "columns": [
            ("date", "Date paid"),
            ("child", "Child"),
            ("family", "Family"),
            ("paid_by", "Paid by"),
            ("amount", "Amount"),
            ("method", "Method"),
            ("status", "Card / payment"),
            ("bank_status", "Bank / Stripe"),
            ("bank_date", "Expected in bank"),
        ],
        "filename": "stripe-bank-payouts.csv",
        "filters": ("q", "unit", "status", "start", "end"),
    },
    "plans": {
        "title": "Billing plans",
        "lead": "Every child's plan. Filter by name, school, payment type, or plan.",
        "columns": [
            ("child", "Child"),
            ("family", "Family"),
            ("unit", "Unit"),
            ("school", "School"),
            ("billing", "Payment type"),
            ("plan", "Plan"),
            ("amount", "Amount"),
            ("auto_charge", "Auto charge"),
            ("next_charge", "Next charge"),
            ("scholarship", "Scholarship"),
            ("status", "Status"),
        ],
        "filename": "billing-plans.csv",
        "filters": ("q", "school", "billing", "plan", "unit"),
    },
    "missing-plans": {
        "title": "Missing billing plans",
        "lead": "Active children with no billing plan or no weekly amount.",
        "columns": [
            ("child", "Child"),
            ("family", "Family"),
            ("unit", "Unit"),
            ("school", "School"),
            ("billing", "Payment type"),
            ("plan", "Plan"),
            ("amount", "Amount"),
            ("reason", "Missing"),
            ("status", "Status"),
        ],
        "filename": "missing-billing-plans.csv",
        "filters": ("q", "unit"),
    },
    "four-cs": {
        "title": "4Cs members & agencies",
        "lead": "Every 4Cs child with agency, authorization, and rate details.",
        "columns": [
            ("child", "Child"),
            ("family", "Family"),
            ("unit", "Unit"),
            ("school", "School"),
            ("agency", "Agency"),
            ("auth_number", "Authorization"),
            ("auth_start", "Auth start"),
            ("auth_end", "Auth end"),
            ("weekly_copay", "Weekly copay"),
            ("weekly_agency_rate", "Agency rate"),
            ("agency_balance", "Agency balance"),
        ],
        "filename": "4cs-members.csv",
        "filters": ("q", "unit", "agency"),
    },
    "scholarships": {
        "title": "Scholarship assignments",
        "lead": "Scholarship types assigned to children, with full rate and family portion.",
        "columns": [
            ("child", "Child"),
            ("family", "Family"),
            ("unit", "Unit"),
            ("fund", "Scholarship"),
            ("full_rate", "Full rate"),
            ("discount", "Discount"),
            ("family_pays", "Family pays"),
            ("start", "Start"),
            ("end", "End"),
            ("status", "Status"),
        ],
        "filename": "scholarship-assignments.csv",
        "filters": ("q", "fund", "status"),
    },
    "scheduled": {
        "title": "Scheduled plan charges",
        "lead": "Children with automatic billing and the next charge date.",
        "columns": [
            ("child", "Child"),
            ("family", "Family"),
            ("unit", "Unit"),
            ("plan", "Plan"),
            ("amount", "Amount"),
            ("repeat", "Repeat"),
            ("next_charge", "Next charge"),
        ],
        "filename": "scheduled-charges.csv",
        "filters": ("q", "unit"),
    },
    "applications": {
        "title": "Application pipeline",
        "lead": "Enrollment applications by status, program, and payment type.",
        "columns": [
            ("child", "Child"),
            ("family", "Family"),
            ("unit", "Unit / location"),
            ("program", "Program"),
            ("payment", "Payment type"),
            ("status", "Status"),
            ("submitted", "Submitted"),
        ],
        "filename": "application-pipeline.csv",
        "filters": ("q", "status"),
    },
}


def build_admin_report(slug, filters=None):
    filters = filters or {}
    spec = ADMIN_DATA_REPORTS.get(slug)
    if not spec:
        return None
    extra = {}
    if slug == "ledger":
        data = ledger_report_rows(filters)
        rows = data["rows"]
        extra["summary"] = f"{len(rows)} entries · charges ${data['total_charges']} · credits ${data['total_credits']} · net ${data['net']}"
        extra["entry_types"] = LEDGER_TYPES
    elif slug == "balances":
        data = balance_report_rows(filters)
        rows = data["rows"]
        extra["summary"] = f"{len(rows)} families · ${data['outstanding']} outstanding · ${data['credit']} in credit"
    elif slug == "payments":
        data = payment_report_rows(filters)
        rows = data["rows"]
        extra["summary"] = f"{len(rows)} payments · ${data['total_payments']} collected"
    elif slug == "stripe-settlement":
        data = stripe_settlement_rows(filters)
        rows = data["rows"]
        extra["summary"] = f"{len(rows)} Stripe and bank rows"
        extra["statuses"] = [value for value, _label in data["statuses"]]
        extra["status_choices"] = data["statuses"]
    elif slug == "plans":
        data = billing_plan_rows(filters)
        rows = data["rows"]
        extra["summary"] = f"{len(rows)} children"
        extra["schools"] = data["schools"]
        extra["billing_types"] = data["billing_types"]
        extra["payment_plans"] = data["payment_plans"]
    elif slug == "missing-plans":
        rows = missing_billing_plan_rows(filters)
        extra["summary"] = f"{len(rows)} children need a plan or amount"
    elif slug == "four-cs":
        data = four_cs_member_rows(filters)
        rows = data["rows"]
        extra["summary"] = f"{len(rows)} 4Cs members"
        extra["agencies"] = data["agencies"]
    elif slug == "scholarships":
        rows = scholarship_report_rows(filters)
        extra["summary"] = f"{len(rows)} assignments"
        extra["funds"] = list(
            PortalScholarshipAssignment.objects.select_related("fund")
            .values_list("fund_id", "fund__name")
            .distinct()
            .order_by("fund__name")
        )
        extra["statuses"] = sorted({row["status"] for row in rows})
    elif slug == "scheduled":
        rows = scheduled_charge_rows(filters)
        extra["summary"] = f"{len(rows)} scheduled plans"
    elif slug == "applications":
        rows = application_pipeline_rows(filters)
        extra["summary"] = f"{len(rows)} applications"
        extra["statuses"] = list(
            EnrollmentApplication.objects.values_list("status", flat=True).distinct().order_by("status")
        )
    else:
        return None
    extra["units"] = unit_options()
    for row in rows:
        row["display"] = [{"key": key, "value": row.get(key, "")} for key, _label in spec["columns"]]
    return {
        "slug": slug,
        "title": spec["title"],
        "lead": spec["lead"],
        "columns": spec["columns"],
        "filename": spec["filename"],
        "filters": spec["filters"],
        "rows": rows,
        **extra,
    }
