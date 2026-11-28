from datetime import datetime, timezone
from decimal import Decimal
from io import BytesIO, StringIO
import json
from unittest.mock import patch

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.management import call_command
from django.db import connection, IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.test import TestCase, Client, RequestFactory
from django.test.utils import CaptureQueriesContext
from django.urls import reverse, resolve
from openpyxl import load_workbook

from accounts.models import Customer, Vendor
from store.models import Category, Item
from transactions.models import Sale, SaleDetail, SaleCancellation, StockMovement
from transactions.forms import SaleCancellationForm
from transactions.filters import filtered_transactions
from transactions.services.stock import save_item
from transactions.services.purchases import create_purchase
from transactions.services.sales import create_sale, cancel_sale, SaleAlreadyCancelled
from transactions.services.exceptions import InventoryError


class CancellationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.staff=get_user_model().objects.create_user(username='ht03-staff',is_staff=True)
        cls.superuser=get_user_model().objects.create_user(username='ht03-super',is_superuser=True)
        cls.normal=get_user_model().objects.create_user(username='ht03-normal')
        cls.customer=Customer.objects.create(first_name='Khách HT03')
        cls.vendor=Vendor.objects.create(name='NCC HT03')
        category=Category.objects.create(name='HT03')
        cls.a=save_item(dict(name='HT03 A',category=category,description='Thử hủy',vendor=cls.vendor,price=1000,quantity=0,min_stock_level=8))
        cls.b=save_item(dict(name='HT03 B',category=category,description='Thử hủy',vendor=cls.vendor,price=2000,quantity=0,min_stock_level=7))
        for item in (cls.a,cls.b):
            create_purchase(dict(item=item,vendor=cls.vendor,price=item.price,quantity=10))
        cls.sale=create_sale(cls.customer.pk,[dict(id=cls.a.pk,quantity=2),dict(id=cls.b.pk,quantity=3)],0,8000,cls.staff)

    def setUp(self):
        self.client.force_login(self.staff)

    def stock(self):
        return tuple(Item.objects.filter(pk__in=[self.a.pk,self.b.pk]).order_by('pk').values_list('quantity',flat=True))

    def snapshot(self):
        return (self.stock(),Sale.objects.get(pk=self.sale.pk).status,SaleCancellation.objects.count(),StockMovement.objects.count())

    def cancel(self,**kwargs):
        return cancel_sale(self.sale.pk,kwargs.get('user',self.staff),kwargs.get('reason','Khách đổi nhu cầu'))

    def test_restores_two_items_audit_actor_reason_and_ledger(self):
        self.assertEqual(self.stock(),(8,7))
        record=self.cancel(reason='  Khách đổi nhu cầu  ')
        self.assertEqual(self.stock(),(10,10))
        self.sale.refresh_from_db()
        self.assertEqual(self.sale.status,Sale.Status.CANCELLED)
        self.assertEqual((record.sale_id,record.sale_reference,record.cancelled_by_id,record.reason),
            (self.sale.pk,self.sale.pk,self.staff.pk,'Khách đổi nhu cầu'))
        expected=[{'item_id':self.a.pk,'quantity':2},{'item_id':self.b.pk,'quantity':3}]
        self.assertEqual(record.restored_items,expected)
        self.assertIsNotNone(record.cancelled_at)
        moves=list(StockMovement.objects.filter(reason='SALE_CANCEL').order_by('item_id').values_list('item_id','delta','quantity_after','ref_type','ref_id','created_by_id'))
        self.assertEqual(moves,[(self.a.pk,2,10,'transactions.Sale',str(self.sale.pk),self.staff.pk),
                                (self.b.pk,3,10,'transactions.Sale',str(self.sale.pk),self.staff.pk)])

    def test_second_cancel_raises_and_changes_nothing(self):
        record=self.cancel(); before=self.snapshot()
        with self.assertRaises(SaleAlreadyCancelled): self.cancel(user=self.superuser,reason='Lý do khác')
        self.assertEqual(self.snapshot(),before)
        record.refresh_from_db();self.assertEqual(record.reason,'Khách đổi nhu cầu')
        self.assertEqual(record.cancelled_by_id,self.staff.pk)

    def test_empty_short_whitespace_and_non_string_reasons_rejected(self):
        before=self.snapshot()
        for reason in ('','abcd','   ','  abc  ',None,123,True):
            with self.subTest(reason=reason),self.assertRaises(InventoryError):self.cancel(reason=reason)
            self.assertEqual(self.snapshot(),before)

    def test_reason_form_and_model_require_five_trimmed_characters(self):
        for reason in ('','abcd','     '):
            self.assertFalse(SaleCancellationForm({'reason':reason}).is_valid())
            record=SaleCancellation(sale=self.sale,sale_reference=self.sale.pk,cancelled_by=self.staff,reason=reason)
            with self.assertRaises(ValidationError):record.full_clean()
        form=SaleCancellationForm({'reason':'  abcde  '});self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data['reason'],'abcde')

    def test_service_checks_permissions_even_without_view(self):
        before=self.snapshot()
        self.normal.is_staff=False
        inactive=get_user_model().objects.create_user(username='inactive',is_staff=True,is_active=False)
        for actor in (None,self.normal,inactive):
            with self.assertRaises(PermissionDenied):self.cancel(user=actor)
            self.assertEqual(self.snapshot(),before)

    def test_superuser_without_staff_flag_can_cancel(self):
        self.assertFalse(self.superuser.is_staff)
        record=self.cancel(user=self.superuser)
        self.assertEqual(record.cancelled_by_id,self.superuser.pk)

    def test_failure_on_second_item_rolls_back_first_stock_and_ledger(self):
        from transactions.services.sales import adjust_stock
        def fail_second(item_id,*args,**kwargs):
            if item_id==self.b.pk:raise InventoryError('Lỗi thử ở mặt hàng B')
            return adjust_stock(item_id,*args,**kwargs)
        before=self.snapshot()
        with patch('transactions.services.sales.adjust_stock',side_effect=fail_second),self.assertRaises(InventoryError):self.cancel()
        self.assertEqual(self.snapshot(),before)

    def test_history_write_failure_rolls_back_all_stock(self):
        before=self.snapshot()
        with patch.object(SaleCancellation,'save',side_effect=RuntimeError('audit failed')),self.assertRaises(RuntimeError):self.cancel()
        self.assertEqual(self.snapshot(),before)

    def test_status_write_failure_rolls_back_history_and_stock(self):
        before=self.snapshot()
        with patch.object(Sale,'save',side_effect=RuntimeError('status failed')),self.assertRaises(RuntimeError):self.cancel()
        self.assertEqual(self.snapshot(),before)

    def test_stock_overflow_is_rejected_atomically(self):
        from transactions.services.stock import adjust_stock
        adjust_stock(self.b.pk,2147483647-7,reason='ADJUST')
        before=self.snapshot()
        with self.assertRaises(InventoryError):self.cancel()
        self.assertEqual(self.snapshot(),before)

    def test_cancellation_locks_sale_on_postgres(self):
        with CaptureQueriesContext(connection) as queries:self.cancel()
        if connection.vendor=='postgresql':
            sql=[entry['sql'] for entry in queries if 'FOR UPDATE' in entry['sql']]
            self.assertTrue(any('"sales"' in query for query in sql))
        self.assertEqual(self.stock(),(10,10))

    def test_anonymous_and_normal_user_cannot_get_or_post_cancel(self):
        before=self.snapshot();url=reverse('sale-cancel',args=[self.sale.pk])
        self.client.logout()
        for method in ('get','post'):
            response=getattr(self.client,method)(url,{'reason':'Không đủ quyền'})
            self.assertEqual(response.status_code,302);self.assertIn('/accounts/login/',response.url)
        self.client.force_login(self.normal)
        for method in ('get','post'):self.assertEqual(getattr(self.client,method)(url,{'reason':'Không đủ quyền'}).status_code,403)
        self.assertEqual(self.snapshot(),before)

    def test_get_form_never_changes_stock_and_post_success_shows_message(self):
        url=reverse('sale-cancel',args=[self.sale.pk]);before=self.snapshot()
        self.assertContains(self.client.get(url),'Lý do hủy');self.assertEqual(self.snapshot(),before)
        response=self.client.post(url,{'reason':'Khách yêu cầu hủy'},follow=True)
        self.assertEqual(response.status_code,200)
        self.assertContains(response,'Đã hủy đơn và hoàn kho thành công.')
        self.assertContains(response,'Khách yêu cầu hủy')
        self.assertEqual(self.stock(),(10,10))

    def test_invalid_reason_post_shows_errors_without_changes(self):
        before=self.snapshot()
        response=self.client.post(reverse('sale-cancel',args=[self.sale.pk]),{'reason':'abc'})
        self.assertEqual(response.status_code,200)
        self.assertContains(response,'Lý do hủy phải có ít nhất 5 ký tự.')
        self.assertContains(response,'Không thể hủy đơn.')
        self.assertEqual(self.snapshot(),before)

    def test_repeated_post_shows_error_without_second_restoration(self):
        url=reverse('sale-cancel',args=[self.sale.pk])
        self.client.post(url,{'reason':'Khách yêu cầu hủy'});before=self.snapshot()
        response=self.client.post(url,{'reason':'Thử hủy lần hai'})
        self.assertEqual(response.status_code,200)
        self.assertContains(response,'Đơn đã hủy; không hoàn kho lần nữa.')
        self.assertEqual(self.snapshot(),before)

    def test_csrf_required_for_cancel_post(self):
        client=Client(enforce_csrf_checks=True);client.force_login(self.staff)
        self.assertEqual(client.post(reverse('sale-cancel',args=[self.sale.pk]),{'reason':'Khách yêu cầu hủy'}).status_code,403)
        self.assertEqual(self.stock(),(8,7))

    def test_missing_sale_returns_404(self):
        for method in ('get','post'):
            response=getattr(self.client,method)(reverse('sale-cancel',args=[999999]),{'reason':'Khách yêu cầu hủy'})
            self.assertEqual(response.status_code,404)

    def test_detail_and_list_show_status_and_hide_cancel_button_after_cancel(self):
        url=reverse('sale-cancel',args=[self.sale.pk])
        self.assertContains(self.client.get(reverse('sale-detail',args=[self.sale.pk])),f'href="{url}"')
        self.assertContains(self.client.get(reverse('saleslist')),f'href="{url}"')
        self.cancel()
        stamp=datetime(2026,1,1,17,30,tzinfo=timezone.utc)
        SaleCancellation.objects.filter(sale=self.sale).update(cancelled_at=stamp)
        for name in ('sale-detail','saleslist'):
            response=self.client.get(reverse(name,args=[self.sale.pk]) if name=='sale-detail' else reverse(name))
            self.assertContains(response,'Đã hủy');self.assertNotContains(response,f'href="{url}"')
        detail=self.client.get(reverse('sale-detail',args=[self.sale.pk]))
        for text in ('Khách đổi nhu cầu','ht03-staff','02/01/2026 00:30'):self.assertContains(detail,text)

    def test_normal_user_never_sees_cancel_button(self):
        self.client.force_login(self.normal)
        for url in (reverse('saleslist'),reverse('sale-detail',args=[self.sale.pk])):
            self.assertNotContains(self.client.get(url),reverse('sale-cancel',args=[self.sale.pk]))

    def test_dashboard_revenue_and_count_exclude_cancelled_sales(self):
        other=create_sale(self.customer.pk,[dict(id=self.a.pk,quantity=1)],0,1000,self.staff)
        self.cancel()
        response=self.client.get(reverse('dashboard'))
        self.assertEqual(list(response.context['sales'].values_list('pk',flat=True)),[other.pk])
        self.assertEqual(sum(map(Decimal,response.context['sale_dates_values'])),Decimal(1000))

    def test_status_filter_and_excel_use_same_filtered_ids(self):
        other=create_sale(self.customer.pk,[dict(id=self.a.pk,quantity=1)],0,1000,self.staff)
        self.cancel()
        for status,ids in [('CANCELLED',[self.sale.pk]),('COMPLETED',[other.pk])]:
            params={'status':status,'customer':self.customer.pk}
            response=self.client.get(reverse('saleslist'),params)
            self.assertEqual([s.pk for s in response.context['sales']],ids)
            export=self.client.get(reverse('sales-export'),params)
            book=load_workbook(BytesIO(export.content));self.addCleanup(book.close)
            self.assertEqual([r[0] for r in list(book.active.values)[1:]],ids)
            self.assertEqual(book.active.cell(1,10).value,'Trạng thái')
            self.assertEqual(book.active.cell(2,10).value,'Đã hủy' if status=='CANCELLED' else 'Hoàn tất')
            self.assertContains(response,'status='+status)

    def test_list_totals_are_revenue_excluding_cancelled_but_count_includes_it(self):
        create_sale(self.customer.pk,[dict(id=self.a.pk,quantity=1)],0,1000,self.staff)
        self.cancel()
        response=self.client.get(reverse('saleslist'))
        self.assertEqual((response.context['filtered_count'],response.context['filtered_total']),(2,1000))
        response=self.client.get(reverse('saleslist'),{'status':'CANCELLED'})
        self.assertEqual((response.context['filtered_count'],response.context['filtered_total']),(1,0))

    def test_invalid_status_is_form_error_and_export_400(self):
        response=self.client.get(reverse('saleslist'),{'status':'invalid'})
        self.assertEqual(response.status_code,200);self.assertTrue(response.context['transaction_filter'].errors)
        self.assertEqual(self.client.get(reverse('sales-export'),{'status':'invalid'}).status_code,400)

    def test_completed_cannot_be_deleted_and_integer_url_resolves(self):
        self.client.force_login(self.superuser)
        url=reverse('sale-delete',kwargs={'pk':self.sale.pk})
        self.assertEqual(resolve(url).kwargs,{'pk':self.sale.pk})
        for method in ('get','post'):self.assertEqual(getattr(self.client,method)(url).status_code,403)
        self.assertEqual(self.stock(),(8,7));self.assertTrue(Sale.objects.filter(pk=self.sale.pk).exists())

    def test_only_superuser_can_delete_cancelled_and_history_survives(self):
        record=self.cancel();before=self.stock();sale_id=self.sale.pk
        url=reverse('sale-delete',args=[sale_id])
        self.assertEqual(self.client.post(url).status_code,403)
        self.client.force_login(self.superuser)
        self.assertContains(self.client.get(url),f'#{sale_id}')
        self.assertEqual(self.client.post(url).status_code,302)
        self.assertFalse(Sale.objects.filter(pk=sale_id).exists());self.assertEqual(self.stock(),before)
        record.refresh_from_db();self.assertIsNone(record.sale_id)
        self.assertEqual(record.sale_reference,sale_id);self.assertEqual(record.cancelled_by_id,self.staff.pk)
        self.assertEqual(StockMovement.objects.filter(reason='SALE_CANCEL').count(),2)

    def test_actor_is_protected_from_deletion(self):
        self.cancel()
        with self.assertRaises(ProtectedError):self.staff.delete()

    def test_cancellation_admin_is_read_only_and_sale_status_not_editable(self):
        record=self.cancel();request=RequestFactory().get('/admin/');request.user=self.superuser
        registered=admin.site._registry[SaleCancellation]
        self.assertFalse(registered.has_add_permission(request))
        self.assertFalse(registered.has_change_permission(request,record))
        self.assertFalse(registered.has_delete_permission(request,record))
        self.assertIn('restored_items',registered.readonly_fields)
        sale_admin=admin.site._registry[Sale]
        self.assertIn('status',sale_admin.readonly_fields)
        self.assertNotIn('delete_selected',sale_admin.get_actions(request))

    def test_sale_admin_refuses_completed_or_non_superuser_delete(self):
        request=RequestFactory().get('/admin/');request.user=self.superuser
        sale_admin=admin.site._registry[Sale]
        self.assertFalse(sale_admin.has_delete_permission(request,self.sale))
        with self.assertRaises(PermissionDenied):sale_admin.delete_model(request,self.sale)
        with self.assertRaises(PermissionDenied):sale_admin.delete_queryset(request,Sale.objects.filter(pk=self.sale.pk))
        self.cancel();self.sale.refresh_from_db();request.user=self.staff
        self.assertFalse(sale_admin.has_delete_permission(request,self.sale))
        with self.assertRaises(PermissionDenied):sale_admin.delete_model(request,self.sale)

    def test_restoration_removes_items_from_ht01_low_stock_list(self):
        self.assertEqual(set(Item.objects.needs_restock().values_list('pk',flat=True)),{self.a.pk,self.b.pk})
        self.cancel()
        self.assertFalse(Item.objects.needs_restock().filter(pk__in=[self.a.pk,self.b.pk]).exists())
        self.assertEqual(self.client.get(reverse('low-stock')).context['paginator'].count,0)

    def test_reconcile_has_zero_stock_and_trade_differences_after_cancel_and_delete(self):
        self.cancel()
        for deleted in (False,True):
            if deleted:
                self.client.force_login(self.superuser)
                self.client.post(reverse('sale-delete',args=[self.sale.pk]))
            output=StringIO();call_command('reconcile_stock',stdout=output)
            rows=json.loads(output.getvalue())['items']
            self.assertEqual(len(rows),2)
            for row in rows:
                self.assertEqual((row['difference'],row['ledger_minus_trade']),(0,0))
                self.assertEqual(row['quantity'],10)

    def test_database_rejects_invalid_status_and_short_reason_and_duplicate_history(self):
        with self.assertRaises(IntegrityError),transaction.atomic():Sale.objects.filter(pk=self.sale.pk).update(status='INVALID')
        self.cancel()
        with self.assertRaises(IntegrityError),transaction.atomic():SaleCancellation.objects.filter(sale=self.sale).update(reason='abc')
        with self.assertRaises(IntegrityError),transaction.atomic():
            SaleCancellation.objects.create(sale=self.sale,sale_reference=self.sale.pk,cancelled_by=self.staff,reason='Trùng lịch sử')
