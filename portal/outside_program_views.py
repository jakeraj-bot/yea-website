"""CRM for outside program vendors and partners."""

from decimal import Decimal, InvalidOperation
from urllib.parse import urlencode

from django.contrib import messages
from django.db.models import Q
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.dateparse import parse_date
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from .calendar_views import staff_or_admin_required
from .member_sets import portal_ops_area
from .models import PortalOutsideProgram
from .staff_auth import (
    can_manage_outside_programs,
    get_staff_account,
    is_admin_portal_authenticated,
)


def _can_manage(request):
    area = portal_ops_area(request)
    if is_admin_portal_authenticated(request):
        return True
    return can_manage_outside_programs(get_staff_account(request.user), portal_area=area)


def _page_context(request, title, **extra):
    from .views import _finalize_admin_context, _portal_context, _staff_context

    area = portal_ops_area(request)
    extra.setdefault("ops_area", area)
    extra.setdefault("outside_program_categories", PortalOutsideProgram.CATEGORY_CHOICES)
    extra.setdefault("page_guide_key", extra.pop("page_guide_key", "outside-programs"))
    if area == "admin":
        return _finalize_admin_context(
            request,
            _portal_context("admin", title, admin_page_slug="outside-programs", **extra),
        )
    return _staff_context(title, request=request, staff_page_slug="outside-programs", **extra)


def _list_url(request):
    if portal_ops_area(request) == "admin":
        return reverse("portal_admin_outside_programs")
    return reverse("portal_staff_outside_programs")


def _parse_amount(raw):
    text = (raw or "").strip().replace("$", "").replace(",", "")
    if not text:
        return None
    try:
        return Decimal(text)
    except (InvalidOperation, TypeError):
        return None


def _filtered_programs(request):
    q = (request.GET.get("q") or "").strip()
    category = (request.GET.get("category") or "").strip()
    qs = PortalOutsideProgram.objects.all()
    if q:
        qs = qs.filter(
            Q(name__icontains=q)
            | Q(email__icontains=q)
            | Q(phone__icontains=q)
            | Q(description__icontains=q)
            | Q(notes__icontains=q)
        )
    if category:
        qs = qs.filter(category=category)
    return q, category, list(qs)


@staff_or_admin_required
@require_http_methods(["GET", "POST"])
def outside_program_list(request):
    if not _can_manage(request):
        return HttpResponseForbidden("Outside programs are for Program director and admin.")
    if request.method == "POST":
        return _save_program(request)
    q, category, programs = _filtered_programs(request)
    editing_id = request.GET.get("edit")
    editing = PortalOutsideProgram.objects.filter(pk=editing_id).first() if editing_id else None
    area = portal_ops_area(request)
    prefix = "portal_admin" if area == "admin" else "portal_staff"
    query = urlencode({key: value for key, value in (("q", q), ("category", category)) if value})
    suffix = f"?{query}" if query else ""
    return render(
        request,
        "portal/staff/outside_programs.html",
        _page_context(
            request,
            "Outside programs",
            programs=programs,
            filter_q=q,
            filter_category=category,
            editing=editing,
            show_form=request.GET.get("add") == "1" or bool(editing),
            list_url=_list_url(request),
            export_url=reverse(f"{prefix}_outside_programs_export") + suffix,
            print_url=reverse(f"{prefix}_outside_programs_print") + suffix,
            save_url_name=f"{prefix}_outside_program_save",
            delete_url_name=f"{prefix}_outside_program_delete",
        ),
    )


def _save_program(request, program=None):
    from .activity_log import log_activity

    name = (request.POST.get("name") or "").strip()
    if not name:
        messages.error(request, "Name is required.")
        return redirect(_list_url(request))
    if program is None:
        program = PortalOutsideProgram()
    program.name = name
    program.email = (request.POST.get("email") or "").strip()
    program.phone = (request.POST.get("phone") or "").strip()
    program.description = (request.POST.get("description") or "").strip()
    program.notes = (request.POST.get("notes") or "").strip()
    category = (request.POST.get("category") or "").strip()
    valid = {choice[0] for choice in PortalOutsideProgram.CATEGORY_CHOICES}
    program.category = category if category in valid else PortalOutsideProgram.CATEGORY_VENDOR
    program.charge_amount = _parse_amount(request.POST.get("charge_amount"))
    program.last_used_on = parse_date(request.POST.get("last_used_on") or "") or None
    program.save()
    log_activity(
        request,
        action="save",
        action_label="Saved an outside program",
        object_type="outside_program",
        object_label=program.name,
    )
    messages.success(request, f"Saved {program.name}.")
    return redirect(_list_url(request))


@staff_or_admin_required
@require_POST
def outside_program_save(request, program_id=None):
    if not _can_manage(request):
        return HttpResponseForbidden("Outside programs are for Program director and admin.")
    program = None
    if program_id:
        program = PortalOutsideProgram.objects.filter(pk=program_id).first()
        if not program:
            messages.error(request, "That outside program was not found.")
            return redirect(_list_url(request))
    return _save_program(request, program)


@staff_or_admin_required
@require_POST
def outside_program_delete(request, program_id):
    if not _can_manage(request):
        return HttpResponseForbidden("Outside programs are for Program director and admin.")
    from .activity_log import log_delete

    program = PortalOutsideProgram.objects.filter(pk=program_id).first()
    if not program:
        messages.error(request, "That outside program was not found.")
        return redirect(_list_url(request))
    try:
        label = program.name
        log_delete(request, object_type="outside_program", object_label=label)
        program.delete()
        messages.success(request, f"Deleted {label}.")
    except ValueError as exc:
        messages.error(request, str(exc))
    return redirect(_list_url(request))


@staff_or_admin_required
@require_GET
def outside_program_export(request):
    import csv

    if not _can_manage(request):
        return HttpResponseForbidden("Outside programs are for Program director and admin.")
    _q, _category, programs = _filtered_programs(request)
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="outside-programs.csv"'
    writer = csv.writer(response)
    writer.writerow(["Name", "Email", "Phone", "Category", "What they do", "Charge to YEA", "Last used", "Notes"])
    for row in programs:
        writer.writerow(
            [
                row.name,
                row.email,
                row.phone,
                row.get_category_display() if row.category else "",
                row.description,
                row.charge_display,
                row.last_used_on.isoformat() if row.last_used_on else "",
                row.notes,
            ]
        )
    return response


@staff_or_admin_required
@require_GET
def outside_program_print(request):
    if not _can_manage(request):
        return HttpResponseForbidden("Outside programs are for Program director and admin.")
    q, category, programs = _filtered_programs(request)
    return render(
        request,
        "portal/staff/outside_programs_print.html",
        _page_context(
            request,
            "Outside programs contact list",
            programs=programs,
            filter_q=q,
            filter_category=category,
            page_guide_key="outside-programs-print",
        ),
    )
