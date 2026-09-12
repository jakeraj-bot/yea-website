"""Check / money order numbers live beside a payment, not inside the description."""

import re

# Safe prefix-only mash from older rows: "Check #2201" or "Money order #1234 — note".
CHECK_MO_DESCRIPTION_RE = re.compile(
    r"^(?P<kind>Check|Money order)\s*#\s*(?P<number>[A-Za-z0-9][A-Za-z0-9\-]*)"
    r"(?:\s*[—–-]\s*(?P<note>.*))?$",
    re.IGNORECASE,
)

RAW_CARD_FIELD_NAMES = (
    "card_number",
    "cardnumber",
    "cc_number",
    "cc-number",
    "pan",
    "cvc",
    "cvv",
    "cvc2",
    "card_cvc",
    "card_cvv",
    "card_expiry",
    "exp_month",
    "exp_year",
)


def parse_check_money_order_description(description):
    """Split a Check/MO prefix from a human note when that is the whole description.

    Returns (kind, number, note). kind is ``check``, ``money_order``, or empty when
    the text is not a safe prefix-only mash (so real notes are left alone).
    """
    text = (description or "").strip()
    if not text:
        return "", "", ""
    match = CHECK_MO_DESCRIPTION_RE.match(text)
    if not match:
        return "", "", text
    kind = match.group("kind").lower().replace(" ", "_")
    number = (match.group("number") or "").strip()
    note = (match.group("note") or "").strip()
    return kind, number, note


def payment_instrument_kind(method_label="", description=""):
    text = f"{method_label or ''} {description or ''}".lower()
    if "money order" in text:
        return "money_order"
    if re.search(r"\bcheck\b", text):
        return "check"
    return ""


def clean_in_person_method_label(method_label):
    """Return Check / Money order / original without a mashed #number."""
    kind, _number, _note = parse_check_money_order_description(method_label or "")
    if kind == "money_order":
        return "Money order"
    if kind == "check":
        return "Check"
    return (method_label or "").strip()


def is_receipt_reference(number):
    return (number or "").strip().upper().startswith("RCPT-")


def display_payment_reference(description="", reference_number="", method_label=""):
    """Build the on-screen note and Check # / Money order # label.

    Stored description is not rewritten. Old rows that mashed the number into
    the description are split only when the whole string is that prefix.
    Stripe receipt numbers (RCPT-...) are not check or money order numbers.
    """
    stored_ref = (reference_number or "").strip()
    parsed_kind, parsed_number, parsed_note = parse_check_money_order_description(description)
    kind = parsed_kind or payment_instrument_kind(method_label, description if parsed_kind else "")
    number = stored_ref or parsed_number
    if number and is_receipt_reference(number) and not parsed_number:
        number = ""
        if not parsed_kind:
            kind = ""

    if number and not kind and not is_receipt_reference(number):
        # Migration 0021 stored check/MO numbers here; label when we cannot tell which.
        if parsed_number or stored_ref:
            kind = "check_or_money_order"

    if not number or kind not in ("check", "money_order", "check_or_money_order"):
        return {
            "description": (description or "").strip(),
            "reference_number": "",
            "reference_label": "",
            "reference_display": "",
        }

    if kind == "money_order":
        label = "Money order #"
    elif kind == "check":
        label = "Check #"
    else:
        label = "Check/MO #"

    display_description = parsed_note if parsed_number else (description or "").strip()
    if parsed_number and not display_description:
        if kind == "money_order":
            display_description = "In-person payment — Money order"
        elif kind == "check":
            display_description = "In-person payment — Check"
        else:
            display_description = "In-person payment"
    return {
        "description": display_description,
        "reference_number": number,
        "reference_label": label,
        "reference_display": f"{label}{number}",
    }


def attach_ledger_reference(row, description="", reference_number="", method_label=""):
    display = display_payment_reference(description, reference_number, method_label)
    row["description"] = display["description"] or description or ""
    row["reference_number"] = display["reference_number"]
    row["reference_label"] = display["reference_label"]
    row["reference_display"] = display["reference_display"]
    if display["reference_label"].startswith("Money order"):
        row["method"] = "Money order"
    elif display["reference_label"].startswith("Check #"):
        row["method"] = "Check"
    return row


def method_label_for_reference(payments, reference_number):
    ref = (reference_number or "").strip()
    if not ref or not payments:
        return ""
    for payment in payments:
        if (payment.reference_number or "").strip() == ref:
            return payment.method_label or ""
    return ""


def reject_raw_card_fields(post):
    """Staff must never type a card number into a YEA form."""
    for name in RAW_CARD_FIELD_NAMES:
        if (post.get(name) or "").strip():
            raise ValueError(
                "Do not type card numbers into the portal. Use Take a card payment so Stripe collects the card."
            )
