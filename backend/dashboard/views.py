from django.db.models import Count, Sum
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import DashboardPermission
from orders.models import Order, OrderStatus
from .dashboard_services import get_dashboard_summary

TERMINAL_DELIVERED = {OrderStatus.DELIVERED, OrderStatus.CLOSED}
TERMINAL_RETURNED = {OrderStatus.RTO_INITIATED, OrderStatus.RETURNED}
IN_TRANSIT = {
    OrderStatus.BOOKING_PLANNED, OrderStatus.PICKUP_COMPLETED, OrderStatus.LABEL_VERIFIED,
    OrderStatus.MANIFEST_CREATED, OrderStatus.AT_ORIGIN_HUB, OrderStatus.SORTED_AT_ORIGIN,
    OrderStatus.DISPATCHED_LINEHAUL, OrderStatus.AT_DESTINATION_HUB, OrderStatus.ROUTE_PLANNED,
    OrderStatus.OUT_FOR_DELIVERY, OrderStatus.REATTEMPT_SCHEDULED,
}

PHASE_MAP = {
    OrderStatus.ORDER_RECEIVED: "First Mile",
    OrderStatus.BOOKING_PLANNED: "First Mile",
    OrderStatus.PICKUP_COMPLETED: "First Mile",
    OrderStatus.LABEL_VERIFIED: "First Mile",
    OrderStatus.MANIFEST_CREATED: "First Mile",
    OrderStatus.AT_ORIGIN_HUB: "First Mile",
    OrderStatus.SORTED_AT_ORIGIN: "Linehaul",
    OrderStatus.DISPATCHED_LINEHAUL: "Linehaul",
    OrderStatus.AT_DESTINATION_HUB: "Linehaul",
    OrderStatus.ROUTE_PLANNED: "Linehaul",
    OrderStatus.OUT_FOR_DELIVERY: "Last Mile",
    OrderStatus.DELIVERY_ATTEMPTED: "Last Mile",
    OrderStatus.DELIVERED: "Last Mile",
    OrderStatus.CLOSED: "Closed",
    OrderStatus.DELIVERY_FAILED: "Exception",
    OrderStatus.REATTEMPT_SCHEDULED: "Exception",
    OrderStatus.RTO_INITIATED: "Exception",
    OrderStatus.RETURNED: "Exception",
    OrderStatus.CANCELLED: "Exception",
}


class DashboardSummaryView(APIView):
    """GET /api/dashboard/summary/ and /api/v1/dashboard/summary/
    Returns full accounting summary: top_cards, sales, cash, bank,
    recent_payments, top_customers, and status_breakdown.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        date_from = request.query_params.get("date_from")
        date_to = request.query_params.get("date_to")
        customer = request.query_params.get("customer")
        journal = request.query_params.get("journal")
        data = get_dashboard_summary(
            date_from=date_from,
            date_to=date_to,
            customer=customer,
            journal=journal,
        )
        return Response(data)


class DashboardStatsView(APIView):
    """Admin / Dispatcher: stats for ALL orders.
    Vendor: stats scoped to their own orders only.
    Driver: stats scoped to their own assigned orders only.
    Anonymous: 401.
    """

    permission_classes = [IsAuthenticated, DashboardPermission]

    def get(self, request):
        qs = Order.objects.all()

        role = getattr(request.user, "role", None)
        if role == "vendor":
            qs = qs.filter(vendor__user=request.user)
        elif role == "driver":
            qs = qs.filter(driver__user=request.user)

        total = qs.count()
        in_transit = qs.filter(status__in=IN_TRANSIT).count()
        delivered = qs.filter(status__in=TERMINAL_DELIVERED).count()
        failed = qs.filter(status=OrderStatus.DELIVERY_FAILED).count()
        rto = qs.filter(status__in=TERMINAL_RETURNED).count()

        cod_collected = qs.filter(is_cod=True, status=OrderStatus.CLOSED).aggregate(s=Sum("cod_amount"))["s"] or 0.0
        cod_pending = qs.filter(is_cod=True).exclude(status=OrderStatus.CLOSED).aggregate(s=Sum("cod_amount"))["s"] or 0.0

        status_counts = qs.values("status").annotate(c=Count("id"))
        status_breakdown: dict[str, int] = {row["status"]: row["c"] for row in status_counts}

        phase_breakdown = {"First Mile": 0, "Linehaul": 0, "Last Mile": 0, "Closed": 0, "Exception": 0}
        for st, c in status_breakdown.items():
            phase_breakdown[PHASE_MAP.get(st, "First Mile")] = phase_breakdown.get(PHASE_MAP.get(st, "First Mile"), 0) + c

        return Response({
            "total_orders": total,
            "in_transit": in_transit,
            "delivered": delivered,
            "delivery_failed": failed,
            "rto": rto,
            "cod_pending": round(cod_pending, 2),
            "cod_collected": round(cod_collected, 2),
            "status_breakdown": status_breakdown,
            "phase_breakdown": phase_breakdown,
        })
