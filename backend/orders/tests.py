"""Tests for RBAC across all API endpoints and Order notification system.

Run with:  python manage.py test orders notifications
No Redis, SMTP or network needed: Celery runs eagerly, email backend is locmem.
"""
from unittest import mock

from django.core import mail
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from accounts.models import User
from fleet.models import Driver
from invoices.models import Invoice, InvoiceStatus
from invoices.services import generate_invoice_number
from notifications.models import Notification, NotificationStatus
from orders.models import Order, OrderStatus
from vendors.models import Vendor

from decimal import Decimal

PASSWORD = "pass1234"


# ----------------------------------------------------------------------- helpers
def make_user(email, role):
    return User.objects.create_user(email=email, password=PASSWORD, role=role, full_name=email.split("@")[0].title())


def make_vendor(name, user=None, email="", phone="9000000000"):
    return Vendor.objects.create(name=name, contact_phone=phone, address=f"{name} Street", user=user, email=email)


def make_order(vendor, status=OrderStatus.ORDER_RECEIVED, driver=None, **kw):
    kw.setdefault("customer_name", "Test Customer")
    kw.setdefault("customer_phone", "9876543210")
    kw.setdefault("delivery_address", "12 Test Rd")
    kw.setdefault("origin_city", "Pune")
    kw.setdefault("destination_city", "Mumbai")
    kw.setdefault("weight_kg", 2.0)
    return Order.objects.create(vendor=vendor, status=status, driver=driver, **kw)


def make_invoice(order, freight="1000.00", status=InvoiceStatus.ISSUED):
    f = Decimal(freight)
    return Invoice.objects.create(
        order=order, invoice_number=generate_invoice_number(order),
        freight_charge=f, total_amount=f, status=status,
    )


def c(user=None):
    client = APIClient()
    if user:
        client.force_authenticate(user=user)
    return client


@override_settings(CELERY_TASK_ALWAYS_EAGER=True)
class BaseRBACCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = make_user("admin@erp.com", "admin")
        cls.dispatcher = make_user("dispatcher@erp.com", "dispatcher")
        cls.driver_user = make_user("driver@erp.com", "driver")
        cls.vendor_a_user = make_user("vendora@erp.com", "vendor")
        cls.vendor_b_user = make_user("vendorb@erp.com", "vendor")
        cls.vendor_a = make_vendor("Alpha Traders", cls.vendor_a_user, email="vendora@erp.com")
        cls.vendor_b = make_vendor("Beta Foods", cls.vendor_b_user, email="vendorb@erp.com")


