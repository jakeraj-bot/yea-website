"""Authorized pickup lists for staff portal."""

from .attendance_service import portal_is_live


def _portal_data_live():
    return portal_is_live()


def _person(name, phone, relationship, source):
    return {
        "name": name.strip(),
        "phone": phone or "",
        "relationship": relationship or "",
        "source": source,
    }


def _unique_people(people):
    seen = set()
    rows = []
    for person in people:
        key = (person["name"].lower(), person["phone"])
        if not person["name"] or key in seen:
            continue
        seen.add(key)
        rows.append(person)
    return rows


def pickup_people_from_application(app):
    people = []
    if app.primary_authorized_pickup == "yes":
        people.append(
            _person(
                f"{app.primary_first_name} {app.primary_last_name}",
                app.primary_phone,
                app.get_primary_relationship_display(),
                "Primary guardian",
            )
        )
    if app.secondary_authorized_pickup == "yes" and app.secondary_first_name:
        people.append(
            _person(
                f"{app.secondary_first_name} {app.secondary_last_name}",
                app.secondary_phone,
                app.get_secondary_relationship_display() if app.secondary_relationship else "Secondary guardian",
                "Secondary guardian",
            )
        )
    for contact in app.emergency_contacts.all():
        if contact.authorized_pickup:
            people.append(
                _person(
                    f"{contact.first_name} {contact.last_name}",
                    contact.phone,
                    contact.relationship,
                    "Emergency contact",
                )
            )
    return _unique_people(people)


def pickup_people_from_profile(profile):
    people = []
    primary = profile.get("primary") or {}
    if primary.get("name"):
        people.append(
            _person(
                primary["name"],
                primary.get("phone", ""),
                primary.get("relationship", "Primary guardian"),
                "Primary guardian",
            )
        )
    secondary = profile.get("secondary") or {}
    if secondary.get("name"):
        people.append(
            _person(
                secondary["name"],
                secondary.get("phone", ""),
                secondary.get("relationship", "Secondary guardian"),
                "Secondary guardian",
            )
        )
    for contact in profile.get("emergency_contacts") or []:
        people.append(
            _person(
                contact.get("name", ""),
                contact.get("phone", ""),
                contact.get("relationship", "Emergency contact"),
                "Emergency contact",
            )
        )
    return _unique_people(people)


def family_authorized_pickup(profile, family_slug=None):
    """Return children and authorized pickup people for a family profile."""
    children = []
    for child in profile.get("children") or []:
        children.append(
            {
                "name": child.get("name", ""),
                "grade": child.get("grade", ""),
                "program": child.get("program", ""),
            }
        )

    people = pickup_people_from_profile(profile)

    if family_slug and _portal_data_live():
        from enrollment.models import EnrollmentApplication
        from portal.models import PortalFamily

        family = PortalFamily.objects.filter(slug=family_slug).first()
        if family:
            apps = EnrollmentApplication.objects.filter(portal_family=family).prefetch_related(
                "emergency_contacts"
            )
            for app in apps:
                people.extend(pickup_people_from_application(app))
            people = _unique_people(people)

    return {"children": children, "authorized": people}


def pickup_report_data(families, family_details, program_filter="all"):
    """Build printable report rows. program_filter: 'all' or substring match."""
    rows = []
    for family in families:
        slug = family.get("slug")
        profile = family_details.get(slug)
        if not profile:
            continue
        authorized = family_authorized_pickup(
            profile, family_slug=slug if _portal_data_live() else None
        )["authorized"]
        for child in profile.get("children") or []:
            program = child.get("program", family.get("program", ""))
            if program_filter != "all" and program_filter.lower() not in program.lower():
                continue
            if not authorized:
                rows.append(
                    {
                        "child": child.get("name", ""),
                        "family": profile.get("family_name", family.get("name", "")),
                        "program": program,
                        "grade": child.get("grade", ""),
                        "pickup_name": "—",
                        "pickup_phone": "—",
                        "relationship": "—",
                        "source": "—",
                    }
                )
                continue
            for person in authorized:
                rows.append(
                    {
                        "child": child.get("name", ""),
                        "family": profile.get("family_name", family.get("name", "")),
                        "program": program,
                        "grade": child.get("grade", ""),
                        "pickup_name": person["name"],
                        "pickup_phone": person["phone"],
                        "relationship": person["relationship"],
                        "source": person["source"],
                    }
                )
    rows.sort(key=lambda row: (row["program"], row["child"], row["pickup_name"]))
    return rows


def pickup_report_programs(families, family_details):
    programs = set()
    for family in families:
        profile = family_details.get(family.get("slug"))
        if not profile:
            continue
        for child in profile.get("children") or []:
            if child.get("program"):
                programs.add(child["program"])
            elif family.get("program"):
                programs.add(family["program"])
    return sorted(programs)


def _truthy_flag(value):
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def emergency_contacts_from_application(app):
    """Emergency contacts stored on an enrollment application."""
    contacts = []
    if not app:
        return contacts
    for contact in app.emergency_contacts.all():
        name = f"{contact.first_name} {contact.last_name}".strip()
        if not name:
            continue
        contacts.append(
            {
                "name": name,
                "phone": contact.phone or "",
                "relationship": contact.relationship or "",
                "authorized_pickup": bool(contact.authorized_pickup),
            }
        )
    return contacts


