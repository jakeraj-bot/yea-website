from decimal import Decimal

from django.db import models
from django.utils import timezone

from .demo_data import (
    FAMILIES_BILLING,
    PARENT_ACCOUNT,
    PARENT_ANNOUNCEMENTS,
    PARENT_DROP_IN,
    PARENT_PAYMENT_PREVIEWS,
    PARENT_PROFILE,
    PARENT_RECEIPTS,
    TAX_STATEMENT_ELIGIBILITY,
    TAX_STATEMENT_SETTINGS,
    enrich_receipt_for_print,
)
from .models import PortalLedgerEntry, PortalParentAccount, PortalPayment, PortalProfileChangeRequest

SEED_FAMILY_SLUGS = frozenset({"jacobs", "martinez", "williams"})
SEED_PREVIEW_KEYS = {
    "jacobs": "private-pay",
    "martinez": "4cs",
    "williams": "scholarship",
}


def _parent_demo_fallbacks_enabled():
    from .parent_auth import portal_preview_mode

    return portal_preview_mode()


def _format_last_login(user):
    if not user.last_login:
        return "First login"
    local = timezone.localtime(user.last_login)
    return local.strftime("%B %d, %Y at %-I:%M %p")


def _child_balances_from_ledger(family):
    if _parent_demo_fallbacks_enabled() and family.slug in SEED_FAMILY_SLUGS:
        billing_demo = FAMILIES_BILLING.get(family.slug, {})
        children = [dict(child) for child in billing_demo.get("children", [])]
        if children:
            return children

    portal_children = list(family.children.filter(is_active=True))
    if portal_children:
        return [
            {
                "name": child.name,
                "balance": f"{family.balance:.2f}",
                "plan": child.billing_plan or family.program_label or "Weekly",
                "amount": f"{child.billing_amount:.2f}" if child.billing_amount is not None else "—",
                "type": family.billing_type or "Private pay",
                "child_id": child.pk,
            }
            for child in portal_children
        ]

    from enrollment.models import EnrollmentApplication
    from enrollment.portal_integration import STATUS_LABELS

    rows = []
    for app in EnrollmentApplication.objects.filter(portal_family=family).order_by("-submitted_at"):
        if app.status == "declined":
            continue
        rows.append(
            {
                "name": f"{app.student_first_name} {app.student_last_name}".strip(),
                "balance": "0.00",
                "plan": app.get_payment_plan_display(),
                "type": app.get_payment_method_display(),
                "status": STATUS_LABELS.get(app.status, "Under review"),
            }
        )
    return rows


def get_billing_live(family):
    demo = {}
    if _parent_demo_fallbacks_enabled() and family.slug in SEED_FAMILY_SLUGS:
        demo = FAMILIES_BILLING.get(family.slug, {})
    ledger_qs = PortalLedgerEntry.objects.filter(family=family)
    if ledger_qs.exists():
        ledger = [
            {
                "date": entry.date.isoformat(),
                "child": entry.child_name,
                "type": entry.entry_type,
                "description": entry.description,
                "amount": f"{abs(entry.amount):.2f}" if entry.entry_type in ("payment", "discount") else f"{entry.amount:.2f}",
                "manual": entry.is_manual,
            }
            for entry in ledger_qs
        ]
    else:
        ledger = demo.get("ledger", [])

    children = _child_balances_from_ledger(family)
    payment_type = demo.get("payment_type") or family.billing_type or "Private pay"
    return {
        "family_name": family.name,
        "slug": family.slug,
        "running_balance": f"{family.balance:.2f}",
        "payment_type": payment_type,
        "payment_type_note": demo.get("account_note", demo.get("payment_type_note", "")),
        "agency_name": demo.get("agency_name", ""),
        "children": children,
        "ledger": ledger,
    }


