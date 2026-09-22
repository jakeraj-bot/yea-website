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
                "body": "If a Needs attention list appears, tap a line to go straight to that family, application, or message. Overdue balances on this page count active children only. Inactive children who still owe are on the Inactive children report, not this card.",
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
            {
                "title": "Enrollment and overdue hide inactive children",
                "body": "Children enrolled and overdue balances count active children only. When a child is inactive they leave those numbers. Review them on All families → Inactive, or Reports → Inactive children, including any remaining balance.",
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
    "admin-attendance": {
        "title": "How to review attendance",
        "intro": "This is the live check-in roster for the organization. Pick a unit — or all units — then mark children present or absent the same way staff does.",
        "steps": [
            {
                "title": "Pick a unit",
                "body": "Use Unit at the top. All units shows every site on one list. Choose one unit to work that site only.",
            },
            {
                "title": "Confirm the date",
                "body": "Change the date if you are looking at another day. The Monday–Friday sheet with kid totals is under Organization reports.",
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
                "title": "Review all from oldest first",
                "body": "Use Review all at the top to start with the application that came in first and still needs a decision. Previous and Next move through that same oldest-first queue. Already approved children are not in this list.",
            },
            {
                "title": "Search and open Review",
                "body": "The list is sorted by received time, oldest first. Find the child, then open Review to read the full application, medical notes, and program choice.",
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
                "body": "Open Review (or use Approve on this list) and type the member start date — each child can start on a different day, and that date goes in the approval email. Attach a billing plan before you approve if you want the email to show tuition or parent copay. Skip the plan for 4Cs so the email states the membership fee and reminds the parent to send their contract to jakeraj@yeanj.org. Approve removes them from this waitlist and adds them to All families Active. If the child already has a family account, we use that account — no duplicate family or second membership. The parent gets an email that payment is due before the program start, with payment steps and a Pay now link.",
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
                "body": "Enter the member start date first — it is required and goes into the approval email. Attach a billing plan before you approve if you want that email to show the amount due (membership plus first tuition or parent copay). Skip the plan for 4Cs so the email states the membership fee and reminds the parent to send their contract to jakeraj@yeanj.org. Approve puts them on All families Active and emails the parent that they can start on that date, that payment is due before the program start, with Pay now steps and a payment-page link. Waitlist holds a before-care spot in order — they stay off Active until you approve. If the child already has an account, we add before care as Approved on that account (no second family). Request changes sends a note the parent can see. Reject needs a clear reason.",
            },
            {
                "title": "Change the membership amount before you approve",
                "body": "The membership charge defaults to the current membership fee. You can change the amount (and description) before you confirm. Type 0 to waive. That edited amount is what posts to the family ledger. A second waitlist or after-care application for the same child does not charge membership again.",
            },
            {
                "title": "Attach a billing plan before you approve",
                "body": "Use the billing plan picker on Approve details — the same weekly, bi-weekly, and monthly private-pay or 4Cs copay types as family Plans. Fill the parent amount so the approval email can show amount due. Amount due is what the parent owes, not the 4Cs agency week amount. Leave the plan off for 4Cs until copay is set: the email then states the membership fee and the contract reminder (send to jakeraj@yeanj.org, YEA signs it and emails it back for 4Cs). You can still add or change the plan later on the family Plans tab.",
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
        "intro": "Every child at this unit is a row, A–Z by child name. Family balance sits on the first child in the household. Inactive children have their own tab.",
        "steps": [
            {
                "title": "Search or filter",
                "body": "Search by family name, child name, or parent phone. (201) 456-5698 and 2014565698 both work. Filters help you find balances, billing type, or status.",
            },
            {
                "title": "Inactive tab",
                "body": "When a child stops attending, make them inactive on the family account. They move from Active to Inactive — the same child, not a copy. You will not see that child on both tabs. The family account, ledger, and parent login stay. If a household has one attending child and one inactive sibling, Active shows only the attending child and Inactive shows only the sibling who left.",
            },
            {
                "title": "Make them active again",
                "body": "Open the Inactive tab and use Make active, or open the family account and use Make active there. They return to this list and to attendance.",
            },
            {
                "title": "Parents can still pay and get tax forms",
                "body": "Inactive does not delete anything. Parents can still see the balance, use Pay now if they owe, download receipts, and get tax statements.",
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
        "intro": "A 4Cs family has two money tracks: parent copay on regular billing, and what the agency pays YEA on this 4Cs tab.",
        "steps": [
            {
                "title": "Add an agency",
                "body": "Use Add agency. Enter the agency name, the child, and the contract start and end dates.",
            },
            {
                "title": "Set daily and weekly rates",
                "body": "There are two sections: what the agency pays YEA, and what the parent pays (copay). Weekly starts as daily × 5 school days. You can override weekly, then any week.",
            },
            {
                "title": "Adjust weeks if needed",
                "body": "Every school week in the contract is listed. Change a week to a different amount or $0 when that week is different.",
            },
            {
                "title": "Parent plan uses copay weeks",
                "body": "On Plans, pick weekly, bi-weekly, or monthly. The plan adds up parent copay weeks only — never the agency amounts.",
            },
            {
                "title": "Agency ledger is separate",
                "body": "Agency expected amounts stay on the 4Cs tab. Check Received when the agency check for that week comes in. That does not post to the parent ledger.",
            },
            {
                "title": "Record a parent copay date",
                "body": "When you record a parent copay, Payment date is the day the money was received. It defaults to today.",
            },
        ],
    },
    "agencies": {
        "title": "How to use Agencies (4Cs)",
        "intro": "A 4Cs family has two money tracks: parent copay on regular billing, and what the agency pays YEA on the 4Cs tab.",
        "steps": [
            {
                "title": "Add an agency",
                "body": "Use Add agency. Enter the agency name, the child, and the contract start and end dates. From the waiting list, Add agency opens with that child already filled in.",
            },
            {
                "title": "Set daily and weekly rates",
                "body": "There are two sections: what the agency pays YEA, and what the parent pays (copay). Weekly starts as daily × 5 school days. You can override weekly, then any week.",
            },
            {
                "title": "Adjust weeks if needed",
                "body": "Every school week in the contract is listed. Change a week to a different amount or $0 when that week is different.",
            },
            {
                "title": "Parent plan uses copay weeks",
                "body": "On Plans, pick weekly, bi-weekly, or monthly. The plan adds up parent copay weeks only — never the agency amounts.",
            },
            {
                "title": "Agency ledger is separate",
                "body": "Agency expected amounts stay on the 4Cs tab. Check Received when the agency check for that week comes in. That does not post to the parent ledger.",
            },
            {
                "title": "Record a parent copay date",
                "body": "When you record a parent copay, Payment date is the day the money was received. It defaults to today.",
            },
        ],
    },
    "agency-billing": {
        "title": "How to read a 4Cs agency account",
        "intro": "This ledger is what the agency owes YEA for one child. Parent copays live on regular billing.",
        "steps": [
            {
                "title": "Read the expected weeks",
                "body": "Each school week shows the agency amount. This is not the parent copay.",
            },
            {
                "title": "Check Received when the check comes in",
                "body": "Mark Received for that week. It records the agency payment here only.",
            },
            {
                "title": "Switch to regular billing for copays",
                "body": "Use Regular billing when you need membership, parent copays, or parent payments.",
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
                "body": "Live Attendance is for checking children in on screen. Blank daily/weekly sheets are for paper if the system is down. Weekly attendance is the Mon–Fri sheet — check After-care, Before-care, or All, then one or more grades to keep those kids on the same page. Before care is the roster of who is approved for before-care. Medical report is allergies and action plans. School bus is grouped by school. Member information is the enrollment roster — school, grade, program, billing, and 4Cs. Emergency contact list is who to call, with an authorized-pickup column.",
            },
            {
                "title": "Set filters, then print",
                "body": "Choose date, program, school, billing type, 4Cs, family, or missing contacts first. Then use the browser Print / Save PDF button.",
            },
            {
                "title": "Exports",
                "body": "If you can see billing, balance files download as CSV and 4Cs expected amounts shows copay and agency totals by child. Program director does not see those unless billing is turned on. Who still owes — by week lists unpaid weeks and lets you charge a $15 late fee only on the children you check. Inactive children is who left the program and any remaining balance — they stay off other reports unless Status is Inactive or All.",
            },
        ],
    },
    "inactive-children": {
        "title": "How to review inactive children",
        "intro": "This list is children marked inactive. Accounts stay on file. Remaining balance is that child's live tuition (charges minus payments; Stripe card fees do not count as still owed).",
        "steps": [
            {
                "title": "Read who left and what they still owe",
                "body": "Each row is an inactive child who moved off Active — not a second copy of the account. Child names open the family profile. Remaining balance is that child's tuition after payments. Parents can still Pay now and download tax statements.",
            },
            {
                "title": "Filter the list",
                "body": "Search by child or family. Still owes Yes keeps only children with a remaining balance. Unit is for admin across sites. Apply, then print or download CSV.",
            },
            {
                "title": "Make them active again",
                "body": "Open the child name, then use Make active on Program status at the top of the profile. They return to All families, attendance, and Overview counts.",
            },
        ],
    },
    "outstanding-balances": {
        "title": "How to use outstanding balances",
        "intro": "This list is one row per child who still owes after payments. Child names open the family billing account. Status is a filter, not a column.",
        "steps": [
            {
                "title": "Read child names and amounts",
                "body": "Each row is a child with that child's remaining amount after payments, not the household last name. Parent card, check, or money order payments drop this number by the tuition applied — Stripe's processing fee is not still owed. Siblings who both owe appear as two rows. Children at $0 stay off the list.",
            },
            {
                "title": "Filter by status",
                "body": "The report starts on Active children who owe. Use Status to switch to waitlist, inactive, withdrawn, suspended, or all statuses. Inactive children who still owe stay on this report when you choose Inactive or All. Apply filters, then print or download CSV.",
            },
        ],
    },
    "four-cs-payout": {
        "title": "How to use 4Cs expected amounts",
        "intro": "This is a forecast from 4Cs plans — what you should collect in copay, and what 4Cs will pay — not a dump of the ledger.",
        "steps": [
            {
                "title": "Read the two money tracks",
                "body": "Copay I should collect is the parent’s family-pays amount after scholarship. What 4Cs / agency will pay is the weekly agency rate and is never reduced by scholarship. Scholarship comes off parent copay only.",
            },
            {
                "title": "Weekly, bi-weekly, and monthly copay totals",
                "body": "Those cards group children by the child’s copay payment plan. Weekly-plan totals are one week of family-pays. Bi-weekly-plan totals are two weeks. Monthly-plan totals use the program weeks in this month (4 or 5). Each child also has a row with that same cadence amount.",
            },
            {
                "title": "Weekly copay for all 4Cs members",
                "body": "That column and card put everyone on a weekly copay, no matter their plan. It uses the plan’s weekly copay (daily × 5 school days, or the weekly override). If only a cycle amount exists, bi-weekly is divided by 2. Monthly uses the weekly rate (or this month’s week count). After-scholarship family-pays is the number you should collect.",
            },
            {
                "title": "What 4Cs will pay",
                "body": "4Cs still pays weekly. The weekly 4Cs card is the sum of weekly agency rates. Bi-weekly and monthly 4Cs cards are two and four weeks of that weekly agency rate, grouped with the child’s copay plan so you can compare. Scholarship does not change agency amounts.",
            },
            {
                "title": "Filter, then print",
                "body": "The list starts on Active 4Cs children. Filter by unit, status, school, grade, program, copay plan, 4Cs cadence, scholarship, agency, or name. Totals follow the filtered rows. Child names open family billing. Print / Save PDF repeats the logo and title on every page.",
            },
        ],
    },
    "owed-weeks": {
        "title": "Who still owes — by week",
        "intro": "See families and children with a balance, which weeks those charges cover, and pick who gets a late fee.",
        "steps": [
            {
                "title": "Read the weeks",
                "body": "Weeks come from the charge description (plan notes, 4Cs week dates, or the school week of the charge date). Amounts are remaining after payments, including family-level payments with no child on the row. Children at $0 stay off the list.",
            },
            {
                "title": "Charge a late fee only if you pick them",
                "body": "Check the children who should get today’s Late fee, then charge selected. Nobody is charged until you choose them.",
            },
        ],
    },
    "weekly-attendance": {
        "title": "How to print weekly attendance",
        "intro": "This is the Monday–Friday attendance sheet. Pick a unit, then After-care, Before-care, or All. Check one or more grades to print those children together — they stay on the same sheet, not split into grade tables.",
        "steps": [
            {
                "title": "Pick a unit",
                "body": "Use the Unit filter on this page. Staff can choose any unit they are allowed to open; it starts on the unit in the header, so you do not have to hunt through the header switcher. Staff cannot see children at a unit they are not assigned to. Admins can choose one unit or All units. A child whose family account is at another site still appears if they attend the unit you picked.",
            },
            {
                "title": "Choose After-care, Before-care, or All",
                "body": "All is the starting list so you do not miss anyone. After-care keeps after-school kids and hides children who only have approved before-care. Before-care keeps approved before-care kids and hides after-school-only children. A child on both programs stays on After-care and Before-care unless that application is inactive. An inactive before-care application stays off Before-care; an inactive after-care application stays off After-care. The printed names follow this filter.",
            },
            {
                "title": "Optionally add parent contact",
                "body": "Check Show primary parent contact on this sheet if you need the parent name, phone, and email under each child. It stays off unless you check it, then Apply filters. The choice stays in the URL so print and reload keep it.",
            },
            {
                "title": "Pick the week and grades",
                "body": "Choose a date in that school week. Leave grades unchecked to include every grade at that unit. Check 2nd and 4th, for example, to print both grades on one weekly grid. Unit and grades work together on this same Monday–Friday sheet.",
            },
            {
                "title": "Read the daily kid totals",
                "body": "The number above Monday is how many children on this filtered sheet were present that day. Tuesday through Friday each have their own count. The numbers follow Unit, grades, and the other filters.",
            },
            {
                "title": "Read the grid like the blank sheet",
                "body": "Grade sits under the child’s name. Unit is in the page header, not a column. A check means present; if they were not there, the cell is a blank line so you can write on a printout.",
            },
            {
                "title": "Narrow further if you need to",
                "body": "Use program, school, present/absent status, and child or family search. Apply filters, then print only what is on the page.",
            },
            {
                "title": "Preview, then print or download",
                "body": "Use Print / Save PDF for paper, or Download CSV for a spreadsheet. The header, kid totals, page number, and print date/time repeat on every printed page. Filters stay off the printed page.",
            },
        ],
    },
    "weekly-attendance-blank": {
        "title": "How to print a blank weekly sheet",
        "intro": "This is the Monday–Friday grid with names filled in and empty lines to mark by hand. Filters match the filled weekly sheet, including After-care, Before-care, or All.",
        "steps": [
            {
                "title": "Pick a unit",
                "body": "Staff start on the header unit and can choose another site they are allowed to open. Admins can choose one unit or All units.",
            },
            {
                "title": "Choose After-care, Before-care, or All",
                "body": "All starts with every enrolled child. After-care hides before-care-only kids. Before-care hides after-school-only kids. The printed names follow this filter.",
            },
            {
                "title": "Pick the week and grades",
                "body": "Choose a date in that school week. Check one or more grades to keep those kids on the same grid. Leave grades unchecked for every grade at that unit.",
            },
            {
                "title": "Read the listed counts",
                "body": "The number above Monday is how many children are listed on this filtered sheet. Tuesday through Friday show the same listed count. Extra blank rows at the bottom are for walk-ins.",
            },
            {
                "title": "Print",
                "body": "Use Print / Save PDF. The header, listed counts, page number, and print date/time appear on every printed page.",
            },
        ],
    },
    "daily-attendance": {
        "title": "How to print daily attendance",
        "intro": "This is the sign-in sheet for one day, with check-in and check-out times filled in when they exist.",
        "steps": [
            {
                "title": "Pick a unit",
                "body": "Staff start on the header unit and can choose another site they are allowed to open. Admins can choose one unit or All units. You will not see children from a unit you cannot open.",
            },
            {
                "title": "Choose After-care, Before-care, or All",
                "body": "All is the starting list. After-care keeps after-school kids. Before-care keeps approved before-care kids. The printed names follow this filter.",
            },
            {
                "title": "Pick the day and grades",
                "body": "Change the date if you need another day. Check grades to keep those kids on one sheet.",
            },
            {
                "title": "Read the day’s kid total",
                "body": "The number above the weekday is how many children on this filtered sheet were present that day. Grade sits under the child’s name. Empty check-in or check-out cells are blank lines, not dashes.",
            },
            {
                "title": "Print",
                "body": "Use Print / Save PDF. The header, day’s total, page number, and print date/time appear on every printed page.",
            },
        ],
    },
    "daily-attendance-blank": {
        "title": "How to print a blank daily sheet",
        "intro": "This is a paper sign-in sheet with enrolled names and empty lines for times and signatures.",
        "steps": [
            {
                "title": "Pick a unit",
                "body": "Staff start on the header unit and can choose another site they are allowed to open. Admins can choose one unit or All units.",
            },
            {
                "title": "Choose After-care, Before-care, or All",
                "body": "Same as the filled daily sheet. All prints both programs. After-care and Before-care change the printed names.",
            },
            {
                "title": "Pick the day and grades",
                "body": "Set the date, then check grades if you only need some classrooms. Names match the filled daily sheet for those filters.",
            },
            {
                "title": "Read the listed count",
                "body": "The number above the weekday is how many children are listed on this filtered sheet. Extra blank rows at the bottom are for walk-ins.",
            },
            {
                "title": "Print",
                "body": "Use Print / Save PDF. The header, listed count, page number, and print date/time appear on every printed page.",
            },
        ],
    },
    "signout-blank": {
        "title": "How to print a sign-out sheet",
        "intro": "This is the paper pickup sheet. Choose After-care, Before-care, or All, then print the names that match.",
        "steps": [
            {
                "title": "Choose After-care, Before-care, or All",
                "body": "All starts with every enrolled child at your unit so you do not miss anyone. After-care hides children who only have approved before-care. Before-care hides after-school-only children. A child on both programs stays on both lists. The printed names follow this filter.",
            },
            {
                "title": "Set the date and print",
                "body": "Change the date if you need another day. Use Print / Save PDF. Parents sign and write the pickup time. Only release children to adults on the authorized pickup list.",
            },
        ],
    },
    "before-care": {
        "title": "How to see before-care kids",
        "intro": "This roster is who is approved for before-care. Waitlist-only children stay off until you approve them. Inactive children stay off. A child whose before-care application is inactive also stays off, even if they still attend after-care.",
        "steps": [
            {
                "title": "Read the list",
                "body": "Each row is a child with approved or enrolled before-care. You see the child name, family, unit, school, and status. Staff see their unit only. Admins can choose one unit or All units.",
            },
            {
                "title": "Open the family account",
                "body": "Click a child name to open that family account. The printed page shows the name without the link.",
            },
            {
                "title": "Print a before-care attendance sheet",
                "body": "Need a weekly or sign-out sheet for only these kids? Open Weekly attendance or Sign-out sheet and choose Before-care. All prints after-school and before-care together.",
            },
        ],
    },
    "member-information": {
        "title": "How to print member information",
        "intro": "This is one roster of every enrolled child you are allowed to see. Filter the columns, then print only what you need.",
        "steps": [
            {
                "title": "Check whose children you see",
                "body": "Staff see only children at the unit in the header. School 18 staff will not see School 26 children. Admins can choose one unit or all units.",
            },
            {
                "title": "Filter until only the needed rows remain",
                "body": "Use school, grade, unit, program type (After-Care, Before-Care, Drop-in), billing type, payment plan, 4Cs member, and whether a 4Cs agency is on file. Search by child or family name.",
            },
            {
                "title": "Read 4Cs columns",
                "body": "Daily amount and copay come from the live 4Cs agency record and this week's contract. If the family is 4Cs but no agency is created yet, those cells say waiting.",
            },
            {
                "title": "Preview, then print or download",
                "body": "The table updates when you apply filters. Use Print / Save PDF for paper, or Download CSV for a spreadsheet. Filters stay off the printed page.",
            },
        ],
    },
    "emergency-contacts": {
        "title": "How to print emergency contacts",
        "intro": "This list is who to call for each child at this unit. Narrow the rows, then print only what you need.",
        "steps": [
            {
                "title": "Check the unit",
                "body": "Staff see only children at the unit in the header. School 18 staff will not see School 26 children. Admins can choose one unit or all units.",
            },
            {
                "title": "Filter until only the needed rows remain",
                "body": "Use program, school attending, family, child, grade, contact search, and authorized pickup. Check Only missing contacts to see children with no emergency contact on file.",
            },
            {
                "title": "Preview, then print",
                "body": "The table updates when you apply filters. Use Print / Save PDF for a paper copy or a PDF. Filters stay off the printed page.",
            },
        ],
    },
    "family-profile": {
        "title": "How to use a family profile",
        "intro": "This is the household: adults, children, medical cards, and emergency contacts.",
        "steps": [
            {
                "title": "Move between tabs",
                "body": "Pickup, Attendance, Incidents, Billing, Plans, 4Cs, Applications, Policies, Email parent, and Notes are along the top of the account.",
            },
            {
                "title": "Find another child without leaving",
                "body": "Use Find a child or family next to Previous / Next. It uses the same name search as All families. Choosing a result opens that child’s account.",
            },
            {
                "title": "Read medical cards",
                "body": "Allergies and action plans are on this page. Hover icons in lists for a short reminder.",
            },
            {
                "title": "Fold profile sections",
                "body": "Use Expand all / Collapse all at the top of Profile, or the chevron on a card. Program status stays open so Make inactive stays in view. Edit member info starts folded.",
            },
            {
                "title": "Correct parent info",
                "body": "Use Edit member info on this page to change the parent email, phone, names, or address after approval. Saving also updates the parent login email so they can sign in and get password resets. Open that section with the chevron if it is folded.",
            },
            {
                "title": "Make a child inactive or active",
                "body": "Stay on the Profile tab. Program status is open at the top, under the tabs — do not use Parent view. Each child’s card also has Make inactive. Use it when a child stops attending. Confirm. They move from the Active tab to Inactive — this does not copy the account. Ledger, receipts, and parent login stay. They leave Overview balances, enrollment, attendance, and the Active families list. Use Make active if they come back. Parents can still pay a remaining balance and download tax statements. Profile cards fold with the chevron; Program status stays open.",
            },
            {
                "title": "Make one application inactive",
                "body": "If a child has before-care and after-care, you can turn off one program without making the whole child inactive. On Program status, each application has Make this before-care application inactive or Make this after-care application inactive. That child leaves attendance and the before-care roster for that program only. Restore this application if they come back to that program. You can also do this from the application page or the Applications tab.",
            },
            {
                "title": "Reset parent password",
                "body": "You cannot look up the current password. On this family account, scroll to Reset parent password and click Email create-password link. The parent gets a one-time link to create a new password (it expires in 72 hours), then they sign in on Parent login. If you need to tell them a password right now, open Set a temporary password instead — that password is shown once. If they forget again, send another link. Parents can also use Forgot password on the Parent login page themselves.",
            },
            {
                "title": "Email the parent",
                "body": "Use Email parent here or on the Email tab. Previous / Next moves you to the next family in your list.",
            },
            {
                "title": "Merge a duplicate account (admin)",
                "body": "If the same child or parent shows up twice, open the account you want to keep and use Merge a duplicate account. That moves children, payments, attendance, and applications onto one family login. Kids at two sites stay on this same household — staff still only see the children at their unit.",
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
    "family-attendance": {
        "title": "How to read this child’s attendance",
        "intro": "This month calendar is for one child on this family account. It shows saved present, absent, and not-marked days.",
        "steps": [
            {
                "title": "Switch children",
                "body": "If this account has two children, use the names under the Attendance tab to switch calendars. You stay on the family account. Inactive children with saved attendance stay on the list and are labeled Inactive.",
            },
            {
                "title": "Read the colors",
                "body": "Green is present. Red is absent. Gray is not marked. Days stay not marked unless staff already saved attendance.",
            },
            {
                "title": "Open a day",
                "body": "Click a date to see the same check-in, check-out, method, and note that Review attendance has when a record exists.",
            },
            {
                "title": "Change month",
                "body": "Use Previous month and Next month. Staff only see children at their unit.",
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
                "body": "+ Add charge for membership, tuition, late fee, field trip, or other. Record payment for cash, check, or money order. Take a card payment opens Stripe Checkout so the card is entered on Stripe, not in this portal.",
            },
            {
                "title": "Set the payment date",
                "body": "Payment date is the day the money was received — the check date, or the day cash or a money order came in. It defaults to today. You can change it. Card payments through Stripe keep the time Stripe charged the card.",
            },
            {
                "title": "Credits and deletes",
                "body": "Adding credit or deleting a charge may require permission. If a button is missing, an organization admin can turn that on under Billing permissions.",
            },
            {
                "title": "Edit a membership charge",
                "body": "Use Edit on a membership line to change the amount or the description. Deletes still ask for a reason.",
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
                "body": "A 4Cs copay still belongs on this family’s regular billing. The plan adds up parent copay weeks. Agency remittance is on the 4Cs tab.",
            },
            {
                "title": "Enter a weekly rate on monthly plans",
                "body": "On Monthly, type the weekly rate — not a flat monthly. A program week counts in the month of its Friday. Example: 9/28/2026–10/2/2026 is the first week of October, not September. Weeks with no program days (Settings → Program calendar days off) are not billed. The plan lists each month: for example September 2026, 4 weeks × $70 = $280; October, 5 × $70 = $350. The ledger posts that month’s amount on the first charge date you set, then on the same day each later month. Family-pays after scholarship is shown on each month.",
            },
            {
                "title": "Add a scholarship on a regular plan",
                "body": "On a private-pay Weekly, Bi-weekly, or Monthly plan, keep the plan amount (the full tuition before scholarship — weekly rate on a Monthly plan). Choose a scholarship type, enter the plan rate before the scholarship, and enter how much the family pays. The card still shows the plan amount plus scholarship and family-pays. The ledger posts the full rate and a scholarship discount, so the family owes the family-pays amount. On Monthly, family-pays is the weekly figure; each month’s table is weeks × that family-pays.",
            },
            {
                "title": "Add a scholarship on a 4Cs plan",
                "body": "On this child’s 4Cs copay plan, choose a scholarship type, enter the parent copay before the scholarship, and enter how much the family pays. The scholarship comes off the parent copay only. 4Cs agency week amounts stay the same.",
            },
            {
                "title": "When weekly 4Cs posts",
                "body": "Weekly parent copay posts every Thursday for the next school week. Check Post today (or set the first charge date to today) to put that charge on the family ledger immediately.",
            },
            {
                "title": "When bi-weekly starts",
                "body": "Parents bill from the program start in Settings → Program calendar (for example 9/8/2026–9/18/2026), even when the 4Cs contract starts 9/1. You can also check or uncheck weeks on this plan so only the weeks you pick get posted.",
            },
        ],
    },
    "family-agency": {
        "title": "How to use the family 4Cs tab",
        "intro": "This is the agency side of a 4Cs household — not parent copays.",
        "steps": [
            {
                "title": "Add or edit the agency",
                "body": "Use Add agency (or Edit agency) for the child. Set daily/weekly rates and adjust any week that is different.",
            },
            {
                "title": "Check Received when the check comes in",
                "body": "Each agency week has a Received box. Checking it records the agency payment here only.",
            },
            {
                "title": "Parent money is on Billing",
                "body": "Copay charges from the billing plan post to the family billing tab, not this one.",
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
            {
                "title": "After you approve before care",
                "body": "The waitlist row is gone. This Applications tab shows before care as Approved on the existing account. We do not create a second family.",
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
    "program-calendar": {
        "title": "How to use the program calendar",
        "intro": "This is when YEA is open for parents. It is not the 4Cs contract date.",
        "steps": [
            {
                "title": "Set the program start",
                "body": "Parents are billed from this date. Example: program starts 9/8/2026 — they are not charged for 9/1–9/4 even when 4Cs pays from 9/1.",
            },
            {
                "title": "Add days off and half days",
                "body": "Full closures skip parent weeks that have no remaining school days. Monthly plans use the same rule: a week with no program days is not billed. Half days are stored on this calendar and do not change the weekly copay amount.",
            },
            {
                "title": "4Cs still follows the contract",
                "body": "Each child’s agency form still uses the 4Cs authorization dates. Agency money stays on the 4Cs tab. Parent copay stays on family billing.",
            },
        ],
    },
    "staff": {
        "title": "How to create staff logins",
        "intro": "Only organization admins create portal logins. Program director and Front desk staff both sign in at the staff portal.",
        "steps": [
            {
                "title": "Create a Program director",
                "body": "Use Create staff account. Choose Program director. Pick a primary unit. They sign in at the staff portal. They see families, attendance, waitlist, applications, Activity calendar, Groups, and Outside programs. They can switch units because they are in charge of programming. Billing stays hidden unless you turn it on.",
            },
            {
                "title": "Create Front desk staff",
                "body": "Use Create staff account. Choose Front desk staff. Give them the unit they work at. They get full site operations: families, billing, take-payment, attendance, activities, groups, waitlist, and applications. They do not get Organization admin (units, staff accounts, or settings).",
            },
            {
                "title": "Turn Program director billing on",
                "body": "Open Billing permissions. Use Program Director can see billing for every Program director, or edit one person and check Program Director can see billing (this person).",
            },
        ],
    },
    "outside-programs": {
        "title": "How to use Outside programs",
        "intro": "This is the contact list for vendors and partners who run programs with YEA. Program directors and admins can add, edit, and delete.",
        "steps": [
            {
                "title": "Add a contact",
                "body": "Use + Add outside program. Enter name, email, phone, what they will be doing, and how much they want to charge YEA. Category and last-used date are optional.",
            },
            {
                "title": "Find someone",
                "body": "Search by name, email, phone, or notes. Filter by category.",
            },
            {
                "title": "Print or export",
                "body": "Print contact list makes a paper or PDF sheet. Export CSV is for a spreadsheet.",
            },
            {
                "title": "Delete",
                "body": "Delete asks for a reason. That reason is saved on the activity log.",
            },
        ],
    },
    "outside-programs-print": {
        "title": "How to print the contact list",
        "intro": "This is a printable list of outside program contacts.",
        "steps": [
            {
                "title": "Check the list",
                "body": "Name, email, phone, category, what they do, charge, and last used are on the sheet.",
            },
            {
                "title": "Print / Save PDF",
                "body": "Use the browser Print / Save PDF button.",
            },
        ],
    },
    "member-billing": {
        "title": "How to use member billing",
        "intro": "This list is families at your unit. Open Billing to post a charge or take a payment. Open Plans to change a child’s schedule.",
        "steps": [
            {
                "title": "Open a family",
                "body": "Use Billing for the ledger and take-payment. Use Plans for weekly amounts.",
            },
            {
                "title": "Who sees this",
                "body": "Front desk staff and other staff see this. Program director only sees it when billing is turned on for that role or person.",
            },
        ],
    },
    "activity-calendar": {
        "title": "How to use the activity calendar",
        "intro": "Schedule activities for your unit, then open a day to add who attended and upload that day’s lesson plan.",
        "steps": [
            {
                "title": "Create one day, a week, or a month",
                "body": "Enter the name, start time, end time, and a date. This day only creates one activity. This week or This month lets you check which weekdays to create — for example Monday and Wednesday only. Leave every box checked for all Monday–Friday days.",
            },
            {
                "title": "Upload a lesson plan per day",
                "body": "For a single day you can attach a PDF, Word file, or image when you create it. For a week or month, open each day on the calendar and upload that day’s lesson plan there.",
            },
            {
                "title": "Add the children who attended",
                "body": "Click an activity. The left list is kids you can add. The right list is members already in the activity. Use Add or Add all shown.",
            },
            {
                "title": "Filter the kids to add",
                "body": "Filter the left list by school attending, grade, child name, and by group (bus run, room, and other groups from the Groups page). Admins and Program directors can also filter by unit. Other staff only see children and activities at their unit.",
            },
        ],
    },
    "activity-calendar-detail": {
        "title": "How to add kids to an activity",
        "intro": "This is one scheduled day. Add who attended, and upload this day’s lesson plan.",
        "steps": [
            {
                "title": "Upload this day’s lesson plan",
                "body": "Use the upload box for a PDF, Word file, or image. Each day in a week or month series has its own file.",
            },
            {
                "title": "Filter, then add",
                "body": "The left list is kids to add. Filter by school attending, grade, name, unit (admin), or a group. Add one child or Add all shown. The right list is already in this activity — Remove takes them off.",
            },
            {
                "title": "Who you can see",
                "body": "Staff only see children at their unit. Admins and Program directors see every unit and can narrow with the unit filter.",
            },
        ],
    },
    "groups": {
        "title": "How to use groups",
        "intro": "Groups are standing lists such as a bus run. They do not have dates. Use them to pick the same kids again on the activity calendar.",
        "steps": [
            {
                "title": "Create a group",
                "body": "Enter a name (for example Bus run). Staff groups stay at their unit. Admins and Program directors pick a unit.",
            },
            {
                "title": "Add members",
                "body": "Click the group. The left list is kids you can add. The right list is already in the group. Filter by school attending, grade, or child name, and by unit if you are an admin.",
            },
            {
                "title": "Print",
                "body": "From a group you can print daily attendance, weekly attendance (Monday–Friday), a member list, contact list, or emergency contacts. The logo and title repeat on printed pages the same way other reports do.",
            },
            {
                "title": "Use a group on the activity calendar",
                "body": "When you add kids to an activity, choose that group in the Group filter so only those members show on the left.",
            },
        ],
    },
    "groups-detail": {
        "title": "How to add kids to a group",
        "intro": "This is one standing group. Add members here, then print or use the group as a filter on the activity calendar.",
        "steps": [
            {
                "title": "Add or remove members",
                "body": "Left is kids to add. Right is already in the group. Filter by school attending, grade, or name (and unit for admin), then Add or Add all shown.",
            },
            {
                "title": "Print sheets",
                "body": "Use the print buttons for daily attendance, weekly attendance (Monday–Friday), a member list, contact list, or emergency contacts.",
            },
        ],
    },
    "groups-print": {
        "title": "How to print a group sheet",
        "intro": "This printout is only the members of this group.",
        "steps": [
            {
                "title": "Check the list",
                "body": "Daily attendance has blank time-in and time-out lines for one day. Weekly attendance has Monday–Friday columns. Member list is names. Contact list is the parent phone. Emergency contacts is who to call.",
            },
            {
                "title": "Print / Save PDF",
                "body": "Use the browser print button. The YEA logo and title stay at the top of each printed page.",
            },
        ],
    },
    "activity": {
        "title": "How to read activity",
        "intro": "This is not one giant list. Choose a person first, then read only what that person did.",
        "steps": [
            {
                "title": "Pick a person",
                "body": "Search by name or username, then click Open activity. You will only see that person’s events — including your own.",
            },
            {
                "title": "Read the list",
                "body": "Each row is a date and time, the action, and the page or family they touched. Optional details sit in the last column.",
            },
            {
                "title": "See why something was deleted",
                "body": "Deletes ask for a required reason before they go through. That reason is saved here so you can see why it was removed. Cancel stays available on the delete prompt.",
            },
        ],
    },
    "billing-settings": {
        "title": "How to use member accounts",
        "intro": "This list is every enrolled family ledger, plus parent portal logins.",
        "steps": [
            {
                "title": "Open a family ledger",
                "body": "Use Manage billing for charges, credits, and payments on one household.",
            },
            {
                "title": "Reset parent password",
                "body": "You cannot look up the old password. Open the family profile, then Email create-password link for a one-time link to create a new password. Optional: set a temporary password that is shown once. Parents can also use Forgot password on Parent login.",
            },
        ],
    },
    "family-notes": {
        "title": "How to use staff notes",
        "intro": "Notes live on this child / family account, next to Profile, Pickup, Attendance, and Billing. Staff and admin can add many notes. Parents never see them.",
        "steps": [
            {
                "title": "Add as many notes as you need",
                "body": "Use Add a note. Choose This household or a child, then write the note. Each new note is saved on its own — you cannot edit another person’s note.",
            },
            {
                "title": "See who wrote it and when",
                "body": "Every note shows the staff or admin name and the date and time. Newest notes are at the top.",
            },
            {
                "title": "Staff stay on their unit",
                "body": "You only see notes for children at the unit in the header. Organization admin sees every note on the household. Delete asks for a reason, which is saved on the activity log.",
            },
        ],
    },
    "family-email": {
        "title": "How to email a parent",
        "intro": "This sends to the primary parent email on the account. You can attach files, and every send is saved in Emails sent. Click a section heading to fold it up or open it.",
        "steps": [
            {
                "title": "Write the message",
                "body": "Compose starts open. The address is filled from the profile. Keep the subject clear so the parent can find it later.",
            },
            {
                "title": "Upload if needed",
                "body": "Use Upload to attach PDF, photos, Word, Excel, PowerPoint, TXT, or CSV. Selected file names appear under the button. Remove a file before you send if you added the wrong one.",
            },
            {
                "title": "Find what you already sent",
                "body": "Emails sent under the compose box lists this family's messages. Click a row to open the full message. Click again or Close to fold it up. Open full email ledger if the list is long.",
            },
            {
                "title": "Collapse sections",
                "body": "Click Compose or Emails sent to hide that block. Expand all / Collapse all is at the top. The page remembers which sections you left open.",
            },
        ],
    },
    "parent-emails": {
        "title": "How to email parents",
        "intro": "Send one message to selected parents. Uploaded files go out with the email, and a copy is saved in Emails sent. Click a section heading to fold it up or open it.",
        "steps": [
            {
                "title": "Write and choose parents",
                "body": "Compose and Recipients start open. Enter the subject and message. Search the list and check only the parents who should get this email.",
            },
            {
                "title": "Upload documents",
                "body": "Use Upload for PDF, photos, or common office files. You can attach more than one. Remove a file before send if it should not go out.",
            },
            {
                "title": "Read the ledger",
                "body": "Emails sent under the form is every parent email from the portal. Click a row to read the full message. Use Emails sent in the menu for filters when the list gets long.",
            },
            {
                "title": "Edit application emails",
                "body": "The four application templates (submitted and approved, regular vs waitlist) are on this page. Change the wording anytime. Placeholders include parent name, child name, program, unit, start date, payment link, and first-payment steps. The start date is filled in when you approve the application.",
            },
            {
                "title": "Collapse sections",
                "body": "Click a heading (templates, Compose, Recipients, Emails sent) to hide that block. Expand all / Collapse all is at the top. The page remembers which sections you left open.",
            },
        ],
    },
    "emails-sent": {
        "title": "How to use the email ledger",
        "intro": "This is a record of parent emails already sent. Staff see their unit. Admin sees the whole organization.",
        "steps": [
            {
                "title": "Filter if you need to",
                "body": "Search by family, email, subject, or who sent it. Use the date boxes to narrow the week or month.",
            },
            {
                "title": "Open a message",
                "body": "Click the email row to open a box with the subject, recipients, sent time, attachments, and full message. Click again or Close to fold it up.",
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
    "parent-emergency-contacts": {
        "title": "How to update emergency contacts",
        "intro": "Add a person we can call, or delete someone who is out of date. Staff gets an email when you change this list.",
        "steps": [
            {
                "title": "Add a contact",
                "body": "Choose the child, then enter first name, last name, and phone. Add the relationship if you know it. Check authorized pickup if that person may pick up your child.",
            },
            {
                "title": "Delete if outdated",
                "body": "Use Delete next to a contact you no longer want. Confirm so we do not remove someone by accident.",
            },
            {
                "title": "Staff gets an email",
                "body": "When you add or delete a contact, YEA is emailed so we know which family, parent, and child changed, and who was added or removed.",
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
            elif slug == "emergency-contacts":
                key = "parent-emergency-contacts"
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
