"""DP01: compare materialized stock with ledger and historical documents."""
import json
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Sum
from store.models import Item
from transactions.models import StockMovement, Purchase, SaleDetail, Sale
from transactions.services.stock import adjust_stock
from transactions.services.exceptions import InventoryError


class Command(BaseCommand):
    help = 'Read stock/ledger/trade balances; --fix alone restores the ledger balance.'

    def add_arguments(self, parser):
        parser.add_argument('--fix', action='store_true')

    @transaction.atomic
    def handle(self, *args, **options):
        rows = []
        items = Item.objects.order_by('pk')
        if options['fix']:
            items = items.select_for_update()
        for item in items:
            book = StockMovement.objects.filter(item=item).aggregate(n=Sum('delta'))['n'] or 0
            incoming = Purchase.objects.filter(item=item).aggregate(n=Sum('quantity'))['n'] or 0
            outgoing = SaleDetail.objects.filter(item=item, sale__status=Sale.Status.COMPLETED).aggregate(n=Sum('quantity'))['n'] or 0
            row = {'item_id': item.pk, 'quantity': item.quantity, 'movement_total': book,
                   'purchases_minus_sales': incoming-outgoing, 'difference': item.quantity-book,
                   'ledger_minus_trade': book-(incoming-outgoing)}
            if options['fix'] and row['difference']:
                try:
                    row['quantity_after_fix'] = adjust_stock(item.pk, book-item.quantity,
                        reason=StockMovement.Reason.ADJUST,
                        ref={'type': 'RECONCILE', 'id': item.pk})
                except InventoryError as error:
                    raise CommandError('; '.join(error.messages))
            rows.append(row)
        self.stdout.write(json.dumps({'fix': options['fix'], 'items': rows}, indent=2))
