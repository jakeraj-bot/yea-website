"""Parent and staff emergency contacts — same EnrollmentApplication records."""

from django.conf import settings
from django.db.models import Max

from core.email_service import send_site_email

from .medical import application_for_child


def staff_alert_emails():
    """Inbox used for parent-initiated portal messages (Contact us / settings)."""
    from .views import PARENT_CONTACT_EMAIL

    candidates = [
        getattr(settings, "PORTAL_ALERT_EMAIL", ""),
        getattr(settings, "CONTACT_EMAIL", ""),
        PARENT_CONTACT_EMAIL,
    ]
    seen = set()
    emails = []
    for raw in candidates:
        email = (raw or "").strip()
        key = email.lower()
        if not email or key in seen:
            continue
        seen.add(key)
        emails.append(email)
    return emails


def contact_payload(contact):
    name = f"{contact.first_name} {contact.last_name}".strip()
    return {
        "id": contact.pk,
        "first_name": contact.first_name,
        "last_name": contact.last_name,
        "name": name,
        "phone": contact.phone or "",
        "relationship": contact.relationship or "",
        "authorized_pickup": bool(contact.authorized_pickup),
    }


def contacts_for_application(app):
    if not app:
        return []
    return [contact_payload(contact) for contact in app.emergency_contacts.all()]


def _child_application(child):
    return application_for_child(child=child, child_name=child.name)


def parent_owned_child(family, child_id):
    if not family or not child_id:
        return None
    try:
        child_id = int(child_id)
    except (TypeError, ValueError):
        return None
    return family.children.filter(pk=child_id, is_active=True).first()


def parent_emergency_children(family):
    """Children on this family account with the contacts staff already store."""
    rows = []
    if not family:
        return rows
    for child in family.children.filter(is_active=True).order_by("name"):
        app = _child_application(child)
        rows.append(
            {
                "id": child.pk,
                "name": child.name,
                "can_add": app is not None,
                "contacts": contacts_for_application(app),
            }
        )
    return rows


def demo_emergency_children(profile):
    contacts = list((profile or {}).get("emergency_contacts") or [])
    rows = []
    for child in (profile or {}).get("children") or []:
        rows.append(
            {
                "id": 0,
                "name": child.get("name") or "Child",
                "can_add": False,
                "contacts": contacts,
            }
        )
    if not rows and contacts:
        rows.append({"id": 0, "name": "Your child", "can_add": False, "contacts": contacts})
    return rows


def attach_child_emergency_contacts(children, family):
    """Add per-child contacts onto a family profile child list (staff + parent)."""
    from enrollment.models import EnrollmentApplication

    apps_by_name = {}
    if family:
        for app in EnrollmentApplication.objects.filter(portal_family=family).prefetch_related(
            "emergency_contacts"
        ):
            name = f"{app.student_first_name} {app.student_last_name}".strip().lower()
            if name and name not in apps_by_name:
                apps_by_name[name] = app
    combined = []
    seen = set()
    for child in children or []:
        child_name = (child.get("name") or "").strip()
        app = None
        child_obj = None
        child_id = child.get("child_id")
        if family and child_id:
            child_obj = family.children.filter(pk=child_id).first()
        if child_obj:
            app = _child_application(child_obj)
        if app is None and child_name:
            app = apps_by_name.get(child_name.lower())
        contacts = contacts_for_application(app)
        child["emergency_contacts"] = contacts
        for contact in contacts:
            key = (contact["name"].lower(), contact["phone"])
            if key in seen:
                continue
            seen.add(key)
            combined.append(contact)
    return combined


def _require_contact_fields(data):
    first_name = (data.get("first_name") or "").strip()
    last_name = (data.get("last_name") or "").strip()
    phone = (data.get("phone") or "").strip()
    relationship = (data.get("relationship") or "").strip()
    if not first_name or not phone:
        raise ValueError("Name and phone are required.")
    if not last_name:
        raise ValueError("First name, last name, and phone are required.")
    return {
        "first_name": first_name[:80],
        "last_name": last_name[:80],
        "phone": phone[:30],
        "relationship": relationship[:80],
        "authorized_pickup": bool(data.get("authorized_pickup")),
    }


def add_parent_emergency_contact(family, child_id, data, *, account=None):
    from enrollment.models import EmergencyContact

    child = parent_owned_child(family, child_id)
    if not child:
        raise ValueError("That child is not on your account.")
    app = _child_application(child)
    if not app:
        raise ValueError(
            "We do not have an enrollment record for this child yet. Use Contact us so staff can add the contact."
        )
    fields = _require_contact_fields(data)
    next_order = (app.emergency_contacts.aggregate(Max("order"))["order__max"] or 0) + 1
    contact = EmergencyContact.objects.create(application=app, order=next_order, **fields)
    payload = contact_payload(contact)
    notify_staff_emergency_contact_change(
        family,
        child,
        action="added",
        contact=payload,
        account=account,
    )
    return payload


def delete_parent_emergency_contact(family, child_id, contact_id, *, account=None):
    from enrollment.models import EmergencyContact

    child = parent_owned_child(family, child_id)
    if not child:
        raise ValueError("That child is not on your account.")
    app = _child_application(child)
    contact = None
    if app and contact_id:
        try:
            contact_id = int(contact_id)
        except (TypeError, ValueError):
            contact_id = None
        if contact_id:
            contact = EmergencyContact.objects.filter(pk=contact_id, application=app).first()
    if not contact:
        raise ValueError("That emergency contact was not found for this child.")
    payload = contact_payload(contact)
    contact.delete()
    notify_staff_emergency_contact_change(
        family,
        child,
        action="deleted",
        contact=payload,
        account=account,
    )
    return payload


def _parent_label(account, family):
    if account and account.user:
        name = (account.user.get_full_name() or "").strip()
        email = account.user.email or ""
        if name and email:
            return f"{name} ({email})"
        return name or email or family.primary_contact or family.name
    return family.primary_contact or family.name


def notify_staff_emergency_contact_change(family, child, *, action, contact, account=None):
    recipients = staff_alert_emails()
    parent_label = _parent_label(account, family)
    parent_email = ""
    if account and account.user and account.user.email:
        parent_email = account.user.email
    change = "added" if action == "added" else "deleted"
    pickup = "Yes" if contact.get("authorized_pickup") else "No"
    subject = f"[YEA Parent Portal] Emergency contact {change} — {child.name}"
    body = (
        f"A parent {change} an emergency contact in the parent portal.\n\n"
        f"Family: {family.name}\n"
        f"Parent: {parent_label}\n"
        f"Child: {child.name}\n"
        f"What changed: {change}\n\n"
        f"Contact name: {contact.get('name') or '—'}\n"
        f"Phone: {contact.get('phone') or '—'}\n"
        f"Relationship: {contact.get('relationship') or '—'}\n"
        f"Authorized pickup: {pickup}\n"
    )
    if change == "deleted":
        body += "\nThis person was removed from the child's emergency contact list.\n"
    sent = send_site_email(
        subject=subject,
        message=body,
        recipient_list=recipients,
        reply_to=[parent_email] if parent_email else None,
    )
    return bool(sent)
