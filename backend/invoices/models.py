import datetime
from decimal import Decimal, ROUND_HALF_UP

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone


class Customer(models.Model):
    """Customer entity for invoicing and CRM.
    Used as Many2one relationship from Invoice (customer = ForeignKey(Customer, related_name='invoices')).
    """
    name = models.CharField(max_length=255, db_index=True)
    email = models.EmailField(blank=True, default="")
    phone = models.CharField(max_length=50, blank=True, default="")
    address = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name", "id"]

    def __str__(self):
        return self.name


class Tag(models.Model):
    """Tag entity for categorizing invoices.
    Used as Many2many relationship from Invoice (tags = ManyToManyField(Tag, related_name='invoices')).
    """
    name = models.CharField(max_length=100, unique=True)
    color = models.CharField(max_length=50, default="#6366f1")

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class JournalType(models.TextChoices):
    CASH = "cash", "Cash"
    BANK = "bank", "Bank"


class Journal(models.Model):
    """Payment journal (e.g. Cash, Bank).
    Default records 'Cash' and 'Bank' are populated via a data migration.
    Used as Many2one relationship from Payment (journal = ForeignKey(Journal, related_name='payments')).
    """
    name = models.CharField(max_length=100)
    type = models.CharField(max_length=20, choices=JournalType.choices, default=JournalType.CASH)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.get_type_display()})"


class InvoiceStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    POSTED = "posted", "Posted"
    ISSUED = "issued", "Issued"  # Preserved for backward compatibility with existing orders module
    PAID = "paid", "Paid"
    CANCELLED = "cancelled", "Cancelled"


class Invoice(models.Model):
    """Invoice model supporting both standalone billing and freight order billing.

    Relationships:
      - customer: ForeignKey(Customer) -> Many2one (Many invoices belong to one Customer)
      - lines: related_name='lines' on InvoiceLine -> One2many (One invoice has many invoice lines)
      - tags: ManyToManyField(Tag) -> Many2many (Invoices can have multiple tags, tags can belong to multiple invoices)
      - payments: related_name='payments' on Payment -> One2many (One invoice has many payments)
    """

    # Primary number: auto-generated like INV/2026/00001 on confirm
    number = models.CharField(max_length=100, unique=True, null=True, blank=True, db_index=True)
    # Legacy alias kept synchronized with number for existing modules & tests
    invoice_number = models.CharField(max_length=100, blank=True, default="", db_index=True)

    # Many2one (FK): Customer has many Invoices, each Invoice links to one Customer
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name="invoices", null=True, blank=True)

    # Optional order link for backward compatibility with domestic logistics order billing
    order = models.ForeignKey("orders.Order", on_delete=models.PROTECT, related_name="invoices", null=True, blank=True)

    invoice_date = models.DateField(default=datetime.date.today)
    due_date = models.DateField(null=True, blank=True)

    status = models.CharField(max_length=20, choices=InvoiceStatus.choices, default=InvoiceStatus.DRAFT, db_index=True)

    # Many2many (M2M): Invoices can have multiple tags, tags can belong to multiple invoices
    tags = models.ManyToManyField(Tag, blank=True, related_name="invoices")

    # Financial fields (computed from lines)
    amount_untaxed = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"), validators=[MinValueValidator(Decimal("0"))])
    amount_tax = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"), validators=[MinValueValidator(Decimal("0"))])
    amount_total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"), validators=[MinValueValidator(Decimal("0"))])
    amount_paid = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"), validators=[MinValueValidator(Decimal("0"))])
    amount_due = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"), validators=[MinValueValidator(Decimal("0"))])

    # Backward compatible fields for legacy orders module
    freight_charge = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"), validators=[MinValueValidator(Decimal("0"))])
    tax_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"), validators=[MinValueValidator(Decimal("0"))])
    cod_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"), validators=[MinValueValidator(Decimal("0"))])
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"), validators=[MinValueValidator(Decimal("0"))])

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["order"],
                condition=~Q(status="cancelled") & Q(order__isnull=False),
                name="uniq_active_invoice_per_order",
            ),
            models.CheckConstraint(condition=Q(amount_untaxed__gte=0), name="invoice_amount_untaxed_gte_0"),
            models.CheckConstraint(condition=Q(amount_tax__gte=0), name="invoice_amount_tax_gte_0"),
            models.CheckConstraint(condition=Q(amount_total__gte=0), name="invoice_amount_total_gte_0"),
            models.CheckConstraint(condition=Q(amount_paid__gte=0), name="invoice_amount_paid_gte_0"),
            models.CheckConstraint(condition=Q(amount_due__gte=0), name="invoice_amount_due_gte_0"),
            models.CheckConstraint(condition=Q(freight_charge__gte=0), name="invoice_freight_gte_0"),
            models.CheckConstraint(condition=Q(tax_amount__gte=0), name="invoice_tax_gte_0"),
            models.CheckConstraint(condition=Q(cod_amount__gte=0), name="invoice_cod_gte_0"),
            models.CheckConstraint(condition=Q(total_amount__gte=0), name="invoice_total_gte_0"),
        ]

    def __str__(self):
        return self.number or self.invoice_number or f"Draft Invoice #{self.id}"

    def clean(self):
        super().clean()
        if self.pk:
            orig = Invoice.objects.filter(pk=self.pk).first()
            if orig and orig.status in (InvoiceStatus.POSTED, InvoiceStatus.PAID, InvoiceStatus.ISSUED):
                # When posted/paid, customer and invoice_date cannot be modified directly
                if self.customer_id != orig.customer_id:
                    raise ValidationError("Customer cannot be changed on a posted or paid invoice.")
                if self.invoice_date != orig.invoice_date:
                    raise ValidationError("Invoice date cannot be changed on a posted or paid invoice.")

    def save(self, *args, **kwargs):
        # Sync number and invoice_number
        if self.number and not self.invoice_number:
            self.invoice_number = self.number
        elif self.invoice_number and not self.number:
            self.number = self.invoice_number

        # Sync amount_total and total_amount
        if self.amount_total > Decimal("0.00") and self.total_amount == Decimal("0.00"):
            self.total_amount = self.amount_total
        elif self.total_amount > Decimal("0.00") and self.amount_total == Decimal("0.00"):
            self.amount_total = self.total_amount

        # Sync tax_amount and amount_tax
        if self.amount_tax > Decimal("0.00") and self.tax_amount == Decimal("0.00"):
            self.tax_amount = self.amount_tax
        elif self.tax_amount > Decimal("0.00") and self.amount_tax == Decimal("0.00"):
            self.amount_tax = self.tax_amount

        # Default amount_due for posted/issued invoices if newly confirmed
        if self.status in (InvoiceStatus.POSTED, InvoiceStatus.ISSUED) and self.amount_paid == Decimal("0.00") and self.amount_due == Decimal("0.00") and self.amount_total > Decimal("0.00"):
            self.amount_due = self.amount_total

        super().save(*args, **kwargs)


