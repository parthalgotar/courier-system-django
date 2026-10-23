"""Invoice business logic, kept out of the views so billing, state transitions,
payments, and APIs share it cleanly.
"""
import datetime
import logging
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Count, Sum, Q
from django.db.models.functions import Coalesce, TruncMonth, TruncYear
from django.utils import timezone

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

logger = logging.getLogger(__name__)

TWO_PLACES = Decimal("0.01")


def to_money(value) -> Decimal:
    """Convert user/float input to a 2-dp Decimal (raises InvalidOperation /
    ValueError for junk, and for NaN / Infinity)."""
    d = Decimal(str(value).strip())
    if not d.is_finite():
        raise InvalidOperation("non-finite amount")
    return d.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


# ------------------------------------------------------------------ Number Generation
def generate_invoice_seq_number(year: int | None = None) -> str:
    """Generate sequential invoice number: INV/YYYY/00001 (e.g. INV/2026/00001)."""
    if not year:
        year = timezone.now().year
    prefix = f"INV/{year}/"
    last_inv = (
        Invoice.objects.filter(
            Q(number__startswith=prefix) | Q(invoice_number__startswith=prefix)
        )
        .order_by("-id")
        .first()
    )
    next_num = 1
    if last_inv:
        ref_num = last_inv.number or last_inv.invoice_number
        try:
            parts = ref_num.split("/")
            if len(parts) == 3 and parts[1] == str(year):
                next_num = int(parts[2]) + 1
            else:
                next_num = (
                    Invoice.objects.filter(
                        Q(number__startswith=prefix) | Q(invoice_number__startswith=prefix)
                    ).count()
                    + 1
                )
        except (ValueError, IndexError):
            next_num = (
                Invoice.objects.filter(
                    Q(number__startswith=prefix) | Q(invoice_number__startswith=prefix)
                ).count()
                + 1
            )

    candidate = f"{prefix}{next_num:05d}"
    while Invoice.objects.filter(Q(number=candidate) | Q(invoice_number=candidate)).exists():
        next_num += 1
        candidate = f"{prefix}{next_num:05d}"
    return candidate


def generate_payment_number(year: int | None = None) -> str:
    """Generate sequential payment number: PAY/YYYY/00001 (e.g. PAY/2026/00001)."""
    if not year:
        year = timezone.now().year
    prefix = f"PAY/{year}/"
    last_payment = Payment.objects.filter(payment_number__startswith=prefix).order_by("-id").first()
    next_num = 1
    if last_payment:
        try:
            parts = last_payment.payment_number.split("/")
            if len(parts) == 3 and parts[1] == str(year):
                next_num = int(parts[2]) + 1
            else:
                next_num = Payment.objects.filter(payment_number__startswith=prefix).count() + 1
        except (ValueError, IndexError):
            next_num = Payment.objects.filter(payment_number__startswith=prefix).count() + 1

    candidate = f"{prefix}{next_num:05d}"
    while Payment.objects.filter(payment_number=candidate).exists():
        next_num += 1
        candidate = f"{prefix}{next_num:05d}"
    return candidate


# ------------------------------------------------------------------ Calculations
def compute_and_save_invoice_totals(invoice: Invoice) -> Invoice:
    """Compute amount_untaxed, amount_tax, amount_total from lines and update invoice."""
    lines = invoice.lines.all()
    untaxed = Decimal("0.00")
    tax_total = Decimal("0.00")

    for line in lines:
        line_sub = (line.quantity * line.unit_price).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
        if line.subtotal != line_sub:
            line.subtotal = line_sub
            line.save(update_fields=["subtotal"])
        untaxed += line_sub
        if line.tax_percent > Decimal("0.00"):
            tax_total += (line_sub * (line.tax_percent / Decimal("100"))).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)

    total = untaxed + tax_total

    invoice.amount_untaxed = untaxed
    invoice.amount_tax = tax_total
    invoice.amount_total = total
    invoice.total_amount = total

    # Recompute paid and due
    paid = (
        invoice.payments.filter(status=PaymentStatus.POSTED).aggregate(s=Coalesce(Sum("amount"), Decimal("0.00")))["s"]
    )
    invoice.amount_paid = paid
    invoice.amount_due = max(Decimal("0.00"), total - paid)

    invoice.save(update_fields=["amount_untaxed", "amount_tax", "amount_total", "total_amount", "amount_paid", "amount_due"])
    return invoice


