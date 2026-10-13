from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from notifications.models import Notification, NotificationChannel, NotificationStatus
from notifications.tasks import send_order_notification
from orders.models import Order, OrderEvent, OrderStatus
from vendors.models import Vendor

User = get_user_model()


class VendorEmailMilestoneNotificationTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            email="admin@test.com", password="password123", role="admin"
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.admin)

    def test_vendor_create_and_update_with_email(self):
        """Vendor email can be created, saved, retrieved, and updated via API."""
        # 1. Create vendor with email
        payload = {
            "name": "Acme Supplies",
            "email": "acme@example.com",
            "contact_phone": "9876543210",
            "address": "123 Industrial Way",
        }
        r = self.client.post("/api/v1/vendors/", payload, format="json")
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        self.assertEqual(r.data["email"], "acme@example.com")
        vendor_id = r.data["id"]

        vendor = Vendor.objects.get(pk=vendor_id)
        self.assertEqual(vendor.email, "acme@example.com")
        self.assertEqual(vendor.billing_email, "acme@example.com")

        # 2. Update vendor email
        r_update = self.client.patch(
            f"/api/v1/vendors/{vendor_id}/",
            {"email": "updated@example.com"},
            format="json",
        )
        self.assertEqual(r_update.status_code, status.HTTP_200_OK)
        self.assertEqual(r_update.data["email"], "updated@example.com")

        vendor.refresh_from_db()
        self.assertEqual(vendor.email, "updated@example.com")

    def test_order_received_notification_uses_vendor_saved_email(self):
        """When an order is created for a vendor with an email, order_received email is sent to vendor's email."""
        vendor = Vendor.objects.create(
            name="Alpha Corp",
            email="alpha.vendor@example.com",
            contact_phone="9988776655",
            address="Plot 5, Sector 2",
        )
        order = Order.objects.create(
            vendor=vendor,
            customer_name="John Doe",
            customer_phone="1234567890",
            delivery_address="456 Elm St",
            weight_kg=5.0,
            status=OrderStatus.ORDER_RECEIVED,
        )
        event = OrderEvent.objects.create(
            order=order,
            status=OrderStatus.ORDER_RECEIVED,
            document_name="Manifest",
        )

        mail.outbox.clear()
        send_order_notification(order.pk, OrderStatus.ORDER_RECEIVED, event.pk)

        notif = Notification.objects.get(
            order=order, order_status=OrderStatus.ORDER_RECEIVED, channel=NotificationChannel.EMAIL
        )
        self.assertEqual(notif.status, NotificationStatus.SENT)
        self.assertEqual(notif.recipient_email, "alpha.vendor@example.com")
        self.assertEqual(notif.error_message, "")

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["alpha.vendor@example.com"])
        self.assertIn("Received", mail.outbox[0].subject)

    def test_order_received_notification_skipped_when_vendor_has_no_email(self):
        """When a vendor has no email, order_received notification is SKIPPED with appropriate message."""
        vendor = Vendor.objects.create(
            name="No Email Corp",
            email="",
            contact_phone="9988776655",
            address="Plot 9, Sector 4",
        )
        order = Order.objects.create(
            vendor=vendor,
            customer_name="Jane Doe",
            customer_phone="1234567890",
            delivery_address="789 Oak Ave",
            weight_kg=2.0,
            status=OrderStatus.ORDER_RECEIVED,
        )
        event = OrderEvent.objects.create(
            order=order,
            status=OrderStatus.ORDER_RECEIVED,
            document_name="Manifest",
        )

        mail.outbox.clear()
        send_order_notification(order.pk, OrderStatus.ORDER_RECEIVED, event.pk)

        notif = Notification.objects.get(
            order=order, order_status=OrderStatus.ORDER_RECEIVED, channel=NotificationChannel.EMAIL
        )
        self.assertEqual(notif.status, NotificationStatus.SKIPPED)
        self.assertEqual(notif.error_message, "No email address for recipient")
        self.assertEqual(len(mail.outbox), 0)

    def test_existing_skipped_notification_resolves_when_vendor_email_added(self):
        """
        Flow tested:
        1. Vendor created without email.
        2. Order created -> notification SKIPPED with 'No email address for recipient'.
        3. Vendor email is entered and saved.
        4. User opens order / checks notifications -> notification is no longer SKIPPED,
           it sends to the vendor's saved email address.
        """
        vendor = Vendor.objects.create(
            name="Late Email Vendor",
            email="",
            contact_phone="09104144971",
            address="Warehouse 10",
        )
        order = Order.objects.create(
            vendor=vendor,
            customer_name="Bob Smith",
            customer_phone="9876543210",
            delivery_address="321 Pine St",
            weight_kg=3.5,
            status=OrderStatus.ORDER_RECEIVED,
        )
        event = OrderEvent.objects.create(
            order=order,
            status=OrderStatus.ORDER_RECEIVED,
            document_name="Manifest",
        )

        # Initially fires without vendor email -> SKIPPED
        send_order_notification(order.pk, OrderStatus.ORDER_RECEIVED, event.pk)
        notif = Notification.objects.get(
            order=order, order_status=OrderStatus.ORDER_RECEIVED, channel=NotificationChannel.EMAIL
        )
        self.assertEqual(notif.status, NotificationStatus.SKIPPED)
        self.assertEqual(notif.error_message, "No email address for recipient")

        # Now edit vendor and enter email
        r_update = self.client.patch(
            f"/api/v1/vendors/{vendor.pk}/",
            {"email": "saved.vendor@example.com"},
            format="json",
        )
        self.assertEqual(r_update.status_code, status.HTTP_200_OK)

        # Open the order's notifications in the Order page
        mail.outbox.clear()
        r_notifs = self.client.get(f"/api/v1/orders/{order.pk}/notifications")
        self.assertEqual(r_notifs.status_code, status.HTTP_200_OK)

        # Verify it is no longer SKIPPED and has vendor's saved email
        notif.refresh_from_db()
        self.assertEqual(notif.status, NotificationStatus.SENT)
        self.assertEqual(notif.recipient_email, "saved.vendor@example.com")
        self.assertEqual(notif.error_message, "")

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["saved.vendor@example.com"])

    def test_notification_retry_endpoint(self):
        """Staff can manually retry a notification via /api/v1/notifications/{id}/retry/."""
        vendor = Vendor.objects.create(
            name="Retry Vendor",
            email="retry.vendor@example.com",
            contact_phone="1122334455",
            address="HQ",
        )
        order = Order.objects.create(
            vendor=vendor,
            customer_name="Alice",
            customer_phone="5551234567",
            delivery_address="1st Ave",
            status=OrderStatus.ORDER_RECEIVED,
        )
        notif = Notification.objects.create(
            order=order,
            order_status=OrderStatus.ORDER_RECEIVED,
            channel=NotificationChannel.EMAIL,
            status=NotificationStatus.FAILED,
            error_message="Connection refused",
        )

        mail.outbox.clear()
        r = self.client.post(f"/api/v1/notifications/{notif.pk}/retry/")
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data["status"], NotificationStatus.SENT)
        self.assertEqual(r.data["recipient_email"], "retry.vendor@example.com")
