from django.conf import settings
from django.contrib import messages
from django.contrib.auth.views import (
    PasswordResetCompleteView,
    PasswordResetConfirmView,
    PasswordResetDoneView,
    PasswordResetView,
)

from core.spam_protection import is_rate_limited, record_attempt

from .forms import PortalPasswordResetForm


class PortalPasswordResetView(PasswordResetView):
    form_class = PortalPasswordResetForm
    template_name = "portal/password_reset/request.html"
    email_template_name = "portal/password_reset/email_body.txt"
    subject_template_name = "portal/password_reset/email_subject.txt"
    portal_type = "parent"
    portal_label = "parent portal"
    login_url_name = "portal_parent_login"
    reset_confirm_url_name = "portal_parent_password_reset_confirm"
    reset_done_url_name = "portal_parent_password_reset_done"

    def form_valid(self, form):
        limit = getattr(settings, "PORTAL_PASSWORD_RESET_RATE_LIMIT", 5)
        window = getattr(settings, "PORTAL_PASSWORD_RESET_RATE_WINDOW_SECONDS", 3600)
        if is_rate_limited(self.request, "portal-password-reset", limit, window):
            messages.error(self.request, "Too many password reset attempts. Please try again later.")
            return self.form_invalid(form)
        record_attempt(self.request, "portal-password-reset", window)
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["portal_label"] = self.portal_label
        context["login_url_name"] = self.login_url_name
        context["portal_area"] = "public"
        return context

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["portal_type"] = self.portal_type
        return kwargs

    def get_success_url(self):
        from django.urls import reverse

        return reverse(self.reset_done_url_name)

    def get_extra_email_context(self):
        return {
            "portal_label": self.portal_label,
            "reset_confirm_url_name": self.reset_confirm_url_name,
        }


class PortalPasswordResetDoneView(PasswordResetDoneView):
    template_name = "portal/password_reset/done.html"
    portal_type = "parent"
    portal_label = "parent portal"
    login_url_name = "portal_parent_login"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["portal_label"] = self.portal_label
        context["login_url_name"] = self.login_url_name
        context["portal_area"] = "public"
        return context


class PortalPasswordResetConfirmView(PasswordResetConfirmView):
    template_name = "portal/password_reset/confirm.html"
    portal_type = "parent"
    portal_label = "parent portal"
    reset_complete_url_name = "portal_parent_password_reset_complete"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["portal_label"] = self.portal_label
        context["portal_area"] = "public"
        return context

    def get_success_url(self):
        from django.urls import reverse

        return reverse(self.reset_complete_url_name)


class PortalPasswordResetCompleteView(PasswordResetCompleteView):
    template_name = "portal/password_reset/complete.html"
    portal_type = "parent"
    portal_label = "parent portal"
    login_url_name = "portal_parent_login"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["portal_label"] = self.portal_label
        context["login_url_name"] = self.login_url_name
        context["portal_area"] = "public"
        return context


class ParentPasswordResetView(PortalPasswordResetView):
    portal_type = "parent"
    portal_label = "parent portal"
    reset_confirm_url_name = "portal_parent_password_reset_confirm"
    reset_done_url_name = "portal_parent_password_reset_done"


class ParentPasswordResetDoneView(PortalPasswordResetDoneView):
    portal_type = "parent"
    portal_label = "parent portal"
    login_url_name = "portal_parent_login"


class ParentPasswordResetConfirmView(PortalPasswordResetConfirmView):
    portal_type = "parent"
    portal_label = "parent portal"
    reset_complete_url_name = "portal_parent_password_reset_complete"


class ParentPasswordResetCompleteView(PortalPasswordResetCompleteView):
    portal_type = "parent"
    portal_label = "parent portal"
    login_url_name = "portal_parent_login"


class StaffPasswordResetView(PortalPasswordResetView):
    portal_type = "staff"
    portal_label = "staff portal"
    reset_confirm_url_name = "portal_staff_password_reset_confirm"
    reset_done_url_name = "portal_staff_password_reset_done"


class StaffPasswordResetDoneView(PortalPasswordResetDoneView):
    portal_type = "staff"
    portal_label = "staff portal"
    login_url_name = "portal_staff_login"


class StaffPasswordResetConfirmView(PortalPasswordResetConfirmView):
    portal_type = "staff"
    portal_label = "staff portal"
    reset_complete_url_name = "portal_staff_password_reset_complete"


class StaffPasswordResetCompleteView(PortalPasswordResetCompleteView):
    portal_type = "staff"
    portal_label = "staff portal"
    login_url_name = "portal_staff_login"


class AdminPasswordResetView(PortalPasswordResetView):
    portal_type = "admin"
    portal_label = "portal admin"
    reset_confirm_url_name = "portal_admin_password_reset_confirm"
    reset_done_url_name = "portal_admin_password_reset_done"


class AdminPasswordResetDoneView(PortalPasswordResetDoneView):
    portal_type = "admin"
    portal_label = "portal admin"
    login_url_name = "portal_admin_login"


class AdminPasswordResetConfirmView(PortalPasswordResetConfirmView):
    portal_type = "admin"
    portal_label = "portal admin"
    reset_complete_url_name = "portal_admin_password_reset_complete"


class AdminPasswordResetCompleteView(PortalPasswordResetCompleteView):
    portal_type = "admin"
    portal_label = "portal admin"
    login_url_name = "portal_admin_login"
