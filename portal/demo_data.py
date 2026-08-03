"""Sample data for portal design previews (replaced by real models later)."""

from enrollment.policies_data import POLICIES as ENROLLMENT_POLICIES

YEA_COMPANY = {
    "name": "Youth Enrichment Academy",
    "address_line1": "279 Belmont Ave",
    "city_state_zip": "Haledon, NJ 07508",
    "phone": "973-555-0100",
    "website": "yeanj.org",
}

UNITS = [
    {
        "slug": "school-18",
        "name": "School 18",
        "program_type": "after_school",
        "active": True,
        "address": "425 18th Ave",
        "city": "Paterson, NJ 07501",
        "capacity": 75,
        "enrolled": 58,
        "manager": "Maria Santos",
        "phone": "973-555-0101",
    },
    {
        "slug": "school-26",
        "name": "School 26",
        "program_type": "after_school",
        "active": True,
        "address": "120 E 26th St",
        "city": "Paterson, NJ 07514",
        "capacity": 60,
        "enrolled": 52,
        "manager": "Lisa M.",
        "phone": "973-555-0102",
    },
    {
        "slug": "dale-ave",
        "name": "Dale Ave",
        "program_type": "after_school",
        "active": True,
        "address": "88 Dale Ave",
        "city": "Paterson, NJ 07501",
        "capacity": 45,
        "enrolled": 32,
        "manager": "James R.",
        "phone": "973-555-0103",
    },
    {
        "slug": "caldwell",
        "name": "Caldwell University",
        "program_type": "summer_camp",
        "active": True,
        "address": "120 Bloomfield Ave",
        "city": "Caldwell, NJ 07006",
        "capacity": 80,
        "enrolled": 48,
        "manager": "Maria Santos",
        "phone": "973-555-0104",
    },
]

CHECKIN_MODES = [
    {
        "key": "staff_checkin",
        "label": "Staff check-in / check-out",
        "description": "Staff mark children present or absent from the attendance roster. Default for all units.",
        "enabled": True,
    },
    {
        "key": "barcode_self",
        "label": "Child barcode ID self check-in",
        "description": "Each child scans a barcode at the door. Requires printed ID cards.",
        "enabled": False,
    },
    {
        "key": "parent_kiosk",
        "label": "Parent kiosk with e-signature",
        "description": "Parents sign in/out at a tablet kiosk. Captures pickup authorization.",
        "enabled": False,
    },
]

MEDICAL_ALERT_TYPES = {
    "allergy": {"label": "Allergy", "symbol": "AL"},
    "allergy_plan": {"label": "Allergy action plan", "symbol": "AP"},
    "asthma": {"label": "Asthma", "symbol": "AS"},
    "asthma_plan": {"label": "Asthma action plan", "symbol": "ASP"},
    "epipen": {"label": "EpiPen", "symbol": "EP"},
    "medication": {"label": "Medication", "symbol": "Rx"},
    "condition": {"label": "Medical condition", "symbol": "MC"},
    "special_needs": {"label": "Special needs", "symbol": "SN"},
    "disability": {"label": "Disability / accommodation", "symbol": "DA"},
}

CHILD_MEDICAL = {
    "Maya Jacobs": {
        "alerts": [
            {"key": "allergy", "detail": "Peanuts — severe"},
            {"key": "epipen", "detail": "EpiPen in backpack; staff may administer per plan"},
            {"key": "allergy_plan", "detail": "Allergy Action Plan on file in office"},
        ],
        "allergies": "Peanuts (severe)",
        "medications": "EpiPen — self-carry; staff may administer in emergency",
        "doctor_name": "Dr. Patel",
        "doctor_phone": "973-555-0300",
        "plans_on_file": ["Allergy Action Plan", "EpiPen authorization"],
        "staff_notes": "Nut-free snack area at table 3. EpiPen stays in red pouch on hook.",
    },
    "Ethan Chen": {
        "alerts": [
            {"key": "asthma", "detail": "Exercise-induced asthma"},
            {"key": "asthma_plan", "detail": "Asthma Action Plan on file"},
            {"key": "medication", "detail": "Rescue inhaler — self-carry with authorization"},
        ],
        "allergies": "None known",
        "medications": "Albuterol inhaler — self-administer with staff awareness",
        "doctor_name": "Dr. Kim",
        "doctor_phone": "973-555-0310",
        "plans_on_file": ["Asthma Action Plan", "Medication self-administration form"],
        "staff_notes": "May use inhaler before gym/outdoor play. Notify parent if used.",
    },
    "Amari Johnson": {
        "alerts": [
            {"key": "allergy", "detail": "Eggs, dairy"},
            {"key": "allergy_plan", "detail": "Allergy Action Plan on file"},
        ],
        "allergies": "Eggs, dairy",
        "medications": "None",
        "doctor_name": "Dr. Rivera",
        "doctor_phone": "973-555-0320",
        "plans_on_file": ["Allergy Action Plan"],
        "staff_notes": "Brings own snack daily. No shared treats.",
    },
    "Layla Thompson": {
        "alerts": [
            {"key": "special_needs", "detail": "Speech delay — prefer short, clear directions"},
        ],
        "allergies": "None known",
        "medications": "None",
        "doctor_name": "",
        "doctor_phone": "",
        "plans_on_file": ["IEP accommodation summary"],
        "staff_notes": "Check in with lead counselor if child is overwhelmed.",
    },
    "Emma Davis": {
        "alerts": [
            {"key": "allergy", "detail": "Bee stings — reported on application, pending verification"},
        ],
        "allergies": "Bee stings (parent reported)",
        "medications": "None",
        "plans_on_file": [],
        "staff_notes": "Immunization form also pending.",
    },
    "Jordan Jacobs": {
        "alerts": [],
        "allergies": "None",
        "medications": "None",
        "doctor_name": "Dr. Patel",
        "doctor_phone": "973-555-0300",
        "plans_on_file": [],
        "staff_notes": "",
    },
    "Sofia Martinez": {
        "alerts": [],
        "allergies": "None",
        "medications": "None",
        "plans_on_file": [],
        "staff_notes": "",
    },
    "Aiden Williams": {
        "alerts": [],
        "allergies": "None",
        "medications": "None",
        "plans_on_file": [],
        "staff_notes": "",
    },
    "Olivia Williams": {
        "alerts": [],
        "allergies": "None",
        "medications": "None",
        "plans_on_file": [],
        "staff_notes": "",
    },
}

PROGRAMS = [
    {
        "id": 1,
        "name": "After-School 2026–27",
        "type": "After-school",
        "start_date": "2026-09-08",
        "end_date": "2027-06-15",
        "units": ["School 18", "School 26", "Dale Ave"],
        "enrolled_count": 142,
        "status": "Active",
    },
    {
        "id": 2,
        "name": "Summer Camp 2027",
        "type": "Summer camp",
        "start_date": "2027-07-01",
        "end_date": "2027-08-15",
        "units": ["Caldwell University"],
        "enrolled_count": 48,
        "status": "Registration open",
    },
    {
        "id": 3,
        "name": "After-School 2025–26",
        "type": "After-school",
        "start_date": "2025-09-08",
        "end_date": "2026-06-12",
        "units": ["School 18", "School 26"],
        "enrolled_count": 118,
        "status": "Ended",
    },
]

STAFF_PROGRAMS_SCHOOL_18 = [
    {"name": "After-School 2026–27", "enrolled": 58, "dates": "Sep 8, 2026 – Jun 15, 2027"},
    {"name": "After-School 2025–26", "enrolled": 52, "dates": "Ended Jun 12, 2026"},
]

ATTENDANCE_SESSION = {
    "date_display": "Monday, September 8, 2026",
    "date_value": "2026-09-08",
    "program": "After-School 2026–27",
    "unit": "School 18",
    "program_start_time": "15:00",
    "program_end_time": "18:00",
    "program_start_display": "3:00 PM",
    "program_end_display": "6:00 PM",
    "summary": {
        "enrolled": 58,
        "present": 5,
        "not_arrived": 2,
        "checked_out": 1,
        "absent": 1,
    },
}

ATTENDANCE_ROSTER = [
    {
        "id": 1,
        "child": "Jordan Jacobs",
        "family": "Jacobs",
        "grade": "4th",
        "status": "present",
        "check_in": "3:12 PM",
        "check_out": "",
        "method": "Staff",
    },
    {
        "id": 2,
        "child": "Maya Jacobs",
        "family": "Jacobs",
        "grade": "1st",
        "status": "present",
        "check_in": "3:18 PM",
        "check_out": "",
        "method": "Staff",
    },
    {
        "id": 3,
        "child": "Sofia Martinez",
        "family": "Martinez",
        "grade": "2nd",
        "status": "present",
        "check_in": "3:05 PM",
        "check_out": "5:45 PM",
        "method": "Staff",
    },
    {
        "id": 4,
        "child": "Aiden Williams",
        "family": "Williams",
        "grade": "3rd",
        "status": "present",
        "check_in": "3:22 PM",
        "check_out": "",
        "method": "Barcode",
    },
    {
        "id": 5,
        "child": "Olivia Williams",
        "family": "Williams",
        "grade": "K",
        "status": "expected",
        "check_in": "",
        "check_out": "",
        "method": "",
    },
    {
        "id": 6,
        "child": "Ethan Chen",
        "family": "Chen",
        "grade": "5th",
        "status": "expected",
        "check_in": "",
        "check_out": "",
        "method": "",
    },
    {
        "id": 7,
        "child": "Amari Johnson",
        "family": "Johnson",
        "grade": "2nd",
        "status": "absent",
        "check_in": "",
        "check_out": "",
        "method": "",
        "note": "Called out sick",
    },
    {
        "id": 8,
        "child": "Layla Thompson",
        "family": "Thompson",
        "grade": "1st",
        "status": "present",
        "check_in": "3:08 PM",
        "check_out": "",
        "method": "Kiosk",
    },
]

FAMILIES = [
    {
        "slug": "jacobs",
        "name": "Jacobs",
        "primary_contact": "Jakera Jacobs",
        "children": ["Jordan Jacobs", "Maya Jacobs"],
        "balance": "127.50",
        "program": "After-School 2026–27",
        "billing_type": "Private pay",
        "status": "Active",
    },
    {
        "slug": "martinez",
        "name": "Martinez",
        "primary_contact": "Maria Martinez",
        "children": ["Sofia Martinez"],
        "balance": "45.00",
        "program": "After-School 2026–27",
        "billing_type": "4Cs",
        "status": "Active",
    },
    {
        "slug": "williams",
        "name": "Williams",
        "primary_contact": "David Williams",
        "children": ["Aiden Williams", "Olivia Williams"],
        "balance": "125.00",
        "program": "After-School 2026–27",
        "billing_type": "Scholarship",
        "status": "Active",
    },
    {
        "slug": "chen",
        "name": "Chen",
        "primary_contact": "Lisa Chen",
        "children": ["Ethan Chen"],
        "balance": "215.00",
        "program": "After-School 2026–27",
        "billing_type": "4Cs",
        "status": "Past due",
    },
    {
        "slug": "johnson",
        "name": "Johnson",
        "primary_contact": "Terrence Johnson",
        "children": ["Amari Johnson"],
        "balance": "20.00",
        "program": "After-School 2026–27",
        "billing_type": "Private pay",
        "status": "Pending membership",
    },
]

