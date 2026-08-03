from django.conf import settings


def site_settings(request):
    return {
        "site_url": settings.SITE_URL.rstrip("/"),
        "site_name": "Youth Education Academy",
    }


def portal_deploy(request):
    """Portal flags for public pages and login screens (not full portal views)."""
    preview_mode = getattr(settings, "PORTAL_PREVIEW_MODE", False)
    staging_site = getattr(settings, "STAGING_SITE", False)
    portal_live = not preview_mode
    portals_public = getattr(settings, "PORTALS_PUBLIC", True)
    return {
        "preview_mode": preview_mode,
        "staging_site": staging_site,
        "portal_live": portal_live,
        "portals_public": portals_public,
        "show_dev_hints": preview_mode and not staging_site,
    }
