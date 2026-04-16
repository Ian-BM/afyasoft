from decimal import Decimal
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone


class UserProfile(models.Model):
    class Role(models.TextChoices):
        ADMIN = "admin", "Administrator"
        MANAGER = "manager", "Manager / Owner"
        WORKER = "worker", "Worker"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="pharmacy_profile",
    )
    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.WORKER,
    )
    manager = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="pharmacy_workers",
        help_text="Assigned manager for this worker account.",
    )

    def __str__(self):
        return f"{self.user.username} ({self.get_role_display()})"


class PharmacySubscription(models.Model):
    started_on = models.DateField(default=timezone.localdate)
    duration_days = models.PositiveIntegerField(default=30)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Pharmacy subscription"
        verbose_name_plural = "Pharmacy subscriptions"

    def __str__(self):
        return f"Subscription ({self.started_on} / {self.duration_days} days)"

    @property
    def expires_on(self):
        return self.started_on + timedelta(days=self.duration_days)

    @property
    def days_remaining(self):
        remaining = (self.expires_on - timezone.localdate()).days
        return max(0, remaining)


class Medicine(models.Model):
    name = models.CharField(max_length=200)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField(default=0)
    expiry_date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Sale(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sales",
    )
    offline_uuid = models.UUIDField(null=True, blank=True, unique=True)
    client_recorded_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Device time when sale was recorded (e.g. offline checkout).",
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Sale #{self.pk} — {self.total}"


class SaleItem(models.Model):
    sale = models.ForeignKey(Sale, related_name="items", on_delete=models.CASCADE)
    medicine = models.ForeignKey(Medicine, on_delete=models.PROTECT)
    medicine_name = models.CharField(max_length=200)
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    line_total = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return f"{self.medicine_name} x{self.quantity}"


class Receipt(models.Model):
    sale = models.OneToOneField(Sale, related_name="receipt", on_delete=models.CASCADE)
    receipt_number = models.CharField(max_length=32, unique=True, blank=True)
    issued_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-issued_at", "-id"]

    def save(self, *args, **kwargs):
        if not self.receipt_number and self.sale_id:
            self.receipt_number = f"RCPT-{self.sale_id:08d}"
        super().save(*args, **kwargs)

    def __str__(self):
        return self.receipt_number or f"Receipt for Sale #{self.sale_id}"


class StockMovement(models.Model):
    class Reason(models.TextChoices):
        SALE = "sale", "Sale"
        RESTOCK = "restock", "Restock"
        ADJUSTMENT = "adjustment", "Adjustment"
        EXPIRED = "expired", "Expired"

    medicine = models.ForeignKey(
        Medicine,
        related_name="stock_movements",
        on_delete=models.CASCADE,
    )
    quantity_change = models.IntegerField()
    reason = models.CharField(max_length=20, choices=Reason.choices)
    date = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="stock_movements",
    )

    class Meta:
        ordering = ["-date", "-id"]

    def __str__(self):
        return f"{self.medicine.name}: {self.quantity_change} ({self.reason})"
