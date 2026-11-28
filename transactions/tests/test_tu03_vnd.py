from datetime import datetime, timezone as utc
from decimal import Decimal
from io import BytesIO
from pathlib import Path
import re
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import connection, IntegrityError, transaction
from django.forms import modelform_factory
from django.template import Context, Template
from django.test import TestCase, SimpleTestCase
from django.urls import reverse
from django.utils import timezone
from openpyxl import load_workbook
from accounts.models import Customer, Vendor
from store.models import Item, Category
from store.forms import ItemForm
from store.money import to_vnd, format_vnd, INTEGER_MESSAGE, MAX_MONEY
from invoice.models import Invoice
from bills.models import Bill
from transactions.models import Sale, Purchase, StockMovement
from transactions.forms import PurchaseForm
from transactions.pricing import check_client_total, SaleInputError
from transactions.services.stock import adjust_stock
from transactions.services.sales import create_sale
from transactions.services.purchases import create_purchase
from transactions.migrations._dp02_data import MONEY


class VNDCurrencyTests(SimpleTestCase):
    def test_half_up_rounding(self):
        for raw, expected in [('1234.5',1235), ('1234.4',1234), ('19.99',20), ('-1.5',-2)]:
            with self.subTest(raw=raw): self.assertEqual(to_vnd(raw), Decimal(expected))

    def test_formatter_and_template_filter(self):
        self.assertEqual(format_vnd(1250000), '1.250.000 ₫')
        self.assertEqual(Template('{% load vietnam %}{{ value|vnd }}').render(Context({'value':1250000})), '1.250.000 ₫')

    def test_nonfinite_and_boolean_money_is_rejected(self):
        for value in ('NaN','Infinity',True,None):
            with self.subTest(value=value), self.assertRaises(ValueError): to_vnd(value)

    def test_settings_are_vietnamese_and_keep_aware_datetimes(self):
        self.assertEqual((settings.TIME_ZONE,settings.LANGUAGE_CODE,settings.CURRENCY_CODE), ('Asia/Ho_Chi_Minh','vi','VND'))
        self.assertTrue(settings.USE_TZ)
        self.assertIn('%d/%m/%Y', settings.DATE_INPUT_FORMATS)
        self.assertIn('%d/%m/%Y %H:%M', settings.DATETIME_INPUT_FORMATS)
        self.assertEqual(MAX_MONEY, Decimal('999999999999999'))

    def test_no_legacy_currency_units_in_templates(self):
        root=Path(__file__).resolve().parents[2]
        violations=[]
        for app in ('store','transactions','invoice','bills','accounts'):
            for path in (root/app/'templates').rglob('*.html'):
                text=path.read_text(encoding='utf-8')
                if 'Ksh' in text or re.search(r"['\"]\s*\$['\"]|\$\s*\{\{",text): violations.append(str(path))
        self.assertEqual(violations,[])

    def test_client_totals_have_zero_tolerance(self):
        for amount in ('199.99','200.01','201'):
            with self.subTest(amount=amount), self.assertRaises(SaleInputError):
                check_client_total({'grand_total':amount},'grand_total',Decimal(200))
        check_client_total({'grand_total':'200.00'},'grand_total',Decimal(200))