# ================================================================ ORDER RBAC
@override_settings(CELERY_TASK_ALWAYS_EAGER=True)
class OrderRBACTests(BaseRBACCase):

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.driver = Driver.objects.create(full_name="Driver Dave", phone="9888877777", user=cls.driver_user)
        cls.order_a = make_order(cls.vendor_a, status=OrderStatus.ORDER_RECEIVED)
        cls.order_b = make_order(cls.vendor_b, status=OrderStatus.ORDER_RECEIVED)
        cls.order_driver = make_order(cls.vendor_a, status=OrderStatus.OUT_FOR_DELIVERY, driver=cls.driver)

    # --- anonymous
    def test_anonymous_cannot_list_orders(self):
        self.assertEqual(c().get("/api/v1/orders/").status_code, 401)

    def test_anonymous_cannot_create_order(self):
        self.assertEqual(c().post("/api/v1/orders/", {}, format="json").status_code, 401)

    # --- admin
    def test_admin_can_list_all_orders(self):
        r = c(self.admin).get("/api/v1/orders/")
        self.assertEqual(r.status_code, 200)
        ids = {row["id"] for row in r.data["results"]}
        self.assertIn(self.order_a.id, ids)
        self.assertIn(self.order_b.id, ids)

    def test_admin_can_create_order(self):
        r = c(self.admin).post("/api/v1/orders/", {
            "vendor_id": self.vendor_a.id, "customer_name": "Admin Test",
            "customer_phone": "1111111111", "delivery_address": "Addr",
        }, format="json")
        self.assertEqual(r.status_code, 201)

    # --- dispatcher
    def test_dispatcher_can_list_and_view_all_orders(self):
        r = c(self.dispatcher).get("/api/v1/orders/")
        self.assertEqual(r.status_code, 200)
        self.assertGreaterEqual(r.data["count"], 2)

    def test_dispatcher_can_create_order(self):
        r = c(self.dispatcher).post("/api/v1/orders/", {
            "vendor_id": self.vendor_b.id, "customer_name": "Dispatcher Test",
            "customer_phone": "2222222222", "delivery_address": "Addr 2",
        }, format="json")
        self.assertEqual(r.status_code, 201)

    # --- vendor
    def test_vendor_sees_only_own_orders(self):
        r = c(self.vendor_a_user).get("/api/v1/orders/")
        self.assertEqual(r.status_code, 200)
        ids = {row["id"] for row in r.data["results"]}
        self.assertIn(self.order_a.id, ids)
        self.assertNotIn(self.order_b.id, ids)

    def test_vendor_can_create_own_order(self):
        r = c(self.vendor_a_user).post("/api/v1/orders/", {
            "vendor_id": self.vendor_a.id, "customer_name": "Vendor Test",
            "customer_phone": "3333333333", "delivery_address": "Addr 3",
        }, format="json")
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.data["vendor_id"], self.vendor_a.id)

    def test_vendor_order_forced_to_own_vendor_id(self):
        # Even if vendor specifies another vendor_id, it is forced to their own vendor profile
        r = c(self.vendor_a_user).post("/api/v1/orders/", {
            "vendor_id": self.vendor_b.id, "customer_name": "Vendor Test 2",
            "customer_phone": "3333333333", "delivery_address": "Addr 4",
        }, format="json")
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.data["vendor_id"], self.vendor_a.id)

    def test_vendor_cannot_access_other_vendor_order(self):
        r = c(self.vendor_a_user).get(f"/api/v1/orders/{self.order_b.id}")
        self.assertEqual(r.status_code, 403)

    # --- driver
    def test_driver_sees_only_assigned_orders(self):
        r = c(self.driver_user).get("/api/v1/orders/")
        self.assertEqual(r.status_code, 200)
        ids = {row["id"] for row in r.data["results"]}
        self.assertIn(self.order_driver.id, ids)
        self.assertNotIn(self.order_a.id, ids)
        self.assertNotIn(self.order_b.id, ids)

    def test_driver_order_detail_access(self):
        # Driver can view assigned order
        r_assigned = c(self.driver_user).get(f"/api/v1/orders/{self.order_driver.id}")
        self.assertEqual(r_assigned.status_code, 200)
        # Driver cannot view unassigned / other driver's order
        r_other = c(self.driver_user).get(f"/api/v1/orders/{self.order_a.id}")
        self.assertEqual(r_other.status_code, 403)

    def test_driver_cannot_create_order(self):
        r = c(self.driver_user).post("/api/v1/orders/", {}, format="json")
        self.assertEqual(r.status_code, 403)


