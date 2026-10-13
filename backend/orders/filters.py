"""Order filtering, searching and ordering helpers."""
import django_filters
from rest_framework.filters import OrderingFilter

from .models import Order, OrderStatus


class OrderFilter(django_filters.FilterSet):
    """
    Supported query params:
      customer_name     — case-insensitive contains
      customer_phone    — case-insensitive contains
      tracking_number   — case-insensitive contains
      status            — exact match (OrderStatus choice)
      created_after     — date >= (YYYY-MM-DD)
      created_before    — date <= (YYYY-MM-DD)
      is_cod            — true/false
      vendor            — vendor id (exact)
      driver            — driver id (exact)

    Invalid values produce 400 instead of 500 or silent ignore.
    """

    customer_name = django_filters.CharFilter(lookup_expr="icontains")
    customer_phone = django_filters.CharFilter(lookup_expr="icontains")
    tracking_number = django_filters.CharFilter(lookup_expr="icontains")
    order_number = django_filters.CharFilter(lookup_expr="icontains")
    status = django_filters.ChoiceFilter(choices=OrderStatus.choices)
    created_after = django_filters.DateFilter(field_name="created_at", lookup_expr="date__gte")
    created_before = django_filters.DateFilter(field_name="created_at", lookup_expr="date__lte")
    is_cod = django_filters.BooleanFilter()
    vendor = django_filters.NumberFilter(field_name="vendor_id")
    driver = django_filters.NumberFilter(field_name="driver_id")

    class Meta:
        model = Order
        fields: list[str] = []


class OrderOrderingFilter(OrderingFilter):
    """Sort via ?ordering=-created_at or ?sort_by=created_at&order=desc.

    A stable ``id`` tie-breaker is always appended so pages never overlap.
    """

    def get_ordering(self, request, queryset, view):
        ordering = None
        sort_by = request.query_params.get("sort_by")
        if sort_by:
            direction = request.query_params.get("order", "asc").strip().lower()
            if direction in ("asc", "desc"):
                prefix = "-" if direction == "desc" else ""
                requested = [prefix + f.strip() for f in sort_by.split(",") if f.strip()]
                ordering = self.remove_invalid_fields(queryset, requested, view, request) or None
        if ordering is None:
            ordering = super().get_ordering(request, queryset, view)
        ordering = list(ordering or ["-created_at"])
        if not any(f.lstrip("-") == "id" for f in ordering):
            ordering.append("-id" if ordering and ordering[0].startswith("-") else "id")
        return ordering
