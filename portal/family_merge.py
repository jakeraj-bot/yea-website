"""Merge duplicate family / child portal records into one household."""

from django.db import transaction
from django.db.models import Q

from enrollment.models import EnrollmentApplication
from enrollment.portal_integration import find_existing_family_for_parent

from .member_admin import parent_email_for_family
from .models import (
    AttendanceRecord,
    PortalAgencyLedgerEntry,
    PortalAgencyProfile,
    PortalAgencyRemittanceAllocation,
    PortalChild,
    PortalFamily,
    PortalFieldTripSignup,
    PortalLedgerEntry,
    PortalParentAccount,
    PortalPolicySignatureRequest,
    PortalWaivedAbsenceCharge,
)


def _norm_name(value):
    return " ".join((value or "").split()).strip().lower()


def dob_for_child(child):
    name = _norm_name(child.name)
    for row in EnrollmentApplication.objects.filter(portal_family=child.family).order_by("-submitted_at"):
        label = _norm_name(f"{row.student_first_name} {row.student_last_name}")
        if label == name and row.student_dob:
            return row.student_dob
    return None


def children_are_same_person(left, right):
    """True when two roster rows are the same child (name + matching DOB)."""
    if _norm_name(left.name) != _norm_name(right.name):
        return False
    dob_left = dob_for_child(left)
    dob_right = dob_for_child(right)
    if dob_left and dob_right and dob_left != dob_right:
        return False
    return True


def _child_has_site_history(child):
    """True when this roster row is actually used at its site (not just a duplicate charge)."""
    if child.attendance_records.exists():
        return True
    from enrollment.locations import get_unit_for_enrollment_key

    name = _norm_name(child.name)
    unit_id = child.unit_id or getattr(child.family, "unit_id", None)
    for app in EnrollmentApplication.objects.filter(
        portal_family=child.family,
        status__in=("approved", "enrolled"),
    ):
        if _norm_name(f"{app.student_first_name} {app.student_last_name}") != name:
            continue
        app_unit = get_unit_for_enrollment_key(app.program_location)
        if app_unit and unit_id and app_unit.pk == unit_id:
            return True
    return False


def keep_both_child_rows(left, right):
    """Same person at two sites with real history at both — allowed on one family."""
    unit_left = left.unit_id or getattr(left.family, "unit_id", None)
    unit_right = right.unit_id or getattr(right.family, "unit_id", None)
    if not unit_left or not unit_right or unit_left == unit_right:
        return False
    return _child_has_site_history(left) and _child_has_site_history(right)


def family_history_score(family):
    payments = family.payments.count()
    ledger = family.ledger_entries.count()
    attendance = AttendanceRecord.objects.filter(child__family=family).count()
    approved = family.enrollment_applications.filter(status__in=("approved", "enrolled")).count()
    has_login = 1 if PortalParentAccount.objects.filter(family=family).exists() else 0
    children = family.children.count()
    return (
        approved * 100
        + payments * 50
        + attendance * 10
        + ledger * 5
        + has_login * 20
        + children * 3,
        family.pk,
    )


def pick_survivor_family(families):
    rows = [family for family in families if family]
    if not rows:
        return None
    return max(rows, key=family_history_score)


def suggested_merge_families(family):
    if not family:
        return []
    seen = {family.pk}
    candidates = []

    def _add(other):
        if other and other.pk not in seen:
            seen.add(other.pk)
            candidates.append(other)

    email = parent_email_for_family(family)
    if email:
        for account in PortalParentAccount.objects.filter(user__email__iexact=email).select_related("family"):
            _add(account.family)
        for app in EnrollmentApplication.objects.filter(
            Q(primary_email__iexact=email) | Q(primary_email_address__iexact=email),
            portal_family__isnull=False,
        ).select_related("portal_family"):
            _add(app.portal_family)

    for child in family.children.all():
        for other in PortalChild.objects.filter(name__iexact=child.name).exclude(family=family).select_related(
            "family"
        ):
            if children_are_same_person(child, other):
                _add(other.family)
        parts = (child.name or "").split()
        if len(parts) >= 2:
            dob = dob_for_child(child)
            if dob:
                match = find_existing_family_for_parent(
                    child_first=parts[0],
                    child_last=" ".join(parts[1:]),
                    child_dob=dob,
                )
                _add(match)
    return candidates


