from django.contrib import admin

from .models import Driver, Vehicle


@admin.register(Driver)
class DriverAdmin(admin.ModelAdmin):
    list_display = ["id", "user", "full_name", "phone", "is_available", "current_lat", "current_lng"]
    list_filter = ["is_available"]
    raw_id_fields = ["user"]


@admin.register(Vehicle)
class VehicleAdmin(admin.ModelAdmin):
    list_display = ["id", "plate_number", "vehicle_type", "capacity_kg"]
