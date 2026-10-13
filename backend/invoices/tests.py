"""Tests for the Accounting / Invoice Management module.

Run with:  python manage.py test invoices
No Redis, SMTP or network is needed: Celery runs eagerly and Django's
locmem e-mail backend captures messages.
"""
from datetime import timedelta
from decimal import Decimal
from unittest import mock

from django.core import mail
from django.db import IntegrityError, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase, override_settings
from django.utils import timezone
from reportlab import rl_config
from rest_framework.test import APIClient

from accounts.models import User
from fleet.models import Driver
from invoices.models import Invoice, InvoiceSendLog, InvoiceSendStatus, InvoiceStatus
from invoices.services import create_invoice_for_order, generate_invoice_number, queue_invoice_email
from invoices.tasks import send_invoice_email
from orders.models import Order, OrderStatus
from vendors.models import Vendor

PASSWORD = "pass1234"


# --------------------------------------------------------------------- helpers
def make_user(email, role):
    return User.objects.create_user(email=email, password=PASSWORD, role=role, full_name=email.split("@")[0].title())


def make_vendor(name, user=None, email=""):
    return Vendor.objects.create(name=name, contact_phone="9000000000", address=f"{name} Street", user=user, email=email)


def make_order(vendor, status=OrderStatus.DELIVERED, **kw):
    kw.setdefault("customer_name", "John Doe")
    kw.setdefault("customer_phone", "9876543210")
    kw.setdefault("delivery_address", "12 Delivery Rd")
    kw.setdefault("origin_city", "Pune")
    kw.setdefault("destination_city", "Mumbai")
    kw.setdefault("weight_kg", 5.5)
    return Order.objects.create(vendor=vendor, status=status, **kw)


def make_invoice(order, freight="1000.00", tax="0.00", status=InvoiceStatus.ISSUED, created_by=None):
    cod = Decimal(str(order.cod_amount)) if order.is_cod else Decimal("0")
    freight, tax = Decimal(freight), Decimal(tax)
    return Invoice.objects.create(
        order=order, invoice_number=generate_invoice_number(order), freight_charge=freight,
        tax_amount=tax, cod_amount=cod, total_amount=freight + tax + cod, status=status, created_by=created_by,
    )


# NOTE: Celery (namespace="CELERY") reads the *prefixed* Django setting before
# any runtime `app.conf` override, so eager mode must be switched via Django
# settings, not `celery_app.conf.task_always_eager = True` (silently ignored).
@override_settings(CELERY_TASK_ALWAYS_EAGER=True)
class BaseCase(TestCase):
    """Two vendors (each with a login), one admin, dispatcher, driver."""

    @classmethod
    def setUpTestData(cls):
        cls.admin = make_user("admin@erp.com", "admin")
        cls.dispatcher = make_user("dispatcher@erp.com", "dispatcher")
        cls.driver_user = make_user("driver@erp.com", "driver")
        cls.vendor_a_user = make_user("vendora@erp.com", "vendor")
        cls.vendor_b_user = make_user("vendorb@erp.com", "vendor")
        cls.vendor_a = make_vendor("Alpha Traders", cls.vendor_a_user)
        cls.vendor_b = make_vendor("Beta Foods", cls.vendor_b_user)

    def setUp(self):
        # Uncompressed PDF streams so tests can look for text inside the bytes.
        self._old_comp = rl_config.pageCompression
        rl_config.pageCompression = 0
        self.addCleanup(setattr, rl_config, "pageCompression", self._old_comp)

    def client_for(self, user):
        c = APIClient()
        if user is not None:
            c.force_authenticate(user=user)
        return c


# ============================================================== model / DB rules
class InvoiceModelTests(BaseCase):
    def test_one_live_invoice_per_order_enforced_by_database(self):
        order = make_order(self.vendor_a)
        make_invoice(order)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Invoice.objects.create(
                order=order, invoice_number="INV-OTHER", freight_charge=Decimal("1"), total_amount=Decimal("1"),
                status=InvoiceStatus.ISSUED,
            )

    def test_cancelled_invoice_does_not_block_a_new_one_and_number_stays_unique(self):
        order = make_order(self.vendor_a)
        first = make_invoice(order)
        first.status = InvoiceStatus.CANCELLED
        first.save()
        second = make_invoice(order)
        self.assertNotEqual(first.invoice_number, second.invoice_number)
        self.assertTrue(second.invoice_number.startswith(first.invoice_number))

    def test_invoice_number_is_unique(self):
        order = make_order(self.vendor_a)
        inv = make_invoice(order)
        other = make_order(self.vendor_a)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Invoice.objects.create(order=other, invoice_number=inv.invoice_number, freight_charge=1, total_amount=1)

    def test_negative_amounts_rejected_by_database(self):
        order = make_order(self.vendor_a)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Invoice.objects.create(order=order, invoice_number="INV-NEG", freight_charge=Decimal("-1"), total_amount=Decimal("1"))

    def test_status_choices(self):
        self.assertEqual({c for c, _ in InvoiceStatus.choices}, {"draft", "posted", "issued", "paid", "cancelled"})
        self.assertEqual({c for c, _ in InvoiceSendStatus.choices}, {"pending", "sent", "failed", "bounced"})

    def test_decimal_precision(self):
        order = make_order(self.vendor_a)
        inv = make_invoice(order, freight="0.10", tax="0.20")
        inv.refresh_from_db()
        self.assertEqual(inv.freight_charge + inv.tax_amount, Decimal("0.30"))  # floats would give 0.30000000000000004


