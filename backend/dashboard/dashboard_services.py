"""Service selectors and aggregation logic for the Invoice/Accounting Dashboard.
All queries use pure ORM aggregation (Sum, Count, Q, Coalesce, TruncMonth) with 0-value fill.
Includes optional 60-second caching with cache invalidation on save/delete signals.
"""
import datetime
from decimal import Decimal

from django.core.cache import cache
from django.db.models import Count, Q, Sum
from django.db.models.functions import Coalesce, TruncMonth
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver
from django.utils import timezone

from invoices.models import Invoice, InvoiceStatus, Journal, Payment, PaymentStatus

CACHE_KEY_PREFIX = "invoice_dashboard_summary_"
CACHE_TIMEOUT = 60  # seconds


def get_last_12_months_keys(end_date: datetime.date | None = None) -> list[str]:
    """Generate last 12 calendar month keys in 'YYYY-MM' format up to end_date."""
    ref = end_date or timezone.now().date()
    keys = []
    y, m = ref.year, ref.month
    for i in range(11, -1, -1):
        month = m - i
        year = y
        while month <= 0:
            month += 12
            year -= 1
        keys.append(f"{year:04d}-{month:02d}")
    return keys


def get_dashboard_summary(
    date_from: str | None = None,
    date_to: str | None = None,
    customer: str | None = None,
    journal: str | None = None,
    use_cache: bool = True,
) -> dict:
    """Compute complete accounting summary for the Odoo-like dashboard.
    Optional query parameters:
      - date_from: YYYY-MM-DD
      - date_to: YYYY-MM-DD
      - customer: customer ID or name substring
      - journal: journal ID, name, or type (cash / bank)
    """
    cache_key = f"{CACHE_KEY_PREFIX}_{date_from}_{date_to}_{customer}_{journal}"
    if use_cache:
        cached_data = cache.get(cache_key)
        if cached_data is not None:
            return cached_data

    today = timezone.now().date()
    inv_qs = Invoice.objects.all()
    pay_qs = Payment.objects.filter(status=PaymentStatus.POSTED)

    # Apply date filters
    if date_from:
        inv_qs = inv_qs.filter(invoice_date__gte=date_from)
        pay_qs = pay_qs.filter(payment_date__gte=date_from)
    if date_to:
        inv_qs = inv_qs.filter(invoice_date__lte=date_to)
        pay_qs = pay_qs.filter(payment_date__lte=date_to)

    # Apply customer filter
    if customer:
        if str(customer).isdigit():
            c_id = int(customer)
            inv_qs = inv_qs.filter(Q(customer_id=c_id) | Q(order__vendor_id=c_id))
            pay_qs = pay_qs.filter(Q(invoice__customer_id=c_id) | Q(invoice__order__vendor_id=c_id))
        else:
            inv_qs = inv_qs.filter(
                Q(customer__name__icontains=customer) | Q(order__customer_name__icontains=customer)
            )
            pay_qs = pay_qs.filter(
                Q(invoice__customer__name__icontains=customer)
                | Q(invoice__order__customer_name__icontains=customer)
            )

    # Apply journal filter to payments and optionally invoices
    if journal:
        if str(journal).isdigit():
            j_id = int(journal)
            pay_qs = pay_qs.filter(journal_id=j_id)
        else:
            j_str = str(journal).lower()
            pay_qs = pay_qs.filter(Q(journal__type__iexact=j_str) | Q(journal__name__icontains=j_str))

    # Active invoice statuses for sales
    CONFIRMED_STATUSES = [InvoiceStatus.POSTED, InvoiceStatus.PAID, InvoiceStatus.ISSUED]

    # 1. Top Cards Aggregations
    invoices_total = (
        inv_qs.filter(status__in=CONFIRMED_STATUSES).aggregate(
            s=Coalesce(Sum("amount_total"), Decimal("0.00"))
        )["s"]
    )

    receivable = (
        inv_qs.filter(status__in=[InvoiceStatus.POSTED, InvoiceStatus.ISSUED]).aggregate(
            s=Coalesce(Sum("amount_due"), Decimal("0.00"))
        )["s"]
    )

    cash_received = (
        pay_qs.filter(journal__type="cash").aggregate(
            s=Coalesce(Sum("amount"), Decimal("0.00"))
        )["s"]
    )

    bank_received = (
        pay_qs.filter(journal__type="bank").aggregate(
            s=Coalesce(Sum("amount"), Decimal("0.00"))
        )["s"]
    )

    draft_total = (
        inv_qs.filter(status=InvoiceStatus.DRAFT).aggregate(
            s=Coalesce(Sum("amount_total"), Decimal("0.00"))
        )["s"]
    )

    overdue_total = (
        inv_qs.filter(
            status__in=[InvoiceStatus.POSTED, InvoiceStatus.ISSUED],
            due_date__isnull=False,
            due_date__lt=today,
        ).aggregate(s=Coalesce(Sum("amount_due"), Decimal("0.00")))["s"]
    )

    # 2. Sales Breakdown
    draft_stats = inv_qs.filter(status=InvoiceStatus.DRAFT).aggregate(
        c=Count("id"),
        s=Coalesce(Sum("amount_total"), Decimal("0.00")),
    )
    unpaid_stats = inv_qs.filter(
        status__in=[InvoiceStatus.POSTED, InvoiceStatus.ISSUED],
        amount_due__gt=Decimal("0.00"),
    ).aggregate(
        c=Count("id"),
        s=Coalesce(Sum("amount_due"), Decimal("0.00")),
    )
    late_stats = inv_qs.filter(
        status__in=[InvoiceStatus.POSTED, InvoiceStatus.ISSUED],
        due_date__isnull=False,
        due_date__lt=today,
    ).aggregate(
        c=Count("id"),
        s=Coalesce(Sum("amount_due"), Decimal("0.00")),
    )

    # 3. Monthly Timelines (12 months with zeros for missing months)
    months_keys = get_last_12_months_keys(today)

    sales_monthly_agg = (
        inv_qs.filter(status__in=CONFIRMED_STATUSES)
        .annotate(m=TruncMonth("invoice_date"))
        .values("m")
        .annotate(total=Coalesce(Sum("amount_total"), Decimal("0.00")))
    )
    sales_map = {row["m"].strftime("%Y-%m"): float(row["total"]) for row in sales_monthly_agg if row["m"]}
    sales_monthly = [{"month": mk, "total": sales_map.get(mk, 0.0)} for mk in months_keys]

    cash_monthly_agg = (
        pay_qs.filter(journal__type="cash")
        .annotate(m=TruncMonth("payment_date"))
        .values("m")
        .annotate(amount=Coalesce(Sum("amount"), Decimal("0.00")))
    )
    cash_map = {row["m"].strftime("%Y-%m"): float(row["amount"]) for row in cash_monthly_agg if row["m"]}
    cash_monthly = [{"month": mk, "amount": cash_map.get(mk, 0.0)} for mk in months_keys]

    bank_monthly_agg = (
        pay_qs.filter(journal__type="bank")
        .annotate(m=TruncMonth("payment_date"))
        .values("m")
        .annotate(amount=Coalesce(Sum("amount"), Decimal("0.00")))
    )
    bank_map = {row["m"].strftime("%Y-%m"): float(row["amount"]) for row in bank_monthly_agg if row["m"]}
    bank_monthly = [{"month": mk, "amount": bank_map.get(mk, 0.0)} for mk in months_keys]

    # 4. Recent Payments (latest 5)
    recent_qs = (
        pay_qs.select_related("invoice", "invoice__customer", "invoice__order", "journal")
        .order_by("-payment_date", "-id")[:5]
    )
    recent_payments = []
    for p in recent_qs:
        inv = p.invoice
        c_name = inv.customer.name if inv.customer else (inv.order.customer_name if inv.order else "—")
        recent_payments.append({
            "id": p.id,
            "number": p.payment_number or f"PAY-{p.id}",
            "invoice_number": inv.number or inv.invoice_number or f"INV-{inv.id}",
            "invoice_id": inv.id,
            "customer": c_name,
            "journal": p.journal.name,
            "journal_type": p.journal.type,
            "amount": float(p.amount),
            "date": p.payment_date.isoformat() if p.payment_date else "",
            "memo": p.memo,
            "status": p.status,
        })

    # 5. Top 5 Customers by Total Invoiced
    cust_agg = (
        inv_qs.filter(customer__isnull=False, status__in=CONFIRMED_STATUSES)
        .values("customer__id", "customer__name")
        .annotate(
            total=Coalesce(Sum("amount_total"), Decimal("0.00")),
            due=Coalesce(Sum("amount_due"), Decimal("0.00")),
        )
        .order_by("-total")[:5]
    )
    top_customers = [
        {
            "id": r["customer__id"],
            "name": r["customer__name"],
            "total": float(r["total"]),
            "due": float(r["due"]),
        }
        for r in cust_agg
    ]

    # 6. Status Breakdown
    status_agg = (
        inv_qs.values("status")
        .annotate(
            count=Count("id"),
            amount=Coalesce(Sum("amount_total"), Decimal("0.00")),
        )
    )
    raw_status_map = {
        row["status"]: {"count": row["count"], "amount": float(row["amount"])}
        for row in status_agg
    }

    # Merge legacy 'issued' into 'posted'
    posted_c = raw_status_map.get(InvoiceStatus.POSTED, {}).get("count", 0) + raw_status_map.get("issued", {}).get("count", 0)
    posted_a = raw_status_map.get(InvoiceStatus.POSTED, {}).get("amount", 0.0) + raw_status_map.get("issued", {}).get("amount", 0.0)

    status_breakdown = {
        "draft": raw_status_map.get(InvoiceStatus.DRAFT, {"count": 0, "amount": 0.0}),
        "posted": {"count": posted_c, "amount": posted_a},
        "paid": raw_status_map.get(InvoiceStatus.PAID, {"count": 0, "amount": 0.0}),
    }

    result = {
        "currency": "USD",
        "top_cards": {
            "invoices_total": float(invoices_total),
            "receivable": float(receivable),
            "cash_received": float(cash_received),
            "bank_received": float(bank_received),
            "draft_total": float(draft_total),
            "overdue_total": float(overdue_total),
        },
        "sales": {
            "to_validate": {"count": draft_stats["c"], "amount": float(draft_stats["s"])},
            "unpaid": {"count": unpaid_stats["c"], "amount": float(unpaid_stats["s"])},
            "late": {"count": late_stats["c"], "amount": float(late_stats["s"])},
            "monthly": sales_monthly,
        },
        "cash": {
            "balance": float(cash_received),
            "monthly": cash_monthly,
        },
        "bank": {
            "balance": float(bank_received),
            "monthly": bank_monthly,
        },
        "recent_payments": recent_payments,
        "top_customers": top_customers,
        "status_breakdown": status_breakdown,
    }

    if use_cache:
        cache.set(cache_key, result, timeout=CACHE_TIMEOUT)

    return result


def invalidate_dashboard_cache():
    """Invalidate all cached dashboard summaries."""
    try:
        cache.clear()
    except Exception:
        pass


@receiver([post_save, post_delete], sender=Invoice)
@receiver([post_save, post_delete], sender=Payment)
def on_financial_data_change(sender, **kwargs):
    """Automatically invalidate dashboard cache on invoice or payment changes."""
    invalidate_dashboard_cache()
