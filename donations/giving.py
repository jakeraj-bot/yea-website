"""Donation and sponsorship options for the donate page."""

AFTER_SCHOOL_WEEKS = 42
AFTER_SCHOOL_WEEKLY = 70
SUMMER_WEEKS = 6
SUMMER_WEEKLY = 290

AFTER_SCHOOL_ANNUAL = AFTER_SCHOOL_WEEKS * AFTER_SCHOOL_WEEKLY
SUMMER_ANNUAL = SUMMER_WEEKS * SUMMER_WEEKLY

MIN_GIFT = 25
SUGGESTED_AMOUNTS = [25, 50, 75, 100]
FIELD_TRIP_AMOUNTS = [50, 100, 250]
BUS_AMOUNTS = [25, 50, 100]

PAYMENT_PLANS = {
    "after_school": [
        {"id": "monthly", "label": "Monthly (10 months)", "amount": AFTER_SCHOOL_ANNUAL // 10},
        {"id": "full", "label": "Pay in full", "amount": AFTER_SCHOOL_ANNUAL},
        {"id": "biweekly", "label": "Bi-weekly (21 payments)", "amount": AFTER_SCHOOL_ANNUAL // 21},
        {"id": "weekly", "label": "Weekly (42 payments)", "amount": AFTER_SCHOOL_WEEKLY},
    ],
    "summer_camp": [
        {"id": "monthly", "label": "Monthly (2 months)", "amount": SUMMER_ANNUAL // 2},
        {"id": "full", "label": "Pay in full", "amount": SUMMER_ANNUAL},
        {"id": "weekly", "label": "Weekly (6 payments)", "amount": SUMMER_WEEKLY},
    ],
}

GIVING_CARDS = [
    {
        "id": "sponsor-child-afterschool",
        "title": "Sponsor a child — after-school",
        "description": (
            "Cover a full school year of after-school for one student "
            f"(September–June, {AFTER_SCHOOL_WEEKS} weeks)."
        ),
        "type": "fixed_with_plans",
        "total": AFTER_SCHOOL_ANNUAL,
        "plans": PAYMENT_PLANS["after_school"],
        "accent": "orange",
    },
    {
        "id": "sponsor-child-summer",
        "title": "Sponsor a child — summer camp",
        "description": (
            "Cover a full summer at Caldwell University for one camper "
            f"(July 6 – August 14, {SUMMER_WEEKS} weeks)."
        ),
        "type": "fixed_with_plans",
        "total": SUMMER_ANNUAL,
        "plans": PAYMENT_PLANS["summer_camp"],
        "accent": "blue",
    },
    {
        "id": "sponsor-supplies",
        "title": "Sponsor supplies",
        "description": "Help stock classrooms with materials, backpacks, and enrichment supplies.",
        "type": "suggested_amounts",
        "amounts": SUGGESTED_AMOUNTS,
        "accent": "green",
    },
    {
        "id": "back-to-school",
        "title": "Back-to-school giving",
        "description": "Help families get ready for the new school year with supplies and program support.",
        "type": "suggested_amounts",
        "amounts": SUGGESTED_AMOUNTS,
        "accent": "purple",
    },
    {
        "id": "sponsor-program",
        "title": "Sponsor our program",
        "description": "Support staffing, enrichment, and growth into new school and community partnerships.",
        "type": "custom_amount",
        "allow_recurring": True,
        "accent": "teal",
    },
    {
        "id": "sponsor-field-trip",
        "title": "Sponsor a field trip",
        "description": "Fund museum visits, community outings, and hands-on learning beyond the classroom.",
        "type": "suggested_amounts",
        "amounts": FIELD_TRIP_AMOUNTS,
        "accent": "blue",
    },
    {
        "id": "sponsor-bus",
        "title": "Sponsor bus transportation",
        "description": "Help children who need transportation get to and from our programs safely each day.",
        "type": "suggested_amounts",
        "amounts": BUS_AMOUNTS,
        "accent": "orange",
    },
    {
        "id": "school-26-launch",
        "title": "School 26 launch fund",
        "description": "Support our newest Paterson site as we grow enrollment and outfit the space for students.",
        "type": "custom_amount",
        "allow_recurring": False,
        "accent": "green",
    },
]


def amount_with_processing_fee(amount_dollars):
    """Gross-up so YEA receives the intended gift after Stripe fees (~2.9% + $0.30)."""
    return round((amount_dollars + 0.30) / (1 - 0.029), 2)
