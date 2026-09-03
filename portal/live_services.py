from django.db import transaction
from django.utils import timezone

from .attendance_service import format_time_display, get_unit
from .demo_data import (
    ADMIN_COMMUNICATIONS,
    INCIDENTS,
    INCIDENT_SEVERITY_OPTIONS,
    INCIDENT_TYPES,
    MESSAGE_THREADS,
    NEWSLETTERS,
    SUPPORT_TICKET_CATEGORIES,
    SUPPORT_TICKETS,
)
from .models import (
    MessageThread,
    PortalAnnouncement,
    PortalChild,
    PortalFamily,
    PortalIncident,
    PortalNewsletter,
    SupportAttachment,
    SupportMessage,
    SupportTicket,
    TeamMessage,
)


def _display_datetime(dt):
    if not dt:
        return ""
    local = timezone.localtime(dt)
    hour = local.hour % 12 or 12
    ap = "AM" if local.hour < 12 else "PM"
    if local.date() == timezone.localdate():
        prefix = "Today"
    else:
        prefix = local.strftime("%b %d")
    return f"{prefix} {hour}:{local.minute:02d} {ap}"


def _child_by_name(name):
    return PortalChild.objects.filter(name=name, is_active=True).select_related("family").first()


def incident_to_dict(incident):
    return {
        "id": incident.legacy_id or f"inc-{incident.pk}",
        "date": incident.date.isoformat(),
        "time": format_time_display(incident.time) if incident.time else "",
        "child": incident.child.name,
        "family_slug": incident.child.family.slug,
        "unit": incident.unit.name,
        "type": incident.incident_type,
        "severity": incident.severity,
        "summary": incident.summary,
        "location": incident.location,
        "staff_reported": incident.staff_reported,
        "parent_notified": incident.parent_notified,
        "parent_notified_time": format_time_display(incident.parent_notified_time)
        if incident.parent_notified_time
        else "",
        "details": incident.details,
        "follow_up": incident.follow_up,
    }


def get_incidents_live():
    unit = get_unit()
    if not unit:
        return []
    return [
        incident_to_dict(inc)
        for inc in PortalIncident.objects.filter(unit=unit).select_related("child", "child__family")
    ]


def get_incident_live(incident_id):
    if not incident_id:
        return None
    unit = get_unit()
    qs = PortalIncident.objects.filter(unit=unit).select_related("child", "child__family")
    match = qs.filter(legacy_id=incident_id).first()
    if match:
        return incident_to_dict(match)
    if incident_id.isdigit():
        match = qs.filter(pk=int(incident_id)).first()
        if match:
            return incident_to_dict(match)
    return None


def get_incident_children_live():
    unit = get_unit()
    if not unit:
        return []
    return list(
        PortalChild.objects.filter(family__unit=unit, is_active=True)
        .order_by("name")
        .values_list("name", flat=True)
    )


def get_incidents_for_family_live(family_slug):
    if not family_slug:
        return []
    return [inc for inc in get_incidents_live() if inc.get("family_slug") == family_slug]


def get_incidents_for_child_live(child_name):
    if not child_name:
        return []
    return [inc for inc in get_incidents_live() if inc.get("child") == child_name]


def get_incidents_by_child_for_family_live(family_slug):
    grouped = {}
    for incident in get_incidents_for_family_live(family_slug):
        child = incident.get("child", "Unknown")
        grouped.setdefault(child, []).append(incident)
    return grouped


def create_incident_live(data):
    unit = get_unit()
    child = _child_by_name(data["child_name"])
    if not unit or not child:
        raise ValueError("Could not find child or unit.")
    incident = PortalIncident.objects.create(
        child=child,
        unit=unit,
        date=data["date"],
        time=data.get("time"),
        incident_type=data["incident_type"],
        severity=data["severity"],
        summary=data["summary"],
        location=data.get("location", ""),
        staff_reported=data.get("staff_reported", "Staff"),
        parent_notified=data.get("parent_notified", False),
        parent_notified_time=data.get("parent_notified_time"),
        details=data.get("details", ""),
        follow_up=data.get("follow_up", ""),
    )
    incident.legacy_id = f"inc-{incident.date.isoformat().replace('-', '')}-{incident.pk:02d}"
    incident.save(update_fields=["legacy_id"])
    return incident_to_dict(incident)