def get_account_live(account):
    from .usernames import display_username

    preview_key = SEED_PREVIEW_KEYS.get(account.family.slug)
    demo = (
        PARENT_ACCOUNT.get(preview_key, {})
        if preview_key and _parent_demo_fallbacks_enabled()
        else {}
    )
    user = account.user
    payment_methods = []
    if account.stripe_customer_id:
        from .stripe_services import list_saved_payment_methods

        try:
            payment_methods = list_saved_payment_methods(account.stripe_customer_id)
        except Exception:
            payment_methods = []
    if not payment_methods:
        payment_methods = demo.get("payment_methods", [])

    return {
        "login_email": user.email,
        "username": display_username(user.username),
        "password_preview": demo.get("password_preview", ""),
        "last_login": _format_last_login(user),
        "autopay_enabled": account.autopay_enabled,
        "autopay_day": account.autopay_day or demo.get("autopay_day", ""),
        "email_receipts": account.email_receipts,
        "email_reminders": account.email_reminders,
        "sms_reminders": account.sms_reminders,
        "payment_methods": payment_methods,
    }


def get_receipts_live(family):
    payments = PortalPayment.objects.filter(family=family, status=PortalPayment.STATUS_PAID).order_by("-paid_at")
    if payments.exists():
        receipts = []
        for payment in payments:
            unit = family.unit if getattr(family, "unit_id", None) else None
            receipts.append(
                {
                    "date": timezone.localtime(payment.paid_at).strftime("%b %d, %Y") if payment.paid_at else "",
                    "reference": payment.receipt_no,
                    "amount": f"{payment.total_charged:.2f}",
                    "method": payment.method_label,
                    "description": _payment_description(payment),
                    "status": "Paid",
                    "location": payment.dropin_location or (unit.name if unit else ""),
                    "child": payment.dropin_child if payment.payment_kind == "dropin" else "",
                    "program": payment.dropin_program,
                }
            )
        return receipts
    preview_key = SEED_PREVIEW_KEYS.get(family.slug)
    if preview_key and _parent_demo_fallbacks_enabled():
        return PARENT_RECEIPTS.get(preview_key, [])
    return []


def _relationship_label(app, prefix):
    if not app:
        return ""
    value = getattr(app, f"{prefix}_relationship", "")
    if not value:
        return ""
    if value == "other":
        return getattr(app, f"{prefix}_relationship_other", "") or "Other"
    display = getattr(app, f"get_{prefix}_relationship_display", None)
    return display() if display else value


def _profile_from_application(family, account):
    from enrollment.models import EnrollmentApplication

    apps = list(
        EnrollmentApplication.objects.filter(portal_family=family)
        .prefetch_related("emergency_contacts")
        .order_by("-submitted_at")
    )
    latest = apps[0] if apps else None
    user = account.user if account else None

    profile = {
        "family_name": family.name,
        "home_address": latest.home_address if latest else "—",
        "primary": {
            "name": family.primary_contact or (user.get_full_name().strip() if user else ""),
            "relationship": _relationship_label(latest, "primary") if latest else "",
            "email": (user.email if user else "") or (latest.primary_email if latest else ""),
            "phone": latest.primary_phone if latest else "",
            "phone_type": latest.get_primary_phone_type_display() if latest else "",
        },
        "secondary": {
            "name": "",
            "relationship": "",
            "email": "",
            "phone": "",
            "phone_type": "",
        },
        "children": [],
        "emergency_contacts": [],
    }

    if latest and latest.secondary_first_name:
        profile["secondary"] = {
            "name": f"{latest.secondary_first_name} {latest.secondary_last_name}".strip(),
            "relationship": _relationship_label(latest, "secondary"),
            "email": latest.secondary_email_address,
            "phone": latest.secondary_phone,
            "phone_type": latest.get_secondary_phone_type_display() if latest.secondary_phone_type else "",
        }

    enrolled_names = set()
    for child in family.children.filter(is_active=True):
        enrolled_names.add(child.name.lower())
        profile["children"].append(
            {
                "name": child.name,
                "dob": "",
                "grade": child.grade,
                "location": family.unit.name if getattr(family, "unit_id", None) else "School 18",
                "program": family.program_label or "After-school program",
                "allergies": "",
                "medications": "",
            }
        )

    for app in apps:
        child_name = f"{app.student_first_name} {app.student_last_name}".strip()
        if child_name.lower() in enrolled_names or app.status == "declined":
            continue
        profile["children"].append(
            {
                "name": child_name,
                "dob": app.student_dob.isoformat(),
                "grade": app.get_student_grade_display(),
                "location": app.get_program_location_display(),
                "program": app.get_program_display(),
                "allergies": "None reported" if app.no_known_allergies else (app.allergies or "—"),
                "medications": "Yes" if app.requires_medication == "yes" else "—",
                "application_status": app.get_status_display(),
            }
        )

    if latest:
        profile["emergency_contacts"] = [
            {
                "name": f"{contact.first_name} {contact.last_name}".strip(),
                "phone": contact.phone,
                "relationship": contact.relationship,
            }
            for contact in latest.emergency_contacts.all()
        ]

    return profile


