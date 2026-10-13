"""Data migration: create Invoice rows for orders that were already billed
before the Invoice model existed.

Before this module, invoices were rendered on demand from fields on the Order
(`invoice_number`, `freight_charge`, `invoice_amount`). Every order already in
status "closed" gets a persistent Invoice built from those fields, so its PDF
keeps working through the new invoice-based endpoint. Re-running is safe: an
order that already has a live invoice is skipped.
"""
from decimal import ROUND_HALF_UP, Decimal

from django.db import migrations

TWO = Decimal("0.01")


def _money(value) -> Decimal:
    return Decimal(str(value or 0)).quantize(TWO, rounding=ROUND_HALF_UP)


def backfill(apps, schema_editor):
    Order = apps.get_model("orders", "Order")
    Invoice = apps.get_model("invoices", "Invoice")

    for order in Order.objects.filter(status="closed").iterator():
        if Invoice.objects.filter(order=order).exclude(status="cancelled").exists():
            continue

        suffix = order.order_number.split("-")[-1]
        base = order.invoice_number or f"INV-{suffix}"
        number, n = base, 1
        while Invoice.objects.filter(invoice_number=number).exists():
            n += 1
            number = f"{base}-{n}"

        freight = _money(order.freight_charge)
        cod = _money(order.cod_amount) if order.is_cod else Decimal("0.00")
        # Legacy total is authoritative when present (it is what the customer
        # was originally shown); fall back to freight + COD.
        total = _money(order.invoice_amount) if order.invoice_amount else freight + cod

        invoice = Invoice.objects.create(
            order=order,
            invoice_number=number,
            freight_charge=freight,
            tax_amount=Decimal("0.00"),
            cod_amount=cod,
            total_amount=total,
            status="issued",
            created_by=None,
        )
        # auto_now_add stamped "now"; restore the real billing time. .update()
        # bypasses auto_now_add.
        Invoice.objects.filter(pk=invoice.pk).update(invoice_date=order.updated_at, created_at=order.updated_at)


class Migration(migrations.Migration):

    dependencies = [
        ("invoices", "0001_initial"),
    ]

    operations = [
        # Reverse is a no-op: removing backfilled invoices on rollback would
        # destroy legitimate data if any were created after the migration.
        migrations.RunPython(backfill, migrations.RunPython.noop),
    ]