def support_ticket_to_dict(ticket):
    return {
        "id": ticket.ticket_id,
        "subject": ticket.subject,
        "category": ticket.category,
        "status": ticket.status,
        "from_area": ticket.from_area,
        "from_name": ticket.from_name,
        "from_detail": ticket.from_detail,
        "unit": ticket.unit.name,
        "preview_family": ticket.preview_family_slug,
        "updated_display": _display_datetime(ticket.updated_at),
        "unread_for_admin": ticket.unread_for_admin,
        "unread_for_user": ticket.unread_for_user,
        "messages": [support_message_to_dict(msg) for msg in ticket.messages.all()],
    }


def support_message_to_dict(message):
    attachments = []
    for attachment in message.attachments.all():
        attachments.append(
            {
                "name": attachment.file.name.split("/")[-1],
                "label": attachment.label or attachment.file.name.split("/")[-1],
                "kind": "image",
                "url": attachment.file.url if attachment.file else "",
            }
        )
    return {
        "author": message.author,
        "role": message.role,
        "time": _display_datetime(message.created_at),
        "body": message.body,
        "attachments": attachments,
        "is_admin": message.is_admin,
    }


def get_support_tickets_live(for_area, preview_family=None):
    unit = get_unit()
    if not unit:
        return []
    qs = SupportTicket.objects.filter(unit=unit).prefetch_related("messages__attachments")
    if for_area == "admin":
        tickets = qs
    elif for_area == "parent":
        tickets = qs.filter(from_area="parent", preview_family_slug=preview_family or "")
    else:
        tickets = qs.filter(from_area="staff")
    return [support_ticket_to_dict(t) for t in tickets]


def get_support_ticket_live(ticket_id, for_area, preview_family=None):
    tickets = get_support_tickets_live(for_area, preview_family)
    if ticket_id:
        match = next((t for t in tickets if t["id"] == ticket_id), None)
        if match:
            return match
    return tickets[0] if tickets else None


def count_support_unread_live(for_admin=False):
    unit = get_unit()
    if not unit:
        return 0
    key = "unread_for_admin" if for_admin else "unread_for_user"
    return sum(getattr(t, key) for t in SupportTicket.objects.filter(unit=unit))


def create_support_ticket_live(from_area, preview_family, data, files=None):
    unit = get_unit()
    if not unit:
        raise ValueError("Unit not configured.")
    family = None
    if preview_family:
        family = PortalFamily.objects.filter(unit=unit, slug=preview_family).first()
    next_num = SupportTicket.objects.count() + 1001
    ticket = SupportTicket.objects.create(
        ticket_id=f"tkt-{next_num}",
        from_area=from_area,
        family=family,
        from_name=data.get("from_name", "Portal user"),
        from_detail=data.get("from_detail", ""),
        unit=unit,
        subject=data["subject"],
        category=data.get("category", "other"),
        status="Open",
        preview_family_slug=preview_family or "",
        unread_for_admin=1,
    )
    message = SupportMessage.objects.create(
        ticket=ticket,
        author=ticket.from_name,
        role=data.get("role", "Parent" if from_area == "parent" else "Staff"),
        body=data["body"],
        is_admin=False,
    )
    for uploaded in files or []:
        SupportAttachment.objects.create(
            message=message,
            file=uploaded,
            label=uploaded.name,
        )
    return support_ticket_to_dict(ticket)


def reply_support_ticket_live(ticket_id, body, is_admin=False, author="YEA Support", role="Admin", files=None):
    ticket = SupportTicket.objects.get(ticket_id=ticket_id)
    message = SupportMessage.objects.create(
        ticket=ticket,
        author=author,
        role=role,
        body=body,
        is_admin=is_admin,
    )
    for uploaded in files or []:
        SupportAttachment.objects.create(message=message, file=uploaded, label=uploaded.name)
    if is_admin:
        ticket.unread_for_user = ticket.unread_for_user + 1
        ticket.unread_for_admin = 0
    else:
        ticket.unread_for_admin = ticket.unread_for_admin + 1
        ticket.unread_for_user = 0
    ticket.status = "Waiting on you" if is_admin else "Open"
    ticket.save()
    return support_ticket_to_dict(ticket)


