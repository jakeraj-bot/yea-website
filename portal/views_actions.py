from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_time
from django.views.decorators.http import require_POST

from .staff_auth import admin_login_required_post, staff_login_required_post

from .attendance_service import portal_is_live, ensure_portal_seeded, get_unit
from .live_services import (
    create_incident_live,
    create_message_thread_live,
    create_support_ticket_live,
    reply_support_ticket_live,
    save_announcement_live,
    save_newsletter_live,
    send_team_message_live,
)


PREVIEW_FAMILY_SLUG = {
    "private-pay": "jacobs",
    "4cs": "martinez",
    "scholarship": "williams",
}


def _needs_live(request):
    if not portal_is_live() or not ensure_portal_seeded():
        messages.error(request, "Run python manage.py seed_portal to enable partially live mode.")
        return False
    return True


def _admin_needs_live(request):
    if not portal_is_live():
        messages.error(request, "Portal admin saves are disabled in preview mode.")
        return False
    return True


@require_POST
def staff_incident_save(request):
    if not _needs_live(request):
        return redirect("portal_staff_page", page="incidents")
    parent_notified = request.POST.get("parent_notified") == "yes"
    notified_time = parse_time(request.POST.get("parent_notified_time") or "") if parent_notified else None
    try:
        incident = create_incident_live(
            {
                "child_name": request.POST.get("child_name"),
                "date": parse_date(request.POST.get("date")),
                "time": parse_time(request.POST.get("time") or ""),
                "incident_type": request.POST.get("incident_type"),
                "severity": request.POST.get("severity"),
                "summary": request.POST.get("summary"),
                "location": request.POST.get("location", ""),
                "details": request.POST.get("details", ""),
                "follow_up": request.POST.get("follow_up", ""),
                "parent_notified": parent_notified,
                "parent_notified_time": notified_time,
            }
        )
        messages.success(request, f"Saved incident for {incident['child']}.")
    except Exception as exc:
        messages.error(request, str(exc))
    return redirect("portal_staff_page", page="incidents")


@require_POST
def support_ticket_create(request):
    if not _needs_live(request):
        return redirect("portal_home")
    area = request.POST.get("from_area", "staff")
    preview_key = request.POST.get("preview_key", "private-pay")
    preview_family = PREVIEW_FAMILY_SLUG.get(preview_key, preview_key)
    if area == "parent":
        from .parent_auth import get_parent_account

        account = get_parent_account(request.user)
        if account:
            preview_family = account.family.slug
    from_name = request.POST.get("from_name") or ("Staff user" if area == "staff" else "Parent user")
    try:
        create_support_ticket_live(
            area,
            preview_family if area == "parent" else "",
            {
                "subject": request.POST.get("subject"),
                "body": request.POST.get("body"),
                "category": request.POST.get("category", "other"),
                "from_name": from_name,
                "from_detail": request.POST.get("from_detail", ""),
                "role": "Parent" if area == "parent" else "Staff",
            },
            files=request.FILES.getlist("attachments"),
        )
        messages.success(request, "Support ticket submitted.")
    except Exception as exc:
        messages.error(request, str(exc))
    if area == "parent":
        return redirect(reverse("portal_parent_page", kwargs={"page": "support"}))
    return redirect("portal_staff_page", page="support")


@require_POST
def support_ticket_reply(request):
    if not _needs_live(request):
        return redirect("portal_home")
    ticket_id = request.POST.get("ticket_id")
    area = request.POST.get("from_area", "admin")
    preview_key = request.POST.get("preview_key", "private-pay")
    is_admin = area == "admin"
    try:
        reply_support_ticket_live(
            ticket_id,
            request.POST.get("body", ""),
            is_admin=is_admin,
            author=request.POST.get("author") or ("YEA Support" if is_admin else "Portal user"),
            role="Admin" if is_admin else request.POST.get("role", "Staff"),
            files=request.FILES.getlist("attachments"),
        )
        messages.success(request, "Reply sent.")
    except Exception as exc:
        messages.error(request, str(exc))
    if area == "parent":
        url = reverse("portal_parent_page", kwargs={"page": "support"})
        if ticket_id:
            url = f"{url}?ticket={ticket_id}"
        return redirect(url)
    if area == "admin":
        return redirect(f"{reverse('portal_admin_page', kwargs={'page': 'support'})}?ticket={ticket_id}")
    return redirect(f"{reverse('portal_staff_page', kwargs={'page': 'support'})}?ticket={ticket_id}")


@require_POST
def team_message_send(request):
    if not _needs_live(request):
        return redirect("portal_home")
    area = request.POST.get("portal_area", "staff")
    thread_id = request.POST.get("thread_id")
    body = request.POST.get("body", "")
    try:
        if thread_id:
            send_team_message_live(
                thread_id,
                body,
                is_admin=(area == "admin"),
                author="Admin" if area == "admin" else "Staff",
                role="Admin" if area == "admin" else "Unit staff",
            )
        else:
            create_message_thread_live(
                {
                    "subject": request.POST.get("subject"),
                    "body": body,
                    "category": request.POST.get("category", "general"),
                    "priority": request.POST.get("priority", "normal"),
                    "author": "Admin" if area == "admin" else "Staff",
                    "role": "Admin" if area == "admin" else "Unit staff",
                },
                is_admin=(area == "admin"),
            )
        messages.success(request, "Message sent.")
    except Exception as exc:
        messages.error(request, str(exc))
    if area == "admin":
        url = reverse("portal_admin_page", kwargs={"page": "messages"})
    else:
        url = reverse("portal_staff_page", kwargs={"page": "messages"})
    if thread_id:
        url = f"{url}?thread={thread_id}"
    return redirect(url)