# ================================================================ ORDER FILTERING
@override_settings(CELERY_TASK_ALWAYS_EAGER=True)
class OrderFilterTests(BaseRBACCase):

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.o1 = make_order(cls.vendor_a, status=OrderStatus.DELIVERED, customer_name="Alice Smith",
                            customer_phone="9000000001", is_cod=True, cod_amount=500.0)
        cls.o2 = make_order(cls.vendor_a, status=OrderStatus.ORDER_RECEIVED, customer_name="Bob Jones",
                            customer_phone="9000000002")
        cls.o3 = make_order(cls.vendor_b, status=OrderStatus.DELIVERED, customer_name="Alice Brown",
                            customer_phone="9000000003")

    def get(self, qs="", user=None):
        url = f"/api/v1/orders/?{qs}" if qs else "/api/v1/orders/"
        return c(user or self.admin).get(url)

    def ids(self, r):
        return {row["id"] for row in r.data["results"]}

    def test_list_has_pagination_envelope(self):
        r = self.get()
        self.assertEqual(r.status_code, 200)
        self.assertIn("count", r.data)
        self.assertIn("results", r.data)

    def test_filter_by_customer_name(self):
        result = self.ids(self.get("customer_name=alice"))
        self.assertIn(self.o1.id, result)
        self.assertIn(self.o3.id, result)

    def test_filter_by_customer_phone(self):
        self.assertEqual(self.ids(self.get("customer_phone=9000000001")), {self.o1.id})

    def test_filter_by_tracking_number(self):
        r = self.get(f"tracking_number={self.o1.tracking_number}")
        self.assertIn(self.o1.id, self.ids(r))

    def test_filter_by_status(self):
        delivered_ids = self.ids(self.get("status=delivered"))
        self.assertIn(self.o1.id, delivered_ids)
        self.assertIn(self.o3.id, delivered_ids)
        self.assertNotIn(self.o2.id, delivered_ids)

    def test_filter_by_cod(self):
        self.assertIn(self.o1.id, self.ids(self.get("is_cod=true")))
        self.assertNotIn(self.o2.id, self.ids(self.get("is_cod=true")))

    def test_filter_by_vendor(self):
        self.assertEqual(self.ids(self.get(f"vendor={self.vendor_b.id}")), {self.o3.id})

    def test_combined_filters(self):
        r = self.get("customer_name=alice&status=delivered")
        self.assertIn(self.o1.id, self.ids(r))
        self.assertIn(self.o3.id, self.ids(r))

    def test_search_by_order_number(self):
        r = self.get(f"search={self.o1.order_number}")
        self.assertIn(self.o1.id, self.ids(r))

    def test_sorting_by_customer_name_asc(self):
        r = self.get("sort_by=customer_name&order=asc")
        self.assertEqual(r.status_code, 200)
        names = [row["customer_name"] for row in r.data["results"]]
        self.assertEqual(names, sorted(names))

    def test_vendor_filter_scope(self):
        r = self.get(f"vendor={self.vendor_b.id}", user=self.vendor_a_user)
        # Vendor A cannot see vendor B orders
        self.assertEqual(r.data["count"], 0)

    def test_page_size_param(self):
        r = self.get("page_size=5")
        self.assertLessEqual(len(r.data["results"]), 5)

    def test_page_size_capped_at_100(self):
        r = self.get("page_size=999")
        self.assertLessEqual(len(r.data["results"]), 100)

    def test_filter_by_date_range(self):
        r = self.get("created_after=2020-01-01&created_before=2035-01-01")
        self.assertEqual(r.status_code, 200)
        self.assertGreaterEqual(r.data["count"], 1)

    def test_filter_empty_results(self):
        r = self.get("customer_name=nonexistent_xyz_name")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["count"], 0)
        self.assertEqual(len(r.data["results"]), 0)

    def test_filter_combined_with_pagination(self):
        r = self.get("status=delivered&page=1&page_size=1")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["count"], 2)
        self.assertEqual(len(r.data["results"]), 1)
        self.assertIsNotNone(r.data["next"])


