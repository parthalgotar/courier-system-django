from django.core.exceptions import ValidationError
from django.core.validators import EmailValidator
from django.db.models import Count, Sum
from django.db.models.functions import Coalesce, TruncMonth
from django.http import HttpResponse
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.filters import SearchFilter
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounts.permissions import InvoicePermission
from config.pagination import StandardPagination
from orders.invoice_pdf import build_invoice_pdf
from .filters import InvoiceFilter, InvoiceOrderingFilter, PaymentFilter
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
from .serializers import (
    CustomerSerializer,
    InvoiceDetailSerializer,
    InvoiceSendLogCreateSerializer,
    InvoiceSendLogSerializer,
    InvoiceSerializer,
    JournalSerializer,
    PayInvoiceSerializer,
    PaymentSerializer,
    TagSerializer,
)
from .services import (
    confirm_invoice,
    create_invoice_payment,
    get_grouped_invoices_tree,
    queue_invoice_email,
    reset_invoice_to_draft,
)


def pdf_response(invoice: Invoice, *, download: bool = False) -> HttpResponse:
    """Render the stored invoice as a PDF HTTP response."""
    response = HttpResponse(build_invoice_pdf(invoice), content_type="application/pdf")
    disposition = "attachment" if download else "inline"
    filename = invoice.number or invoice.invoice_number or f"invoice_{invoice.id}"
    response["Content-Disposition"] = f'{disposition}; filename="{filename}.pdf"'
    return response


# Status transition rules for update-status action
ALLOWED_TRANSITIONS = {
    InvoiceStatus.DRAFT:      [InvoiceStatus.POSTED, InvoiceStatus.ISSUED, InvoiceStatus.CANCELLED],
    InvoiceStatus.POSTED:     [InvoiceStatus.PAID, InvoiceStatus.DRAFT, InvoiceStatus.CANCELLED],
    InvoiceStatus.ISSUED:     [InvoiceStatus.PAID, InvoiceStatus.DRAFT, InvoiceStatus.CANCELLED],
    InvoiceStatus.PAID:       [InvoiceStatus.CANCELLED],
    InvoiceStatus.CANCELLED:  [],
}


class InvoiceStatusUpdateSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=InvoiceStatus.choices)


class CustomerViewSet(viewsets.ModelViewSet):
    """API for managing customers: /api/v1/invoices/customers/ and /api/customers/."""
    permission_classes = [IsAuthenticated]
    queryset = Customer.objects.all().order_by("name")
    serializer_class = CustomerSerializer
    pagination_class = None
    filter_backends = [SearchFilter]
    search_fields = ["name", "email", "phone"]


class TagViewSet(viewsets.ModelViewSet):
    """API for managing tags: /api/v1/invoices/tags/ and /api/tags/."""
    permission_classes = [IsAuthenticated]
    queryset = Tag.objects.all().order_by("name")
    serializer_class = TagSerializer
    pagination_class = None
    filter_backends = [SearchFilter]
    search_fields = ["name"]


class JournalViewSet(viewsets.ModelViewSet):
    """API for journals (Cash / Bank): /api/v1/invoices/journals/ and /api/journals/."""
    permission_classes = [IsAuthenticated]
    queryset = Journal.objects.all().order_by("name")
    serializer_class = JournalSerializer
    pagination_class = None
    filter_backends = [SearchFilter]
    search_fields = ["name", "type"]


