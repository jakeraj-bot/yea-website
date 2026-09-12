from django.contrib import admin

from .models import (
    AttendanceRecord,
    PortalActivityEvent,
    PortalBillingDefaultRule,
    PortalChild,
    PortalEmailTemplate,
    PortalFamily,
    PortalFeeRule,
    PortalParentEmail,
    PortalParentEmailAttachment,
    PortalPaymentPlan,
    PortalProcessingFee,
    PortalProgram,
    PortalScholarshipFund,
    PortalUnit,
)


@admin.register(PortalUnit)
class PortalUnitAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "is_active")


@admin.register(PortalProgram)
class PortalProgramAdmin(admin.ModelAdmin):
    list_display = ("name", "unit", "start_time", "end_time", "is_active")
    list_filter = ("unit",)


@admin.register(PortalFamily)
class PortalFamilyAdmin(admin.ModelAdmin):
    list_display = ("name", "unit", "primary_contact", "status", "balance")
    list_filter = ("unit", "status")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(PortalChild)
class PortalChildAdmin(admin.ModelAdmin):
    list_display = ("name", "family", "unit", "grade", "is_active")
    list_filter = ("unit", "family__unit", "is_active")


@admin.register(AttendanceRecord)
class AttendanceRecordAdmin(admin.ModelAdmin):
    list_display = ("child", "date", "status", "check_in_time", "check_out_time", "method")
    list_filter = ("date", "status", "program")


@admin.register(PortalFeeRule)
class PortalFeeRuleAdmin(admin.ModelAdmin):
    """Org-wide fee catalog — membership, late fees, drop-in rates, etc."""

    list_display = ("name", "key", "display", "amount", "frequency", "period")
    list_filter = ("frequency",)
    search_fields = ("name", "key", "notes")
    ordering = ("name",)
    fieldsets = (
        (
            None,
            {
                "fields": ("key", "name", "amount", "display"),
                "description": (
                    "Set amounts here for the school year. The membership fee (key: membership) "
                    "posts to a family account when staff approves an enrollment application. "
                    "Other rules are reference defaults until automated billing is wired up."
                ),
            },
        ),
        ("Schedule & notes", {"fields": ("frequency", "period", "notes")}),
    )


@admin.register(PortalPaymentPlan)
class PortalPaymentPlanAdmin(admin.ModelAdmin):
    list_display = ("name", "interval", "is_active")
    list_filter = ("is_active",)


@admin.register(PortalProcessingFee)
class PortalProcessingFeeAdmin(admin.ModelAdmin):
    list_display = ("name", "percent", "flat_amount", "is_active")
    list_filter = ("is_active",)


@admin.register(PortalBillingDefaultRule)
class PortalBillingDefaultRuleAdmin(admin.ModelAdmin):
    list_display = (
        "role_name",
        "can_add_charge",
        "can_delete_charge",
        "can_add_credit",
        "can_edit_family_plans",
        "can_approve_applications",
        "can_approve_waitlist",
    )


@admin.register(PortalScholarshipFund)
class PortalScholarshipFundAdmin(admin.ModelAdmin):
    list_display = ("name", "is_active")
    list_filter = ("is_active",)


@admin.register(PortalEmailTemplate)
class PortalEmailTemplateAdmin(admin.ModelAdmin):
    list_display = ("name", "key", "is_enabled", "updated_at")
    list_filter = ("is_enabled",)


class PortalParentEmailAttachmentInline(admin.TabularInline):
    model = PortalParentEmailAttachment
    extra = 0
    readonly_fields = ("original_name", "content_type", "size", "file")


@admin.register(PortalParentEmail)
class PortalParentEmailAdmin(admin.ModelAdmin):
    list_display = ("subject", "sender_name", "sent_at", "unit", "family")
    list_filter = ("source", "unit", "sent_at")
    search_fields = ("subject", "sender_name", "body")
    readonly_fields = (
        "family",
        "unit",
        "sent_by",
        "sender_name",
        "recipients",
        "subject",
        "body",
        "attachment_names",
        "source",
        "sent_at",
    )
    inlines = [PortalParentEmailAttachmentInline]


@admin.register(PortalActivityEvent)
class PortalActivityEventAdmin(admin.ModelAdmin):
    list_display = ("created_at", "actor_name", "action_label", "object_label")
    list_filter = ("action", "actor_role")
    search_fields = ("actor_name", "actor_username", "object_label", "delete_reason")
    readonly_fields = (
        "actor",
        "actor_username",
        "actor_name",
        "actor_role",
        "unit",
        "created_at",
        "action",
        "action_label",
        "object_type",
        "object_label",
        "page_path",
        "details",
        "delete_reason",
    )