# ================================================================ VENDOR RBAC
class VendorRBACTests(BaseRBACCase):

    def test_anonymous_blocked(self):
        self.assertEqual(c().get("/api/v1/vendors/").status_code, 401)

    def test_admin_sees_all_vendors(self):
        r = c(self.admin).get("/api/v1/vendors/")
        self.assertEqual(r.status_code, 200)
        results = r.data.get("results", r.data)
        ids = {row["id"] for row in results}
        self.assertIn(self.vendor_a.id, ids)
        self.assertIn(self.vendor_b.id, ids)

    def test_vendor_sees_only_own_record(self):
        r = c(self.vendor_a_user).get("/api/v1/vendors/")
        self.assertEqual(r.status_code, 200)
        results = r.data.get("results", r.data)
        ids = {row["id"] for row in results}
        self.assertIn(self.vendor_a.id, ids)
        self.assertNotIn(self.vendor_b.id, ids)

    def test_vendor_cannot_create(self):
        r = c(self.vendor_a_user).post("/api/v1/vendors/", {"name": "Hacker Corp", "contact_phone": "0", "address": "x"}, format="json")
        self.assertEqual(r.status_code, 403)

    def test_driver_blocked_from_vendors(self):
        self.assertEqual(c(self.driver_user).get("/api/v1/vendors/").status_code, 403)

    def test_dispatcher_can_read_all(self):
        r = c(self.dispatcher).get("/api/v1/vendors/")
        self.assertEqual(r.status_code, 200)
        results = r.data.get("results", r.data)
        ids = {row["id"] for row in results}
        self.assertIn(self.vendor_a.id, ids)

    def test_dispatcher_cannot_create_vendor(self):
        r = c(self.dispatcher).post("/api/v1/vendors/", {"name": "New Co", "contact_phone": "111", "address": "New St"}, format="json")
        self.assertEqual(r.status_code, 403)

    def test_admin_can_create_vendor(self):
        r = c(self.admin).post("/api/v1/vendors/", {"name": "New Co", "contact_phone": "111", "address": "New St"}, format="json")
        self.assertEqual(r.status_code, 201)

    def test_admin_can_link_vendor_to_user(self):
        new_user = make_user("vendorlink@erp.com", "vendor")
        r = c(self.admin).post(f"/api/v1/vendors/{self.vendor_a.id}/link_user/", {"user_id": new_user.id}, format="json")
        self.assertEqual(r.status_code, 200)
        self.vendor_a.refresh_from_db()
        self.assertEqual(self.vendor_a.user_id, new_user.id)

    def test_dispatcher_cannot_link_vendor_to_user(self):
        new_user = make_user("vendorlink2@erp.com", "vendor")
        r = c(self.dispatcher).post(f"/api/v1/vendors/{self.vendor_a.id}/link_user/", {"user_id": new_user.id}, format="json")
        self.assertEqual(r.status_code, 403)


# ================================================================ FLEET RBAC
class FleetRBACTests(BaseRBACCase):

    def test_anonymous_blocked(self):
        self.assertEqual(c().get("/api/v1/fleet/drivers").status_code, 401)

    def test_admin_can_list_drivers(self):
        r = c(self.admin).get("/api/v1/fleet/drivers")
        self.assertEqual(r.status_code, 200)

    def test_dispatcher_can_list_drivers(self):
        r = c(self.dispatcher).get("/api/v1/fleet/drivers")
        self.assertEqual(r.status_code, 200)

    def test_driver_can_list_drivers_sees_only_self(self):
        d1 = Driver.objects.create(full_name="Driver Self", phone="9111111111", user=self.driver_user)
        d2 = Driver.objects.create(full_name="Driver Other", phone="9222222222")
        r = c(self.driver_user).get("/api/v1/fleet/drivers")
        self.assertEqual(r.status_code, 200)
        results = r.data.get("results", r.data)
        ids = {row["id"] for row in results}
        self.assertIn(d1.id, ids)
        self.assertNotIn(d2.id, ids)

    def test_driver_can_only_update_own_location(self):
        d1 = Driver.objects.create(full_name="Driver Location 1", phone="9333333333", user=self.driver_user)
        d2 = Driver.objects.create(full_name="Driver Location 2", phone="9444444444")
        r_own = c(self.driver_user).patch(f"/api/v1/fleet/drivers/{d1.id}/location", {"latitude": 19.1, "longitude": 72.8}, format="json")
        self.assertEqual(r_own.status_code, 200)
        r_other = c(self.driver_user).patch(f"/api/v1/fleet/drivers/{d2.id}/location", {"latitude": 19.1, "longitude": 72.8}, format="json")
        self.assertEqual(r_other.status_code, 403)

    def test_vendor_blocked_from_fleet(self):
        self.assertEqual(c(self.vendor_a_user).get("/api/v1/fleet/drivers").status_code, 403)

    def test_dispatcher_cannot_create_driver(self):
        r = c(self.dispatcher).post("/api/v1/fleet/drivers", {"full_name": "Test Driver", "phone": "9999999999"}, format="json")
        self.assertEqual(r.status_code, 403)

    def test_admin_can_create_driver(self):
        r = c(self.admin).post("/api/v1/fleet/drivers", {"full_name": "New Driver", "phone": "8888888888"}, format="json")
        self.assertEqual(r.status_code, 201)


