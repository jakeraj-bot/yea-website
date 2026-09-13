"""Shared helpers for the activity calendar and member groups."""

from calendar import SUNDAY, Calendar
from datetime import date, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from django.core.files.base import ContentFile
from django.db.models import Count, Q, Prefetch
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_time

from .attendance_calendar import parse_calendar_month, shift_month
from .models import (
    PortalCalendarActivity,
    PortalCalendarActivityMember,
    PortalChild,
    PortalMemberGroup,
    PortalMemberGroupMember,
    PortalUnit,
)
from .staff_auth import is_admin_portal_authenticated, resolve_staff_unit
from .unit_visibility import child_belongs_to_unit, children_for_unit, unit_label_for_child


LESSON_PLAN_MAX_BYTES = 10 * 1024 * 1024
LESSON_PLAN_EXTENSIONS = {
    ".pdf",
    ".doc",
    ".docx",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
}
LESSON_PLAN_CONTENT_TYPES = {
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "image/png",
    "image/jpeg",
    "image/gif",
    "image/webp",
}

PRINT_KINDS = ("daily-attendance", "weekly-attendance", "members", "contacts", "emergency")
PRINT_KIND_ALIASES = {"attendance": "daily-attendance"}
PRINT_KIND_LABELS = {
    "daily-attendance": "Daily attendance",
    "weekly-attendance": "Weekly attendance",
    "members": "Member list",
    "contacts": "Contact list",
    "emergency": "Emergency contacts",
}


def portal_ops_area(request):
    if request.path.startswith("/portal/admin/") or is_admin_portal_authenticated(request):
        return "admin"
    return "staff"


def programming_area(request, area=None):
    """Admin and Program director see all units for activities and groups."""
    area = area or portal_ops_area(request)
    if area == "admin":
        return "admin"
    from .staff_auth import get_staff_account, is_program_director

    if is_program_director(get_staff_account(request.user)):
        return "admin"
    return "staff"


def ops_unit(request, area=None):
    area = area or portal_ops_area(request)
    if area == "admin":
        return None
    return resolve_staff_unit(request)


def unit_choices_for_area(area):
    qs = PortalUnit.objects.filter(is_active=True).order_by("name")
    return [(unit.slug, unit.name) for unit in qs]


def parse_optional_date(raw):
    text = (raw or "").strip()
    if not text:
        return None
    return parse_date(text)


def parse_optional_time(raw):
    text = (raw or "").strip()
    if not text:
        return None
    return parse_time(text)


def add_hours_to_time(start_time, hours=1):
    if not start_time:
        return None
    return (datetime.combine(date.today(), start_time) + timedelta(hours=hours)).time()


def resolve_end_time(start_time, end_time=None):
    if end_time:
        return end_time
    return add_hours_to_time(start_time, 1)


def normalize_print_kind(kind):
    kind = (kind or "").strip()
    return PRINT_KIND_ALIASES.get(kind, kind)


def group_week_days(start=None):
    days = weekday_dates_for_repeat(start or timezone.localdate(), "week")
    return [
        {
            "date": day,
            "label": day.strftime("%a"),
            "date_short": day.strftime("%m/%d").lstrip("0").replace("/0", "/"),
        }
        for day in days
    ]


WEEKDAY_CHOICES = (
    (0, "Monday"),
    (1, "Tuesday"),
    (2, "Wednesday"),
    (3, "Thursday"),
    (4, "Friday"),
)
DEFAULT_WEEKDAYS = (0, 1, 2, 3, 4)


def parse_posted_weekdays(raw_values, *, sent=False):
    """Return selected Mon–Fri indexes, or None when the form omitted the boxes."""
    if not sent:
        return None
    picked = []
    for value in raw_values or []:
        try:
            day = int(value)
        except (TypeError, ValueError):
            continue
        if day in DEFAULT_WEEKDAYS and day not in picked:
            picked.append(day)
    return picked


def weekday_dates_for_repeat(start, repeat, weekdays=None):
    """Return dates for a single day, selected weekdays that week, or those weekdays in the month."""
    if not start:
        return []
    allowed = DEFAULT_WEEKDAYS if weekdays is None else tuple(weekdays)
    allowed_set = {day for day in allowed if day in DEFAULT_WEEKDAYS}
    if repeat == "once" or not repeat:
        return [start]
    if not allowed_set:
        return []
    if repeat == "week":
        monday = start - timedelta(days=start.weekday())
        return [monday + timedelta(days=offset) for offset in range(5) if offset in allowed_set]
    if repeat == "month":
        first = date(start.year, start.month, 1)
        days = []
        cursor = first
        while cursor.month == start.month:
            if cursor.weekday() in allowed_set:
                days.append(cursor)
            cursor += timedelta(days=1)
        return days
    return [start]