FAMILIES_BILLING = {
    "jacobs": {
        "family_name": "Jacobs",
        "slug": "jacobs",
        "running_balance": "127.50",
        "children": [
            {"name": "Jordan Jacobs", "balance": "47.50", "plan": "Weekly", "amount": "35.00/wk", "type": "Private pay"},
            {"name": "Maya Jacobs", "balance": "80.00", "plan": "Weekly", "amount": "60.00/wk", "type": "Private pay"},
        ],
        "ledger": [
            {"date": "2026-09-08", "child": "Jordan Jacobs", "type": "charge", "description": "Membership fee", "amount": "20.00"},
            {"date": "2026-09-08", "child": "Jordan Jacobs", "type": "charge", "description": "Weekly tuition", "amount": "35.00"},
            {"date": "2026-09-07", "child": "Jordan Jacobs", "type": "charge", "description": "Late pickup fee", "amount": "15.00", "manual": True},
            {"date": "2026-09-05", "child": "Maya Jacobs", "type": "payment", "description": "Autopay — card ending 4242", "amount": "-80.00"},
            {"date": "2026-09-01", "child": "Maya Jacobs", "type": "charge", "description": "Membership fee", "amount": "20.00"},
            {"date": "2026-09-01", "child": "Maya Jacobs", "type": "charge", "description": "Weekly tuition", "amount": "60.00"},
        ],
    },
    "martinez": {
        "family_name": "Martinez",
        "slug": "martinez",
        "running_balance": "45.00",
        "account_note": "Regular account — membership & parent copays only. Agency remittance is on the separate 4Cs account.",
        "children": [{"name": "Sofia Martinez", "balance": "45.00", "plan": "Weekly copay", "amount": "25.00/wk", "type": "4Cs (copay only)"}],
        "ledger": [
            {"date": "2026-09-08", "child": "Sofia Martinez", "type": "charge", "description": "Membership fee", "amount": "20.00"},
            {"date": "2026-09-08", "child": "Sofia Martinez", "type": "charge", "description": "Weekly copay (4Cs)", "amount": "25.00"},
        ],
    },
    "williams": {
        "family_name": "Williams",
        "slug": "williams",
        "running_balance": "125.00",
        "children": [
            {
                "name": "Aiden Williams",
                "balance": "50.00",
                "plan": "Weekly",
                "type": "Scholarship",
                "full_rate": "70.00/wk",
                "scholarship_discount": "20.00/wk",
                "parent_amount": "50.00/wk",
                "scholarship_name": "YEA General Scholarship",
            },
            {
                "name": "Olivia Williams",
                "balance": "75.00",
                "plan": "Weekly",
                "amount": "75.00/wk",
                "type": "Private pay",
            },
        ],
        "ledger": [
            {"date": "2026-09-08", "child": "Aiden Williams", "type": "charge", "description": "Weekly tuition", "amount": "70.00"},
            {"date": "2026-09-08", "child": "Aiden Williams", "type": "discount", "description": "YEA General Scholarship", "amount": "-20.00"},
            {"date": "2026-09-08", "child": "Olivia Williams", "type": "charge", "description": "Weekly tuition", "amount": "75.00"},
            {"date": "2026-09-07", "child": "Aiden Williams", "type": "payment", "description": "Autopay — card ending 4242", "amount": "-50.00"},
            {"date": "2026-09-07", "child": "Olivia Williams", "type": "payment", "description": "Staff — check #1042", "amount": "-75.00"},
        ],
    },
    "chen": {
        "family_name": "Chen",
        "slug": "chen",
        "running_balance": "215.00",
        "account_note": "Regular account — membership & parent copays only. Agency remittance is on the separate 4Cs account.",
        "children": [{"name": "Ethan Chen", "balance": "215.00", "plan": "Weekly copay", "amount": "30.00/wk", "type": "4Cs (copay only)"}],
        "ledger": [
            {"date": "2026-09-08", "child": "Ethan Chen", "type": "charge", "description": "Weekly copay (4Cs)", "amount": "30.00"},
            {"date": "2026-09-01", "child": "Ethan Chen", "type": "charge", "description": "Membership fee", "amount": "20.00"},
        ],
    },
    "johnson": {
        "family_name": "Johnson",
        "slug": "johnson",
        "running_balance": "20.00",
        "children": [{"name": "Amari Johnson", "balance": "20.00"}],
        "ledger": [
            {"date": "2026-09-10", "child": "Amari Johnson", "type": "charge", "description": "Membership fee", "amount": "20.00"},
        ],
    },
    "thompson": {
        "family_name": "Thompson",
        "slug": "thompson",
        "running_balance": "0.00",
        "children": [
            {"name": "Layla Thompson", "balance": "0.00", "plan": "Weekly", "amount": "60.00/wk", "type": "Private pay"},
        ],
        "ledger": [
            {"date": "2026-09-06", "child": "Layla Thompson", "type": "charge", "description": "Membership fee", "amount": "20.00"},
            {"date": "2026-09-06", "child": "Layla Thompson", "type": "charge", "description": "Weekly tuition", "amount": "60.00"},
            {"date": "2026-09-06", "child": "Layla Thompson", "type": "payment", "description": "Autopay — card ending 4242", "amount": "-80.00"},
        ],
    },
    "patel": {
        "family_name": "Patel",
        "slug": "patel",
        "running_balance": "0.00",
        "account_note": "Regular account — membership & parent copays only. Agency remittance is on the separate 4Cs account.",
        "children": [
            {"name": "Nia Patel", "balance": "0.00", "plan": "Weekly copay", "amount": "25.00/wk", "type": "4Cs (copay only)"},
        ],
        "ledger": [],
    },
    "lee": {
        "family_name": "Lee",
        "slug": "lee",
        "running_balance": "0.00",
        "children": [
            {"name": "Marcus Lee", "balance": "0.00", "plan": "Weekly", "amount": "55.00/wk", "type": "Private pay"},
        ],
        "ledger": [
            {"date": "2026-09-07", "child": "Marcus Lee", "type": "charge", "description": "Membership fee", "amount": "20.00"},
            {"date": "2026-09-07", "child": "Marcus Lee", "type": "charge", "description": "Weekly tuition", "amount": "55.00"},
            {"date": "2026-09-07", "child": "Marcus Lee", "type": "payment", "description": "Check #2201", "amount": "-75.00"},
        ],
    },
}

BILLING_CHARGE_TYPES = [
    {"value": "membership", "label": "Membership fee ($20/child)"},
    {"value": "tuition", "label": "Weekly / periodic tuition"},
    {"value": "copay", "label": "4Cs weekly copay"},
    {"value": "late_fee", "label": "Late payment fee"},
    {"value": "late_pickup", "label": "Late pickup fee"},
    {"value": "field_trip", "label": "Field trip / activity fee"},
    {"value": "manual", "label": "Other manual charge"},
]

STAFF_BILLING_PERMISSIONS = {
    "can_add_charge": True,
    "can_delete_charge": False,
    "can_add_credit": False,
    "role_label": "Unit staff (default)",
}

ADMIN_BILLING_PERMISSIONS = {
    "can_add_charge": True,
    "can_delete_charge": True,
    "can_add_credit": True,
    "role_label": "Portal admin",
}

ADMIN_DASHBOARD = {
    "total_enrolled": 190,
    "total_families": 156,
    "open_applications": 7,
    "overdue_families": 4,
    "overdue_amount": "680.00",
    "policy_completion_pct": 94,
    "staff_count": 12,
    "active_programs": 2,
    "agency_children": 12,
}

ADMIN_ENROLLMENT_BY_UNIT = [
    {"unit": "School 18", "slug": "school-18", "enrolled": 58, "capacity": 75, "programs": 1, "open_apps": 3},
    {"unit": "School 26", "slug": "school-26", "enrolled": 52, "capacity": 60, "programs": 1, "open_apps": 2},
    {"unit": "Dale Ave", "slug": "dale-ave", "enrolled": 32, "capacity": 45, "programs": 1, "open_apps": 1},
    {"unit": "Caldwell University", "slug": "caldwell", "enrolled": 48, "capacity": 80, "programs": 1, "open_apps": 1},
]

ADMIN_ALERTS = [
    {"text": "7 applications awaiting review across all units", "link_name": "portal_admin_page", "link_arg": "applications"},
    {"text": "4 families with overdue balances ($680 total)", "link_name": "portal_admin_page", "link_arg": "member-billing"},
    {"text": "1 family — zero attendance last week (review charges)", "link_name": "portal_admin_page", "link_arg": "dashboard"},
    {"text": "2 unread staff messages", "link_name": "portal_admin_page", "link_arg": "messages"},
    {"text": "Nia Patel — 0 of 12 policies signed", "link_name": "portal_admin_page", "link_arg": "member-policies"},
    {"text": "Summer Camp 2027 — 48 enrolled of 80 capacity", "link_name": "portal_admin_page", "link_arg": "programs"},
]

ADMIN_AGENCIES = [
    {
        "slug": "passaic-4cs",
        "name": "Passaic County 4Cs",
        "contact_name": "Billing Department",
        "contact_email": "billing@passaic4cs.org",
        "contact_phone": "973-555-0400",
        "contract_start": "2025-07-01",
        "contract_end": "2027-06-30",
        "default_weekly_rate": "110.00",
        "children_enrolled": 12,
        "units": ["School 18", "School 26", "Dale Ave"],
        "remittance_schedule": "Monthly (1st business day)",
        "active": True,
    },
]

PORTAL_STAFF_ROLES = [
    "Portal admin",
    "Unit director",
    "Front desk staff",
    "Unit staff",
]

FEE_RULES = [
    {
        "key": "membership",
        "name": "Membership fee",
        "amount": "20.00",
        "display": "$20.00",
        "frequency": "Per child / year",
        "period": "Sep 1 – Aug 31",
        "notes": "Posted once per child at enrollment or renewal.",
    },
    {
        "key": "late_payment",
        "name": "Late payment fee",
        "amount": "25.00",
        "display": "$25.00",
        "frequency": "Per occurrence",
        "period": "After 10-day grace period",
        "notes": "Applied when balance remains unpaid after due date.",
    },
    {
        "key": "late_pickup",
        "name": "Late pickup fee",
        "amount": "1.00",
        "display": "$1.00 / min",
        "frequency": "Per minute after 6:00 PM",
        "period": "Unit default — override per account",
        "notes": "School 18 closes at 6:00 PM; fee starts at 6:01 PM.",
    },
    {
        "key": "field_trip",
        "name": "Field trip / activity",
        "amount": "",
        "display": "Variable",
        "frequency": "One-time",
        "period": "Posted manually by staff",
        "notes": "Amount set when trip is scheduled.",
    },
]

ADMIN_REPORTS = [
    {
        "name": "Organization enrollment summary",
        "description": "Headcount by unit, program, and payment type (private pay, 4Cs, scholarship)",
        "format": "PDF / Excel",
        "slug": "enrollment",
    },
    {
        "name": "Cross-unit financial summary",
        "description": "Revenue collected, outstanding balances, and agency remittance org-wide",
        "format": "PDF / Excel",
        "slug": "financial",
    },
    {
        "name": "Outstanding balances (all units)",
        "description": "Every family with balance due — sorted by amount",
        "format": "PDF / Excel",
        "link_name": "portal_admin_page",
        "link_arg": "member-billing",
    },
    {
        "name": "4Cs agency remittance report",
        "description": "Agency charges vs payments across all 4Cs children and units",
        "format": "PDF / Excel",
        "link_name": "portal_admin_page",
        "link_arg": "agencies",
    },
    {
        "name": "Scholarship utilization",
        "description": "Assigned scholarships, discounts posted, and remaining fund balances",
        "format": "PDF / Excel",
        "link_name": "portal_admin_page",
        "link_arg": "scholarships",
    },
    {
        "name": "Member signed policies (all units)",
        "description": "Policy completion by family and child — 12 policies per child",
        "format": "PDF",
        "link_name": "portal_admin_page",
        "link_arg": "member-policies",
    },
    {
        "name": "Staff roster & portal access",
        "description": "Portal users, roles, unit assignments, and last login",
        "format": "PDF",
        "link_name": "portal_admin_page",
        "link_arg": "staff",
    },
    {
        "name": "Application pipeline",
        "description": "Submitted, under review, approved, and pending membership by unit",
        "format": "PDF / Excel",
    },
]