# ================================================================ INVENTORY RBAC
class InventoryRBACTests(BaseRBACCase):

    def test_anonymous_blocked(self):
        self.assertEqual(c().get("/api/v1/inventory/warehouses").status_code, 401)

    def test_admin_can_list_warehouses(self):
        r = c(self.admin).get("/api/v1/inventory/warehouses")
        self.assertEqual(r.status_code, 200)

    def test_vendor_can_read_inventory(self):
        r = c(self.vendor_a_user).get("/api/v1/inventory/items")
        self.assertEqual(r.status_code, 200)

    def test_driver_blocked_from_inventory(self):
        self.assertEqual(c(self.driver_user).get("/api/v1/inventory/items").status_code, 403)

    def test_vendor_cannot_create_inventory_item(self):
        r = c(self.vendor_a_user).post("/api/v1/inventory/items", {}, format="json")
        self.assertEqual(r.status_code, 403)


# ================================================================ DASHBOARD RBAC
class DashboardRBACTests(BaseRBACCase):

    def test_anonymous_blocked(self):
        self.assertEqual(c().get("/api/v1/dashboard/stats").status_code, 401)

    def test_admin_can_access_dashboard(self):
        r = c(self.admin).get("/api/v1/dashboard/stats")
        self.assertEqual(r.status_code, 200)
        self.assertIn("total_orders", r.data)

    def test_dispatcher_can_access_dashboard(self):
        r = c(self.dispatcher).get("/api/v1/dashboard/stats")
        self.assertEqual(r.status_code, 200)

    def test_vendor_gets_scoped_dashboard(self):
        make_order(self.vendor_a, status=OrderStatus.DELIVERED)
        r = c(self.vendor_a_user).get("/api/v1/dashboard/stats")
        self.assertEqual(r.status_code, 200)
        self.assertIn("total_orders", r.data)

    def test_driver_can_access_own_dashboard(self):
        r = c(self.driver_user).get("/api/v1/dashboard/stats")
        self.assertEqual(r.status_code, 200)
        self.assertIn("total_orders", r.data)


# ================================================================ DISPATCH RBAC
class DispatchRBACTests(BaseRBACCase):

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.order = make_order(cls.vendor_a, status=OrderStatus.ROUTE_PLANNED,
                               delivery_lat=19.0, delivery_lng=72.0)

    def test_anonymous_blocked(self):
        r = c().post(f"/api/v1/dispatch/orders/{self.order.id}/assign")
        self.assertEqual(r.status_code, 401)

    def test_vendor_blocked(self):
        r = c(self.vendor_a_user).post(f"/api/v1/dispatch/orders/{self.order.id}/assign")
        self.assertEqual(r.status_code, 403)

    def test_driver_blocked(self):
        r = c(self.driver_user).post(f"/api/v1/dispatch/orders/{self.order.id}/assign")
        self.assertEqual(r.status_code, 403)

    def test_admin_can_dispatch(self):
        # No available drivers → 409, but auth passes
        r = c(self.admin).post(f"/api/v1/dispatch/orders/{self.order.id}/assign")
        self.assertIn(r.status_code, [200, 409])

    def test_dispatcher_can_dispatch(self):
        r = c(self.dispatcher).post(f"/api/v1/dispatch/orders/{self.order.id}/assign")
        self.assertIn(r.status_code, [200, 409])


