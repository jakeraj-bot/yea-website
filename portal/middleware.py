from django.utils import translation

from .activity_log import log_from_middleware
from .parent_i18n import (
    get_parent_language,
    is_parent_portal_request,
    language_cookie_kwargs,
    set_parent_language,
)


class ParentLanguageMiddleware:
    """Activate EN/ES for parent portal pages from the yea_parent_lang cookie."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        parent_request = is_parent_portal_request(request)
        if parent_request:
            lang = get_parent_language(request)
            set_parent_language(request, lang)
            translation.activate(lang)
            request.LANGUAGE_CODE = lang
        else:
            request.parent_lang = "en"
        response = self.get_response(request)
        if parent_request:
            cookie = language_cookie_kwargs(getattr(request, "parent_lang", "en"))
            if request.COOKIES.get(cookie["key"]) != cookie["value"]:
                response.set_cookie(**cookie)
            translation.deactivate()
        return response


class PortalActivityMiddleware:
    """Log successful portal writes that views did not log explicitly."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        try:
            log_from_middleware(request, response)
        except Exception:
            pass
        return response
