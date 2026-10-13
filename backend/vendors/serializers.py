from rest_framework import serializers

from .models import Vendor


class VendorSerializer(serializers.ModelSerializer):
    billing_email = serializers.ReadOnlyField()

    class Meta:
        model = Vendor
        fields = ["id", "user", "name", "contact_phone", "email", "billing_email", "address", "latitude", "longitude"]