def _payment_description(payment):
    if payment.payment_kind == "dropin":
        return f"Drop-in — {payment.dropin_child} · {payment.dropin_program}"
    return "Family balance payment"


def get_profile_live(family, account=None):
    if _parent_demo_fallbacks_enabled() and family.slug in SEED_FAMILY_SLUGS:
        demo_profiles = {
            "jacobs": PARENT_PROFILE,
            "martinez": PARENT_PAYMENT_PREVIEWS["4cs"]["profile"],
            "williams": PARENT_PAYMENT_PREVIEWS["scholarship"]["profile"],
        }
        profile = dict(demo_profiles[family.slug])
        profile["family_name"] = family.name
        return profile
    return _profile_from_application(family, account)


def _dashboard_status_for_family(family):
    from enrollment.models import EnrollmentApplication
    from enrollment.portal_integration import STATUS_LABELS

    apps = EnrollmentApplication.objects.filter(portal_family=family).order_by("-submitted_at")
    latest = apps.first()
    if latest:
        return STATUS_LABELS.get(latest.status, "Under review")
    if family.status == "Pending enrollment":
        return "Under review"
    if family.children.filter(is_active=True).exists():
        return "Enrolled"
    return "No active application"


def _policies_counts_for_family(family):
    from enrollment.models import EnrollmentApplication
    from enrollment.policies_data import POLICIES

    apps = EnrollmentApplication.objects.filter(portal_family=family).prefetch_related("policy_signatures")
    if not apps.exists():
        return 0, len(POLICIES)
    signed = sum(app.policy_signatures.count() for app in apps)
    total = len(POLICIES) * apps.count()
    return signed, max(total, signed)


def build_parent_preview_live(family, account):
    from .stripe_services import reconcile_pending_stripe_payments_for_family, stripe_configured

    reconciled = []
    if stripe_configured():
        try:
            reconciled = reconcile_pending_stripe_payments_for_family(family)
        except Exception:
            reconciled = []
    billing = get_billing_live(family)
    profile = get_profile_live(family, account)
    balance = billing["running_balance"]
    policies_signed, policies_total = _policies_counts_for_family(family)
    dashboard = {
        "balance": balance,
        "running_balance": balance,
        "application_status": _dashboard_status_for_family(family),
        "policies_signed": policies_signed,
        "policies_total": policies_total,
        "family_name": family.name,
    }
    return {
        "key": family.slug,
        "label": family.billing_type or "Private pay",
        "family_name": family.name,
        "billing": billing,
        "profile": profile,
        "dashboard": dashboard,
        "stripe_reconciled": reconciled,
    }