def search_families_for_merge(query):
    """Find children/families matching a name (Danuska, last name, email)."""
    query = (query or "").strip()
    children = list(
        PortalChild.objects.filter(Q(name__icontains=query) | Q(family__name__icontains=query))
        .select_related("family", "unit", "family__unit")
        .order_by("name", "family_id")
    )
    families = list(
        PortalFamily.objects.filter(
            Q(name__icontains=query)
            | Q(primary_contact__icontains=query)
            | Q(slug__icontains=query)
            | Q(parent_account__user__email__icontains=query)
            | Q(parent_account__user__first_name__icontains=query)
        )
        .select_related("unit")
        .distinct()
        .order_by("name", "pk")
    )
    apps = list(
        EnrollmentApplication.objects.filter(
            Q(student_first_name__icontains=query)
            | Q(student_last_name__icontains=query)
            | Q(family_name__icontains=query)
            | Q(primary_email__icontains=query)
            | Q(primary_first_name__icontains=query)
            | Q(primary_last_name__icontains=query)
        )
        .select_related("portal_family", "portal_family__unit")
        .order_by("-submitted_at")
    )
    return children, families, apps


@transaction.atomic
def merge_children(keep_child, drop_child):
    if keep_child.pk == drop_child.pk:
        return keep_child
    if drop_child.attendance_records.count() > keep_child.attendance_records.count() and not keep_child.attendance_records.exists():
        keep_child, drop_child = drop_child, keep_child

    for record in list(drop_child.attendance_records.all()):
        if AttendanceRecord.objects.filter(
            child=keep_child, program=record.program, date=record.date
        ).exists():
            record.delete()
        else:
            record.child = keep_child
            record.save(update_fields=["child"])

    drop_child.incidents.update(child=keep_child)
    drop_child.scholarships.update(child=keep_child)
    drop_child.drop_off_bookings.update(child=keep_child, family=keep_child.family)

    for signup in list(drop_child.field_trip_signups.all()):
        if PortalFieldTripSignup.objects.filter(trip=signup.trip, child=keep_child).exists():
            signup.delete()
        else:
            signup.child = keep_child
            signup.family = keep_child.family
            signup.save(update_fields=["child", "family"])

    for request_row in list(drop_child.policy_requests.all()):
        if PortalPolicySignatureRequest.objects.filter(child=keep_child, policy=request_row.policy).exists():
            request_row.delete()
        else:
            request_row.child = keep_child
            request_row.family = keep_child.family
            request_row.save(update_fields=["child", "family"])

    keep_profile = PortalAgencyProfile.objects.filter(child=keep_child).first()
    drop_profile = PortalAgencyProfile.objects.filter(child=drop_child).first()
    if drop_profile and keep_profile:
        drop_profile.contract_weeks.update(profile=keep_profile)
        PortalAgencyLedgerEntry.objects.filter(profile=drop_profile).update(profile=keep_profile)
        PortalAgencyRemittanceAllocation.objects.filter(profile=drop_profile).update(profile=keep_profile)
        drop_profile.delete()
    elif drop_profile:
        drop_profile.child = keep_child
        drop_profile.family = keep_child.family
        drop_profile.save(update_fields=["child", "family"])

    fields = []
    if not keep_child.grade and drop_child.grade:
        keep_child.grade = drop_child.grade
        fields.append("grade")
    if not keep_child.school and drop_child.school:
        keep_child.school = drop_child.school
        fields.append("school")
    if not keep_child.unit_id and drop_child.unit_id:
        keep_child.unit_id = drop_child.unit_id
        fields.append("unit")
    if drop_child.is_active and not keep_child.is_active:
        keep_child.is_active = True
        fields.append("is_active")
    if fields:
        keep_child.save(update_fields=fields)
    drop_child.delete()
    return keep_child


