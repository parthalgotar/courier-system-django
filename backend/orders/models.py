import datetime
import uuid

from django.db import models


def _tracking_number():
    return uuid.uuid4().hex[:10].upper()


def _order_number():
    return f"ORD-{uuid.uuid4().hex[:8].upper()}"


class OrderStatus(models.TextChoices):
    # Phase 1 - First Mile
    ORDER_RECEIVED = "order_received", "Order Received"
    BOOKING_PLANNED = "booking_planned", "Booking Planned"
    PICKUP_COMPLETED = "pickup_completed", "Pickup Completed"
    LABEL_VERIFIED = "label_verified", "Label Verified"
    MANIFEST_CREATED = "manifest_created", "Manifest Created"
    AT_ORIGIN_HUB = "at_origin_hub", "At Origin Hub"
    # Phase 2 - Middle Mile / Linehaul
    SORTED_AT_ORIGIN = "sorted_at_origin", "Sorted at Origin"
    DISPATCHED_LINEHAUL = "dispatched_linehaul", "Dispatched (Linehaul)"
    AT_DESTINATION_HUB = "at_destination_hub", "At Destination Hub"
    ROUTE_PLANNED = "route_planned", "Route Planned"
    # Phase 3 - Last Mile
    OUT_FOR_DELIVERY = "out_for_delivery", "Out for Delivery"
    DELIVERY_ATTEMPTED = "delivery_attempted", "Delivery Attempted"
    DELIVERED = "delivered", "Delivered"
    CLOSED = "closed", "Closed / Billed"
    # Exception branch
    DELIVERY_FAILED = "delivery_failed", "Delivery Failed"
    REATTEMPT_SCHEDULED = "reattempt_scheduled", "Reattempt Scheduled"
    RTO_INITIATED = "rto_initiated", "RTO Initiated"
    RETURNED = "returned", "Returned"
    CANCELLED = "cancelled", "Cancelled"


# Ordered milestone list — validates "next step" transitions. FRD Business
# Rule: "A shipment cannot move to the next milestone unless the current
# milestone's document/record is generated."
HAPPY_PATH_ORDER = [
    OrderStatus.ORDER_RECEIVED,
    OrderStatus.BOOKING_PLANNED,
    OrderStatus.PICKUP_COMPLETED,
    OrderStatus.LABEL_VERIFIED,
    OrderStatus.MANIFEST_CREATED,
    OrderStatus.AT_ORIGIN_HUB,
    OrderStatus.SORTED_AT_ORIGIN,
    OrderStatus.DISPATCHED_LINEHAUL,
    OrderStatus.AT_DESTINATION_HUB,
    OrderStatus.ROUTE_PLANNED,
    OrderStatus.OUT_FOR_DELIVERY,
    OrderStatus.DELIVERY_ATTEMPTED,
    OrderStatus.DELIVERED,
    OrderStatus.CLOSED,
]

# Document generated at each milestone (FRD Section 7 - Core Document Backbone)
MILESTONE_DOCUMENTS = {
    OrderStatus.ORDER_RECEIVED: "Customer Order / Shipping Request",
    OrderStatus.BOOKING_PLANNED: "Booking Confirmation",
    OrderStatus.PICKUP_COMPLETED: "Pickup Acknowledgement",
    OrderStatus.LABEL_VERIFIED: "Shipping Label / Barcode Verification",
    OrderStatus.MANIFEST_CREATED: "Consignment Note / LR / Waybill",
    OrderStatus.AT_ORIGIN_HUB: "Inbound Scan / Goods Receipt Record",
    OrderStatus.SORTED_AT_ORIGIN: "Sorting Sheet / Load Planning Sheet",
    OrderStatus.DISPATCHED_LINEHAUL: "Manifest / Trip Sheet",
    OrderStatus.AT_DESTINATION_HUB: "Arrival Confirmation / Inbound Manifest",
    OrderStatus.ROUTE_PLANNED: "Delivery Run Sheet / Delivery Manifest",
    OrderStatus.OUT_FOR_DELIVERY: "Delivery Dispatch Record",
    OrderStatus.DELIVERY_ATTEMPTED: "Delivery Attempt Record",
    OrderStatus.DELIVERED: "Proof of Delivery (POD)",
    OrderStatus.CLOSED: "Freight Invoice / Shipment Closure Record",
    OrderStatus.DELIVERY_FAILED: "Non-Delivery Report (NDR)",
    OrderStatus.REATTEMPT_SCHEDULED: "Reattempt Instruction",
    OrderStatus.RTO_INITIATED: "RTO / Return Shipment Note",
    OrderStatus.RETURNED: "Shipment Closure Record",
    OrderStatus.CANCELLED: "Cancellation Record",
}


class Order(models.Model):
    order_number = models.CharField(max_length=50, unique=True, db_index=True, default=_order_number)
    tracking_number = models.CharField(max_length=20, unique=True, db_index=True, default=_tracking_number)

    vendor = models.ForeignKey("vendors.Vendor", on_delete=models.PROTECT, related_name="orders")
    customer_name = models.CharField(max_length=255)
    customer_phone = models.CharField(max_length=30)
    customer_email = models.EmailField(null=True, blank=True, default="")
    delivery_address = models.CharField(max_length=500)
    delivery_lat = models.FloatField(null=True, blank=True)
    delivery_lng = models.FloatField(null=True, blank=True)

    origin_city = models.CharField(max_length=120, blank=True, default="")
    destination_city = models.CharField(max_length=120, blank=True, default="")
    commodity = models.CharField(max_length=255, default="General Cargo")
    weight_kg = models.FloatField(default=0.0)
    declared_value = models.FloatField(default=0.0)
    is_cod = models.BooleanField(default=False)
    cod_amount = models.FloatField(default=0.0)

    status = models.CharField(
        max_length=25, choices=OrderStatus.choices, default=OrderStatus.ORDER_RECEIVED, db_index=True
    )

    pickup_date = models.CharField(max_length=20, null=True, blank=True)
    pickup_slot = models.CharField(max_length=20, null=True, blank=True)

    # Business order date (editable). Separate from created_at which is the system record timestamp.
    order_date = models.DateField(default=datetime.date.today, db_index=True)

    driver = models.ForeignKey("fleet.Driver", on_delete=models.SET_NULL, null=True, blank=True, related_name="orders")

    delivery_attempt_count = models.IntegerField(default=0)

    freight_charge = models.FloatField(default=0.0)
    invoice_number = models.CharField(max_length=50, null=True, blank=True)
    invoice_amount = models.FloatField(default=0.0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.order_number


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    sku = models.CharField(max_length=100)
    quantity = models.IntegerField(default=1)


class OrderEvent(models.Model):
    """One row per milestone / document generated — FRD document backbone +
    audit trail, in one table."""

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="events")
    status = models.CharField(max_length=25, choices=OrderStatus.choices)
    document_name = models.CharField(max_length=150)
    remarks = models.CharField(max_length=500, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["id"]