def get_parent_policy_data_live(family):
    from enrollment.models import EnrollmentApplication
    from portal.demo_data import POLICIES_PER_CHILD, get_family_policies

    demo = get_family_policies(family.slug) if _parent_demo_fallbacks_enabled() else None
    if demo:
        return demo

    apps = list(
        EnrollmentApplication.objects.filter(portal_family=family)
        .prefetch_related("policy_signatures")
        .order_by("-submitted_at")
    )
    from enrollment.policy_display import get_application_policies

    children = []
    for app in apps:
        child_name = f"{app.student_first_name} {app.student_last_name}".strip()
        policies = get_application_policies(app)
        signed_count = sum(1 for policy in policies if policy["signed"])
        children.append(
            {
                "child_name": child_name,
                "signed_by": f"{app.primary_first_name} {app.primary_last_name}".strip(),
                "signed_count": signed_count,
                "total_count": len(policies),
                "complete": signed_count == len(policies),
                "policies": policies,
            }
        )

    signed_count = sum(child["signed_count"] for child in children)
    total_count = sum(child["total_count"] for child in children)
    return {
        "family_slug": family.slug,
        "family_name": family.name,
        "signed_by": family.primary_contact,
        "program_year": "2026–27",
        "unit": family.unit.name if getattr(family, "unit_id", None) else "School 18",
        "children": children,
        "child_count": len(children),
        "signed_count": signed_count,
        "total_count": total_count,
        "policies_per_child": POLICIES_PER_CHILD,
        "complete": total_count > 0 and signed_count == total_count,
    }


def record_successful_payment(payment, method_label="Card"):
    from django.db import transaction

    with transaction.atomic():
        payment.status = PortalPayment.STATUS_PAID
        payment.method_label = method_label or payment.method_label
        payment.paid_at = timezone.now()
        if not payment.receipt_no:
            payment.receipt_no = _next_receipt_no()
        payment.save()

        family = payment.family
        if payment.payment_kind == "balance":
            family.balance = max(Decimal("0"), family.balance - payment.amount)
            family.save(update_fields=["balance"])
            PortalLedgerEntry.objects.create(
                family=family,
                child_name="",
                date=timezone.localdate(),
                entry_type="payment",
                description=f"Online payment — {method_label}",
                amount=-payment.amount,
            )
        elif payment.payment_kind == "dropin" and payment.dropin_booking_id:
            from dropin.models import DropInBooking

            booking = DropInBooking.objects.filter(pk=payment.dropin_booking_id).first()
            if booking and booking.status == DropInBooking.STATUS_PENDING:
                booking.status = DropInBooking.STATUS_PAID
                booking.paid_at = timezone.now()
                booking.stripe_session_id = payment.stripe_session_id
                booking.save(update_fields=["status", "paid_at", "stripe_session_id"])
        send_payment_receipt_email(payment)
        return payment


def _next_receipt_no():
    today = timezone.localdate().strftime("%y%m%d")
    count = PortalPayment.objects.filter(receipt_no__startswith=f"RCPT-{today}").count() + 1
    return f"RCPT-{today}-{count:03d}"


def payment_to_receipt_dict(payment, preview_key):
    family = payment.family
    unit = family.unit if getattr(family, "unit_id", None) else None
    receipt = {
        "reference": payment.receipt_no,
        "date": timezone.localtime(payment.paid_at).date().isoformat() if payment.paid_at else "",
        "amount": f"{payment.total_charged or payment.amount:.2f}",
        "method": f"Card — {payment.method_label}",
        "description": _payment_description(payment),
        "child": payment.dropin_child if payment.payment_kind == "dropin" else "",
        "program": payment.dropin_program,
        "location": payment.dropin_location or (unit.name if unit else ""),
    }
    return enrich_receipt_for_print(receipt, preview_key, family=family)


