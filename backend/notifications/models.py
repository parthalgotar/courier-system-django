"""Notification model — tracks every email/SMS attempt per order status change."""
from django.conf import settings
from django.db import models


class NotificationChannel(models.TextChoices):
    EMAIL = "email", "Email"
    SMS = "sms", "SMS"
    BOTH = "both", "Both (Email + SMS)"


class NotificationStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    SENT = "sent", "Sent"
    FAILED = "failed", "Failed"
    SKIPPED = "skipped", "Skipped"  # no recipient / not applicable


class Notification(models.Model):
    """One row per notification attempt.
    Tracks recipient details, subject, body, milestone status, and delivery outcome.
    """

    order = models.ForeignKey(
        "orders.Order", on_delete=models.CASCADE, related_name="notifications"
    )
    event = models.ForeignKey(
        "orders.OrderEvent", on_delete=models.SET_NULL, null=True, blank=True, related_name="notifications"
    )
    order_status = models.CharField(max_length=30)
    channel = models.CharField(max_length=10, choices=NotificationChannel.choices)
    recipient = models.CharField(max_length=255, blank=True, default="")
    recipient_email = models.EmailField(blank=True, default="")
    recipient_phone = models.CharField(max_length=30, blank=True, default="")
    recipient_type = models.CharField(max_length=20, blank=True, default="customer")
    subject = models.CharField(max_length=255, blank=True, default="")
    message = models.TextField(blank=True, default="")
    status = models.CharField(
        max_length=10, choices=NotificationStatus.choices, default=NotificationStatus.PENDING, db_index=True
    )
    error_message = models.TextField(blank=True, default="")
    attempts = models.PositiveSmallIntegerField(default=0)
    sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["order", "event", "channel"],
                condition=models.Q(event__isnull=False),
                name="uniq_notification_per_order_event_channel",
            )
        ]

    def __str__(self):
        return f"{self.order_id} | {self.order_status} | {self.channel} [{self.status}]"
