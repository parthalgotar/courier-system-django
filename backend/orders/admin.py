from django.contrib import admin

from .models import Order, OrderEvent, OrderItem


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0


class OrderEventInline(admin.TabularInline):
    model = OrderEvent
    extra = 0
    readonly_fields = ["status", "document_name", "remarks", "created_at"]
    can_delete = False


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ["order_number", "tracking_number", "customer_name", "status", "is_cod", "created_at"]
    list_filter = ["status", "is_cod"]
    search_fields = ["order_number", "tracking_number", "customer_name"]
    inlines = [OrderItemInline, OrderEventInline]
