"""Live data builders for staff portal pages."""

from datetime import date, timedelta
from decimal import Decimal

from django.db.models import Count, Q
from django.utils import timezone

from enrollment.models import EnrollmentApplication
from enrollment.portal_integration import applications_for_staff

from .attendance_service import build_roster, build_session_context, get_active_program, get_unit
from .demo_data import (
    AGENCY_UNIT_DATA,
    CHILD_MEDICAL,
    DASHBOARD_ALERTS,
    FAMILIES,
    FAMILY_DETAILS,
    MEDICAL_ALERT_TYPES,
    MEDICAL_REPORT_META,
    PROGRAM_ROSTER,
    STAFF_PROGRAMS_SCHOOL_18,
    get_family_policies,
    get_member_policy_summaries,
)
from .live_services import _medical_from_application, count_messages_unread_live
from .models import AttendanceRecord, PortalChild, PortalFamily, PortalProgram
from .parent_services import get_parent_policy_data_live
from .pickup_services import pickup_report_data, pickup_report_programs


def get_programs_for_unit(unit):
    programs = PortalProgram.objects.filter(unit=unit, is_active=True).order_by("name")
    if not programs.exists():
        return []
    rows = []
    for program in programs:
        enrolled = PortalChild.objects.filter(family__unit=unit, is_active=True).count()
        rows.append(
            {
                "name": program.name,
                "enrolled": enrolled,
                "dates": "Active season",
                "slug": program.name.lower().replace(" ", "-").replace("–", "-"),
                "program_id": program.pk,
            }
        )
    return rows


def get_program_roster(unit, program_name=None):
    children = (
        PortalChild.objects.filter(family__unit=unit, is_active=True)
        .select_related("family")
        .order_by("name")
    )
    if not children.exists():
        return []
    roster = []
    for child in children:
        roster.append(
            {
                "child": child.name,
                "family": child.family.name,
                "family_slug": child.family.slug,
                "grade": child.grade,
                "status": child.family.status or "Active",
            }
        )
    return roster


def get_member_summaries_for_unit(unit):
    families = list(PortalFamily.objects.filter(unit=unit).order_by("name"))
    if not families:
        return []
    summaries = []
    for family in families:
        policy_data = get_parent_policy_data_live(family)
        if not policy_data:
            continue
        summaries.append(
            {
                "slug": family.slug,
                "name": family.name,
                "children": policy_data.get("child_count", 0),
                "signed": policy_data.get("signed_count", 0),
                "total": policy_data.get("total_count", 0),
                "complete": policy_data.get("complete", False),
                "label": family.primary_contact or family.name,
            }
        )
    return summaries


def get_family_policies_for_staff(family_slug, family_id=None):
    from .member_admin import resolve_family

    family = resolve_family(family_slug=family_slug, family_id=family_id)
    if family:
        live = get_parent_policy_data_live(family)
        if live:
            return live
    return get_family_policies(family_slug)


def get_medical_data_for_child(child_name, family_slug=None):
    demo = CHILD_MEDICAL.get(child_name, {})
    child = PortalChild.objects.filter(name=child_name).select_related("family").first()
    if family_slug and not child:
        child = PortalChild.objects.filter(family__slug=family_slug, name=child_name).first()
    if not child:
        app = (
            EnrollmentApplication.objects.filter(
                student_first_name__iexact=child_name.split()[0] if child_name else "",
            )
            .order_by("-submitted_at")
            .first()
        )
        if app:
            medical = _medical_from_application(app)
            alerts = _alerts_from_medical_dict(medical, child_name)
            return {**medical, "alerts": alerts, "staff_notes": demo.get("staff_notes", "")}
        return demo

    app = (
        EnrollmentApplication.objects.filter(portal_family=child.family)
        .order_by("-submitted_at")
        .first()
    )
    if app:
        medical = _medical_from_application(app)
        alerts = _alerts_from_medical_dict(medical, child_name)
        return {
            **medical,
            "alerts": alerts,
            "staff_notes": demo.get("staff_notes", child.note or ""),
        }
    return demo


def _alerts_from_medical_dict(medical, child_name):
    alerts = []
    allergies = (medical.get("allergies") or "").strip()
    if allergies and allergies.lower() not in ("none", "n/a", "no"):
        alerts.append({"key": "allergy", "detail": allergies})
    medications = (medical.get("medications") or "").strip()
    if medications and medications.lower() not in ("none", "n/a", "no"):
        alerts.append({"key": "medication", "detail": medications})
    for plan in medical.get("plans_on_file") or []:
        key = plan.lower().replace(" ", "_").replace("-", "_")
        if "epi" in key:
            alerts.append({"key": "epipen", "detail": plan})
        elif "asthma" in key:
            alerts.append({"key": "asthma", "detail": plan})
        elif "allergy" in key:
            alerts.append({"key": "allergy", "detail": plan})
    if not alerts:
        demo_med = CHILD_MEDICAL.get(child_name, {})
        alerts = demo_med.get("alerts", [])
    return alerts


