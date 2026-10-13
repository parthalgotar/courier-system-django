"""
Renders the Freight Invoice / Shipment Closure Record (FRD Milestone 14)
as a downloadable PDF, styled to match the ERP console's freight-green theme.

The PDF is generated from the persistent `invoices.Invoice` record: invoice
number, date, status and every amount come from the stored row, so a
re-generated PDF is always identical to the one issued originally. Order and
vendor details (route, consignee, addresses, commodity) are read through the
invoice's order.
"""
import io
from decimal import Decimal

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

INK = colors.HexColor("#101820")
FREIGHT = colors.HexColor("#2F6F4E")
FREIGHT_DARK = colors.HexColor("#1E4A33")
MUTED = colors.HexColor("#4B5A63")
LINE = colors.HexColor("#DDE2DC")
ALERT = colors.HexColor("#B3261E")


def _money(value) -> str:
    return f"{Decimal(value):,.2f}"


def build_invoice_pdf(invoice) -> bytes:
    """Return PDF bytes for an `invoices.Invoice` instance."""
    order = invoice.order
    vendor = order.vendor
    vendor_name = vendor.name or "—"
    vendor_address = vendor.address or "—"

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.setTitle(f"Invoice {invoice.invoice_number}")
    width, height = A4
    left = 20 * mm
    right = width - 20 * mm

    # Header band
    c.setFillColor(FREIGHT_DARK)
    c.rect(0, height - 38 * mm, width, 38 * mm, fill=1, stroke=0)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 20)
    c.drawString(left, height - 15 * mm, "ERP Console")
    c.setFillColor(colors.HexColor("#8FD9B4"))
    c.setFont("Helvetica-Bold", 11)
    c.drawString(left, height - 22 * mm, "FREIGHT INVOICE")
    c.setFillColor(colors.white)
    c.setFont("Helvetica", 9)
    c.drawRightString(right, height - 15 * mm, invoice.invoice_number)
    c.drawRightString(right, height - 21 * mm, f"Date: {invoice.invoice_date:%d %b %Y}")
    c.drawRightString(right, height - 27 * mm, f"Order: {order.order_number}")
    c.drawRightString(right, height - 33 * mm, f"Tracking: {order.tracking_number}")

    y = height - 50 * mm
    mid = width / 2

    def label_value(y, label, value, x=left):
        c.setFont("Helvetica", 8.5)
        c.setFillColor(MUTED)
        c.drawString(x, y, label.upper())
        c.setFont("Helvetica-Bold", 10.5)
        c.setFillColor(INK)
        c.drawString(x, y - 5.2 * mm, value)

    label_value(y, "Shipper (Vendor)", vendor_name)
    label_value(y, "Consignee", order.customer_name, x=mid)
    c.setFont("Helvetica", 8.5)
    c.setFillColor(MUTED)
    c.drawString(left, y - 9.5 * mm, vendor_address[:70])
    c.drawString(mid, y - 9.5 * mm, order.delivery_address[:70])
    if vendor.contact_phone:
        c.drawString(left, y - 13.5 * mm, f"Tel: {vendor.contact_phone}"[:70])

    y -= 25 * mm
    label_value(y, "Route", f"{order.origin_city or '—'}  ->  {order.destination_city or '—'}")
    label_value(y, "Invoice status", invoice.get_status_display(), x=mid)
    label_value(y - 11 * mm, "Commodity", f"{order.commodity} ({order.weight_kg} kg)")

    # Charges table
    y -= 32 * mm
    c.setFillColor(colors.HexColor("#F3F5F2"))
    c.rect(left, y, right - left, 8 * mm, fill=1, stroke=0)
    c.setFillColor(INK)
    c.setFont("Helvetica-Bold", 9)
    c.drawString(left + 2 * mm, y + 2.5 * mm, "DESCRIPTION")
    c.drawRightString(right - 2 * mm, y + 2.5 * mm, "AMOUNT (INR)")

    rows = [("Freight charges", invoice.freight_charge)]
    if invoice.cod_amount:
        rows.append(("COD amount collected", invoice.cod_amount))
    rows.append(("Tax", invoice.tax_amount))

    row_y = y - 8 * mm
    c.setFont("Helvetica", 10)
    for desc, amount in rows:
        c.setFillColor(INK)
        c.drawString(left + 2 * mm, row_y + 2 * mm, desc)
        c.drawRightString(right - 2 * mm, row_y + 2 * mm, _money(amount))
        c.setStrokeColor(LINE)
        c.line(left, row_y, right, row_y)
        row_y -= 8 * mm

    c.setFont("Helvetica-Bold", 12)
    c.setFillColor(FREIGHT)
    c.drawString(left + 2 * mm, row_y - 2 * mm, "TOTAL")
    c.drawRightString(right - 2 * mm, row_y - 2 * mm, f"INR {_money(invoice.total_amount)}")

    if invoice.status == "cancelled":
        c.saveState()
        c.setFillColor(ALERT)
        c.setFont("Helvetica-Bold", 60)
        c.translate(width / 2, height / 2)
        c.rotate(35)
        c.setFillAlpha(0.18)
        c.drawCentredString(0, 0, "CANCELLED")
        c.restoreState()

    c.setFont("Helvetica", 7.5)
    c.setFillColor(MUTED)
    c.drawString(left, 15 * mm, "System-generated invoice — ERP Console (Domestic Logistics Platform).")

    c.showPage()
    c.save()
    buf.seek(0)
    return buf.read()
