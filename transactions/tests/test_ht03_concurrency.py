from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db import connection, connections, close_old_connections
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase, skipUnlessDBFeature

from accounts.models import Customer, Vendor
from store.models import Category, Item
from transactions.models import Sale, SaleCancellation, StockMovement
from transactions.services.stock import save_item
from transactions.services.purchases import create_purchase
from transactions.services.sales import create_sale, cancel_sale, SaleAlreadyCancelled


class ConcurrentCancellationTests(TransactionTestCase):
    def setUp(self):
        executor=MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())

    @skipUnlessDBFeature('has_select_for_update')
    def test_two_threads_restore_same_sale_exactly_once_on_postgresql16(self):
        self.assertEqual(connection.vendor,'postgresql')
        self.assertTrue(160000<=connection.pg_version<170000)
        user=get_user_model().objects.create_user(username='ht03-race',is_staff=True)
        customer=Customer.objects.create(first_name='Race HT03')
        vendor=Vendor.objects.create(name='Race vendor')
        category=Category.objects.create(name='Race')
        a=save_item(dict(name='Race A',category=category,price=1000,quantity=0))
        b=save_item(dict(name='Race B',category=category,price=2000,quantity=0))
        for item in (a,b):create_purchase(dict(item=item,vendor=vendor,quantity=10,price=item.price))
        sale=create_sale(customer.pk,[dict(id=a.pk,quantity=2),dict(id=b.pk,quantity=3)],0,8000,user)
        barrier=Barrier(2,timeout=10)
        def worker():
            close_old_connections()
            try:
                actor=get_user_model().objects.get(pk=user.pk)
                with connection.cursor() as cursor:cursor.execute("SET lock_timeout = '8s'")
                barrier.wait()
                try:
                    cancel_sale(sale.pk,actor,'Hai luồng cùng yêu cầu hủy')
                    return 'cancelled'
                except SaleAlreadyCancelled:
                    return 'already_cancelled'
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures=[pool.submit(worker) for _ in range(2)]
            results=[future.result(timeout=20) for future in futures]
        self.assertCountEqual(results,['cancelled','already_cancelled'])
        self.assertEqual(tuple(Item.objects.filter(pk__in=[a.pk,b.pk]).order_by('pk').values_list('quantity',flat=True)),(10,10))
        self.assertEqual(SaleCancellation.objects.filter(sale=sale).count(),1)
        self.assertEqual(StockMovement.objects.filter(reason='SALE_CANCEL').count(),2)
        sale.refresh_from_db();self.assertEqual(sale.status,Sale.Status.CANCELLED)
