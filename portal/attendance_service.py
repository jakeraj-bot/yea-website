from datetime import date, datetime, time

from django.utils.dateparse import parse_date, parse_time

from .models import AttendanceRecord, PortalChild, PortalFamily, PortalProgram, PortalUnit


DEFAULT_UNIT_SLUG = "school-18"


def portal_is_live():
    from django.conf import settings

    return not getattr(settings, "PORTAL_PREVIEW_MODE", False)


def parse_time_input(value):
    if not value:
        return datetime.now().time().replace(second=0, microsecond=0)
    if isinstance(value, time):
        return value
    parsed = parse_time(value)
    if parsed:
        return parsed
    return datetime.now().time().replace(second=0, microsecond=0)


def format_time_display(value):
    if not value:
        return ""
    if isinstance(value, str):
        return value
    hour = value.hour
    minute = value.minute
    ap = "AM" if hour < 12 else "PM"
    hour12 = hour % 12 or 12
    return f"{hour12}:{minute:02d} {ap}"


def get_attendance_date(request):
    raw = request.GET.get("date") or request.POST.get("date")
    if raw:
        parsed = parse_date(raw)
        if parsed:
            return parsed
    return date.today()


def get_unit(slug=DEFAULT_UNIT_SLUG):
    return PortalUnit.objects.filter(slug=slug, is_active=True).first()


def get_active_program(unit):
    if not unit:
        return None
    return PortalProgram.objects.filter(unit=unit, is_active=True).order_by("id").first()


def ensure_portal_seeded():
    from portal.models import PortalFamily

    return PortalChild.objects.exists() or PortalFamily.objects.exists()


def record_for_row(record):
    if not record:
        return {
            "status": AttendanceRecord.STATUS_EXPECTED,
            "check_in": "",
            "check_out": "",
            "method": "",
            "note": "",
            "has_check_in": False,
            "has_check_out": False,
        }
    return {
        "status": record.status,
        "check_in": format_time_display(record.check_in_time),
        "check_out": format_time_display(record.check_out_time),
        "method": record.method or "",
        "note": record.note or "",
        "has_check_in": bool(record.check_in_time),
        "has_check_out": bool(record.check_out_time),
    }


def child_can_check_out(record_data):
    return record_data["has_check_in"] and not record_data["has_check_out"]


def build_roster(unit, program, attendance_date):
    if not unit or not program:
        return []

    children = (
        PortalChild.objects.filter(family__unit=unit, is_active=True)
        .select_related("family")
        .order_by("name")
    )
    records = {
        record.child_id: record
        for record in AttendanceRecord.objects.filter(program=program, date=attendance_date, child__in=children)
    }

    roster = []
    for child in children:
        record = records.get(child.id)
        row_data = record_for_row(record)
        roster.append(
            {
                "id": child.id,
                "child": child.name,
                "family": child.family.name,
                "grade": child.grade,
                "status": row_data["status"],
                "check_in": row_data["check_in"],
                "check_out": row_data["check_out"],
                "method": row_data["method"],
                "note": child.note or row_data["note"],
                "can_check_in": True,
                "can_check_out": child_can_check_out(row_data),
                "is_complete": row_data["has_check_in"] and row_data["has_check_out"],
            }
        )
    return roster


def compute_summary(roster, enrolled_total=None):
    present = sum(1 for row in roster if row["status"] == AttendanceRecord.STATUS_PRESENT)
    absent = sum(1 for row in roster if row["status"] == AttendanceRecord.STATUS_ABSENT)
    expected = sum(1 for row in roster if row["status"] == AttendanceRecord.STATUS_EXPECTED)
    checked_out = sum(1 for row in roster if row["check_out"])
    enrolled = enrolled_total if enrolled_total is not None else len(roster)
    return {
        "enrolled": enrolled,
        "present": present,
        "not_arrived": expected,
        "checked_out": checked_out,
        "absent": absent,
    }


