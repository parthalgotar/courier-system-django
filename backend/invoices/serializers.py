from decimal import Decimal
from rest_framework import serializers

from .models import (
    Customer,
    Invoice,
    InvoiceLine,
    InvoiceSendLog,
    InvoiceSendStatus,
    InvoiceStatus,
    Journal,
    Payment,
    PaymentStatus,
    Tag,
)
from .services import compute_and_save_invoice_totals


class CustomerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = ["id", "name", "email", "phone", "address", "created_at"]


class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ["id", "name", "color"]


class JournalSerializer(serializers.ModelSerializer):
    type_display = serializers.CharField(source="get_type_display", read_only=True)

    class Meta:
        model = Journal
        fields = ["id", "name", "type", "type_display"]


class InvoiceLineSerializer(serializers.ModelSerializer):
    subtotal = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = InvoiceLine
        fields = ["id", "invoice", "product", "description", "quantity", "unit_price", "tax_percent", "subtotal"]
        extra_kwargs = {
            "invoice": {"required": False},
        }

    def validate(self, attrs):
        inv = attrs.get("invoice") or getattr(self.instance, "invoice", None)
        if inv and inv.status in (InvoiceStatus.POSTED, InvoiceStatus.PAID, InvoiceStatus.ISSUED):
            raise serializers.ValidationError("Cannot add or edit lines on a posted or paid invoice.")
        return attrs


class PaymentSerializer(serializers.ModelSerializer):
    journal_name = serializers.CharField(source="journal.name", read_only=True)
    journal_type = serializers.CharField(source="journal.type", read_only=True)
    invoice_number = serializers.CharField(source="invoice.number", read_only=True)
    customer_name = serializers.SerializerMethodField()
    number = serializers.CharField(source="payment_number", read_only=True)

    class Meta:
        model = Payment
        fields = [
            "id",
            "payment_number",
            "number",
            "invoice",
            "invoice_number",
            "customer_name",
            "journal",
            "journal_name",
            "journal_type",
            "amount",
            "payment_date",
            "memo",
            "status",
            "created_by",
            "created_at",
        ]
        read_only_fields = ["id", "payment_number", "number", "created_at"]

    def get_customer_name(self, obj):
        if obj.invoice and obj.invoice.customer:
            return obj.invoice.customer.name
        if obj.invoice and obj.invoice.order:
            return obj.invoice.order.customer_name
        return "—"


class PayInvoiceSerializer(serializers.Serializer):
    """Serializer for registering a payment from the Pay modal."""
    journal = serializers.PrimaryKeyRelatedField(queryset=Journal.objects.all())
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0.01"))
    payment_date = serializers.DateField(required=False)
    memo = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")


class InvoiceSendLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = InvoiceSendLog
        fields = ["id", "recipient_email", "status", "sent_at", "attempts", "error_message", "created_at"]
        read_only_fields = fields

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get("request")
        role = getattr(getattr(request, "user", None), "role", None)
        if role not in ("admin", "dispatcher"):
            data.pop("error_message", None)
        return data


class InvoiceSendLogCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = InvoiceSendLog
        fields = ["recipient_email", "status", "sent_at", "attempts", "error_message"]
        extra_kwargs = {
            "recipient_email": {"default": "", "allow_blank": True},
            "status": {"default": InvoiceSendStatus.PENDING},
            "sent_at": {"required": False, "allow_null": True},
            "attempts": {"required": False, "default": 0},
            "error_message": {"default": "", "allow_blank": True},
        }


