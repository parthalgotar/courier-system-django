from django.contrib import admin

from .models import Vendor


@admin.register(Vendor)
class VendorAdmin(admin.ModelAdmin):
    list_display = ["id", "name", "contact_phone", "address", "user", "email"]
    search_fields = ["name", "contact_phone", "email", "user__email"]
    # Linking a vendor to a login account is done here (see backend/README.md).
    raw_id_fields = ["user"]