PORTAL_STAFF_USERS = [
    {
        "id": 1,
        "name": "Jakera Jacobs",
        "email": "jakeraj@yeanj.org",
        "role": "Portal admin",
        "units": "All units",
        "status": "Active",
        "last_login": "Sep 8, 2026",
        "can_add_charge": True,
        "can_delete_charge": True,
        "can_add_credit": True,
    },
    {
        "id": 2,
        "name": "Maria Santos",
        "email": "maria.s@yeanj.org",
        "role": "Unit director",
        "units": "School 18",
        "status": "Active",
        "last_login": "Sep 8, 2026",
        "can_add_charge": True,
        "can_delete_charge": True,
        "can_add_credit": False,
    },
    {
        "id": 3,
        "name": "James R.",
        "email": "james.r@yeanj.org",
        "role": "Front desk staff",
        "units": "School 18, Dale Ave",
        "status": "Active",
        "last_login": "Sep 7, 2026",
        "can_add_charge": True,
        "can_delete_charge": False,
        "can_add_credit": False,
    },
    {
        "id": 4,
        "name": "Lisa M.",
        "email": "lisa.m@yeanj.org",
        "role": "Unit staff",
        "units": "School 26",
        "status": "Active",
        "last_login": "Sep 6, 2026",
        "can_add_charge": True,
        "can_delete_charge": False,
        "can_add_credit": False,
    },
    {
        "id": 5,
        "name": "David K.",
        "email": "david.k@yeanj.org",
        "role": "Unit director",
        "units": "Caldwell University",
        "status": "Active",
        "last_login": "Sep 5, 2026",
        "can_add_charge": True,
        "can_delete_charge": True,
        "can_add_credit": False,
    },
    {
        "id": 6,
        "name": "Angela T.",
        "email": "angela.t@yeanj.org",
        "role": "Unit staff",
        "units": "School 18",
        "status": "Invited",
        "last_login": "—",
        "can_add_charge": True,
        "can_delete_charge": False,
        "can_add_credit": False,
    },
]


def prepare_billing_preview(billing, permissions):
    """Attach ledger ids and deletable flags for billing UI previews."""
    enriched = {**billing}
    ledger = []
    for index, row in enumerate(billing.get("ledger", [])):
        is_manual = row.get("manual") or row.get("type") in ("charge", "credit")
        ledger.append(
            {
                **row,
                "id": row.get("id", index + 1),
                "deletable": permissions.get("can_delete_charge") and is_manual and row.get("type") != "payment",
            }
        )
    enriched["ledger"] = ledger
    return enriched


PARENT_PROFILE = {
    "family_name": "Jacobs",
    "home_address": "123 Main Street, Paterson, NJ 07501",
    "primary": {
        "name": "Jakera Jacobs",
        "relationship": "Mother",
        "email": "jakeraj@yeanj.org",
        "phone": "609-357-8608",
        "phone_type": "Cell",
    },
    "secondary": {
        "name": "James Jacobs",
        "relationship": "Father",
        "email": "jjacobs@email.com",
        "phone": "973-555-0182",
        "phone_type": "Cell",
    },
    "children": [
        {
            "name": "Jordan Jacobs",
            "dob": "2016-04-12",
            "grade": "4th",
            "location": "School 18",
            "program": "After-School 2026–27",
            "allergies": "None",
            "medications": "None",
        },
        {
            "name": "Maya Jacobs",
            "dob": "2019-08-03",
            "grade": "1st",
            "location": "School 18",
            "program": "After-School 2026–27",
            "allergies": "Peanuts",
            "medications": "EpiPen on file",
        },
    ],
    "emergency_contacts": [
        {"name": "Grandma Rosa Jacobs", "phone": "973-555-0100", "relationship": "Grandmother"},
        {"name": "Uncle Mike Jacobs", "phone": "973-555-0199", "relationship": "Uncle"},
    ],
}

PARENT_PROFILE_MARTINEZ = {
    "family_name": "Martinez",
    "home_address": "45 Lakeview Ave, Paterson, NJ 07502",
    "primary": {
        "name": "Maria Martinez",
        "relationship": "Mother",
        "email": "maria.m@email.com",
        "phone": "973-555-0200",
        "phone_type": "Cell",
    },
    "secondary": {"name": "", "relationship": "", "email": "", "phone": "", "phone_type": ""},
    "children": [
        {
            "name": "Sofia Martinez",
            "dob": "2017-11-20",
            "grade": "2nd",
            "location": "School 18",
            "program": "After-School 2026–27",
            "allergies": "None",
            "medications": "None",
            "payment_type": "4Cs",
        },
    ],
    "emergency_contacts": [
        {"name": "Carlos Martinez", "phone": "973-555-0201", "relationship": "Father"},
        {"name": "Tia Rosa", "phone": "973-555-0202", "relationship": "Aunt"},
    ],
}

PARENT_PROFILE_WILLIAMS = {
    "family_name": "Williams",
    "home_address": "78 Elm Street, Paterson, NJ 07504",
    "primary": {
        "name": "David Williams",
        "relationship": "Father",
        "email": "david.w@email.com",
        "phone": "973-555-0210",
        "phone_type": "Cell",
    },
    "secondary": {
        "name": "Keisha Williams",
        "relationship": "Mother",
        "email": "keisha.w@email.com",
        "phone": "973-555-0211",
        "phone_type": "Cell",
    },
    "children": [
        {
            "name": "Aiden Williams",
            "dob": "2018-02-14",
            "grade": "3rd",
            "location": "School 18",
            "program": "After-School 2026–27",
            "allergies": "None",
            "medications": "None",
            "payment_type": "Scholarship",
        },
        {
            "name": "Olivia Williams",
            "dob": "2020-09-01",
            "grade": "K",
            "location": "School 18",
            "program": "After-School 2026–27",
            "allergies": "None",
            "medications": "None",
            "payment_type": "Private pay",
        },
    ],
    "emergency_contacts": [
        {"name": "Grandma Doris", "phone": "973-555-0212", "relationship": "Grandmother"},
    ],
}

PARENT_PAYMENT_PREVIEWS = {
    "private-pay": {
        "key": "private-pay",
        "label": "Private pay",
        "family_name": "Jacobs",
        "profile": PARENT_PROFILE,
        "billing": {
            **FAMILIES_BILLING["jacobs"],
            "payment_type": "Private pay",
            "payment_type_note": "",
        },
        "dashboard": {
            "balance": "127.50",
            "application_status": "Under review",
            "policies_signed": 24,
            "policies_total": 24,
        },
    },
    "4cs": {
        "key": "4cs",
        "label": "4Cs",
        "family_name": "Martinez",
        "profile": PARENT_PROFILE_MARTINEZ,
        "billing": {
            **FAMILIES_BILLING["martinez"],
            "payment_type": "4Cs",
            "payment_type_note": "You pay membership and your weekly copay here. Passaic County 4Cs pays YEA directly for Sofia's program — that agency portion is not on your account.",
            "agency_name": "Passaic County 4Cs",
        },
        "dashboard": {
            "balance": "45.00",
            "application_status": "Enrolled",
            "policies_signed": 12,
            "policies_total": 12,
        },
    },
    "scholarship": {
        "key": "scholarship",
        "label": "Scholarship",
        "family_name": "Williams",
        "profile": PARENT_PROFILE_WILLIAMS,
        "billing": {
            **FAMILIES_BILLING["williams"],
            "payment_type": "Scholarship",
            "payment_type_note": "Scholarship children are charged the full program rate, then a scholarship discount is applied each billing cycle. You pay the remaining amount.",
        },
        "dashboard": {
            "balance": "125.00",
            "application_status": "Enrolled",
            "policies_signed": 24,
            "policies_total": 24,
        },
    },
}

PARENT_RECEIPTS = {
    "private-pay": [
        {
            "date": "2026-09-05",
            "child": "Maya Jacobs",
            "description": "Weekly tuition — After-School Program",
            "amount": "80.00",
            "method": "Autopay — Visa ending 4242",
            "reference": "RCPT-240905-001",
            "location": "School 18",
            "program": "After-School Program 2026–27",
        },
        {
            "date": "2026-09-08",
            "child": "Jordan Jacobs",
            "description": "Membership fee + weekly tuition",
            "amount": "55.00",
            "method": "Pending — balance due",
            "reference": "INV-240908-014",
            "location": "School 18",
            "program": "After-School Program 2026–27",
        },
        {
            "date": "2026-09-01",
            "child": "Maya Jacobs",
            "description": "Membership fee + weekly tuition",
            "amount": "80.00",
            "method": "Autopay — Visa ending 4242",
            "reference": "RCPT-240901-003",
            "location": "School 18",
            "program": "After-School Program 2026–27",
        },
        {
            "date": "2026-09-15",
            "child": "Jordan Jacobs",
            "description": "After-school drop-in day",
            "amount": "35.00",
            "method": "Card — Visa ending 4242",
            "reference": "RCPT-240915-002",
            "location": "School 18",
            "program": "After-school drop-in",
        },
    ],
    "4cs": [
        {
            "date": "2026-09-08",
            "child": "Sofia Martinez",
            "description": "Membership fee + weekly copay",
            "amount": "45.00",
            "method": "Balance due",
            "reference": "INV-240908-022",
            "location": "School 18",
            "program": "After-School Program 2026–27",
        },
        {
            "date": "2026-09-01",
            "child": "Sofia Martinez",
            "description": "Weekly copay (4Cs)",
            "amount": "25.00",
            "method": "Check #2187",
            "reference": "RCPT-240901-018",
            "location": "School 18",
            "program": "After-School Program 2026–27",
        },
    ],
    "scholarship": [
        {
            "date": "2026-09-07",
            "child": "Aiden Williams",
            "description": "Weekly tuition (after scholarship)",
            "amount": "50.00",
            "method": "Autopay — Visa ending 4242",
            "reference": "RCPT-240907-008",
            "location": "School 18",
            "program": "After-School Program 2026–27",
        },
        {
            "date": "2026-09-07",
            "child": "Olivia Williams",
            "description": "Weekly tuition",
            "amount": "75.00",
            "method": "Check #1042",
            "reference": "RCPT-240907-009",
            "location": "School 18",
            "program": "After-School Program 2026–27",
        },
        {
            "date": "2026-09-08",
            "child": "Aiden Williams",
            "description": "Weekly tuition + scholarship discount",
            "amount": "50.00",
            "method": "Balance due",
            "reference": "INV-240908-031",
            "location": "School 18",
            "program": "After-School Program 2026–27",
        },
    ],
}

