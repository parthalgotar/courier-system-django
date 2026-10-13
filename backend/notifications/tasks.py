"""Celery tasks for order-status email/SMS notifications.

Notification matrix (from PDF):
  ORDER_RECEIVED   → Vendor   → Email + SMS
  BOOKING_PLANNED  → Vendor   → Email
  OUT_FOR_DELIVERY → Customer → Email + SMS
  DELIVERED        → Vendor   → Email
  DELIVERY_FAILED  → Dispatcher → Email
  RTO_INITIATED    → Customer → Email + SMS
  CLOSED           → Vendor   → Email (PDF Invoice Ready)

Design:
  * Idempotent: the DB unique constraint on (order, status, channel) prevents
    duplicate rows; the task checks for existing sent/failed rows and exits
    early if already processed.
  * Asynchronous: always called with .delay() so the order-update request is
    never blocked.
  * Graceful degradation: missing recipients are recorded as SKIPPED; SMTP
    errors are recorded as FAILED (after retries).
  * SMS: The default SMS backend just logs the message (no real API key needed).
    Set SMS_BACKEND=twilio and SMS_ACCOUNT_SID/AUTH_TOKEN/FROM_NUMBER to send
    real messages.
"""
import logging

from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Notification matrix
# ---------------------------------------------------------------------------
# order_status → {recipient_type, channels}
#   recipient_type: "vendor" | "customer" | "dispatcher"
#   channels: list of "email" | "sms"
NOTIFICATION_MATRIX = {
    "order_received":   {"recipient": "vendor",      "channels": ["email", "sms"]},
    "booking_planned":  {"recipient": "vendor",      "channels": ["email"]},
    "out_for_delivery": {"recipient": "customer",    "channels": ["email", "sms"]},
    "delivered":        {"recipient": "vendor",      "channels": ["email"]},
    "delivery_failed":  {"recipient": "dispatcher",  "channels": ["email"]},
    "rto_initiated":    {"recipient": "customer",    "channels": ["email", "sms"]},
    "closed":           {"recipient": "vendor",      "channels": ["email"]},
}


def _get_recipients(order, recipient_type: str) -> dict:
    """Return {email, phone, name} for the given recipient type."""
    if recipient_type == "vendor":
        vendor = getattr(order, "vendor", None)
        if not vendor:
            return {"email": "", "phone": "", "name": "Vendor"}
        email = (getattr(vendor, "billing_email", "") or "").strip()
        if not email:
            email = (getattr(vendor, "email", "") or "").strip()
        return {
            "email": email,
            "phone": (getattr(vendor, "contact_phone", "") or "").strip(),
            "name": vendor.name,
        }
    if recipient_type == "customer":
        return {
            "email": getattr(order, "customer_email", "") or "",
            "phone": order.customer_phone or "",
            "name": order.customer_name,
        }
    if recipient_type == "dispatcher":
        dispatcher_email = getattr(settings, "DISPATCHER_NOTIFICATION_EMAIL", "")
        return {
            "email": dispatcher_email,
            "phone": "",
            "name": "Dispatcher",
        }
    return {"email": "", "phone": "", "name": ""}