# ------------------------------------------------------------------ State Management
def confirm_invoice(invoice: Invoice) -> Invoice:
    """Confirm a draft invoice -> changes status to posted, validates at least 1 line,
    generates invoice number, calculates totals, and sets amount_due = total.
    """
    if invoice.status != InvoiceStatus.DRAFT:
        raise ValidationError(f"Only draft invoices can be confirmed (current status: '{invoice.status}').")

    if not invoice.lines.exists():
        raise ValidationError("Invoice must have at least one line before confirmation.")

    # Calculate totals from lines
    compute_and_save_invoice_totals(invoice)

    # Generate sequential invoice number if not already assigned
    if not invoice.number or not invoice.number.startswith("INV/"):
        yr = invoice.invoice_date.year if invoice.invoice_date else timezone.now().year
        invoice.number = generate_invoice_seq_number(yr)
        invoice.invoice_number = invoice.number

    # Set due amount = total amount if not paid
    invoice.amount_due = invoice.amount_total - invoice.amount_paid
    invoice.status = InvoiceStatus.POSTED
    invoice.save()
    return invoice


def reset_invoice_to_draft(invoice: Invoice) -> Invoice:
    """Reset a posted invoice back to draft.
    Allowed only if status is posted/issued and no active payments exist.
    """
    if invoice.status not in (InvoiceStatus.POSTED, InvoiceStatus.ISSUED):
        raise ValidationError(f"Only posted invoices can be reset to draft (current status: '{invoice.status}').")

    active_payments = invoice.payments.filter(status=PaymentStatus.POSTED)
    if active_payments.exists():
        raise ValidationError("Cannot reset invoice to draft because payments have already been recorded.")

    invoice.status = InvoiceStatus.DRAFT
    invoice.save(update_fields=["status", "updated_at"])
    return invoice


def create_invoice_payment(
    invoice_id: int,
    journal_id: int,
    amount: Decimal | float | str,
    payment_date: datetime.date | None = None,
    memo: str = "",
    user=None,
) -> tuple[Payment, Invoice]:
    """Record a payment for an invoice with race condition protection using select_for_update.
    Recomputes amount_paid and amount_due.
    If amount_due == 0 -> automatically marks invoice status as 'paid'.
    Partial payments keep status as 'posted'.
    """
    with transaction.atomic():
        invoice = Invoice.objects.select_for_update().get(pk=invoice_id)

        if invoice.status not in (InvoiceStatus.POSTED, InvoiceStatus.ISSUED):
            if invoice.status == InvoiceStatus.PAID:
                raise ValidationError("Invoice is already fully paid.")
            if invoice.status == InvoiceStatus.DRAFT:
                raise ValidationError("Draft invoices cannot be paid. Please confirm the invoice first.")
            raise ValidationError(f"Cannot record payment for an invoice with status '{invoice.status}'.")

        try:
            journal = Journal.objects.get(pk=journal_id)
        except Journal.DoesNotExist:
            raise ValidationError(f"Journal with id {journal_id} does not exist.")

        amt = to_money(amount)
        if amt <= Decimal("0.00"):
            raise ValidationError("Payment amount must be greater than zero.")

        if amt > invoice.amount_due:
            raise ValidationError(
                f"Payment amount (${amt}) cannot exceed the remaining amount due (${invoice.amount_due})."
            )

        pay_date = payment_date or timezone.now().date()
        pay_num = generate_payment_number(pay_date.year)
        payment_memo = memo or invoice.number or invoice.invoice_number or f"Payment for #{invoice.id}"

        payment = Payment.objects.create(
            payment_number=pay_num,
            invoice=invoice,
            journal=journal,
            amount=amt,
            payment_date=pay_date,
            memo=payment_memo,
            status=PaymentStatus.POSTED,
            created_by=user,
        )

        # Recompute totals
        total_paid = (
            invoice.payments.filter(status=PaymentStatus.POSTED).aggregate(
                s=Coalesce(Sum("amount"), Decimal("0.00"))
            )["s"]
        )
        invoice.amount_paid = total_paid
        remaining_due = max(Decimal("0.00"), invoice.amount_total - total_paid)
        invoice.amount_due = remaining_due

        if remaining_due == Decimal("0.00"):
            invoice.status = InvoiceStatus.PAID
        else:
            invoice.status = InvoiceStatus.POSTED

        invoice.save(update_fields=["amount_paid", "amount_due", "status", "updated_at"])

    return payment, invoice


