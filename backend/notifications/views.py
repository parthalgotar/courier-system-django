from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter

from config.pagination import StandardPagination
from .models import Notification
from .serializers import NotificationSerializer


class NotificationListView(generics.ListAPIView):
    """
    GET /api/v1/notifications/
    List order notifications with filtering by order, status, channel.
    Scoped by role:
      - Admin / Dispatcher: all notifications
      - Vendor: own orders only
      - Driver: own assigned orders only
    """

    serializer_class = NotificationSerializer
    pagination_class = StandardPagination
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ["order", "order_status", "channel", "status"]
    ordering = ["-created_at"]

    def get_queryset(self):
        qs = Notification.objects.select_related("order", "event").all()
        user = self.request.user
        role = getattr(user, "role", None)
        if role == "vendor":
            qs = qs.filter(order__vendor__user=user)
        elif role == "driver":
            qs = qs.filter(order__driver__user=user)
        elif role not in ("admin", "dispatcher"):
            qs = qs.none()
        return qs


class OrderNotificationListView(generics.ListAPIView):
    """
    GET /api/v1/orders/{order_id}/notifications/
    List all notifications for a specific order.
    Automatically re-evaluates notifications that were previously SKIPPED
    due to missing email if the recipient now has a saved email address.
    """

    serializer_class = NotificationSerializer
    pagination_class = StandardPagination
    permission_classes = [IsAuthenticated]

    def _auto_retry_skipped_notifications(self, order_id):
        from orders.models import Order
        from .models import NotificationChannel, NotificationStatus
        from .tasks import send_order_notification, _get_recipients

        try:
            order = Order.objects.select_related("vendor", "vendor__user", "driver").filter(pk=order_id).first()
            if not order:
                return

            skipped_list = Notification.objects.filter(
                order=order,
                status=NotificationStatus.SKIPPED,
            )
            for sn in skipped_list:
                info = _get_recipients(order, sn.recipient_type)
                # If it was skipped for email and we now have an email, retry
                if sn.channel == NotificationChannel.EMAIL and info.get("email"):
                    try:
                        send_order_notification.apply(
                            args=[order.pk, sn.order_status, sn.event_id],
                            kwargs={"force_retry": True},
                        )
                    except Exception:
                        pass
        except Exception:
            pass

    def get_queryset(self):
        order_id = self.kwargs.get("order_id")
        self._auto_retry_skipped_notifications(order_id)
        qs = Notification.objects.select_related("order", "event").filter(order_id=order_id)
        user = self.request.user
        role = getattr(user, "role", None)
        if role == "vendor":
            qs = qs.filter(order__vendor__user=user)
        elif role == "driver":
            qs = qs.filter(order__driver__user=user)
        elif role not in ("admin", "dispatcher"):
            qs = qs.none()
        return qs


class NotificationRetryView(generics.GenericAPIView):
    """
    POST /api/v1/notifications/{id}/retry/
    Admin / Dispatcher: manually re-trigger or retry a notification.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, pk=None):
        from django.shortcuts import get_object_or_404
        from rest_framework import status
        from rest_framework.response import Response
        from .tasks import send_order_notification

        if getattr(request.user, "role", None) not in ("admin", "dispatcher"):
            return Response({"detail": "Only staff can retry notifications."}, status=status.HTTP_403_FORBIDDEN)

        notif = get_object_or_404(Notification.objects.select_related("order"), pk=pk)
        try:
            send_order_notification.apply(
                args=[notif.order_id, notif.order_status, notif.event_id],
                kwargs={"force_retry": True},
            )
        except Exception:
            pass

        notif.refresh_from_db()
        return Response(NotificationSerializer(notif).data)