PARENT_DROP_IN = {
    "private-pay": {
        "status": "approved",
        "status_label": "Approved",
        "registered": True,
        "fees": {"after_school": "35", "summer_camp": "55"},
        "deadlines": {
            "after_school": "9:00 AM on day of care",
            "summer_camp": "24 hours before care date",
        },
        "locations": [
            "School 18 — after-school",
            "School 26 — after-school",
            "Dale Ave — after-school (bus to School 18)",
            "Caldwell University — summer camp",
        ],
        "bookings": [
            {
                "date": "Sep 15, 2026",
                "child": "Jordan Jacobs",
                "program": "After-school drop-in",
                "location": "School 18",
                "status": "Confirmed",
                "amount": "35.00",
            },
            {
                "date": "Aug 2, 2027",
                "child": "Maya Jacobs",
                "program": "Summer camp drop-in",
                "location": "Caldwell University",
                "status": "Confirmed",
                "amount": "55.00",
            },
        ],
        "waitlist": [],
    },
    "4cs": {
        "status": "approved",
        "status_label": "Approved",
        "registered": True,
        "fees": {"after_school": "35", "summer_camp": "55"},
        "deadlines": {
            "after_school": "9:00 AM on day of care",
            "summer_camp": "24 hours before care date",
        },
        "locations": ["School 18 — after-school"],
        "bookings": [],
        "waitlist": [],
    },
    "scholarship": {
        "status": "approved",
        "status_label": "Approved",
        "registered": True,
        "fees": {"after_school": "35", "summer_camp": "55"},
        "deadlines": {
            "after_school": "9:00 AM on day of care",
            "summer_camp": "24 hours before care date",
        },
        "locations": ["School 18 — after-school"],
        "bookings": [
            {
                "date": "Oct 3, 2026",
                "child": "Olivia Williams",
                "program": "After-school drop-in",
                "location": "School 18",
                "status": "Waitlist #2",
                "amount": "35.00",
            },
        ],
        "waitlist": [
            {
                "date": "Oct 3, 2026",
                "child": "Olivia Williams",
                "program": "After-school drop-in",
                "location": "School 18",
                "requested": "Sep 28, 2026",
            },
        ],
    },
}

PARENT_ACCOUNT = {
    "private-pay": {
        "login_email": "jakeraj@yeanj.org",
        "username": "jakeraj",
        "password_preview": "JacobsFamily2026!",
        "last_login": "September 8, 2026 at 3:42 PM",
        "autopay_enabled": True,
        "autopay_day": "Friday before each billing week",
        "email_receipts": True,
        "email_reminders": True,
        "sms_reminders": False,
        "payment_methods": [
            {
                "type": "card",
                "label": "Visa ending 4242",
                "expires": "08/2028",
                "default": True,
            },
        ],
    },
    "4cs": {
        "login_email": "maria.m@email.com",
        "username": "mmartinez",
        "password_preview": "Martinez2026!",
        "last_login": "September 7, 2026 at 5:10 PM",
        "autopay_enabled": False,
        "autopay_day": "",
        "email_receipts": True,
        "email_reminders": True,
        "sms_reminders": True,
        "payment_methods": [],
    },
    "scholarship": {
        "login_email": "david.w@email.com",
        "username": "dwilliams",
        "password_preview": "Williams2026!",
        "last_login": "September 6, 2026 at 8:22 AM",
        "autopay_enabled": True,
        "autopay_day": "Friday before each billing week",
        "email_receipts": True,
        "email_reminders": True,
        "sms_reminders": False,
        "payment_methods": [
            {
                "type": "card",
                "label": "Visa ending 4242",
                "expires": "11/2027",
                "default": True,
            },
            {
                "type": "card",
                "label": "Mastercard ending 8210",
                "expires": "03/2029",
                "default": False,
            },
        ],
    },
}

SCHOLARSHIP_FUNDS = [
    {"id": 1, "name": "YEA General Scholarship", "description": "Organization-wide need-based award", "active": True},
    {"id": 2, "name": "Paterson Youth Fund", "description": "City partnership — School 18 families", "active": True},
    {"id": 3, "name": "Summer Camp Sponsor", "description": "Caldwell summer only", "active": True},
]

SCHOLARSHIP_ASSIGNMENTS = [
    {
        "child": "Aiden Williams",
        "family": "Williams",
        "family_slug": "williams",
        "unit": "School 18",
        "fund": "YEA General Scholarship",
        "full_rate": "70.00",
        "parent_amount": "50.00",
        "discount": "20.00",
        "start": "2026-09-01",
        "end": "2027-06-15",
        "status": "Active",
    },
    {
        "child": "Layla Thompson",
        "family": "Thompson",
        "family_slug": "thompson",
        "unit": "School 18",
        "fund": "Paterson Youth Fund",
        "full_rate": "60.00",
        "parent_amount": "25.00",
        "discount": "35.00",
        "start": "2026-09-01",
        "end": "2027-06-15",
        "status": "Active",
    },
]

SCHOLARSHIP_CHILD_OPTIONS = [
    {"name": "Jordan Jacobs", "family": "Jacobs"},
    {"name": "Maya Jacobs", "family": "Jacobs"},
    {"name": "Sofia Martinez", "family": "Martinez"},
    {"name": "Aiden Williams", "family": "Williams"},
    {"name": "Olivia Williams", "family": "Williams"},
    {"name": "Ethan Chen", "family": "Chen"},
    {"name": "Amari Johnson", "family": "Johnson"},
    {"name": "Layla Thompson", "family": "Thompson"},
]

SAMPLE_APPLICATION = {
    "reference": "ac81c804-5e0d-41d5-b544-29a918f3884c",
    "status": "Under review",
    "submitted": "September 8, 2026",
    "child_name": "Jordan Jacobs",
    "program": "After-school program",
    "location": "School 18 — Paterson",
    "family_name": "Jacobs",
    "student_dob": "April 12, 2016",
    "grade": "4th",
    "primary_parent": "Jakera Jacobs",
    "primary_email": "jakeraj@yeanj.org",
    "primary_phone": "609-357-8608",
    "home_address": "123 Main Street, Paterson, NJ 07501",
    "payment_method": "Private Pay (card)",
    "payment_plan": "Weekly",
    "membership_fee_agreed": "Yes",
    "emergency_contacts": [
        {"name": "Grandma Rosa Jacobs", "phone": "973-555-0100"},
        {"name": "Uncle Mike Jacobs", "phone": "973-555-0199"},
    ],
    "policies_signed": 12,
}

# Default for backward compatibility
FAMILY_BILLING = FAMILIES_BILLING["jacobs"]

STAFF_APPLICATIONS = [
    {
        "slug": "jordan-jacobs",
        "child": "Jordan Jacobs",
        "family": "Jacobs",
        "submitted": "Sep 8, 2026",
        "program": "After-school",
        "status": "Under review",
        "returning": False,
    },
    {
        "slug": "nia-patel",
        "child": "Nia Patel",
        "family": "Patel",
        "submitted": "Sep 9, 2026",
        "program": "After-school",
        "status": "Under review",
        "returning": False,
    },
    {
        "slug": "marcus-lee",
        "child": "Marcus Lee",
        "family": "Lee",
        "submitted": "Sep 7, 2026",
        "program": "After-school",
        "status": "Approved",
        "returning": True,
    },
    {
        "slug": "emma-davis",
        "child": "Emma Davis",
        "family": "Davis",
        "submitted": "Sep 6, 2026",
        "program": "After-school",
        "status": "Pending documents",
        "returning": False,
    },
]

STAFF_APPLICATION_DETAILS = {
    "jordan-jacobs": {
        **SAMPLE_APPLICATION,
        "returning_member": False,
        "membership_required": True,
        "internal_note": "",
    },
    "nia-patel": {
        "reference": "b2c4e801-991a-4f21-9c12-882190f551aa",
        "status": "Under review",
        "submitted": "September 9, 2026",
        "child_name": "Nia Patel",
        "program": "After-school program",
        "location": "School 18 — Paterson",
        "family_name": "Patel",
        "student_dob": "March 3, 2018",
        "grade": "2nd",
        "primary_parent": "Priya Patel",
        "primary_email": "priya.patel@email.com",
        "primary_phone": "973-555-0144",
        "home_address": "88 Oak Street, Paterson, NJ 07501",
        "payment_method": "4Cs",
        "payment_plan": "Weekly",
        "membership_fee_agreed": "Yes",
        "emergency_contacts": [
            {"name": "Raj Patel", "phone": "973-555-0145"},
            {"name": "Anita Patel", "phone": "973-555-0146"},
        ],
        "policies_signed": 12,
        "returning_member": False,
        "membership_required": True,
        "internal_note": "Verify 4Cs authorization #",
    },
    "marcus-lee": {
        "reference": "c3d5f902-aa11-4b22-8d33-991200e662bb",
        "status": "Approved",
        "submitted": "September 7, 2026",
        "child_name": "Marcus Lee",
        "program": "After-school program",
        "location": "School 18 — Paterson",
        "family_name": "Lee",
        "student_dob": "July 9, 2015",
        "grade": "5th",
        "primary_parent": "Angela Lee",
        "primary_email": "angela.lee@email.com",
        "primary_phone": "973-555-0166",
        "home_address": "210 Park Ave, Paterson, NJ 07502",
        "payment_method": "Private Pay (card)",
        "payment_plan": "Bi-Weekly",
        "membership_fee_agreed": "Yes",
        "emergency_contacts": [{"name": "James Lee", "phone": "973-555-0167"}],
        "policies_signed": 12,
        "returning_member": True,
        "membership_required": False,
        "internal_note": "Returning — membership waived for fall",
    },
    "emma-davis": {
        "reference": "d4e6a013-bb22-5c33-9e44-002311f773cc",
        "status": "Pending documents",
        "submitted": "September 6, 2026",
        "child_name": "Emma Davis",
        "program": "After-school program",
        "location": "School 18 — Paterson",
        "family_name": "Davis",
        "student_dob": "January 15, 2019",
        "grade": "1st",
        "primary_parent": "Nicole Davis",
        "primary_email": "nicole.davis@email.com",
        "primary_phone": "973-555-0177",
        "home_address": "55 Cedar Lane, Paterson, NJ 07503",
        "payment_method": "Private Pay (card)",
        "payment_plan": "Weekly",
        "membership_fee_agreed": "Yes",
        "emergency_contacts": [{"name": "Tom Davis", "phone": "973-555-0178"}],
        "policies_signed": 8,
        "returning_member": False,
        "membership_required": True,
        "internal_note": "Missing immunization form",
    },
}

FAMILY_DETAILS = {
    "jacobs": PARENT_PROFILE,
    "martinez": {
        "family_name": "Martinez",
        "home_address": "45 Lakeview Ave, Paterson, NJ 07502",
        "primary": {
            "name": "Maria Martinez",
            "relationship": "Mother",
            "email": "maria.m@email.com",
            "phone": "973-555-0200",
            "phone_type": "Cell",
        },
        "secondary": {"name": "", "relationship": "", "email": "", "phone": "", "phone_type": ""},
        "children": [
            {
                "name": "Sofia Martinez",
                "dob": "2017-11-20",
                "grade": "2nd",
                "location": "School 18",
                "program": "After-School 2026–27",
                "allergies": "None",
                "medications": "None",
                "billing_type": "4Cs",
            },
        ],
        "emergency_contacts": [
            {"name": "Carlos Martinez", "phone": "973-555-0201", "relationship": "Father"},
            {"name": "Tia Rosa", "phone": "973-555-0202", "relationship": "Aunt"},
        ],
    },
}

