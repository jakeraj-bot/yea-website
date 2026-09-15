"""Parent Family Profile change requests for staff/admin approval."""

from django.utils import timezone

from .models import PortalChild, PortalProfileChangeRequest
from .unit_visibility import family_visible_to_unit, unit_label_for_child

FIELD_LABELS = {
    "home_address": "Home address",
    "primary_name": "Primary guardian — Name",
    "primary_relationship": "Primary guardian — Relationship",
    "primary_phone": "Primary guardian — Phone",
    "primary_email": "Primary guardian — Email",
    "secondary_name": "Secondary guardian — Name",
    "secondary_relationship": "Secondary guardian — Relationship",
    "secondary_phone": "Secondary guardian — Phone",
    "secondary_email": "Secondary guardian — Email",
    "medical_notes": "Medical — Staff notes",
    "emergency_contacts": "Emergency contacts",
}

NAMED_PROFILE_FIELDS = (
    "home_address",
    "primary_name",
    "primary_relationship",
    "primary_phone",
    "primary_email",
    "secondary_name",
    "secondary_relationship",
    "secondary_phone",
    "secondary_email",
    "medical_notes",
)


def _blank(value):
    text = "" if value is None else str(value).strip()
    if text in {"—", "-", "None"}:
        return ""
    return text


def _pair(value):
    """Normalize stored change values to {from, to}."""
    if isinstance(value, dict) and ("to" in value or "from" in value):
        return {"from": _blank(value.get("from")), "to": _blank(value.get("to"))}
    return {"from": "", "to": _blank(value)}


def _values_differ(old, new):
    return _blank(old) != _blank(new)


def change_display_rows(changes):
    """Flatten a change payload into labeled from/to rows for staff review."""
    if not isinstance(changes, dict):
        return []
    if isinstance(changes.get("rows"), list) and changes["rows"]:
        rows = []
        for item in changes["rows"]:
            if not isinstance(item, dict):
                continue
            label = _blank(item.get("label"))
            new_value = _blank(item.get("newValue") or item.get("new") or item.get("to"))
            old_value = _blank(item.get("oldValue") or item.get("old") or item.get("from"))
            if not label or not new_value:
                continue
            rows.append(
                {
                    "label": label,
                    "old": old_value or "Not on file",
                    "new": new_value,
                }
            )
        if rows:
            return rows

    rows = []
    for key, label in FIELD_LABELS.items():
        if key not in changes:
            continue
        if key == "emergency_contacts":
            contacts = changes.get("emergency_contacts") or []
            if isinstance(contacts, dict):
                contacts = contacts.get("to") or []
            if not isinstance(contacts, list):
                continue
            for index, contact in enumerate(contacts, start=1):
                if not isinstance(contact, dict):
                    continue
                name = _blank(contact.get("name"))
                phone = _blank(contact.get("phone"))
                relationship = _blank(contact.get("relationship"))
                summary = ", ".join(part for part in (name, phone, relationship) if part)
                if not summary:
                    continue
                rows.append(
                    {
                        "label": f"Emergency contact {index}",
                        "old": "See current profile",
                        "new": summary,
                    }
                )
            continue
        pair = _pair(changes.get(key))
        if not pair["to"] and not pair["from"]:
            continue
        if pair["to"] == pair["from"]:
            continue
        rows.append(
            {
                "label": label,
                "old": pair["from"] or "Not on file",
                "new": pair["to"] or "Not on file",
            }
        )

    for child in changes.get("children") or []:
        if not isinstance(child, dict):
            continue
        name = _blank(child.get("name")) or "Child"
        for field, suffix in (("allergies", "Allergies"), ("medications", "Medications")):
            if field not in child:
                continue
            pair = _pair(child.get(field))
            if pair["to"] == pair["from"]:
                continue
            rows.append(
                {
                    "label": f"{name} — {suffix}",
                    "old": pair["from"] or "Not on file",
                    "new": pair["to"] or "Not on file",
                }
            )
    return rows


def pending_queryset(unit=None):
    qs = (
        PortalProfileChangeRequest.objects.filter(status=PortalProfileChangeRequest.STATUS_PENDING)
        .select_related("account__family", "account__family__unit", "account__user")
        .order_by("submitted_at", "pk")
    )
    if unit is None:
        return qs
    family_ids = []
    for change in qs:
        family = getattr(change.account, "family", None)
        if family_visible_to_unit(family, unit):
            family_ids.append(change.pk)
    return qs.filter(pk__in=family_ids)


