from django.contrib import admin
from .models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ["order_id", "order_status", "channel", "recipient", "status", "attempts", "sent_at", "created_at"]
    list_filter = ["status", "channel", "order_status"]
    search_fields = ["order__order_number", "recipient"]
    readonly_fields = ["order", "order_status", "channel", "recipient", "status", "error_message", "attempts", "sent_at", "created_at"]
    ordering = ["-created_at"]
