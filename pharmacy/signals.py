from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Receipt, Sale, UserProfile


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def ensure_pharmacy_profile(sender, instance, created, **kwargs):
    if kwargs.get("raw"):
        return
    if created:
        role = UserProfile.Role.ADMIN if instance.is_superuser else UserProfile.Role.WORKER
        UserProfile.objects.create(user=instance, role=role)
        return
    if not UserProfile.objects.filter(user=instance).exists():
        role = UserProfile.Role.ADMIN if instance.is_superuser else UserProfile.Role.WORKER
        UserProfile.objects.create(user=instance, role=role)


@receiver(post_save, sender=Sale)
def ensure_sale_receipt(sender, instance, created, **kwargs):
    if kwargs.get("raw"):
        return
    if created:
        Receipt.objects.get_or_create(sale=instance)