# ================================================= billing -> invoice creation
class BillingCreatesInvoiceTests(BaseCase):
    def bill(self, order, user=None, **params):
        params.setdefault("freight_charge", "1200")
        return self.client_for(user or self.admin).post(f"/api/v1/orders/{order.id}/close-billing", params)

    def bill_url(self, order, qs):
        return self.client_for(self.admin).post(f"/api/v1/orders/{order.id}/close-billing?{qs}")

    def test_billing_creates_invoice_and_keeps_existing_behaviour(self):
        order = make_order(self.vendor_a)
        r = self.bill_url(order, "freight_charge=1200")
        self.assertEqual(r.status_code, 200)
        # existing response shape / values preserved
        self.assertEqual(r.data["status"], "closed")
        self.assertEqual(r.data["freight_charge"], 1200.0)
        self.assertEqual(r.data["invoice_amount"], 1200.0)
        self.assertEqual(r.data["invoice_number"], f"INV-{order.order_number.split('-')[-1]}")
        self.assertEqual(r.data["events"][-1]["status"], "closed")
        # ... and the new persistent record
        inv = Invoice.objects.get(order=order)
        self.assertEqual(inv.invoice_number, r.data["invoice_number"])
        self.assertEqual(inv.freight_charge, Decimal("1200.00"))
        self.assertEqual(inv.tax_amount, Decimal("0.00"))
        self.assertEqual(inv.total_amount, Decimal("1200.00"))
        self.assertEqual(inv.status, InvoiceStatus.ISSUED)
        self.assertEqual(inv.created_by, self.admin)
        self.assertIsNotNone(inv.invoice_date)

    def test_cod_order_total_matches_legacy_rule(self):
        order = make_order(self.vendor_a, is_cod=True, cod_amount=500.0)
        r = self.bill_url(order, "freight_charge=1200")
        inv = Invoice.objects.get(order=order)
        self.assertEqual(inv.cod_amount, Decimal("500.00"))
        self.assertEqual(inv.total_amount, Decimal("1700.00"))
        self.assertEqual(r.data["invoice_amount"], 1700.0)  # old rule: freight + cod

    def test_tax_is_optional_and_added_to_total(self):
        order = make_order(self.vendor_a)
        r = self.bill_url(order, "freight_charge=1000&tax_amount=180.50")
        inv = Invoice.objects.get(order=order)
        self.assertEqual(inv.tax_amount, Decimal("180.50"))
        self.assertEqual(inv.total_amount, Decimal("1180.50"))
        self.assertEqual(r.data["invoice_amount"], 1180.5)

    def test_retrying_billing_does_not_duplicate_invoice(self):
        order = make_order(self.vendor_a)
        self.assertEqual(self.bill_url(order, "freight_charge=1200").status_code, 200)
        retry = self.bill_url(order, "freight_charge=1200")
        self.assertEqual(retry.status_code, 409)  # unchanged legacy behaviour
        self.assertEqual(Invoice.objects.filter(order=order).count(), 1)

    def test_rebilling_an_order_that_already_has_a_live_invoice_reuses_it(self):
        """Even if an order is forced back to DELIVERED (e.g. via admin), the
        service must not mint a second live invoice."""
        order = make_order(self.vendor_a)
        self.bill_url(order, "freight_charge=1200")
        Order.objects.filter(pk=order.pk).update(status=OrderStatus.DELIVERED)
        r = self.bill_url(order, "freight_charge=9999")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Invoice.objects.filter(order=order).count(), 1)
        self.assertEqual(Invoice.objects.get(order=order).freight_charge, Decimal("1200.00"))  # original kept
        self.assertEqual(r.data["freight_charge"], 1200.0)

    def test_service_is_idempotent(self):
        order = make_order(self.vendor_a)
        a, created_a = create_invoice_for_order(order, freight_charge="10")
        b, created_b = create_invoice_for_order(order, freight_charge="99")
        self.assertTrue(created_a)
        self.assertFalse(created_b)
        self.assertEqual(a.pk, b.pk)

    def test_each_invoice_number_is_unique(self):
        numbers = set()
        for _ in range(5):
            o = make_order(self.vendor_a)
            self.bill_url(o, "freight_charge=10")
            numbers.add(Invoice.objects.get(order=o).invoice_number)
        self.assertEqual(len(numbers), 5)

    def test_existing_validation_messages_preserved_and_no_invoice_created(self):
        order = make_order(self.vendor_a)
        r = self.client_for(self.admin).post(f"/api/v1/orders/{order.id}/close-billing")
        self.assertEqual((r.status_code, r.data["detail"]), (422, "freight_charge query param is required"))
        for bad in ("abc", "nan", "inf"):
            self.assertEqual(self.bill_url(order, f"freight_charge={bad}").status_code, 422, bad)
        self.assertEqual(self.bill_url(order, "freight_charge=-5").status_code, 422)
        self.assertEqual(self.bill_url(order, "freight_charge=10&tax_amount=x").status_code, 422)
        self.assertEqual(self.bill_url(order, "freight_charge=10&tax_amount=-1").status_code, 422)
        self.assertEqual(Invoice.objects.count(), 0)
        order.refresh_from_db()
        self.assertEqual(order.status, OrderStatus.DELIVERED)  # untouched

    def test_only_delivered_orders_can_be_billed(self):
        order = make_order(self.vendor_a, status=OrderStatus.OUT_FOR_DELIVERY)
        r = self.bill_url(order, "freight_charge=10")
        self.assertEqual((r.status_code, r.data["detail"]), (409, "Order must be Delivered before billing/closure"))
        self.assertEqual(Invoice.objects.count(), 0)

    def test_billing_requires_authentication_and_admin_or_dispatcher(self):
        order = make_order(self.vendor_a)
        url = f"/api/v1/orders/{order.id}/close-billing?freight_charge=10"
        self.assertEqual(self.client_for(None).post(url).status_code, 401)
        self.assertEqual(self.client_for(self.vendor_a_user).post(url).status_code, 403)
        self.assertEqual(self.client_for(self.driver_user).post(url).status_code, 403)
        self.assertEqual(Invoice.objects.count(), 0)
        self.assertEqual(self.client_for(self.dispatcher).post(url).status_code, 200)
        self.assertEqual(Invoice.objects.get(order=order).created_by, self.dispatcher)

    def test_billing_atomic_when_invoice_creation_fails(self):
        order = make_order(self.vendor_a)
        with mock.patch("orders.views.create_invoice_for_order", side_effect=RuntimeError("boom")):
            c = self.client_for(self.admin)
            c.raise_request_exception = False
            r = c.post(f"/api/v1/orders/{order.id}/close-billing?freight_charge=10")
        self.assertEqual(r.status_code, 500)
        order.refresh_from_db()
        self.assertEqual(order.status, OrderStatus.DELIVERED)  # rolled back, not half-closed
        self.assertEqual(order.invoice_number, None)


