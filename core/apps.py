from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "core"

    def ready(self):
        import logging

        from django.conf import settings

        from core.email_service import email_is_configured

        if not settings.DEBUG and not email_is_configured():
            logging.getLogger(__name__).warning(
                "SMTP email is NOT configured — application and contact emails will not be delivered. "
                "Set EMAIL_HOST, EMAIL_HOST_USER, and EMAIL_HOST_PASSWORD in your environment."
            )