def seed_parent_accounts(unit):
    from django.contrib.auth import get_user_model

    from .demo_data import PARENT_ACCOUNT
    from .usernames import display_username, portal_username

    User = get_user_model()
    seed_map = [
        ("jacobs", "private-pay", "jakeraj"),
        ("martinez", "4cs", "mmartinez"),
        ("williams", "scholarship", "dwilliams"),
    ]
    logins = []
    for family_slug, preview_key, default_username in seed_map:
        family = unit.families.filter(slug=family_slug).first()
        if not family:
            continue
        demo_account = PARENT_ACCOUNT.get(preview_key, {})
        username = demo_account.get("username", default_username)
        email = demo_account.get("login_email", f"{username}@example.com")
        password = demo_account.get("password_preview", "ChangeMe2026!")
        user, user_created = User.objects.get_or_create(
            username=portal_username("parent", username),
            defaults={"email": email, "first_name": family.name},
        )
        if user_created:
            user.set_password(password)
            user.save()
        demo_billing = FAMILIES_BILLING.get(family_slug, {})
        account, account_created = PortalParentAccount.objects.get_or_create(
            user=user,
            defaults={
                "family": family,
                "autopay_enabled": demo_account.get("autopay_enabled", False),
                "autopay_day": demo_account.get("autopay_day", ""),
                "email_receipts": demo_account.get("email_receipts", True),
                "email_reminders": demo_account.get("email_reminders", True),
                "sms_reminders": demo_account.get("sms_reminders", False),
            },
        )
        if not account_created:
            account.family = family
            account.autopay_enabled = demo_account.get("autopay_enabled", False)
            account.autopay_day = demo_account.get("autopay_day", "")
            account.email_receipts = demo_account.get("email_receipts", True)
            account.email_reminders = demo_account.get("email_reminders", True)
            account.sms_reminders = demo_account.get("sms_reminders", False)
            account.save()
        if demo_billing.get("running_balance") is not None:
            family.balance = Decimal(str(demo_billing["running_balance"]))
            family.save(update_fields=["balance"])
        if not PortalLedgerEntry.objects.filter(family=family).exists():
            from django.utils.dateparse import parse_date

            for row in demo_billing.get("ledger", []):
                amount = Decimal(str(row["amount"]).replace("-", ""))
                if row["type"] in ("payment", "discount"):
                    amount = -amount
                PortalLedgerEntry.objects.create(
                    family=family,
                    child_name=row.get("child", ""),
                    date=parse_date(row["date"]) if isinstance(row["date"], str) else row["date"],
                    entry_type=row["type"],
                    description=row["description"],
                    amount=amount,
                    is_manual=row.get("manual", False),
                )
        logins.append((display_username(user.username), password, family.name))
    return logins


def get_parent_user_display(account, preview):
    if account:
        user = account.user
        name = user.get_full_name().strip() or user.first_name.strip() or account.family.name
        return name or user.username
    return preview.get("family_name", "Parent")


def get_parent_avatar_initials(display_name):
    parts = [part for part in display_name.split() if part]
    if len(parts) >= 2:
        return f"{parts[0][0]}{parts[-1][0]}".upper()
    if parts:
        return parts[0][:2].upper()
    return "P"


def get_parent_avatar_context(account, preview):
    display_name = get_parent_user_display(account, preview)
    photo_url = ""
    if account and account.profile_photo:
        photo_url = account.profile_photo.url
    return {
        "display_name": display_name,
        "initials": get_parent_avatar_initials(display_name),
        "photo_url": photo_url,
    }


def preview_key_for_family(family):
    return SEED_PREVIEW_KEYS.get(family.slug, family.slug)


def get_parent_billing_for_request(family, preview_key):
    if family:
        return get_billing_live(family)
    return PARENT_PAYMENT_PREVIEWS.get(preview_key, PARENT_PAYMENT_PREVIEWS["private-pay"])["billing"]


def get_parent_announcement_live(family):
    from .models import PortalAnnouncement

    preview_key = SEED_PREVIEW_KEYS.get(family.slug)
    if preview_key and _parent_demo_fallbacks_enabled():
        demo = PARENT_ANNOUNCEMENTS.get(preview_key)
        if demo:
            return demo
    for announcement in PortalAnnouncement.objects.filter(unit=family.unit, status="Published").order_by(
        "-posted_date"
    ):
        if "Portal banner" in (announcement.channels or []):
            return {
                "active": True,
                "title": announcement.title,
                "body": announcement.body,
                "style": announcement.style,
                "posted": announcement.posted_date.strftime("%b %d, %Y") if announcement.posted_date else "—",
                "unit": family.unit.name if getattr(family, "unit_id", None) else "",
            }
    return {}