# ================================================================ INVOICE STATUS MANAGEMENT
class InvoiceStatusManagementTests(BaseRBACCase):

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.order = make_order(cls.vendor_a, status=OrderStatus.CLOSED)
        cls.invoice = make_invoice(cls.order, status=InvoiceStatus.DRAFT)

    def _patch_status(self, user, new_status):
        return c(user).patch(
            f"/api/v1/invoices/{self.invoice.id}/update-status/",
            {"status": new_status},
            format="json",
        )

    def test_admin_can_advance_draft_to_issued(self):
        self.invoice.status = InvoiceStatus.DRAFT
        self.invoice.save()
        r = self._patch_status(self.admin, "issued")
        self.assertEqual(r.status_code, 200)
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.status, InvoiceStatus.ISSUED)

    def test_admin_can_advance_issued_to_paid(self):
        self.invoice.status = InvoiceStatus.ISSUED
        self.invoice.save()
        r = self._patch_status(self.admin, "paid")
        self.assertEqual(r.status_code, 200)
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.status, InvoiceStatus.PAID)

    def test_admin_can_cancel(self):
        self.invoice.status = InvoiceStatus.ISSUED
        self.invoice.save()
        r = self._patch_status(self.admin, "cancelled")
        self.assertEqual(r.status_code, 200)
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.status, InvoiceStatus.CANCELLED)

    def test_invalid_transition_rejected(self):
        self.invoice.status = InvoiceStatus.DRAFT
        self.invoice.save()
        r = self._patch_status(self.admin, "paid")  # draft → paid not allowed
        self.assertEqual(r.status_code, 409)

    def test_cancelled_is_terminal(self):
        self.invoice.status = InvoiceStatus.CANCELLED
        self.invoice.save()
        r = self._patch_status(self.admin, "issued")
        self.assertEqual(r.status_code, 409)

    def test_dispatcher_cannot_change_status(self):
        r = self._patch_status(self.dispatcher, "issued")
        self.assertEqual(r.status_code, 403)

    def test_vendor_cannot_change_status(self):
        r = self._patch_status(self.vendor_a_user, "issued")
        self.assertIn(r.status_code, [403])

    def test_driver_cannot_change_status(self):
        r = self._patch_status(self.driver_user, "issued")
        self.assertEqual(r.status_code, 403)

    def test_anonymous_cannot_change_status(self):
        r = c().patch(f"/api/v1/invoices/{self.invoice.id}/update-status/", {"status": "issued"}, format="json")
        self.assertEqual(r.status_code, 401)