def emergency_contacts_from_profile(profile):
    """Emergency contacts on a family profile (live or demo)."""
    contacts = []
    for contact in (profile or {}).get("emergency_contacts") or []:
        name = (contact.get("name") or "").strip()
        if not name:
            continue
        contacts.append(
            {
                "name": name,
                "phone": contact.get("phone") or "",
                "relationship": contact.get("relationship") or "",
                "authorized_pickup": _truthy_flag(contact.get("authorized_pickup")),
            }
        )
    return contacts


def _blank_contact_row():
    return {
        "contact_name": "—",
        "contact_phone": "—",
        "relationship": "—",
        "authorized_pickup": "",
        "authorized_label": "—",
        "has_contact": False,
    }


def _contact_row(contact):
    authorized = bool(contact.get("authorized_pickup"))
    return {
        "contact_name": contact.get("name") or "—",
        "contact_phone": contact.get("phone") or "—",
        "relationship": contact.get("relationship") or "—",
        "authorized_pickup": "yes" if authorized else "no",
        "authorized_label": "Yes" if authorized else "No",
        "has_contact": True,
    }


def child_emergency_contact_rows(base, contacts):
    if not contacts:
        return [{**base, **_blank_contact_row()}]
    return [{**base, **_contact_row(contact)} for contact in contacts]


def emergency_contact_report_data(families, family_details):
    """Build printable emergency-contact rows from demo/preview family profiles."""
    rows = []
    for family in families:
        slug = family.get("slug")
        profile = family_details.get(slug)
        if not profile:
            continue
        contacts = emergency_contacts_from_profile(profile)
        family_name = profile.get("family_name", family.get("name", ""))
        unit_name = ""
        for child in profile.get("children") or []:
            unit_name = child.get("location") or child.get("unit_name") or unit_name
        if not unit_name:
            unit_name = family.get("unit") or "School 18"
        unit_slug = family.get("unit_slug") or "school-18"
        for child in profile.get("children") or []:
            program = child.get("program", family.get("program", ""))
            school = (child.get("school") or child.get("location") or "").strip()
            base = {
                "child": child.get("name", ""),
                "family": family_name,
                "family_slug": slug or "",
                "unit": child.get("unit_name") or child.get("location") or unit_name,
                "unit_slug": child.get("unit_slug") or unit_slug,
                "program": program or "After-school program",
                "grade": child.get("grade") or "—",
                "school": school or "—",
            }
            rows.extend(child_emergency_contact_rows(base, contacts))
    rows.sort(key=lambda row: (row["unit"].lower(), row["child"].lower(), row["contact_name"].lower()))
    return rows


def emergency_contact_report_options(rows):
    programs = sorted({row["program"] for row in rows if row.get("program")})
    schools = sorted({row["school"] for row in rows if row.get("school") and row["school"] != "—"})
    grades = sorted({row["grade"] for row in rows if row.get("grade") and row["grade"] != "—"})
    children = sorted({row["child"] for row in rows if row.get("child")})
    families = []
    family_seen = set()
    units = []
    unit_seen = set()
    for row in rows:
        family_key = row.get("family_slug") or row.get("family")
        if family_key and family_key not in family_seen:
            family_seen.add(family_key)
            families.append({"slug": family_key, "name": row.get("family") or family_key})
        unit_key = row.get("unit_slug") or row.get("unit")
        if unit_key and unit_key not in unit_seen:
            unit_seen.add(unit_key)
            units.append({"slug": row.get("unit_slug") or "", "name": row.get("unit") or unit_key})
    families.sort(key=lambda item: item["name"].lower())
    units.sort(key=lambda item: (item["name"] or "").lower())
    return {
        "programs": programs,
        "schools": schools,
        "grades": grades,
        "children": children,
        "families": families,
        "units": units,
    }


def filter_emergency_contact_rows(rows, filters=None):
    """Keep rows that match every selected filter. Empty filters mean 'all'."""
    filters = filters or {}
    unit = str(filters.get("unit") or "").strip()
    program = str(filters.get("program") or "").strip()
    school = str(filters.get("school") or "").strip()
    family = str(filters.get("family") or "").strip()
    child = str(filters.get("child") or "").strip()
    grade = str(filters.get("grade") or "").strip()
    query = str(filters.get("q") or "").strip().lower()
    authorized = str(filters.get("authorized") or "").strip().lower()
    missing = _truthy_flag(filters.get("missing"))
    kept = []
    for row in rows:
        if unit and row.get("unit_slug") != unit and row.get("unit") != unit:
            continue
        if program and row.get("program") != program:
            continue
        if school and row.get("school") != school:
            continue
        if family and row.get("family_slug") != family and row.get("family") != family:
            continue
        if child and row.get("child") != child:
            continue
        if grade and row.get("grade") != grade:
            continue
        if missing and row.get("has_contact"):
            continue
        if authorized in {"yes", "no"} and row.get("authorized_pickup") != authorized:
            continue
        if query:
            haystack = " ".join(
                [
                    row.get("contact_name") or "",
                    row.get("contact_phone") or "",
                    row.get("relationship") or "",
                ]
            ).lower()
            if query not in haystack:
                continue
        kept.append(row)
    return kept