# ============================================================ e-mail delivery
class InvoiceEmailTests(BaseCase):
    def bill(self, order):
        with self.captureOnCommitCallbacks(execute=True):
            r = self.client_for(self.admin).post(f"/api/v1/orders/{order.id}/close-billing?freight_charge=1200")
        self.assertEqual(r.status_code, 200)
        return Invoice.objects.get(order=order)

    def test_billing_emails_pdf_to_vendor_and_logs_it(self):
        order = make_order(self.vendor_a)
        inv = self.bill(order)
        # At least one email should be sent (invoice PDF + possibly an order status notification).
        self.assertGreaterEqual(len(mail.outbox), 1)
        # Find the invoice-PDF email (has a PDF attachment).
        invoice_emails = [m for m in mail.outbox if m.attachments]
        self.assertEqual(len(invoice_emails), 1, "Expected exactly 1 email with a PDF attachment")
        msg = invoice_emails[0]
        self.assertEqual(msg.to, ["vendora@erp.com"])
        self.assertIn(inv.invoice_number, msg.subject)
        name, content, mimetype = msg.attachments[0]
        self.assertEqual((name, mimetype), (f"{inv.invoice_number}.pdf", "application/pdf"))
        self.assertTrue(content.startswith(b"%PDF"))
        log = InvoiceSendLog.objects.get(invoice=inv)
        self.assertEqual(log.status, InvoiceSendStatus.SENT)
        self.assertEqual(log.recipient_email, "vendora@erp.com")
        self.assertIsNotNone(log.sent_at)

    def test_vendor_without_account_uses_vendor_email(self):
        v = make_vendor("No Login Ltd", user=None, email="billing@nologin.com")
        inv = self.bill(make_order(v))
        self.assertEqual(mail.outbox[0].to, ["billing@nologin.com"])
        self.assertEqual(InvoiceSendLog.objects.get(invoice=inv).status, InvoiceSendStatus.SENT)

    def test_linked_user_email_takes_priority(self):
        self.vendor_a.email = "old@alpha.com"
        self.vendor_a.save()
        self.bill(make_order(self.vendor_a))
        self.assertEqual(mail.outbox[0].to, ["vendora@erp.com"])

    def test_no_recipient_is_recorded_as_failed_and_billing_still_succeeds(self):
        v = make_vendor("Nobody Inc")
        inv = self.bill(make_order(v))
        self.assertEqual(mail.outbox, [])
        log = InvoiceSendLog.objects.get(invoice=inv)
        self.assertEqual(log.status, InvoiceSendStatus.FAILED)
        self.assertIn("no registered e-mail", log.error_message)

    def test_broker_down_does_not_break_billing(self):
        """Redis not running: .delay() raises. Billing must still return 200."""
        order = make_order(self.vendor_a)
        with mock.patch.object(send_invoice_email, "delay", side_effect=ConnectionError("redis unreachable")):
            inv = self.bill(order)
        order.refresh_from_db()
        self.assertEqual(order.status, OrderStatus.CLOSED)
        log = InvoiceSendLog.objects.get(invoice=inv)
        self.assertEqual(log.status, InvoiceSendStatus.FAILED)
        self.assertIn("redis unreachable", log.error_message)

    def test_email_is_queued_not_sent_inline_when_not_eager(self):
        """With a real broker the request only enqueues; it doesn't call SMTP."""
        order = make_order(self.vendor_a)
        with self.settings(CELERY_TASK_ALWAYS_EAGER=False), mock.patch.object(send_invoice_email, "delay") as delay:
            inv = self.bill(order)
        log = InvoiceSendLog.objects.get(invoice=inv)
        delay.assert_called_once_with(log.pk)
        self.assertEqual(log.status, InvoiceSendStatus.PENDING)
        self.assertEqual(mail.outbox, [])

    def test_task_is_only_enqueued_after_commit(self):
        order = make_order(self.vendor_a)
        with mock.patch.object(send_invoice_email, "delay") as delay:
            with self.captureOnCommitCallbacks(execute=False) as callbacks:
                r = self.client_for(self.admin).post(f"/api/v1/orders/{order.id}/close-billing?freight_charge=10")
            self.assertEqual(r.status_code, 200)
            self.assertEqual(len(callbacks), 1)
            delay.assert_not_called()  # registered, but not run until the transaction commits
            callbacks[0]()
            delay.assert_called_once()

    def test_smtp_failure_marks_log_failed_after_retries(self):
        inv = make_invoice(make_order(self.vendor_a))
        log = queue_invoice_email_now(inv)
        with mock.patch("django.core.mail.EmailMessage.send", side_effect=OSError("smtp down")):
            result = send_invoice_email.apply(args=[log.pk])
        log.refresh_from_db()
        self.assertEqual(log.status, InvoiceSendStatus.FAILED)
        self.assertIn("smtp down", log.error_message)
        self.assertEqual(log.attempts, 4)  # first try + 3 retries
        self.assertIsNone(log.sent_at)
        self.assertEqual(mail.outbox, [])
        self.assertTrue(result.successful())  # handled: recorded, not crashed

    def test_transient_failure_then_success(self):
        inv = make_invoice(make_order(self.vendor_a))
        log = queue_invoice_email_now(inv)
        real_send = mail.EmailMessage.send
        calls = {"n": 0}

        def flaky(self_, fail_silently=False):
            calls["n"] += 1
            if calls["n"] == 1:
                raise OSError("temporary")
            return real_send(self_, fail_silently=fail_silently)

        with mock.patch("django.core.mail.EmailMessage.send", flaky):
            send_invoice_email.apply(args=[log.pk])
        log.refresh_from_db()
        self.assertEqual(log.status, InvoiceSendStatus.SENT)
        self.assertEqual(log.attempts, 2)
        self.assertEqual(log.error_message, "")
        self.assertEqual(len(mail.outbox), 1)

    def test_sent_log_is_never_sent_twice(self):
        inv = make_invoice(make_order(self.vendor_a))
        log = queue_invoice_email_now(inv)
        send_invoice_email.apply(args=[log.pk])
        send_invoice_email.apply(args=[log.pk])  # e.g. broker redelivery
        self.assertEqual(len(mail.outbox), 1)

    def test_missing_log_does_not_crash(self):
        self.assertEqual(send_invoice_email.apply(args=[999999]).result, "missing")

    def test_resend_endpoint_admin_only(self):
        inv = self.bill(make_order(self.vendor_a))
        mail.outbox.clear()
        url = f"/api/v1/invoices/{inv.id}/send-email/"
        self.assertEqual(self.client_for(None).post(url).status_code, 401)
        self.assertEqual(self.client_for(self.dispatcher).post(url).status_code, 403)  # read-only role
        self.assertEqual(self.client_for(self.vendor_a_user).post(url).status_code, 403)
        self.assertEqual(self.client_for(self.driver_user).post(url).status_code, 403)
        with self.captureOnCommitCallbacks(execute=True):
            r = self.client_for(self.admin).post(url)
        self.assertEqual(r.status_code, 202)  # accepted: sending happens after the response
        self.assertEqual(r.data["status"], "pending")
        self.assertEqual(InvoiceSendLog.objects.filter(invoice=inv).count(), 2)
        new_log = InvoiceSendLog.objects.get(pk=r.data["id"])
        self.assertEqual(new_log.status, InvoiceSendStatus.SENT)  # the (eager) task ran after commit
        self.assertEqual(len(mail.outbox), 1)

    def test_cannot_email_cancelled_invoice(self):
        inv = make_invoice(make_order(self.vendor_a), status=InvoiceStatus.CANCELLED)
        r = self.client_for(self.admin).post(f"/api/v1/invoices/{inv.id}/send-email/")
        self.assertEqual(r.status_code, 409)
        self.assertEqual(InvoiceSendLog.objects.count(), 0)

    def test_error_message_hidden_from_vendor_but_visible_to_staff(self):
        inv = make_invoice(make_order(self.vendor_a))
        InvoiceSendLog.objects.create(invoice=inv, recipient_email="x@y.com", status="failed", error_message="SMTP secret detail")
        vendor_view = self.client_for(self.vendor_a_user).get(f"/api/v1/invoices/{inv.id}/").data["send_logs"][0]
        admin_view = self.client_for(self.admin).get(f"/api/v1/invoices/{inv.id}/").data["send_logs"][0]
        self.assertNotIn("error_message", vendor_view)
        self.assertEqual(admin_view["error_message"], "SMTP secret detail")


