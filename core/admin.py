from django.contrib import admin

from .models import ContactMessage


@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ("name", "email", "topic", "created_at")
    list_filter = ("topic", "created_at")
    search_fields = ("name", "email", "message")
    readonly_fields = ("name", "email", "topic", "message", "created_at")