AGENCY_UNIT_DATA = {
    "agency_name": "Passaic County 4Cs",
    "unit": "School 18",
    "children": [
        {
            "slug": "sofia-martinez",
            "child": "Sofia Martinez",
            "family": "Martinez",
            "family_slug": "martinez",
            "dob": "2017-11-20",
            "grade": "2nd",
            "program": "After-School 2026–27",
            "auth_number": "4CS-2026-8841",
            "auth_start": "2026-09-01",
            "auth_end": "2027-08-31",
            "weekly_copay": "25.00",
            "agency_rate": "110.00",
            "copay_balance": "25.00",
            "agency_balance": "0.00",
            "last_agency_payment": "2026-09-01",
            "agency_payment_amount": "440.00",
        },
        {
            "slug": "ethan-chen",
            "child": "Ethan Chen",
            "family": "Chen",
            "family_slug": "chen",
            "dob": "2014-06-12",
            "grade": "5th",
            "program": "After-School 2026–27",
            "auth_number": "4CS-2026-9012",
            "auth_start": "2026-09-01",
            "auth_end": "2027-08-31",
            "weekly_copay": "30.00",
            "agency_rate": "95.00",
            "copay_balance": "90.00",
            "agency_balance": "190.00",
            "last_agency_payment": "2026-08-25",
            "agency_payment_amount": "380.00",
        },
    ],
    "recent_agency_payments": [
        {
            "date": "2026-09-01",
            "reference": "4CS-REM-0901",
            "amount": "820.00",
            "children": "Martinez, Chen",
            "allocations": [
                {"child": "Sofia Martinez", "family_slug": "martinez", "amount": "440.00"},
                {"child": "Ethan Chen", "family_slug": "chen", "amount": "380.00"},
            ],
        },
        {
            "date": "2026-08-01",
            "reference": "4CS-REM-0801",
            "amount": "795.00",
            "children": "Martinez, Chen",
            "allocations": [
                {"child": "Sofia Martinez", "family_slug": "martinez", "amount": "415.00"},
                {"child": "Ethan Chen", "family_slug": "chen", "amount": "380.00"},
            ],
        },
    ],
    "family_options": [
        {"slug": "martinez", "name": "Martinez", "children": ["Sofia Martinez"]},
        {"slug": "chen", "name": "Chen", "children": ["Ethan Chen"]},
        {"slug": "williams", "name": "Williams", "children": ["Aiden Williams", "Olivia Williams"]},
        {"slug": "johnson", "name": "Johnson", "children": ["Amari Johnson"]},
    ],
    "program_options": ["After-School 2026–27", "Summer Camp 2027"],
}

AGENCY_BILLING = {
    "martinez": {
        "family_name": "Martinez",
        "slug": "martinez",
        "child_name": "Sofia Martinez",
        "auth_number": "4CS-2026-8841",
        "agency_name": "Passaic County 4Cs",
        "running_balance": "0.00",
        "weekly_agency_rate": "110.00",
        "ledger": [
            {"date": "2026-09-01", "type": "payment", "description": "Agency remittance 4CS-REM-0901 (batch w/ Chen)", "amount": "-440.00"},
            {"date": "2026-09-08", "type": "charge", "description": "Weekly agency rate (4 wks)", "amount": "440.00"},
            {"date": "2026-08-01", "type": "payment", "description": "Agency remittance 4CS-REM-0801 (batch w/ Chen)", "amount": "-415.00"},
            {"date": "2026-08-04", "type": "charge", "description": "Weekly agency rate (4 wks)", "amount": "440.00"},
        ],
    },
    "chen": {
        "family_name": "Chen",
        "slug": "chen",
        "child_name": "Ethan Chen",
        "auth_number": "4CS-2026-9012",
        "agency_name": "Passaic County 4Cs",
        "running_balance": "190.00",
        "weekly_agency_rate": "95.00",
        "ledger": [
            {"date": "2026-09-08", "type": "charge", "description": "Weekly agency rate (2 wks)", "amount": "190.00"},
            {"date": "2026-09-01", "type": "payment", "description": "Agency remittance 4CS-REM-0901 (batch w/ Martinez)", "amount": "-380.00"},
            {"date": "2026-09-01", "type": "charge", "description": "Weekly agency rate (4 wks)", "amount": "380.00"},
            {"date": "2026-08-01", "type": "payment", "description": "Agency remittance 4CS-REM-0801 (batch w/ Martinez)", "amount": "-380.00"},
            {"date": "2026-08-04", "type": "charge", "description": "Weekly agency rate (4 wks)", "amount": "380.00"},
        ],
    },
}

STAFF_REPORTS = [
    {
        "name": "Daily attendance sheet",
        "description": "Sign-in sheet for today",
        "format": "PDF",
        "slug": "attendance",
    },
    {
        "name": "Weekly attendance summary",
        "description": "Mon–Fri totals per child",
        "format": "PDF",
        "slug": "weekly-attendance",
    },
    {
        "name": "Daily attendance (blank)",
        "description": "Manual sign-in sheet with date and enrolled names — print and fill by hand",
        "format": "PDF",
        "slug": "attendance-blank-daily",
    },
    {
        "name": "Weekly attendance (blank)",
        "description": "Mon–Fri grid with week dates and enrolled names for manual tracking",
        "format": "PDF",
        "slug": "attendance-blank-weekly",
    },
    {
        "name": "Sign-out sheet (blank)",
        "description": "Enrolled children with parent signature & pickup time columns",
        "format": "PDF",
        "slug": "signout-blank",
    },
    {
        "name": "Enrollment roster",
        "description": "All children in program at this unit",
        "format": "PDF",
        "slug": "roster",
    },
    {
        "name": "Authorized pickup report",
        "description": "Printable list of who may pick up each child — filter by program",
        "format": "PDF",
        "slug": "pickup-report",
    },
    {
        "name": "Medical report",
        "description": "Allergies, medications, action plans & staff notes for every enrolled child",
        "format": "PDF",
        "slug": "medical",
    },
    {
        "name": "Member signed policies",
        "description": "All families — view & print signed policies on file",
        "format": "PDF",
        "slug": "member-policies",
    },
    {"name": "Application (blank)", "description": "Printable enrollment form", "format": "PDF", "slug": "application-blank"},
    {"name": "Application (filled)", "description": "From submitted application", "format": "PDF", "slug": "application-filled", "link_arg": "jordan-jacobs"},
    {"name": "Outstanding balances", "description": "Families with balance due", "format": "PDF / Excel", "slug": "balances", "link_name": "portal_staff_page", "link_arg": "families"},
    {"name": "4Cs copay report", "description": "Weekly copays & agency remittance", "format": "PDF / Excel", "slug": "4cs", "link_name": "portal_staff_page", "link_arg": "agency"},
]

PROGRAM_ROSTER = [
    {"child": "Jordan Jacobs", "family": "Jacobs", "family_slug": "jacobs", "grade": "4th", "status": "Active"},
    {"child": "Maya Jacobs", "family": "Jacobs", "family_slug": "jacobs", "grade": "1st", "status": "Active"},
    {"child": "Sofia Martinez", "family": "Martinez", "family_slug": "martinez", "grade": "2nd", "status": "Active"},
    {"child": "Aiden Williams", "family": "Williams", "family_slug": "williams", "grade": "3rd", "status": "Active"},
    {"child": "Olivia Williams", "family": "Williams", "family_slug": "williams", "grade": "K", "status": "Active"},
    {"child": "Ethan Chen", "family": "Chen", "family_slug": "chen", "grade": "5th", "status": "Active"},
    {"child": "Amari Johnson", "family": "Johnson", "family_slug": "johnson", "grade": "2nd", "status": "Pending membership"},
    {"child": "Layla Thompson", "family": "Thompson", "family_slug": "thompson", "grade": "1st", "status": "Active"},
]

MEDICAL_REPORT_META = {
    "unit": "School 18",
    "program": "After-School 2026–27",
    "generated_date": "September 8, 2026",
}


def build_medical_report_rows():
    """All enrolled children at the unit with medical snapshot for staff report."""
    rows = []
    for roster in PROGRAM_ROSTER:
        child_name = roster["child"]
        medical = CHILD_MEDICAL.get(child_name, {})
        alerts = []
        for item in medical.get("alerts", []):
            key = item["key"]
            definition = MEDICAL_ALERT_TYPES.get(key, {})
            alerts.append(
                {
                    "key": key,
                    "symbol": definition.get("symbol", "?"),
                    "label": definition.get("label", key),
                    "detail": item.get("detail", ""),
                }
            )
        rows.append(
            {
                **roster,
                "has_medical": bool(alerts),
                "alerts": alerts,
                "allergies": medical.get("allergies") or "None known",
                "medications": medical.get("medications") or "None",
                "plans_on_file": medical.get("plans_on_file") or [],
                "doctor_name": medical.get("doctor_name", ""),
                "doctor_phone": medical.get("doctor_phone", ""),
                "staff_notes": medical.get("staff_notes", ""),
            }
        )
    return rows


MEDICAL_REPORT_ROWS = build_medical_report_rows()

POLICIES_PER_CHILD = len(ENROLLMENT_POLICIES)

CHILD_POLICY_CONFIG = {
    "Jordan Jacobs": {"signed_count": 12, "signed_by": "Jakera Jacobs", "signed_date": "September 8, 2026"},
    "Maya Jacobs": {"signed_count": 12, "signed_by": "Jakera Jacobs", "signed_date": "September 8, 2026"},
    "Sofia Martinez": {"signed_count": 12, "signed_by": "Maria Martinez", "signed_date": "September 5, 2026"},
    "Aiden Williams": {"signed_count": 12, "signed_by": "David Williams", "signed_date": "September 4, 2026"},
    "Olivia Williams": {"signed_count": 12, "signed_by": "David Williams", "signed_date": "September 4, 2026"},
    "Ethan Chen": {"signed_count": 12, "signed_by": "Lisa Chen", "signed_date": "September 3, 2026"},
    "Amari Johnson": {"signed_count": 12, "signed_by": "Terrence Johnson", "signed_date": "September 10, 2026"},
    "Layla Thompson": {"signed_count": 12, "signed_by": "Angela Thompson", "signed_date": "September 6, 2026"},
    "Nia Patel": {"signed_count": 0, "signed_by": "Priya Patel", "signed_date": ""},
    "Marcus Lee": {"signed_count": 12, "signed_by": "Angela Lee", "signed_date": "September 7, 2026"},
}

FAMILY_POLICY_META = {
    "jacobs": {"program_year": "2026–27", "unit": "School 18"},
    "martinez": {"program_year": "2026–27", "unit": "School 18"},
    "williams": {"program_year": "2026–27", "unit": "School 18"},
    "chen": {"program_year": "2026–27", "unit": "School 18"},
    "johnson": {"program_year": "2026–27", "unit": "School 18"},
    "thompson": {"program_year": "2026–27", "unit": "School 18"},
    "patel": {"program_year": "2026–27", "unit": "School 18"},
    "lee": {"program_year": "2026–27", "unit": "School 26"},
}

ADMIN_MEMBER_FAMILIES = FAMILIES + [
    {
        "slug": "thompson",
        "name": "Thompson",
        "primary_contact": "Angela Thompson",
        "children": ["Layla Thompson"],
        "balance": "0.00",
        "program": "After-School 2026–27",
        "billing_type": "Private pay",
        "status": "Active",
        "unit": "School 18",
    },
    {
        "slug": "patel",
        "name": "Patel",
        "primary_contact": "Priya Patel",
        "children": ["Nia Patel"],
        "balance": "0.00",
        "program": "After-School 2026–27",
        "billing_type": "4Cs",
        "status": "Application pending",
        "unit": "School 18",
    },
    {
        "slug": "lee",
        "name": "Lee",
        "primary_contact": "Angela Lee",
        "children": ["Marcus Lee"],
        "balance": "0.00",
        "program": "After-School 2026–27",
        "billing_type": "Private pay",
        "status": "Active",
        "unit": "School 26",
    },
]


