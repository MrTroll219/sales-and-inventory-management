from django.core.management import call_command
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class MinStockMigrationTests(TransactionTestCase):
    def setUp(self):
        executor=MigrationExecutor(connection)
        executor.migrate([('store','0003_tu03_vnd')])
        self.old=executor.loader.project_state([('store','0003_tu03_vnd')]).apps

    def tearDown(self):
        call_command('flush',interactive=False,verbosity=0)
        executor=MigrationExecutor(connection); executor.migrate(executor.loader.graph.leaf_nodes())
        super().tearDown()

    def test_existing_items_get_zero_threshold_without_stock_or_price_changes(self):
        category=self.old.get_model('store','Category').objects.create(name='HT01 cũ')
        item=self.old.get_model('store','Item').objects.create(name='Hàng cũ',category_id=category.pk,quantity=7,price=1000)
        executor=MigrationExecutor(connection); executor.migrate([('store','0004_ht01_min_stock_level')])
        apps=executor.loader.project_state([('store','0004_ht01_min_stock_level')]).apps
        current=apps.get_model('store','Item').objects.get(pk=item.pk)
        self.assertEqual((current.min_stock_level,current.quantity,current.price),(0,7,1000))
