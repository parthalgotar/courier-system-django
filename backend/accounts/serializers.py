from django.contrib.auth import get_user_model
from rest_framework import serializers

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "email", "full_name", "role", "is_active"]


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=6)
    role = serializers.CharField(required=False, default="vendor")

    class Meta:
        model = User
        fields = ["id", "email", "full_name", "password", "role"]

    def validate_role(self, value):
        role_lower = str(value).strip().lower()
        if role_lower == "admin":
            raise serializers.ValidationError("Public registration cannot create admin accounts.")
        if role_lower not in ("vendor", "driver", "dispatcher"):
            return "vendor"
        return role_lower

    def create(self, validated_data):
        password = validated_data.pop("password")
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user
