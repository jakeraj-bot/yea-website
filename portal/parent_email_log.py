"""Validate parent-email attachments, record sent mail, and build the ledger."""

from datetime import datetime
from pathlib import Path

from django.core.files.base import ContentFile
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone

from .models import PortalParentEmail, PortalParentEmailAttachment

MAX_ATTACHMENT_BYTES = 10 * 1024 * 1024
MAX_ATTACHMENT_COUNT = 5
MAX_ATTACHMENT_TOTAL_BYTES = 25 * 1024 * 1024
LEDGER_PREVIEW_LIMIT = 8

ALLOWED_EXTENSIONS = {
    ".pdf",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".ppt",
    ".pptx",
    ".txt",
    ".csv",
}

ALLOWED_CONTENT_TYPES = {
    "application/pdf",
    "image/png",
    "image/jpeg",
    "image/gif",
    "image/webp",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-powerpoint",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "text/plain",
    "text/csv",
    "application/csv",
}


def _clean_filename(name):
    return Path(name or "").name.strip()


def collect_email_attachments(uploaded_files):
    """Return [(filename, content, mimetype), ...] or raise ValueError."""
    files = [item for item in (uploaded_files or []) if item]
    if not files:
        return []
    if len(files) > MAX_ATTACHMENT_COUNT:
        raise ValueError(f"You can attach up to {MAX_ATTACHMENT_COUNT} files.")

    payloads = []
    total = 0
    for uploaded in files:
        name = _clean_filename(getattr(uploaded, "name", "") or "attachment")
        if not name:
            raise ValueError("One of the files is missing a name.")
        suffix = Path(name).suffix.lower()
        if suffix not in ALLOWED_EXTENSIONS:
            raise ValueError(
                "Use PDF, images (JPG, PNG, GIF, WebP), Word, Excel, PowerPoint, TXT, or CSV."
            )
        content_type = (getattr(uploaded, "content_type", "") or "").split(";")[0].strip().lower()
        if content_type and content_type not in ALLOWED_CONTENT_TYPES:
            if suffix in {".txt", ".csv"} and content_type.startswith("text/"):
                pass
            else:
                raise ValueError(f"{name} is not a file type we can email.")
        size = getattr(uploaded, "size", None)
        content = uploaded.read()
        if size is None:
            size = len(content)
        if size > MAX_ATTACHMENT_BYTES:
            raise ValueError(f"{name} is larger than 10 MB.")
        total += size
        if total > MAX_ATTACHMENT_TOTAL_BYTES:
            raise ValueError("Those files together are larger than 25 MB.")
        payloads.append((name, content, content_type or "application/octet-stream"))
    return payloads


def sender_display_name(user):
    if not user or not getattr(user, "is_authenticated", False):
        return ""
    return (user.get_full_name() or user.username or "").strip()


def record_sent_parent_email(
    *,
    subject,
    body,
    recipients,
    attachments=None,
    family=None,
    unit=None,
    sender=None,
    source=PortalParentEmail.SOURCE_FAMILY,
):
    names = []
    seen = set()
    for email in recipients or []:
        cleaned = (email or "").strip()
        key = cleaned.lower()
        if cleaned and key not in seen:
            seen.add(key)
            names.append(cleaned)
    if not names:
        return None

    attachment_names = []
    payloads = attachments or []
    for item in payloads:
        if isinstance(item, (tuple, list)) and item:
            attachment_names.append(str(item[0]))
        elif hasattr(item, "name"):
            attachment_names.append(_clean_filename(item.name))

    if family and unit is None:
        unit = getattr(family, "unit", None)

    row = PortalParentEmail.objects.create(
        family=family,
        unit=unit,
        sent_by=sender if sender and getattr(sender, "is_authenticated", False) else None,
        sender_name=sender_display_name(sender),
        recipients=names,
        subject=(subject or "").strip()[:200],
        body=body or "",
        attachment_names=attachment_names,
        source=source or PortalParentEmail.SOURCE_FAMILY,
    )
    for item in payloads:
        if not isinstance(item, (tuple, list)) or len(item) < 2:
            continue
        filename, content = item[0], item[1]
        content_type = item[2] if len(item) > 2 else ""
        saved = PortalParentEmailAttachment(
            email=row,
            original_name=filename,
            content_type=content_type or "",
            size=len(content or b""),
        )
        saved.file.save(filename, ContentFile(content or b""), save=True)
    return row


def visible_parent_emails(request, *, area, unit=None):
    from .staff_auth import resolve_staff_unit
    from .unit_visibility import families_qs_for_unit

    qs = PortalParentEmail.objects.select_related("family", "family__unit", "unit", "sent_by")
    if area == "admin":
        return qs
    staff_unit = unit or resolve_staff_unit(request)
    if not staff_unit:
        return qs.none()
    family_ids = families_qs_for_unit(staff_unit).values("pk")
    return qs.filter(Q(unit=staff_unit) | Q(family_id__in=family_ids))


def _parse_date(value):
    raw = (value or "").strip()
    if not raw:
        return None
    try:
        return datetime.strptime(raw, "%Y-%m-%d").date()
    except ValueError:
        return None


def filter_parent_emails(qs, *, family=None, search="", date_from=None, date_to=None):
    from .member_admin import parent_email_for_family

    if family:
        parent_email = (parent_email_for_family(family) or "").strip().lower()
        family_q = Q(family=family)
        if parent_email:
            family_q |= Q(recipients__icontains=parent_email)
        qs = qs.filter(family_q)
    query = (search or "").strip()
    if query:
        qs = qs.filter(
            Q(subject__icontains=query)
            | Q(body__icontains=query)
            | Q(sender_name__icontains=query)
            | Q(recipients__icontains=query)
            | Q(family__name__icontains=query)
        )
    start = date_from if hasattr(date_from, "year") else _parse_date(date_from)
    end = date_to if hasattr(date_to, "year") else _parse_date(date_to)
    if start:
        qs = qs.filter(sent_at__date__gte=start)
    if end:
        qs = qs.filter(sent_at__date__lte=end)
    return qs


def email_ledger_full_url(area, extra_query=""):
    if area == "admin":
        url = reverse("portal_admin_page", kwargs={"page": "emails-sent"})
    else:
        url = reverse("portal_staff_page", kwargs={"page": "emails-sent"})
    if extra_query:
        return f"{url}?{extra_query}"
    return url


def email_ledger_context(
    request,
    *,
    area,
    family=None,
    unit=None,
    limit=None,
    full=False,
):
    search = (request.GET.get("q") or "").strip()
    date_from = request.GET.get("from") or request.GET.get("date_from") or ""
    date_to = request.GET.get("to") or request.GET.get("date_to") or ""
    qs = filter_parent_emails(
        visible_parent_emails(request, area=area, unit=unit),
        family=family,
        search=search if full else "",
        date_from=date_from if full else "",
        date_to=date_to if full else "",
    )
    total = qs.count()
    preview_limit = LEDGER_PREVIEW_LIMIT if not full else None
    if limit is None:
        limit = preview_limit
    rows = list(qs[:limit] if limit else qs[:300])
    query_parts = []
    if family:
        query_parts.append(f"family_id={family.pk}")
    extra_query = "&".join(query_parts)
    return {
        "email_ledger": rows,
        "email_ledger_total": total,
        "email_ledger_limited": bool(limit and total > len(rows)),
        "email_ledger_full": full,
        "email_ledger_q": search,
        "email_ledger_from": (date_from or "").strip(),
        "email_ledger_to": (date_to or "").strip(),
        "email_ledger_url": email_ledger_full_url(area, extra_query),
        "email_ledger_now": timezone.now(),
    }