# ================================================================ NOTIFICATION SYSTEM
@override_settings(
    CELERY_TASK_ALWAYS_EAGER=True,
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    SMS_BACKEND="log",
)
class OrderNotificationTests(BaseRBACCase):

    def test_notification_idempotency(self):
        """Triggering the same notification twice does not create duplicates."""
        from notifications.tasks import send_order_notification
        order = make_order(self.vendor_a, status=OrderStatus.DELIVERED)
        send_order_notification.apply(args=[order.pk, "delivered"])
        send_order_notification.apply(args=[order.pk, "delivered"])
        count = Notification.objects.filter(order=order, order_status="delivered").count()
        # Should have at most 1 row (email only for delivered)
        self.assertLessEqual(count, 1)

    def test_no_notification_for_unlisted_status(self):
        """Status not in matrix fires no notification."""
        from notifications.tasks import send_order_notification
        order = make_order(self.vendor_a)
        result = send_order_notification.apply(args=[order.pk, "label_verified"])
        self.assertEqual(result.result, "no-notification-for-status")

    def test_booking_planned_notification_created(self):
        """BOOKING_PLANNED status sends email notification."""
        from notifications.tasks import send_order_notification
        order = make_order(self.vendor_a, status=OrderStatus.BOOKING_PLANNED)
        send_order_notification.apply(args=[order.pk, "booking_planned"])
        notif = Notification.objects.filter(order=order, order_status="booking_planned", channel="email").first()
        self.assertIsNotNone(notif)

    def test_delivery_failed_notifies_dispatcher(self):
        """DELIVERY_FAILED sends email to dispatcher."""
        from notifications.tasks import send_order_notification
        order = make_order(self.vendor_a, status=OrderStatus.DELIVERY_FAILED)
        with self.settings(DISPATCHER_NOTIFICATION_EMAIL="dispatcher@test.com"):
            send_order_notification.apply(args=[order.pk, "delivery_failed"])
        notif = Notification.objects.filter(order=order, order_status="delivery_failed", channel="email").first()
        self.assertIsNotNone(notif)
        self.assertEqual(notif.status, NotificationStatus.SENT)

    def test_sms_notification_created_for_out_for_delivery(self):
        """OUT_FOR_DELIVERY creates both email and sms notification rows."""
        from notifications.tasks import send_order_notification
        order = make_order(self.vendor_a, status=OrderStatus.OUT_FOR_DELIVERY)
        send_order_notification.apply(args=[order.pk, "out_for_delivery"])
        channels = list(Notification.objects.filter(order=order, order_status="out_for_delivery").values_list("channel", flat=True))
        self.assertIn("sms", channels)
        self.assertIn("email", channels)

    def test_no_email_if_no_recipient(self):
        """Vendor without email → notification skipped gracefully."""
        from notifications.tasks import send_order_notification
        vendor_no_email = make_vendor("No Email Vendor", user=None, email="", phone="9000000001")
        order = make_order(vendor_no_email, status=OrderStatus.DELIVERED)
        send_order_notification.apply(args=[order.pk, "delivered"])
        notif = Notification.objects.filter(order=order, order_status="delivered", channel="email").first()
        self.assertIsNotNone(notif)
        self.assertIn(notif.status, [NotificationStatus.SKIPPED, NotificationStatus.FAILED])

    def test_smtp_failure_marks_notification_failed(self):
        """SMTP errors are caught; order update still succeeds."""
        from notifications.tasks import send_order_notification
        order = make_order(self.vendor_a, status=OrderStatus.DELIVERED)
        # Must patch the reference *inside* the notifications.tasks module, not
        # the original django.core.mail.send_mail, because the task already
        # holds a direct reference to it via "from django.core.mail import send_mail".
        with mock.patch("notifications.tasks.send_mail", side_effect=OSError("smtp down")):
            # override_task_always_eager is already True from the test settings;
            # apply() forces synchronous inline execution with no Celery broker.
            # We also force max_retries=0 so the task fails immediately (not retries).
            send_order_notification.apply(args=[order.pk, "delivered"], kwargs={}, retries=3)
        notif = Notification.objects.filter(order=order, order_status="delivered", channel="email").first()
        self.assertIsNotNone(notif)
        self.assertEqual(notif.status, NotificationStatus.FAILED)
        self.assertIn("smtp down", notif.error_message)

    def test_reattempt_triggers_out_for_delivery_notification(self):
        """Calling /orders/{id}/reattempt transitions to OUT_FOR_DELIVERY and queues notifications."""
        order = make_order(self.vendor_a, status=OrderStatus.DELIVERY_FAILED)
        r = c(self.admin).post(f"/api/v1/orders/{order.id}/reattempt")
        self.assertEqual(r.status_code, 200)
        order.refresh_from_db()
        self.assertEqual(order.status, OrderStatus.OUT_FOR_DELIVERY)
        notifs = list(Notification.objects.filter(order=order, order_status="out_for_delivery"))
        self.assertGreaterEqual(len(notifs), 1)

    def test_notification_message_content_and_recipient_fields(self):
        """Notification record has populated message with weight, address, and recipient info."""
        from notifications.tasks import send_order_notification
        order = make_order(self.vendor_a, status=OrderStatus.OUT_FOR_DELIVERY, customer_email="cust@erp.com")
        send_order_notification.apply(args=[order.pk, "out_for_delivery"])
        notif = Notification.objects.filter(order=order, order_status="out_for_delivery", channel="email").first()
        self.assertIsNotNone(notif)
        self.assertEqual(notif.recipient_email, "cust@erp.com")
        self.assertTrue(len(notif.subject) > 0)
        self.assertTrue(len(notif.message) > 0)

    def test_notifications_list_api_and_order_notifications_api(self):
        """API endpoints for listing notifications are functional and scoped."""
        order = make_order(self.vendor_a, status=OrderStatus.DELIVERED)
        from notifications.tasks import send_order_notification
        send_order_notification.apply(args=[order.pk, "delivered"])

        # Order specific notifications
        r_order = c(self.admin).get(f"/api/v1/orders/{order.id}/notifications")
        self.assertEqual(r_order.status_code, 200)
        self.assertIn("results", r_order.data)
        self.assertGreaterEqual(r_order.data["count"], 1)

        # Global notifications list
        r_global = c(self.admin).get("/api/v1/notifications/")
        self.assertEqual(r_global.status_code, 200)
        self.assertIn("results", r_global.data)
        self.assertGreaterEqual(r_global.data["count"], 1)


