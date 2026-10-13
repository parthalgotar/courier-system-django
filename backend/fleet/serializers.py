from rest_framework import serializers

from .models import Driver, Vehicle


class DriverSerializer(serializers.ModelSerializer):
    class Meta:
        model = Driver
        fields = ["id", "user", "full_name", "phone", "is_available", "current_lat", "current_lng"]
        read_only_fields = ["is_available", "current_lat", "current_lng"]


class DriverLocationSerializer(serializers.Serializer):
    latitude = serializers.FloatField()
    longitude = serializers.FloatField()


class VehicleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vehicle
        fields = ["id", "plate_number", "vehicle_type", "capacity_kg"]