def _child_policies(child_name, signed_by_fallback=""):
    config = CHILD_POLICY_CONFIG.get(
        child_name,
        {"signed_count": 0, "signed_by": signed_by_fallback, "signed_date": ""},
    )
    signed_by = config.get("signed_by") or signed_by_fallback
    policies = []
    for index, policy in enumerate(ENROLLMENT_POLICIES):
        signed = index < config.get("signed_count", 0)
        policies.append(
            {
                "slug": policy["slug"],
                "title": policy["title"],
                "paragraphs": policy["paragraphs"],
                "acknowledgment": policy.get("acknowledgment", ""),
                "signed": signed,
                "signed_date": config.get("signed_date") if signed else None,
                "signed_by": signed_by if signed else None,
                "child_name": child_name,
            }
        )
    signed_count = sum(1 for policy in policies if policy["signed"])
    return {
        "child_name": child_name,
        "signed_by": signed_by,
        "signed_count": signed_count,
        "total_count": POLICIES_PER_CHILD,
        "complete": signed_count == POLICIES_PER_CHILD,
        "policies": policies,
    }


def get_family_policies(family_slug):
    family = next((f for f in ADMIN_MEMBER_FAMILIES if f["slug"] == family_slug), None)
    if not family:
        return None
    meta = FAMILY_POLICY_META.get(
        family_slug,
        {"program_year": "2026–27", "unit": family.get("unit", "School 18")},
    )
    children = [_child_policies(name, family["primary_contact"]) for name in family["children"]]
    signed_count = sum(child["signed_count"] for child in children)
    total_count = len(family["children"]) * POLICIES_PER_CHILD
    return {
        "family_slug": family_slug,
        "family_name": family["name"],
        "signed_by": family["primary_contact"],
        "program_year": meta["program_year"],
        "unit": meta.get("unit", family.get("unit", "School 18")),
        "children": children,
        "child_count": len(family["children"]),
        "signed_count": signed_count,
        "total_count": total_count,
        "policies_per_child": POLICIES_PER_CHILD,
        "complete": signed_count == total_count,
    }


def get_member_policy_summaries(families):
    summaries = []
    for family in families:
        data = get_family_policies(family["slug"])
        if not data:
            continue
        child_summary = ", ".join(
            f"{child['child_name'].split()[0]} {child['signed_count']}/{child['total_count']}"
            for child in data["children"]
        )
        summaries.append(
            {
                "slug": family["slug"],
                "family_name": data["family_name"],
                "primary_contact": family["primary_contact"],
                "children": family["children"],
                "child_count": data["child_count"],
                "unit": data["unit"],
                "signed_count": data["signed_count"],
                "total_count": data["total_count"],
                "policies_per_child": data["policies_per_child"],
                "complete": data["complete"],
                "program_year": data["program_year"],
                "child_summary": child_summary,
            }
        )
    return summaries


DASHBOARD_ALERTS = [
    {"text": "4 applications awaiting review", "link_name": "portal_staff_page", "link_arg": "applications"},
    {"text": "2 families past due on balance", "link_name": "portal_staff_page", "link_arg": "families"},
    {"text": "Ethan Chen — 4Cs copay overdue", "link_name": "portal_staff_family_billing", "link_kw": {"family_slug": "chen"}},
    {"text": "1 unread message from admin", "link_name": "portal_staff_page", "link_arg": "messages"},
]

STRIPE_PROCESSING_FEE = {
    "percent": 2.9,
    "fixed_cents": 30,
    "label": "Card processing fee",
    "note": "Parents pay the card processing fee (2.9% + $0.30) on online payments.",
}


def calculate_card_processing_fee(amount_str):
    try:
        amount = float(str(amount_str).replace(",", ""))
    except (TypeError, ValueError):
        amount = 0.0
    fee = round(amount * (STRIPE_PROCESSING_FEE["percent"] / 100) + STRIPE_PROCESSING_FEE["fixed_cents"] / 100, 2)
    total = round(amount + fee, 2)
    return {
        "subtotal": f"{amount:.2f}",
        "fee": f"{fee:.2f}",
        "total": f"{total:.2f}",
    }


def _unit_for_location(location_label):
    if not location_label:
        return UNITS[0]
    for unit in UNITS:
        if unit["name"] in location_label or location_label.startswith(unit["name"]):
            return unit
    return UNITS[0]