def serialize_profile_change(change, unit=None):
    family = getattr(change.account, "family", None)
    user = getattr(change.account, "user", None)
    unit_name = ""
    if family:
        if unit:
            unit_name = unit.name
        elif getattr(family, "unit", None):
            unit_name = family.unit.name
        children = list(family.children.filter(is_active=True)[:3])
        labels = []
        for child in children:
            label, _slug = unit_label_for_child(child)
            if label and label not in labels:
                labels.append(label)
        if labels:
            unit_name = ", ".join(labels)
    rows = change_display_rows(change.changes or {})
    return {
        "pk": change.pk,
        "family_name": family.name if family else "Family",
        "family_slug": family.slug if family else "",
        "family_id": family.pk if family else None,
        "unit_name": unit_name or "—",
        "parent_email": (user.email if user else "") or "",
        "submitted_at": change.submitted_at,
        "submitted_sort": change.submitted_at.isoformat() if change.submitted_at else "",
        "rows": rows,
        "summary": ", ".join(row["label"] for row in rows) or "Profile update",
        "status": change.status,
    }


def pending_profile_reviews(unit=None):
    return [serialize_profile_change(change, unit=unit) for change in pending_queryset(unit)]


def pending_profile_reviews_for_family(family):
    if not family:
        return []
    qs = (
        PortalProfileChangeRequest.objects.filter(
            account__family=family,
            status=PortalProfileChangeRequest.STATUS_PENDING,
        )
        .select_related("account__family", "account__family__unit", "account__user")
        .order_by("submitted_at", "pk")
    )
    return [serialize_profile_change(change) for change in qs]


def pending_profile_change_count(unit=None):
    return pending_queryset(unit).count()


def get_pending_profile_changes(account):
    if not account:
        return []
    qs = account.change_requests.filter(status=PortalProfileChangeRequest.STATUS_PENDING).order_by(
        "submitted_at", "pk"
    )
    return [
        {
            "pk": change.pk,
            "changes": change.changes,
            "submitted_at": change.submitted_at,
            "rows": change_display_rows(change.changes or {}),
        }
        for change in qs
    ]


def _current_profile_snapshot(account):
    from .parent_services import get_profile_live

    return get_profile_live(account.family, account)


def _posted_named_fields(data):
    posted = {}
    for key in NAMED_PROFILE_FIELDS:
        if key not in data:
            continue
        value = data.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            posted[key] = text
    return posted


def _posted_children(data, profile):
    rows = []
    for child in profile.get("children") or []:
        child_id = child.get("child_id")
        if not child_id:
            continue
        allergies = _blank(data.get(f"child_allergies_{child_id}"))
        medications = _blank(data.get(f"child_medications_{child_id}"))
        entry = {"child_id": child_id, "name": child.get("name") or ""}
        changed = False
        if allergies and _values_differ(allergies, child.get("allergies")):
            entry["allergies"] = {"from": _blank(child.get("allergies")), "to": allergies}
            changed = True
        if medications and _values_differ(medications, child.get("medications")):
            entry["medications"] = {"from": _blank(child.get("medications")), "to": medications}
            changed = True
        if changed:
            rows.append(entry)
    return rows


def _posted_emergency_contacts(data):
    import json

    raw = data.get("emergency_contacts_json") or data.get("emergency_contacts") or ""
    if not raw:
        return None
    if isinstance(raw, list):
        return raw
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError):
        return None
    if not isinstance(parsed, list):
        return None
    contacts = []
    for item in parsed:
        if not isinstance(item, dict):
            continue
        name = _blank(item.get("name"))
        phone = _blank(item.get("phone"))
        relationship = _blank(item.get("relationship"))
        if name or phone:
            contacts.append({"name": name, "phone": phone, "relationship": relationship})
    return contacts or None


def _display_rows_from_json(data):
    import json

    raw = data.get("changes_json") or ""
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError):
        return []
    if not isinstance(parsed, list):
        return []
    return change_display_rows({"rows": parsed})


def build_parent_profile_changes(account, data):
    profile = _current_profile_snapshot(account)
    payload = {}
    primary = profile.get("primary") or {}
    secondary = profile.get("secondary") or {}
    current = {
        "home_address": profile.get("home_address"),
        "primary_name": primary.get("name"),
        "primary_relationship": primary.get("relationship"),
        "primary_phone": primary.get("phone"),
        "primary_email": primary.get("email"),
        "secondary_name": secondary.get("name"),
        "secondary_relationship": secondary.get("relationship"),
        "secondary_phone": secondary.get("phone"),
        "secondary_email": secondary.get("email"),
        "medical_notes": "",
    }
    posted = _posted_named_fields(data)
    for key, new_value in posted.items():
        old_value = current.get(key)
        if key == "medical_notes" or _values_differ(old_value, new_value):
            if key == "medical_notes" and not new_value:
                continue
            payload[key] = {"from": _blank(old_value), "to": new_value}

    children = _posted_children(data, profile)
    if children:
        payload["children"] = children

    contacts = _posted_emergency_contacts(data)
    if contacts is not None:
        current_contacts = profile.get("emergency_contacts") or []
        simplified_current = [
            {
                "name": _blank(item.get("name")),
                "phone": _blank(item.get("phone")),
                "relationship": _blank(item.get("relationship")),
            }
            for item in current_contacts
            if isinstance(item, dict)
        ]
        if contacts != simplified_current:
            payload["emergency_contacts"] = contacts

    extra_rows = _display_rows_from_json(data)
    if extra_rows:
        existing_labels = {row["label"] for row in change_display_rows(payload)}
        leftover = [row for row in extra_rows if row["label"] not in existing_labels]
        if leftover:
            payload["rows"] = leftover

    if not payload:
        raise ValueError("No changes to submit.")
    return payload


