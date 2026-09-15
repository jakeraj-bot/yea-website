from django import template
from django.utils.safestring import mark_safe

from portal.parent_i18n import get_parent_language, translate, translate_label

register = template.Library()


@register.simple_tag(takes_context=True)
def pt(context, key, **kwargs):
    request = context.get("request")
    lang = context.get("parent_lang") or get_parent_language(request)
    text = translate(lang, key, **kwargs)
    if "<" in text:
        return mark_safe(text)
    return text


@register.simple_tag(takes_context=True)
def ptl(context, value):
    request = context.get("request")
    lang = context.get("parent_lang") or get_parent_language(request)
    return translate_label(lang, value)


@register.simple_tag(takes_context=True)
def parent_portal_href(context, page, **query):
    from urllib.parse import urlencode

    from django.urls import reverse

    extra = {key: value for key, value in query.items() if value not in (None, "")}
    if context.get("admin_preview_sample"):
        url = reverse("portal_admin_parent_preview_sample_page", kwargs={"page": page})
        params = {"pay": context.get("parent_preview_key") or "private-pay", **extra}
        return f"{url}?{urlencode(params)}"
    if context.get("admin_support_preview") and context.get("admin_preview_family_slug"):
        url = reverse(
            "portal_admin_parent_preview_page",
            kwargs={"family_slug": context["admin_preview_family_slug"], "page": page},
        )
        params = dict(extra)
        family_id = context.get("admin_preview_family_id")
        if family_id:
            params["id"] = family_id
        if params:
            return f"{url}?{urlencode(params)}"
        return url
    url = reverse("portal_parent_page", kwargs={"page": page})
    pay_query = context.get("parent_pay_query") or ""
    if extra:
        encoded = urlencode(extra)
        if pay_query:
            separator = "&" if "?" in pay_query else "?"
            return f"{url}{pay_query}{separator}{encoded}"
        return f"{url}?{encoded}"
    return f"{url}{pay_query}"


@register.simple_tag(takes_context=True)
def parent_pay_url(context):
    from django.urls import reverse

    pay_query = context.get("parent_pay_query") or ""
    if context.get("admin_preview_sample"):
        return reverse("portal_admin_parent_preview_sample_page", kwargs={"page": "billing"})
    if context.get("admin_support_preview") and context.get("admin_preview_family_slug"):
        url = reverse(
            "portal_admin_parent_preview_page",
            kwargs={"family_slug": context["admin_preview_family_slug"], "page": "billing"},
        )
        family_id = context.get("admin_preview_family_id")
        if family_id:
            return f"{url}?id={family_id}"
        return url
    return reverse("portal_parent_payment") + pay_query