def message_thread_to_dict(thread):
    return {
        "id": thread.legacy_id,
        "subject": thread.subject,
        "category": thread.category,
        "unit": thread.unit.name,
        "priority": thread.priority,
        "updated_display": _display_datetime(thread.updated_at),
        "unread_for_staff": thread.unread_for_staff,
        "unread_for_admin": thread.unread_for_admin,
        "messages": [
            {
                "author": msg.author,
                "role": msg.role,
                "time": _display_datetime(msg.created_at),
                "body": msg.body,
                "is_admin": msg.is_admin,
            }
            for msg in thread.messages.all()
        ],
    }


def get_message_threads_live(unit=None, for_admin=False):
    qs = MessageThread.objects.prefetch_related("messages").order_by("-updated_at")
    if for_admin:
        pass
    elif unit:
        qs = qs.filter(unit=unit)
    else:
        unit = get_unit()
        if not unit:
            return []
        qs = qs.filter(unit=unit)
    return [message_thread_to_dict(thread) for thread in qs]


def get_message_thread_live(thread_id, unit=None, for_admin=False):
    threads = get_message_threads_live(unit=unit, for_admin=for_admin)
    if thread_id:
        match = next((t for t in threads if t["id"] == thread_id), None)
        if match:
            return match
    return threads[0] if threads else None


def count_messages_unread_live(for_admin=False, unit=None):
    qs = MessageThread.objects.all()
    if not for_admin:
        if unit:
            qs = qs.filter(unit=unit)
        else:
            unit = get_unit()
            if not unit:
                return 0
            qs = qs.filter(unit=unit)
    key = "unread_for_admin" if for_admin else "unread_for_staff"
    return sum(getattr(t, key) for t in qs)


def send_team_message_live(thread_id, body, is_admin=False, author="Staff", role="Staff"):
    thread = MessageThread.objects.get(legacy_id=thread_id)
    TeamMessage.objects.create(
        thread=thread,
        author=author,
        role=role,
        body=body,
        is_admin=is_admin,
    )
    if is_admin:
        thread.unread_for_staff = thread.unread_for_staff + 1
        thread.unread_for_admin = 0
    else:
        thread.unread_for_admin = thread.unread_for_admin + 1
        thread.unread_for_staff = 0
    thread.save()
    result = message_thread_to_dict(thread)
    notify_urgent_team_message(thread, body, author, is_admin=is_admin)
    return result


def notify_urgent_team_message(thread, body, author, is_admin=False):
    """Email portal admins when staff flag a thread as urgent."""
    if thread.priority != "urgent":
        return
    from django.conf import settings
    from django.core.mail import send_mail

    if is_admin:
        return
    subject = f"[YEA Portal · Urgent] {thread.subject}"
    unit_name = thread.unit.name if thread.unit_id else "Portal"
    message = (
        f"Urgent team message from {author} ({unit_name})\n\n"
        f"Subject: {thread.subject}\n\n"
        f"{body.strip()}\n\n"
        f"Open the admin portal → Team messages to reply."
    )
    send_mail(
        subject,
        message,
        settings.DEFAULT_FROM_EMAIL,
        [settings.PORTAL_ALERT_EMAIL],
        fail_silently=True,
    )


def create_message_thread_live(data, is_admin=True):
    unit = get_unit()
    if not unit:
        raise ValueError("Unit not configured.")
    base_slug = data["subject"].lower().replace(" ", "-")[:40]
    slug = base_slug
    counter = 1
    while MessageThread.objects.filter(legacy_id=slug).exists():
        slug = f"{base_slug}-{counter}"
        counter += 1
    thread = MessageThread.objects.create(
        legacy_id=slug,
        subject=data["subject"],
        category=data.get("category", "general"),
        unit=unit,
        priority=data.get("priority", "normal"),
        unread_for_staff=1 if is_admin else 0,
    )
    TeamMessage.objects.create(
        thread=thread,
        author=data.get("author", "Admin"),
        role=data.get("role", "Admin"),
        body=data["body"],
        is_admin=is_admin,
    )
    notify_urgent_team_message(thread, data["body"], data.get("author", "Admin"), is_admin=is_admin)
    return message_thread_to_dict(thread)


