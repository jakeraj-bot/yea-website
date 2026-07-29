"""Authorized pickup lists for staff portal."""

from .attendance_service import portal_is_live, ensure_portal_seeded


def _portal_data_live():
    return portal_is_live() and ensure_portal_seeded()


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
        authorized = pickup_people_from_profile(profile)
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
