from decimal import Decimal
from io import StringIO
import json
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase
from django.test.utils import CaptureQueriesContext

OLD=[('store','0002_dp02_decimal_constraints'),('invoice','0002_dp02_decimal_constraints'),
     ('bills','0002_dp02_decimal_constraints'),('transactions','0005_dp01_stock_movement')]


class VNDMigrationTests(TransactionTestCase):
    def setUp(self):
        executor=MigrationExecutor(connection); executor.migrate(OLD)
        self.old=executor.loader.project_state(OLD).apps
        category=self.old.get_model('store','Category').objects.create(name='TU03 legacy')
        self.item=self.old.get_model('store','Item').objects.create(name='Legacy',category_id=category.pk,quantity=12,price=Decimal('19.99'))
        self.boundary=self.old.get_model('store','Item').objects.create(name='Boundary',category_id=category.pk,quantity=0,price=Decimal('9999999999999.99'))
        customer=self.old.get_model('accounts','Customer').objects.create(first_name='Legacy')
        self.sale=self.old.get_model('transactions','Sale').objects.create(customer_id=customer.pk,sub_total=99999,
            tax_amount=Decimal('9999.90'),tax_percentage=10,grand_total=Decimal('109998.90'),amount_paid=110000,amount_change=Decimal('1.10'))
        self.bill=self.old.get_model('bills','Bill').objects.create(slug='tu03-bill',institution_name='Legacy',payment_details='Cash',amount=Decimal('1234.50'))
        self.invoice=self.old.get_model('invoice','Invoice').objects.create(slug='tu03-invoice',customer_name='Legacy',
            contact_number='123',item_id=self.item.pk,quantity=3,price_per_item=Decimal('19.99'),shipping=Decimal('0.49'),total=Decimal('59.97'),grand_total=Decimal('60.46'))

    def tearDown(self):
        call_command('flush',interactive=False,verbosity=0)
        executor=MigrationExecutor(connection); executor.migrate(executor.loader.graph.leaf_nodes())
        super().tearDown()

    def preflight(self,valid=True):
        output=StringIO()
        if valid: call_command('check_vnd_data',stdout=output)
        else:
            with self.assertRaises(CommandError): call_command('check_vnd_data',stdout=output)
        return json.loads(output.getvalue())

    def test_legacy_decimal_values_round_half_up_without_touching_stock(self):
        with CaptureQueriesContext(connection) as queries: report=self.preflight()
        self.assertTrue(report['safe_to_migrate'])
        self.assertTrue(all(q['sql'].lstrip().upper().startswith(('SELECT','PRAGMA')) for q in queries))
        executor=MigrationExecutor(connection); targets=executor.loader.graph.leaf_nodes(); executor.migrate(targets)
        apps=executor.loader.project_state(targets).apps
        item=apps.get_model('store','Item').objects.get(pk=self.item.pk)
        sale=apps.get_model('transactions','Sale').objects.get(pk=self.sale.pk)
        self.assertEqual((item.price,item.quantity),(Decimal(20),12))
        self.assertEqual(apps.get_model('store','Item').objects.get(pk=self.boundary.pk).price,Decimal('10000000000000'))
        self.assertEqual(apps.get_model('bills','Bill').objects.get(pk=self.bill.pk).amount,Decimal(1235))
        invoice=apps.get_model('invoice','Invoice').objects.get(pk=self.invoice.pk)
        self.assertEqual((invoice.price_per_item,invoice.shipping,invoice.total,invoice.grand_total),tuple(map(Decimal,['20','0','60','60'])))
        self.assertEqual((sale.sub_total,sale.tax_amount,sale.grand_total,sale.amount_change),tuple(map(Decimal,['99999','10000','109999','1'])))
        self.assertTrue(self.preflight()['safe_to_migrate'])

    def test_rounding_conflicts_stop_migration_without_repair_or_disabled_checks(self):
        model=self.old.get_model('transactions','Sale')
        model.objects.filter(pk=self.sale.pk).update(sub_total=Decimal('.49'),tax_amount=Decimal('.49'),
            grand_total=Decimal('.98'),amount_paid=Decimal('.98'),amount_change=0)
        self.assertFalse(self.preflight(valid=False)['safe_to_migrate'])
        executor=MigrationExecutor(connection)
        with self.assertRaisesRegex(RuntimeError,'TU03 preflight failed'):
            executor.migrate(executor.loader.graph.leaf_nodes())
        self.assertEqual(model.objects.get(pk=self.sale.pk).grand_total,Decimal('.98'))
        self.assertEqual(self.old.get_model('store','Item').objects.get(pk=self.item.pk).price,Decimal('19.99'))