@admin_login_required_post
@require_POST
def admin_announcement_save(request):
    if not _admin_needs_live(request):
        return redirect("portal_admin_page", page="communications")
    legacy_id = request.POST.get("legacy_id") or None
    channels = []
    if request.POST.get("channel_banner"):
        channels.append("Portal banner")
    if request.POST.get("channel_email"):
        channels.append("Email")
    try:
        status = request.POST.get("status", "Draft")
        posted_date = parse_date(request.POST.get("posted_date") or "")
        if status == "Published" and not posted_date:
            posted_date = timezone.localdate()
        save_announcement_live(
            {
                "title": request.POST.get("title"),
                "body": request.POST.get("body", ""),
                "body_html": request.POST.get("body_html", ""),
                "audience": request.POST.get("audience", ""),
                "channels": channels or ["Portal banner"],
                "status": status,
                "style": request.POST.get("style", "info"),
                "posted_date": posted_date if status == "Published" else None,
            },
            legacy_id=legacy_id,
        )
        messages.success(request, "Announcement saved.")
    except Exception as exc:
        messages.error(request, str(exc))
    return redirect("portal_admin_page", page="communications")


@admin_login_required_post
@require_POST
def admin_newsletter_save(request):
    if not _admin_needs_live(request):
        return redirect("portal_admin_page", page="communications")
    legacy_id = request.POST.get("legacy_id") or None
    try:
        status = request.POST.get("status", "Draft")
        sent_date = parse_date(request.POST.get("sent_date") or "")
        if status == "Sent" and not sent_date:
            sent_date = timezone.localdate()
        save_newsletter_live(
            {
                "title": request.POST.get("title"),
                "template_id": request.POST.get("template_id", "weekly-unit"),
                "subject": request.POST.get("subject", ""),
                "body": request.POST.get("body", ""),
                "sections": [
                    {
                        "title": request.POST.get("section_1_title", ""),
                        "body": request.POST.get("section_1_body", ""),
                        "image": request.POST.get("section_1_image", ""),
                    },
                    {
                        "title": request.POST.get("section_2_title", ""),
                        "body": request.POST.get("section_2_body", ""),
                        "image": request.POST.get("section_2_image", ""),
                    },
                ],
                "status": status,
                "sent_date": sent_date if status == "Sent" else None,
                "recipients_label": request.POST.get("recipients_label", "—"),
            },
            legacy_id=legacy_id,
        )
        messages.success(request, "Newsletter saved.")
    except Exception as exc:
        messages.error(request, str(exc))
    edit = request.POST.get("legacy_id")
    if edit:
        return redirect(f"{reverse('portal_admin_page', kwargs={'page': 'communications'})}?edit={edit}")
    return redirect("portal_admin_page", page="communications")


@admin_login_required_post
@require_POST
def admin_announcement_delete(request):
    from .models import PortalAnnouncement

    if not _admin_needs_live(request):
        return redirect("portal_admin_page", page="communications")
    legacy_id = request.POST.get("legacy_id")
    try:
        deleted, _ = PortalAnnouncement.objects.filter(legacy_id=legacy_id).delete()
        if deleted:
            messages.success(request, "Announcement deleted.")
        else:
            messages.error(request, "Announcement not found.")
    except Exception as exc:
        messages.error(request, str(exc))
    return redirect("portal_admin_page", page="communications")


def _perm_yes(post, key):
    return post.get(key, "no") in ("yes", "on", "1", "true")


@admin_login_required_post
@require_POST
def admin_billing_permissions(request):
    from .admin_config import get_charge_types_admin
    from .admin_services import save_billing_permissions
    from .models import PortalStaffAccount

    if not _admin_needs_live(request):
        return redirect("portal_admin_page", page="billing-permissions")
    charge_types = get_charge_types_admin()
    updated = 0
    try:
        for account in PortalStaffAccount.objects.all():
            sid = account.pk
            charge_perms = {}
            for ct in charge_types:
                charge_perms[ct["value"]] = _perm_yes(request.POST, f"charge_{ct['value']}_{sid}")
            save_billing_permissions(
                sid,
                _perm_yes(request.POST, f"add_charge_{sid}"),
                _perm_yes(request.POST, f"delete_charge_{sid}"),
                _perm_yes(request.POST, f"add_credit_{sid}"),
                _perm_yes(request.POST, f"edit_plans_{sid}"),
                charge_perms,
            )
            updated += 1
        messages.success(request, f"Billing permissions saved for {updated} staff member(s).")
    except Exception as exc:
        messages.error(request, str(exc))
    return redirect("portal_admin_page", page="billing-permissions")


@admin_login_required_post
@require_POST
def admin_staff_invite(request):
    from .admin_services import invite_staff_user

    if not _admin_needs_live(request):
        return redirect("portal_admin_page", page="staff")
    role = request.POST.get("role", "Unit staff")
    password = request.POST.get("password", "").strip()
    if password and len(password) < 8:
        messages.error(request, "Password must be at least 8 characters.")
        return redirect("portal_admin_page", page="staff")
    try:
        account, created, temp_password, username = invite_staff_user(
            request.POST.get("name", "").strip(),
            request.POST.get("email", "").strip(),
            role,
            unit_slug=request.POST.get("unit_slug") or None,
            unit_slugs=request.POST.getlist("unit_slugs"),
            all_units_access=request.POST.get("all_units_access") == "on" or role == "Portal admin",
            password=password or None,
        )
        if created and temp_password:
            login_path = "/portal/admin/login/" if role == "Portal admin" else "/portal/staff/login/"
            portal_label = "admin portal" if role == "Portal admin" else "staff portal"
            messages.success(
                request,
                f"Account created for {account.display_name}. "
                f"Sign-in username: {username} · Password: {temp_password} "
                f"(share privately — sign in at {login_path} for the {portal_label})",
            )
        elif temp_password:
            messages.success(
                request,
                f"Updated {account.display_name} and set a new password.",
            )
        else:
            messages.success(request, f"Staff account updated for {account.display_name}.")
    except Exception as exc:
        messages.error(request, str(exc))
    return redirect("portal_admin_page", page="staff")


