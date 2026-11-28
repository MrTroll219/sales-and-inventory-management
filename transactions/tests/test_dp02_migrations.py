"""DP02: read-only preflight and upgrading the schema shipped by v0-goc."""
from decimal import Decimal
from io import StringIO
import json

from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase
from django.test.utils import CaptureQueriesContext

OLD = [('store', '0001_initial'), ('invoice', '0001_initial'), ('bills', '0001_initial'),
       ('transactions', '0003_alter_purchase_quantity'),
       ('accounts', '0002_alter_profile_email_alter_profile_first_name_and_more')]
NEW = [('store', '0002_dp02_decimal_constraints'), ('invoice', '0002_dp02_decimal_constraints'),
       ('bills', '0002_dp02_decimal_constraints'), ('transactions', '0004_dp02_decimal_constraints'),
       ('accounts', '0002_alter_profile_email_alter_profile_first_name_and_more')]


class DecimalMigrationTests(TransactionTestCase):
    def setUp(self):
        executor = MigrationExecutor(connection)
        executor.migrate(OLD)
        self.old = executor.loader.project_state(OLD).apps
        self.Item = self.old.get_model('store', 'Item')
        self.Invoice = self.old.get_model('invoice', 'Invoice')
        self.Bill = self.old.get_model('bills', 'Bill')
        self.Sale = self.old.get_model('transactions', 'Sale')
        self.Purchase = self.old.get_model('transactions', 'Purchase')
        category = self.old.get_model('store', 'Category').objects.create(name='Legacy')
        self.item = self.Item.objects.create(name='Legacy item', category_id=category.pk,
            quantity=10, price=1.005)
        customer = self.old.get_model('accounts', 'Customer').objects.create(first_name='Legacy')
        vendor = self.old.get_model('accounts', 'Vendor').objects.create(name='Legacy vendor')
        self.invoice = self.Invoice.objects.create(slug='legacy-invoice', customer_name='Legacy', contact_number='123',
            item_id=self.item.pk, quantity=3.0, price_per_item=19.99, shipping=0.105,
            total=59.97, grand_total=60.075)
        self.bill = self.Bill.objects.create(slug='legacy-bill', institution_name='Legacy',
            payment_details='Cash', amount=2.675)
        self.sale = self.Sale.objects.create(customer_id=customer.pk, sub_total=100,
            tax_amount=Decimal('7.13'), tax_percentage=7.125, grand_total=Decimal('107.13'),
            amount_paid=110, amount_change=Decimal('2.87'))
        self.purchase = self.Purchase.objects.create(slug='legacy-purchase', item_id=self.item.pk,
            vendor_id=vendor.pk, quantity=2, price=Decimal('2.50'), total_value=Decimal('5.00'))
        self.old.get_model('transactions', 'SaleDetail').objects.create(sale_id=self.sale.pk,
            item_id=self.item.pk, quantity=3, price=Decimal('3.33'), total_detail=Decimal('9.99'))

    def tearDown(self):
        # Only the disposable test database. Remove deliberately invalid legacy
        # rows before restoring the schema for the rest of the suite.
        call_command('flush', interactive=False, verbosity=0)
        MigrationExecutor(connection).migrate(NEW)
        super().tearDown()

    def preflight(self, valid=True):
        output = StringIO()
        if valid:
            call_command('check_decimal_data', stdout=output)
        else:
            with self.assertRaises(CommandError):
                call_command('check_decimal_data', stdout=output)
        return json.loads(output.getvalue())

    def test_legacy_demo_migrates_with_half_up_decimal_values_preserved(self):
        self.assertTrue(self.preflight()['safe_to_migrate'])
        executor = MigrationExecutor(connection)
        executor.migrate(NEW)
        apps = executor.loader.project_state(NEW).apps
        item = apps.get_model('store', 'Item').objects.get(pk=self.item.pk)
        invoice = apps.get_model('invoice', 'Invoice').objects.get(pk=self.invoice.pk)
        bill = apps.get_model('bills', 'Bill').objects.get(pk=self.bill.pk)
        sale = apps.get_model('transactions', 'Sale').objects.get(pk=self.sale.pk)
        self.assertEqual(item.price, Decimal('1.01'))
        self.assertEqual(item.quantity, 10)
        self.assertEqual(invoice.quantity, 3)
        self.assertIsInstance(invoice.quantity, int)
        self.assertEqual((invoice.price_per_item, invoice.shipping, invoice.total, invoice.grand_total),
            tuple(map(Decimal, ['19.99', '0.11', '59.97', '60.08'])))
        self.assertEqual(bill.amount, Decimal('2.68'))
        self.assertEqual(sale.tax_percentage, Decimal('7.13'))
        self.assertEqual((sale.sub_total, sale.tax_amount, sale.grand_total, sale.amount_paid, sale.amount_change),
            tuple(map(Decimal, ['100', '7.13', '107.13', '110', '2.87'])))
        self.assertTrue(self.preflight()['safe_to_migrate'])

    def test_fractional_and_negative_invoice_quantities_block_before_conversion(self):
        for quantity in (1.5, -1.0):
            with self.subTest(quantity=quantity):
                self.Invoice.objects.filter(pk=self.invoice.pk).update(quantity=quantity)
                with CaptureQueriesContext(connection) as queries:
                    report = self.preflight(valid=False)
                self.assertFalse(report['safe_to_migrate'])
                self.assertTrue(any(v['model'] == 'invoice.Invoice' and v['pk'] == self.invoice.pk
                    and v['field'] == 'quantity' for v in report['violations']))
                self.assertTrue(all(q['sql'].lstrip().upper().startswith(('SELECT', 'PRAGMA')) for q in queries),
                                [q['sql'] for q in queries])
                with self.assertRaisesRegex(RuntimeError, 'DP02 preflight failed.*invoice.Invoice'):
                    MigrationExecutor(connection).migrate(NEW)
                self.assertEqual(self.Invoice.objects.get(pk=self.invoice.pk).quantity, quantity)
        self.Invoice.objects.filter(pk=self.invoice.pk).update(quantity=3)

    def test_other_legacy_violations_are_reported_and_migration_does_not_repair_them(self):
        cases = [(self.Item, self.item.pk, 'price', -1),
                 (self.Item, self.item.pk, 'quantity', -1),
                 (self.Bill, self.bill.pk, 'amount', -1),
                 (self.Purchase, self.purchase.pk, 'quantity', 0),
                 (self.Sale, self.sale.pk, 'tax_percentage', 101),
                 (self.Sale, self.sale.pk, 'grand_total', Decimal('107.14')),
                 (self.Sale, self.sale.pk, 'amount_change', Decimal('2.86')),
                 (self.Item, self.item.pk, 'price', float('inf'))]
        for model, pk, field, invalid in cases:
            with self.subTest(model=model.__name__, field=field, invalid=invalid):
                before = getattr(model.objects.get(pk=pk), field)
                model.objects.filter(pk=pk).update(**{field: invalid})
                report = self.preflight(valid=False)
                self.assertTrue(any(v['field'] == field for v in report['violations']))
                with self.assertRaisesRegex(RuntimeError, 'DP02 preflight failed'):
                    MigrationExecutor(connection).migrate(NEW)
                self.assertEqual(getattr(model.objects.get(pk=pk), field), invalid)
                model.objects.filter(pk=pk).update(**{field: before})

    def test_clean_preflight_uses_only_read_queries_and_changes_nothing(self):
        before = list(self.Invoice.objects.values())
        with CaptureQueriesContext(connection) as queries:
            report = self.preflight()
        self.assertTrue(report['safe_to_migrate'])
        self.assertTrue(all(q['sql'].lstrip().upper().startswith(('SELECT', 'PRAGMA')) for q in queries))
        self.assertEqual(list(self.Invoice.objects.values()), before)