def get_tax_eligibility_live(family):
    preview_key = SEED_PREVIEW_KEYS.get(family.slug, family.slug)
    demo = TAX_STATEMENT_ELIGIBILITY.get(preview_key) if _parent_demo_fallbacks_enabled() else None
    balance = f"{family.balance:.2f}"
    require_zero = TAX_STATEMENT_SETTINGS.get("require_zero_balance", True)
    if require_zero and family.balance > 0:
        return {
            "eligible": False,
            "balance": balance,
            "reason": "Pay your remaining balance before downloading your tax statement.",
        }
    paid_total = PortalPayment.objects.filter(
        family=family,
        status=PortalPayment.STATUS_PAID,
        payment_kind="balance",
    ).aggregate(total=models.Sum("amount"))["total"] or Decimal("0")
    if paid_total <= 0:
        if demo:
            return demo
        return {
            "eligible": False,
            "balance": balance,
            "reason": "No qualifying payments yet for this tax year.",
            "paid_total": "0.00",
        }
    return {"eligible": True, "balance": balance, "reason": "", "paid_total": f"{paid_total:.2f}"}


def get_tax_statement_data(family):
    from django.db.models import Sum

    tax_year = TAX_STATEMENT_SETTINGS.get("tax_year", str(timezone.localdate().year - 1))
    payments = PortalPayment.objects.filter(
        family=family,
        status=PortalPayment.STATUS_PAID,
        paid_at__year=int(tax_year),
    ).order_by("-paid_at")
    rows = [
        {
            "date": timezone.localtime(p.paid_at).strftime("%b %d, %Y") if p.paid_at else "",
            "reference": p.receipt_no,
            "description": _payment_description(p),
            "amount": f"{p.total_charged or p.amount:.2f}",
        }
        for p in payments
    ]
    total = payments.aggregate(total=Sum("amount"))["total"] or Decimal("0")
    return {
        "family_name": family.name,
        "tax_year": tax_year,
        "rows": rows,
        "total": f"{total:.2f}",
        "generated": timezone.localdate().isoformat(),
    }


def get_pending_profile_changes(account):
    return list(
        account.change_requests.filter(status=PortalProfileChangeRequest.STATUS_PENDING).values(
            "pk", "changes", "submitted_at"
        )
    )


def submit_profile_change_request(account, changes):
    if not changes:
        raise ValueError("No changes to submit.")
    return PortalProfileChangeRequest.objects.create(account=account, changes=changes)


def update_account_settings(account, data):
    user = account.user
    if data.get("email"):
        user.email = data["email"].strip()
        user.save(update_fields=["email"])
    if data.get("new_password"):
        user.set_password(data["new_password"])
        user.save(update_fields=["password"])
    account.autopay_enabled = bool(data.get("autopay_enabled"))
    account.autopay_day = data.get("autopay_day", account.autopay_day)
    account.email_receipts = bool(data.get("email_receipts", account.email_receipts))
    account.email_reminders = bool(data.get("email_reminders", account.email_reminders))
    account.sms_reminders = bool(data.get("sms_reminders", account.sms_reminders))
    account.save()
    return account


def sign_policy_for_family(family, child_name, policy_slug, signature_name):
    from enrollment.models import EnrollmentApplication, PolicySignature
    from enrollment.policies_data import POLICIES

    policy = next((p for p in POLICIES if p["slug"] == policy_slug), None)
    if not policy:
        raise ValueError("Policy not found.")
    app = (
        EnrollmentApplication.objects.filter(portal_family=family)
        .filter(student_first_name__icontains=child_name.split()[0])
        .order_by("-submitted_at")
        .first()
    )
    if not app:
        raise ValueError("No application found for this child.")
    PolicySignature.objects.update_or_create(
        application=app,
        policy_slug=policy_slug,
        defaults={
            "policy_title": policy["title"],
            "signature_name": signature_name.strip(),
            "signed_date": timezone.localdate(),
        },
    )
    return app


def send_payment_receipt_email(payment):
    account = getattr(payment.family, "parent_account", None)
    if not account or not account.email_receipts:
        return
    user = account.user
    if not user.email:
        return
    from django.conf import settings
    from django.core.mail import send_mail

    subject = f"YEA payment receipt — {payment.receipt_no}"
    body = (
        f"Thank you for your payment.\n\n"
        f"Receipt: {payment.receipt_no}\n"
        f"Amount: ${payment.total_charged or payment.amount:.2f}\n"
        f"Description: {_payment_description(payment)}\n\n"
        f"View all receipts in your parent portal."
    )
    send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [user.email], fail_silently=True)