class PaymentViewSet(viewsets.ReadOnlyModelViewSet):
    """API for listing and grouping payments: /api/v1/invoices/payments/."""
    permission_classes = [IsAuthenticated]
    queryset = Payment.objects.select_related("invoice", "invoice__customer", "invoice__order", "journal").order_by("-payment_date", "-id")
    serializer_class = PaymentSerializer
    pagination_class = StandardPagination
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_class = PaymentFilter
    search_fields = ["payment_number", "memo", "invoice__number", "invoice__invoice_number"]

    @action(detail=False, methods=["get"], url_path="grouped")
    def grouped(self, request):
        """Group payments by journal, date (month), or customer."""
        qs = self.filter_queryset(self.get_queryset())
        group_by = request.query_params.get("group_by", "journal,month").strip()
        fields = [f.strip().lower() for f in group_by.split(",") if f.strip()][:3]

        def _group_payments(sub_qs, f_list):
            if not f_list:
                return [PaymentSerializer(p).data for p in sub_qs[:50]]
            cur = f_list[0]
            rest = f_list[1:]

            if cur in ("journal", "journal_type"):
                groups = (
                    sub_qs.values("journal__id", "journal__name", "journal__type")
                    .annotate(
                        count=Count("id", distinct=True),
                        total=Coalesce(Sum("amount"), 0.0),
                    )
                    .order_by("journal__name")
                )
                res = []
                for g in groups:
                    j_id = g["journal__id"]
                    j_name = g["journal__name"] or "No Journal"
                    nxt = sub_qs.filter(journal_id=j_id)
                    res.append({
                        "key": j_name,
                        "field": "journal",
                        "count": g["count"],
                        "total": float(g["total"]),
                        "children": _group_payments(nxt, rest),
                    })
                return res

            elif cur in ("month", "date"):
                groups = (
                    sub_qs.annotate(m=TruncMonth("payment_date"))
                    .values("m")
                    .annotate(
                        count=Count("id", distinct=True),
                        total=Coalesce(Sum("amount"), 0.0),
                    )
                    .order_by("-m")
                )
                res = []
                for g in groups:
                    m_val = g["m"]
                    m_str = m_val.strftime("%Y-%m") if m_val else "No Date"
                    nxt = sub_qs.filter(payment_date__year=m_val.year, payment_date__month=m_val.month) if m_val else sub_qs.filter(payment_date__isnull=True)
                    res.append({
                        "key": m_str,
                        "field": "month",
                        "count": g["count"],
                        "total": float(g["total"]),
                        "children": _group_payments(nxt, rest),
                    })
                return res

            elif cur == "customer":
                groups = (
                    sub_qs.values("invoice__customer__id", "invoice__customer__name")
                    .annotate(
                        count=Count("id", distinct=True),
                        total=Coalesce(Sum("amount"), 0.0),
                    )
                    .order_by("-total")
                )
                res = []
                for g in groups:
                    c_id = g["invoice__customer__id"]
                    c_name = g["invoice__customer__name"] or "No Customer"
                    nxt = sub_qs.filter(invoice__customer_id=c_id) if c_id else sub_qs.filter(invoice__customer__isnull=True)
                    res.append({
                        "key": c_name,
                        "field": "customer",
                        "count": g["count"],
                        "total": float(g["total"]),
                        "children": _group_payments(nxt, rest),
                    })
                return res

            return []

        tree = _group_payments(qs, fields)
        return Response(tree)


