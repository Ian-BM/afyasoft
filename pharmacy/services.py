from decimal import Decimal
from uuid import UUID

from django.db import transaction

from .models import Medicine, Sale, SaleItem, StockMovement


def apply_stock_change(*, medicine, quantity_change, reason, user=None):
    """
    Safely update stock and create an audit movement row.
    """
    new_qty = medicine.quantity + quantity_change
    if new_qty < 0:
        raise ValueError(f'Insufficient stock for "{medicine.name}" (available {medicine.quantity}).')

    medicine.quantity = new_qty
    medicine.save(update_fields=["quantity", "updated_at"])
    StockMovement.objects.create(
        medicine=medicine,
        quantity_change=quantity_change,
        reason=reason,
        user=user,
    )
    return medicine


def complete_sale(user, payload, *, offline_uuid=None, client_recorded_at=None):
    """
    Create a sale from cart payload: list of {"id": int, "qty": int}.

    If offline_uuid is provided and already exists, returns the existing sale (idempotent sync).

    Returns:
        (sale, None, duplicate) on success — duplicate True if matched an existing offline_uuid
        (None, error_message, False) on failure
    """
    if not isinstance(payload, list) or not payload:
        return None, "Cart is empty.", False

    try:
        with transaction.atomic():
            if offline_uuid is not None:
                existing = (
                    Sale.objects.select_for_update()
                    .filter(offline_uuid=offline_uuid)
                    .first()
                )
                if existing:
                    return existing, None, True

            sale = Sale.objects.create(
                user=user,
                total=Decimal("0.00"),
                offline_uuid=offline_uuid,
                client_recorded_at=client_recorded_at,
            )
            total = Decimal("0.00")

            for row in payload:
                mid = int(row.get("id"))
                qty = int(row.get("qty", 0))
                if qty < 1:
                    continue
                med = Medicine.objects.select_for_update().get(pk=mid)
                if med.quantity < qty:
                    raise ValueError(
                        f'Insufficient stock for "{med.name}" (available {med.quantity}).'
                    )
                unit = med.price
                line = unit * qty
                SaleItem.objects.create(
                    sale=sale,
                    medicine=med,
                    medicine_name=med.name,
                    quantity=qty,
                    unit_price=unit,
                    line_total=line,
                )
                apply_stock_change(
                    medicine=med,
                    quantity_change=-qty,
                    reason=StockMovement.Reason.SALE,
                    user=user,
                )
                total += line

            if total <= 0:
                sale.delete()
                return None, "No valid lines in cart.", False

            sale.total = total
            sale.save(update_fields=["total"])

    except Medicine.DoesNotExist:
        return None, "One or more items are no longer available.", False
    except ValueError as e:
        return None, str(e), False

    return sale, None, False


def parse_offline_uuid(value):
    if value is None or value == "":
        return None
    try:
        return UUID(str(value))
    except (ValueError, TypeError, AttributeError):
        return None