def notify_staff_profile_change(change):
    from core.email_service import send_site_email

    from .emergency_contact_services import staff_alert_emails

    family = getattr(change.account, "family", None)
    user = getattr(change.account, "user", None)
    family_name = family.name if family else "Family"
    parent_email = (user.email if user else "") or ""
    rows = change_display_rows(change.changes or {})
    lines = [
        "A parent submitted a Family Profile change for staff review.",
        "",
        f"Family: {family_name}",
        f"Parent: {parent_email or family_name}",
        "",
        "Open Pending reviews in the admin or staff portal to approve or decline.",
        "",
    ]
    for row in rows:
        lines.append(f"{row['label']}: {row['old']} → {row['new']}")
    recipients = staff_alert_emails()
    if not recipients:
        return False
    return bool(
        send_site_email(
            subject=f"[YEA Parent Portal] Profile change to review — {family_name}",
            message="\n".join(lines),
            recipient_list=recipients,
            reply_to=[parent_email] if parent_email else None,
        )
    )


def submit_profile_change_request(account, data):
    payload = build_parent_profile_changes(account, data)
    existing = (
        account.change_requests.filter(status=PortalProfileChangeRequest.STATUS_PENDING)
        .order_by("submitted_at", "pk")
        .first()
    )
    if existing:
        merged = dict(existing.changes or {})
        for key, value in payload.items():
            if key == "children":
                by_id = {
                    item.get("child_id"): item
                    for item in merged.get("children") or []
                    if isinstance(item, dict)
                }
                for item in value:
                    by_id[item.get("child_id")] = item
                merged["children"] = list(by_id.values())
            elif key == "rows":
                labels = {row.get("label") for row in value}
                previous = [
                    row
                    for row in merged.get("rows") or []
                    if isinstance(row, dict) and row.get("label") not in labels
                ]
                merged["rows"] = previous + value
            else:
                merged[key] = value
        existing.changes = merged
        existing.save(update_fields=["changes"])
        notify_staff_profile_change(existing)
        return existing
    change = PortalProfileChangeRequest.objects.create(account=account, changes=payload)
    notify_staff_profile_change(change)
    return change


def _relationship_value(text):
    from enrollment.models import EnrollmentApplication

    raw = _blank(text)
    if not raw:
        return None, None
    choices = dict(EnrollmentApplication.RELATIONSHIP_CHOICES)
    key = raw.lower().replace(" ", "_")
    if key in choices:
        return key, ""
    by_label = {label.lower(): value for value, label in EnrollmentApplication.RELATIONSHIP_CHOICES}
    if raw.lower() in by_label:
        return by_label[raw.lower()], ""
    return "other", raw[:80]


def _apply_relationship(applications, prefix, text):
    value, other = _relationship_value(text)
    if not value:
        return
    fields = [f"{prefix}_relationship"]
    for app in applications:
        setattr(app, f"{prefix}_relationship", value)
        if other:
            setattr(app, f"{prefix}_relationship_other", other)
            fields.append(f"{prefix}_relationship_other")
        app.save(update_fields=list(dict.fromkeys(fields)))


def _apply_child_medical(family, child_payload):
    from .medical import application_for_child, medical_value_is_positive

    child_id = child_payload.get("child_id")
    child = None
    if child_id:
        child = PortalChild.objects.filter(pk=child_id, family=family).first()
    if not child and child_payload.get("name"):
        child = PortalChild.objects.filter(family=family, name__iexact=child_payload["name"]).first()
    app = application_for_child(child=child, child_name=child_payload.get("name") or "", family_slug=family.slug)
    if not app:
        return
    updates = []
    if "allergies" in child_payload:
        text = _pair(child_payload["allergies"])["to"]
        if medical_value_is_positive(text):
            app.allergies = text
            app.no_known_allergies = False
        else:
            app.allergies = ""
            app.no_known_allergies = True
        updates.extend(["allergies", "no_known_allergies"])
    if "medications" in child_payload:
        text = _pair(child_payload["medications"])["to"]
        if medical_value_is_positive(text):
            app.requires_medication = "yes"
            note = f"Medications: {text}"
            existing = _blank(app.medical_condition_explain)
            if note not in existing:
                app.medical_condition_explain = f"{existing}\n{note}".strip() if existing else note
                updates.append("medical_condition_explain")
        else:
            app.requires_medication = "no"
        updates.append("requires_medication")
    if updates:
        app.save(update_fields=list(dict.fromkeys(updates)))