def visible_activities_qs(area, staff_unit, unit_slug=""):
    qs = PortalCalendarActivity.objects.select_related("unit", "created_by")
    if area == "staff":
        if not staff_unit:
            return qs.none()
        return qs.filter(unit=staff_unit)
    slug = (unit_slug or "").strip()
    if slug:
        qs = qs.filter(unit__slug=slug)
    return qs


def visible_groups_qs(area, staff_unit, unit_slug=""):
    qs = PortalMemberGroup.objects.select_related("unit", "created_by").annotate(
        member_count=Count("memberships")
    )
    if area == "staff":
        if not staff_unit:
            return qs.none()
        return qs.filter(unit=staff_unit)
    slug = (unit_slug or "").strip()
    if slug:
        qs = qs.filter(unit__slug=slug)
    return qs


def get_visible_activity(activity_id, area, staff_unit):
    qs = visible_activities_qs(area, staff_unit).prefetch_related(
        Prefetch(
            "memberships",
            queryset=PortalCalendarActivityMember.objects.select_related(
                "child", "child__family", "child__unit", "child__family__unit"
            ),
        )
    )
    return qs.filter(pk=activity_id).first()


def get_visible_group(group_id, area, staff_unit):
    qs = visible_groups_qs(area, staff_unit).prefetch_related(
        Prefetch(
            "memberships",
            queryset=PortalMemberGroupMember.objects.select_related(
                "child", "child__family", "child__unit", "child__family__unit"
            ),
        )
    )
    return qs.filter(pk=group_id).first()


def scoped_children_qs(area, staff_unit, unit_slug=""):
    if area == "staff":
        return children_for_unit(staff_unit, active_only=True)
    slug = (unit_slug or "").strip()
    if slug:
        unit = PortalUnit.objects.filter(slug=slug, is_active=True).first()
        return children_for_unit(unit, active_only=True)
    return PortalChild.objects.filter(is_active=True).select_related(
        "family", "family__unit", "unit"
    )


def _grade_sort_key(grade):
    raw = (grade or "").strip()
    lower = raw.lower()
    if lower in {"k", "kindergarten"}:
        return (0, 0, lower)
    digits = "".join(ch for ch in raw if ch.isdigit())
    if digits:
        return (1, int(digits), lower)
    return (2, 0, lower)


def picker_school_choices(qs):
    names = {
        (name or "").strip()
        for name in qs.exclude(school="").values_list("school", flat=True)
        if (name or "").strip()
    }
    return sorted(names, key=str.lower)


def picker_grade_choices(qs):
    grades = {
        (name or "").strip()
        for name in qs.exclude(grade="").values_list("grade", flat=True)
        if (name or "").strip()
    }
    return sorted(grades, key=_grade_sort_key)


def apply_child_filters(qs, *, q="", group_id=None, exclude_ids=None, school="", grade=""):
    name = (q or "").strip()
    if name:
        qs = qs.filter(Q(name__icontains=name) | Q(family__name__icontains=name))
    school_name = (school or "").strip()
    if school_name:
        qs = qs.filter(school__iexact=school_name)
    grade_name = (grade or "").strip()
    if grade_name:
        qs = qs.filter(grade__iexact=grade_name)
    if group_id:
        qs = qs.filter(group_memberships__group_id=group_id)
    if exclude_ids:
        qs = qs.exclude(pk__in=list(exclude_ids))
    return qs.distinct().order_by("name")


def child_can_join(child, area, staff_unit):
    if not child or not child.is_active:
        return False
    if area == "staff":
        return child_belongs_to_unit(child, staff_unit)
    return True


def serialize_child(child):
    unit_name, unit_slug = unit_label_for_child(child)
    return {
        "id": child.pk,
        "name": child.name,
        "family": child.family.name if child.family_id else "",
        "family_slug": child.family.slug if child.family_id else "",
        "grade": child.grade or "",
        "school": child.school or "",
        "unit": unit_name,
        "unit_slug": unit_slug,
    }


