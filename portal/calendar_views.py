"""Staff and admin views for the activity calendar and member groups."""

from functools import wraps

from django.conf import settings
from django.contrib import messages
from django.db.models import Count
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from .attendance_calendar import parse_calendar_month
from .member_sets import (
    PRINT_KIND_LABELS,
    PRINT_KINDS,
    activity_month_context,
    add_children_to_activity,
    add_children_to_group,
    apply_child_filters,
    attach_lesson_plan,
    create_activities,
    create_group,
    get_visible_activity,
    get_visible_group,
    group_member_children,
    group_print_rows,
    ops_unit,
    parse_optional_date,
    parse_optional_time,
    picker_payload,
    portal_ops_area,
    posted_child_ids,
    read_lesson_plan,
    remove_child_from_activity,
    remove_child_from_group,
    resolve_create_unit,
    scoped_children_qs,
    series_siblings,
    unit_choices_for_area,
    visible_activities_qs,
    visible_groups_qs,
)
from .staff_auth import (
    is_admin_portal_authenticated,
    is_staff_portal_authenticated,
    portal_preview_mode,
)


def staff_or_admin_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if portal_preview_mode():
            return view_func(request, *args, **kwargs)
        if is_staff_portal_authenticated(request) or is_admin_portal_authenticated(request):
            return view_func(request, *args, **kwargs)
        from .staff_auth import activate_portal_area

        if activate_portal_area(request, "staff") or activate_portal_area(request, "admin"):
            return view_func(request, *args, **kwargs)
        login_url = getattr(settings, "PORTAL_STAFF_LOGIN_URL", "/portal/staff/login/")
        if request.path.startswith("/portal/admin/"):
            login_url = getattr(settings, "PORTAL_ADMIN_LOGIN_URL", "/portal/admin/login/")
        return redirect(f"{login_url}?next={request.get_full_path()}")

    return wrapper


def _page_context(request, title, *, staff_slug, admin_slug, page_guide_key, **extra):
    from .views import _portal_context, _staff_context

    area = portal_ops_area(request)
    extra.setdefault("ops_area", area)
    extra.setdefault("show_unit_filter", area == "admin")
    extra.setdefault("unit_choices", unit_choices_for_area(area) if area == "admin" else [])
    if area == "admin":
        return _portal_context(
            "admin",
            title,
            admin_page_slug=admin_slug,
            page_guide_key=page_guide_key,
            **extra,
        )
    return _staff_context(
        title,
        request=request,
        staff_page_slug=staff_slug,
        page_guide_key=page_guide_key,
        **extra,
    )


def _url(request, staff_name, admin_name, **kwargs):
    name = admin_name if portal_ops_area(request) == "admin" else staff_name
    return reverse(name, kwargs=kwargs or None)


def _calendar_url(request, **kwargs):
    return _url(request, "portal_staff_activity_calendar", "portal_admin_activity_calendar", **kwargs)


def _activity_url(request, activity_id):
    return _url(
        request,
        "portal_staff_activity_detail",
        "portal_admin_activity_detail",
        activity_id=activity_id,
    )


def _groups_url(request):
    return _url(request, "portal_staff_groups", "portal_admin_groups")


def _group_url(request, group_id):
    return _url(request, "portal_staff_group_detail", "portal_admin_group_detail", group_id=group_id)


def _picker_filters(request, area):
    q = (request.GET.get("q") or request.POST.get("q") or "").strip()
    unit_slug = (request.GET.get("unit") or request.POST.get("filter_unit") or "").strip()
    if area != "admin":
        unit_slug = ""
    group_raw = (request.GET.get("group") or request.POST.get("group") or "").strip()
    group_id = None
    if group_raw:
        try:
            group_id = int(group_raw)
        except (TypeError, ValueError):
            group_id = None
    return q, unit_slug, group_id


def _keep_picker_query(q, unit_slug, group_id):
    parts = []
    if q:
        parts.append(f"q={q}")
    if unit_slug:
        parts.append(f"unit={unit_slug}")
    if group_id:
        parts.append(f"group={group_id}")
    return ("?" + "&".join(parts)) if parts else ""


@staff_or_admin_required
@require_http_methods(["GET", "POST"])
def activity_calendar(request):
    area = portal_ops_area(request)
    staff_unit = ops_unit(request, area)
    if request.method == "POST":
        return _create_activity(request, area, staff_unit)

    month_start = parse_calendar_month(request.GET.get("month"), fallback=timezone.localdate())
    unit_slug = (request.GET.get("unit") or "").strip() if area == "admin" else ""
    activities = list(
        visible_activities_qs(area, staff_unit, unit_slug)
        .filter(activity_date__year=month_start.year, activity_date__month=month_start.month)
        .annotate(member_count=Count("memberships"))
        .order_by("activity_date", "start_time", "name")
    )
    context = _page_context(
        request,
        "Activity calendar",
        staff_slug="activity-calendar",
        admin_slug="activity-calendar",
        page_guide_key="activity-calendar",
        calendar=activity_month_context(month_start, activities),
        activities=activities,
        filter_unit=unit_slug,
        create_url=_calendar_url(request),
        today=timezone.localdate().isoformat(),
        default_time="15:00",
        default_unit=staff_unit.slug if staff_unit else "",
        calendar_list_url=_calendar_url(request),
    )
    return render(request, "portal/staff/activity_calendar.html", context)