def apply_profile_change_payload(family, changes, reviewer="Staff"):
    from enrollment.models import EnrollmentApplication

    from .member_admin import (
        _normalize_member_email,
        _split_person_name,
        _sync_parent_login_email,
        member_info_for_family,
    )

    data = changes or {}
    info = member_info_for_family(family) or {}
    applications = list(EnrollmentApplication.objects.filter(portal_family=family))

    if "primary_name" in data:
        first, last = _split_person_name(_pair(data["primary_name"])["to"])
        info["primary_first_name"] = first or info.get("primary_first_name") or ""
        info["primary_last_name"] = last or info.get("primary_last_name") or ""
    if "primary_phone" in data:
        info["primary_phone"] = _pair(data["primary_phone"])["to"]
    if "primary_email" in data:
        info["primary_email"] = _pair(data["primary_email"])["to"]
    if "home_address" in data:
        info["home_address"] = _pair(data["home_address"])["to"]
    if "secondary_name" in data:
        first, last = _split_person_name(_pair(data["secondary_name"])["to"])
        info["secondary_first_name"] = first
        info["secondary_last_name"] = last
    if "secondary_phone" in data:
        info["secondary_phone"] = _pair(data["secondary_phone"])["to"]
    if "secondary_email" in data:
        info["secondary_email"] = _pair(data["secondary_email"])["to"]

    email = _blank(info.get("primary_email"))
    if email:
        email = _normalize_member_email(email)
        _sync_parent_login_email(
            family,
            email,
            first_name=info.get("primary_first_name") or "",
            last_name=info.get("primary_last_name") or "",
        )

    contact = f"{info.get('primary_first_name') or ''} {info.get('primary_last_name') or ''}".strip()
    family_updates = []
    if contact and family.primary_contact != contact:
        family.primary_contact = contact
        family_updates.append("primary_contact")
    if family_updates:
        family.save(update_fields=family_updates)

    app_fields = {
        "primary_email": email or None,
        "primary_email_address": email or None,
        "primary_first_name": info.get("primary_first_name") or None,
        "primary_last_name": info.get("primary_last_name") or None,
        "primary_phone": info.get("primary_phone") or None,
        "home_address": info.get("home_address") or None,
        "secondary_first_name": info.get("secondary_first_name") or "",
        "secondary_last_name": info.get("secondary_last_name") or "",
        "secondary_phone": info.get("secondary_phone") or "",
        "secondary_email_address": info.get("secondary_email") or "",
    }
    for app in applications:
        changed = []
        for field, value in app_fields.items():
            if value is None:
                continue
            if getattr(app, field) != value:
                setattr(app, field, value)
                changed.append(field)
        if changed:
            app.save(update_fields=changed)

    if "primary_relationship" in data:
        _apply_relationship(applications, "primary", _pair(data["primary_relationship"])["to"])
    if "secondary_relationship" in data:
        _apply_relationship(applications, "secondary", _pair(data["secondary_relationship"])["to"])

    for child_payload in data.get("children") or []:
        if isinstance(child_payload, dict):
            _apply_child_medical(family, child_payload)

    if "medical_notes" in data:
        from .family_notes import add_family_note

        note = _pair(data["medical_notes"])["to"]
        if note:
            add_family_note(
                family,
                body=f"Parent medical note (approved by {reviewer}): {note}",
                user=None,
                unit=family.unit,
            )
    return family


def approve_profile_change(change_id, reviewer="Staff", approve=True, notes="", unit=None):
    change = (
        PortalProfileChangeRequest.objects.filter(pk=change_id)
        .select_related("account__family", "account__family__unit")
        .first()
    )
    if not change:
        raise ValueError("Change request not found.")
    family = change.account.family
    if unit is not None and not family_visible_to_unit(family, unit):
        raise ValueError("That profile change is not for this unit.")
    if change.status != PortalProfileChangeRequest.STATUS_PENDING:
        raise ValueError("That profile change was already reviewed.")
    if approve:
        apply_profile_change_payload(family, change.changes or {}, reviewer=reviewer)
        change.status = PortalProfileChangeRequest.STATUS_APPROVED
    else:
        change.status = PortalProfileChangeRequest.STATUS_REJECTED
    change.reviewed_at = timezone.now()
    change.reviewed_by = (reviewer or "Staff")[:120]
    change.notes = notes or change.notes
    change.save()
    return change