def _amount_in_words(amount_str):
    try:
        dollars = int(float(str(amount_str).replace(",", "")))
    except (TypeError, ValueError):
        dollars = 0
    ones = [
        "",
        "One",
        "Two",
        "Three",
        "Four",
        "Five",
        "Six",
        "Seven",
        "Eight",
        "Nine",
        "Ten",
        "Eleven",
        "Twelve",
        "Thirteen",
        "Fourteen",
        "Fifteen",
        "Sixteen",
        "Seventeen",
        "Eighteen",
        "Nineteen",
    ]
    tens = ["", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety"]
    if dollars == 0:
        return "Zero dollars"
    if dollars < 20:
        return f"{ones[dollars]} dollars"
    if dollars < 100:
        word = tens[dollars // 10]
        if dollars % 10:
            word = f"{word}-{ones[dollars % 10].lower()}"
        return f"{word} dollars"
    hundreds = dollars // 100
    remainder = dollars % 100
    word = f"{ones[hundreds]} hundred"
    if remainder:
        word = f"{word} {_amount_in_words(str(remainder)).replace(' dollars', '')} dollars"
    else:
        word = f"{word} dollars"
    return word


def enrich_receipt_for_print(receipt, preview_key):
    preview = PARENT_PAYMENT_PREVIEWS.get(preview_key, PARENT_PAYMENT_PREVIEWS["private-pay"])
    profile = preview["profile"]
    child_name = receipt.get("child", "")
    location_label = receipt.get("location", "School 18")
    program = receipt.get("program", "After-School Program 2026–27")
    for child in profile.get("children", []):
        if child.get("name") == child_name:
            location_label = receipt.get("location") or child.get("location", location_label)
            program = receipt.get("program") or child.get("program", program)
            break
    unit = _unit_for_location(location_label)
    is_paid = "RCPT" in receipt.get("reference", "")
    amount = receipt.get("amount", "0.00")
    paid_through = "Other"
    method = receipt.get("method", "")
    if "Visa" in method or "card" in method.lower() or "Autopay" in method or "Card" in method:
        paid_through = "Card"
    elif "Check" in method:
        paid_through = "Check"
    elif "Cash" in method:
        paid_through = "Cash"
    date_raw = receipt.get("date", "")
    try:
        from datetime import datetime

        date_display = datetime.strptime(date_raw, "%Y-%m-%d").strftime("%B %d, %Y")
    except ValueError:
        date_display = date_raw
    amount_due = receipt.get("amount_due", amount)
    amount_received = amount if is_paid else "0.00"
    balance_due = "0.00" if is_paid else amount
    return {
        **receipt,
        "receipt_no": receipt.get("reference", ""),
        "date_display": date_display,
        "received_from": f'{profile["primary"]["name"]} ({preview["family_name"]} family)',
        "amount_due": amount_due,
        "amount_received": amount_received,
        "balance_due": balance_due,
        "amount_in_words": _amount_in_words(amount),
        "payment_for": receipt.get("description", "Program payment"),
        "program": program,
        "paid_through": paid_through,
        "paid_through_detail": method if paid_through in ("Other", "Card") else "",
        "received_by": "Maria Santos — Site Director",
        "location_name": unit["name"],
        "location_address": f'{unit["address"]}, {unit["city"]}',
        "company_name": YEA_COMPANY["name"],
        "company_address_line1": YEA_COMPANY["address_line1"],
        "company_city_state_zip": YEA_COMPANY["city_state_zip"],
        "company_phone": YEA_COMPANY["phone"],
        "company_website": YEA_COMPANY["website"],
        "company": YEA_COMPANY,
        "is_paid": is_paid,
    }


def build_preview_payment_receipt(preview_key, amount_str, method_label="Visa ending 4242"):
    from datetime import date

    preview = PARENT_PAYMENT_PREVIEWS[preview_key]
    ref = f"RCPT-{date.today().strftime('%y%m%d')}-PRE"
    receipt = {
        "date": date.today().isoformat(),
        "child": preview["profile"]["children"][0]["name"] if preview["profile"].get("children") else "",
        "description": "Online program payment",
        "amount": f"{float(amount_str):.2f}",
        "method": f"Card — {method_label}",
        "reference": ref,
    }
    return enrich_receipt_for_print(receipt, preview_key)


TAX_STATEMENT_SETTINGS = {
    "require_zero_balance": True,
    "tax_year": "2025",
    "available_from": "January 15",
}

TAX_STATEMENT_ELIGIBILITY = {
    "private-pay": {"eligible": False, "balance": "127.50", "reason": "Pay your remaining balance before downloading your tax statement."},
    "4cs": {"eligible": True, "balance": "0.00", "reason": ""},
    "scholarship": {"eligible": False, "balance": "125.00", "reason": "Pay your remaining balance before downloading your tax statement."},
}

MESSAGE_CATEGORIES = [
    {"key": "coverage", "label": "Coverage"},
    {"key": "maintenance", "label": "Maintenance"},
    {"key": "emergency", "label": "Emergency"},
    {"key": "operations", "label": "Operations"},
    {"key": "general", "label": "General"},
]

MESSAGE_THREADS = [
    {
        "id": "coverage-school18",
        "subject": "Coverage needed — School 18 front desk",
        "category": "coverage",
        "unit": "School 18",
        "priority": "urgent",
        "updated_display": "Today 2:14 PM",
        "unread_for_staff": 1,
        "unread_for_admin": 0,
        "messages": [
            {
                "author": "Maria Santos",
                "role": "Unit director · School 18",
                "time": "Today 2:10 PM",
                "body": "James called out sick. Can someone cover front desk check-in until 4:30? I can stay until 3 but need handoff.",
                "is_admin": False,
            },
            {
                "author": "Jakera Jacobs",
                "role": "Portal admin",
                "time": "Today 2:14 PM",
                "body": "Lisa M. can come over from School 26 at 3:15. James R. — can you extend until Lisa arrives?",
                "is_admin": True,
            },
        ],
    },
    {
        "id": "maintenance-gym",
        "subject": "Gym AC not cooling — School 18",
        "category": "maintenance",
        "unit": "School 18",
        "priority": "normal",
        "updated_display": "Yesterday 5:42 PM",
        "unread_for_staff": 0,
        "unread_for_admin": 1,
        "messages": [
            {
                "author": "James R.",
                "role": "Front desk · School 18",
                "time": "Yesterday 5:40 PM",
                "body": "Gym feels warm after 4 PM. Kids were moved to cafeteria. Maintenance ticket #M-4412 if you need it.",
                "is_admin": False,
            },
        ],
    },
    {
        "id": "emergency-pickup",
        "subject": "Authorized pickup change — Martinez family",
        "category": "emergency",
        "unit": "School 18",
        "priority": "urgent",
        "updated_display": "Sep 8, 11:20 AM",
        "unread_for_staff": 0,
        "unread_for_admin": 0,
        "messages": [
            {
                "author": "Maria Santos",
                "role": "Unit director · School 18",
                "time": "Sep 8, 11:05 AM",
                "body": "Maria Martinez called — grandmother picking up Sofia today only. ID verified at desk. Added note on family profile.",
                "is_admin": False,
            },
            {
                "author": "Jakera Jacobs",
                "role": "Portal admin",
                "time": "Sep 8, 11:20 AM",
                "body": "Thanks — logged. Remind front desk to check photo ID against authorized pickup list.",
                "is_admin": True,
            },
        ],
    },
    {
        "id": "ops-summer-registration",
        "subject": "Summer camp registration push — all units",
        "category": "operations",
        "unit": "All units",
        "priority": "normal",
        "updated_display": "Sep 5, 9:00 AM",
        "unread_for_staff": 0,
        "unread_for_admin": 0,
        "messages": [
            {
                "author": "Jakera Jacobs",
                "role": "Portal admin",
                "time": "Sep 5, 9:00 AM",
                "body": "Please mention Summer Camp 2027 registration at pickup this week. Flyers are in the office — 48 of 80 spots filled at Caldwell.",
                "is_admin": True,
            },
        ],
    },
]

INCIDENTS = [
    {
        "id": "inc-2026-0912-01",
        "date": "2026-09-12",
        "time": "3:45 PM",
        "child": "Jordan Jacobs",
        "family_slug": "jacobs",
        "unit": "School 18",
        "type": "Injury",
        "severity": "Minor",
        "summary": "Scraped knee on playground — cleaned and bandaged",
        "location": "Playground",
        "staff_reported": "Maria Santos",
        "parent_notified": True,
        "parent_notified_time": "3:52 PM",
        "details": "Jordan fell while running during outdoor free play. Small abrasion left knee. Washed with soap/water, bandage applied, ice pack 10 min. Child returned to activity when comfortable.",
        "follow_up": "None required. Parent acknowledged at pickup.",
    },
    {
        "id": "inc-2026-0908-02",
        "date": "2026-09-08",
        "time": "4:10 PM",
        "child": "Maya Jacobs",
        "family_slug": "jacobs",
        "unit": "School 18",
        "type": "Allergy response",
        "severity": "Moderate",
        "summary": "Possible peanut exposure — EpiPen not used; monitored",
        "location": "Cafeteria",
        "staff_reported": "James R.",
        "parent_notified": True,
        "parent_notified_time": "4:12 PM",
        "details": "Another child's snack may have contained traces of peanut. Maya had no symptoms. Sat with staff, watched 30 min per allergy plan. Parent contacted immediately.",
        "follow_up": "Snack table reassignment confirmed with parent.",
    },
    {
        "id": "inc-2026-0905-03",
        "date": "2026-09-05",
        "time": "2:30 PM",
        "child": "Ethan Chen",
        "family_slug": "chen",
        "unit": "School 18",
        "type": "Behavior",
        "severity": "Low",
        "summary": "Conflict during group game — resolved with staff mediation",
        "location": "Gym",
        "staff_reported": "Lisa M.",
        "parent_notified": False,
        "parent_notified_time": "",
        "details": "Verbal disagreement with peer during dodgeball. Staff separated, discussed expectations. Both children resumed activity.",
        "follow_up": "No parent notification required per policy for minor peer conflict without injury.",
    },
]

PARENT_ANNOUNCEMENTS = {
    "private-pay": {
        "active": True,
        "title": "After-school starts Monday, September 8",
        "body": "Doors open at 3:00 PM. Remember membership fees post to your account each September. Questions? Reply through the office line — not WhatsApp.",
        "style": "info",
        "posted": "Sep 6, 2026",
        "unit": "School 18",
    },
    "4cs": {
        "active": True,
        "title": "Copay reminder",
        "body": "Your weekly 4Cs copay posts every Monday. Agency tuition is billed separately — you only pay membership and copay here.",
        "style": "info",
        "posted": "Sep 8, 2026",
        "unit": "School 18",
    },
    "scholarship": {
        "active": True,
        "title": "Scholarship discount posted",
        "body": "Your program rate and scholarship discount appear as separate lines each billing cycle. Balance due reflects your family portion only.",
        "style": "success",
        "posted": "Sep 8, 2026",
        "unit": "School 18",
    },
}

ADMIN_COMMUNICATIONS = [
    {
        "id": "ann-001",
        "title": "After-school starts Monday, September 8",
        "body": "Doors open at 3:00 PM. Remember membership fees post each September.",
        "audience": "All parents · School 18",
        "unit": "School 18",
        "payment_types": ["All payment types"],
        "channels": ["Portal banner", "Email"],
        "status": "Published",
        "posted": "Sep 6, 2026",
        "style": "info",
    },
    {
        "id": "ann-002",
        "title": "Summer Camp 2027 — registration open",
        "body": "Early registration opens October 1. Spots fill quickly — log in to apply.",
        "audience": "All parents · Caldwell University",
        "unit": "Caldwell University",
        "payment_types": ["All payment types"],
        "channels": ["Portal banner"],
        "status": "Draft",
        "posted": "—",
        "style": "promo",
    },
]

NEWSLETTER_TEMPLATES = [
    {"id": "weekly-unit", "name": "Weekly unit update", "description": "Program highlights, reminders, upcoming dates"},
    {"id": "weather-closure", "name": "Weather / closure alert", "description": "Urgent — short copy for email"},
]

NEWSLETTERS = [
    {
        "id": "nl-001",
        "title": "School 18 — Week of Sep 8",
        "template_id": "weekly-unit",
        "unit": "School 18",
        "status": "Sent",
        "sent": "Sep 6, 2026",
        "recipients": "42 families",
        "subject": "This week at School 18",
        "body": "Welcome back! This week we focus on routines, homework help, and outdoor play. Picture day is Thursday.",
    },
    {
        "id": "nl-002",
        "title": "Caldwell — Summer camp reminder",
        "template_id": "weekly-unit",
        "unit": "Caldwell University",
        "status": "Draft",
        "sent": "—",
        "recipients": "—",
        "subject": "Summer Camp 2027 — save the date",
        "body": "Registration opens soon. Reply with questions or visit the parent portal to apply.",
    },
]

SUPPORT_TICKET_CATEGORIES = [
    {"key": "billing", "label": "Billing & payments"},
    {"key": "portal", "label": "Portal / login"},
    {"key": "attendance", "label": "Attendance & schedule"},
    {"key": "technical", "label": "App / check-in"},
    {"key": "other", "label": "Other"},
]

SUPPORT_TICKETS = [
    {
        "id": "tkt-1001",
        "subject": "Payment page shows wrong balance",
        "category": "billing",
        "status": "Open",
        "from_area": "parent",
        "from_name": "Jakera Jacobs",
        "from_detail": "Jacobs family · School 18",
        "unit": "School 18",
        "preview_family": "jacobs",
        "updated_display": "Today 11:42 AM",
        "unread_for_admin": 1,
        "unread_for_user": 0,
        "messages": [
            {
                "author": "Jakera Jacobs",
                "role": "Parent",
                "time": "Today 11:40 AM",
                "body": "When I tap Pay balance, the amount is $50 higher than what billing shows. Screenshot attached.",
                "attachments": [
                    {
                        "name": "billing-screenshot.png",
                        "label": "Billing page screenshot",
                        "kind": "image",
                    },
                ],
                "is_admin": False,
            },
        ],
    },
    {
        "id": "tkt-1002",
        "subject": "Can't see tax statement download",
        "category": "portal",
        "status": "Waiting on you",
        "from_area": "parent",
        "from_name": "Jakera Jacobs",
        "from_detail": "Jacobs family · School 18",
        "unit": "School 18",
        "preview_family": "jacobs",
        "updated_display": "Yesterday 4:15 PM",
        "unread_for_admin": 0,
        "unread_for_user": 1,
        "messages": [
            {
                "author": "Jakera Jacobs",
                "role": "Parent",
                "time": "Mon 3:20 PM",
                "body": "Tax statements page says I'm eligible but there's no PDF button.",
                "attachments": [],
                "is_admin": False,
            },
            {
                "author": "YEA Support",
                "role": "Admin",
                "time": "Yesterday 4:15 PM",
                "body": "Thanks — we fixed a zero-balance check. Please refresh and try again. Let us know if the download still missing.",
                "attachments": [],
                "is_admin": True,
            },
        ],
    },
    {
        "id": "tkt-2001",
        "subject": "Check-in kiosk frozen on loading screen",
        "category": "technical",
        "status": "Open",
        "from_area": "staff",
        "from_name": "Maria Santos",
        "from_detail": "Unit director · School 18",
        "unit": "School 18",
        "updated_display": "Today 9:05 AM",
        "unread_for_admin": 1,
        "unread_for_user": 0,
        "messages": [
            {
                "author": "Maria Santos",
                "role": "Unit director · School 18",
                "time": "Today 9:02 AM",
                "body": "Front desk iPad stuck on spinner since 8:45. Parents can't sign in. Photo of screen attached.",
                "attachments": [
                    {
                        "name": "kiosk-error.jpg",
                        "label": "Kiosk loading screen",
                        "kind": "image",
                    },
                ],
                "is_admin": False,
            },
        ],
    },
    {
        "id": "tkt-2002",
        "subject": "Agency billing export missing Martinez family",
        "category": "billing",
        "status": "Resolved",
        "from_area": "staff",
        "from_name": "James Okonkwo",
        "from_detail": "Billing clerk · School 18",
        "unit": "School 18",
        "updated_display": "Sep 4, 2026",
        "unread_for_admin": 0,
        "unread_for_user": 0,
        "messages": [
            {
                "author": "James Okonkwo",
                "role": "Billing clerk · School 18",
                "time": "Sep 3, 2026",
                "body": "4Cs export for August is missing Martinez. Screenshot of roster vs export.",
                "attachments": [
                    {
                        "name": "export-mismatch.png",
                        "label": "Roster vs export",
                        "kind": "image",
                    },
                ],
                "is_admin": False,
            },
            {
                "author": "YEA Support",
                "role": "Admin",
                "time": "Sep 4, 2026",
                "body": "Fixed — Martinez was on a pending enrollment row. Re-run export and it should appear.",
                "attachments": [],
                "is_admin": True,
            },
        ],
    },
]

ABSENCE_CHARGE_ALERTS = {
    "feature_enabled": True,
    "programs_with_alerts": ["After-School 2026–27"],
    "programs_without_alerts": ["Summer Camp 2027 — pay for registered weeks whether or not child attends"],
    "families": [
        {
            "family": "Chen",
            "slug": "chen",
            "child": "Ethan Chen",
            "program": "After-School 2026–27",
            "week_label": "Sep 1–5, 2026",
            "attendance_days": 0,
            "charges_to_review": [{"description": "Weekly copay (4Cs)", "amount": "30.00"}],
        },
    ],
}

STAFF_COMPLIANCE = [
    {
        "name": "Maria Santos",
        "role": "Unit director",
        "unit": "School 18",
        "cari": "2026-03-15",
        "chri": "2026-03-15",
        "medical": "2026-09-01",
        "cpr_required": True,
        "cpr": "2027-01-20",
        "status": "Current",
    },
    {
        "name": "James R.",
        "role": "Front desk",
        "unit": "School 18",
        "cari": "2025-08-01",
        "chri": "2025-08-01",
        "medical": "2026-08-15",
        "cpr_required": True,
        "cpr": "2026-02-10",
        "status": "CPR expires in 45 days",
    },
    {
        "name": "Tanya Brooks",
        "role": "Unit staff",
        "unit": "School 18",
        "cari": "2026-06-20",
        "chri": "2026-06-20",
        "medical": "2027-03-01",
        "cpr_required": False,
        "cpr": "—",
        "status": "Current",
    },
    {
        "name": "Kevin Lee",
        "role": "Unit staff",
        "unit": "School 18",
        "cari": "2026-02-10",
        "chri": "2026-02-10",
        "medical": "2026-11-01",
        "cpr_required": False,
        "cpr": "—",
        "status": "Current",
    },
    {
        "name": "Lisa M.",
        "role": "Unit director",
        "unit": "School 26",
        "cari": "2026-01-10",
        "chri": "2026-01-10",
        "medical": "2026-10-01",
        "cpr_required": True,
        "cpr": "2026-11-05",
        "status": "Current",
    },
    {
        "name": "Ana Perez",
        "role": "Lead staff",
        "unit": "School 26",
        "cari": "2025-12-01",
        "chri": "2025-12-01",
        "medical": "2026-07-15",
        "cpr_required": True,
        "cpr": "2027-04-12",
        "status": "Current",
    },
    {
        "name": "Marcus Johnson",
        "role": "Unit staff",
        "unit": "School 26",
        "cari": "2026-04-05",
        "chri": "2026-04-05",
        "medical": "2027-01-20",
        "cpr_required": False,
        "cpr": "—",
        "status": "Current",
    },
    {
        "name": "James R.",
        "role": "Site manager",
        "unit": "Dale Ave",
        "cari": "2025-08-01",
        "chri": "2025-08-01",
        "medical": "2026-08-15",
        "cpr_required": True,
        "cpr": "2026-02-10",
        "status": "CPR expires in 45 days",
    },
    {
        "name": "Diana Ortiz",
        "role": "Lead staff",
        "unit": "Dale Ave",
        "cari": "2026-05-18",
        "chri": "2026-05-18",
        "medical": "2027-02-01",
        "cpr_required": True,
        "cpr": "2027-06-30",
        "status": "Current",
    },
    {
        "name": "Sam Rivera",
        "role": "Unit staff",
        "unit": "Dale Ave",
        "cari": "2026-03-22",
        "chri": "2026-03-22",
        "medical": "2026-12-01",
        "cpr_required": False,
        "cpr": "—",
        "status": "Current",
    },
    {
        "name": "Patricia Kim",
        "role": "Camp director",
        "unit": "Caldwell University",
        "cari": "2026-02-01",
        "chri": "2026-02-01",
        "medical": "2026-09-15",
        "cpr_required": True,
        "cpr": "2027-03-10",
        "status": "Current",
    },
    {
        "name": "Chris Nguyen",
        "role": "Lead counselor",
        "unit": "Caldwell University",
        "cari": "2025-11-20",
        "chri": "2025-11-20",
        "medical": "2026-08-01",
        "cpr_required": True,
        "cpr": "2026-09-28",
        "status": "Current",
    },
]

STAFF_COMPLIANCE_CPR_REQUIRED_PER_UNIT = 2

INCIDENT_TYPES = [
    "Injury",
    "Allergy response",
    "Behavior",
    "Medication",
    "Illness",
    "Other",
]

INCIDENT_SEVERITY_OPTIONS = ["Minor", "Moderate", "Serious"]

NJ_LICENSING_FORMS = [
    {"name": "Member enrollment form", "description": "Auto-filled from child enrollment record", "slug": "enrollment"},
    {"name": "Emergency contact binder sheet", "description": "All children at unit — contacts & pickup list", "slug": "emergency"},
    {"name": "Attendance history", "description": "Date range per child or unit", "slug": "attendance"},
    {"name": "Incident & accident log", "description": "Filter by child, site, or day", "slug": "incidents"},
]

LESSON_PLANNER_TOPICS = [
    "Team-building icebreaker",
    "STEM: simple machines",
    "Literacy: story circle",
    "Outdoor cooperative games",
    "Art: collage & self-portrait",
    "__custom__",
]

LESSON_PLANNER_SAMPLE = {
    "topic": "Team-building icebreaker",
    "age_group": "Grades 1–3",
    "group_size": 12,
    "duration": "45 minutes",
    "goals": "Learn names and practice cooperative listening.",
    "accommodations": "One child with exercise-induced asthma — keep inhaler accessible; avoid long continuous running.",
    "plan": {
        "objective": "Students will learn names and practice cooperative listening.",
        "materials": ["Name tags", "Soft ball", "Timer", "Whiteboard"],
        "steps": [
            "Welcome circle (5 min) — review expectations for safe play.",
            "Name wave (10 min) — each child says name + favorite snack.",
            "Pass the story (15 min) — each adds one sentence to a group story.",
            "Reflection (5 min) — thumbs up/down on favorite activity.",
            "Transition (10 min) — hand sanitizer, line up for snack.",
        ],
        "modifications": "For smaller group, pair children for name game. For mixed ages, assign older buddies.",
        "visual_aids": [
            {
                "title": "Welcome circle layout",
                "description": "Top-down diagram of children seated in a circle with a facilitator.",
                "image": "images/lesson-visual-overview.svg",
            },
            {
                "title": "Name tag example",
                "description": "Sample name tag with first name large and a fun icon sticker.",
                "image": "images/lesson-visual-materials.svg",
            },
            {
                "title": "Story ball pass",
                "description": "Illustration of soft ball moving child-to-child during the group story.",
                "image": "images/lesson-visual-example.svg",
            },
        ],
    },
}


def get_message_thread(thread_id):
    if thread_id:
        match = next((t for t in MESSAGE_THREADS if t["id"] == thread_id), None)
        if match:
            return match
    return MESSAGE_THREADS[0] if MESSAGE_THREADS else None


def count_unread_messages(for_admin=False):
    key = "unread_for_admin" if for_admin else "unread_for_staff"
    return sum(t.get(key, 0) for t in MESSAGE_THREADS)


def get_support_tickets(for_area, preview_family=None):
    if for_area == "admin":
        return SUPPORT_TICKETS
    if for_area == "parent":
        return [
            t
            for t in SUPPORT_TICKETS
            if t["from_area"] == "parent" and t.get("preview_family") == preview_family
        ]
    if for_area == "staff":
        return [t for t in SUPPORT_TICKETS if t["from_area"] == "staff"]
    return []


def get_support_ticket(ticket_id, for_area, preview_family=None):
    tickets = get_support_tickets(for_area, preview_family)
    if ticket_id:
        match = next((t for t in tickets if t["id"] == ticket_id), None)
        if match:
            return match
    return tickets[0] if tickets else None


def count_unread_support_tickets(for_admin=False):
    key = "unread_for_admin" if for_admin else "unread_for_user"
    tickets = SUPPORT_TICKETS if for_admin else [t for t in SUPPORT_TICKETS if t["from_area"] != "admin"]
    return sum(t.get(key, 0) for t in tickets)


def get_staff_compliance_by_unit():
    units = {}
    for row in STAFF_COMPLIANCE:
        unit = row["unit"]
        if unit not in units:
            units[unit] = {
                "unit": unit,
                "staff_count": 0,
                "cpr_required": STAFF_COMPLIANCE_CPR_REQUIRED_PER_UNIT,
                "cpr_covered": 0,
                "cpr_expiring": 0,
                "cari_current": 0,
                "chri_current": 0,
                "medical_current": 0,
            }
        entry = units[unit]
        entry["staff_count"] += 1
        if row.get("cpr_required"):
            if row.get("cpr") and row["cpr"] != "—":
                entry["cpr_covered"] += 1
            if "expires" in row.get("status", "").lower():
                entry["cpr_expiring"] += 1
        if row.get("cari"):
            entry["cari_current"] += 1
        if row.get("chri"):
            entry["chri_current"] += 1
        if row.get("medical"):
            entry["medical_current"] += 1
    return list(units.values())


def get_incident(incident_id):
    if incident_id:
        match = next((i for i in INCIDENTS if i["id"] == incident_id), None)
        if match:
            return match
    return None


def get_incidents_for_child(child_name):
    if not child_name:
        return []
    return [i for i in INCIDENTS if i.get("child") == child_name]


def get_incidents_for_family(family_slug):
    if not family_slug:
        return []
    return [i for i in INCIDENTS if i.get("family_slug") == family_slug]


def get_incidents_by_child_for_family(family_slug):
    grouped = {}
    for incident in get_incidents_for_family(family_slug):
        child = incident.get("child", "Unknown")
        grouped.setdefault(child, []).append(incident)
    return grouped


def get_incident_roster_children():
    seen = set()
    children = []
    for row in ATTENDANCE_ROSTER:
        name = row["child"]
        if name not in seen:
            seen.add(name)
            children.append(name)
    return children


def build_lesson_plan_preview(topic, goals, age_group, group_size, duration, accommodations):
    goals = (goals or "").strip()
    topic = (topic or "Custom activity").strip()
    objective = goals or f"Children will explore {topic.lower()} through hands-on, age-appropriate activities."
    materials = ["Chart paper & markers", "Timer", "Cleanup supplies", "Printed handout (optional)"]
    if "art" in topic.lower() or "collage" in topic.lower():
        materials.extend(["Construction paper", "Glue sticks", "Safety scissors", "Magazines for collage"])
    elif "stem" in topic.lower() or "machine" in topic.lower():
        materials.extend(["Building blocks or recycled materials", "Rubber bands", "Small weights"])
    elif "outdoor" in topic.lower() or "game" in topic.lower():
        materials.extend(["Cones", "Soft balls", "Whistle", "First aid kit nearby"])
    else:
        materials.extend(["Index cards", "Soft ball or talking piece"])

    steps = [
        f"Opening (5 min) — introduce today's focus: {topic}. Review safety and participation expectations.",
        f"Warm-up (8 min) — quick activity connected to: {goals or 'getting everyone involved'}.",
        f"Main activity (20 min) — guided practice where children {goals.lower() if goals else 'work together on the lesson goal'}.",
        "Check-in (5 min) — ask two reflection questions; note who needs extra support.",
        "Cleanup & transition (7 min) — reset space and preview what comes next.",
    ]
    visual_aids = [
        {
            "title": f"Activity overview — {topic}",
            "description": f"Illustrated poster showing the main steps and what success looks like for {age_group}.",
            "image": "images/lesson-visual-overview.svg",
        },
        {
            "title": "Materials setup photo",
            "description": "Labeled photo of tables arranged with all materials ready before children arrive.",
            "image": "images/lesson-visual-materials.svg",
        },
        {
            "title": "Example finished work",
            "description": f"Sample outcome so staff and children know the goal — tailored to: {goals or topic}.",
            "image": "images/lesson-visual-example.svg",
        },
    ]
    if accommodations.strip():
        modifications = (
            f"Accommodations noted: {accommodations} "
            "Offer seated alternatives, visual timers, and buddy pairs. Shorten continuous movement blocks if needed."
        )
    else:
        modifications = "Pair mixed ages, offer a quiet corner for overstimulation, and allow extra processing time."

    return {
        "topic": topic,
        "age_group": age_group or "Grades 1–3",
        "group_size": group_size or 12,
        "duration": duration or "45 minutes",
        "goals": goals,
        "accommodations": accommodations or "",
        "plan": {
            "objective": objective,
            "materials": materials,
            "steps": steps,
            "modifications": modifications,
            "visual_aids": visual_aids,
        },
    }
