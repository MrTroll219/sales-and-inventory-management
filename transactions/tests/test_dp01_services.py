from decimal import Decimal
from io import StringIO
import json
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db import connection
from django.db.models import Sum
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from accounts.models import Customer, Vendor
from store.models import Category, Item
from store.forms import ItemForm
from transactions.models import Purchase, Sale, SaleDetail, StockMovement
from transactions.services.stock import adjust_stock, save_item
from transactions.services.purchases import create_purchase, update_purchase, delete_purchase
from transactions.services.sales import create_sale, SaleLines
from transactions.services.exceptions import InventoryError, InsufficientStock, InvalidQuantity


class InventoryServiceTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name='DP01')
        self.item = Item.objects.create(name='DP01 A', category=self.category, price=100)
        self.other = Item.objects.create(name='DP01 B', category=self.category, price=50)
        self.vendor = Vendor.objects.create(name='DP01 vendor')
        self.customer = Customer.objects.create(first_name='DP01 customer')
        self.user = get_user_model().objects.create_user(username='dp01', is_staff=True, is_superuser=True)
        adjust_stock(self.item.pk, 10, reason='ADJUST')

    def stock(self):
        return Item.objects.get(pk=self.item.pk).quantity

    def purchase(self, **changes):
        data = dict(item=self.item, vendor=self.vendor, price=Decimal('5'), quantity=3)
        data.update(changes)
        return create_purchase(data)

    def snapshot(self):
        return (self.stock(), Purchase.objects.count(), Sale.objects.count(),
                SaleDetail.objects.count(), StockMovement.objects.count())

    def test_adjustment_records_exact_delta_balance_reference_and_actor(self):
        result = adjust_stock(self.item.pk, -2, reason='ADJUST',
            ref={'type': 'count', 'id': 42, 'user': self.user})
        event = StockMovement.objects.latest('pk')
        self.assertEqual((result, self.stock(), event.delta, event.quantity_after), (8, 8, -2, 8))
        self.assertEqual((event.ref_type, event.ref_id, event.created_by), ('count', '42', self.user))

    def test_adjustment_uses_f_expression_and_database_row_lock(self):
        with CaptureQueriesContext(connection) as queries:
            adjust_stock(self.item.pk, 1, reason='ADJUST')
        sql = '\n'.join(q['sql'] for q in queries)
        self.assertIn('UPDATE', sql)
        self.assertIn('+ 1', sql)
        if connection.vendor == 'postgresql':
            self.assertIn('FOR UPDATE', sql)

    def test_invalid_delta_or_reason_does_not_write(self):
        before = self.snapshot()
        for delta in (True, 1.5, None, 'NaN', 'Infinity', 2147483648):
            with self.subTest(delta=delta), self.assertRaises(InvalidQuantity):
                adjust_stock(self.item.pk, delta, reason='ADJUST')
        with self.assertRaises(InventoryError):
            adjust_stock(self.item.pk, 1, reason='BAD')
        self.assertEqual(self.snapshot(), before)

    def test_insufficient_stock_exposes_item_requested_and_available(self):
        before = self.snapshot()
        with self.assertRaises(InsufficientStock) as caught:
            adjust_stock(self.item.pk, -11, reason='SALE_OUT')
        error = caught.exception
        self.assertEqual((error.item.pk, error.requested, error.available), (self.item.pk, 11, 10))
        self.assertEqual(self.snapshot(), before)

    def test_ledger_failure_rolls_back_stock_write(self):
        before = self.snapshot()
        with patch.object(StockMovement.objects, 'create', side_effect=RuntimeError('ledger failed')):
            with self.assertRaises(RuntimeError):
                adjust_stock(self.item.pk, 3, reason='ADJUST')
        self.assertEqual(self.snapshot(), before)

    def test_create_purchase_posts_once_with_reference(self):
        purchase = self.purchase()
        event = StockMovement.objects.latest('pk')
        self.assertEqual((self.stock(), purchase.total_value), (13, Decimal('15.00')))
        self.assertEqual((event.reason, event.delta, event.quantity_after, event.ref_id),
            ('PURCHASE_IN', 3, 13, str(purchase.pk)))

    def test_purchase_failure_after_stock_write_rolls_back_document_and_ledger(self):
        before = self.snapshot()
        with patch.object(StockMovement.objects, 'create', side_effect=RuntimeError('ledger failed')):
            with self.assertRaises(RuntimeError): self.purchase()
        self.assertEqual(self.snapshot(), before)

    def test_update_purchase_posts_only_difference(self):
        purchase = self.purchase()
        update_purchase(purchase.pk, {'quantity': 5})
        event = StockMovement.objects.latest('pk')
        self.assertEqual((event.reason, event.delta, event.quantity_after), ('PURCHASE_EDIT', 2, 15))
        count = StockMovement.objects.count()
        update_purchase(purchase.pk, {'description': 'only text'})
        self.assertEqual((self.stock(), StockMovement.objects.count()), (15, count))

    def test_update_purchase_moves_two_items_with_matching_ledger(self):
        purchase = self.purchase()
        update_purchase(purchase.pk, {'item': self.other, 'quantity': 4})
        self.assertEqual((self.stock(), Item.objects.get(pk=self.other.pk).quantity), (10, 4))
        self.assertEqual(list(StockMovement.objects.filter(reason='PURCHASE_EDIT').values_list('delta', flat=True)), [-3, 4])

    def test_invalid_purchase_input_is_rejected_atomically(self):
        before = self.snapshot()
        for values in ({'quantity': 0}, {'quantity': 1.5}, {'price': -1}):
            with self.subTest(values=values), self.assertRaises(InventoryError): self.purchase(**values)
        self.assertEqual(self.snapshot(), before)

    def test_delete_purchase_debits_stock_and_preserves_audit_reference(self):
        purchase = self.purchase()
        pk = purchase.pk
        delete_purchase(pk)
        event = StockMovement.objects.latest('pk')
        self.assertFalse(Purchase.objects.filter(pk=pk).exists())
        self.assertEqual((self.stock(), event.reason, event.delta, event.quantity_after, event.ref_id),
            (10, 'PURCHASE_DELETE', -3, 10, str(pk)))

    def test_delete_purchase_that_would_make_stock_negative_is_rejected(self):
        purchase = self.purchase(quantity=10)
        create_sale(self.customer.pk, [{'id': self.item.pk, 'quantity': 15}], 0, 1500, self.user)
        before = self.snapshot()
        with self.assertRaises(InsufficientStock): delete_purchase(purchase.pk)
        self.assertEqual(self.snapshot(), before)
        self.assertTrue(Purchase.objects.filter(pk=purchase.pk).exists())

    def test_purchase_save_only_calculates_value_without_stock_side_effect(self):
        before = self.stock(), StockMovement.objects.count()
        purchase = Purchase(item=self.item, vendor=self.vendor, quantity=2, price=Decimal('3'))
        purchase.save()
        self.assertEqual(purchase.total_value, Decimal('6'))
        self.assertEqual((self.stock(), StockMovement.objects.count()), before)

    def test_create_sale_uses_db_price_groups_lines_and_records_actor(self):
        sale = create_sale(self.customer.pk,
            [{'id': self.item.pk, 'quantity': 1, 'price': 0.01}, {'id': self.item.pk, 'quantity': 1}],
            10, 250, self.user)
        self.assertEqual((sale.sub_total, sale.tax_amount, sale.grand_total, sale.amount_change),
            tuple(map(Decimal, ['200', '20', '220', '30'])))
        event = StockMovement.objects.latest('pk')
        self.assertEqual((self.stock(), SaleDetail.objects.count(), event.delta, event.quantity_after,
                          event.reason, event.created_by), (8, 1, -2, 8, 'SALE_OUT', self.user))

    def test_create_sale_insufficient_stock_rolls_back_everything(self):
        before = self.snapshot()
        with self.assertRaises(InsufficientStock):
            create_sale(self.customer.pk, [{'id': self.item.pk, 'quantity': 11}], 0, 1100, self.user)
        self.assertEqual(self.snapshot(), before)

    def test_create_sale_detail_failure_rolls_back_stock_and_ledger(self):
        before = self.snapshot()
        with patch.object(SaleDetail.objects, 'create', side_effect=RuntimeError('detail failed')):
            with self.assertRaises(RuntimeError):
                create_sale(self.customer.pk, [{'id': self.item.pk, 'quantity': 1}], 0, 100, self.user)
        self.assertEqual(self.snapshot(), before)

    def test_create_sale_rejects_untrusted_header_totals_before_writes(self):
        before = self.snapshot()
        with self.assertRaises(ValueError):
            create_sale(self.customer.pk, SaleLines([{'id': self.item.pk, 'quantity': 1}], {'grand_total': 1}), 0, 100, self.user)
        self.assertEqual(self.snapshot(), before)

    def test_item_form_uses_stock_service_for_create_and_edit(self):
        data = {'name': 'Form item', 'description': 'stock', 'category': self.category.pk,
                'vendor': self.vendor.pk, 'price': '1', 'quantity': 4}
        form = ItemForm(data=data)
        self.assertTrue(form.is_valid(), form.errors)
        item = form.save()
        self.assertEqual((item.quantity, item.stock_movements.get().delta), (4, 4))
        form = ItemForm(instance=item, data=dict(data, quantity=2))
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        self.assertEqual(list(item.stock_movements.values_list('delta', flat=True)), [4, -2])

    def test_metadata_only_item_save_does_not_overwrite_newer_stock(self):
        save_item({'name': 'New name'}, self.item.pk)
        self.assertEqual(self.stock(), 10)

    def test_reconcile_is_read_only_until_fix_and_fix_is_idempotent(self):
        # Deliberate corruption in the disposable test DB, never production code.
        Item.objects.filter(pk=self.item.pk).update(quantity=7)
        count = StockMovement.objects.count()
        out = StringIO(); call_command('reconcile_stock', stdout=out)
        row = json.loads(out.getvalue())['items'][0]
        self.assertEqual((row['quantity'], row['movement_total'], row['difference']), (7, 10, -3))
        self.assertEqual((self.stock(), StockMovement.objects.count()), (7, count))
        call_command('reconcile_stock', fix=True, stdout=StringIO())
        event = StockMovement.objects.latest('pk')
        self.assertEqual((self.stock(), event.delta, event.quantity_after, event.ref_type), (10, 0, 10, 'RECONCILE'))
        self.assertEqual(StockMovement.objects.filter(item=self.item).aggregate(n=Sum('delta'))['n'], 10)
        call_command('reconcile_stock', fix=True, stdout=StringIO())
        self.assertEqual(StockMovement.objects.count(), count+1)

    def test_purchase_delete_view_reports_inventory_error_and_then_can_delete(self):
        self.client.force_login(self.user)
        purchase = self.purchase(quantity=10)
        create_sale(self.customer.pk, [{'id': self.item.pk, 'quantity': 15}], 0, 1500, self.user)
        url = reverse('purchase-delete', kwargs={'pk': purchase.pk})
        response = self.client.post(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'sẽ âm')
        self.assertTrue(Purchase.objects.filter(pk=purchase.pk).exists())
        adjust_stock(self.item.pk, 10, reason='ADJUST')
        self.assertEqual(self.client.post(url).status_code, 302)
        self.assertFalse(Purchase.objects.filter(pk=purchase.pk).exists())

    def test_purchase_create_view_calls_service_once(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse('purchase-create'), {'item': self.item.pk,
            'vendor': self.vendor.pk, 'quantity': 2, 'price': '5', 'delivery_status': 'P'})
        self.assertEqual(response.status_code, 302)
        self.assertEqual((self.stock(), StockMovement.objects.filter(reason='PURCHASE_IN').count()), (12, 1))

    def test_purchase_and_movement_admin_are_read_only(self):
        from django.contrib import admin
        from django.test import RequestFactory
        request = RequestFactory().get('/admin/'); request.user = self.user
        for model in (Purchase, StockMovement):
            model_admin = admin.site._registry[model]
            self.assertFalse(model_admin.has_add_permission(request))
            self.assertFalse(model_admin.has_change_permission(request))
            self.assertFalse(model_admin.has_delete_permission(request))