# ------------------------------------------------------------------ Multi-level Group By Tree
def get_grouped_invoices_tree(qs, group_by_fields: list[str]) -> list[dict]:
    """Build a nested tree for multi-level group-by on invoices.
    Supports any number of levels in any order.
    Allowed fields: vendor, status, driver, order_date, customer, route,
    invoice_date (or month), payment_status, journal, tags.
    """
    def _build_tree(sub_qs, fields: list[str]) -> list[dict]:
        if not fields:
            # Leaf level: return invoice items
            items = []
            for inv in sub_qs[:100]:
                cust_name = inv.customer.name if inv.customer else (inv.order.customer_name if inv.order else "—")
                items.append({
                    "id": inv.id,
                    "number": inv.number or inv.invoice_number or f"INV-{inv.id}",
                    "invoice_number": inv.number or inv.invoice_number or f"INV-{inv.id}",
                    "customer": cust_name,
                    "customer_name": cust_name,
                    "invoice_date": inv.invoice_date.isoformat() if inv.invoice_date else "",
                    "due_date": inv.due_date.isoformat() if inv.due_date else "",
                    "status": inv.status,
                    "amount_total": float(inv.amount_total),
                    "amount_due": float(inv.amount_due),
                    "amount_paid": float(inv.amount_paid),
                    "order_id": inv.order_id,
                    "order_number": inv.order.order_number if inv.order else "",
                    "vendor_name": inv.order.vendor.name if (inv.order and inv.order.vendor) else "",
                })
            return items

        current_field = fields[0].strip().lower()
        remaining_fields = fields[1:]

        if current_field in ("vendor", "partner"):
            groups = (
                sub_qs.values("order__vendor__id", "order__vendor__name")
                .annotate(
                    count=Count("id", distinct=True),
                    total=Coalesce(Sum("amount_total"), Decimal("0.00")),
                    due=Coalesce(Sum("amount_due"), Decimal("0.00")),
                )
                .order_by("order__vendor__name")
            )
            result = []
            for g in groups:
                v_name = g["order__vendor__name"] or "No Vendor / Direct"
                v_id = g["order__vendor__id"]
                nxt_qs = sub_qs.filter(order__vendor_id=v_id) if v_id else sub_qs.filter(Q(order__isnull=True) | Q(order__vendor__isnull=True))
                result.append({
                    "key": v_name,
                    "field": "vendor",
                    "count": g["count"],
                    "total": float(g["total"]),
                    "due": float(g["due"]),
                    "children": _build_tree(nxt_qs, remaining_fields),
                })
            return result

        elif current_field == "status":
            groups = (
                sub_qs.values("status")
                .annotate(
                    count=Count("id", distinct=True),
                    total=Coalesce(Sum("amount_total"), Decimal("0.00")),
                    due=Coalesce(Sum("amount_due"), Decimal("0.00")),
                )
                .order_by("status")
            )
            result = []
            status_labels = dict(InvoiceStatus.choices)
            for g in groups:
                st = g["status"]
                st_label = status_labels.get(st, st.capitalize())
                nxt_qs = sub_qs.filter(status=st)
                result.append({
                    "key": st_label,
                    "field": "status",
                    "count": g["count"],
                    "total": float(g["total"]),
                    "due": float(g["due"]),
                    "children": _build_tree(nxt_qs, remaining_fields),
                })
            return result

        elif current_field in ("driver", "salesperson"):
            groups = (
                sub_qs.values("order__driver__id", "order__driver__full_name", "order__driver__user__full_name")
                .annotate(
                    count=Count("id", distinct=True),
                    total=Coalesce(Sum("amount_total"), Decimal("0.00")),
                    due=Coalesce(Sum("amount_due"), Decimal("0.00")),
                )
                .order_by("order__driver__id")
            )
            result = []
            for g in groups:
                d_id = g["order__driver__id"]
                if d_id:
                    name = (g["order__driver__full_name"] or g["order__driver__user__full_name"] or "").strip()
                    d_name = name if name else f"Driver {d_id}"
                else:
                    d_name = "Unassigned Driver"
                nxt_qs = sub_qs.filter(order__driver_id=d_id) if d_id else sub_qs.filter(Q(order__isnull=True) | Q(order__driver__isnull=True))
                result.append({
                    "key": d_name,
                    "field": "driver",
                    "count": g["count"],
                    "total": float(g["total"]),
                    "due": float(g["due"]),
                    "children": _build_tree(nxt_qs, remaining_fields),
                })
            return result

        elif current_field in ("order_date", "orderdate"):
            groups = (
                sub_qs.annotate(od_m=TruncMonth("order__order_date"))
                .values("od_m")
                .annotate(
                    count=Count("id", distinct=True),
                    total=Coalesce(Sum("amount_total"), Decimal("0.00")),
                    due=Coalesce(Sum("amount_due"), Decimal("0.00")),
                )
                .order_by("-od_m")
            )
            result = []
            for g in groups:
                m_val = g["od_m"]
                m_str = m_val.strftime("%B %Y") if m_val else "No Order Date"
                nxt_qs = (
                    sub_qs.filter(order__order_date__year=m_val.year, order__order_date__month=m_val.month)
                    if m_val
                    else sub_qs.filter(Q(order__isnull=True) | Q(order__order_date__isnull=True))
                )
                result.append({
                    "key": m_str,
                    "field": "order_date",
                    "count": g["count"],
                    "total": float(g["total"]),
                    "due": float(g["due"]),
                    "children": _build_tree(nxt_qs, remaining_fields),
                })
            return result

        elif current_field == "customer":
            groups = (
                sub_qs.values("customer__id", "customer__name")
                .annotate(
                    count=Count("id", distinct=True),
                    total=Coalesce(Sum("amount_total"), Decimal("0.00")),
                    due=Coalesce(Sum("amount_due"), Decimal("0.00")),
                )
                .order_by("-total")
            )
            result = []
            for g in groups:
                c_name = g["customer__name"] or "No Customer"
                c_id = g["customer__id"]
                nxt_qs = sub_qs.filter(customer_id=c_id) if c_id else sub_qs.filter(customer__isnull=True)
                result.append({
                    "key": c_name,
                    "field": "customer",
                    "count": g["count"],
                    "total": float(g["total"]),
                    "due": float(g["due"]),
                    "children": _build_tree(nxt_qs, remaining_fields),
                })
            return result

        elif current_field in ("route", "routes"):
            groups = (
                sub_qs.values("order__origin_city", "order__destination_city")
                .annotate(
                    count=Count("id", distinct=True),
                    total=Coalesce(Sum("amount_total"), Decimal("0.00")),
                    due=Coalesce(Sum("amount_due"), Decimal("0.00")),
                )
                .order_by("order__origin_city")
            )
            result = []
            for g in groups:
                orig = (g["order__origin_city"] or "").strip()
                dest = (g["order__destination_city"] or "").strip()
                if orig and dest:
                    r_name = f"{orig} → {dest}"
                    nxt_qs = sub_qs.filter(order__origin_city=orig, order__destination_city=dest)
                else:
                    r_name = "Direct / No Route"
                    nxt_qs = sub_qs.filter(Q(order__isnull=True) | Q(order__origin_city="") | Q(order__destination_city=""))
                result.append({
                    "key": r_name,
                    "field": "route",
                    "count": g["count"],
                    "total": float(g["total"]),
                    "due": float(g["due"]),
                    "children": _build_tree(nxt_qs, remaining_fields),
                })
            return result

        elif current_field in ("month", "invoice_date", "date"):
            groups = (
                sub_qs.annotate(m=TruncMonth("invoice_date"))
                .values("m")
                .annotate(
                    count=Count("id", distinct=True),
                    total=Coalesce(Sum("amount_total"), Decimal("0.00")),
                    due=Coalesce(Sum("amount_due"), Decimal("0.00")),
                )
                .order_by("-m")
            )
            result = []
            for g in groups:
                m_val = g["m"]
                m_str = m_val.strftime("%B %Y") if m_val else "No Date"
                nxt_qs = (
                    sub_qs.filter(invoice_date__year=m_val.year, invoice_date__month=m_val.month)
                    if m_val
                    else sub_qs.filter(invoice_date__isnull=True)
                )
                result.append({
                    "key": m_str,
                    "field": "invoice_date",
                    "count": g["count"],
                    "total": float(g["total"]),
                    "due": float(g["due"]),
                    "children": _build_tree(nxt_qs, remaining_fields),
                })
            return result

        elif current_field in ("payment_status", "payment_method"):
            groups = (
                sub_qs.values("status")
                .annotate(
                    count=Count("id", distinct=True),
                    total=Coalesce(Sum("amount_total"), Decimal("0.00")),
                    due=Coalesce(Sum("amount_due"), Decimal("0.00")),
                )
                .order_by("status")
            )
            result = []
            for g in groups:
                st = g["status"]
                st_label = "Paid" if st == "paid" else ("Posted (Unpaid)" if st == "posted" else st.capitalize())
                nxt_qs = sub_qs.filter(status=st)
                result.append({
                    "key": st_label,
                    "field": "payment_status",
                    "count": g["count"],
                    "total": float(g["total"]),
                    "due": float(g["due"]),
                    "children": _build_tree(nxt_qs, remaining_fields),
                })
            return result

        elif current_field in ("tags", "tag"):
            groups = (
                sub_qs.values("tags__id", "tags__name")
                .annotate(
                    count=Count("id", distinct=True),
                    total=Coalesce(Sum("amount_total"), Decimal("0.00")),
                    due=Coalesce(Sum("amount_due"), Decimal("0.00")),
                )
                .order_by("tags__name")
            )
            result = []
            for g in groups:
                t_name = g["tags__name"] or "Untagged"
                t_id = g["tags__id"]
                nxt_qs = sub_qs.filter(tags__id=t_id) if t_id else sub_qs.filter(tags__isnull=True)
                result.append({
                    "key": t_name,
                    "field": "tags",
                    "count": g["count"],
                    "total": float(g["total"]),
                    "due": float(g["due"]),
                    "children": _build_tree(nxt_qs, remaining_fields),
                })
            return result

        elif current_field in ("journal", "journal_type"):
            groups = (
                sub_qs.values("payments__journal__id", "payments__journal__name")
                .annotate(
                    count=Count("id", distinct=True),
                    total=Coalesce(Sum("amount_total"), Decimal("0.00")),
                    due=Coalesce(Sum("amount_due"), Decimal("0.00")),
                )
                .order_by("payments__journal__name")
            )
            result = []
            for g in groups:
                j_name = g["payments__journal__name"] or "No Journal"
                j_id = g["payments__journal__id"]
                nxt_qs = sub_qs.filter(payments__journal_id=j_id) if j_id else sub_qs.filter(payments__isnull=True)
                result.append({
                    "key": j_name,
                    "field": "journal",
                    "count": g["count"],
                    "total": float(g["total"]),
                    "due": float(g["due"]),
                    "children": _build_tree(nxt_qs, remaining_fields),
                })
            return result

        return []

    valid_fields = [f for f in group_by_fields if f.strip()]
    if not valid_fields:
        return []
    return _build_tree(qs, valid_fields)


