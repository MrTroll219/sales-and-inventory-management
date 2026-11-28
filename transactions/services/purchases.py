from django.core.exceptions import ValidationError
from django.db import transaction
from store.models import Item
from transactions.models import Purchase, StockMovement
from .exceptions import InventoryError, InvalidQuantity
from .stock import adjust_stock, _integer
from transactions.pricing import money, SaleInputError

FIELDS = {'item', 'item_id', 'vendor', 'vendor_id', 'description', 'quantity', 'price',
          'delivery_date', 'delivery_status'}


def _values(data):
    values = dict(data)
    if set(values) - FIELDS:
        raise InventoryError('Trường phiếu nhập không hợp lệ.')
    if 'quantity' in values:
        values['quantity'] = _integer(values['quantity'])
        if not values['quantity']:
            raise InvalidQuantity('Số lượng nhập phải lớn hơn 0.')
    if 'price' in values:
        try:
            values['price'] = money(values['price'], 'price')
        except SaleInputError as error:
            raise InventoryError(str(error))
    return values


def _validate(purchase):
    purchase.total_value = purchase.price * purchase.quantity
    try:
        purchase.full_clean(exclude=['slug'])
    except ValidationError as error:
        raise InventoryError(error.messages)


@transaction.atomic
def create_purchase(data):
    values = _values(data)
    purchase = Purchase(**values)
    _validate(purchase)
    purchase.save(force_insert=True)
    adjust_stock(purchase.item_id, purchase.quantity, reason=StockMovement.Reason.PURCHASE_IN, ref=purchase)
    purchase._state.fields_cache.pop('item', None)
    return purchase


@transaction.atomic
def update_purchase(purchase_id, data):
    purchase = Purchase.objects.select_for_update().get(pk=purchase_id)
    values = _values(data)
    if not values:
        return purchase
    previous_item, previous_quantity = purchase.item_id, purchase.quantity
    for name, value in values.items():
        setattr(purchase, name, value)
    _validate(purchase)
    deltas = {previous_item: -previous_quantity}
    deltas[purchase.item_id] = deltas.get(purchase.item_id, 0) + purchase.quantity
    # Deterministic locks avoid opposing item-swap deadlocks.
    list(Item.objects.select_for_update().filter(pk__in=sorted(deltas)).order_by('pk'))
    for item_id in sorted(deltas):
        if deltas[item_id]:
            adjust_stock(item_id, deltas[item_id], reason=StockMovement.Reason.PURCHASE_EDIT, ref=purchase)
    purchase.save()
    purchase._state.fields_cache.pop('item', None)
    return purchase


@transaction.atomic
def delete_purchase(purchase_id):
    purchase = Purchase.objects.select_for_update().get(pk=purchase_id)
    adjust_stock(purchase.item_id, -purchase.quantity, reason=StockMovement.Reason.PURCHASE_DELETE, ref=purchase)
    purchase.delete()