def announcement_to_dict(item):
    return {
        "id": item.legacy_id or f"ann-{item.pk}",
        "title": item.title,
        "body": item.body,
        "audience": item.audience,
        "unit": item.unit.name,
        "channels": item.channels,
        "status": item.status,
        "posted": item.posted_date.isoformat() if item.posted_date else "—",
        "style": item.style,
    }


def get_announcements_live():
    unit = get_unit()
    if not unit:
        return []
    return [announcement_to_dict(a) for a in PortalAnnouncement.objects.filter(unit=unit)]


def newsletter_to_dict(item):
    return {
        "id": item.legacy_id or f"nl-{item.pk}",
        "title": item.title,
        "template_id": item.template_id,
        "unit": item.unit.name,
        "status": item.status,
        "sent": item.sent_date.isoformat() if item.sent_date else "—",
        "recipients": item.recipients_label or "—",
        "subject": item.subject,
        "body": item.body,
    }


def get_newsletters_live():
    unit = get_unit()
    if not unit:
        return []
    return [newsletter_to_dict(n) for n in PortalNewsletter.objects.filter(unit=unit)]


def save_announcement_live(data, legacy_id=None):
    unit = get_unit()
    if legacy_id:
        item = PortalAnnouncement.objects.get(legacy_id=legacy_id, unit=unit)
    else:
        item = PortalAnnouncement(unit=unit)
        item.legacy_id = f"ann-{PortalAnnouncement.objects.count() + 1:03d}"
    item.title = data["title"]
    item.body = data.get("body", "")
    item.body_html = data.get("body_html", data.get("body", ""))
    item.audience = data.get("audience", f"All parents · {unit.name}")
    item.channels = data.get("channels", ["Portal banner"])
    item.status = data.get("status", "Draft")
    item.style = data.get("style", "info")
    item.posted_date = data.get("posted_date")
    item.save()
    return announcement_to_dict(item)


def save_newsletter_live(data, legacy_id=None):
    unit = get_unit()
    if legacy_id:
        item = PortalNewsletter.objects.get(legacy_id=legacy_id, unit=unit)
    else:
        item = PortalNewsletter(unit=unit)
        item.legacy_id = f"nl-{PortalNewsletter.objects.count() + 1:03d}"
    item.title = data["title"]
    item.template_id = data.get("template_id", "weekly-unit")
    item.subject = data.get("subject", "")
    item.body = data.get("body", "")
    item.sections = data.get("sections", [])
    item.status = data.get("status", "Draft")
    item.sent_date = data.get("sent_date")
    item.recipients_label = data.get("recipients_label", "—")
    item.save()
    return newsletter_to_dict(item)


def _medical_from_application(app):
    from .medical import medical_from_application

    return medical_from_application(app)


def _child_from_application(app):
    from enrollment.locations import get_location_label
    from enrollment.portal_integration import STATUS_LABELS

    child_name = f"{app.student_first_name} {app.student_last_name}".strip()
    status_label = STATUS_LABELS.get(app.status, "Under review")
    return {
        "name": child_name,
        "dob": app.student_dob.strftime("%B %d, %Y"),
        "grade": app.get_student_grade_display(),
        "program": app.get_program_display(),
        "location": get_location_label(app.program_location),
        "note": status_label,
        "enrollment_status": status_label,
        "pending": app.status in {"under_review", "pending_documents", "approved"},
        "medical": _medical_from_application(app),
        "application_ref": str(app.reference),
    }