# ------------------------------------------------------------------ Legacy Orders Integration
def generate_invoice_number(order) -> str:
    """Unique invoice number for order billing.
    ORD-1A2B3C4D -> INV-1A2B3C4D.
    """
    base = f"INV-{order.order_number.split('-')[-1]}"
    candidate, n = base, 1
    while Invoice.objects.filter(Q(invoice_number=candidate) | Q(number=candidate)).exists():
        n += 1
        candidate = f"{base}-{n}"
    return candidate


def get_live_invoice(order):
    """The order's non-cancelled invoice, if any."""
    return Invoice.objects.filter(order=order).exclude(status=InvoiceStatus.CANCELLED).first()


def get_invoice_for_order(order):
    """Best invoice to show for an order: the live one, else the most recent (cancelled) one."""
    return get_live_invoice(order) or Invoice.objects.filter(order=order).order_by("-id").first()


def create_invoice_for_order(order, *, freight_charge, tax_amount=Decimal("0.00"), created_by=None):
    """Create (or on retry, return) the invoice for a billed order.
    Idempotent: returns (invoice, created).
    """
    existing = get_live_invoice(order)
    if existing:
        return existing, False

    freight = to_money(freight_charge)
    tax = to_money(tax_amount)
    cod = to_money(order.cod_amount) if order.is_cod else Decimal("0.00")
    total = freight + tax + cod

    last_error = None
    for _ in range(3):
        try:
            with transaction.atomic():
                inv_num = generate_invoice_number(order)
                invoice = Invoice.objects.create(
                    order=order,
                    invoice_number=inv_num,
                    number=inv_num,
                    freight_charge=freight,
                    tax_amount=tax,
                    cod_amount=cod,
                    total_amount=total,
                    amount_untaxed=freight,
                    amount_tax=tax,
                    amount_total=total,
                    amount_paid=Decimal("0.00"),
                    amount_due=total,
                    status=InvoiceStatus.ISSUED,
                    created_by=created_by,
                )
            return invoice, True
        except IntegrityError as exc:
            last_error = exc
            existing = get_live_invoice(order)
            if existing:
                return existing, False
    if last_error is not None:
        raise last_error
    raise RuntimeError("Failed to create invoice after retries.")


