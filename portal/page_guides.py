"""Click-to-open how-to walkthroughs for staff, admin, and selected parent pages."""

GUIDES = {
    "dashboard": {
        "title": "How to start the day",
        "intro": "This is the Today page for the unit in the header. Use it to see who is here and jump to the work you need.",
        "steps": [
            {
                "title": "Check who is here",
                "body": "The cards at the top show who is present, who has not arrived, who is absent, and how many applications still need a decision.",
            },
            {
                "title": "Open what needs attention",
                "body": "If a Needs attention list appears, tap a line to go straight to that family, application, or message.",
            },
            {
                "title": "Use the yellow buttons",
                "body": "Attendance roster is check-in and check-out. Drop-off pickup is the school pickup list. Families is the full member list for this unit.",
            },
            {
                "title": "Switch units if you work at more than one site",
                "body": "Use the unit menu in the header. Everything on this page is for the unit that is selected.",
            },
        ],
    },
    "admin-dashboard": {
        "title": "How to use organization admin",
        "intro": "Admin is for the whole organization. Day-to-day unit work lives in the staff portal — same login.",
        "steps": [
            {
                "title": "Open staff without a second account",
                "body": "Click Staff portal in the header (or Switch to staff in the menu). You do not need a separate staff login to take attendance, see families, or run a unit.",
            },
            {
                "title": "Pick the unit",
                "body": "Once you are in staff, choose the site from the unit menu in the header if you work at more than one location.",
            },
            {
                "title": "Come back to admin anytime",
                "body": "Use Admin portal in the header when you need billing settings, staff accounts, or organization reports.",
            },
        ],
    },
    "programs": {
        "title": "How to use programs",
        "intro": "This list is the program sessions at your unit. Staff do not create programs here — that is done in portal admin.",
        "steps": [
            {
                "title": "Open a roster",
                "body": "Click View roster to see who is enrolled in that session, with medical icons.",
            },
            {
                "title": "Take attendance",
                "body": "Use Attendance in the menu (or the attendance link on a program) to check children in and out for today.",
            },
        ],
    },
    "program-roster": {
        "title": "How to use a program roster",
        "intro": "This is the enrolled list for one session.",
        "steps": [
            {
                "title": "Find a child",
                "body": "Use search if the list is long. Medical icons on a row mean you should hover or open the family profile before you release the child.",
            },
            {
                "title": "Open the family",
                "body": "Use Profile to see pickup people, billing, and medical details.",
            },
            {
                "title": "Print or take attendance",
                "body": "Export roster PDF for a paper copy. Today’s attendance is the live check-in screen.",
            },
        ],
    },
    "attendance": {
        "title": "How to take attendance",
        "intro": "This is the live roster for the date at the top. Check children in when they arrive and out when they leave.",
        "steps": [
            {
                "title": "Confirm the date and unit",
                "body": "The unit is in the header. Change the date if you are looking at another day.",
            },
            {
                "title": "Check one child in",
                "body": "Use + Check in. Choose the child, how they arrived, and the time. Add a note if something is unusual.",
            },
            {
                "title": "Check a group in",
                "body": "Use Bulk / multiples when a bus or whole group arrives together. You can use the program start time if that matches when they walked in.",
            },
            {
                "title": "Check out or mark absent",
                "body": "+ Check out (or bulk checkout) when they leave. Mark Absent if they will not attend. Undo absent if they show up later.",
            },
            {
                "title": "Read medical icons",
                "body": "Hover an icon for the allergy or plan. Open Medical report (PDF) if you need a full printout for the room.",
            },
        ],
    },
    "drop-off-pickup": {
        "title": "How to run drop-off pickup",
        "intro": "This list is who staff pick up from school for the drop-off program — not the regular after-school attendance roster.",
        "steps": [
            {
                "title": "Pick the date",
                "body": "Change the date to see that day’s pickup run.",
            },
            {
                "title": "See who to pick up",
                "body": "Paid requests are confirmed. Unpaid requests still need the parent to finish payment. You can mark paid if they pay at the desk.",
            },
            {
                "title": "Open the family if you need details",
                "body": "Use the family link for pickup people, phone numbers, or medical notes.",
            },
            {
                "title": "Drop-off members",
                "body": "The members list is children on the drop-off program. Their parents see a Drop-off tab even on days they did not book.",
            },
        ],
    },
    "applications": {
        "title": "How to review applications",
        "intro": "This queue is applications that still need a decision. Waitlist is a separate page.",
        "steps": [
            {
                "title": "Search and open Review",
                "body": "Find the child, then open Review to read the full application, medical notes, and program choice.",
            },
            {
                "title": "Create an application for a walk-in",
                "body": "Use + Create application when a family enrolls by phone, paper, or at the desk. The parent still finishes policies in their portal.",
            },
            {
                "title": "Know what you can approve",
                "body": "Some staff can only view or request changes. If Approve is missing, an admin (or a portal admin using Staff portal) needs to finish the decision.",
            },
        ],
    },
    "waitlist": {
        "title": "How to use the waitlist",
        "intro": "Children here are waiting for a before-care or other waitlisted spot, in request order. You can also add After-care onto an existing waitlisted before-care record.",
        "steps": [
            {
                "title": "Find the waitlisted child",
                "body": "Search or scan the list for the child who applied for before-care only. The # column is waitlist order. Open Review if you need to confirm the child and program.",
            },
            {
                "title": "Add After-care",
                "body": "If they also need after-school, use + After-care on that row. We reuse the existing waitlist application — the parent does not fill out a new enrollment form.",
            },
            {
                "title": "Save",
                "body": "Confirm to save. After-care is added onto this child's record and goes to the after-school review queue. Their before-care waitlist spot stays as it is.",
            },
            {
                "title": "Approve when a before-care spot opens",
                "body": "Approve adds them to the roster. You do not need a new application.",
            },
        ],
    },
    "create-application": {
        "title": "How to create an application",
        "intro": "Use this when you enroll a family for them (walk-in, phone, or paper).",
        "steps": [
            {
                "title": "Fill household and child fields",
                "body": "Name, contact, and child details are required. Choose the program location that matches this unit.",
            },
            {
                "title": "Mark returning vs new",
                "body": "Returning members may not owe a new membership fee. New members usually do.",
            },
            {
                "title": "After you save",
                "body": "The parent gets an email to finish policies and medical information in the parent portal.",
            },
        ],
    },
    "application-detail": {
        "title": "How to decide on an application",
        "intro": "This is one child’s full application. Take the action at the bottom after you have read it.",
        "steps": [
            {
                "title": "Read medical and location first",
                "body": "Confirm the unit/location is correct. If it is wrong, change the application location so the family lands at the right site.",
            },
            {
                "title": "Approve, waitlist, request changes, or reject",
                "body": "Approve puts them on the roster (and may add the membership fee). Waitlist holds a spot in order. Request changes sends a note the parent can see. Reject needs a clear reason.",
            },
            {
                "title": "Print if you need a paper copy",
                "body": "Use the PDF for files, 4Cs packets, or the family. Previous / Next moves you through the queue.",
            },
            {
                "title": "Add After-care without a new application",
                "body": "If this child is waitlisted for before-care only and now also needs after-school, use + After-care. Confirm to save. The existing record is reused — before-care waitlist stays the same, and After-care goes to the after-school queue.",
            },
        ],
    },
    "families": {
        "title": "How to use the families list",
        "intro": "Every child at this unit is a row. Family balance sits on the first child in the household.",
        "steps": [
            {
                "title": "Search or filter",
                "body": "Search by name. Filters help you find balances, billing type, or status.",
            },
            {
                "title": "Save school attending",
                "body": "If the school box is empty, choose the school and save. Bus and pickup reports use this.",
            },
            {
                "title": "Open the account",
                "body": "Account (or Profile) opens pickup, billing, plans, and medical. Parent view is what the family sees.",
            },
        ],
    },
    "member-policies": {
        "title": "How to check member policies",
        "intro": "This is signature status for every family at the unit.",
        "steps": [
            {
                "title": "Read complete vs incomplete",
                "body": "Each child needs the full set of policies signed. Before-care waitlist uses the same signatures as the rest of the family.",
            },
            {
                "title": "Print",
                "body": "Print all members for a binder, or open one family to print just theirs.",
            },
        ],
    },
    "agency": {
        "title": "How to use 4Cs / Agency",
        "intro": "A 4Cs family has two money tracks: regular billing (copays and membership) and the agency remittance account.",
        "steps": [
            {
                "title": "Add a 4Cs child",
                "body": "Use + Add 4Cs child with the authorization number, parent copay, and agency rate.",
            },
            {
                "title": "Record a parent copay",
                "body": "Copays post to the family’s regular billing account — not the agency ledger.",
            },
            {
                "title": "Record agency remittance",
                "body": "When the 4Cs check arrives, record remittance so it can apply across the children on that check.",
            },
            {
                "title": "Finish waiting children",
                "body": "If a child is approved but waiting for 4Cs information, open that row and complete the missing fields.",
            },
        ],
    },
    "agency-billing": {
        "title": "How to read a 4Cs agency account",
        "intro": "This ledger is agency remittance for one child. Parent copays and membership live on regular billing.",
        "steps": [
            {
                "title": "Check the weekly rate and balance",
                "body": "This page is what the agency owes, not what the parent owes.",
            },
            {
                "title": "Switch to regular billing for copays",
                "body": "Use Regular billing on the family when you need membership, copays, or parent payments.",
            },
        ],
    },
    "messages": {
        "title": "How to use team messages",
        "intro": "This is staff-to-admin messaging inside the portal. It is not text messaging to parents.",
        "steps": [
            {
                "title": "Start a message",
                "body": "Use + New message. Pick a category and priority. Urgent messages email admins when email is set up.",
            },
            {
                "title": "Reply in the thread",
                "body": "Open a thread on the left, then reply on the right. Unread counts show what still needs a look.",
            },
        ],
    },
    "incidents": {
        "title": "How to log an incident",
        "intro": "Log injuries, behavior notes, and medication events during or right after they happen.",
        "steps": [
            {
                "title": "Start a log",
                "body": "Use + Log incident. Choose the child, type, and severity, then write what happened and any follow-up.",
            },
            {
                "title": "Note if the parent was told",
                "body": "Track that you notified the parent so the next staff person can see it.",
            },
            {
                "title": "Print",
                "body": "Print the full log, one child, or a single incident for the file.",
            },
        ],
    },
    "support": {
        "title": "How to get portal support",
        "intro": "Support tickets go to YEA admin for portal or billing problems. Team messages are for day-to-day site communication.",
        "steps": [
            {
                "title": "Open a ticket",
                "body": "Use + New ticket. Describe what you were doing and what went wrong.",
            },
            {
                "title": "Attach a screenshot",
                "body": "A picture of the screen (PNG, JPG, or HEIC) helps us fix it faster.",
            },
            {
                "title": "Read the reply here",
                "body": "Answers show in the same thread. You do not need to email separately.",
            },
        ],
    },
    "reports": {
        "title": "How to print reports",
        "intro": "Use these PDFs and CSVs for the clipboard, the bus, medical binders, and office files.",
        "steps": [
            {
                "title": "Pick the right sheet",
                "body": "Live Attendance is for checking children in on screen. Blank daily/weekly sheets are for paper if the system is down. Medical report is allergies and action plans. School bus is grouped by school.",
            },
            {
                "title": "Set filters, then print",
                "body": "Choose date, program, or school first. Then use the browser Print / Save PDF button.",
            },
            {
                "title": "Exports",
                "body": "Outstanding balances and 4Cs copay files download as CSV for spreadsheets.",
            },
        ],
    },
    "family-profile": {
        "title": "How to use a family profile",
        "intro": "This is the household: adults, children, medical cards, and emergency contacts.",
        "steps": [
            {
                "title": "Move between tabs",
                "body": "Pickup, Incidents, Billing, Plans, 4Cs, Applications, Policies, and Email parent are along the top of the account.",
            },
            {
                "title": "Read medical cards",
                "body": "Allergies and action plans are on this page. Hover icons in lists for a short reminder.",
            },
            {
                "title": "Correct parent info",
                "body": "Use Edit member info on this page to change the parent email, phone, names, or address after approval. Saving also updates the parent login email so they can sign in and get password resets.",
            },
            {
                "title": "Email the parent",
                "body": "Use Email parent here or on the Email tab. Previous / Next moves you to the next family in your list.",
            },
        ],
    },
    "family-pickup": {
        "title": "How to check authorized pickup",
        "intro": "Only the people on this list may take the child, unless a director has approved an exception.",
        "steps": [
            {
                "title": "Match the name and ID",
                "body": "Ask for photo ID and match it to the authorized person and relationship on this page.",
            },
            {
                "title": "If nobody is listed",
                "body": "Do not release the child until you have a person on file. Ask a director or the parent to update the account.",
            },
        ],
    },
    "family-incidents": {
        "title": "How to see this family’s incidents",
        "intro": "These are logged events for children in this household.",
        "steps": [
            {
                "title": "Log a new incident",
                "body": "Use + Log incident to open the full incident form.",
            },
            {
                "title": "Print one child or one event",
                "body": "Use the print links when you need a copy for the file or the parent.",
            },
        ],
    },
    "family-billing": {
        "title": "How to use family billing",
        "intro": "This ledger is what the family owes. Portal admins working in Staff portal can post the same charges they can in admin.",
        "steps": [
            {
                "title": "Read the balance",
                "body": "The banner is the family total. The table is every charge, payment, credit, and discount.",
            },
            {
                "title": "Add a charge or record a payment",
                "body": "+ Add charge for membership, tuition, late fee, field trip, or other. Record payment for cash, check, or a card you enter for them.",
            },
            {
                "title": "Credits and deletes",
                "body": "Adding credit or deleting a charge may require permission. If a button is missing, an organization admin can turn that on under Billing permissions.",
            },
        ],
    },
    "family-plans": {
        "title": "How to read billing plans",
        "intro": "Each child has a plan (private pay, 4Cs copay, scholarship, and so on) and whether it auto-charges.",
        "steps": [
            {
                "title": "Read, don’t guess",
                "body": "Staff can view the plan, amount, and schedule here. Changing the plan itself is an admin task.",
            },
            {
                "title": "4Cs vs private pay",
                "body": "A 4Cs copay still belongs on this family’s regular billing. Agency remittance is on the 4Cs tab.",
            },
        ],
    },
    "family-agency": {
        "title": "How to use the family 4Cs tab",
        "intro": "This is the agency side of a 4Cs household.",
        "steps": [
            {
                "title": "Open the agency account",
                "body": "Use 4Cs account for remittance history on a child.",
            },
            {
                "title": "If the tab is empty",
                "body": "Add the child on the unit 4Cs / Agency page first.",
            },
        ],
    },
    "family-applications": {
        "title": "How to see this family’s applications",
        "intro": "Every linked application for the household stays here, even after it is approved.",
        "steps": [
            {
                "title": "Switch children if needed",
                "body": "A family can have more than one child. Open the application you need, then print the PDF if you want a paper copy.",
            },
            {
                "title": "Add After-care for a waitlisted before-care child",
                "body": "Find the waitlisted before-care child, then use + After-care and confirm to save. No new enrollment application is required. After-care is added onto this record; before-care waitlist stays the same.",
            },
        ],
    },
    "family-policies": {
        "title": "How to check this family’s policies",
        "intro": "Signed policies are required before enrollment is complete.",
        "steps": [
            {
                "title": "See what is still unsigned",
                "body": "Incomplete items are listed per child. The parent finishes them in the parent portal.",
            },
            {
                "title": "Print the packet",
                "body": "Use Print / Save PDF for files or an audit.",
            },
        ],
    },
    "family-email": {
        "title": "How to email a parent",
        "intro": "This sends to the primary parent email on the account.",
        "steps": [
            {
                "title": "Write and send",
                "body": "The address is filled from the profile. Keep the subject clear. Cancel if you are not ready to send.",
            },
        ],
    },
    "parent-applications": {
        "title": "How to add After-care",
        "intro": "If your child is on the before-care waitlist and you also need after-school, add it here. You do not start a new application.",
        "steps": [
            {
                "title": "Find your child",
                "body": "This list is each child on your account. A before-care-only waitlist child shows Before care and Waitlist.",
            },
            {
                "title": "Click + After-care",
                "body": "On that child's row, use + After-care. If you do not see that button, After-care is already on file.",
            },
            {
                "title": "Confirm",
                "body": "Pick the after-school site if asked, then confirm. We reuse the family, medical, contacts, and signed policies already on file.",
            },
            {
                "title": "What happens next",
                "body": "After-care goes to staff for review. Your before-care waitlist spot does not change. This page will show After-school with a before-care waitlist note.",
            },
        ],
    },
    "parent-application": {
        "title": "How to add After-care from this application",
        "intro": "This is one child's application. If they are waitlisted for before-care only, you can add After-care here without starting over.",
        "steps": [
            {
                "title": "Use + After-care",
                "body": "The button is at the top with Download PDF. Click it if you also need after-school.",
            },
            {
                "title": "Confirm",
                "body": "Pick the site if asked, then confirm. Medical information and signed policies stay on file. Before-care waitlist does not change.",
            },
        ],
    },
}


def guide_for(key):
    if not key:
        return None
    guide = GUIDES.get(str(key))
    if not guide:
        return None
    steps = list(guide.get("steps") or [])
    if not steps:
        return None
    return {
        "key": key,
        "title": guide["title"],
        "intro": guide.get("intro") or "",
        "steps": steps,
        "step_count": len(steps),
    }


def page_guide_from_context(context):
    key = context.get("page_guide_key")
    if not key:
        if context.get("portal_area") == "parent":
            slug = context.get("parent_page_slug")
            if slug == "applications":
                key = "parent-applications"
            elif slug == "application":
                key = "parent-application"
            else:
                return None
        else:
            family_tab = context.get("family_tab")
            if family_tab:
                key = f"family-{family_tab}"
            else:
                slug = context.get("staff_page_slug") or context.get("admin_page_slug")
                if context.get("portal_area") == "admin" and slug == "dashboard":
                    key = "admin-dashboard"
                else:
                    key = slug
    return guide_for(key)
