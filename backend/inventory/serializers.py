from rest_framework import serializers

from .models import InventoryItem, Warehouse


class WarehouseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Warehouse
        fields = ["id", "name", "address", "latitude", "longitude"]


class InventoryItemSerializer(serializers.ModelSerializer):
    warehouse_id = serializers.PrimaryKeyRelatedField(queryset=Warehouse.objects.all(), source="warehouse")

    class Meta:
        model = InventoryItem
        fields = ["id", "sku", "name", "quantity", "warehouse_id"]


class StockAdjustSerializer(serializers.Serializer):
    delta = serializers.IntegerField()
