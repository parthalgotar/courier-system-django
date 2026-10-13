import django_filters
from django.db.models import Q
from django.utils import timezone
from rest_framework.filters import OrderingFilter

from .models import Invoice, InvoiceStatus, Payment, PaymentStatus


class InvoiceFilter(django_filters.FilterSet):
    """Filters for /api/invoices/ and /api/invoices/grouped/.
    Supports: status, customer, date range, unpaid (amount_due > 0),
    overdue (due_date < today and status = posted), tags, search by number.
    """

    status = django_filters.ChoiceFilter(choices=InvoiceStatus.choices)
    customer = django_filters.NumberFilter(field_name="customer_id")
    customer_name = django_filters.CharFilter(method="filter_customer_name")

    # Date range filters
    date_from = django_filters.DateFilter(field_name="invoice_date", lookup_expr="gte")
    date_to = django_filters.DateFilter(field_name="invoice_date", lookup_expr="lte")
    created_after = django_filters.DateFilter(field_name="invoice_date", lookup_expr="gte")
    created_before = django_filters.DateFilter(field_name="invoice_date", lookup_expr="lte")

    # Custom flags
    unpaid = django_filters.BooleanFilter(method="filter_unpaid")
    overdue = django_filters.BooleanFilter(method="filter_overdue")

    tags = django_filters.CharFilter(method="filter_tags")
    journal = django_filters.CharFilter(method="filter_journal")
    search = django_filters.CharFilter(method="filter_search")

    # Legacy order filters
    invoice_number = django_filters.CharFilter(method="filter_invoice_number")
    order_id = django_filters.NumberFilter(field_name="order_id")
    order_number = django_filters.CharFilter(field_name="order__order_number", lookup_expr="icontains")
    tracking_number = django_filters.CharFilter(field_name="order__tracking_number", lookup_expr="icontains")
    vendor = django_filters.NumberFilter(field_name="order__vendor_id")
    min_total = django_filters.NumberFilter(field_name="amount_total", lookup_expr="gte")
    max_total = django_filters.NumberFilter(field_name="amount_total", lookup_expr="lte")

    class Meta:
        model = Invoice
        fields: list[str] = []

    def filter_unpaid(self, queryset, name, value):
        if value:
            return queryset.filter(amount_due__gt=0)
        return queryset

    def filter_overdue(self, queryset, name, value):
        if value:
            today = timezone.now().date()
            return queryset.filter(due_date__lt=today, status__in=[InvoiceStatus.POSTED, "issued"])
        return queryset

    def filter_customer_name(self, queryset, name, value):
        if not value:
            return queryset
        return queryset.filter(
            Q(customer__name__icontains=value) | Q(order__customer_name__icontains=value)
        )

    def filter_tags(self, queryset, name, value):
        if not value:
            return queryset
        if value.isdigit():
            return queryset.filter(tags__id=int(value))
        return queryset.filter(tags__name__icontains=value)

    def filter_journal(self, queryset, name, value):
        if not value:
            return queryset
        if value.isdigit():
            return queryset.filter(payments__journal_id=int(value))
        return queryset.filter(
            Q(payments__journal__name__icontains=value) | Q(payments__journal__type__iexact=value)
        )

    def filter_invoice_number(self, queryset, name, value):
        if not value:
            return queryset
        return queryset.filter(Q(number__icontains=value) | Q(invoice_number__icontains=value))

    def filter_search(self, queryset, name, value):
        if not value:
            return queryset
        val = value.strip()
        return queryset.filter(
            Q(number__icontains=val)
            | Q(invoice_number__icontains=val)
            | Q(customer__name__icontains=val)
            | Q(order__order_number__icontains=val)
            | Q(order__tracking_number__icontains=val)
            | Q(order__customer_name__icontains=val)
            | Q(order__vendor__name__icontains=val)
        ).distinct()


class PaymentFilter(django_filters.FilterSet):
    """Filters for payments list: journal, date range, customer, status, search."""

    journal = django_filters.CharFilter(method="filter_journal")
    customer = django_filters.CharFilter(method="filter_customer")
    status = django_filters.ChoiceFilter(choices=PaymentStatus.choices)
    date_from = django_filters.DateFilter(field_name="payment_date", lookup_expr="gte")
    date_to = django_filters.DateFilter(field_name="payment_date", lookup_expr="lte")
    search = django_filters.CharFilter(method="filter_search")

    class Meta:
        model = Payment
        fields: list[str] = []

    def filter_journal(self, queryset, name, value):
        if not value:
            return queryset
        if value.isdigit():
            return queryset.filter(journal_id=int(value))
        return queryset.filter(
            Q(journal__name__icontains=value) | Q(journal__type__iexact=value)
        )

    def filter_customer(self, queryset, name, value):
        if not value:
            return queryset
        if value.isdigit():
            return queryset.filter(
                Q(invoice__customer_id=int(value)) | Q(invoice__order__customer_name__icontains=value)
            )
        return queryset.filter(
            Q(invoice__customer__name__icontains=value) | Q(invoice__order__customer_name__icontains=value)
        )

    def filter_search(self, queryset, name, value):
        if not value:
            return queryset
        val = value.strip()
        return queryset.filter(
            Q(payment_number__icontains=val)
            | Q(memo__icontains=val)
            | Q(invoice__number__icontains=val)
            | Q(invoice__invoice_number__icontains=val)
            | Q(invoice__customer__name__icontains=val)
        ).distinct()


class InvoiceOrderingFilter(OrderingFilter):
    """Sorting via either DRF's standard ?ordering=-amount_total or ?sort_by=amount_total&order=desc."""

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
        ordering = list(ordering or [])
        if not any(f.lstrip("-") == "id" for f in ordering):
            ordering.append("-id" if ordering and ordering[0].startswith("-") else "id")
        return ordering
