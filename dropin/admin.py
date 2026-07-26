from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html
from django.utils import timezone

from .models import (
    DropInBooking,
    DropInChild,
    DropInDayCapacity,
    DropInEmergencyContact,
    DropInFamilyProfile,
    DropInPolicySignature,
    DropInWaitlistEntry,
)
from .notifications import notify_parent_approved


class DropInChildInline(admin.TabularInline):
    model = DropInChild
    extra = 0


class DropInEmergencyContactInline(admin.TabularInline):
    model = DropInEmergencyContact
    extra = 0


class DropInPolicySignatureInline(admin.TabularInline):
    model = DropInPolicySignature
    extra = 0
    readonly_fields = ("policy_slug", "policy_title", "signature_name", "signed_date", "extra_data")


@admin.register(DropInFamilyProfile)
class DropInFamilyProfileAdmin(admin.ModelAdmin):
    list_display = ("family_name", "primary_email", "primary_phone", "status", "submitted_at", "approved_at")
    list_filter = ("status", "submitted_at")
    search_fields = ("family_name", "primary_email", "primary_first_name", "primary_last_name")
    readonly_fields = ("reference", "submitted_at", "updated_at", "approved_at")
    actions = ["approve_profiles", "reject_profiles"]
    inlines = [DropInChildInline, DropInEmergencyContactInline, DropInPolicySignatureInline]

    @admin.action(description="Approve selected families for drop-in booking")
    def approve_profiles(self, request, queryset):
        for profile in queryset:
            if profile.status != DropInFamilyProfile.STATUS_APPROVED:
                profile.status = DropInFamilyProfile.STATUS_APPROVED
                profile.approved_at = timezone.now()
                profile.save(update_fields=["status", "approved_at"])
                notify_parent_approved(profile)

    @admin.action(description="Reject selected families")
    def reject_profiles(self, request, queryset):
        queryset.update(status=DropInFamilyProfile.STATUS_REJECTED, approved_at=None)


@admin.register(DropInDayCapacity)
class DropInDayCapacityAdmin(admin.ModelAdmin):
    list_display = (
        "date",
        "program",
        "location",
        "max_slots",
        "booked_display",
        "spots_left",
        "waitlist_display",
        "roster_link",
    )
    list_filter = ("program", "location", "date")
    date_hierarchy = "date"
    ordering = ("date", "program", "location")

    @admin.display(description="Booked")
    def booked_display(self, obj):
        from .services import booked_count

        return booked_count(obj.program, obj.location, obj.date)

    @admin.display(description="Spots left")
    def spots_left(self, obj):
        from .services import spots_remaining

        remaining, _ = spots_remaining(obj.program, obj.location, obj.date)
        return remaining

    @admin.display(description="Waitlist")
    def waitlist_display(self, obj):
        from .services import spots_remaining, waitlist_count

        remaining, _ = spots_remaining(obj.program, obj.location, obj.date)
        count = waitlist_count(obj.program, obj.location, obj.date)
        if remaining <= 0 and count:
            return format_html('<strong style="color:#b45309;">{} waiting — contact in order if spot opens</strong>', count)
        if count:
            return str(count)
        return "—"

    @admin.display(description="Roster")
    def roster_link(self, obj):
        url = (
            reverse("dropin_roster")
            + f"?date={obj.date.isoformat()}&program={obj.program}&location={obj.location}"
        )
        return format_html('<a href="{}" target="_blank" rel="noopener">View / print</a>', url)


@admin.register(DropInWaitlistEntry)
class DropInWaitlistEntryAdmin(admin.ModelAdmin):
    list_display = ("date", "queue_position", "child", "program", "location", "profile", "status", "created_at")
    list_filter = ("status", "program", "location", "date")
    search_fields = ("child__first_name", "child__last_name", "profile__family_name")
    date_hierarchy = "date"
    ordering = ("date", "program", "location", "created_at")

    @admin.display(description="#")
    def queue_position(self, obj):
        earlier = DropInWaitlistEntry.objects.filter(
            date=obj.date,
            program=obj.program,
            location=obj.location,
            status=DropInWaitlistEntry.STATUS_WAITING,
            created_at__lte=obj.created_at,
        ).count()
        return earlier


@admin.register(DropInBooking)
class DropInBookingAdmin(admin.ModelAdmin):
    list_display = (
        "date",
        "child",
        "program",
        "location",
        "status",
        "profile",
        "created_at",
    )
    list_filter = ("status", "program", "location", "date")
    search_fields = (
        "child__first_name",
        "child__last_name",
        "profile__family_name",
        "profile__primary_email",
    )
    date_hierarchy = "date"
    readonly_fields = ("reference", "stripe_session_id", "created_at", "paid_at")
