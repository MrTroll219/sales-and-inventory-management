from django.db import transaction
from store.models import Item
from accounts.models import Customer
from transactions.models import Sale, SaleDetail, StockMovement
from transactions.pricing import SaleInputError, positive_integer, compute_sale_totals, check_client_total
from .stock import adjust_stock


@transaction.atomic
def create_sale(customer_id, lines, tax_percentage, amount_paid, user):
    customer_id = positive_integer(customer_id, 'customer', maximum=9223372036854775807)
    if not isinstance(lines, list) or not lines:
        raise SaleInputError('Đơn hàng phải có ít nhất một mặt hàng.')
    quantities, client_lines = {}, []
    for line in lines:
        if not isinstance(line, dict):
            raise SaleInputError('Mỗi dòng hàng phải là JSON object.')
        item_id = positive_integer(line.get('id'), 'id', maximum=9223372036854775807)
        quantity = positive_integer(line.get('quantity'), 'quantity')
        quantities[item_id] = positive_integer(quantities.get(item_id, 0) + quantity, 'quantity')
        client_lines.append((line, item_id, quantity))
    customer = Customer.objects.get(pk=customer_id)
    items = {item.pk: item for item in Item.objects.select_for_update().filter(pk__in=sorted(quantities)).order_by('pk')}
    if set(items) != set(quantities):
        raise SaleInputError('Có mặt hàng không tồn tại.')
    totals = compute_sale_totals([{'id': pk, 'price': items[pk].price, 'quantity': q}
        for pk, q in quantities.items()], tax_percentage, amount_paid)
    prices = {line['id']: line['price'] for line in totals['lines']}
    for line, item_id, quantity in client_lines:
        check_client_total(line, 'total_item', prices[item_id] * quantity)
    # The view passes optional header assertions with the line list, not as trusted totals.
    header = getattr(lines, 'client_totals', {})
    for field in ('sub_total', 'grand_total'):
        check_client_total(header, field, totals[field])
    sale = Sale.objects.create(customer=customer, **{k: v for k, v in totals.items() if k != 'lines'})
    for line in totals['lines']:
        adjust_stock(line['id'], -line['quantity'], reason=StockMovement.Reason.SALE_OUT,
                     ref={'type': 'transactions.Sale', 'id': sale.pk, 'user': user})
        SaleDetail.objects.create(sale=sale, item=items[line['id']], price=line['price'],
                                 quantity=line['quantity'], total_detail=line['total_detail'])
    return sale


class SaleLines(list):
    """Untrusted optional header assertions, validated inside the transaction."""
    def __init__(self, lines, client_totals):
        if not isinstance(lines, list):
            raise SaleInputError('Đơn hàng phải có ít nhất một mặt hàng.')
        super().__init__(lines)
        self.client_totals = client_totals