def _drop_in_offered():
    from dropin.models import DropInDayCapacity

    return DropInDayCapacity.objects.exists()


def _drop_in_program_catalog():
    from dropin import constants

    fees = {
        "after_school": f"{constants.FEE_DOLLARS[constants.PROGRAM_AFTER_SCHOOL]:.0f}",
        "summer_camp": f"{constants.FEE_DOLLARS[constants.PROGRAM_SUMMER_CAMP]:.0f}",
    }
    deadlines = {
        "after_school": constants.DEADLINE_LABEL[constants.PROGRAM_AFTER_SCHOOL],
        "summer_camp": constants.DEADLINE_LABEL[constants.PROGRAM_SUMMER_CAMP],
    }
    locations = [label for _, label in constants.LOCATION_CHOICES]
    return fees, deadlines, locations


def get_drop_in_live(account):
    from dropin import constants
    from dropin.models import DropInBooking, DropInFamilyProfile, DropInWaitlistEntry

    preview_key = SEED_PREVIEW_KEYS.get(account.family.slug)
    if preview_key and preview_key in PARENT_DROP_IN and _parent_demo_fallbacks_enabled():
        data = dict(PARENT_DROP_IN[preview_key])
        data.setdefault("offered", True)
        data.setdefault("show_program_details", True)
        profile = getattr(account.user, "dropin_profile", None)
        if profile:
            data["status"] = profile.status
            data["status_label"] = profile.get_status_display()
            data["registered"] = True
        return data

    profile = getattr(account.user, "dropin_profile", None)
    fees, deadlines, locations = _drop_in_program_catalog()
    offered = _drop_in_offered()

    if not profile:
        return {
            "status": "not_registered",
            "status_label": "Not registered",
            "registered": False,
            "offered": offered,
            "show_program_details": False,
            "fees": fees,
            "deadlines": deadlines,
            "locations": locations,
            "bookings": [],
            "waitlist": [],
            "children": [_child_option(c) for c in account.family.children.filter(is_active=True)],
        }

    bookings = []
    for booking in profile.bookings.filter(status=DropInBooking.STATUS_PAID).order_by("-date")[:20]:
        bookings.append(
            {
                "date": booking.date.strftime("%b %d, %Y"),
                "child": str(booking.child),
                "program": booking.get_program_display(),
                "location": booking.get_location_display(),
                "status": "Confirmed",
                "amount": f"{booking.amount_cents / 100:.2f}",
                "reference": str(booking.reference),
            }
        )
    waitlist = []
    for entry in profile.waitlist_entries.filter(status=DropInWaitlistEntry.STATUS_WAITING).order_by("-date")[:10]:
        waitlist.append(
            {
                "date": entry.date.strftime("%b %d, %Y"),
                "child": str(entry.child),
                "program": entry.get_program_display(),
                "location": entry.get_location_display(),
                "requested": timezone.localtime(entry.created_at).strftime("%b %d, %Y"),
            }
        )
    return {
        "status": profile.status,
        "status_label": profile.get_status_display(),
        "registered": True,
        "offered": offered,
        "show_program_details": offered,
        "fees": fees,
        "deadlines": deadlines,
        "locations": locations,
        "bookings": bookings,
        "waitlist": waitlist,
        "children": [_child_option(c) for c in profile.children.all()],
    }


def _child_option(child):
    return {"id": child.pk, "name": str(child)}