@admin_login_required_post
@require_POST
def admin_admin_invite(request):
    from .admin_services import invite_admin_user

    if not _admin_needs_live(request):
        return redirect("portal_admin_page", page="staff")
    password = request.POST.get("password", "").strip()
    if password and len(password) < 8:
        messages.error(request, "Password must be at least 8 characters.")
        return redirect("portal_admin_page", page="staff")
    try:
        account, created, temp_password, username = invite_admin_user(
            request.POST.get("name", "").strip(),
            request.POST.get("username", "").strip(),
            request.POST.get("email", "").strip(),
            password=password or None,
        )
        messages.success(
            request,
            f"Admin portal login created for {account.display_name}. "
            f"Sign-in username: {username} · Password: {temp_password} "
            f"(share privately — sign in at /portal/admin/login/)",
        )
    except Exception as exc:
        messages.error(request, str(exc))
    return redirect("portal_admin_page", page="staff")


@admin_login_required_post
@require_POST
def admin_bulk_billing_post(request):
    from django.urls import reverse

    from .billing_services import build_bulk_charge_preview, default_entry_date, post_bulk_charges

    redirect_url = reverse("portal_admin_page", kwargs={"page": "member-billing"})
    if not _admin_needs_live(request):
        return redirect(redirect_url)

    unit_slug = request.POST.get("unit", "").strip() or None
    charge_mode = request.POST.get("mode", "weekly_tuition")
    billing_filter = request.POST.get("billing_type", "").strip()
    custom_amount = request.POST.get("custom_amount", "")
    custom_description = request.POST.get("custom_description", "")
    entry_date = parse_date(request.POST.get("date") or "") or default_entry_date()

    try:
        rows = build_bulk_charge_preview(
            unit_slug=unit_slug,
            charge_mode=charge_mode,
            billing_filter=billing_filter,
            custom_amount=custom_amount or None,
            custom_description=custom_description,
        )
        if not rows:
            raise ValueError("No matching members to charge. Adjust filters and try again.")
        posted = post_bulk_charges(rows, entry_date)
        total = sum(row["amount"] for row in rows)
        messages.success(
            request,
            f"Posted {posted} charge(s) totaling ${total:.2f} for {entry_date.isoformat()}.",
        )
    except ValueError as exc:
        messages.error(request, str(exc))

    return redirect(redirect_url)


@admin_login_required_post
@require_POST
def admin_staff_edit(request):
    from .admin_services import update_staff_user

    if not _admin_needs_live(request):
        return redirect("portal_admin_page", page="staff")
    try:
        account, new_password = update_staff_user(request.POST.get("staff_id"), request.POST)
        if new_password:
            messages.success(request, f"Updated {account.display_name} and set a new password.")
        else:
            messages.success(request, f"Updated {account.display_name}.")
    except Exception as exc:
        messages.error(request, str(exc))
    edit_id = request.POST.get("staff_id")
    if edit_id:
        return redirect(f"{reverse('portal_admin_page', kwargs={'page': 'staff'})}?edit={edit_id}")
    return redirect("portal_admin_page", page="staff")


@admin_login_required_post
@require_POST
def admin_staff_role_create(request):
    from .admin_config import save_custom_role

    if not _admin_needs_live(request):
        return redirect("portal_admin_page", page="staff")
    try:
        role, created = save_custom_role(request.POST.get("role_name", ""))
        if created:
            messages.success(request, f"Role “{role.name}” created. Set default permissions in Billing permissions.")
        else:
            messages.info(request, f"Role “{role.name}” already exists.")
    except Exception as exc:
        messages.error(request, str(exc))
    return redirect("portal_admin_page", page="staff")


@admin_login_required_post
@require_POST
def admin_default_rule_save(request):
    from .admin_config import save_default_billing_rule

    if not _admin_needs_live(request):
        return redirect("portal_admin_page", page="billing-permissions")
    try:
        save_default_billing_rule(request.POST)
        messages.success(request, "Default rule saved.")
    except Exception as exc:
        messages.error(request, str(exc))
    return redirect("portal_admin_page", page="billing-permissions")


@admin_login_required_post
@require_POST
def admin_waive_charge(request):
    from .admin_config import waive_absence_charge

    if not _admin_needs_live(request):
        return redirect("portal_admin_page", page="dashboard")
    try:
        waive_absence_charge(
            request.POST.get("family_slug", ""),
            request.POST.get("child_name", ""),
            request.POST.get("week_label", ""),
            request.POST.get("charge_description", ""),
            request.POST.get("amount", "0"),
        )
        messages.success(request, "Charge waived for this week.")
    except Exception as exc:
        messages.error(request, str(exc))
    return redirect("portal_admin_page", page="dashboard")


@admin_login_required_post
@require_POST
def admin_unit_save(request):
    from .admin_config import save_unit

    if not _admin_needs_live(request):
        return redirect("portal_admin_page", page="units")
    try:
        unit_pk = request.POST.get("unit_id") or None
        save_unit(request.POST, unit_pk=int(unit_pk) if unit_pk else None)
        messages.success(request, "Unit saved.")
    except Exception as exc:
        messages.error(request, str(exc))
    return redirect("portal_admin_page", page="units")


@admin_login_required_post
@require_POST
def admin_unit_action(request):
    from .admin_config import delete_unit, set_unit_active

    if not _admin_needs_live(request):
        return redirect("portal_admin_page", page="units")
    action = request.POST.get("action", "")
    unit_id = request.POST.get("unit_id")
    try:
        if action == "delete":
            delete_unit(unit_id)
            messages.success(request, "Unit deleted permanently.")
        else:
            set_unit_active(unit_id, action == "activate")
            messages.success(request, "Unit status updated.")
    except Exception as exc:
        messages.error(request, str(exc))
    return redirect("portal_admin_page", page="units")


