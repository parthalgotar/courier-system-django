from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractUser
from django.db import models


class UserManager(BaseUserManager):
    """Custom manager required because USERNAME_FIELD is 'email', not the
    default 'username' — Django's built-in createsuperuser command needs
    create_user/create_superuser to accept email as the first argument."""

    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("Email is required")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("full_name", extra_fields.get("full_name", ""))
        return self.create_user(email, password, **extra_fields)


class UserRole(models.TextChoices):
    ADMIN = "admin", "Admin"
    DISPATCHER = "dispatcher", "Dispatcher"
    DRIVER = "driver", "Driver"
    VENDOR = "vendor", "Vendor"


class User(AbstractUser):
    """Custom user: email is the login field, plus a role for the ERP."""

    username = None
    email = models.EmailField(unique=True)
    full_name = models.CharField(max_length=255, blank=True)
    role = models.CharField(max_length=20, choices=UserRole.choices, default=UserRole.DISPATCHER)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    def __str__(self):
        return self.email