def build_medical_report_rows(unit):
    children = (
        PortalChild.objects.filter(family__unit=unit, is_active=True)
        .select_related("family")
        .order_by("name")
    )
    if not children.exists():
        from .demo_data import build_medical_report_rows

        return build_medical_report_rows()

    rows = []
    for child in children:
        medical = get_medical_data_for_child(child.name, child.family.slug)
        alerts = []
        for item in medical.get("alerts", []):
            key = item.get("key", "")
            definition = MEDICAL_ALERT_TYPES.get(key, {})
            alerts.append(
                {
                    "key": key,
                    "label": definition.get("label", key),
                    "symbol": definition.get("symbol", "?"),
                    "detail": item.get("detail", ""),
                }
            )
        rows.append(
            {
                "child": child.name,
                "family": child.family.name,
                "grade": child.grade,
                "program": child.family.program_label or "After-School",
                "has_medical": bool(alerts or medical.get("allergies") or medical.get("medications")),
                "alerts": alerts,
                "allergies": medical.get("allergies") or "None reported",
                "medications": medical.get("medications") or "None reported",
                "doctor_name": medical.get("doctor_name") or "—",
                "doctor_phone": medical.get("doctor_phone") or "—",
                "plans_on_file": medical.get("plans_on_file") or [],
                "staff_notes": medical.get("staff_notes") or "",
            }
        )
    return rows


def medical_report_meta(unit):
    program = get_active_program(unit)
    return {
        "unit": unit.name if unit else MEDICAL_REPORT_META["unit"],
        "program": program.name if program else MEDICAL_REPORT_META["program"],
        "generated_date": timezone.localdate().strftime("%B %d, %Y"),
    }


def pickup_report_for_unit(unit, program_filter="all"):
    families = []
    family_details = {}
    for family in PortalFamily.objects.filter(unit=unit).prefetch_related("children"):
        children = [c.name for c in family.children.filter(is_active=True)]
        families.append(
            {
                "slug": family.slug,
                "name": family.name,
                "children": children,
                "program": family.program_label or "After-School 2026–27",
            }
        )
        family_details[family.slug] = {"program": family.program_label or "After-School 2026–27"}
    if not families:
        return pickup_report_programs(FAMILIES, FAMILY_DETAILS), pickup_report_data(
            FAMILIES, FAMILY_DETAILS, program_filter=program_filter
        )
    return pickup_report_programs(families, family_details), pickup_report_data(
        families, family_details, program_filter=program_filter
    )


def build_dashboard_live(unit, program):
    today = timezone.localdate()
    roster = build_roster(unit, program, today) if unit and program else []
    session = build_session_context(unit, program, today, roster) if unit and program else {}
    apps = applications_for_staff(unit) if unit else []
    open_apps = [a for a in apps if a.get("status") in ("Under review", "Pending documents", "Waitlist")]
    past_due = PortalFamily.objects.filter(unit=unit, balance__gt=Decimal("0")).count()
    unread = count_messages_unread_live(for_admin=False)

    alerts = []
    if open_apps:
        alerts.append(
            {
                "text": f"{len(open_apps)} application{'s' if len(open_apps) != 1 else ''} awaiting review",
                "link_name": "portal_staff_page",
                "link_arg": "applications",
            }
        )
    if past_due:
        alerts.append(
            {
                "text": f"{past_due} {'families' if past_due != 1 else 'family'} with balance due",
                "link_name": "portal_staff_page",
                "link_arg": "families",
            }
        )
    overdue_family = (
        PortalFamily.objects.filter(unit=unit, balance__gt=Decimal("0")).order_by("-balance").first()
    )
    if overdue_family:
        alerts.append(
            {
                "text": f"{overdue_family.name} — ${overdue_family.balance:.2f} balance due",
                "link_name": "portal_staff_family_billing",
                "link_kw": {"family_slug": overdue_family.slug},
            }
        )
    if unread:
        alerts.append(
            {
                "text": f"{unread} unread team message{'s' if unread != 1 else ''}",
                "link_name": "portal_staff_page",
                "link_arg": "messages",
            }
        )
    if not alerts:
        pass

    return {
        "attendance": session or {
            "date_display": today.strftime("%A, %B %d, %Y"),
            "summary": {
                "present": 0,
                "not_arrived": 0,
                "absent": 0,
                "enrolled": 0,
                "checked_out": 0,
            },
        },
        "application_count": len(open_apps),
        "alerts": alerts,
    }


def weekly_attendance_report_data(unit, program, anchor_date=None):
    anchor_date = anchor_date or timezone.localdate()
    monday = anchor_date - timedelta(days=anchor_date.weekday())
    weekdays = [monday + timedelta(days=i) for i in range(5)]
    roster_children = (
        PortalChild.objects.filter(family__unit=unit, is_active=True).order_by("name")
        if unit
        else []
    )
    rows = []
    for child in roster_children:
        day_marks = []
        present_count = 0
        for day in weekdays:
            record = AttendanceRecord.objects.filter(child=child, program=program, date=day).first()
            present = record and record.status == AttendanceRecord.STATUS_PRESENT
            day_marks.append(present)
            if present:
                present_count += 1
        rows.append(
            {
                "child": child.name,
                "days": day_marks,
                "weekday_labels": [d.strftime("%a") for d in weekdays],
                "total": present_count,
            }
        )
    return rows, weekdays