def build_session_context(unit, program, attendance_date, roster):
    from django.utils.formats import date_format

    date_display = date_format(attendance_date, "l, F j, Y")
    return {
        "date_display": date_display,
        "date_value": attendance_date.isoformat(),
        "program": program.name if program else "",
        "unit": unit.name if unit else "",
        "program_start_time": program.start_time.strftime("%H:%M") if program else "15:00",
        "program_end_time": program.end_time.strftime("%H:%M") if program else "18:00",
        "program_start_display": format_time_display(program.start_time) if program else "3:00 PM",
        "program_end_display": format_time_display(program.end_time) if program else "6:00 PM",
        "summary": compute_summary(roster),
    }


def get_or_create_record(child, program, attendance_date):
    record, _ = AttendanceRecord.objects.get_or_create(
        child=child,
        program=program,
        date=attendance_date,
        defaults={"status": AttendanceRecord.STATUS_EXPECTED},
    )
    return record


def check_in_child(child_id, program, attendance_date, check_in_time, method="Staff", note=""):
    child = PortalChild.objects.get(pk=child_id, is_active=True)
    record = get_or_create_record(child, program, attendance_date)
    record.status = AttendanceRecord.STATUS_PRESENT
    record.check_in_time = check_in_time
    record.check_out_time = None
    record.method = method or "Staff"
    if note:
        record.note = note
    record.save()
    return record


def check_out_child(child_id, program, attendance_date, check_out_time):
    child = PortalChild.objects.get(pk=child_id, is_active=True)
    record = get_or_create_record(child, program, attendance_date)
    if not record.check_in_time:
        raise ValueError("Child must be checked in before check out.")
    record.check_out_time = check_out_time
    record.save()
    return record


def mark_absent(child_id, program, attendance_date, note=""):
    child = PortalChild.objects.get(pk=child_id, is_active=True)
    record = get_or_create_record(child, program, attendance_date)
    record.status = AttendanceRecord.STATUS_ABSENT
    record.check_in_time = None
    record.check_out_time = None
    record.method = ""
    if note:
        record.note = note
    record.save()
    return record


def undo_absent(child_id, program, attendance_date):
    child = PortalChild.objects.get(pk=child_id, is_active=True)
    record = get_or_create_record(child, program, attendance_date)
    record.status = AttendanceRecord.STATUS_EXPECTED
    record.check_in_time = None
    record.check_out_time = None
    record.method = ""
    record.save()
    return record


def families_for_staff(unit):
    from enrollment.application_review import repair_family_units_from_applications
    from enrollment.models import EnrollmentApplication
    from enrollment.portal_integration import family_display_label

    repair_family_units_from_applications()
    families = PortalFamily.objects.filter(unit=unit).prefetch_related("children")
    rows = []
    for family in families:
        enrolled = [child.name for child in family.children.filter(is_active=True)]
        enrolled_lower = {name.lower() for name in enrolled}
        pending_children = []
        for app in EnrollmentApplication.objects.filter(portal_family=family).order_by("-submitted_at"):
            child_name = f"{app.student_first_name} {app.student_last_name}".strip()
            if child_name.lower() not in enrolled_lower and app.status not in {"declined", "enrolled"}:
                pending_children.append(child_name)
        rows.append(
            {
                "id": family.pk,
                "slug": family.slug,
                "name": family_display_label(family),
                "primary_contact": family.primary_contact,
                "children": enrolled + pending_children,
                "school": ", ".join(
                    sorted({child.school for child in family.children.filter(is_active=True) if child.school})
                )
                or "—",
                "balance": format(family.balance, ".2f"),
                "program": family.program_label,
                "billing_type": family.billing_type,
                "status": "Suspended" if family.is_suspended else family.status,
                "has_application": family.enrollment_applications.exists(),
            }
        )
    return rows


def attendance_redirect(request, attendance_date, extra_query=""):
    from django.shortcuts import redirect
    from django.urls import reverse

    url = reverse("portal_staff_page", kwargs={"page": "attendance"})
    query = f"date={attendance_date.isoformat()}"
    if extra_query:
        query = f"{query}&{extra_query}"
    return redirect(f"{url}?{query}")
