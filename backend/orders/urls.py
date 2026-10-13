from django.urls import path
from notifications.views import OrderNotificationListView
from .views import (
    OrderAdvanceView,
    OrderBookView,
    OrderCloseBillingView,
    OrderDeliveryAttemptView,
    OrderDetailView,
    OrderInvoicePdfView,
    OrderListCreateView,
    OrderReattemptView,
    OrderRtoView,
    OrderTrackView,
)

urlpatterns = [
    path("", OrderListCreateView.as_view(), name="order-list"),
    path("track/<str:tracking_number>", OrderTrackView.as_view(), name="order-track"),
    path("<int:order_id>", OrderDetailView.as_view(), name="order-detail"),
    path("<int:order_id>/notifications", OrderNotificationListView.as_view(), name="order-notifications"),
    path("<int:order_id>/book", OrderBookView.as_view(), name="order-book"),
    path("<int:order_id>/advance", OrderAdvanceView.as_view(), name="order-advance"),
    path("<int:order_id>/delivery-attempt", OrderDeliveryAttemptView.as_view(), name="order-delivery-attempt"),
    path("<int:order_id>/reattempt", OrderReattemptView.as_view(), name="order-reattempt"),
    path("<int:order_id>/rto", OrderRtoView.as_view(), name="order-rto"),
    path("<int:order_id>/close-billing", OrderCloseBillingView.as_view(), name="order-close-billing"),
    path("<int:order_id>/invoice.pdf", OrderInvoicePdfView.as_view(), name="order-invoice-pdf"),
]