def ensure_dropin_profile(account):
    from dropin.models import DropInChild, DropInFamilyProfile

    profile = getattr(account.user, "dropin_profile", None)
    if profile:
        return profile
    family = account.family
    user = account.user
    parts = (family.primary_contact or user.get_full_name() or user.username).split()
    first = parts[0] if parts else user.first_name or "Parent"
    last = parts[-1] if len(parts) > 1 else user.last_name or family.name
    profile = DropInFamilyProfile.objects.create(
        user=user,
        family_name=family.name,
        primary_email=user.email,
        home_address="—",
        primary_first_name=first,
        primary_last_name=last,
        primary_phone="—",
        status=DropInFamilyProfile.STATUS_PENDING,
    )
    for child in family.children.filter(is_active=True):
        name_parts = child.name.split()
        DropInChild.objects.create(
            profile=profile,
            first_name=name_parts[0],
            last_name=" ".join(name_parts[1:]) if len(name_parts) > 1 else family.name,
            gender="female",
            date_of_birth=timezone.localdate(),
            grade="1",
            school=family.unit.name if getattr(family, "unit_id", None) else "School 18",
        )
    return profile


def seed_dropin_profiles(unit):
    from datetime import timedelta

    from dropin import constants
    from dropin.models import DropInChild, DropInDayCapacity, DropInFamilyProfile

    for account in PortalParentAccount.objects.filter(family__unit=unit):
        profile = ensure_dropin_profile(account)
        if account.family.slug in SEED_FAMILY_SLUGS and profile.status != DropInFamilyProfile.STATUS_APPROVED:
            profile.status = DropInFamilyProfile.STATUS_APPROVED
            profile.approved_at = timezone.now()
            profile.save(update_fields=["status", "approved_at"])
        if not profile.children.exists():
            for child in account.family.children.filter(is_active=True):
                name_parts = child.name.split()
                DropInChild.objects.create(
                    profile=profile,
                    first_name=name_parts[0],
                    last_name=" ".join(name_parts[1:]) if len(name_parts) > 1 else account.family.name,
                    gender="female",
                    date_of_birth=timezone.localdate(),
                    grade="1",
                    school=unit.name,
                )

    today = timezone.localdate()
    for offset in range(45):
        care_date = today + timedelta(days=offset)
        for location in constants.AFTER_SCHOOL_LOCATIONS:
            DropInDayCapacity.objects.get_or_create(
                program=constants.PROGRAM_AFTER_SCHOOL,
                location=location,
                date=care_date,
                defaults={"max_slots": 12},
            )


def book_dropin_live(account, child_name, program_key, location_label, care_date):
    from dropin import constants
    from dropin.models import DropInBooking, DropInWaitlistEntry
    from dropin.services import validate_booking, validate_waitlist_join

    profile = ensure_dropin_profile(account)
    child = profile.children.filter(first_name__icontains=child_name.split()[0]).first()
    if not child:
        raise ValueError("Child not found on your drop-in registration.")

    program = constants.PROGRAM_AFTER_SCHOOL if program_key != "summer" else constants.PROGRAM_SUMMER_CAMP
    location = _portal_location_key(location_label)
    ok, message = validate_booking(program, location, care_date, child, profile=profile)
    if not ok:
        ok_wait, _ = validate_waitlist_join(program, location, care_date, child, profile=profile)
        if ok_wait:
            DropInWaitlistEntry.objects.get_or_create(
                profile=profile,
                child=child,
                program=program,
                location=location,
                date=care_date,
                defaults={"status": DropInWaitlistEntry.STATUS_WAITING},
            )
            raise ValueError("That day is full — you were added to the waitlist.")
        raise ValueError(message)

    amount_cents = int(constants.FEE_DOLLARS[program] * 100)
    booking = DropInBooking.objects.create(
        profile=profile,
        child=child,
        program=program,
        location=location,
        date=care_date,
        amount_cents=amount_cents,
        status=DropInBooking.STATUS_PENDING,
    )
    return booking


def _portal_location_key(label):
    from dropin import constants

    label = (label or "").strip().lower()
    for key, display in constants.LOCATION_CHOICES:
        if display.lower().startswith(label) or label in display.lower():
            return key
    mapping = {
        "school 18": "school_18",
        "school 26": "school_26",
        "dale ave": "dale_ave",
        "caldwell": "caldwell",
    }
    for fragment, key in mapping.items():
        if fragment in label:
            return key
    raise ValueError("Select a valid location.")