class InvoiceViewSet(
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.ReadOnlyModelViewSet,
):
    """Complete Invoice Management ViewSet:
    - Normal list: GET /api/v1/invoices/ (supports pagination, filtering, search, sorting)
    - Grouped list: GET /api/v1/invoices/grouped/?group_by=customer,status,month
    - Confirm: POST /api/v1/invoices/{id}/confirm/
    - Reset to Draft: POST /api/v1/invoices/{id}/reset-to-draft/
    - Pay: POST /api/v1/invoices/{id}/pay/
    - PDF: GET /api/v1/invoices/{id}/pdf/
    - Send email: POST /api/v1/invoices/{id}/send-email/
    - Send logs: GET /api/v1/invoices/{id}/send-logs/
    """

    permission_classes = [IsAuthenticated, InvoicePermission]
    pagination_class = StandardPagination
    filter_backends = [DjangoFilterBackend, SearchFilter, InvoiceOrderingFilter]
    filterset_class = InvoiceFilter
    search_fields = [
        "number",
        "invoice_number",
        "customer__name",
        "order__order_number",
        "order__tracking_number",
        "order__customer_name",
        "order__vendor__name",
    ]
    ordering_fields = [
        "invoice_date",
        "created_at",
        "amount_total",
        "total_amount",
        "freight_charge",
        "number",
        "invoice_number",
        "status",
    ]
    ordering = ["-created_at"]

    def get_serializer_class(self):
        return InvoiceSerializer if self.action == "list" else InvoiceDetailSerializer

    def get_queryset(self):
        qs = Invoice.objects.select_related(
            "customer", "order", "order__vendor", "order__driver", "order__driver__user", "created_by"
        ).prefetch_related(
            "tags", "lines", "payments", "payments__journal"
        )
        role = getattr(self.request.user, "role", None)
        if self.action == "list":
            if role == "vendor":
                qs = qs.filter(order__vendor__user=self.request.user)
            elif role not in ("admin", "dispatcher") and not getattr(self.request.user, "is_superuser", False):
                qs = qs.none()
        else:
            qs = qs.prefetch_related("send_logs")
        return qs

    def create(self, request, *args, **kwargs):
        role = getattr(request.user, "role", None)
        if role == "dispatcher":
            return Response(
                {"detail": 'Method "POST" not allowed.'},
                status=status.HTTP_405_METHOD_NOT_ALLOWED,
            )
        serializer = InvoiceSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        invoice = serializer.save()
        return Response(InvoiceDetailSerializer(invoice, context={"request": request}).data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        invoice = self.get_object()
        if invoice.status in (InvoiceStatus.POSTED, InvoiceStatus.PAID, InvoiceStatus.ISSUED):
            return Response(
                {"detail": "Posted or Paid invoices are read-only and cannot be modified."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        serializer = InvoiceSerializer(invoice, data=request.data, partial=True, context={"request": request})
        serializer.is_valid(raise_exception=True)
        updated = serializer.save()
        return Response(InvoiceDetailSerializer(updated, context={"request": request}).data)

    def destroy(self, request, *args, **kwargs):
        invoice = self.get_object()
        if invoice.status == InvoiceStatus.PAID:
            return Response(
                {"detail": "A Paid invoice cannot be deleted."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        order = invoice.order
        if order and order.status == "closed":
            return Response(
                {"detail": "Cannot delete an invoice for a closed/billed order."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if order and order.invoice_number in (invoice.invoice_number, invoice.number):
            order.invoice_number = ""
            order.invoice_amount = 0.0
            order.save(update_fields=["invoice_number", "invoice_amount"])
        return super().destroy(request, *args, **kwargs)

    # ---------------------------------------------------------------- State Actions
    @action(detail=True, methods=["post"], url_path="confirm")
    def confirm(self, request, pk=None):
        """POST /api/invoices/{id}/confirm/ -> draft -> posted.
        Validates at least 1 line, generates invoice number, calculates totals, sets amount_due = total.
        """
        invoice = self.get_object()
        try:
            confirmed = confirm_invoice(invoice)
        except ValidationError as err:
            msg = err.message if hasattr(err, "message") else str(err)
            return Response({"detail": msg}, status=status.HTTP_400_BAD_REQUEST)
        return Response(InvoiceDetailSerializer(confirmed, context={"request": request}).data)

    @action(detail=True, methods=["post"], url_path="reset-to-draft")
    def reset_to_draft(self, request, pk=None):
        """POST /api/invoices/{id}/reset-to-draft/ -> posted -> draft.
        Allowed only if posted and no payments exist.
        """
        invoice = self.get_object()
        try:
            draft_inv = reset_invoice_to_draft(invoice)
        except ValidationError as err:
            msg = err.message if hasattr(err, "message") else str(err)
            return Response({"detail": msg}, status=status.HTTP_400_BAD_REQUEST)
        return Response(InvoiceDetailSerializer(draft_inv, context={"request": request}).data)

    @action(detail=True, methods=["post"], url_path="pay")
    def pay(self, request, pk=None):
        """POST /api/invoices/{id}/pay/ -> creates a Payment linked to invoice.
        Recomputes amount_paid and amount_due. If amount_due == 0 -> marks as paid.
        """
        invoice = self.get_object()
        serializer = PayInvoiceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            payment, updated_invoice = create_invoice_payment(
                invoice_id=invoice.id,
                journal_id=data["journal"].id,
                amount=data["amount"],
                payment_date=data.get("payment_date"),
                memo=data.get("memo", ""),
                user=request.user,
            )
        except ValidationError as err:
            msg = err.message if hasattr(err, "message") else str(err)
            return Response({"detail": msg}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            {
                "payment": PaymentSerializer(payment, context={"request": request}).data,
                "invoice": InvoiceDetailSerializer(updated_invoice, context={"request": request}).data,
                "detail": "Payment created successfully.",
            },
            status=status.HTTP_201_CREATED,
        )

    # ---------------------------------------------------------------- Multi-Level Group By
    @action(detail=False, methods=["get"], url_path="grouped")
    def grouped(self, request):
        """GET /api/invoices/grouped/?group_by=customer,status,month
        Supports 1 to 3 group-by levels in any order.
        Allowed fields: customer, status, month (or invoice_date), tags, journal.
        Combines with all standard filters (status, customer, date_from, unpaid, overdue, tags, search).
        """
        qs = self.filter_queryset(self.get_queryset())
        group_by = request.query_params.get("group_by", "customer,status,month").strip()
        fields = [f.strip() for f in group_by.split(",") if f.strip()]

        tree = get_grouped_invoices_tree(qs, fields)
        return Response(tree)

    # ---------------------------------------------------------------- Existing PDF & Email Actions
    @action(detail=True, methods=["get"], url_path="pdf")
    def pdf(self, request, pk=None):
        invoice = self.get_object()
        download = request.query_params.get("download", "").lower() in ("1", "true", "yes")
        return pdf_response(invoice, download=download)

    @action(detail=True, methods=["get"], url_path="send-logs")
    def send_logs_list(self, request, pk=None):
        invoice = self.get_object()
        logs = invoice.send_logs.all()
        serializer = InvoiceSendLogSerializer(logs, many=True, context={"request": request})
        return Response(serializer.data)

    @action(detail=True, methods=["post"], url_path="send-email")
    def send_email(self, request, pk=None):
        invoice = self.get_object()
        if invoice.status not in (InvoiceStatus.POSTED, InvoiceStatus.PAID, InvoiceStatus.ISSUED):
            return Response(
                {"detail": f"Only posted or paid invoices can be e-mailed (this one is '{invoice.status}')"},
                status=status.HTTP_409_CONFLICT,
            )
        recipient_email = (request.data or {}).get("recipient_email", "").strip()
        if recipient_email:
            try:
                EmailValidator()(recipient_email)
            except ValidationError:
                return Response(
                    {"detail": f"Invalid recipient email address: '{recipient_email}'"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        log = queue_invoice_email(invoice, recipient_email=recipient_email or None)
        log.refresh_from_db()
        return Response(InvoiceSendLogSerializer(log, context={"request": request}).data, status=status.HTTP_202_ACCEPTED)

    @action(detail=True, methods=["post"], url_path="create-send-log")
    def create_send_log(self, request, pk=None):
        if getattr(request.user, "role", None) not in ("admin",):
            return Response(
                {"detail": "Only admins can create send log entries."},
                status=status.HTTP_403_FORBIDDEN,
            )
        invoice = self.get_object()
        serializer = InvoiceSendLogCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        log = serializer.save(invoice=invoice)
        return Response(
            InvoiceSendLogSerializer(log, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["patch"], url_path="update-status")
    def update_status(self, request, pk=None):
        if getattr(request.user, "role", None) not in ("admin",):
            return Response(
                {"detail": "Only admins can update invoice status."},
                status=status.HTTP_403_FORBIDDEN,
            )

        invoice = self.get_object()
        serializer = InvoiceStatusUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        new_status = serializer.validated_data["status"]

        allowed = ALLOWED_TRANSITIONS.get(invoice.status, [])
        if new_status not in allowed:
            return Response(
                {
                    "detail": (
                        f"Cannot transition from '{invoice.status}' to '{new_status}'. "
                        f"Allowed transitions: {[s for s in allowed] or 'none (terminal state)'}."
                    )
                },
                status=status.HTTP_409_CONFLICT,
            )

        invoice.status = new_status
        invoice.save(update_fields=["status"])
        invoice.refresh_from_db()
        return Response(InvoiceDetailSerializer(invoice, context={"request": request}).data)