class VNDApplicationTests(TestCase):
    def setUp(self):
        self.category=Category.objects.create(name='TU03')
        self.vendor=Vendor.objects.create(name='Nhà cung cấp TU03')
        self.item=Item.objects.create(name='Sản phẩm TU03',category=self.category,vendor=self.vendor,price=33333)
        adjust_stock(self.item.pk,10,reason='ADJUST')
        self.customer=Customer.objects.create(first_name='Khách TU03')
        self.user=get_user_model().objects.create_user(username='tu03')
        self.client.force_login(self.user)

    def sale(self):
        return create_sale(self.customer.pk,[{'id':self.item.pk,'quantity':3}],10,110000,self.user)

    def test_sale_tax_rounds_to_dong_and_inventory_is_unchanged_in_policy(self):
        sale=self.sale()
        self.assertEqual((sale.sub_total,sale.tax_amount,sale.grand_total,sale.amount_change),
                         tuple(map(Decimal,['99999','10000','109999','1'])))
        self.item.refresh_from_db()
        self.assertEqual(self.item.quantity,7)
        self.assertEqual(StockMovement.objects.latest('pk').delta,-3)

    def test_all_money_forms_reject_fraction_and_accept_integral_value(self):
        cases=[(ItemForm,{'name':'Form','description':'TU03','category':self.category.pk,
                         'vendor':self.vendor.pk,'quantity':1},'price'),
               (PurchaseForm,{'item':self.item.pk,'vendor':self.vendor.pk,'quantity':1,'delivery_status':'P'},'price'),
               (modelform_factory(Invoice,fields=['customer_name','contact_number','item','quantity','shipping','price_per_item']),
                {'customer_name':'Khách','contact_number':'123','item':self.item.pk,'quantity':1,'shipping':0},'price_per_item'),
               (modelform_factory(Bill,fields=['institution_name','payment_details','amount']),
                {'institution_name':'Đơn vị','payment_details':'Tiền mặt'},'amount')]
        for cls,data,field in cases:
            with self.subTest(field=field,form=cls.__name__):
                form=cls(data=dict(data,**{field:'1000.5'}))
                self.assertFalse(form.is_valid())
                self.assertIn(INTEGER_MESSAGE,form.errors[field])
                valid=cls(data=dict(data,**{field:'1000.00'}))
                self.assertTrue(valid.is_valid(),valid.errors)

    def test_vietnamese_datetime_form_input_is_accepted(self):
        form=PurchaseForm(data={'item':self.item.pk,'vendor':self.vendor.pk,'quantity':1,'price':'1000',
            'delivery_status':'P','delivery_date':'02/01/2026 00:30'})
        self.assertTrue(form.is_valid(),form.errors)
        self.assertEqual(form.cleaned_data['delivery_date'].astimezone(utc.utc),datetime(2026,1,1,17,30,tzinfo=utc.utc))

    def test_excel_sales_forces_vn_time_and_numeric_vnd_columns(self):
        sale=self.sale()
        Sale.objects.filter(pk=sale.pk).update(date_added=datetime(2026,1,1,17,30,tzinfo=utc.utc))
        with timezone.override('UTC'):
            response=self.client.get(reverse('sales-export'))
        self.assertEqual(response.status_code,200)
        workbook=load_workbook(BytesIO(response.content)); self.addCleanup(workbook.close)
        sheet=workbook.active
        self.assertEqual(sheet.cell(2,2).value,datetime(2026,1,2,0,30))
        self.assertEqual(sheet.cell(2,5).value,109999)
        for col in (4,5,6,8,9):
            self.assertEqual(sheet.cell(2,col).number_format,'#,##0 "₫"')
            self.assertIn('(VND)',sheet.cell(1,col).value)

    def test_excel_purchases_keeps_missing_delivery_empty(self):
        create_purchase({'item':self.item,'vendor':self.vendor,'quantity':2,'price':1000})
        response=self.client.get(reverse('purchases-export'))
        workbook=load_workbook(BytesIO(response.content)); self.addCleanup(workbook.close)
        sheet=workbook.active
        self.assertIsNone(sheet.cell(2,6).value)
        for col in (9,10): self.assertEqual(sheet.cell(2,col).number_format,'#,##0 "₫"')

    def test_sale_detail_displays_vnd_and_vietnamese_date(self):
        sale=self.sale()
        Sale.objects.filter(pk=sale.pk).update(date_added=datetime(2026,1,1,17,30,tzinfo=utc.utc))
        response=self.client.get(reverse('sale-detail',kwargs={'pk':sale.pk}))
        self.assertContains(response,'109.999 ₫')
        self.assertContains(response,'02/01/2026 00:30')
        self.assertContains(response,'Tổng cộng')
        self.assertNotContains(response,'Ksh')

    def test_all_money_fields_have_zero_scale_and_integrality_checks(self):
        from django.apps import apps
        for (app,name),fields in MONEY.items():
            model=apps.get_model(app,name)
            with connection.cursor() as cursor:
                constraints=connection.introspection.get_constraints(cursor,model._meta.db_table)
            for field in fields:
                with self.subTest(model=name,field=field):
                    self.assertEqual((model._meta.get_field(field).max_digits,model._meta.get_field(field).decimal_places),(15,0))
                    self.assertTrue(constraints[f'{name.lower()}_{field}_vnd_int']['check'])
        self.assertEqual(Sale._meta.get_field('tax_percentage').decimal_places,2)

    def test_sqlite_cannot_store_fractional_money_via_raw_sql(self):
        if connection.vendor=='sqlite':
            with self.assertRaises(IntegrityError),transaction.atomic(),connection.cursor() as cursor:
                cursor.execute('UPDATE store_item SET price = %s WHERE id = %s',[1000.5,self.item.pk])
        else:
            # PostgreSQL NUMERIC(15,0) normalizes the input before CHECK evaluation.
            with connection.cursor() as cursor:
                cursor.execute('UPDATE store_item SET price = %s WHERE id = %s',[1000.5,self.item.pk])
            self.item.refresh_from_db()
            self.assertEqual(self.item.price,Decimal(1001))
