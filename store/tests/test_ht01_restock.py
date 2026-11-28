from datetime import datetime, timezone as utc
from io import BytesIO
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse
from openpyxl import load_workbook
from accounts.models import Customer, Vendor
from store.forms import ItemForm
from store.models import Category, Item
from transactions.models import Purchase, StockMovement
from transactions.services.stock import save_item, adjust_stock
from transactions.services.sales import create_sale
from transactions.services.purchases import create_purchase


class RestockTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user=get_user_model().objects.create_user(username='ht01',is_superuser=True,is_staff=True)
        cls.category=Category.objects.create(name='Thiết bị HT01')
        cls.vendor=Vendor.objects.create(name='Nhà cung cấp HT01')
        cls.customer=Customer.objects.create(first_name='Khách HT01')
        cls.low=cls.item('Thiếu hai',3,5)
        cls.boundary=cls.item('Chạm ngưỡng',5,5)
        cls.enough=cls.item('Đủ hàng',6,5)
        cls.disabled=cls.item('Tắt cảnh báo',0,0)

    @classmethod
    def item(cls,name,quantity,level,vendor=True):
        return save_item({'name':name,'description':'Dữ liệu thử HT01','category':cls.category,
            'vendor':cls.vendor if vendor else None,'price':1000,'quantity':quantity,'min_stock_level':level})

    def setUp(self):
        self.client.force_login(self.user)

    def form_data(self,**changes):
        data={'name':self.low.name,'description':self.low.description,'category':self.category.pk,
              'vendor':self.vendor.pk,'price':'1000','quantity':self.low.quantity}
        data.update(changes)
        return data

    def workbook(self):
        response=self.client.get(reverse('low-stock-export'))
        self.assertEqual(response.status_code,200)
        self.assertIn('application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',response['Content-Type'])
        book=load_workbook(BytesIO(response.content)); self.addCleanup(book.close)
        return book

    def test_boundaries_match_queryset_and_property(self):
        self.assertEqual(set(Item.objects.needs_restock().values_list('pk',flat=True)),{self.low.pk,self.boundary.pk})
        self.assertTrue(self.low.needs_restock)
        self.assertTrue(self.boundary.needs_restock)
        self.assertFalse(self.enough.needs_restock)
        self.assertFalse(self.disabled.needs_restock)

    def test_zero_threshold_disables_warning_for_any_nonnegative_stock(self):
        for quantity in (0,3,100):
            item=self.item(f'Tắt {quantity}',quantity,0)
            self.assertFalse(item.needs_restock)
            self.assertFalse(Item.objects.needs_restock().filter(pk=item.pk).exists())
            self.assertEqual(item.suggested_order_qty,0)

    def test_shortage_and_suggested_quantity_follow_formula(self):
        self.assertEqual((self.low.stock_shortage,self.low.suggested_order_qty),(2,7))
        self.assertEqual((self.boundary.stock_shortage,self.boundary.suggested_order_qty),(0,5))
        self.assertEqual((self.enough.stock_shortage,self.enough.suggested_order_qty),(0,4))

    def test_large_threshold_formula_does_not_overflow_postgres_integer(self):
        item=self.item('Ngưỡng lớn',0,2147483647)
        self.assertEqual(item.suggested_order_qty,4294967294)
        self.assertEqual(Item.objects.restock_list().first().pk,item.pk)

    def test_list_orders_by_shortage_descending(self):
        worst=self.item('Thiếu nhiều nhất',1,10)
        response=self.client.get(reverse('low-stock'))
        self.assertEqual(response.status_code,200)
        self.assertEqual([i.pk for i in response.context['items']],[worst.pk,self.low.pk,self.boundary.pk])
        self.assertContains(response,'Tạo phiếu nhập')
        self.assertContains(response,f"{reverse('purchase-create')}?item={self.low.pk}")

    def test_sale_enters_list_and_purchase_to_target_leaves_it(self):
        create_sale(self.customer.pk,[{'id':self.enough.pk,'quantity':3}],0,3000,self.user)
        self.assertTrue(Item.objects.needs_restock().filter(pk=self.enough.pk).exists())
        current=Item.objects.get(pk=self.enough.pk)
        self.assertEqual(current.quantity,3)
        create_purchase({'item':current,'vendor':self.vendor,'price':1000,'quantity':current.suggested_order_qty})
        current.refresh_from_db()
        self.assertEqual(current.quantity,10)
        self.assertFalse(current.needs_restock)
        self.assertFalse(Item.objects.needs_restock().filter(pk=current.pk).exists())

    def test_dashboard_count_and_link_match_list(self):
        response=self.client.get(reverse('dashboard'))
        self.assertEqual(response.context['low_stock_count'],2)
        self.assertContains(response,'Cần nhập hàng:')
        self.assertContains(response,f'id="low-stock-card" class="restock-card" href="{reverse("low-stock")}"')
        create_sale(self.customer.pk,[{'id':self.enough.pk,'quantity':1}],0,1000,self.user)
        self.assertEqual(self.client.get(reverse('dashboard')).context['low_stock_count'],3)

    def test_anonymous_list_export_and_dashboard_redirect(self):
        self.client.logout()
        for name in ('low-stock','low-stock-export','dashboard'):
            with self.subTest(name=name):
                response=self.client.get(reverse(name))
                self.assertEqual(response.status_code,302)
                self.assertIn('/accounts/login/',response.url)

    def test_purchase_prefill_is_initial_only_and_does_not_write(self):
        before=Purchase.objects.count(),StockMovement.objects.count()
        response=self.client.get(reverse('purchase-create'),{'item':self.low.pk})
        self.assertEqual(response.status_code,200)
        self.assertEqual(int(response.context['form']['item'].value()),self.low.pk)
        self.assertEqual((Purchase.objects.count(),StockMovement.objects.count()),before)
        response=self.client.post(reverse('purchase-create')+f'?item={self.low.pk}',
            {'item':self.enough.pk,'vendor':self.vendor.pk,'quantity':2,'price':'1000','delivery_status':'P'})
        self.assertEqual(response.status_code,302)
        self.assertEqual(Purchase.objects.get().item_id,self.enough.pk)

    def test_invalid_prefill_is_ignored_without_server_error(self):
        for value in ('abc','-1','0','999999999999999999999999','999999'):
            with self.subTest(value=value):
                response=self.client.get(reverse('purchase-create'),{'item':value})
                self.assertEqual(response.status_code,200)
                self.assertIsNone(response.context['form']['item'].value())

    def test_threshold_form_rejects_negative_fractional_and_overflow(self):
        for level in ('-1','1.5','2147483648'):
            with self.subTest(level=level):
                form=ItemForm(instance=self.low,data=self.form_data(min_stock_level=level))
                self.assertFalse(form.is_valid())
                self.assertIn('min_stock_level',form.errors)

    def test_threshold_negative_is_rejected_by_model_and_database(self):
        self.low.min_stock_level=-1
        with self.assertRaises(ValidationError): self.low.full_clean()
        with self.assertRaises(IntegrityError),transaction.atomic():
            Item.objects.filter(pk=self.low.pk).update(min_stock_level=-1)

    def test_edit_threshold_only_does_not_change_stock_or_ledger(self):
        form=ItemForm(instance=self.low,data=self.form_data(min_stock_level=8))
        self.assertTrue(form.is_valid(),form.errors)
        before=StockMovement.objects.count()
        item=form.save()
        self.assertEqual((item.min_stock_level,item.quantity),(8,3))
        self.assertEqual(StockMovement.objects.count(),before)

    def test_threshold_edit_does_not_overwrite_stock_changed_after_form_validation(self):
        form=ItemForm(instance=self.low,data=self.form_data(min_stock_level=8))
        self.assertTrue(form.is_valid(),form.errors)
        adjust_stock(self.low.pk,-1,reason='ADJUST')
        item=form.save()
        self.assertEqual((item.min_stock_level,item.quantity),(8,2))

    def test_omitted_threshold_preserves_old_value_and_new_item_defaults_to_zero(self):
        form=ItemForm(instance=self.low,data=self.form_data())
        self.assertTrue(form.is_valid(),form.errors)
        self.assertEqual(form.save().min_stock_level,5)
        form=ItemForm(data=self.form_data(name='Khách cũ tạo hàng'))
        self.assertTrue(form.is_valid(),form.errors)
        self.assertEqual(form.save().min_stock_level,0)

    def test_product_edit_page_shows_threshold_and_can_disable_it(self):
        url=reverse('product-update',kwargs={'slug':self.low.slug})
        response=self.client.get(url)
        self.assertContains(response,'name="min_stock_level"')
        self.assertContains(response,'Tồn tối thiểu')
        response=self.client.post(url,self.form_data(min_stock_level=0))
        self.assertEqual(response.status_code,302)
        self.low.refresh_from_db()
        self.assertEqual((self.low.min_stock_level,self.low.quantity),(0,3))
        self.assertFalse(self.low.needs_restock)

    def test_only_low_stock_product_rows_are_highlighted(self):
        response=self.client.get(reverse('productslist'))
        self.assertContains(response,f'<tr data-item-id="{self.low.pk}" class="table-warning low-stock-row">',html=False)
        self.assertContains(response,f'<tr data-item-id="{self.boundary.pk}" class="table-warning low-stock-row">',html=False)
        self.assertNotContains(response,f'<tr data-item-id="{self.enough.pk}" class="table-warning low-stock-row">')
        self.assertNotContains(response,f'<tr data-item-id="{self.disabled.pk}" class="table-warning low-stock-row">')

    def test_excel_matches_live_list_has_vietnamese_headers_and_vn_timestamp(self):
        with patch('store.views.timezone.now',return_value=datetime(2026,1,1,17,30,tzinfo=utc.utc)):
            book=self.workbook()
        sheet=book.active
        self.assertEqual([c.value for c in sheet[1]],['Tên','Danh mục','Tồn','Ngưỡng tối thiểu','Thiếu','Đề xuất nhập','Nhà cung cấp'])
        self.assertEqual(sheet.max_row,3)
        self.assertEqual([c.value for c in sheet[2]],[self.low.name,self.category.name,3,5,2,7,self.vendor.name])
        self.assertEqual([c.number_format for c in sheet[2][2:6]],['0']*4)
        self.assertEqual(book['Thông tin']['B1'].value,datetime(2026,1,2,0,30))
        self.assertEqual(book['Thông tin']['B1'].number_format,'DD/MM/YYYY HH:MM')

    def test_empty_list_and_excel_are_valid(self):
        Item.objects.update(min_stock_level=0)
        response=self.client.get(reverse('low-stock'))
        self.assertContains(response,'Không có mặt hàng nào cần nhập.')
        self.assertEqual(self.workbook().active.max_row,1)
        self.assertEqual(self.client.get(reverse('dashboard')).context['low_stock_count'],0)

    def test_export_includes_items_beyond_list_pagination_and_missing_vendor(self):
        for i in range(26): self.item(f'Bổ sung {i:02}',0,1,vendor=False)
        response=self.client.get(reverse('low-stock'))
        self.assertEqual(len(response.context['items']),25)
        book=self.workbook()
        self.assertEqual(book.active.max_row,29)
        rows=list(book.active.iter_rows(min_row=2,values_only=True))
        self.assertTrue(any(row[0]=='Bổ sung 00' and row[6] is None for row in rows))