def picker_payload(
    *,
    enrolled_children,
    area,
    staff_unit,
    q="",
    unit_slug="",
    group_id=None,
    school="",
    grade="",
    show_group_filter=True,
):
    enrolled_ids = {child.pk for child in enrolled_children}
    scoped_qs = scoped_children_qs(area, staff_unit, unit_slug)
    available_qs = apply_child_filters(
        scoped_qs,
        q=q,
        group_id=group_id,
        exclude_ids=enrolled_ids,
        school=school,
        grade=grade,
    )
    enrolled_qs = apply_child_filters(
        PortalChild.objects.filter(pk__in=enrolled_ids).select_related(
            "family", "family__unit", "unit"
        ),
        q=q,
        group_id=None,
    )
    groups = list(visible_groups_qs(area, staff_unit))
    return {
        "available_children": [serialize_child(child) for child in available_qs],
        "enrolled_children": [serialize_child(child) for child in enrolled_qs],
        "available_ids": [child.pk for child in available_qs],
        "filter_q": q,
        "filter_unit": unit_slug if area == "admin" else "",
        "filter_group": str(group_id or ""),
        "filter_school": (school or "").strip(),
        "filter_grade": (grade or "").strip(),
        "group_choices": [(str(group.pk), f"{group.name} · {group.unit.name}") for group in groups],
        "school_choices": picker_school_choices(scoped_qs),
        "grade_choices": picker_grade_choices(scoped_qs),
        "show_group_filter": show_group_filter,
        "show_unit_filter": area == "admin",
        "fixed_unit_name": staff_unit.name if area == "staff" and staff_unit else "",
        "unit_choices": unit_choices_for_area(area) if area == "admin" else [],
    }


def create_activities(*, name, start_time, start_date, repeat, unit, user, lesson_file=None, end_time=None, weekdays=None):
    name = (name or "").strip()
    if not name or not start_time or not start_date or not unit:
        return [], "Name, date, start time, and unit are required."
    resolved_end = resolve_end_time(start_time, end_time)
    if resolved_end and resolved_end <= start_time:
        return [], "End time must be after start time."
    if repeat in {"week", "month"} and weekdays is not None and not weekdays:
        return [], "Choose at least one weekday."
    dates = weekday_dates_for_repeat(start_date, repeat, weekdays=weekdays)
    if not dates:
        return [], "Choose a date."
    series_id = uuid4() if len(dates) > 1 else None
    created = []
    plan_payload = None
    if lesson_file and len(dates) == 1:
        plan_payload, error = read_lesson_plan(lesson_file)
        if error:
            return [], error
    for activity_date in dates:
        existing = PortalCalendarActivity.objects.filter(
            unit=unit,
            name=name,
            activity_date=activity_date,
            start_time=start_time,
        ).first()
        if existing:
            created.append(existing)
            continue
        activity = PortalCalendarActivity(
            name=name,
            activity_date=activity_date,
            start_time=start_time,
            end_time=resolved_end,
            unit=unit,
            created_by=user if getattr(user, "is_authenticated", False) else None,
            series_id=series_id,
        )
        activity.save()
        if plan_payload:
            attach_lesson_plan(activity, plan_payload)
        created.append(activity)
    return created, ""


def create_group(*, name, unit, user):
    name = (name or "").strip()
    if not name or not unit:
        return None, "Name and unit are required."
    group, _created = PortalMemberGroup.objects.get_or_create(
        name=name,
        unit=unit,
        defaults={"created_by": user if getattr(user, "is_authenticated", False) else None},
    )
    return group, ""


def add_children_to_activity(activity, child_ids, *, area, staff_unit, user):
    added = 0
    for child in PortalChild.objects.filter(pk__in=child_ids, is_active=True).select_related("family"):
        if not child_can_join(child, area, staff_unit):
            continue
        _, created = PortalCalendarActivityMember.objects.get_or_create(
            activity=activity,
            child=child,
            defaults={"added_by": user if getattr(user, "is_authenticated", False) else None},
        )
        if created:
            added += 1
    return added


def remove_child_from_activity(activity, child_id, *, area, staff_unit):
    membership = activity.memberships.filter(child_id=child_id).select_related("child", "child__family").first()
    if not membership:
        return False
    if not child_can_join(membership.child, area, staff_unit):
        return False
    membership.delete()
    return True


def add_children_to_group(group, child_ids, *, area, staff_unit, user):
    added = 0
    for child in PortalChild.objects.filter(pk__in=child_ids, is_active=True).select_related("family"):
        if not child_can_join(child, area, staff_unit):
            continue
        if area == "admin" and child_effective_unit_id(child) != group.unit_id:
            continue
        if area == "staff" and group.unit_id != getattr(staff_unit, "pk", None):
            continue
        _, created = PortalMemberGroupMember.objects.get_or_create(
            group=group,
            child=child,
            defaults={"added_by": user if getattr(user, "is_authenticated", False) else None},
        )
        if created:
            added += 1
    return added


def remove_child_from_group(group, child_id, *, area, staff_unit):
    membership = group.memberships.filter(child_id=child_id).select_related("child", "child__family").first()
    if not membership:
        return False
    if not child_can_join(membership.child, area, staff_unit):
        return False
    membership.delete()
    return True


def child_effective_unit_id(child):
    return child.unit_id or getattr(child.family, "unit_id", None)