def _merge_parent_accounts(keep, drop):
    keep_account = PortalParentAccount.objects.filter(family=keep).select_related("user").first()
    drop_account = PortalParentAccount.objects.filter(family=drop).select_related("user").first()
    if drop_account and keep_account:
        if not keep_account.stripe_customer_id and drop_account.stripe_customer_id:
            keep_account.stripe_customer_id = drop_account.stripe_customer_id
            keep_account.save(update_fields=["stripe_customer_id"])
        drop_user = drop_account.user
        drop_account.change_requests.update(account=keep_account)
        drop_account.delete()
        if drop_user and drop_user.pk != keep_account.user_id and not drop_user.is_superuser:
            drop_user.delete()
    elif drop_account:
        drop_account.family = keep
        drop_account.save(update_fields=["family"])


@transaction.atomic
def merge_families(keep, drop):
    """Move every child, ledger, payment, application, and login onto `keep`.

    Payment history is never deleted. Same-person child rows are combined unless
    they truly attend two different sites.
    """
    if not keep or not drop:
        raise ValueError("Choose two family accounts to merge.")
    if keep.pk == drop.pk:
        raise ValueError("Those are the same family account.")

    keep_balance = keep.balance or 0
    drop_balance = drop.balance or 0
    drop_slug = drop.slug
    drop_name = drop.name

    drop_children = list(drop.children.all())
    keep_children = list(keep.children.all())
    for incoming in drop_children:
        match = next((child for child in keep_children if children_are_same_person(child, incoming)), None)
        if match and keep_both_child_rows(match, incoming):
            incoming.family = keep
            incoming.save(update_fields=["family"])
            keep_children.append(incoming)
            continue
        if match:
            merge_children(match, incoming)
            continue
        incoming.family = keep
        incoming.save(update_fields=["family"])
        keep_children.append(incoming)

    EnrollmentApplication.objects.filter(portal_family=drop).update(portal_family=keep)
    PortalLedgerEntry.objects.filter(family=drop).update(family=keep)
    drop.payments.update(family=keep)
    drop.discount_assignments.update(family=keep)
    drop.prior_balances.update(linked_family=keep)
    drop.policy_requests.update(family=keep)
    drop.field_trip_signups.update(family=keep)
    drop.drop_off_bookings.update(family=keep)
    drop.supportticket_set.update(family=keep)
    drop.support_view_sessions.update(family=keep)
    drop.agency_profiles.update(family=keep)
    PortalWaivedAbsenceCharge.objects.filter(family_slug=drop_slug).update(family_slug=keep.slug)

    _merge_parent_accounts(keep, drop)

    keep.balance = keep_balance + drop_balance
    updates = ["balance"]
    if keep.status == "Pending enrollment" and drop.status == "Active":
        keep.status = "Active"
        updates.append("status")
    if not keep.primary_contact and drop.primary_contact:
        keep.primary_contact = drop.primary_contact
        updates.append("primary_contact")
    if not keep.program_label and drop.program_label:
        keep.program_label = drop.program_label
        updates.append("program_label")
    keep.save(update_fields=updates)
    drop.delete()
    return keep, drop_name


def describe_family(family):
    email = parent_email_for_family(family)
    children = ", ".join(child.name for child in family.children.all()) or "(no children)"
    unit = family.unit.name if family.unit_id else "—"
    login = "yes" if PortalParentAccount.objects.filter(family=family).exists() else "no"
    return (
        f"#{family.pk} {family.name} · {unit} · children: {children} · "
        f"email: {email or '—'} · parent login: {login} · "
        f"payments: {family.payments.count()} · ledger: {family.ledger_entries.count()} · "
        f"balance: {family.balance}"
    )
