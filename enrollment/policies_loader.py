"""Load enrollment policies in the requested language."""

from .policies_data import POLICIES, POLICY_BY_SLUG


def get_policies(lang="en"):
    if lang == "es":
        from .policies_data_es import POLICIES_ES

        return POLICIES_ES
    return POLICIES


def get_policy_by_slug(slug, lang="en"):
    if lang == "es":
        from .policies_data_es import POLICY_BY_SLUG_ES

        return POLICY_BY_SLUG_ES.get(slug)
    return POLICY_BY_SLUG.get(slug)