# ------------------------------------------------------------------ E-mail Sending
def queue_invoice_email(invoice, *, recipient_email: str | None = None) -> InvoiceSendLog:
    """Record an e-mail delivery attempt and hand it to Celery.
    ``recipient_email`` – if provided, overrides the vendor's billing_email.
    """
    if recipient_email:
        recipient = recipient_email
    elif invoice.order and getattr(invoice.order, "vendor", None):
        recipient = invoice.order.vendor.billing_email
    elif invoice.customer:
        recipient = invoice.customer.email
    else:
        recipient = ""

    log = InvoiceSendLog.objects.create(
        invoice=invoice,
        recipient_email=recipient or "",
        status=InvoiceSendStatus.PENDING if recipient else InvoiceSendStatus.FAILED,
        error_message="" if recipient else "Vendor has no registered e-mail address",
    )
    if not recipient:
        vendor_id = getattr(invoice.order, "vendor_id", None) if invoice.order else None
        logger.warning("Invoice %s: vendor %s has no e-mail; nothing sent", invoice.invoice_number, vendor_id)
        return log

    log_id = log.pk

    def _enqueue():
        from .tasks import send_invoice_email

        try:
            send_invoice_email.delay(log_id)
        except Exception as exc:
            logger.warning(
                "Could not queue invoice e-mail for log %s (%s: %s)",
                log_id, exc.__class__.__name__, exc,
            )
            InvoiceSendLog.objects.filter(pk=log_id, status=InvoiceSendStatus.PENDING).update(
                status=InvoiceSendStatus.FAILED,
                error_message=f"Broker unavailable: {exc.__class__.__name__}: {exc}"[:1000],
            )

    transaction.on_commit(_enqueue)
    return log
