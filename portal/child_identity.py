"""Match the same child when a middle name is added or dropped."""

import re

_NAME_SPLIT = re.compile(r"[^\w]+", re.UNICODE)


def normalize_person_name(value):
    return " ".join((value or "").split()).strip().lower()


def name_tokens(value):
    return [part for part in _NAME_SPLIT.split(normalize_person_name(value)) if part]


def full_child_name(first="", last="", child_name=""):
    if (child_name or "").strip():
        return " ".join((child_name or "").split()).strip()
    return " ".join(part for part in [first, last] if (part or "").strip()).strip()


def child_names_match(left, right):
    """True when two labels are the same child, including an extra middle name.

    "Danuska Montoya Cuenca" and "Danuska Daenerys Montoya Cuenca" match.
    "Danuska Rivera" and "Danuska Lee" do not.
    """
    left_norm = normalize_person_name(left)
    right_norm = normalize_person_name(right)
    if not left_norm or not right_norm:
        return False
    if left_norm == right_norm:
        return True

    left_tokens = name_tokens(left_norm)
    right_tokens = name_tokens(right_norm)
    if not left_tokens or not right_tokens:
        return False
    if left_tokens == right_tokens:
        return True
    if left_tokens[0] != right_tokens[0]:
        return False

    shorter, longer = sorted((left_tokens, right_tokens), key=len)
    if len(shorter) < 2:
        return False
    if set(shorter) <= set(longer) and shorter[-1] in longer:
        return True
    return left_tokens[-1] == right_tokens[-1]


def child_name_in_collection(name, names):
    return any(child_names_match(name, other) for other in names if other)
