from datetime import timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.utils import timezone

from pharmacy.models import Medicine


class Command(BaseCommand):
    help = "Load sample medicines for local demos (skips if data exists)."

    def handle(self, *args, **options):
        if Medicine.objects.exists():
            self.stdout.write(self.style.WARNING("Medicines already exist; skipping seed."))
            return

        today = timezone.localdate()
        rows = [
            ("Amoxicillin 500mg", Decimal("12.50"), 120, today + timedelta(days=400)),
            ("Paracetamol 500mg", Decimal("4.25"), 8, today + timedelta(days=180)),
            ("Ibuprofen 200mg", Decimal("6.99"), 45, today + timedelta(days=25)),
            ("Vitamin D3 1000IU", Decimal("9.50"), 12, today + timedelta(days=520)),
            ("Cetirizine 10mg", Decimal("7.00"), 5, today + timedelta(days=14)),
            ("Omeprazole 20mg", Decimal("18.00"), 200, today + timedelta(days=-5)),
        ]
        for name, price, qty, exp in rows:
            Medicine.objects.create(name=name, price=price, quantity=qty, expiry_date=exp)
        self.stdout.write(self.style.SUCCESS(f"Created {len(rows)} demo medicines."))