@admin_login_required_post
@require_POST
def admin_program_save(request):
    from .admin_config import save_program

    if not _admin_needs_live(request):
        return redirect("portal_admin_page", page="programs")
    try:
        data = request.POST.copy()
        data["unit_slugs"] = request.POST.getlist("unit_slugs")
        save_program(data, program_name=request.POST.get("program_name") or None)
        messages.success(request, "Program saved.")
    except Exception as exc:
        messages.error(request, str(exc))
    return redirect("portal_admin_page", page="programs")


@admin_login_required_post
@require_POST
def admin_program_delete(request):
    from .admin_config import delete_program

    if not _admin_needs_live(request):
        return redirect("portal_admin_page", page="programs")
    try:
        ids = [int(x) for x in request.POST.getlist("program_ids") if str(x).isdigit()]
        delete_program(ids)
        messages.success(request, "Program removed.")
    except Exception as exc:
        messages.error(request, str(exc))
    return redirect("portal_admin_page", page="programs")


@admin_login_required_post
@require_POST
def admin_agency_save(request):
    from .admin_config import save_agency

    if not _admin_needs_live(request):
        return redirect("portal_admin_page", page="agencies")
    try:
        agency_pk = request.POST.get("agency_id") or None
        save_agency(request.POST, agency_pk=int(agency_pk) if agency_pk else None)
        messages.success(request, "Agency saved.")
    except Exception as exc:
        messages.error(request, str(exc))
    return redirect("portal_admin_page", page="agencies")


@admin_login_required_post
@require_POST
def admin_scholarship_save(request):
    from .admin_config import save_scholarship_assignment

    if not _admin_needs_live(request):
        return redirect("portal_admin_page", page="scholarships")
    try:
        pk = request.POST.get("assignment_id") or None
        save_scholarship_assignment(request.POST, assignment_pk=int(pk) if pk else None)
        messages.success(request, "Scholarship assignment saved.")
    except Exception as exc:
        messages.error(request, str(exc))
    return redirect("portal_admin_page", page="scholarships")


@admin_login_required_post
@require_POST
def admin_fee_save(request):
    from .admin_config import save_fee_rule

    if not _admin_needs_live(request):
        return redirect("portal_admin_page", page="fees")
    try:
        save_fee_rule(int(request.POST.get("fee_id")), request.POST)
        messages.success(request, "Fee rule updated.")
    except Exception as exc:
        messages.error(request, str(exc))
    return redirect("portal_admin_page", page="fees")


@admin_login_required_post
@require_POST
def admin_payment_plan_save(request):
    from .admin_config import save_payment_plan

    if not _admin_needs_live(request):
        return redirect("portal_admin_page", page="fees")
    pk = request.POST.get("plan_id") or None
    try:
        save_payment_plan(request.POST, plan_pk=int(pk) if pk else None)
        messages.success(request, "Payment plan saved.")
    except Exception as exc:
        messages.error(request, str(exc))
    return redirect("portal_admin_page", page="fees")


@admin_login_required_post
@require_POST
def admin_payment_plan_delete(request):
    from .admin_config import delete_payment_plan

    if not _admin_needs_live(request):
        return redirect("portal_admin_page", page="fees")
    try:
        delete_payment_plan(int(request.POST.get("plan_id")))
        messages.success(request, "Payment plan deleted.")
    except Exception as exc:
        messages.error(request, str(exc))
    return redirect("portal_admin_page", page="fees")


@admin_login_required_post
@require_POST
def admin_processing_fee_save(request):
    from .admin_config import save_processing_fee

    if not _admin_needs_live(request):
        return redirect("portal_admin_page", page="fees")
    pk = request.POST.get("fee_id") or None
    try:
        save_processing_fee(request.POST, fee_pk=int(pk) if pk else None)
        messages.success(request, "Processing fee saved.")
    except Exception as exc:
        messages.error(request, str(exc))
    return redirect("portal_admin_page", page="fees")


@admin_login_required_post
@require_POST
def admin_processing_fee_delete(request):
    from .admin_config import delete_processing_fee

    if not _admin_needs_live(request):
        return redirect("portal_admin_page", page="fees")
    try:
        delete_processing_fee(int(request.POST.get("fee_id")))
        messages.success(request, "Processing fee deleted.")
    except Exception as exc:
        messages.error(request, str(exc))
    return redirect("portal_admin_page", page="fees")


@admin_login_required_post
@require_POST
def admin_tax_settings_save(request):
    from .admin_config import save_tax_settings

    if not _admin_needs_live(request):
        return redirect("portal_admin_page", page="fees")
    try:
        save_tax_settings(request.POST)
        messages.success(request, "Tax statement settings saved.")
    except Exception as exc:
        messages.error(request, str(exc))
    return redirect("portal_admin_page", page="fees")


@admin_login_required_post
@require_POST
def admin_checkin_save(request):
    from .admin_config import save_checkin_settings

    if not _admin_needs_live(request):
        return redirect("portal_admin_page", page="checkin-settings")
    try:
        save_checkin_settings(request.POST)
        messages.success(request, "Check-in settings saved.")
    except Exception as exc:
        messages.error(request, str(exc))
    return redirect("portal_admin_page", page="checkin-settings")


@admin_login_required_post
@require_POST
def admin_policy_create(request):
    from .admin_config import create_org_policy

    if not _admin_needs_live(request):
        return redirect("portal_admin_page", page="member-policies")
    try:
        policy = create_org_policy(
            request.POST.get("title", ""),
            request.POST.get("body", ""),
            notify_families=request.POST.get("notify_parents") == "on",
        )
        messages.success(request, f"Policy “{policy.title}” added — parents will see a signing alert.")
    except Exception as exc:
        messages.error(request, str(exc))
    return redirect("portal_admin_page", page="member-policies")