def queue_invoice_email_now(invoice):
    """Create the pending log the way billing does, without the on_commit hop."""
    with mock.patch("invoices.services.transaction.on_commit"):
        return queue_invoice_email(invoice)


# ========================================================== RBAC + vendor isolation
class InvoiceAccessControlTests(BaseCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.inv_a = make_invoice(make_order(cls.vendor_a, status=OrderStatus.CLOSED))
        cls.inv_b = make_invoice(make_order(cls.vendor_b, status=OrderStatus.CLOSED))
        cls.orphan_user = make_user("orphan@erp.com", "vendor")  # vendor role, not linked to any Vendor

    def ids(self, r):
        return {row["id"] for row in r.data["results"]}

    # ---- anonymous
    def test_anonymous_gets_401_everywhere(self):
        c = self.client_for(None)
        for url in ("/api/v1/invoices/", f"/api/v1/invoices/{self.inv_a.id}/", f"/api/v1/invoices/{self.inv_a.id}/pdf/",
                    f"/api/v1/orders/{self.inv_a.order_id}/invoice.pdf"):
            self.assertEqual(c.get(url).status_code, 401, url)

    def test_garbage_token_is_rejected(self):
        c = APIClient()
        c.credentials(HTTP_AUTHORIZATION="Bearer not-a-real-token")
        self.assertEqual(c.get("/api/v1/invoices/").status_code, 401)

    def test_real_jwt_login_flow(self):
        c = APIClient()
        token = c.post("/api/v1/auth/login", {"email": "vendora@erp.com", "password": PASSWORD}).data["access_token"]
        c.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        r = c.get("/api/v1/invoices/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.ids(r), {self.inv_a.id})

    # ---- admin
    def test_admin_sees_and_downloads_all(self):
        c = self.client_for(self.admin)
        self.assertEqual(self.ids(c.get("/api/v1/invoices/")), {self.inv_a.id, self.inv_b.id})
        for inv in (self.inv_a, self.inv_b):
            self.assertEqual(c.get(f"/api/v1/invoices/{inv.id}/").status_code, 200)
            self.assertEqual(c.get(f"/api/v1/invoices/{inv.id}/pdf/").status_code, 200)

    # ---- dispatcher: read-only
    def test_dispatcher_reads_all_but_cannot_modify(self):
        c = self.client_for(self.dispatcher)
        self.assertEqual(self.ids(c.get("/api/v1/invoices/")), {self.inv_a.id, self.inv_b.id})
        self.assertEqual(c.get(f"/api/v1/invoices/{self.inv_b.id}/").status_code, 200)
        self.assertEqual(c.get(f"/api/v1/invoices/{self.inv_b.id}/pdf/").status_code, 200)
        url = f"/api/v1/invoices/{self.inv_a.id}/"
        for method in ("post", "put", "patch", "delete"):
            r = getattr(c, method)(url, {"status": "paid"}, format="json")
            self.assertIn(r.status_code, (403, 405), f"{method} -> {r.status_code}")
        self.assertEqual(c.post("/api/v1/invoices/", {}, format="json").status_code, 405)
        self.inv_a.refresh_from_db()
        self.assertEqual(self.inv_a.status, InvoiceStatus.ISSUED)

    # ---- vendor: own only
    def test_vendor_list_contains_only_own_invoices(self):
        self.assertEqual(self.ids(self.client_for(self.vendor_a_user).get("/api/v1/invoices/")), {self.inv_a.id})
        self.assertEqual(self.ids(self.client_for(self.vendor_b_user).get("/api/v1/invoices/")), {self.inv_b.id})

    def test_vendor_can_view_and_download_own(self):
        c = self.client_for(self.vendor_a_user)
        self.assertEqual(c.get(f"/api/v1/invoices/{self.inv_a.id}/").status_code, 200)
        self.assertEqual(c.get(f"/api/v1/invoices/{self.inv_a.id}/pdf/").status_code, 200)
        self.assertEqual(c.get(f"/api/v1/orders/{self.inv_a.order_id}/invoice.pdf").status_code, 200)

    def test_vendor_cannot_access_other_vendors_invoice_by_changing_the_id(self):
        c = self.client_for(self.vendor_a_user)
        for url in (f"/api/v1/invoices/{self.inv_b.id}/", f"/api/v1/invoices/{self.inv_b.id}/pdf/",
                    f"/api/v1/invoices/{self.inv_b.id}/pdf/?download=1",
                    f"/api/v1/orders/{self.inv_b.order_id}/invoice.pdf"):
            r = c.get(url)
            self.assertEqual(r.status_code, 403, url)
            self.assertNotIn(b"%PDF", r.content)
            self.assertNotIn(self.inv_b.invoice_number.encode(), r.content)

    def test_vendor_cannot_modify_own_invoice(self):
        c = self.client_for(self.vendor_a_user)
        self.assertEqual(c.post(f"/api/v1/invoices/{self.inv_a.id}/send-email/").status_code, 403)
        for method in ("put", "patch", "delete"):
            self.assertIn(getattr(c, method)(f"/api/v1/invoices/{self.inv_a.id}/", {}, format="json").status_code, (403, 405))

    def test_vendor_filter_param_cannot_widen_scope(self):
        r = self.client_for(self.vendor_a_user).get(f"/api/v1/invoices/?vendor={self.vendor_b.id}")
        self.assertEqual(r.data["count"], 0)

    def test_vendor_role_without_linked_vendor_sees_nothing(self):
        c = self.client_for(self.orphan_user)
        self.assertEqual(c.get("/api/v1/invoices/").data["count"], 0)
        self.assertEqual(c.get(f"/api/v1/invoices/{self.inv_a.id}/").status_code, 403)

    def test_unlinked_vendor_record_is_not_matched_by_unlinked_user(self):
        """None == None must not grant access: an unlinked Vendor's invoices
        are invisible to every vendor account."""
        v = make_vendor("Unlinked Co")
        inv = make_invoice(make_order(v))
        for u in (self.vendor_a_user, self.orphan_user):
            self.assertEqual(self.client_for(u).get(f"/api/v1/invoices/{inv.id}/").status_code, 403)

    # ---- driver: none
    def test_driver_has_no_invoice_access(self):
        Driver.objects.create(full_name="Raj", phone="1")
        c = self.client_for(self.driver_user)
        for url in ("/api/v1/invoices/", f"/api/v1/invoices/{self.inv_a.id}/", f"/api/v1/invoices/{self.inv_a.id}/pdf/",
                    f"/api/v1/orders/{self.inv_a.order_id}/invoice.pdf"):
            self.assertEqual(c.get(url).status_code, 403, url)

    def test_unknown_or_malformed_ids(self):
        c = self.client_for(self.admin)
        self.assertEqual(c.get("/api/v1/invoices/999999/").status_code, 404)
        self.assertEqual(c.get("/api/v1/invoices/abc/").status_code, 404)


# ============================================================== list API features
class InvoiceListApiTests(BaseCase):
    URL = "/api/v1/invoices/"

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        # 3 hand-made invoices with distinctive data...
        o1 = make_order(cls.vendor_a, customer_name="John Smith")
        o2 = make_order(cls.vendor_a, customer_name="Mary Jones", is_cod=True, cod_amount=500.0)
        o3 = make_order(cls.vendor_b, customer_name="Johnny Bravo")
        cls.i1 = make_invoice(o1, freight="1000.00", status=InvoiceStatus.ISSUED)
        cls.i2 = make_invoice(o2, freight="2000.00", tax="100.00", status=InvoiceStatus.PAID)
        cls.i3 = make_invoice(o3, freight="300.00", status=InvoiceStatus.CANCELLED)
        now = timezone.now()
        Invoice.objects.filter(pk=cls.i1.pk).update(invoice_date=now - timedelta(days=30), created_at=now - timedelta(days=30))
        Invoice.objects.filter(pk=cls.i2.pk).update(invoice_date=now - timedelta(days=10), created_at=now - timedelta(days=10))
        cls.d = lambda days: (now - timedelta(days=days)).date().isoformat()

    def get(self, qs="", user=None):
        return self.client_for(user or self.admin).get(f"{self.URL}?{qs}" if qs else self.URL)

    def ids(self, r):
        return [row["id"] for row in r.data["results"]]

    # ---- shape
    def test_list_payload(self):
        r = self.get()
        self.assertEqual(r.status_code, 200)
        self.assertEqual(set(r.data), {"count", "next", "previous", "results"})
        row = next(x for x in r.data["results"] if x["id"] == self.i2.id)
        self.assertEqual(row["invoice_number"], self.i2.invoice_number)
        self.assertEqual(row["order_number"], self.i2.order.order_number)
        self.assertEqual(row["vendor_name"], "Alpha Traders")
        self.assertEqual(row["customer_name"], "Mary Jones")
        self.assertEqual((row["freight_charge"], row["tax_amount"], row["cod_amount"], row["total_amount"]),
                         ("2000.00", "100.00", "500.00", "2600.00"))
        self.assertEqual(row["status"], "paid")

    def test_detail_payload(self):
        d = self.client_for(self.admin).get(f"{self.URL}{self.i2.id}/").data
        self.assertEqual(d["order"]["customer_name"], "Mary Jones")
        self.assertEqual(d["vendor"]["name"], "Alpha Traders")
        self.assertEqual(d["send_logs"], [])
        self.assertNotIn("@", d["created_by_name"])

    # ---- filters
    def test_individual_filters(self):
        self.assertEqual(set(self.ids(self.get("status=paid"))), {self.i2.id})
        self.assertEqual(set(self.ids(self.get("status=issued"))), {self.i1.id})
        self.assertEqual(set(self.ids(self.get(f"vendor={self.vendor_b.id}"))), {self.i3.id})
        self.assertEqual(set(self.ids(self.get("customer_name=john"))), {self.i1.id, self.i3.id})  # icontains
        self.assertEqual(set(self.ids(self.get(f"order_number={self.i1.order.order_number}"))), {self.i1.id})
        self.assertEqual(set(self.ids(self.get(f"tracking_number={self.i2.order.tracking_number}"))), {self.i2.id})
        self.assertEqual(set(self.ids(self.get(f"invoice_number={self.i3.invoice_number}"))), {self.i3.id})
        self.assertEqual(set(self.ids(self.get("min_total=2000"))), {self.i2.id})
        self.assertEqual(set(self.ids(self.get("max_total=1000"))), {self.i1.id, self.i3.id})

    def test_date_range(self):
        self.assertEqual(set(self.ids(self.get(f"created_after={self.d(15)}"))), {self.i2.id, self.i3.id})
        self.assertEqual(set(self.ids(self.get(f"created_before={self.d(15)}"))), {self.i1.id})
        self.assertEqual(set(self.ids(self.get(f"created_after={self.d(40)}&created_before={self.d(20)}"))), {self.i1.id})

    def test_multiple_filters_combined(self):
        r = self.get(f"vendor={self.vendor_a.id}&customer_name=john&status=issued&min_total=500")
        self.assertEqual(self.ids(r), [self.i1.id])

    def test_empty_result(self):
        r = self.get("status=paid&customer_name=nobody")
        self.assertEqual((r.status_code, r.data["count"], r.data["results"]), (200, 0, []))

    def test_invalid_filter_values_are_400_not_500(self):
        for qs in ("status=bogus", "created_after=not-a-date", "created_before=2024-13-45",
                   "min_total=abc", "max_total=1e999x", "vendor=abc"):
            r = self.get(qs)
            self.assertEqual(r.status_code, 400, qs)

    def test_search(self):
        self.assertEqual(set(self.ids(self.get("search=Bravo"))), {self.i3.id})
        self.assertEqual(set(self.ids(self.get(f"search={self.i1.invoice_number}"))), {self.i1.id})
        self.assertEqual(set(self.ids(self.get("search=Beta"))), {self.i3.id})  # vendor name
        self.assertEqual(self.get("search=zzzzzz").data["count"], 0)

    def test_filters_respect_rbac(self):
        r = self.get("customer_name=john", user=self.vendor_a_user)
        self.assertEqual(set(self.ids(r)), {self.i1.id})  # i3 (Johnny) belongs to vendor B

    # ---- sorting
    def test_sorting_both_syntaxes(self):
        self.assertEqual(self.ids(self.get("sort_by=total_amount&order=desc")), [self.i2.id, self.i1.id, self.i3.id])
        self.assertEqual(self.ids(self.get("sort_by=total_amount&order=asc")), [self.i3.id, self.i1.id, self.i2.id])
        self.assertEqual(self.ids(self.get("ordering=-total_amount")), [self.i2.id, self.i1.id, self.i3.id])
        self.assertEqual(self.ids(self.get("ordering=total_amount")), [self.i3.id, self.i1.id, self.i2.id])
        self.assertEqual(self.ids(self.get("sort_by=invoice_date&order=asc"))[0], self.i1.id)
        self.assertEqual(self.ids(self.get("sort_by=status&order=asc"))[0], self.i3.id)  # cancelled < issued < paid

    def test_default_sort_is_newest_first(self):
        self.assertEqual(self.ids(self.get())[0], self.i3.id)
        self.assertEqual(self.ids(self.get())[-1], self.i1.id)

    def test_invalid_sort_is_ignored_safely(self):
        for qs in ("sort_by=hack;drop&order=desc", "sort_by=order__vendor__user__password", "sort_by=total_amount&order=sideways",
                   "ordering=nonsense"):
            r = self.get(qs)
            self.assertEqual(r.status_code, 200, qs)
            self.assertEqual(r.data["count"], 3)

    def test_sort_with_filters(self):
        r = self.get("vendor=" + str(self.vendor_a.id) + "&sort_by=total_amount&order=desc")
        self.assertEqual(self.ids(r), [self.i2.id, self.i1.id])


class InvoicePaginationTests(BaseCase):
    URL = "/api/v1/invoices/"

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        # 120 invoices; deliberately all with the SAME total so paging over a
        # sort with ties must still be stable.
        for i in range(120):
            make_invoice(make_order(cls.vendor_a if i % 2 == 0 else cls.vendor_b), freight="100.00")

    def get(self, qs="", user=None):
        return self.client_for(user or self.admin).get(f"{self.URL}?{qs}")

    def test_default_page_size_is_50(self):
        r = self.get()
        self.assertEqual((r.data["count"], len(r.data["results"])), (120, 50))
        self.assertIsNone(r.data["previous"])
        self.assertIn("page=2", r.data["next"])

    def test_pages_1_2_3(self):
        sizes = [len(self.get(f"page={p}&page_size=50").data["results"]) for p in (1, 2, 3)]
        self.assertEqual(sizes, [50, 50, 20])
        last = self.get("page=3")
        self.assertIsNone(last.data["next"])
        self.assertIn("page=2", last.data["previous"])

    def test_page_size_variants(self):
        self.assertEqual(len(self.get("page_size=1").data["results"]), 1)
        self.assertEqual(self.get("page_size=1").data["count"], 120)
        self.assertEqual(len(self.get("page_size=100").data["results"]), 100)

    def test_page_size_is_capped_at_100(self):
        r = self.get("page_size=100000")
        self.assertEqual(len(r.data["results"]), 100)
        self.assertEqual(r.data["count"], 120)
        self.assertIsNotNone(r.data["next"])

    def test_invalid_page_parameters(self):
        self.assertEqual(self.get("page=0").status_code, 404)
        self.assertEqual(self.get("page=99").status_code, 404)
        self.assertEqual(self.get("page=abc").status_code, 404)
        self.assertEqual(len(self.get("page_size=abc").data["results"]), 50)  # falls back to default
        self.assertEqual(len(self.get("page_size=-5").data["results"]), 50)
        self.assertEqual(len(self.get("page_size=0").data["results"]), 50)

    def test_no_overlap_or_gaps_across_pages_even_with_ties(self):
        seen = []
        for p in (1, 2, 3):
            seen += [r["id"] for r in self.get(f"page={p}&page_size=50&sort_by=total_amount&order=desc").data["results"]]
        self.assertEqual(len(seen), 120)
        self.assertEqual(len(set(seen)), 120)

    def test_pagination_plus_filter_plus_rbac(self):
        r = self.get("page_size=10&page=2", user=self.vendor_a_user)
        self.assertEqual((r.data["count"], len(r.data["results"])), (60, 10))
        self.assertTrue(all(row["vendor_id"] == self.vendor_a.id for row in r.data["results"]))
        r = self.get(f"vendor={self.vendor_b.id}&page_size=25")
        self.assertEqual((r.data["count"], len(r.data["results"])), (60, 25))


# ===================================================================== PDF
class InvoicePdfTests(BaseCase):
    def setUp(self):
        super().setUp()
        self.order = make_order(self.vendor_a, is_cod=True, cod_amount=500.0, customer_name="Priya Nair")
        with self.captureOnCommitCallbacks(execute=True):
            self.client_for(self.admin).post(f"/api/v1/orders/{self.order.id}/close-billing?freight_charge=1234.50&tax_amount=61.73")
        self.inv = Invoice.objects.get(order=self.order)

    def pdf(self, url, user=None):
        return self.client_for(user or self.admin).get(url)

    def test_pdf_contains_stored_invoice_data(self):
        r = self.pdf(f"/api/v1/invoices/{self.inv.id}/pdf/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r["Content-Type"], "application/pdf")
        self.assertTrue(r.content.startswith(b"%PDF"))
        body = r.content
        for needle in (self.inv.invoice_number, self.order.order_number, self.order.tracking_number, "Alpha Traders",
                       "Alpha Traders Street", "Priya Nair", "Pune", "Mumbai", "1,234.50", "61.73", "500.00", "1,796.23",
                       "Issued", f"{self.inv.invoice_date:%d %b %Y}"):
            self.assertIn(needle.encode(), body, needle)
        self.assertEqual(self.inv.total_amount, Decimal("1796.23"))

    def test_pdf_is_generated_from_the_invoice_not_from_live_order_fields(self):
        """Editing the order afterwards must not change the issued invoice."""
        Order.objects.filter(pk=self.order.pk).update(freight_charge=99999.0, invoice_amount=99999.0, customer_name="Changed Name")
        body = self.pdf(f"/api/v1/invoices/{self.inv.id}/pdf/").content
        self.assertIn(b"1,234.50", body)
        self.assertIn(b"1,796.23", body)
        self.assertNotIn(b"99,999.00", body)

    def test_pdf_is_reproducible(self):
        a = self.pdf(f"/api/v1/invoices/{self.inv.id}/pdf/").content
        b = self.pdf(f"/api/v1/orders/{self.order.id}/invoice.pdf").content
        for needle in (b"1,796.23", self.inv.invoice_number.encode()):
            self.assertIn(needle, a)
            self.assertIn(needle, b)

    def test_disposition_inline_vs_download(self):
        inline = self.pdf(f"/api/v1/invoices/{self.inv.id}/pdf/")["Content-Disposition"]
        attach = self.pdf(f"/api/v1/invoices/{self.inv.id}/pdf/?download=1")["Content-Disposition"]
        self.assertTrue(inline.startswith("inline;"))
        self.assertTrue(attach.startswith("attachment;"))
        self.assertIn(f'{self.inv.invoice_number}.pdf', attach)

    def test_legacy_order_pdf_endpoint_permissions(self):
        url = f"/api/v1/orders/{self.order.id}/invoice.pdf"
        self.assertEqual(self.pdf(url).status_code, 200)
        self.assertEqual(self.pdf(url, self.dispatcher).status_code, 200)
        self.assertEqual(self.pdf(url, self.vendor_a_user).status_code, 200)
        self.assertEqual(self.pdf(url, self.vendor_b_user).status_code, 403)
        self.assertEqual(self.pdf(url, self.driver_user).status_code, 403)
        self.assertEqual(self.client_for(None).get(url).status_code, 401)

    def test_legacy_endpoint_keeps_409_for_unbilled_order_but_does_not_leak_it_to_strangers(self):
        pending = make_order(self.vendor_a, status=OrderStatus.OUT_FOR_DELIVERY)
        url = f"/api/v1/orders/{pending.id}/invoice.pdf"
        r = self.pdf(url)
        self.assertEqual((r.status_code, r.data["detail"]), (409, "Invoice is only available after the order is closed and billed"))
        self.assertEqual(self.pdf(url, self.vendor_b_user).status_code, 403)  # not 409: state of others' orders is not revealed

    def test_closed_order_without_invoice_record_is_404_not_500(self):
        legacy = make_order(self.vendor_a, status=OrderStatus.CLOSED)
        self.assertEqual(self.pdf(f"/api/v1/orders/{legacy.id}/invoice.pdf").status_code, 404)

    def test_cancelled_invoice_pdf_is_marked(self):
        Invoice.objects.filter(pk=self.inv.pk).update(status=InvoiceStatus.CANCELLED)
        body = self.pdf(f"/api/v1/invoices/{self.inv.id}/pdf/").content
        self.assertIn(b"CANCELLED", body)
        self.assertIn(b"Cancelled", body)


# ====================================================== backfill data migration
class BackfillMigrationTests(TransactionTestCase):
    """Orders billed BEFORE this module existed get an Invoice row."""

    def test_closed_orders_are_backfilled_and_rerun_is_safe(self):
        executor = MigrationExecutor(connection)
        before = [("invoices", "0001_initial"), ("vendors", "0002_vendor_user_email")]
        executor.migrate(before)  # roll invoices back to before the data migration
        apps = executor.loader.project_state(before).apps
        HVendor, HOrder, HInvoice = apps.get_model("vendors", "Vendor"), apps.get_model("orders", "Order"), apps.get_model("invoices", "Invoice")

        v = HVendor.objects.create(name="Legacy Vendor", contact_phone="1", address="x")
        closed = HOrder.objects.create(order_number="ORD-AAAA1111", tracking_number="T1", vendor=v, customer_name="c",
                                       customer_phone="1", delivery_address="a", status="closed", is_cod=True, cod_amount=250.0,
                                       freight_charge=800.5, invoice_number="INV-AAAA1111", invoice_amount=1050.5)
        HOrder.objects.create(order_number="ORD-BBBB2222", tracking_number="T2", vendor=v, customer_name="c",
                              customer_phone="1", delivery_address="a", status="delivered")
        no_number = HOrder.objects.create(order_number="ORD-CCCC3333", tracking_number="T3", vendor=v, customer_name="c",
                                          customer_phone="1", delivery_address="a", status="closed", freight_charge=10.0, invoice_amount=10.0)
        self.assertEqual(HInvoice.objects.count(), 0)

        executor = MigrationExecutor(connection)
        executor.migrate([("invoices", "0002_backfill_closed_orders")])

        latest = MigrationExecutor(connection).loader.project_state([("invoices", "0002_backfill_closed_orders")]).apps
        inv_model = latest.get_model("invoices", "Invoice")
        self.assertEqual(inv_model.objects.count(), 2)  # delivered order untouched
        inv = inv_model.objects.get(order_id=closed.pk)
        self.assertEqual(inv.invoice_number, "INV-AAAA1111")
        self.assertEqual((inv.freight_charge, inv.cod_amount, inv.tax_amount, inv.total_amount),
                         (Decimal("800.50"), Decimal("250.00"), Decimal("0.00"), Decimal("1050.50")))
        self.assertEqual(inv.status, "issued")
        self.assertEqual(inv.invoice_date, closed.updated_at)  # real billing time preserved
        self.assertEqual(inv_model.objects.get(order_id=no_number.pk).invoice_number, "INV-CCCC3333")

        # re-applying the function is a no-op
        from importlib import import_module
        import_module("invoices.migrations.0002_backfill_closed_orders").backfill(latest, None)
        self.assertEqual(inv_model.objects.count(), 2)
