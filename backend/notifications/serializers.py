from rest_framework import serializers
from .models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    order_number = serializers.CharField(source="order.order_number", read_only=True)
    tracking_number = serializers.CharField(source="order.tracking_number", read_only=True)

    class Meta:
        model = Notification
        fields = [
            "id",
            "order",
            "order_number",
            "tracking_number",
            "event",
            "order_status",
            "channel",
            "recipient",
            "recipient_email",
            "recipient_phone",
            "recipient_type",
            "subject",
            "message",
            "status",
            "error_message",
            "attempts",
            "sent_at",
            "created_at",
        ]
