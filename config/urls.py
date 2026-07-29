from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.sitemaps.views import sitemap
from django.urls import include, path
from django.views.generic import TemplateView

from core.sitemaps import StaticViewSitemap

sitemaps = {"static": StaticViewSitemap}

urlpatterns = [
    path("admin/", admin.site.urls),
    path(
        "robots.txt",
        TemplateView.as_view(
            template_name="robots.txt",
            content_type="text/plain",
        ),
        name="robots_txt",
    ),
    path(
        "sitemap.xml",
        sitemap,
        {"sitemaps": sitemaps},
        name="django.contrib.sitemaps.views.sitemap",
    ),
    path("", include("core.urls")),
    path("programs/", include("programs.urls")),
    path("partnerships/", include("partnerships.urls")),
    path("donate/", include("donations.urls")),
    path("apply/", include("enrollment.urls")),
    path("drop-in/", include("dropin.urls")),
    path("portal/", include("portal.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