def family_meta_live(family_slug, unit=None, family_id=None):
    from enrollment.portal_integration import family_display_label
    from portal.member_admin import resolve_family

    family = resolve_family(family_slug=family_slug, family_id=family_id, unit=unit)
    if not family:
        return None
    enrolled = [c.name for c in family.children.filter(is_active=True)]
    pending = []
    from enrollment.models import EnrollmentApplication

    for app in EnrollmentApplication.objects.filter(portal_family=family).order_by("-submitted_at"):
        child_name = f"{app.student_first_name} {app.student_last_name}".strip()
        if child_name.lower() not in {name.lower() for name in enrolled} and app.status not in {
            "declined",
            "enrolled",
        }:
            pending.append(child_name)
    return {
        "id": family.pk,
        "slug": family.slug,
        "name": family_display_label(family),
        "primary_contact": family.primary_contact,
        "children": enrolled + pending,
        "balance": format(family.balance, ".2f"),
        "program": family.program_label,
        "billing_type": family.billing_type,
        "status": "Suspended" if family.is_suspended else family.status,
    }


def family_profile_live(family_slug, unit=None, family_id=None):
    from enrollment.models import EnrollmentApplication
    from enrollment.portal_integration import family_display_label
    from portal.member_admin import resolve_family
    from portal.models import PortalParentAccount

    family = resolve_family(family_slug=family_slug, family_id=family_id, unit=unit)
    if not family:
        return None

    parent_account = PortalParentAccount.objects.filter(family=family).select_related("user").first()
    applications = list(
        EnrollmentApplication.objects.filter(portal_family=family)
        .prefetch_related("emergency_contacts")
        .order_by("-submitted_at")
    )
    latest_app = applications[0] if applications else None

    primary = {
        "name": family.primary_contact,
        "email": parent_account.user.email if parent_account else "",
        "phone": latest_app.primary_phone if latest_app else "",
    }
    secondary = {"name": "", "email": "", "phone": ""}
    if latest_app and latest_app.secondary_first_name:
        secondary = {
            "name": f"{latest_app.secondary_first_name} {latest_app.secondary_last_name}".strip(),
            "email": latest_app.secondary_email_address,
            "phone": latest_app.secondary_phone,
        }

    emergency_contacts = []
    if latest_app:
        emergency_contacts = [
            {
                "name": f"{contact.first_name} {contact.last_name}".strip(),
                "phone": contact.phone,
                "relationship": contact.relationship,
            }
            for contact in latest_app.emergency_contacts.all()
        ]

    enrolled_names = {c.name.lower() for c in family.children.filter(is_active=True)}
    children = [
        {"name": c.name, "grade": c.grade, "school": c.school, "program": family.program_label, "note": c.note}
        for c in family.children.filter(is_active=True)
    ]
    for app in applications:
        child_name = f"{app.student_first_name} {app.student_last_name}".strip()
        if child_name.lower() not in enrolled_names and app.status not in {"declined", "enrolled"}:
            children.append(_child_from_application(app))

    return {
        "family_name": family_display_label(family),
        "family_name_raw": family.name,
        "home_address": latest_app.home_address if latest_app else "—",
        "primary": primary,
        "secondary": secondary,
        "children": children,
        "emergency_contacts": emergency_contacts,
        "pending_application_count": sum(
            1
            for app in applications
            if app.status in {"under_review", "pending_documents", "approved"}
            and f"{app.student_first_name} {app.student_last_name}".strip().lower() not in enrolled_names
        ),
    }


