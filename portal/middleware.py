from .activity_log import log_from_middleware


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