class InvoiceLine(models.Model):
    """Line items belonging to an invoice.
    One2many from invoice side: Invoice has many lines (related_name='lines'),
    each line belongs to one Invoice (ForeignKey).
    """
    invoice = models.ForeignKey(Invoice, related_name="lines", on_delete=models.CASCADE)
    product = models.CharField(max_length=255, blank=True, default="")
    description = models.CharField(max_length=255, blank=True, default="")
    quantity = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("1.00"), validators=[MinValueValidator(Decimal("0.01"))])
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"), validators=[MinValueValidator(Decimal("0.00"))])
    tax_percent = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("0.00"), validators=[MinValueValidator(Decimal("0.00"))])
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))

    class Meta:
        ordering = ["id"]

    def clean(self):
        super().clean()
        if self.invoice_id:
            inv = getattr(self, "invoice", None) or Invoice.objects.filter(pk=self.invoice_id).first()
            if inv and inv.status in (InvoiceStatus.POSTED, InvoiceStatus.PAID, InvoiceStatus.ISSUED):
                raise ValidationError("Cannot add or modify lines on a posted or paid invoice.")

    def save(self, *args, **kwargs):
        qty = self.quantity or Decimal("0")
        price = self.unit_price or Decimal("0")
        self.subtotal = (qty * price).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        super().save(*args, **kwargs)

    def __str__(self):
        item = self.product or self.description or f"Line #{self.id}"
        return f"{item} ({self.quantity} @ {self.unit_price})"


class PaymentStatus(models.TextChoices):
    POSTED = "posted", "Posted"
    CANCELLED = "cancelled", "Cancelled"


class Payment(models.Model):
    """Payment recorded against an invoice.
    Relationships:
      - invoice: ForeignKey(Invoice, related_name='payments') -> One2many from Invoice side
      - journal: ForeignKey(Journal, related_name='payments') -> Many2one (Many payments link to one Journal)
    """
    payment_number = models.CharField(max_length=100, unique=True, blank=True, db_index=True)
    # One2many from invoice side: Invoice has many payments (related_name='payments'), each payment is linked to one Invoice (FK)
    invoice = models.ForeignKey(Invoice, related_name="payments", on_delete=models.PROTECT)
    # Many2one: Journal has many payments, each payment links to one Journal (FK)
    journal = models.ForeignKey(Journal, on_delete=models.PROTECT, related_name="payments")
    amount = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))])
    payment_date = models.DateField(default=datetime.date.today)
    memo = models.CharField(max_length=255, blank=True, default="")
    status = models.CharField(max_length=20, choices=PaymentStatus.choices, default=PaymentStatus.POSTED, db_index=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-payment_date", "-id"]

    @property
    def number(self):
        return self.payment_number

    def __str__(self):
        return f"{self.payment_number} - {self.amount} ({self.journal.name})"


class InvoiceSendStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    SENT = "sent", "Sent"
    FAILED = "failed", "Failed"
    BOUNCED = "bounced", "Bounced"


class InvoiceSendLog(models.Model):
    """One row per attempt to e-mail an invoice PDF to the vendor/customer."""

    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name="send_logs")
    recipient_email = models.EmailField(blank=True, default="")
    sent_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(
        max_length=20, choices=InvoiceSendStatus.choices, default=InvoiceSendStatus.PENDING, db_index=True
    )
    error_message = models.TextField(blank=True, default="")
    attempts = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return f"{self.invoice_id} -> {self.recipient_email or '(no recipient)'} [{self.status}]"
