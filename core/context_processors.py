from django.conf import settings


def site_settings(request):
    return {
        "site_url": settings.SITE_URL.rstrip("/"),
        "site_name": "Youth Education Academy",
    }