@admin_login_required_post
@require_POST
def admin_newsletter_delete(request):
    from .models import PortalNewsletter

    if not _admin_needs_live(request):
        return redirect("portal_admin_page", page="communications")
    legacy_id = request.POST.get("legacy_id")
    try:
        nl = PortalNewsletter.objects.filter(legacy_id=legacy_id).first()
        if nl:
            nl.delete()
            messages.success(request, "Newsletter deleted.")
        else:
            messages.error(request, "Newsletter not found.")
    except Exception as exc:
        messages.error(request, str(exc))
    return redirect("portal_admin_page", page="communications")


@admin_login_required_post
@require_POST
def admin_profile_change_action(request):
    from .admin_services import approve_profile_change

    if not _admin_needs_live(request):
        return redirect("portal_admin_page", page="dashboard")
    change_id = request.POST.get("change_id")
    action = request.POST.get("action", "approve")
    try:
        change = approve_profile_change(change_id, approve=action == "approve")
        if action == "approve":
            messages.success(request, f"Profile change approved for {change.account.family.name}.")
        else:
            messages.info(request, f"Profile change declined for {change.account.family.name}.")
    except Exception as exc:
        messages.error(request, str(exc))
    return redirect("portal_admin_page", page="dashboard")


@require_POST
def parent_payment_checkout(request):
    from decimal import Decimal, InvalidOperation

    from .models import PortalPayment
    from .parent_auth import get_parent_account, portal_preview_mode
    from .stripe_services import (
        create_balance_checkout_session,
        create_dropin_checkout_session,
        stripe_configured,
    )

    if portal_preview_mode():
        messages.info(request, "Design preview mode — use the sample payment flow.")
        return redirect("portal_parent_payment_complete")

    account = get_parent_account(request.user)
    if not account:
        messages.error(request, "Sign in to your parent account to pay online.")
        return redirect("portal_parent_login")

    if not stripe_configured():
        messages.error(request, "Stripe is not configured yet. Add MEMBER_STRIPE keys to your .env file.")
        return redirect("portal_parent_page", page="billing")

    is_dropin = request.POST.get("source") == "dropin"
    try:
        amount = Decimal(str(request.POST.get("amount", "0")).replace(",", ""))
    except (InvalidOperation, TypeError):
        amount = Decimal("0")
    if amount <= 0:
        messages.error(request, "Enter a valid payment amount.")
        return redirect("portal_parent_payment")

    payment = PortalPayment.objects.create(
        family=account.family,
        amount=amount,
        payment_kind="dropin" if is_dropin else "balance",
        dropin_child=request.POST.get("child", ""),
        dropin_program=request.POST.get("program_label") or request.POST.get("program", ""),
        dropin_location=request.POST.get("location", ""),
        dropin_date=request.POST.get("date", ""),
    )
    booking_id = request.POST.get("booking_id")
    if booking_id and is_dropin:
        from dropin.models import DropInBooking

        booking = DropInBooking.objects.filter(pk=booking_id, profile__user=account.user).first()
        if booking:
            payment.dropin_booking = booking
            payment.amount = Decimal(str(booking.amount_cents)) / Decimal("100")
            payment.dropin_child = str(booking.child)
            payment.dropin_program = booking.get_program_display()
            payment.dropin_location = booking.get_location_display()
            payment.dropin_date = booking.date.isoformat()
            payment.save()
            amount = payment.amount
    try:
        if is_dropin:
            session = create_dropin_checkout_session(request, payment)
        else:
            session = create_balance_checkout_session(request, payment)
    except Exception as exc:
        payment.delete()
        messages.error(request, str(exc))
        return redirect("portal_parent_payment_preview")
    return redirect(session.url, code=303)


@require_POST
def parent_card_setup(request):
    from .parent_auth import get_parent_account, portal_preview_mode
    from .stripe_services import create_setup_checkout_session, stripe_configured

    if portal_preview_mode():
        messages.info(request, "Design preview mode — card saves are simulated.")
        return redirect("portal_parent_page", page="account")

    account = get_parent_account(request.user)
    if not account:
        messages.error(request, "Sign in to manage payment methods.")
        return redirect("portal_parent_login")

    if not stripe_configured():
        messages.error(request, "Stripe is not configured yet.")
        return redirect("portal_parent_page", page="account")

    try:
        session = create_setup_checkout_session(request, account)
    except Exception as exc:
        messages.error(request, str(exc))
        return redirect("portal_parent_page", page="account")
    return redirect(session.url, code=303)


ALLOWED_PHOTO_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
MAX_PHOTO_BYTES = 5 * 1024 * 1024


@require_POST
def parent_profile_photo_upload(request):
    from .parent_auth import get_parent_account, portal_preview_mode

    if portal_preview_mode():
        messages.info(request, "Design preview mode — photo uploads are disabled.")
        return redirect("portal_parent_page", page="account")

    account = get_parent_account(request.user)
    if not account:
        messages.error(request, "Sign in to update your profile photo.")
        return redirect("portal_parent_login")

    photo = request.FILES.get("profile_photo")
    if not photo:
        messages.error(request, "Choose a photo to upload.")
        return redirect("portal_parent_page", page="account")

    if photo.content_type not in ALLOWED_PHOTO_TYPES:
        messages.error(request, "Use a JPG, PNG, WebP, or GIF image.")
        return redirect("portal_parent_page", page="account")

    if photo.size > MAX_PHOTO_BYTES:
        messages.error(request, "Photo must be 5 MB or smaller.")
        return redirect("portal_parent_page", page="account")

    if account.profile_photo:
        account.profile_photo.delete(save=False)
    account.profile_photo = photo
    account.save(update_fields=["profile_photo"])
    messages.success(request, "Profile photo updated.")
    return redirect("portal_parent_page", page="account")


