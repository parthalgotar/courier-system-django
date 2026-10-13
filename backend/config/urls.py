from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path
from rest_framework.routers import SimpleRouter

from invoices.views import CustomerViewSet, JournalViewSet, PaymentViewSet, TagViewSet


def health(request):
    return JsonResponse({"status": "ok"})


standalone_router = SimpleRouter(trailing_slash=True)
standalone_router.register("journals", JournalViewSet, basename="standalone-journal")
standalone_router.register("customers", CustomerViewSet, basename="standalone-customer")
standalone_router.register("tags", TagViewSet, basename="standalone-tag")
standalone_router.register("payments", PaymentViewSet, basename="standalone-payment")

urlpatterns = [
    path("admin/", admin.site.urls),
    path("health", health),
    # v1 prefixes
    path("api/v1/auth/", include("accounts.urls")),
    path("api/v1/vendors/", include("vendors.urls")),
    path("api/v1/fleet/", include("fleet.urls")),
    path("api/v1/inventory/", include("inventory.urls")),
    path("api/v1/orders/", include("orders.urls")),
    path("api/v1/dispatch/", include("dispatch.urls")),
    path("api/v1/dashboard/", include("dashboard.urls")),
    path("api/v1/invoices/", include("invoices.urls")),
    path("api/v1/notifications/", include("notifications.urls")),
    path("api/v1/", include(standalone_router.urls)),

    # /api/ compatibility aliases
    path("api/auth/", include("accounts.urls")),
    path("api/vendors/", include("vendors.urls")),
    path("api/fleet/", include("fleet.urls")),
    path("api/inventory/", include("inventory.urls")),
    path("api/orders/", include("orders.urls")),
    path("api/dispatch/", include("dispatch.urls")),
    path("api/dashboard/", include("dashboard.urls")),
    path("api/invoices/", include("invoices.urls")),
    path("api/notifications/", include("notifications.urls")),
    path("api/", include(standalone_router.urls)),
]