def read_lesson_plan(uploaded):
    if not uploaded:
        return None, "Choose a lesson plan file."
    name = Path(getattr(uploaded, "name", "") or "lesson-plan").name
    suffix = Path(name).suffix.lower()
    if suffix not in LESSON_PLAN_EXTENSIONS:
        return None, "Use a PDF, Word document, or image for the lesson plan."
    content_type = (getattr(uploaded, "content_type", "") or "").split(";")[0].strip().lower()
    if content_type and content_type not in LESSON_PLAN_CONTENT_TYPES:
        return None, "That file type is not allowed for a lesson plan."
    size = getattr(uploaded, "size", None)
    content = uploaded.read()
    if size is None:
        size = len(content)
    if size > LESSON_PLAN_MAX_BYTES:
        return None, "Lesson plans must be 10 MB or smaller."
    if not content:
        return None, "That lesson plan file is empty."
    return {"name": name, "content": content}, ""


def attach_lesson_plan(activity, payload):
    activity.lesson_plan.save(payload["name"], ContentFile(payload["content"]), save=False)
    activity.lesson_plan_name = payload["name"]
    activity.save(update_fields=["lesson_plan", "lesson_plan_name", "updated_at"])
    return activity


def month_calendar_rows(month_start, activities):
    by_iso = {}
    for activity in activities:
        key = activity.activity_date.isoformat()
        by_iso.setdefault(key, []).append(activity)
    weeks = []
    today = timezone.localdate()
    for week in Calendar(firstweekday=SUNDAY).monthdatescalendar(month_start.year, month_start.month):
        days = []
        for day in week:
            iso = day.isoformat()
            days.append(
                {
                    "date": day,
                    "iso": iso,
                    "day": day.day,
                    "in_month": day.month == month_start.month,
                    "is_today": day == today,
                    "activities": by_iso.get(iso, []),
                }
            )
        weeks.append(days)
    return weeks


def activity_month_context(month_start, activities):
    return {
        "month_start": month_start,
        "month_value": month_start.strftime("%Y-%m"),
        "month_label": month_start.strftime("%B %Y"),
        "prev_month": shift_month(month_start, -1).strftime("%Y-%m"),
        "next_month": shift_month(month_start, 1).strftime("%Y-%m"),
        "weekdays": ("Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"),
        "weeks": month_calendar_rows(month_start, activities),
    }


def series_siblings(activity):
    if not activity or not activity.series_id:
        return []
    return list(
        PortalCalendarActivity.objects.filter(series_id=activity.series_id)
        .exclude(pk=activity.pk)
        .order_by("activity_date")
    )


def resolve_create_unit(request, area, staff_unit):
    if area == "staff":
        return staff_unit
    slug = (request.POST.get("unit") or "").strip()
    if slug:
        return PortalUnit.objects.filter(slug=slug, is_active=True).first()
    return PortalUnit.objects.filter(is_active=True).order_by("name").first()


def posted_child_ids(request):
    raw = request.POST.getlist("child_id") or request.POST.getlist("child_ids")
    ids = []
    for value in raw:
        try:
            ids.append(int(value))
        except (TypeError, ValueError):
            continue
    single = request.POST.get("child_id")
    if single and not ids:
        try:
            ids.append(int(single))
        except (TypeError, ValueError):
            pass
    return ids


def group_member_children(group):
    return [
        membership.child
        for membership in group.memberships.all()
        if membership.child_id and membership.child.is_active
    ]


def group_print_rows(group, kind):
    from .medical import application_for_child
    from .pickup_services import child_emergency_contact_rows, emergency_contacts_from_application

    children = group_member_children(group)
    rows = []
    for index, child in enumerate(children, start=1):
        unit_name, unit_slug = unit_label_for_child(child)
        app = application_for_child(child=child, child_name=child.name)
        school = (child.school or (getattr(app, "student_school", "") if app else "") or "").strip()
        grade = child.grade or (app.get_student_grade_display() if app else "") or "—"
        parent_name = ""
        parent_phone = ""
        if app:
            parent_name = f"{app.primary_first_name} {app.primary_last_name}".strip()
            parent_phone = app.primary_phone or ""
        if not parent_name:
            parent_name = child.family.primary_contact if child.family_id else ""
        base = {
            "index": index,
            "child": child.name,
            "family": child.family.name if child.family_id else "",
            "family_slug": child.family.slug if child.family_id else "",
            "unit": unit_name or group.unit.name,
            "unit_slug": unit_slug or group.unit.slug,
            "grade": grade or "—",
            "school": school or "—",
            "parent_name": parent_name or "—",
            "parent_phone": parent_phone or "—",
        }
        if kind == "emergency":
            contacts = emergency_contacts_from_application(app)
            rows.extend(child_emergency_contact_rows(base, contacts))
        else:
            rows.append(base)
    return rows
