"""Build signed policy payloads for display and print."""

from urllib.parse import urlencode

from django.urls import reverse

from enrollment.policies_loader import get_policies, get_policy_by_slug


def _format_signed_date(value):
    if not value:
        return None
    return value.strftime("%B %d, %Y")


def _extra_fields_display(policy_def, extra_data):
    if not extra_data:
        return []
    fields_by_name = {field["name"]: field for field in policy_def.get("fields", [])}
    lines = []
    for key, value in extra_data.items():
        if value in (None, ""):
            continue
        field = fields_by_name.get(key, {})
        label = field.get("label", key.replace("_", " ").title())
        display_value = value
        if field.get("type") == "choice":
            choices = dict(field.get("choices", []))
            display_value = choices.get(value, value)
        lines.append({"label": label, "value": display_value})
    return lines


def get_application_policies(app, lang="en"):
    """Return signed policy dicts with full text for one enrollment application."""
    policies_source = get_policies(lang)
    signed_by_slug = {sig.policy_slug: sig for sig in app.policy_signatures.all()}
    child_name = f"{app.student_first_name} {app.student_last_name}".strip()
    policies = []
    for policy in policies_source:
        sig = signed_by_slug.get(policy["slug"])
        extra_data = (sig.extra_data or {}) if sig else {}
        policies.append(
            {
                "slug": policy["slug"],
                "title": policy["title"],
                "paragraphs": policy["paragraphs"],
                "acknowledgment": policy.get("acknowledgment", ""),
                "signed": bool(sig),
                "signed_date": _format_signed_date(sig.signed_date) if sig else None,
                "signed_by": sig.signature_name if sig else None,
                "child_name": child_name,
                "extra_fields": _extra_fields_display(policy, extra_data),
            }
        )
    return policies


def get_application_policy(app, policy_slug, lang="en"):
    """Return one policy dict for an application, or None if slug unknown."""
    policy_def = get_policy_by_slug(policy_slug, lang)
    if not policy_def:
        return None
    for policy in get_application_policies(app, lang=lang):
        if policy["slug"] == policy_slug:
            return policy
    return None


def attach_policy_print_urls(policies, url_name, query=None, **url_kwargs):
    """Add a print_url to each signed policy for portal templates."""
    for policy in policies:
        if policy.get("signed"):
            url = reverse(url_name, kwargs={**url_kwargs, "policy_slug": policy["slug"]})
            if query:
                url = f"{url}?{urlencode(query)}"
            policy["print_url"] = url
        else:
            policy["print_url"] = ""
    return policies
