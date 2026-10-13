from rest_framework import serializers

from fleet.models import Driver
from vendors.models import Vendor
from .models import Order, OrderEvent, OrderItem


class OrderItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderItem
        fields = ["id", "sku", "quantity"]


class OrderEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderEvent
        fields = ["id", "status", "document_name", "remarks", "created_at"]


class OrderCreateSerializer(serializers.ModelSerializer):
    vendor_id = serializers.PrimaryKeyRelatedField(queryset=Vendor.objects.all(), source="vendor", required=False)
    driver_id = serializers.PrimaryKeyRelatedField(
        queryset=Driver.objects.all(), source="driver", required=False, allow_null=True
    )
    items = OrderItemSerializer(many=True, required=False)

    class Meta:
        model = Order
        fields = [
            "vendor_id", "customer_name", "customer_phone", "customer_email", "delivery_address",
            "delivery_lat", "delivery_lng", "origin_city", "destination_city",
            "commodity", "weight_kg", "declared_value", "is_cod", "cod_amount",
            "order_date", "driver_id", "items",
        ]

    def create(self, validated_data):
        items_data = validated_data.pop("items", [])
        order = Order.objects.create(**validated_data)
        for item in items_data:
            OrderItem.objects.create(order=order, **item)
        return order


class OrderSerializer(serializers.ModelSerializer):
    vendor_id = serializers.IntegerField(source="vendor.id", read_only=True)
    driver_id = serializers.SerializerMethodField()
    items = OrderItemSerializer(many=True, read_only=True)
    invoice_id = serializers.SerializerMethodField()

    def get_driver_id(self, obj):
        return obj.driver_id  # Django FK auto-exposes the raw column as <field>_id

    def get_invoice_id(self, obj):
        if hasattr(obj, "_prefetched_objects_cache") and "invoices" in obj._prefetched_objects_cache:
            invs = obj.invoices.all()
            active = [i for i in invs if i.status != "cancelled"]
            if active:
                return active[0].id
            return invs[0].id if invs else None
        invoice = obj.invoices.exclude(status="cancelled").first() or obj.invoices.first()
        return invoice.id if invoice else None

    class Meta:
        model = Order
        fields = [
            "id", "order_number", "tracking_number", "vendor_id", "customer_name",
            "customer_phone", "customer_email", "delivery_address", "origin_city", "destination_city",
            "commodity", "weight_kg", "declared_value", "is_cod", "cod_amount", "status",
            "order_date", "pickup_date", "pickup_slot", "driver_id", "delivery_attempt_count",
            "freight_charge", "invoice_number", "invoice_amount", "invoice_id", "created_at",
            "updated_at", "items",
        ]


class OrderDetailSerializer(OrderSerializer):
    events = OrderEventSerializer(many=True, read_only=True)

    class Meta(OrderSerializer.Meta):
        fields = OrderSerializer.Meta.fields + ["events"]


class PublicOrderTrackSerializer(serializers.ModelSerializer):
    """Trimmed public tracking response — hides billing, vendor margins, and customer phone/address."""
    events = OrderEventSerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = [
            "order_number", "tracking_number", "status",
            "origin_city", "destination_city", "commodity", "weight_kg",
            "pickup_date", "pickup_slot", "created_at", "updated_at", "events",
        ]


class BookingSerializer(serializers.Serializer):
    pickup_date = serializers.CharField()
    pickup_slot = serializers.CharField()


class DeliveryAttemptSerializer(serializers.Serializer):
    success = serializers.BooleanField()
    remarks = serializers.CharField(required=False, allow_null=True)
    recipient_name = serializers.CharField(required=False, allow_null=True)
    proof_type = serializers.CharField(required=False, allow_null=True)
