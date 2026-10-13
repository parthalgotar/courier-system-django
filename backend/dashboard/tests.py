import datetime
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import User
from dashboard.dashboard_services import get_dashboard_summary
from invoices.models import Customer, Invoice, InvoiceLine, InvoiceStatus, Journal, Payment, PaymentStatus


class DashboardSummaryTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="dash_user@erp.com", password="pwd", role="admin")
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

        self.customer1 = Customer.objects.create(name="Apex Corp")
        self.customer2 = Customer.objects.create(name="Zenith Ltd")

        self.j_cash = Journal.objects.get_or_create(name="Cash", defaults={"type": "cash"})[0]
        self.j_bank = Journal.objects.get_or_create(name="Bank", defaults={"type": "bank"})[0]

        today = timezone.now().date()
        yesterday = today - datetime.timedelta(days=1)
        two_days_ago = today - datetime.timedelta(days=2)

        # 1. Draft invoices (to_validate)
        self.inv_draft1 = Invoice.objects.create(
            customer=self.customer1,
            invoice_date=today,
            status=InvoiceStatus.DRAFT,
            amount_total=Decimal("500.00"),
            total_amount=Decimal("500.00"),
        )
        self.inv_draft2 = Invoice.objects.create(
            customer=self.customer2,
            invoice_date=today,
            status=InvoiceStatus.DRAFT,
            amount_total=Decimal("750.00"),
            total_amount=Decimal("750.00"),
        )

        # 2. Posted unpaid & on-time invoice
        self.inv_posted = Invoice.objects.create(
            customer=self.customer1,
            number="INV/2026/00101",
            invoice_date=today,
            due_date=today + datetime.timedelta(days=15),
            status=InvoiceStatus.POSTED,
            amount_total=Decimal("1200.00"),
            amount_due=Decimal("1200.00"),
            total_amount=Decimal("1200.00"),
        )

        # 3. Posted overdue (late) invoice (due_date < today)
        self.inv_late = Invoice.objects.create(
            customer=self.customer2,
            number="INV/2026/00102",
            invoice_date=two_days_ago,
            due_date=yesterday,
            status=InvoiceStatus.POSTED,
            amount_total=Decimal("800.00"),
            amount_due=Decimal("800.00"),
            total_amount=Decimal("800.00"),
        )

        # 4. Paid invoice with Cash & Bank payments
        self.inv_paid = Invoice.objects.create(
            customer=self.customer1,
            number="INV/2026/00103",
            invoice_date=today,
            status=InvoiceStatus.PAID,
            amount_total=Decimal("1500.00"),
            amount_paid=Decimal("1500.00"),
            amount_due=Decimal("0.00"),
            total_amount=Decimal("1500.00"),
        )
        Payment.objects.create(
            payment_number="PAY/2026/00001",
            invoice=self.inv_paid,
            journal=self.j_cash,
            amount=Decimal("600.00"),
            payment_date=today,
            status=PaymentStatus.POSTED,
        )
        Payment.objects.create(
            payment_number="PAY/2026/00002",
            invoice=self.inv_paid,
            journal=self.j_bank,
            amount=Decimal("900.00"),
            payment_date=today,
            status=PaymentStatus.POSTED,
        )

    def test_summary_numbers_draft_unpaid_late_cash_bank(self):
        """Verify summary values: draft count/amount, unpaid, late, cash vs bank."""
        summary = get_dashboard_summary(use_cache=False)

        # Draft totals: 500 + 750 = 1250
        self.assertEqual(summary["sales"]["to_validate"]["count"], 2)
        self.assertEqual(summary["sales"]["to_validate"]["amount"], 1250.0)
        self.assertEqual(summary["top_cards"]["draft_total"], 1250.0)

        # Unpaid: posted (1200) + late (800) = 2000
        self.assertEqual(summary["sales"]["unpaid"]["count"], 2)
        self.assertEqual(summary["sales"]["unpaid"]["amount"], 2000.0)
        self.assertEqual(summary["top_cards"]["receivable"], 2000.0)

        # Late: overdue posted invoice = 800
        self.assertEqual(summary["sales"]["late"]["count"], 1)
        self.assertEqual(summary["sales"]["late"]["amount"], 800.0)
        self.assertEqual(summary["top_cards"]["overdue_total"], 800.0)

        # Cash vs Bank: cash = 600, bank = 900
        self.assertEqual(summary["top_cards"]["cash_received"], 600.0)
        self.assertEqual(summary["top_cards"]["bank_received"], 900.0)
        self.assertEqual(summary["cash"]["balance"], 600.0)
        self.assertEqual(summary["bank"]["balance"], 900.0)

        # Invoices total: posted (1200) + late (800) + paid (1500) = 3500
        self.assertEqual(summary["top_cards"]["invoices_total"], 3500.0)

        # Status breakdown
        self.assertEqual(summary["status_breakdown"]["draft"]["count"], 2)
        self.assertEqual(summary["status_breakdown"]["posted"]["count"], 2)
        self.assertEqual(summary["status_breakdown"]["paid"]["count"], 1)

    def test_dashboard_api_endpoint(self):
        """GET /api/dashboard/summary/ through API client."""
        res = self.client.get("/api/dashboard/summary/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["currency"], "USD")
        self.assertEqual(len(res.data["sales"]["monthly"]), 12)
        self.assertEqual(len(res.data["recent_payments"]), 2)
        self.assertGreaterEqual(len(res.data["top_customers"]), 2)
