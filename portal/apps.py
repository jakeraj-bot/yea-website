from django.apps import AppConfig


class PortalConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "portal"
    verbose_name = "YEA Portal"

    def ready(self):
        from django.contrib import admin

        from .forms import DjangoAdminAuthenticationForm

        admin.site.login_form = DjangoAdminAuthenticationForm
