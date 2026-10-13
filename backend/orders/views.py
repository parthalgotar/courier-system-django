"""Order views with full RBAC, filtering, searching, sorting, and pagination."""
from decimal import InvalidOperation

from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter

from accounts.permissions import HasRole, InvoicePermission, OrderPermission
from config.pagination import StandardPagination
from invoices.services import create_invoice_for_order, get_invoice_for_order, queue_invoice_email, to_money
from invoices.views import pdf_response
from .filters import OrderFilter, OrderOrderingFilter
from .models import MILESTONE_DOCUMENTS, Order, OrderEvent, OrderStatus
from .serializers import (
    BookingSerializer,
    DeliveryAttemptSerializer,
    OrderCreateSerializer,
    OrderDetailSerializer,
    OrderSerializer,
    PublicOrderTrackSerializer,
)
from .services import next_happy_status

MAX_DELIVERY_ATTEMPTS = 3


def _log_event(order: Order, status_: str, remarks: str | None = None) -> Order:
    order.status = status_
    order.save()
    event = OrderEvent.objects.create(
        order=order,
        status=status_,
        document_name=MILESTONE_DOCUMENTS.get(status_, "Record"),
        remarks=remarks,
    )
    # Fire notifications asynchronously (never blocks the request)
    try:
        from notifications.tasks import send_order_notification
        send_order_notification.delay(order.pk, status_, event.pk)
    except Exception as exc:
        try:
            from notifications.models import Notification, NotificationChannel, NotificationStatus
            Notification.objects.create(
                order=order,
                event=event,
                order_status=status_,
                channel=NotificationChannel.EMAIL,
                status=NotificationStatus.FAILED,
                error_message=f"Broker queue failed: {exc}",
            )
        except Exception:
            pass
    return order