def _create_activity(request, area, staff_unit):
    unit = resolve_create_unit(request, area, staff_unit)
    if area == "staff" and not unit:
        messages.error(request, "Choose a unit before you create an activity.")
        return redirect(_calendar_url(request))
    name = request.POST.get("name")
    start_date = parse_optional_date(request.POST.get("date"))
    start_time = parse_optional_time(request.POST.get("time"))
    repeat = (request.POST.get("repeat") or "once").strip()
    if repeat not in {"once", "week", "month"}:
        repeat = "once"
    created, error = create_activities(
        name=name,
        start_time=start_time,
        start_date=start_date,
        repeat=repeat,
        unit=unit,
        user=request.user,
        lesson_file=request.FILES.get("lesson_plan") if repeat == "once" else None,
    )
    if error:
        messages.error(request, error)
        return redirect(_calendar_url(request))
    if not created:
        messages.error(request, "No activities were created.")
        return redirect(_calendar_url(request))
    if len(created) == 1:
        messages.success(request, f"Saved {created[0].name}. Add the children who attended.")
        return redirect(_activity_url(request, created[0].pk))
    messages.success(
        request,
        f"Added {created[0].name} on {len(created)} days. Open a day later to upload that day’s lesson plan.",
    )
    month = created[0].activity_date.strftime("%Y-%m")
    return redirect(f"{_calendar_url(request)}?month={month}")


@staff_or_admin_required
@require_http_methods(["GET", "POST"])
def activity_detail(request, activity_id):
    area = portal_ops_area(request)
    staff_unit = ops_unit(request, area)
    activity = get_visible_activity(activity_id, area, staff_unit)
    if not activity:
        messages.error(request, "That activity is not available.")
        return redirect(_calendar_url(request))

    q, unit_slug, group_id = _picker_filters(request, area)
    if request.method == "POST":
        action = (request.POST.get("action") or "").strip()
        q, unit_slug, group_id = _picker_filters(request, area)
        if action == "add":
            added = add_children_to_activity(
                activity, posted_child_ids(request), area=area, staff_unit=staff_unit, user=request.user
            )
            messages.success(request, f"Added {added} member{'s' if added != 1 else ''}.")
        elif action == "add_filtered":
            enrolled_ids = {row.child_id for row in activity.memberships.all()}
            available = apply_child_filters(
                scoped_children_qs(area, staff_unit, unit_slug),
                q=q,
                group_id=group_id,
                exclude_ids=enrolled_ids,
            )
            added = add_children_to_activity(
                activity,
                [child.pk for child in available],
                area=area,
                staff_unit=staff_unit,
                user=request.user,
            )
            messages.success(request, f"Added {added} member{'s' if added != 1 else ''} from the filtered list.")
        elif action == "remove":
            if remove_child_from_activity(activity, request.POST.get("child_id"), area=area, staff_unit=staff_unit):
                messages.success(request, "Removed that member.")
            else:
                messages.error(request, "Could not remove that member.")
        elif action == "lesson_plan":
            payload, error = read_lesson_plan(request.FILES.get("lesson_plan"))
            if error:
                messages.error(request, error)
            else:
                attach_lesson_plan(activity, payload)
                messages.success(request, "Lesson plan saved for this day.")
        elif action == "delete":
            label = activity.name
            activity.delete()
            messages.success(request, f"Deleted {label}.")
            return redirect(_calendar_url(request))
        return redirect(_activity_url(request, activity.pk) + _keep_picker_query(q, unit_slug, group_id))

    enrolled = [row.child for row in activity.memberships.all()]
    picker = picker_payload(
        enrolled_children=enrolled,
        area=area,
        staff_unit=staff_unit,
        q=q,
        unit_slug=unit_slug,
        group_id=group_id,
        show_group_filter=True,
    )
    context = _page_context(
        request,
        activity.name,
        staff_slug="activity-calendar",
        admin_slug="activity-calendar",
        page_guide_key="activity-calendar-detail",
        activity=activity,
        series_days=series_siblings(activity),
        picker=picker,
        picker_action=_activity_url(request, activity.pk),
        calendar_url=_calendar_url(request),
        available_heading="Kids to add",
        enrolled_heading="In this activity",
    )
    return render(request, "portal/staff/activity_detail.html", context)