def seed_partial_live_data(unit, program):
    from django.utils.dateparse import parse_date, parse_time

    for row in INCIDENTS:
        child = _child_by_name(row["child"])
        if not child:
            continue
        PortalIncident.objects.update_or_create(
            legacy_id=row["id"],
            defaults={
                "child": child,
                "unit": unit,
                "date": parse_date(row["date"]),
                "time": _parse_display_time(row.get("time", "")),
                "incident_type": row["type"],
                "severity": row["severity"],
                "summary": row["summary"],
                "location": row.get("location", ""),
                "staff_reported": row.get("staff_reported", "Staff"),
                "parent_notified": row.get("parent_notified", False),
                "parent_notified_time": _parse_display_time(row.get("parent_notified_time", ""))
                if row.get("parent_notified_time")
                else None,
                "details": row.get("details", ""),
                "follow_up": row.get("follow_up", ""),
            },
        )

    for row in SUPPORT_TICKETS:
        family = None
        slug = row.get("preview_family")
        if slug:
            family = PortalFamily.objects.filter(unit=unit, slug=slug).first()
        ticket, _ = SupportTicket.objects.update_or_create(
            ticket_id=row["id"],
            defaults={
                "from_area": row["from_area"],
                "family": family,
                "from_name": row["from_name"],
                "from_detail": row.get("from_detail", ""),
                "unit": unit,
                "subject": row["subject"],
                "category": row.get("category", "other"),
                "status": row.get("status", "Open"),
                "preview_family_slug": slug or "",
                "unread_for_admin": row.get("unread_for_admin", 0),
                "unread_for_user": row.get("unread_for_user", 0),
            },
        )
        if not ticket.messages.exists():
            for msg in row.get("messages", []):
                SupportMessage.objects.create(
                    ticket=ticket,
                    author=msg["author"],
                    role=msg["role"],
                    body=msg["body"],
                    is_admin=msg.get("is_admin", False),
                )

    for row in MESSAGE_THREADS:
        thread, _ = MessageThread.objects.update_or_create(
            legacy_id=row["id"],
            defaults={
                "subject": row["subject"],
                "category": row.get("category", "general"),
                "unit": unit,
                "priority": row.get("priority", "normal"),
                "unread_for_staff": row.get("unread_for_staff", 0),
                "unread_for_admin": row.get("unread_for_admin", 0),
            },
        )
        if not thread.messages.exists():
            for msg in row.get("messages", []):
                TeamMessage.objects.create(
                    thread=thread,
                    author=msg["author"],
                    role=msg["role"],
                    body=msg["body"],
                    is_admin=msg.get("is_admin", False),
                )

    for row in ADMIN_COMMUNICATIONS:
        PortalAnnouncement.objects.update_or_create(
            legacy_id=row["id"],
            defaults={
                "title": row["title"],
                "body": row.get("body", ""),
                "unit": unit,
                "audience": row.get("audience", ""),
                "channels": row.get("channels", []),
                "status": row.get("status", "Draft"),
                "style": row.get("style", "info"),
                "posted_date": parse_date(row["posted"]) if row.get("posted") and row["posted"] != "—" else None,
            },
        )

    for row in NEWSLETTERS:
        PortalNewsletter.objects.update_or_create(
            legacy_id=row["id"],
            defaults={
                "title": row["title"],
                "unit": unit,
                "template_id": row.get("template_id", ""),
                "subject": row.get("subject", ""),
                "body": row.get("body", ""),
                "status": row.get("status", "Draft"),
                "sent_date": parse_date(row["sent"]) if row.get("sent") and row["sent"] != "—" else None,
                "recipients_label": row.get("recipients", ""),
            },
        )


def _parse_display_time(value):
    if not value or value == "—":
        return None
    from datetime import datetime

    try:
        return datetime.strptime(value.strip(), "%I:%M %p").time()
    except ValueError:
        from django.utils.dateparse import parse_time

        return parse_time(value)


LIVE_FEATURE_LABELS = [
    "Attendance (check-in/out saves)",
    "Families & members",
    "Incidents log",
    "Support tickets + image uploads",
    "Staff ↔ admin messages",
    "Parent announcements & newsletters (save drafts)",
    "Parent portal login & family accounts",
    "Parent billing ledger (seeded balances)",
    "Stripe payments & saved cards (when configured)",
    "Parent profile change requests + account settings",
    "Drop-in registration & booking (portal)",
    "Policy signing from parent portal",
    "Tax statements (print/PDF)",
    "Email receipts after payment",
    "Admin dashboard (live enrollment & billing stats)",
    "Admin staff invites & billing permissions",
    "Parent profile change review (admin)",
    "Admin member billing across all units",
    "Admin enrollment & financial reports",
]

STILL_DEMO_LABELS = [
    "Autopay scheduled processing (prefs save live)",
    "SMS sending",
    "AI lesson planner (sample output only)",
    "NJ licensing PDF generation",
    "Fee rules & scholarship fund editor",
    "Check-in mode configuration",
    "Unit/program add & edit forms",
]