# ---------------------------------------------------------------- Create (Milestone 1) + List
class OrderListCreateView(generics.ListCreateAPIView):
    """
    GET  /api/v1/orders/   — paginated list with filters/search/sort (RBAC scoped)
    POST /api/v1/orders/   — create order (admin/dispatcher/vendor)
    """

    permission_classes = [OrderPermission]
    pagination_class = StandardPagination
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderOrderingFilter]
    filterset_class = OrderFilter
    search_fields = [
        "order_number", "tracking_number", "customer_name",
        "customer_phone", "delivery_address", "vendor__name",
    ]

    def get_serializer_class(self):
        return OrderCreateSerializer if self.request.method == "POST" else OrderSerializer

    def get_queryset(self):
        qs = Order.objects.select_related("vendor", "driver").prefetch_related("invoices").order_by("-created_at")
        user = self.request.user
        role = getattr(user, "role", None)

        if role == "vendor":
            # Vendor sees only their own orders
            qs = qs.filter(vendor__user=user)
        elif role == "driver":
            # Driver sees only their assigned orders
            linked_driver = getattr(user, "driver", None)
            if linked_driver:
                qs = qs.filter(driver=linked_driver)
            else:
                qs = qs.none()
        # admin/dispatcher see all

        return qs

    def get_permissions(self):
        if self.request.method == "POST":
            return [HasRole("admin", "dispatcher", "vendor")()]
        return [OrderPermission()]

    def create(self, request, *args, **kwargs):
        data = request.data.copy() if hasattr(request.data, "copy") else dict(request.data)
        role = getattr(request.user, "role", None)
        if role == "vendor":
            vendor = getattr(request.user, "vendor_profile", None)
            if not vendor:
                return Response(
                    {"detail": "No vendor profile linked to this user account. Contact administrator."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            data["vendor_id"] = vendor.pk

        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        order = serializer.save()
        event = OrderEvent.objects.create(
            order=order,
            status=OrderStatus.ORDER_RECEIVED,
            document_name=MILESTONE_DOCUMENTS[OrderStatus.ORDER_RECEIVED],
            remarks="Customer order captured",
        )
        # Trigger ORDER_RECEIVED notification
        try:
            from notifications.tasks import send_order_notification
            send_order_notification.delay(order.pk, OrderStatus.ORDER_RECEIVED, event.pk)
        except Exception as exc:
            try:
                from notifications.models import Notification, NotificationChannel, NotificationStatus
                Notification.objects.create(
                    order=order,
                    event=event,
                    order_status=OrderStatus.ORDER_RECEIVED,
                    channel=NotificationChannel.EMAIL,
                    status=NotificationStatus.FAILED,
                    error_message=f"Broker queue failed: {exc}",
                )
            except Exception:
                pass
        return Response(OrderDetailSerializer(order).data, status=status.HTTP_201_CREATED)


# ---------------------------------------------------------------- Read
class OrderDetailView(generics.RetrieveAPIView):
    permission_classes = [OrderPermission]
    queryset = Order.objects.select_related("vendor", "driver").prefetch_related("invoices").all()
    serializer_class = OrderDetailSerializer
    lookup_url_kwarg = "order_id"

    def get_object(self):
        obj = get_object_or_404(Order.objects.select_related("vendor", "driver").prefetch_related("invoices"), id=self.kwargs["order_id"])
        self.check_object_permissions(self.request, obj)
        return obj


class OrderTrackView(APIView):
    """Public tracking endpoint — no auth required."""
    permission_classes = [AllowAny]

    def get(self, request, tracking_number):
        order = Order.objects.filter(tracking_number=tracking_number).first()
        if not order:
            return Response({"detail": "No shipment with that tracking number"}, status=404)
        return Response(PublicOrderTrackSerializer(order).data)


# ---------------------------------------------------------------- Booking (Milestone 2)
class OrderBookView(APIView):
    permission_classes = [HasRole("admin", "dispatcher")]

    def post(self, request, order_id):
        order = get_object_or_404(Order, id=order_id)
        if order.status != OrderStatus.ORDER_RECEIVED:
            return Response({"detail": "Booking can only be planned right after order is received"}, status=409)
        serializer = BookingSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        order.pickup_date = serializer.validated_data["pickup_date"]
        order.pickup_slot = serializer.validated_data["pickup_slot"]
        order.save()
        order = _log_event(order, OrderStatus.BOOKING_PLANNED, "Pickup scheduled")
        return Response(OrderDetailSerializer(order).data)


# ---------------------------------------------------------------- Generic milestone advance
class OrderAdvanceView(APIView):
    permission_classes = [HasRole("admin", "dispatcher")]

    def post(self, request, order_id):
        order = get_object_or_404(Order, id=order_id)
        nxt = next_happy_status(order.status)
        if nxt is None:
            return Response({"detail": f"Cannot advance further from '{order.status}'"}, status=409)
        if nxt in (OrderStatus.DELIVERY_ATTEMPTED, OrderStatus.DELIVERED):
            return Response({"detail": "Use /delivery-attempt to record a delivery outcome"}, status=409)
        if nxt == OrderStatus.CLOSED:
            return Response({"detail": "Use /close-billing to close and invoice"}, status=409)
        remarks = request.query_params.get("remarks")
        order = _log_event(order, nxt, remarks)
        return Response(OrderDetailSerializer(order).data)


# ---------------------------------------------------------------- Delivery attempt (Milestone 12-13)
class OrderDeliveryAttemptView(APIView):
    permission_classes = [HasRole("admin", "dispatcher", "driver")]

    def post(self, request, order_id):
        order = get_object_or_404(Order, id=order_id)
        if order.status not in (OrderStatus.OUT_FOR_DELIVERY, OrderStatus.REATTEMPT_SCHEDULED):
            return Response({"detail": "Order must be out for delivery to log an attempt"}, status=409)

        serializer = DeliveryAttemptSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        order.delivery_attempt_count += 1
        order.save()

        if data["success"]:
            if not data.get("proof_type"):
                return Response({"detail": "proof_type is required to mark an order Delivered"}, status=422)
            order = _log_event(
                order, OrderStatus.DELIVERED,
                f"POD captured via {data['proof_type']}; recipient: {data.get('recipient_name') or 'N/A'}",
            )
            return Response(OrderDetailSerializer(order).data)

        order = _log_event(order, OrderStatus.DELIVERY_FAILED, data.get("remarks") or "Delivery attempt failed")

        if order.delivery_attempt_count >= MAX_DELIVERY_ATTEMPTS:
            order = _log_event(
                order, OrderStatus.RTO_INITIATED,
                f"Auto RTO after {order.delivery_attempt_count} failed attempts",
            )
        return Response(OrderDetailSerializer(order).data)


class OrderReattemptView(APIView):
    permission_classes = [HasRole("admin", "dispatcher")]

    def post(self, request, order_id):
        order = get_object_or_404(Order, id=order_id)
        if order.status != OrderStatus.DELIVERY_FAILED:
            return Response({"detail": "Reattempt can only be scheduled after a failed delivery"}, status=409)
        remarks = request.query_params.get("remarks")
        order = _log_event(order, OrderStatus.REATTEMPT_SCHEDULED, remarks or "Re-delivery scheduled")
        order = _log_event(order, OrderStatus.OUT_FOR_DELIVERY, "Out for delivery (reattempt)")
        return Response(OrderDetailSerializer(order).data)


class OrderRtoView(APIView):
    permission_classes = [HasRole("admin", "dispatcher")]

    def post(self, request, order_id):
        order = get_object_or_404(Order, id=order_id)
        if order.status not in (OrderStatus.DELIVERY_FAILED, OrderStatus.RTO_INITIATED):
            return Response({"detail": "RTO can only start from a failed delivery"}, status=409)
        remarks = request.query_params.get("remarks")
        order = _log_event(order, OrderStatus.RTO_INITIATED, remarks or "Customer refused / max attempts reached")
        order = _log_event(order, OrderStatus.RETURNED, "Reverse shipment created back to origin")
        return Response(OrderDetailSerializer(order).data)


# ---------------------------------------------------------------- Billing / Closure (Milestone 14)
class OrderCloseBillingView(APIView):
    """Close + bill a delivered order and create its persistent Invoice."""

    permission_classes = [HasRole("admin", "dispatcher")]

    def post(self, request, order_id):
        order = get_object_or_404(Order, id=order_id)
        if order.status != OrderStatus.DELIVERED:
            return Response({"detail": "Order must be Delivered before billing/closure"}, status=409)
        try:
            freight_charge = to_money(request.query_params.get("freight_charge"))
        except (TypeError, ValueError, InvalidOperation):
            return Response({"detail": "freight_charge query param is required"}, status=422)
        try:
            tax_amount = to_money(request.query_params.get("tax_amount") or 0)
        except (TypeError, ValueError, InvalidOperation):
            return Response({"detail": "tax_amount must be a valid number"}, status=422)
        if freight_charge < 0 or tax_amount < 0:
            return Response({"detail": "freight_charge and tax_amount cannot be negative"}, status=422)

        with transaction.atomic():
            order = Order.objects.select_for_update().get(pk=order.pk)
            if order.status != OrderStatus.DELIVERED:
                return Response({"detail": "Order must be Delivered before billing/closure"}, status=409)

            invoice, created = create_invoice_for_order(
                order, freight_charge=freight_charge, tax_amount=tax_amount, created_by=request.user
            )

            order.freight_charge = float(invoice.freight_charge)
            order.invoice_number = invoice.invoice_number
            order.invoice_amount = float(invoice.total_amount)
            order.save()
            order = _log_event(order, OrderStatus.CLOSED, f"Freight Invoice {order.invoice_number} generated")

            if created:
                queue_invoice_email(invoice)

        return Response(OrderDetailSerializer(order).data)


# ---------------------------------------------------------------- Invoice PDF download
class OrderInvoicePdfView(APIView):
    """GET /orders/{id}/invoice.pdf — backwards-compatible endpoint."""

    permission_classes = [IsAuthenticated, InvoicePermission]

    def get(self, request, order_id):
        order = get_object_or_404(Order.objects.select_related("vendor"), id=order_id)

        if not InvoicePermission.user_can_access_order(request.user, order, request.method):
            raise PermissionDenied()

        if order.status != OrderStatus.CLOSED:
            return Response({"detail": "Invoice is only available after the order is closed and billed"}, status=409)

        invoice = get_invoice_for_order(order)
        if invoice is None:
            return Response({"detail": "No invoice record exists for this order"}, status=404)
        self.check_object_permissions(request, invoice)

        return pdf_response(invoice)
