from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

from .models import EmergencyContact, EnrollmentApplication, PolicySignature


class EmergencyContactInline(admin.TabularInline):
    model = EmergencyContact
    extra = 0


class PolicySignatureInline(admin.TabularInline):
    model = PolicySignature
    extra = 0
    readonly_fields = ("policy_slug", "policy_title", "signature_name", "signed_date", "extra_data")


@admin.register(EnrollmentApplication)
class EnrollmentApplicationAdmin(admin.ModelAdmin):
    list_display = (
        "student_first_name",
        "student_last_name",
        "child_number",
        "family_name",
        "program",
        "program_location",
        "submitted_at",
        "family_group",
        "print_link",
    )
    list_filter = ("program", "program_location", "submitted_at")
    search_fields = (
        "student_first_name",
        "student_last_name",
        "family_name",
        "primary_email",
        "family_group",
    )
    readonly_fields = ("reference", "family_group", "submitted_at", "print_link")
    inlines = [EmergencyContactInline, PolicySignatureInline]

    @admin.display(description="Print")
    def print_link(self, obj):
        if not obj.pk:
            return "—"
        url = reverse("enrollment_print", args=[obj.reference])
        return format_html('<a href="{}" target="_blank" rel="noopener">Print application</a>', url)
