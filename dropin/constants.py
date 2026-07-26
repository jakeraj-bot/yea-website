from datetime import time
from decimal import Decimal

PROGRAM_AFTER_SCHOOL = "after_school"
PROGRAM_SUMMER_CAMP = "summer_camp"

PROGRAM_CHOICES = [
    (PROGRAM_AFTER_SCHOOL, "After-school drop-in"),
    (PROGRAM_SUMMER_CAMP, "Summer camp drop-in"),
]

LOCATION_CHOICES = [
    ("school_18", "School 18 — Paterson"),
    ("school_26", "School 26 — Paterson"),
    ("dale_ave", "Dale Ave — Paterson (bus to School 18)"),
    ("caldwell", "Caldwell University"),
]

AFTER_SCHOOL_LOCATIONS = {"school_18", "school_26", "dale_ave"}
SUMMER_CAMP_LOCATIONS = {"caldwell"}

FEE_DOLLARS = {
    PROGRAM_AFTER_SCHOOL: Decimal("20.00"),
    PROGRAM_SUMMER_CAMP: Decimal("35.00"),
}

# Same-day signup deadlines (America/New_York, configured in settings.TIME_ZONE)
SIGNUP_DEADLINE = {
    PROGRAM_AFTER_SCHOOL: time(14, 0),  # 2:00 PM
    PROGRAM_SUMMER_CAMP: time(7, 30),  # 7:30 AM
}

DEADLINE_LABEL = {
    PROGRAM_AFTER_SCHOOL: "2:00 PM on the day of care",
    PROGRAM_SUMMER_CAMP: "7:30 AM on the day of care",
}

# Every YEA location offers drop-in for its program(s).
DROPIN_LOCATIONS_BY_PROGRAM = {
    PROGRAM_AFTER_SCHOOL: [
        ("school_18", "School 18 — Paterson"),
        ("school_26", "School 26 — Paterson"),
        ("dale_ave", "Dale Ave — Paterson (bus to School 18)"),
    ],
    PROGRAM_SUMMER_CAMP: [
        ("caldwell", "Caldwell University"),
    ],
}

ALL_DROPIN_LOCATION_LABELS = [label for _, label in LOCATION_CHOICES]