@require_POST
def parent_profile_photo_remove(request):
    from .parent_auth import get_parent_account, portal_preview_mode

    if portal_preview_mode():
        messages.info(request, "Design preview mode — photo uploads are disabled.")
        return redirect("portal_parent_page", page="account")

    account = get_parent_account(request.user)
    if not account:
        messages.error(request, "Sign in to update your profile photo.")
        return redirect("portal_parent_login")

    if account.profile_photo:
        account.profile_photo.delete(save=False)
        account.profile_photo = ""
        account.save(update_fields=["profile_photo"])
    messages.success(request, "Profile photo removed.")
    return redirect("portal_parent_page", page="account")


@require_POST
@staff_login_required_post
def staff_application_review(request, app_slug):
    from enrollment.application_review import (
        approve_application,
        reject_application,
        request_application_changes,
        save_internal_note,
    )
    from enrollment.portal_integration import get_application_by_reference

    redirect_url = reverse("portal_staff_application_detail", kwargs={"app_slug": app_slug})
    app = get_application_by_reference(app_slug)
    if not app:
        messages.error(request, "Application not found.")
        return redirect("portal_staff_page", page="applications")

    action = request.POST.get("action", "")
    try:
        if action == "approve":
            approve_application(app)
            messages.success(request, f"Approved — {app.student_first_name} {app.student_last_name} is on the roster.")
        elif action == "request_changes":
            request_application_changes(app, request.POST.get("staff_message", ""))
            messages.success(request, "Change request sent to the parent by email and in their portal.")
        elif action == "reject":
            reject_application(app, request.POST.get("staff_message", ""))
            messages.success(request, "Application declined. The parent was notified.")
        elif action == "save_note":
            save_internal_note(app, request.POST.get("internal_note", ""))
            messages.success(request, "Internal note saved.")
        else:
            messages.error(request, "Unknown review action.")
    except ValueError as exc:
        messages.error(request, str(exc))

    return redirect(redirect_url)


@require_POST
@admin_login_required_post
def admin_application_review(request, app_slug):
    from enrollment.application_review import (
        approve_application,
        reject_application,
        request_application_changes,
        save_internal_note,
    )
    from enrollment.portal_integration import get_application_by_reference

    redirect_url = reverse("portal_admin_application_detail", kwargs={"app_slug": app_slug})
    app = get_application_by_reference(app_slug)
    if not app:
        messages.error(request, "Application not found.")
        return redirect("portal_admin_page", page="applications")

    action = request.POST.get("action", "")
    try:
        if action == "approve":
            approve_application(app)
            messages.success(request, f"Approved — {app.student_first_name} {app.student_last_name} is on the roster.")
        elif action == "request_changes":
            request_application_changes(app, request.POST.get("staff_message", ""))
            messages.success(request, "Change request sent to the parent by email and in their portal.")
        elif action == "reject":
            reject_application(app, request.POST.get("staff_message", ""))
            messages.success(request, "Application declined. The parent was notified.")
        elif action == "save_note":
            save_internal_note(app, request.POST.get("internal_note", ""))
            messages.success(request, "Internal note saved.")
        else:
            messages.error(request, "Unknown review action.")
    except ValueError as exc:
        messages.error(request, str(exc))

    return redirect(redirect_url)


@require_POST
def staff_billing_action(request, family_slug):
    from django.urls import reverse

    from .billing_services import (
        default_entry_date,
        delete_ledger_entry,
        get_family_for_billing,
        post_charge,
        post_credit,
        post_payment,
        update_child_billing_plan,
    )
    from .staff_auth import (
        billing_permissions_for_staff,
        get_staff_account,
        is_admin_portal_authenticated,
        is_staff_portal_authenticated,
        resolve_staff_unit,
    )
    from .parent_auth import portal_preview_mode

    area = request.POST.get("portal_area", "staff")
    if not portal_preview_mode():
        if area == "admin" and not is_admin_portal_authenticated(request):
            from django.conf import settings

            login_url = getattr(settings, "PORTAL_ADMIN_LOGIN_URL", "/portal/admin/login/")
            return redirect(f"{login_url}?next={request.get_full_path()}")
        if area != "admin" and not is_staff_portal_authenticated(request):
            from django.conf import settings

            login_url = getattr(settings, "PORTAL_STAFF_LOGIN_URL", "/portal/staff/login/")
            return redirect(f"{login_url}?next={request.get_full_path()}")

    if area == "admin":
        redirect_url = reverse("portal_admin_family_billing", kwargs={"family_slug": family_slug})
        permissions = billing_permissions_for_staff(None, portal_area="admin")
        unit = None
    else:
        redirect_url = reverse("portal_staff_family_billing", kwargs={"family_slug": family_slug})
        permissions = billing_permissions_for_staff(get_staff_account(request.user))
        unit = resolve_staff_unit(request)

    if not _needs_live(request):
        return redirect(redirect_url)

    family = get_family_for_billing(family_slug, unit)
    if not family:
        messages.error(request, "Family not found.")
        if area == "admin":
            return redirect("portal_admin_page", page="billing-settings")
        return redirect("portal_staff_page", page="families")

    action = request.POST.get("action", "")
    entry_date = parse_date(request.POST.get("date") or "") or default_entry_date()

    try:
        if action == "charge":
            if not permissions.get("can_add_charge"):
                raise ValueError("Your role cannot post charges.")
            post_charge(
                family,
                request.POST.get("child_name", "").strip(),
                request.POST.get("charge_type", "manual"),
                request.POST.get("amount", ""),
                entry_date,
                request.POST.get("description", ""),
            )
            messages.success(request, "Charge posted to the family ledger.")
        elif action == "credit":
            if not permissions.get("can_add_credit"):
                raise ValueError("Your role cannot post credits.")
            post_credit(
                family,
                request.POST.get("child_name", "").strip(),
                request.POST.get("amount", ""),
                entry_date,
                request.POST.get("reason", ""),
            )
            messages.success(request, "Credit posted to the family ledger.")
        elif action == "payment":
            method = request.POST.get("method", "cash")
            method_labels = {"card": "Card (staff entry)", "cash": "Cash", "check": "Check"}
            note = request.POST.get("note", "")
            if method == "check" and request.POST.get("check_number"):
                note = f"Check #{request.POST.get('check_number')} — {note}".strip(" —")
            post_payment(
                family,
                request.POST.get("child_name", "").strip(),
                request.POST.get("amount", ""),
                entry_date,
                method_labels.get(method, method),
                note,
            )
            messages.success(request, "Payment recorded.")
        elif action == "delete":
            if not permissions.get("can_delete_charge"):
                raise ValueError("Your role cannot delete ledger entries.")
            delete_ledger_entry(family, request.POST.get("entry_id"))
            messages.success(request, "Ledger entry removed.")
        elif action == "update_plan":
            if area != "admin" and not permissions.get("can_edit_family_plans"):
                raise ValueError("Your role cannot edit billing plans.")
            update_child_billing_plan(
                family,
                request.POST.get("child_name", "").strip(),
                request.POST.get("billing_plan", "Weekly"),
                request.POST.get("billing_amount"),
                request.POST.get("billing_type"),
            )
            messages.success(request, "Billing plan updated.")
        else:
            messages.error(request, "Unknown billing action.")
    except ValueError as exc:
        messages.error(request, str(exc))

    return redirect(redirect_url)


