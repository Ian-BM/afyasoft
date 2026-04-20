from django.contrib import admin

from .models import (
    Medicine,
    PharmacySubscription,
    Receipt,
    Sale,
    SaleItem,
    StockMovement,
    UserProfile,
)


class SaleItemInline(admin.TabularInline):
    model = SaleItem
    extra = 0
    readonly_fields = ("medicine_name", "line_total")


@admin.register(Medicine)
class MedicineAdmin(admin.ModelAdmin):
    list_display = ("name", "price", "quantity", "expiry_date")
    search_fields = ("name",)


@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = ("id", "created_at", "total", "user", "offline_uuid")
    list_filter = ("created_at",)
    inlines = [SaleItemInline]


@admin.register(Receipt)
class ReceiptAdmin(admin.ModelAdmin):
    list_display = ("receipt_number", "sale", "issued_at")
    list_filter = ("issued_at",)
    search_fields = ("receipt_number", "sale__id")


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "role", "pharmacy_name", "client_name", "manager")
    list_filter = ("role", "manager", "subscription_started_on")
    search_fields = ("user__username", "pharmacy_name", "client_name")


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = ("date", "medicine", "quantity_change", "reason", "user")
    list_filter = ("reason", "date")
    search_fields = ("medicine__name", "user__username")


@admin.register(PharmacySubscription)
class PharmacySubscriptionAdmin(admin.ModelAdmin):
    list_display = ("started_on", "duration_days", "is_active")
