from django.contrib import admin

from .models import AttendanceRecord, PortalChild, PortalFamily, PortalProgram, PortalUnit


@admin.register(PortalUnit)
class PortalUnitAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "is_active")


@admin.register(PortalProgram)
class PortalProgramAdmin(admin.ModelAdmin):
    list_display = ("name", "unit", "start_time", "end_time", "is_active")
    list_filter = ("unit",)


@admin.register(PortalFamily)
class PortalFamilyAdmin(admin.ModelAdmin):
    list_display = ("name", "unit", "primary_contact", "status")
    list_filter = ("unit", "status")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(PortalChild)
class PortalChildAdmin(admin.ModelAdmin):
    list_display = ("name", "family", "grade", "is_active")
    list_filter = ("family__unit", "is_active")


@admin.register(AttendanceRecord)
class AttendanceRecordAdmin(admin.ModelAdmin):
    list_display = ("child", "date", "status", "check_in_time", "check_out_time", "method")
    list_filter = ("date", "status", "program")
