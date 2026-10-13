from django.contrib import admin
from .models import Customer, Invoice, InvoiceLine, InvoiceSendLog, Journal, Payment, Tag


class InvoiceLineInline(admin.TabularInline):
    model = InvoiceLine
    extra = 1
    fields = ["product", "description", "quantity", "unit_price", "tax_percent", "subtotal"]
    readonly_fields = ["subtotal"]


class InvoiceSendLogInline(admin.TabularInline):
    model = InvoiceSendLog
    extra = 0
    can_delete = False
    readonly_fields = ["recipient_email", "status", "sent_at", "attempts", "error_message", "created_at"]


class PaymentInline(admin.TabularInline):
    model = Payment
    extra = 0
    can_delete = False
    readonly_fields = ["payment_number", "journal", "amount", "payment_date", "memo", "status", "created_at"]


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ["id", "name", "email", "phone", "created_at"]
    search_fields = ["name", "email", "phone"]


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ["id", "name", "color"]
    search_fields = ["name"]


@admin.register(Journal)
class JournalAdmin(admin.ModelAdmin):
    list_display = ["id", "name", "type"]
    list_filter = ["type"]
    search_fields = ["name"]


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ["payment_number", "invoice", "journal", "amount", "payment_date", "status", "created_at"]
    list_filter = ["status", "journal__type", "journal"]
    search_fields = ["payment_number", "memo", "invoice__number", "invoice__invoice_number"]
    readonly_fields = ["payment_number", "created_at"]


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ["display_number", "customer", "invoice_date", "status", "amount_total", "amount_due", "amount_paid"]
    list_filter = ["status", "tags", "customer"]
    search_fields = ["number", "invoice_number", "customer__name", "order__order_number"]
    inlines = [InvoiceLineInline, PaymentInline, InvoiceSendLogInline]
    filter_horizontal = ["tags"]

    def display_number(self, obj):
        return obj.number or obj.invoice_number or f"Invoice #{obj.id}"
    display_number.short_description = "Number"


@admin.register(InvoiceSendLog)
class InvoiceSendLogAdmin(admin.ModelAdmin):
    list_display = ["invoice", "recipient_email", "status", "sent_at", "attempts", "created_at"]
    list_filter = ["status"]
    search_fields = ["invoice__invoice_number", "invoice__number", "recipient_email"]
    readonly_fields = ["created_at"]