def _subject_and_body(order, order_status: str, recipient_info: dict) -> tuple[str, str]:
    """Generate email subject + body for the given status."""
    name = recipient_info["name"]
    tracking = order.tracking_number
    order_num = order.order_number
    weight = f"{order.weight_kg} kg" if order.weight_kg else "Standard parcel"
    driver_info = f"{order.driver.full_name} ({order.driver.phone})" if order.driver else "Pending assignment"
    slot_info = f"Date: {order.pickup_date or 'TBD'}, Slot: {order.pickup_slot or 'TBD'}"

    templates = {
        "order_received": (
            f"Order {order_num} Received — Tracking #{tracking}",
            f"Hello {name},\n\nWe have received your shipment request {order_num} (tracking: {tracking}).\n"
            f"Commodity: {order.commodity} | Weight: {weight}\n"
            f"Delivery Address: {order.delivery_address}\n"
            "Our logistics operations team will plan the pickup shortly.\n\nThank you,\nERP Logistics",
        ),
        "booking_planned": (
            f"Pickup Scheduled for Order {order_num}",
            f"Hello {name},\n\nPickup for order {order_num} (tracking: {tracking}) has been scheduled.\n"
            f"Pickup Window: {slot_info}\n"
            f"Package Weight: {weight}\n\nThank you,\nERP Logistics",
        ),
        "out_for_delivery": (
            f"Your Order {tracking} is Out for Delivery",
            f"Hello {name},\n\nYour shipment (tracking: {tracking}, weight: {weight}) is out for delivery today!\n"
            f"Delivery Agent: {driver_info}\n"
            f"Destination Address: {order.delivery_address}\n"
            "Please keep your phone available for the delivery agent.\n\nThank you,\nERP Logistics",
        ),
        "delivered": (
            f"Order {order_num} Delivered Successfully",
            f"Hello {name},\n\nOrder {order_num} (tracking: {tracking}) has been successfully delivered.\n"
            f"Recipient: {order.customer_name}\n"
            f"Delivery Agent: {driver_info}\n"
            f"Delivery Address: {order.delivery_address}\n\nThank you,\nERP Logistics",
        ),
        "delivery_failed": (
            f"Delivery Failed — Order {order_num} Needs Attention",
            f"Hello {name},\n\nDelivery attempt #{order.delivery_attempt_count} for order {order_num} "
            f"(tracking: {tracking}) to {order.customer_name} has FAILED.\n"
            f"Delivery Agent: {driver_info}\n"
            f"Destination Address: {order.delivery_address}\n"
            "Please review in the ERP console to schedule a reattempt or initiate RTO.\n\nERP Logistics",
        ),
        "rto_initiated": (
            f"Return Initiated for Shipment {tracking}",
            f"Hello {name},\n\nWe were unable to deliver your shipment (tracking: {tracking}) "
            f"after {order.delivery_attempt_count} attempt(s). A return to origin (RTO) has been initiated.\n"
            "Please contact our logistics support team if you have any questions.\n\nThank you,\nERP Logistics",
        ),
        "closed": (
            f"Invoice Ready — Order {order_num} Closed",
            f"Hello {name},\n\nOrder {order_num} (tracking: {tracking}) has been closed and billed.\n"
            f"Invoice Number: {order.invoice_number or 'N/A'}\n"
            f"Total Invoiced Amount: ₹{order.invoice_amount:,.2f} (Freight: ₹{order.freight_charge:,.2f})\n"
            "The invoice PDF document is attached or available for download in your console.\n\nThank you,\nERP Logistics",
        ),
    }
    return templates.get(order_status, (f"Update for Order {order_num}", f"Status updated to {order_status}."))


def _sms_body(order, order_status: str) -> str:
    """Short SMS text for the given status."""
    tracking = order.tracking_number
    driver_str = f" with {order.driver.full_name} ({order.driver.phone})" if order.driver else ""
    templates = {
        "order_received": f"ERP: Order {order.order_number} ({order.weight_kg}kg) received. Tracking: {tracking}",
        "out_for_delivery": f"ERP: Shipment {tracking} is out for delivery today{driver_str}. Destination: {order.delivery_address[:30]}",
        "rto_initiated": f"ERP: Return initiated for shipment {tracking}. Contact support for help.",
    }
    return templates.get(order_status, f"ERP: Your order {tracking} status: {order_status}")


def _send_sms(phone: str, body: str) -> None:
    """Send SMS. Uses Twilio if configured; otherwise logs the message."""
    if not phone:
        raise ValueError("No phone number")

    sms_backend = getattr(settings, "SMS_BACKEND", "log")

    if sms_backend == "twilio":
        import importlib
        try:
            twilio_rest = importlib.import_module("twilio.rest")
        except ModuleNotFoundError:
            raise RuntimeError(
                "twilio package not installed. Run: pip install twilio"
            )
        Client = twilio_rest.Client
        account_sid = getattr(settings, "TWILIO_ACCOUNT_SID", None) or getattr(settings, "SMS_ACCOUNT_SID", "")
        auth_token = getattr(settings, "TWILIO_AUTH_TOKEN", None) or getattr(settings, "SMS_AUTH_TOKEN", "")
        from_number = getattr(settings, "TWILIO_FROM_NUMBER", None) or getattr(settings, "SMS_FROM_NUMBER", "")
        client = Client(account_sid, auth_token)
        client.messages.create(
            body=body,
            from_=from_number,
            to=phone,
        )
    else:
        logger.info("[SMS LOG] To: %s | Message: %s", phone, body)


