import datetime
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import User
from fleet.models import Driver
from invoices.models import Customer, Invoice, InvoiceLine, InvoiceStatus, Journal, Payment, PaymentStatus, Tag
from orders.models import Order
from vendors.models import Vendor


class AccountingFeatureTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            email="admin_acct@erp.com", password="pass", role="admin", full_name="Admin Acct"
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.admin)

        # Create master data
        self.customer = Customer.objects.create(name="Acme Corp", email="acme@corp.com", phone="1234567890")
        self.customer2 = Customer.objects.create(name="Globex Inc", email="globex@inc.com")
        self.tag_urgent = Tag.objects.create(name="Urgent", color="#ef4444")
        self.tag_wholesale = Tag.objects.create(name="Wholesale", color="#3b82f6")

        self.journal_cash = Journal.objects.get_or_create(name="Cash", defaults={"type": "cash"})[0]
        self.journal_bank = Journal.objects.get_or_create(name="Bank", defaults={"type": "bank"})[0]

    def test_invoice_creation_in_draft(self):
        """Invoice is created in draft with computed lines."""
        data = {
            "customer": self.customer.id,
            "invoice_date": "2026-10-01",
            "lines": [
                {"product": "Widget A", "quantity": "2.00", "unit_price": "100.00", "tax_percent": "10.00"},
                {"product": "Widget B", "quantity": "1.00", "unit_price": "50.00", "tax_percent": "0.00"},
            ],
            "tags": [self.tag_urgent.id],
        }
        res = self.client.post("/api/v1/invoices/", data, format="json")
        self.assertEqual(res.status_code, 201)
        inv_id = res.data["id"]
        inv = Invoice.objects.get(id=inv_id)

        self.assertEqual(inv.status, InvoiceStatus.DRAFT)
        self.assertEqual(inv.amount_untaxed, Decimal("250.00"))
        self.assertEqual(inv.amount_tax, Decimal("20.00"))
        self.assertEqual(inv.amount_total, Decimal("270.00"))
        self.assertEqual(inv.lines.count(), 2)

    def test_confirm_invoice_validates_lines_generates_number(self):
        """Confirming an invoice validates lines, generates number like INV/2026/00001,
        and sets amount_due = amount_total.
        """
        # Empty lines invoice confirmation fails
        inv_empty = Invoice.objects.create(customer=self.customer, invoice_date=datetime.date(2026, 10, 1), status=InvoiceStatus.DRAFT)
        res_fail = self.client.post(f"/api/v1/invoices/{inv_empty.id}/confirm/")
        self.assertEqual(res_fail.status_code, 400)
        self.assertIn("at least one line", res_fail.data["detail"])

        # Invoice with lines confirmation succeeds
        inv = Invoice.objects.create(customer=self.customer, invoice_date=datetime.date(2026, 10, 1), status=InvoiceStatus.DRAFT)
        InvoiceLine.objects.create(invoice=inv, product="Services", quantity=Decimal("1.00"), unit_price=Decimal("500.00"), tax_percent=Decimal("5.00"))

        res = self.client.post(f"/api/v1/invoices/{inv.id}/confirm/")
        self.assertEqual(res.status_code, 200)

        inv.refresh_from_db()
        self.assertEqual(inv.status, InvoiceStatus.POSTED)
        self.assertTrue(inv.number.startswith("INV/2026/"))
        self.assertEqual(inv.amount_untaxed, Decimal("500.00"))
        self.assertEqual(inv.amount_tax, Decimal("25.00"))
        self.assertEqual(inv.amount_total, Decimal("525.00"))
        self.assertEqual(inv.amount_due, Decimal("525.00"))
        self.assertEqual(inv.amount_paid, Decimal("0.00"))

    def test_reset_to_draft(self):
        """Reset to draft allowed only if posted and no payments exist."""
        inv = Invoice.objects.create(customer=self.customer, invoice_date=datetime.date(2026, 10, 1), status=InvoiceStatus.DRAFT)
        InvoiceLine.objects.create(invoice=inv, product="Item", quantity=Decimal("1.00"), unit_price=Decimal("100.00"))
        self.client.post(f"/api/v1/invoices/{inv.id}/confirm/")

        # Reset to draft succeeds when 0 payments exist
        res = self.client.post(f"/api/v1/invoices/{inv.id}/reset-to-draft/")
        self.assertEqual(res.status_code, 200)
        inv.refresh_from_db()
        self.assertEqual(inv.status, InvoiceStatus.DRAFT)

        # Confirm again and pay -> reset to draft fails
        self.client.post(f"/api/v1/invoices/{inv.id}/confirm/")
        self.client.post(f"/api/v1/invoices/{inv.id}/pay/", {"journal": self.journal_cash.id, "amount": "50.00"}, format="json")

        res_blocked = self.client.post(f"/api/v1/invoices/{inv.id}/reset-to-draft/")
        self.assertEqual(res_blocked.status_code, 400)
        self.assertIn("payments have already been recorded", res_blocked.data["detail"])

    def test_partial_payment_and_full_payment_to_paid(self):
        """Partial payment keeps status 'posted'; paying remaining balance transitions status to 'paid'."""
        inv = Invoice.objects.create(customer=self.customer, invoice_date=datetime.date(2026, 10, 1), status=InvoiceStatus.DRAFT)
        InvoiceLine.objects.create(invoice=inv, product="Item", quantity=Decimal("1.00"), unit_price=Decimal("1000.00"))
        self.client.post(f"/api/v1/invoices/{inv.id}/confirm/")

        # Partial payment of 400
        pay_res1 = self.client.post(
            f"/api/v1/invoices/{inv.id}/pay/",
            {"journal": self.journal_cash.id, "amount": "400.00", "memo": "Partial cash payment"},
            format="json",
        )
        self.assertEqual(pay_res1.status_code, 201)
        self.assertTrue(pay_res1.data["payment"]["payment_number"].startswith("PAY/"))

        inv.refresh_from_db()
        self.assertEqual(inv.status, InvoiceStatus.POSTED)
        self.assertEqual(inv.amount_paid, Decimal("400.00"))
        self.assertEqual(inv.amount_due, Decimal("600.00"))

        # Overpayment rejection: remaining is 600, attempting to pay 600.01 fails
        overpay_res = self.client.post(
            f"/api/v1/invoices/{inv.id}/pay/",
            {"journal": self.journal_bank.id, "amount": "600.01"},
            format="json",
        )
        self.assertEqual(overpay_res.status_code, 400)
        self.assertIn("cannot exceed", overpay_res.data["detail"])

        # Pay remaining 600 -> automatically becomes 'paid'
        pay_res2 = self.client.post(
            f"/api/v1/invoices/{inv.id}/pay/",
            {"journal": self.journal_bank.id, "amount": "600.00", "memo": "Final bank settlement"},
            format="json",
        )
        self.assertEqual(pay_res2.status_code, 201)

        inv.refresh_from_db()
        self.assertEqual(inv.status, InvoiceStatus.PAID)
        self.assertEqual(inv.amount_paid, Decimal("1000.00"))
        self.assertEqual(inv.amount_due, Decimal("0.00"))

    def test_grouped_invoices_endpoint(self):
        """GET /api/invoices/grouped/?group_by=customer,status,month returns nested tree."""
        # Create multiple invoices
        inv1 = Invoice.objects.create(customer=self.customer, invoice_date=datetime.date(2026, 10, 1), status=InvoiceStatus.DRAFT)
        InvoiceLine.objects.create(invoice=inv1, product="A", quantity=Decimal("1.00"), unit_price=Decimal("100.00"))
        self.client.post(f"/api/v1/invoices/{inv1.id}/confirm/")

        inv2 = Invoice.objects.create(customer=self.customer2, invoice_date=datetime.date(2026, 10, 1), status=InvoiceStatus.DRAFT)
        InvoiceLine.objects.create(invoice=inv2, product="B", quantity=Decimal("1.00"), unit_price=Decimal("200.00"))
        self.client.post(f"/api/v1/invoices/{inv2.id}/confirm/")
        self.client.post(f"/api/v1/invoices/{inv2.id}/pay/", {"journal": self.journal_cash.id, "amount": "200.00"}, format="json")

        res = self.client.get("/api/v1/invoices/grouped/?group_by=customer,status")
        self.assertEqual(res.status_code, 200)
        tree = res.data
        self.assertIsInstance(tree, list)
        self.assertGreaterEqual(len(tree), 2)

        # Check structure
        first_group = tree[0]
        self.assertIn("key", first_group)
        self.assertEqual(first_group["field"], "customer")
        self.assertIn("count", first_group)
        self.assertIn("total", first_group)
        self.assertIn("due", first_group)
        self.assertIn("children", first_group)

    def test_grouped_invoices_order_fields(self):
        """GET /api/invoices/grouped/?group_by=vendor,status,driver,order_date supports 4-level nesting with linked orders."""
        vendor_user = User.objects.create_user(email="v_acct@erp.com", password="pass", role="vendor")
        vendor = Vendor.objects.create(name="Vendor Alpha", user=vendor_user)

        driver_user = User.objects.create_user(email="d_acct@erp.com", password="pass", role="driver", full_name="Driver John")
        driver = Driver.objects.create(user=driver_user, full_name="Driver John", phone="9999999999")

        order = Order.objects.create(
            vendor=vendor,
            customer_name="Alpha Cust",
            driver=driver,
            order_date=datetime.date(2026, 10, 5),
            origin_city="Mumbai",
            destination_city="Pune",
        )

        inv = Invoice.objects.create(
            order=order,
            customer=self.customer,
            invoice_date=datetime.date(2026, 10, 5),
            status=InvoiceStatus.POSTED,
            amount_total=Decimal("1500.00"),
            amount_due=Decimal("1500.00"),
        )

        res = self.client.get("/api/v1/invoices/grouped/?group_by=vendor,status,driver,order_date")
        self.assertEqual(res.status_code, 200)
        tree = res.data
        self.assertIsInstance(tree, list)
        self.assertGreaterEqual(len(tree), 1)

        # Level 1: Vendor
        v_node = next((n for n in tree if n["key"] == "Vendor Alpha"), None)
        self.assertIsNotNone(v_node)
        self.assertEqual(v_node["field"], "vendor")

        # Level 2: Status
        status_children = v_node["children"]
        self.assertGreaterEqual(len(status_children), 1)
        s_node = status_children[0]
        self.assertEqual(s_node["field"], "status")

        # Level 3: Driver
        driver_children = s_node["children"]
        self.assertGreaterEqual(len(driver_children), 1)
        d_node = driver_children[0]
        self.assertEqual(d_node["field"], "driver")
        self.assertEqual(d_node["key"], "Driver John")

        # Level 4: Order Date
        date_children = d_node["children"]
        self.assertGreaterEqual(len(date_children), 1)
        od_node = date_children[0]
        self.assertEqual(od_node["field"], "order_date")
        self.assertEqual(od_node["key"], "October 2026")

        # Leaf items
        leaves = od_node["children"]
        self.assertEqual(len(leaves), 1)
        self.assertEqual(leaves[0]["id"], inv.id)
        self.assertEqual(leaves[0]["vendor_name"], "Vendor Alpha")

    def test_dashboard_summary_endpoint(self):
        """GET /api/dashboard/summary/ returns accurate metrics and filled 12 months."""
        # Setup draft, posted, paid invoices
        inv1 = Invoice.objects.create(customer=self.customer, invoice_date=datetime.date(2026, 10, 1), status=InvoiceStatus.DRAFT)
        InvoiceLine.objects.create(invoice=inv1, product="D", quantity=Decimal("1.00"), unit_price=Decimal("150.00"))
        inv1.amount_total = Decimal("150.00")
        inv1.save()

        inv2 = Invoice.objects.create(customer=self.customer, invoice_date=datetime.date(2026, 10, 1), status=InvoiceStatus.DRAFT)
        InvoiceLine.objects.create(invoice=inv2, product="P", quantity=Decimal("1.00"), unit_price=Decimal("500.00"))
        self.client.post(f"/api/v1/invoices/{inv2.id}/confirm/")
        self.client.post(f"/api/v1/invoices/{inv2.id}/pay/", {"journal": self.journal_cash.id, "amount": "200.00"}, format="json")

        inv3 = Invoice.objects.create(customer=self.customer2, invoice_date=datetime.date(2026, 10, 1), status=InvoiceStatus.DRAFT)
        InvoiceLine.objects.create(invoice=inv3, product="B", quantity=Decimal("1.00"), unit_price=Decimal("300.00"))
        self.client.post(f"/api/v1/invoices/{inv3.id}/confirm/")
        self.client.post(f"/api/v1/invoices/{inv3.id}/pay/", {"journal": self.journal_bank.id, "amount": "300.00"}, format="json")

        res = self.client.get("/api/v1/dashboard/summary/")
        self.assertEqual(res.status_code, 200)
        data = res.data

        self.assertEqual(data["currency"], "USD")
        self.assertIn("top_cards", data)
        self.assertIn("sales", data)
        self.assertIn("cash", data)
        self.assertIn("bank", data)
        self.assertIn("recent_payments", data)
        self.assertIn("top_customers", data)
        self.assertIn("status_breakdown", data)

        # 12-month array has 12 items
        self.assertEqual(len(data["sales"]["monthly"]), 12)
        self.assertEqual(len(data["cash"]["monthly"]), 12)
        self.assertEqual(len(data["bank"]["monthly"]), 12)

        # Cash received = 200, Bank received = 300
        self.assertEqual(data["top_cards"]["cash_received"], 200.0)
        self.assertEqual(data["top_cards"]["bank_received"], 300.0)
