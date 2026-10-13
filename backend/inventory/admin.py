from django.contrib import admin

from .models import InventoryItem, Warehouse


@admin.register(Warehouse)
class WarehouseAdmin(admin.ModelAdmin):
    list_display = ["id", "name", "address"]


@admin.register(InventoryItem)
class InventoryItemAdmin(admin.ModelAdmin):
    list_display = ["id", "sku", "name", "quantity", "warehouse"]
    search_fields = ["sku", "name"]
