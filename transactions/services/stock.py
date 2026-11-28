"""DP01: the only application module that writes Item.quantity."""
from decimal import Decimal, DecimalException
from django.db import transaction
from django.db.models import F, Sum
from store.models import Item
from transactions.models import StockMovement
from .exceptions import InventoryError, InvalidQuantity, InsufficientStock


def _integer(value, *, signed=False):
    try:
        number = Decimal(str(value))
        if isinstance(value, bool) or not number.is_finite() or number != number.to_integral_value():
            raise ValueError
        if not (-2147483647 if signed else 0) <= number <= 2147483647:
            raise ValueError
        return int(number)
    except (ValueError, TypeError, DecimalException):
        raise InvalidQuantity('Số lượng phải là số nguyên trong phạm vi cho phép.')


@transaction.atomic
def adjust_stock(item_id, delta, *, reason, ref=None):
    delta = _integer(delta, signed=True)
    if reason not in StockMovement.Reason.values:
        raise InventoryError('Lý do biến động kho không hợp lệ.')
    item = Item.objects.select_for_update().get(pk=item_id)
    after = item.quantity + delta
    if after < 0:
        raise InsufficientStock(item, -delta, item.quantity)
    _integer(after)
    reference = ref or {}
    if not isinstance(reference, dict):
        reference = {'type': ref._meta.label, 'id': ref.pk}
    movement_delta = delta
    if reference.get('type') == 'RECONCILE':
        # Repair a materialized balance, not an additional receipt/issue.
        # Zero ledger delta keeps SUM(delta) stable and the repair idempotent.
        book = StockMovement.objects.filter(item=item).aggregate(total=Sum('delta'))['total'] or 0
        if reason != StockMovement.Reason.ADJUST or after != book:
            raise InventoryError('Đối soát chỉ được khôi phục về số dư sổ kho.')
        movement_delta = 0
    changed = Item.objects.filter(pk=item_id, quantity__gte=-delta).update(quantity=F('quantity') + delta)
    if not changed:
        raise InsufficientStock(item, -delta, item.quantity)
    StockMovement.objects.create(item=item, delta=movement_delta, quantity_after=after,
        reason=reason, ref_type=reference.get('type', ''), ref_id=str(reference.get('id', '') or ''),
        created_by=reference.get('user'))
    return after


@transaction.atomic
def save_item(data, item_id=None, user=None):
    """Keep Item forms on the same stock path, including initial balances."""
    values = dict(data)
    target = _integer(values.pop('quantity')) if 'quantity' in values else None
    if item_id is None:
        item = Item.objects.create(**values)  # default quantity=0
    else:
        item = Item.objects.select_for_update().get(pk=item_id)
        for name, value in values.items():
            setattr(item, name, value)
        item.save(update_fields=list(values))
    if target is not None:
        adjust_stock(item.pk, target - item.quantity, reason=StockMovement.Reason.ADJUST,
                     ref={'type': 'store.Item', 'id': item.pk, 'user': user})
    item.refresh_from_db()
    return item
