"""Sandbox parent portal — a dedicated practice family, never a live household."""

from datetime import date
from decimal import Decimal

from django.conf import settings
from django.contrib.auth import get_user_model, login, logout
from django.db import transaction
from django.utils import timezone

from core.stripe_config import member_stripe_configured, member_stripe_is_test_mode

from .models import (
    PortalChild,
    PortalFamily,
    PortalLedgerEntry,
    PortalOrgSetting,
    PortalParentAccount,
    PortalUnit,
)
from .staff_auth import get_portal_auth, set_portal_auth
from .usernames import display_username, portal_username

PRACTICE_FAMILY_SLUG = "practice"
PRACTICE_FAMILY_NAME = "Practice family"
PRACTICE_USERNAME = "practiceparent"
PRACTICE_PASSWORD = "PracticeFamily2026!"
PRACTICE_EMAIL = "practiceparent@example.invalid"
PRACTICE_PRIMARY = "Alex Practice"
PRACTICE_CHILD_NAME = "Sam Practice"
PRACTICE_CHILD_GRADE = "4th"
PRACTICE_BALANCE = Decimal("85.00")
PRACTICE_AUTH_BACKEND = "django.contrib.auth.backends.ModelBackend"

SESSION_FLAG = "practice_parent_session"
SESSION_RESTORE_USER = "practice_restore_user_id"
SESSION_RESTORE_AUTH = "practice_restore_portal_auth"


def is_practice_family(family):
    return bool(family and getattr(family, "slug", "") == PRACTICE_FAMILY_SLUG)


def exclude_practice_families(qs):
    return qs.exclude(slug=PRACTICE_FAMILY_SLUG)


def practice_parent_available():
    if getattr(settings, "ALLOW_PORTAL_DEMO_SEED", False):
        return True
    if getattr(settings, "ALLOW_PORTAL_PRACTICE", False):
        return True
    # Local design (DEBUG on, not the partner staging site) — show the button.
    if getattr(settings, "DEBUG", False) and not getattr(settings, "STAGING_SITE", False):
        return True
    try:
        return bool(PortalOrgSetting.load().practice_parent_enabled)
    except Exception:
        return False


def practice_can_use_stripe_checkout():
    """Practice payments may hit Stripe only with test keys — never live charges."""
    return member_stripe_configured() and member_stripe_is_test_mode()


def is_practice_parent_session(request, account=None):
    if request is None:
        return False
    if request.session.get(SESSION_FLAG):
        return True
    if account and is_practice_family(account.family):
        return True
    if getattr(request, "user", None) and request.user.is_authenticated:
        from .parent_auth import get_parent_account

        live_account = account or get_parent_account(request.user)
        return bool(live_account and is_practice_family(live_account.family))
    return False


def can_return_to_admin(request):
    return bool(request and request.session.get(SESSION_RESTORE_USER))


def _practice_unit():
    unit = PortalUnit.objects.filter(is_active=True).order_by("name").first()
    if unit:
        return unit
    unit, _created = PortalUnit.objects.get_or_create(
        slug="school-18",
        defaults={"name": "School 18", "is_active": True},
    )
    return unit


def _seed_practice_application(family, child):
    from enrollment.models import EmergencyContact, EnrollmentApplication

    first, last = PRACTICE_CHILD_NAME.split(" ", 1)
    app = EnrollmentApplication.objects.filter(
        portal_family=family,
        student_first_name__iexact=first,
        student_last_name__iexact=last,
    ).first()
    if app:
        return app
    app = EnrollmentApplication.objects.create(
        program="after_school",
        program_location="school_18",
        family_name=family.name,
        primary_email=PRACTICE_EMAIL,
        home_address="100 Practice Lane",
        primary_first_name="Alex",
        primary_last_name="Practice",
        primary_gender="female",
        primary_language="english",
        primary_relationship="guardian",
        primary_phone="555-0140",
        primary_phone_type="cell",
        primary_text_subscription="yes",
        primary_email_subscription="yes",
        primary_email_address=PRACTICE_EMAIL,
        primary_authorized_pickup="yes",
        student_first_name=first,
        student_last_name=last,
        student_gender="female",
        student_dob=date(2016, 4, 12),
        student_language="english",
        student_ethnicity="unknown",
        student_race="unknown",
        student_grade="4",
        student_school="Paterson School 18",
        health_statement="good_health",
        membership_fee_agreed="no",
        payment_method="private_pay",
        payment_plan="weekly",
        payment_plan_signature="Alex Practice",
        payment_plan_signed_date=date(2026, 8, 1),
        status="enrolled",
        portal_family=family,
    )
    EmergencyContact.objects.create(
        application=app,
        order=1,
        first_name="Casey",
        last_name="Neighbor",
        phone="555-0141",
        relationship="Neighbor",
        authorized_pickup=True,
    )
    return app