class OrderInvoiceLinkTests(BaseRBACCase):
    def test_order_serialized_with_invoice_id(self):
        order_with_inv = make_order(self.vendor_a, status=OrderStatus.CLOSED)
        inv = make_invoice(order_with_inv)
        order_without_inv = make_order(self.vendor_a, status=OrderStatus.CLOSED)

        # Detail endpoint
        res = c(self.admin).get(f"/api/v1/orders/{order_with_inv.id}")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["invoice_id"], inv.id)

        res_no_inv = c(self.admin).get(f"/api/v1/orders/{order_without_inv.id}")
        self.assertEqual(res_no_inv.status_code, 200)
        self.assertIsNone(res_no_inv.data["invoice_id"])

        # Filter invoices by order_id
        inv_res = c(self.admin).get(f"/api/v1/invoices/?order_id={order_with_inv.id}")
        self.assertEqual(inv_res.status_code, 200)
        self.assertEqual(inv_res.data["count"], 1)
        self.assertEqual(inv_res.data["results"][0]["id"], inv.id)

        inv_res_empty = c(self.admin).get(f"/api/v1/invoices/?order_id={order_without_inv.id}")
        self.assertEqual(inv_res_empty.status_code, 200)
        self.assertEqual(inv_res_empty.data["count"], 0)


class SecurityAndPublicEndpointTests(BaseRBACCase):

    def test_registration_cannot_create_admin(self):
        """Public registration rejects role=admin."""
        r = c().post("/api/v1/auth/register/", {
            "email": "hacker_admin@erp.com",
            "password": PASSWORD,
            "full_name": "Hacker Admin",
            "role": "admin",
        }, format="json")
        self.assertEqual(r.status_code, 400)

    def test_registration_public_role_default(self):
        """Public registration defaults to vendor/allowed roles."""
        r = c().post("/api/v1/auth/register/", {
            "email": "newuser@erp.com",
            "password": PASSWORD,
            "full_name": "New User",
        }, format="json")
        self.assertEqual(r.status_code, 201)
        created = User.objects.get(email="newuser@erp.com")
        self.assertNotEqual(created.role, "admin")

    def test_public_track_endpoint_is_trimmed(self):
        """Public track endpoint returns safe tracking info only and no sensitive internal fields."""
        order = make_order(
            self.vendor_a,
            status=OrderStatus.OUT_FOR_DELIVERY,
            freight_charge=Decimal("450.00"),
            customer_phone="9988776655",
            delivery_address="Secret Home Address 42",
        )
        r = c().get(f"/api/v1/orders/track/{order.tracking_number}")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["tracking_number"], order.tracking_number)
        self.assertEqual(r.data["status"], OrderStatus.OUT_FOR_DELIVERY)
        self.assertIn("origin_city", r.data)
        self.assertIn("destination_city", r.data)
        self.assertNotIn("customer_phone", r.data)
        self.assertNotIn("freight_charge", r.data)
        self.assertNotIn("delivery_address", r.data)

    def test_cannot_delete_invoice_for_closed_order(self):
        """Admin cannot delete an invoice for a closed order."""
        order = make_order(self.vendor_a, status=OrderStatus.CLOSED)
        inv = make_invoice(order)
        r = c(self.admin).delete(f"/api/v1/invoices/{inv.id}/")
        self.assertEqual(r.status_code, 400)
        self.assertTrue(Invoice.objects.filter(id=inv.id).exists())