@require_POST
def staff_create_application(request):
    from enrollment.staff_application import create_staff_application

    redirect_url = reverse("portal_staff_page", kwargs={"page": "applications"})
    if not _needs_live(request):
        return redirect(redirect_url)

    unit = get_unit()
    if not unit:
        messages.error(request, "Portal unit not configured.")
        return redirect(redirect_url)

    form = {
        "family_name": request.POST.get("family_name", ""),
        "primary_parent_name": request.POST.get("primary_parent_name", ""),
        "email": request.POST.get("email", ""),
        "phone": request.POST.get("phone", ""),
        "home_address": request.POST.get("home_address", ""),
        "student_first_name": request.POST.get("student_first_name", ""),
        "student_last_name": request.POST.get("student_last_name", ""),
        "student_dob": parse_date(request.POST.get("student_dob") or ""),
        "grade": request.POST.get("grade", "1"),
        "returning_member": request.POST.get("returning_member", "no"),
        "payment_method": request.POST.get("payment_method", "private_pay"),
        "action": request.POST.get("action", "submit"),
    }
    if not all([form["family_name"], form["email"], form["student_first_name"], form["student_last_name"]]):
        messages.error(request, "Family name, email, and child name are required.")
        return redirect("portal_staff_page", page="create-application")

    try:
        app = create_staff_application(form, unit)
        from core.email_service import email_is_configured
        from enrollment.notifications import send_application_submitted_emails

        staff_sent, parent_sent = send_application_submitted_emails(
            app,
            staff_created=True,
            save_draft=form.get("action") == "draft",
        )
        if not email_is_configured():
            messages.warning(
                request,
                "Application saved, but email is not configured on the server — no notifications were sent. "
                "Set EMAIL_HOST, EMAIL_HOST_USER, and EMAIL_HOST_PASSWORD in Render.",
            )
        elif not staff_sent and not parent_sent:
            messages.warning(
                request,
                "Application saved, but confirmation emails could not be sent. Check Render logs and SMTP settings.",
            )
        elif not parent_sent:
            messages.warning(
                request,
                f"Application created for {app.student_first_name} {app.student_last_name}. "
                "Staff was notified, but the parent confirmation email failed.",
            )
        elif not staff_sent:
            messages.warning(
                request,
                f"Application created for {app.student_first_name} {app.student_last_name}. "
                "Parent was notified, but the staff alert email failed.",
            )
        else:
            messages.success(
                request,
                f"Application created for {app.student_first_name} {app.student_last_name}. "
                "Staff and parent notified by email.",
            )
    except Exception as exc:
        messages.error(request, f"Could not create application: {exc}")
        return redirect("portal_staff_page", page="create-application")

    return redirect("portal_staff_application_detail", app_slug=str(app.reference))


@require_POST
def staff_agency_action(request):
    from django.utils.dateparse import parse_date

    from .agency_services import add_agency_child, post_agency_remittance
    from .billing_services import post_payment
    from .staff_auth import resolve_staff_unit

    redirect_url = reverse("portal_staff_page", kwargs={"page": "agency"})
    if not _needs_live(request):
        return redirect(redirect_url)

    unit = resolve_staff_unit(request)
    if not unit:
        messages.error(request, "Portal unit not configured.")
        return redirect(redirect_url)

    action = request.POST.get("action", "")
    try:
        if action == "add_child":
            add_agency_child(
                unit,
                request.POST.get("family_slug", "").strip(),
                request.POST.get("child_name", ""),
                request.POST.get("grade", ""),
                request.POST.get("auth_number", ""),
                request.POST.get("weekly_copay", "0"),
                request.POST.get("weekly_agency_rate", "0"),
                program_label=request.POST.get("program", ""),
                notes=request.POST.get("notes", ""),
                auth_start=parse_date(request.POST.get("auth_start") or "") if request.POST.get("auth_start") else None,
                auth_end=parse_date(request.POST.get("auth_end") or "") if request.POST.get("auth_end") else None,
            )
            messages.success(request, "4Cs child saved and linked to agency billing.")
        elif action == "remittance":
            allocations = []
            for key, value in request.POST.items():
                if key.startswith("alloc_") and value:
                    profile_id = key.replace("alloc_", "")
                    allocations.append({"profile_id": profile_id, "amount": value})
            post_agency_remittance(
                unit,
                parse_date(request.POST.get("date") or "") or timezone.localdate(),
                request.POST.get("reference", ""),
                request.POST.get("total_amount", ""),
                allocations,
            )
            messages.success(request, "Agency remittance posted to 4Cs accounts.")
        elif action == "copay":
            from .billing_services import get_family_for_billing

            family = get_family_for_billing(request.POST.get("family_slug", ""), unit)
            if not family:
                raise ValueError("Family not found.")
            post_payment(
                family,
                request.POST.get("child_name", "").strip(),
                request.POST.get("amount", ""),
                parse_date(request.POST.get("date") or "") or timezone.localdate(),
                request.POST.get("method_label", "Cash"),
                request.POST.get("note", "Weekly copay"),
            )
            messages.success(request, "Parent copay posted to regular family billing.")
        else:
            messages.error(request, "Unknown agency action.")
    except ValueError as exc:
        messages.error(request, str(exc))

    return redirect(redirect_url)