# ---------------------------------------------------------------------------
# Main notification task
# ---------------------------------------------------------------------------
@shared_task(bind=True, max_retries=3)
def send_order_notification(self, order_pk: int, order_status: str, event_pk: int = None, force_retry: bool = False):
    """Fire all notifications for a single order-status transition."""
    from orders.models import Order, OrderEvent
    from .models import Notification, NotificationChannel, NotificationStatus

    try:
        order = Order.objects.select_related("vendor", "vendor__user", "driver").get(pk=order_pk)
    except Order.DoesNotExist:
        logger.error("send_order_notification: order %s does not exist", order_pk)
        return "missing-order"

    event = None
    if event_pk:
        event = OrderEvent.objects.filter(pk=event_pk).first()

    matrix_entry = NOTIFICATION_MATRIX.get(order_status)
    if not matrix_entry:
        return "no-notification-for-status"

    recipient_type = matrix_entry["recipient"]
    channels = matrix_entry["channels"]
    recipient_info = _get_recipients(order, recipient_type)

    for channel in channels:
        target_val = recipient_info.get("email" if channel == "email" else "phone", "")
        notif, created = Notification.objects.get_or_create(
            order=order,
            event=event,
            channel=channel,
            defaults={
                "order_status": order_status,
                "recipient": target_val,
                "recipient_email": recipient_info.get("email", ""),
                "recipient_phone": recipient_info.get("phone", ""),
                "recipient_type": recipient_type,
                "status": NotificationStatus.PENDING,
            },
        )

        if not created:
            if notif.status == NotificationStatus.SENT and not force_retry:
                continue
            if notif.status == NotificationStatus.SKIPPED:
                has_new_target = bool(
                    (channel == "email" and recipient_info.get("email"))
                    or (channel == "sms" and recipient_info.get("phone"))
                )
                if not has_new_target and not force_retry:
                    continue
            elif notif.status == NotificationStatus.FAILED and not force_retry:
                continue

        notif.order_status = order_status
        notif.recipient_email = recipient_info.get("email", "")
        notif.recipient_phone = recipient_info.get("phone", "")
        notif.recipient_type = recipient_type

        try:
            if channel == "email":
                recipient_email = recipient_info.get("email", "")
                if not recipient_email:
                    notif.status = NotificationStatus.SKIPPED
                    notif.error_message = "No email address for recipient"
                    notif.save()
                    continue

                subject, body = _subject_and_body(order, order_status, recipient_info)
                notif.subject = subject
                notif.message = body

                send_mail(
                    subject=subject,
                    message=body,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[recipient_email],
                    fail_silently=False,
                )
                notif.recipient = recipient_email
                notif.status = NotificationStatus.SENT
                notif.sent_at = timezone.now()
                notif.attempts += 1
                notif.error_message = ""
                notif.save()

            elif channel == "sms":
                recipient_phone = recipient_info.get("phone", "")
                if not recipient_phone:
                    notif.status = NotificationStatus.SKIPPED
                    notif.error_message = "No phone number for recipient"
                    notif.save()
                    continue

                sms_text = _sms_body(order, order_status)
                notif.subject = f"SMS: {order_status}"
                notif.message = sms_text

                _send_sms(recipient_phone, sms_text)
                notif.recipient = recipient_phone
                notif.status = NotificationStatus.SENT
                notif.sent_at = timezone.now()
                notif.attempts += 1
                notif.error_message = ""
                notif.save()

        except Exception as exc:
            notif.attempts += 1
            notif.error_message = f"{exc.__class__.__name__}: {exc}"[:1000]
            if hasattr(self, "request") and getattr(self.request, "retries", 0) < getattr(self, "max_retries", 3):
                notif.save()
                logger.warning("Notification %s (%s/%s) failed: %s; retrying", notif.pk, order_status, channel, exc)
                raise self.retry(exc=exc, countdown=30 * (2 ** self.request.retries))
            notif.status = NotificationStatus.FAILED
            notif.save()
            logger.error("Notification %s permanently failed: %s", notif.pk, exc)

    return "done"