class InvoiceSerializer(serializers.ModelSerializer):
    """Full representation used by both list and detail endpoints."""

    lines = InvoiceLineSerializer(many=True, required=False)
    payments = PaymentSerializer(many=True, read_only=True)
    payment_count = serializers.IntegerField(source="payments.count", read_only=True)
    customer_name = serializers.SerializerMethodField()
    tag_details = TagSerializer(source="tags", many=True, read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    # Legacy fields preserved for order billing
    order_id = serializers.IntegerField(read_only=True, required=False, allow_null=True)
    order_number = serializers.CharField(source="order.order_number", read_only=True)
    tracking_number = serializers.CharField(source="order.tracking_number", read_only=True)
    vendor_id = serializers.IntegerField(source="order.vendor_id", read_only=True)
    vendor_name = serializers.CharField(source="order.vendor.name", read_only=True)

    class Meta:
        model = Invoice
        fields = [
            "id",
            "number",
            "invoice_number",
            "customer",
            "customer_name",
            "invoice_date",
            "due_date",
            "status",
            "status_display",
            "tags",
            "tag_details",
            "lines",
            "payments",
            "payment_count",
            "amount_untaxed",
            "amount_tax",
            "amount_total",
            "amount_paid",
            "amount_due",
            "created_at",
            "updated_at",
            # Legacy order fields
            "order_id",
            "order_number",
            "tracking_number",
            "vendor_id",
            "vendor_name",
            "freight_charge",
            "tax_amount",
            "cod_amount",
            "total_amount",
        ]
        read_only_fields = [
            "id",
            "number",
            "invoice_number",
            "status_display",
            "payment_count",
            "amount_paid",
            "amount_due",
            "created_at",
            "updated_at",
        ]

    def get_customer_name(self, obj):
        if obj.customer:
            return obj.customer.name
        if obj.order and obj.order.customer_name:
            return obj.order.customer_name
        return "—"

    def validate(self, attrs):
        if self.instance and self.instance.status in (InvoiceStatus.POSTED, InvoiceStatus.PAID, InvoiceStatus.ISSUED):
            # Enforce read-only when posted or paid
            modifiable_fields = {"status"}
            incoming_mods = {k for k in attrs.keys() if k not in modifiable_fields}
            if incoming_mods:
                raise serializers.ValidationError(
                    {"detail": f"Posted and paid invoices are read-only (attempted to edit {list(incoming_mods)})."}
                )
        return attrs

    def create(self, validated_data):
        lines_data = validated_data.pop("lines", [])
        tags_data = validated_data.pop("tags", [])

        # Default initial status is draft
        validated_data["status"] = InvoiceStatus.DRAFT
        request = self.context.get("request")
        if request and request.user and request.user.is_authenticated:
            validated_data["created_by"] = request.user

        invoice = Invoice.objects.create(**validated_data)
        if tags_data:
            invoice.tags.set(tags_data)

        for line_dict in lines_data:
            InvoiceLine.objects.create(invoice=invoice, **line_dict)

        if lines_data:
            compute_and_save_invoice_totals(invoice)

        return invoice

    def update(self, instance, validated_data):
        if instance.status in (InvoiceStatus.POSTED, InvoiceStatus.PAID, InvoiceStatus.ISSUED):
            raise serializers.ValidationError({"detail": "Posted or Paid invoices are read-only and cannot be modified."})

        lines_data = validated_data.pop("lines", None)
        tags_data = validated_data.pop("tags", None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if tags_data is not None:
            instance.tags.set(tags_data)

        if lines_data is not None:
            instance.lines.all().delete()
            for line_dict in lines_data:
                InvoiceLine.objects.create(invoice=instance, **line_dict)
            compute_and_save_invoice_totals(instance)

        return instance


class InvoiceDetailSerializer(InvoiceSerializer):
    """Full detail representation including order info and delivery logs."""

    order = serializers.SerializerMethodField()
    vendor = serializers.SerializerMethodField()
    created_by_name = serializers.SerializerMethodField()
    send_logs = InvoiceSendLogSerializer(many=True, read_only=True)

    class Meta(InvoiceSerializer.Meta):
        fields = InvoiceSerializer.Meta.fields + ["order", "vendor", "created_by_name", "send_logs"]
        read_only_fields = fields

    def get_order(self, obj):
        o = obj.order
        if not o:
            return None
        v = getattr(o, "vendor", None)
        return {
            "id": o.id,
            "order_number": o.order_number,
            "tracking_number": o.tracking_number,
            "status": o.status,
            "customer_name": o.customer_name,
            "customer_phone": o.customer_phone,
            "customer_email": o.customer_email,
            "delivery_address": o.delivery_address,
            "origin_city": o.origin_city,
            "destination_city": o.destination_city,
            "commodity": o.commodity,
            "weight_kg": o.weight_kg,
            "is_cod": o.is_cod,
            "payment_type": "cash_on_delivery" if o.is_cod else "prepaid",
            "vendor": {
                "id": v.id,
                "name": v.name,
                "phone": v.contact_phone,
                "contact_phone": v.contact_phone,
                "address": v.address,
            } if v else None,
        }

    def get_vendor(self, obj):
        if not obj.order or not getattr(obj.order, "vendor", None):
            return None
        v = obj.order.vendor
        return {
            "id": v.id,
            "name": v.name,
            "phone": v.contact_phone,
            "contact_phone": v.contact_phone,
            "address": v.address,
        }

    def get_created_by_name(self, obj):
        return (obj.created_by.full_name if obj.created_by_id else "") or ""