@staff_or_admin_required
@require_http_methods(["GET", "POST"])
def group_list(request):
    area = portal_ops_area(request)
    staff_unit = ops_unit(request, area)
    if request.method == "POST":
        unit = resolve_create_unit(request, area, staff_unit)
        group, error = create_group(name=request.POST.get("name"), unit=unit, user=request.user)
        if error:
            messages.error(request, error)
            return redirect(_groups_url(request))
        messages.success(request, f"Saved {group.name}. Add members next.")
        return redirect(_group_url(request, group.pk))

    unit_slug = (request.GET.get("unit") or "").strip() if area == "admin" else ""
    groups = list(visible_groups_qs(area, staff_unit, unit_slug))
    context = _page_context(
        request,
        "Groups",
        staff_slug="groups",
        admin_slug="groups",
        page_guide_key="groups",
        groups=groups,
        filter_unit=unit_slug,
        create_url=_groups_url(request),
        default_unit=staff_unit.slug if staff_unit else "",
    )
    return render(request, "portal/staff/groups.html", context)


@staff_or_admin_required
@require_http_methods(["GET", "POST"])
def group_detail(request, group_id):
    area = portal_ops_area(request)
    staff_unit = ops_unit(request, area)
    group = get_visible_group(group_id, area, staff_unit)
    if not group:
        messages.error(request, "That group is not available.")
        return redirect(_groups_url(request))

    q, unit_slug, _group_filter = _picker_filters(request, area)
    if area == "admin" and not unit_slug:
        unit_slug = group.unit.slug
    if request.method == "POST":
        action = (request.POST.get("action") or "").strip()
        q, unit_slug, _group_filter = _picker_filters(request, area)
        if area == "admin" and not unit_slug:
            unit_slug = group.unit.slug
        if action == "add":
            added = add_children_to_group(
                group, posted_child_ids(request), area=area, staff_unit=staff_unit, user=request.user
            )
            messages.success(request, f"Added {added} member{'s' if added != 1 else ''}.")
        elif action == "add_filtered":
            enrolled_ids = {row.child_id for row in group.memberships.all()}
            available = apply_child_filters(
                scoped_children_qs(area, staff_unit, unit_slug),
                q=q,
                exclude_ids=enrolled_ids,
            )
            added = add_children_to_group(
                group,
                [child.pk for child in available],
                area=area,
                staff_unit=staff_unit,
                user=request.user,
            )
            messages.success(request, f"Added {added} member{'s' if added != 1 else ''} from the filtered list.")
        elif action == "remove":
            if remove_child_from_group(group, request.POST.get("child_id"), area=area, staff_unit=staff_unit):
                messages.success(request, "Removed that member.")
            else:
                messages.error(request, "Could not remove that member.")
        elif action == "delete":
            label = group.name
            group.delete()
            messages.success(request, f"Deleted {label}.")
            return redirect(_groups_url(request))
        return redirect(_group_url(request, group.pk) + _keep_picker_query(q, unit_slug, None))

    enrolled = group_member_children(group)
    picker = picker_payload(
        enrolled_children=enrolled,
        area=area,
        staff_unit=staff_unit,
        q=q,
        unit_slug=unit_slug,
        group_id=None,
        show_group_filter=False,
    )
    print_links = [
        {
            "kind": kind,
            "label": PRINT_KIND_LABELS[kind],
            "url": _url(
                request,
                "portal_staff_group_print",
                "portal_admin_group_print",
                group_id=group.pk,
                kind=kind,
            ),
        }
        for kind in PRINT_KINDS
    ]
    context = _page_context(
        request,
        group.name,
        staff_slug="groups",
        admin_slug="groups",
        page_guide_key="groups-detail",
        group=group,
        picker=picker,
        picker_action=_group_url(request, group.pk),
        groups_url=_groups_url(request),
        print_links=print_links,
        available_heading="Kids to add",
        enrolled_heading="In this group",
    )
    return render(request, "portal/staff/group_detail.html", context)


@staff_or_admin_required
@require_http_methods(["GET"])
def group_print(request, group_id, kind):
    area = portal_ops_area(request)
    staff_unit = ops_unit(request, area)
    group = get_visible_group(group_id, area, staff_unit)
    if not group or kind not in PRINT_KINDS:
        messages.error(request, "That printout is not available.")
        return redirect(_groups_url(request))
    rows = group_print_rows(group, kind)
    context = _page_context(
        request,
        f"{group.name} — {PRINT_KIND_LABELS[kind]}",
        staff_slug="groups",
        admin_slug="groups",
        page_guide_key="groups-print",
        group=group,
        print_kind=kind,
        print_label=PRINT_KIND_LABELS[kind],
        report_rows=rows,
        generated_date=timezone.localdate().strftime("%B %d, %Y"),
        group_url=_group_url(request, group.pk),
        groups_url=_groups_url(request),
    )
    return render(request, "portal/staff/group_print.html", context)
