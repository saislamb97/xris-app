from django.conf import settings
from django.db import models
from django.utils import timezone
from django.db.models import JSONField
from datetime import timedelta


# ------------------------------------------------------------------------
# Subscription Package Model (FREE or PREMIUM)
# ------------------------------------------------------------------------
class SubscriptionPackage(models.Model):
    PACKAGE_FREE = 'FREE'
    PACKAGE_PREMIUM = 'PREMIUM'
    
    PACKAGE_CHOICES = [
        (PACKAGE_FREE, 'Free'),
        (PACKAGE_PREMIUM, 'Premium'),
    ]

    name = models.CharField(
        max_length=20,
        choices=PACKAGE_CHOICES,
        default=PACKAGE_FREE,
        unique=True
    )
    description = JSONField(default=list, blank=True)  # Optional list of features
    price = models.DecimalField(max_digits=6, decimal_places=2, default=0.00)
    duration_days = models.PositiveIntegerField(default=30)  # e.g. 30-day access
    stripe_price_id = models.CharField(max_length=100, blank=True, null=True)

    def __str__(self):
        return self.get_name_display()

    class Meta:
        ordering = ['price']


# ------------------------------------------------------------------------
# User Subscription Model
# ------------------------------------------------------------------------
class Subscription(models.Model):
    STATUS_ACTIVE = 'ACTIVE'
    STATUS_CANCELLED = 'CANCELLED'
    STATUS_EXPIRED = 'EXPIRED'

    STATUS_CHOICES = [
        (STATUS_ACTIVE, 'Active'),
        (STATUS_CANCELLED, 'Cancelled'),
        (STATUS_EXPIRED, 'Expired'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='subscriptions'  # plural now
    )
    package = models.ForeignKey(
        SubscriptionPackage,
        on_delete=models.PROTECT,
        related_name='subscriptions'
    )

    # Stripe Info
    price = models.DecimalField(max_digits=6, decimal_places=2, default=0.00)
    stripe_subscription_id = models.CharField(max_length=100, blank=True, null=True)
    stripe_customer_id = models.CharField(max_length=100, blank=True, null=True)

    # Status & Dates
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_ACTIVE)
    pending_cancellation = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    renewed_at = models.DateTimeField(auto_now=True)
    expiry_date = models.DateTimeField()

    def __str__(self):
        return f"{self.user.email} - {self.package.name}"

    def save(self, *args, **kwargs):
        if not self.expiry_date and self.package:
            self.set_expiry()
        super().save(*args, **kwargs)

    def set_expiry(self):
        """Sets expiry date based on package duration."""
        if self.package:
            self.expiry_date = timezone.now() + timedelta(days=self.package.duration_days)

    @property
    def is_current(self):
        """Returns True if subscription is active and not expired."""
        return self.status == self.STATUS_ACTIVE and self.expiry_date >= timezone.now()

    @property
    def days_remaining(self):
        if self.expiry_date and self.expiry_date >= timezone.now():
            return (self.expiry_date - timezone.now()).days
        return 0

    class Meta:
        ordering = ['-created_at']
