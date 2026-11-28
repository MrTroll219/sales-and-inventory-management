from django.core.management import call_command
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class OpeningBalanceMigrationTests(TransactionTestCase):
    def setUp(self):
        # Restore current schema in this NEW fixture; leave old test fixtures untouched.
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())
        executor = MigrationExecutor(connection)
        self.target = ('transactions', '0005_dp01_stock_movement')
        executor.migrate([('transactions', '0004_dp02_decimal_constraints')])
        self.apps = executor.loader.project_state([('transactions', '0004_dp02_decimal_constraints')]).apps

    def tearDown(self):
        call_command('flush', interactive=False, verbosity=0)
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())
        super().tearDown()

    def test_existing_stock_is_preserved_and_has_an_opening_ledger_entry(self):
        category = self.apps.get_model('store', 'Category').objects.create(name='DP01 legacy')
        item = self.apps.get_model('store', 'Item').objects.create(name='Legacy balance', category_id=category.pk, quantity=7, price=1)
        executor = MigrationExecutor(connection)
        executor.migrate([self.target])
        apps = executor.loader.project_state([self.target]).apps
        movement = apps.get_model('transactions', 'StockMovement').objects.get(item_id=item.pk)
        self.assertEqual((movement.delta, movement.quantity_after, movement.reason, movement.ref_type),
                         (7, 7, 'ADJUST', 'DP01_OPENING'))
        self.assertEqual(apps.get_model('store', 'Item').objects.get(pk=item.pk).quantity, 7)
