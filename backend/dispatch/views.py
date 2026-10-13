from django.shortcuts import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import DispatchPermission
from fleet.models import Driver
from orders.models import MILESTONE_DOCUMENTS, Order, OrderEvent, OrderStatus
from orders.serializers import OrderSerializer
from .route_optimizer import find_nearest_available_driver


class AssignNearestDriverView(APIView):
    """
    POST /dispatch/orders/{id}/assign — admin / dispatcher only.

    Finds the nearest available driver to the delivery address and assigns
    them for last-mile delivery.
    """

    permission_classes = [IsAuthenticated, DispatchPermission]

    def post(self, request, order_id):
        order = get_object_or_404(Order, id=order_id)

        if order.status not in (OrderStatus.ROUTE_PLANNED, OrderStatus.AT_DESTINATION_HUB):
            return Response(
                {"detail": "Order must have reached the destination hub / route planning stage before driver assignment"},
                status=409,
            )
        if order.delivery_lat is None or order.delivery_lng is None:
            return Response({"detail": "Order has no delivery coordinates"}, status=400)

        drivers = list(Driver.objects.filter(is_available=True))
        nearest = find_nearest_available_driver(drivers, order.delivery_lat, order.delivery_lng)
        if not nearest:
            return Response({"detail": "No available drivers right now"}, status=409)

        if order.status == OrderStatus.AT_DESTINATION_HUB:
            OrderEvent.objects.create(
                order=order,
                status=OrderStatus.ROUTE_PLANNED,
                document_name=MILESTONE_DOCUMENTS[OrderStatus.ROUTE_PLANNED],
                remarks=f"Assigned to driver #{nearest.id}",
            )
            order.status = OrderStatus.ROUTE_PLANNED

        order.driver = nearest
        nearest.is_available = False
        nearest.save()

        OrderEvent.objects.create(
            order=order,
            status=OrderStatus.OUT_FOR_DELIVERY,
            document_name=MILESTONE_DOCUMENTS[OrderStatus.OUT_FOR_DELIVERY],
            remarks=f"Loaded onto driver #{nearest.id}'s vehicle",
        )
        order.status = OrderStatus.OUT_FOR_DELIVERY
        order.save()

        # Fire out-for-delivery notification
        try:
            from notifications.tasks import send_order_notification
            send_order_notification.delay(order.pk, OrderStatus.OUT_FOR_DELIVERY)
        except Exception:
            pass

        return Response(OrderSerializer(order).data)
