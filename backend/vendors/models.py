from django.conf import settings
from django.db import models


class Vendor(models.Model):
    name = models.CharField(max_length=255)
    contact_phone = models.CharField(max_length=30)
    address = models.CharField(max_length=500)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)

    # Accounting / Invoice Management ----------------------------------
    # Links a vendor to a login account. This is what decides which
    # orders/invoices a logged-in vendor user "owns" (PDF section 5.5).
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="vendor_profile",
    )
    # Fallback billing address for vendors that have no login account yet.
    # If `user` is set, the user's account e-mail is used first.
    email = models.EmailField(blank=True, default="")

    def __str__(self):
        return self.name

    @property
    def billing_email(self) -> str:
        """The address invoices are e-mailed to: the linked user's registered
        e-mail if there is one, otherwise the vendor's own e-mail."""
        if self.user_id and self.user.email:
            return self.user.email
        return self.email