def ensure_practice_balance(family):
    from .family_list import household_ledger_totals, sync_family_balance_from_ledger

    total = household_ledger_totals([family.pk]).get(family.pk, Decimal("0"))
    if total > 0:
        sync_family_balance_from_ledger(family)
        return family
    PortalLedgerEntry.objects.create(
        family=family,
        child_name=PRACTICE_CHILD_NAME,
        date=timezone.localdate(),
        entry_type="charge",
        description="Practice after-school week (sandbox)",
        amount=PRACTICE_BALANCE,
        is_manual=True,
    )
    sync_family_balance_from_ledger(family)
    return family


@transaction.atomic
def ensure_practice_parent_account():
    """Create or refresh the isolated Practice family + parent login."""
    unit = _practice_unit()
    family, _created = PortalFamily.objects.update_or_create(
        unit=unit,
        slug=PRACTICE_FAMILY_SLUG,
        defaults={
            "name": PRACTICE_FAMILY_NAME,
            "primary_contact": PRACTICE_PRIMARY,
            "billing_type": "Private pay",
            "program_label": "After-school",
            "status": "Active",
            "is_suspended": False,
        },
    )

    child, _child_created = PortalChild.objects.update_or_create(
        family=family,
        name=PRACTICE_CHILD_NAME,
        defaults={
            "grade": PRACTICE_CHILD_GRADE,
            "school": "Paterson School 18",
            "is_active": True,
            "unit": unit,
            "billing_plan": "Weekly",
            "billing_amount": Decimal("85.00"),
        },
    )
    _seed_practice_application(family, child)
    ensure_practice_balance(family)

    User = get_user_model()
    username = portal_username("parent", PRACTICE_USERNAME)
    user, user_created = User.objects.get_or_create(
        username=username,
        defaults={
            "email": PRACTICE_EMAIL,
            "first_name": "Alex",
            "last_name": "Practice",
        },
    )
    if user_created or not user.has_usable_password():
        user.set_password(PRACTICE_PASSWORD)
        user.email = PRACTICE_EMAIL
        user.save()
    else:
        # Keep the known practice password so the admin button and docs stay in sync.
        user.set_password(PRACTICE_PASSWORD)
        user.email = PRACTICE_EMAIL
        user.first_name = "Alex"
        user.last_name = "Practice"
        user.save(update_fields=["password", "email", "first_name", "last_name"])

    account, _account_created = PortalParentAccount.objects.update_or_create(
        user=user,
        defaults={
            "family": family,
            "autopay_enabled": False,
            "email_receipts": True,
            "email_reminders": True,
            "sms_reminders": False,
        },
    )
    if account.family_id != family.pk:
        account.family = family
        account.save(update_fields=["family"])
    return account


def practice_login_hint():
    return {
        "url": "/portal/login/",
        "username": PRACTICE_USERNAME,
        "password": PRACTICE_PASSWORD,
        "display_username": PRACTICE_USERNAME,
    }


def start_practice_parent_session(request):
    """Switch this browser session from admin to the sandbox parent."""
    account = ensure_practice_parent_account()
    restore_user_id = request.user.pk if request.user.is_authenticated else None
    restore_auth = get_portal_auth(request) or "admin"
    login(request, account.user, backend=PRACTICE_AUTH_BACKEND)
    set_portal_auth(request, "parent")
    request.session[SESSION_FLAG] = True
    if restore_user_id:
        request.session[SESSION_RESTORE_USER] = restore_user_id
        request.session[SESSION_RESTORE_AUTH] = restore_auth
    return account


def restore_admin_from_practice(request):
    """Put the admin back in the same browser after practice."""
    user_id = request.session.get(SESSION_RESTORE_USER)
    auth = request.session.get(SESSION_RESTORE_AUTH) or "admin"
    User = get_user_model()
    user = User.objects.filter(pk=user_id).first() if user_id else None
    if not user:
        logout(request)
        return False
    login(request, user, backend=PRACTICE_AUTH_BACKEND)
    set_portal_auth(request, auth)
    request.session.pop(SESSION_FLAG, None)
    request.session.pop(SESSION_RESTORE_USER, None)
    request.session.pop(SESSION_RESTORE_AUTH, None)
    return True


def complete_practice_test_payment(account, amount, *, is_dropin=False, dropin=None):
    """Record a sandbox payment without calling live Stripe."""
    from .models import PortalPayment
    from .parent_services import record_successful_payment
    from .processing_fees import apply_fee_to_payment

    dropin = dropin or {}
    payment = PortalPayment.objects.create(
        family=account.family,
        amount=amount,
        payment_kind="dropin" if is_dropin else "balance",
        dropin_child=dropin.get("child", ""),
        dropin_program=dropin.get("program", ""),
        dropin_location=dropin.get("location", ""),
        dropin_date=dropin.get("date", ""),
        method_label="Stripe test (practice)",
    )
    apply_fee_to_payment(payment)
    return record_successful_payment(
        payment,
        method_label="Stripe test (practice)",
        ledger_note="Practice parent test payment — Stripe test mode",
        child_name="" if is_dropin else PRACTICE_CHILD_NAME,
    )


def practice_parent_logins():
    return [(PRACTICE_USERNAME, PRACTICE_PASSWORD, PRACTICE_FAMILY_NAME)]


def display_practice_username():
    return display_username(portal_username("parent", PRACTICE_USERNAME))
