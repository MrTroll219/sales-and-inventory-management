from django.core.management import call_command
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class CancellationMigrationTests(TransactionTestCase):
    def setUp(self):
        executor=MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())
        targets=[node for node in executor.loader.graph.leaf_nodes() if node[0]!='transactions'] + [('transactions','0006_tu03_vnd')]
        executor.migrate(targets)
        self.apps=executor.loader.project_state(targets).apps

    def tearDown(self):
        call_command('flush',interactive=False,verbosity=0)
        executor=MigrationExecutor(connection);executor.migrate(executor.loader.graph.leaf_nodes())
        super().tearDown()

    def test_old_sales_default_completed_without_stock_money_or_detail_changes(self):
        category=self.apps.get_model('store','Category').objects.create(name='Legacy HT03')
        item=self.apps.get_model('store','Item').objects.create(name='Legacy',category_id=category.pk,quantity=7,price=1000)
        customer=self.apps.get_model('accounts','Customer').objects.create(first_name='Legacy')
        sale=self.apps.get_model('transactions','Sale').objects.create(customer_id=customer.pk,sub_total=2000,grand_total=2000,amount_paid=2000)
        self.apps.get_model('transactions','SaleDetail').objects.create(sale_id=sale.pk,item_id=item.pk,price=1000,quantity=2,total_detail=2000)
        executor=MigrationExecutor(connection);executor.migrate(executor.loader.graph.leaf_nodes())
        apps=executor.loader.project_state(executor.loader.graph.leaf_nodes()).apps
        current=apps.get_model('transactions','Sale').objects.get(pk=sale.pk)
        self.assertEqual((current.status,current.grand_total,current.amount_paid),('COMPLETED',2000,2000))
        self.assertEqual(apps.get_model('store','Item').objects.get(pk=item.pk).quantity,7)
        self.assertEqual(apps.get_model('transactions','SaleDetail').objects.get(sale_id=sale.pk).quantity,2)
        self.assertFalse(apps.get_model('transactions','SaleCancellation').objects.exists())