@require_POST
def parent_profile_save(request):
    import json

    from .parent_auth import get_parent_account, portal_preview_mode
    from .parent_services import submit_profile_change_request

    if portal_preview_mode():
        return redirect("portal_parent_page", page="profile")
    account = get_parent_account(request.user)
    if not account:
        return redirect("portal_parent_login")

    changes = {}
    for key in (
        "home_address",
        "primary_name",
        "primary_phone",
        "primary_email",
        "secondary_name",
        "secondary_phone",
        "secondary_email",
    ):
        value = request.POST.get(key, "").strip()
        if value:
            changes[key] = value
    emergency = request.POST.get("emergency_contacts_json", "")
    if emergency:
        try:
            changes["emergency_contacts"] = json.loads(emergency)
        except json.JSONDecodeError:
            pass
    try:
        submit_profile_change_request(account, changes)
        messages.success(request, "Profile changes submitted for staff review.")
    except ValueError as exc:
        messages.error(request, str(exc))
    return redirect("portal_parent_page", page="profile")


@require_POST
def parent_account_update(request):
    from django.contrib.auth import authenticate

    from .parent_auth import get_parent_account, portal_preview_mode
    from .parent_services import update_account_settings

    if portal_preview_mode():
        return redirect("portal_parent_page", page="account")
    account = get_parent_account(request.user)
    if not account:
        return redirect("portal_parent_login")

    action = request.POST.get("action", "settings")
    data = {
        "autopay_enabled": request.POST.get("autopay_enabled") == "on",
        "autopay_day": request.POST.get("autopay_day", ""),
        "email_receipts": request.POST.get("email_receipts") == "on",
        "email_reminders": request.POST.get("email_reminders") == "on",
        "sms_reminders": request.POST.get("sms_reminders") == "on",
    }
    if action == "password":
        if request.POST.get("new_password") != request.POST.get("confirm_password"):
            messages.error(request, "New passwords do not match.")
            return redirect("portal_parent_page", page="account")
        if not authenticate(username=account.user.username, password=request.POST.get("current_password", "")):
            messages.error(request, "Current password is incorrect.")
            return redirect("portal_parent_page", page="account")
        data["new_password"] = request.POST.get("new_password")
    elif action == "email":
        data["email"] = request.POST.get("email", "")
    try:
        update_account_settings(account, data)
        messages.success(request, "Account settings saved.")
    except Exception as exc:
        messages.error(request, str(exc))
    return redirect("portal_parent_page", page="account")


@require_POST
def parent_policy_sign(request):
    from .parent_auth import get_parent_account, portal_preview_mode
    from .parent_services import sign_policy_for_family

    if portal_preview_mode():
        return redirect("portal_parent_page", page="policies")
    account = get_parent_account(request.user)
    if not account:
        return redirect("portal_parent_login")
    try:
        sign_policy_for_family(
            account.family,
            request.POST.get("child_name", ""),
            request.POST.get("policy_slug", ""),
            request.POST.get("signature_name", ""),
        )
        messages.success(request, "Policy signed successfully.")
    except ValueError as exc:
        messages.error(request, str(exc))
    return redirect("portal_parent_page", page="policies")


@require_POST
def parent_dropin_register(request):
    from .parent_auth import get_parent_account, portal_preview_mode
    from .parent_services import ensure_dropin_profile

    if portal_preview_mode():
        return redirect("portal_parent_page", page="drop-in")
    account = get_parent_account(request.user)
    if not account:
        return redirect("portal_parent_login")
    ensure_dropin_profile(account)
    messages.success(request, "Drop-in registration submitted for staff review.")
    return redirect("portal_parent_page", page="drop-in")


@require_POST
def parent_dropin_book(request):
    from django.utils.dateparse import parse_date

    from .parent_auth import get_parent_account, portal_preview_mode
    from .parent_services import book_dropin_live

    if portal_preview_mode():
        return redirect("portal_parent_page", page="drop-in")
    account = get_parent_account(request.user)
    if not account:
        return redirect("portal_parent_login")
    care_date = parse_date(request.POST.get("date") or "")
    if not care_date:
        messages.error(request, "Select a valid date.")
        return redirect("portal_parent_page", page="drop-in")
    try:
        booking = book_dropin_live(
            account,
            request.POST.get("child", ""),
            request.POST.get("program", "after-school"),
            request.POST.get("location", ""),
            care_date,
        )
        from dropin import constants

        fee = constants.FEE_DOLLARS[booking.program]
        query = (
            f"?source=dropin&booking_id={booking.pk}&child={booking.child}"
            f"&program_label={booking.get_program_display()}&location={booking.get_location_display()}"
            f"&date={booking.date.isoformat()}&amount={fee}"
        )
        messages.success(request, "Drop-in day reserved — continue to payment.")
        return redirect(f"{reverse('portal_parent_payment')}{query}")
    except ValueError as exc:
        messages.warning(request, str(exc))
    return redirect("portal_parent_page", page="drop-in")

