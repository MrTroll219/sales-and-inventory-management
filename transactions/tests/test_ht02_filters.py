from datetime import datetime, timezone
from decimal import Decimal
from io import BytesIO
from urllib.parse import parse_qs

from django.contrib.auth import get_user_model
from django.test import TestCase, RequestFactory
from django.urls import reverse
from openpyxl import load_workbook

from accounts.models import Customer, Vendor
from store.models import Category
from transactions.models import Sale, Purchase, StockMovement
from transactions.filters import filtered_transactions
from transactions.services.stock import save_item
from transactions.services.sales import create_sale
from transactions.services.purchases import create_purchase
from transactions.views import export_sales_to_excel, export_purchases_to_excel


class TransactionFilterTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(username='ht02', is_staff=True, is_superuser=True)
        cls.a = Customer.objects.create(first_name='An', last_name='Nguyễn', phone='0901111111')
        cls.b = Customer.objects.create(first_name='Bình', last_name=None, phone='0902222222')
        cls.va = Vendor.objects.create(name='Nhà cung cấp A')
        cls.vb = Vendor.objects.create(name='Nhà cung cấp B')
        category = Category.objects.create(name='HT02')
        cls.item = save_item(dict(name='Giấy',description='HT02',category=category,vendor=cls.va,price=1000,quantity=1000))
        cls.other = save_item(dict(name='Bút',description='HT02',category=category,vendor=cls.vb,price=1000,quantity=1000))
        stamps = ['2026-10-31T16:59:59+00:00', '2026-10-31T17:00:00+00:00',
                  '2026-11-30T16:59:59.999999+00:00', '2026-11-30T17:00:00+00:00',
                  '2026-11-15T10:00:00+00:00']
        cls.sales, cls.purchases = [], []
        for index, text in enumerate(stamps):
            customer = cls.a if index in (0,1,2) else cls.b
            item = cls.item if index in (0,1,2) else cls.other
            sale = create_sale(customer.pk,[dict(id=item.pk,quantity=index+1)],0,1000*(index+1),cls.user)
            purchase = create_purchase(dict(item=item,vendor=cls.va if index in (0,1,2) else cls.vb,
                price=1000,quantity=index+1,delivery_status='S' if index==2 else 'P'))
            stamp = datetime.fromisoformat(text)
            Sale.objects.filter(pk=sale.pk).update(date_added=stamp)
            Purchase.objects.filter(pk=purchase.pk).update(order_date=stamp)
            cls.sales.append(sale); cls.purchases.append(purchase)

    def setUp(self):
        self.client.force_login(self.user)

    def params(self, **more):
        return dict(date_from='01/11/2026',date_to='30/11/2026',**more)

    def ids(self, kind, params):
        filters, queryset = filtered_transactions(kind, params)
        self.assertTrue(filters.is_valid(), filters.errors)
        return list(queryset.values_list('pk',flat=True))

    def list_response(self, kind, params):
        return self.client.get(reverse('saleslist' if kind=='sales' else 'purchaseslist'), params)

    def export(self, kind, params):
        return self.client.get(reverse('sales-export' if kind=='sales' else 'purchases-export'), params)

    def excel_rows(self, response):
        self.assertEqual(response.status_code,200)
        book=load_workbook(BytesIO(response.content)); self.addCleanup(book.close)
        return list(book.active.iter_rows(min_row=2,values_only=True))

    def test_vietnam_date_bounds_include_last_microsecond_exclude_next_midnight(self):
        for kind, records in [('sales',self.sales),('purchases',self.purchases)]:
            with self.subTest(kind=kind):
                self.assertEqual(self.ids(kind,self.params()),[records[i].pk for i in (2,4,1)])

    def test_date_from_and_date_to_work_independently(self):
        self.assertEqual(self.ids('sales',{'date_from':'01/12/2026'}),[self.sales[3].pk])
        self.assertEqual(self.ids('sales',{'date_to':'31/10/2026'}),[self.sales[0].pk])

    def test_same_day_range_includes_2359_vietnam(self):
        for kind, records in [('sales',self.sales),('purchases',self.purchases)]:
            self.assertEqual(self.ids(kind,dict(date_from='30/11/2026',date_to='30/11/2026')),[records[2].pk])

    def test_iso_dates_equal_vietnamese_dates(self):
        self.assertEqual(self.ids('sales',{'date_from':'2026-11-01','date_to':'2026-11-30'}),self.ids('sales',self.params()))

    def test_customer_and_combined_date_customer(self):
        self.assertEqual(self.ids('sales',{'customer':self.a.pk}),[self.sales[i].pk for i in (2,1,0)])
        self.assertEqual(self.ids('sales',self.params(customer=self.a.pk)),[self.sales[i].pk for i in (2,1)])

    def test_customer_search_full_name_phone_and_nullable_last_name(self):
        for query, expected in [('An Nguyễn',(2,1,0)),('090111',(2,1,0)),('Bình',(3,4)),('absent',())]:
            with self.subTest(query=query):
                self.assertEqual(self.ids('sales',{'q':query}),[self.sales[i].pk for i in expected])

    def test_money_range_is_inclusive_and_combines_with_customer(self):
        self.assertEqual(self.ids('sales',{'min':'2000','max':'3000'}),[self.sales[i].pk for i in (2,1)])
        self.assertEqual(self.ids('sales',dict(customer=self.a.pk,min='3000',max='3000')),[self.sales[2].pk])
        self.assertEqual(self.ids('sales',{'min':'5000'}),[self.sales[4].pk])
        self.assertEqual(self.ids('sales',{'max':'1000'}),[self.sales[0].pk])

    def test_purchase_vendor_item_status_and_combination(self):
        for params, indices in [({'vendor':self.va.pk},(2,1,0)),({'item':self.other.pk},(3,4)),
                                ({'delivery_status':'S'},(2,)),(self.params(vendor=self.va.pk,item=self.item.pk,delivery_status='P'),(1,))]:
            self.assertEqual(self.ids('purchases',params),[self.purchases[i].pk for i in indices])

    def test_no_parameters_returns_all_newest_first_in_list_and_excel(self):
        for kind, records in [('sales',self.sales),('purchases',self.purchases)]:
            expected=[records[i].pk for i in (3,2,4,1,0)]
            response=self.list_response(kind,{})
            self.assertEqual([row.pk for row in response.context[kind]],expected)
            self.assertEqual([row[0] for row in self.excel_rows(self.export(kind,{}))],expected)
            self.assertIn('filename='+kind+'.xlsx',self.export(kind,{})['Content-Disposition'])

    def test_equal_timestamps_have_stable_pk_tiebreak(self):
        stamp=datetime(2026,11,1,tzinfo=timezone.utc)
        Sale.objects.all().update(date_added=stamp)
        self.assertEqual(self.ids('sales',{}),sorted([s.pk for s in self.sales],reverse=True))

    def test_every_valid_filter_exports_exact_list_queryset(self):
        cases=[('sales',self.params(customer=self.a.pk)),('sales',{'q':'090222','min':'4000'}),
               ('purchases',self.params(vendor=self.va.pk)),('purchases',{'item':self.other.pk,'delivery_status':'P'})]
        for kind, params in cases:
            with self.subTest(kind=kind,params=params):
                response=self.list_response(kind,params)
                rows=self.excel_rows(self.export(kind,params))
                self.assertEqual([r[0] for r in rows],[r.pk for r in response.context['view'].object_list])
                self.assertEqual(len(rows),response.context['filtered_count'])

    def test_count_and_money_are_for_full_filtered_set(self):
        for kind in ('sales','purchases'):
            response=self.list_response(kind,self.params())
            self.assertEqual(response.context['filtered_count'],3)
            self.assertEqual(response.context['filtered_total'],Decimal(10000))
            self.assertContains(response,'10.000 ₫')

    def test_pagination_and_export_links_keep_query_and_totals_include_all_pages(self):
        for _ in range(11):
            create_sale(self.a.pk,[dict(id=self.item.pk,quantity=1)],0,1000,self.user)
        response=self.list_response('sales',{'customer':self.a.pk,'q':'An','page':'2'})
        self.assertEqual(response.context['filtered_count'],14)
        self.assertEqual(response.context['filtered_total'],Decimal(17000))
        self.assertEqual(len(response.context['sales']),4)
        self.assertContains(response,f'customer={self.a.pk}&amp;q=An&amp;page=1')
        self.assertContains(response,f'/transactions/sales/export/?customer={self.a.pk}&amp;q=An')
        self.assertNotIn('page=',response.context['filter_query'])
        self.assertEqual(len(self.excel_rows(self.export('sales',{'customer':self.a.pk,'q':'An','page':'2'}))),14)

    def test_purchase_pagination_keeps_vendor_item_and_status(self):
        for _ in range(11):
            create_purchase(dict(item=self.item,vendor=self.va,quantity=1,price=1000))
        params=dict(vendor=self.va.pk,item=self.item.pk,delivery_status='P',page=2)
        response=self.list_response('purchases',params)
        self.assertEqual(response.context['filtered_count'],13)
        self.assertEqual(response.context['filtered_total'],Decimal(14000))
        query=response.context['filter_query']
        self.assertNotIn('page=',query)
        self.assertEqual(parse_qs(query),{'vendor':[str(self.va.pk)],'item':[str(self.item.pk)],'delivery_status':['P']})
        self.assertContains(response,query.replace('&','&amp;')+'&amp;page=1')

    def test_reversed_dates_show_error_and_export_400_not_all_data(self):
        for kind in ('sales','purchases'):
            params=dict(date_from='30/11/2026',date_to='01/11/2026')
            response=self.list_response(kind,params)
            self.assertEqual(response.status_code,200)
            self.assertContains(response,'Ngày kết thúc phải bằng hoặc sau ngày bắt đầu.')
            self.assertEqual(response.context['filtered_count'],0)
            self.assertEqual(self.export(kind,params).status_code,400)

    def test_invalid_parameters_are_errors_never_500(self):
        cases=[('sales',{'customer':'abc'}),('sales',{'customer':'9999999999999999999999999'}),
               ('sales',{'min':'xyz'}),('sales',{'min':'NaN'}),('sales',{'max':'Infinity'}),
               ('sales',{'min':'-1'}),('sales',{'min':'1000.5'}),('sales',{'max':'1000000000000000'}),
               ('sales',{'q':'x'*257}),('purchases',{'vendor':'abc'}),('purchases',{'item':'abc'}),
               ('purchases',{'delivery_status':'invalid'}),('sales',{'date_to':'31/02/2026'}),
               ('purchases',{'date_from':'bad'}),('sales',{'date_from':'01/01/0001'})]
        for kind, params in cases:
            with self.subTest(kind=kind,params=params):
                response=self.list_response(kind,params)
                self.assertEqual(response.status_code,200)
                self.assertTrue(response.context['transaction_filter'].errors)
                self.assertEqual(response.context['filtered_count'],0)
                export=self.export(kind,params)
                self.assertEqual(export.status_code,400)
                self.assertEqual(export.json()['status'],'error')

    def test_reversed_money_range_is_validation_error(self):
        response=self.list_response('sales',{'min':'3000','max':'2000'})
        self.assertContains(response,'Tổng tiền tối đa phải bằng hoặc lớn hơn tối thiểu.')
        self.assertEqual(response.context['filtered_count'],0)

    def test_blank_and_unknown_parameters_preserve_unfiltered_results(self):
        self.assertEqual(len(self.ids('sales',dict(q='',customer='',min='',max='',date_from='',unknown='ignored'))),5)
        self.assertEqual(len(self.ids('purchases',dict(vendor='',item='',delivery_status='',unknown='ignored'))),5)

    def test_empty_result_has_zero_summary_and_header_only_excel(self):
        for kind in ('sales','purchases'):
            params={'date_from':'01/01/2030'}
            response=self.list_response(kind,params)
            self.assertEqual((response.context['filtered_count'],response.context['filtered_total']),(0,0))
            self.assertEqual(self.excel_rows(self.export(kind,params)),[])

    def test_filenames_include_normalized_date_range(self):
        for kind in ('sales','purchases'):
            self.assertIn(f'filename={kind}_2026-11-01_2026-11-30.xlsx',self.export(kind,self.params())['Content-Disposition'])
            self.assertIn(f'filename={kind}_2026-11-01_all.xlsx',self.export(kind,{'date_from':'01/11/2026'})['Content-Disposition'])

    def test_excel_keeps_vietnam_time_headers_and_vnd_formats(self):
        stamp=datetime(2026,11,30,16,59,tzinfo=timezone.utc)
        Sale.objects.filter(pk=self.sales[2].pk).update(date_added=stamp)
        Purchase.objects.filter(pk=self.purchases[2].pk).update(order_date=stamp)
        for kind,column,moneycolumn in [('sales',2,5),('purchases',5,10)]:
            response=self.export(kind,dict(date_from='30/11/2026',date_to='30/11/2026'))
            book=load_workbook(BytesIO(response.content)); self.addCleanup(book.close)
            sheet=book.active
            self.assertEqual(sheet.cell(2,column).value,datetime(2026,11,30,23,59))
            self.assertIn('(VND)',sheet.cell(1,moneycolumn).value)
            self.assertEqual(sheet.cell(2,moneycolumn).number_format,'#,##0 "₫"')

    def test_exports_use_one_joined_query_independent_of_row_count(self):
        for kind, view in [('sales',export_sales_to_excel),('purchases',export_purchases_to_excel)]:
            for params, count in [({},5),({'date_from':'01/12/2026'},1)]:
                request=RequestFactory().get('/',params); request.user=self.user
                with self.assertNumQueries(1):
                    response=view(request)
                self.assertEqual(len(self.excel_rows(response)),count)

    def test_list_querysets_join_related_objects_without_n_plus_one(self):
        for kind in ('sales','purchases'):
            filters, queryset=filtered_transactions(kind,{})
            with self.assertNumQueries(1):
                for row in queryset:
                    if kind=='sales': str(row.customer)
                    else: row.item.name; row.vendor.name

    def test_anonymous_cannot_list_or_export(self):
        self.client.logout()
        for name in ('saleslist','purchaseslist','sales-export','purchases-export'):
            response=self.client.get(reverse(name))
            self.assertEqual(response.status_code,302)
            self.assertIn('/accounts/login/',response.url)

    def test_filtering_and_export_never_write_inventory_or_ledger(self):
        self.item.refresh_from_db(); quantity=self.item.quantity
        movements=StockMovement.objects.count()
        for kind in ('sales','purchases'):
            self.list_response(kind,self.params()); self.export(kind,self.params())
        self.item.refresh_from_db()
        self.assertEqual(self.item.quantity,quantity)
        self.assertEqual(StockMovement.objects.count(),movements)
