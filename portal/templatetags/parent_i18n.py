from django import template
from django.utils.safestring import mark_safe

from portal.parent_i18n import get_parent_language, translate

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
def parent_pay_url(context):
    from django.urls import reverse

    request = context.get("request")
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
    if request:
        try:
            return reverse("portal_parent_payment") + pay_query
        except Exception:
            pass
    return "#"
