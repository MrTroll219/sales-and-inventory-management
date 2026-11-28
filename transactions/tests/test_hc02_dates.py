"""HC02: Excel date handling and lossless minute-precision form round trips."""
from transactions.services.purchases import create_purchase, update_purchase
from transactions.tests.purchase_api import purchase_data
from datetime import datetime, timezone as dt_timezone
from decimal import Decimal
from html.parser import HTMLParser
from io import BytesIO

from django import forms
from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from django.utils import timezone
from openpyxl import load_workbook

from accounts.models import Customer, Vendor
from store.models import Category, Item
from transactions.forms import PurchaseForm
from transactions.models import Purchase, Sale
from transactions.utils import to_excel_datetime


class ExcelDateTests(SimpleTestCase):
    def test_none_stays_empty(self):
        self.assertIsNone(to_excel_datetime(None))

    def test_naive_datetime_is_unchanged(self):
        value = datetime(2026, 1, 2, 10, 30)
        self.assertEqual(to_excel_datetime(value), value)

    def test_aware_utc_in_utc(self):
        with timezone.override("UTC"):
            self.assertEqual(to_excel_datetime(datetime(2026, 1, 1, 17, 30,
                                                       tzinfo=dt_timezone.utc)),
                             datetime(2026, 1, 1, 17, 30))

    def test_local_timezone_conversion_crosses_midnight(self):
        with timezone.override("Asia/Ho_Chi_Minh"):
            self.assertEqual(to_excel_datetime(datetime(2026, 1, 1, 17, 30,
                                                       tzinfo=dt_timezone.utc)),
                             datetime(2026, 1, 2, 0, 30))


class DeliveryInputParser(HTMLParser):
    value = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "input" and attrs.get("name") == "delivery_date":
            self.value = attrs.get("value", "")


class ExportAndFormTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(username="hc02", is_superuser=True)
        cls.vendor = Vendor.objects.create(name="HC02 Vendor")
        cls.customer = Customer.objects.create(first_name="HC02", last_name="Customer")
        category = Category.objects.create(name="HC02 Category")
        cls.item = Item.objects.create(name="HC02 Item", category=category, quantity=0, price=100)
        cls.date = datetime(2026, 1, 1, 17, 30, tzinfo=dt_timezone.utc)

    def setUp(self):
        self.client.force_login(self.user)

    def purchase(self, date=None):
        return create_purchase(dict(item=self.item, vendor=self.vendor, quantity=10,
                                       price=Decimal("5.00"), delivery_date=date))

    def workbook(self, name):
        response = self.client.get(reverse(name))
        self.assertEqual(response.status_code, 200)
        self.assertIn("spreadsheetml.sheet", response["Content-Type"])
        workbook = load_workbook(BytesIO(response.content))
        self.addCleanup(workbook.close)
        return workbook.active

    def data(self, delivery_date):
        return {"item": self.item.pk, "vendor": self.vendor.pk, "price": "5.00",
                "quantity": 10, "delivery_date": delivery_date,
                "delivery_status": "P", "description": "Only description changed"}

    def test_purchase_export_mixed_dates_and_cell_formats(self):
        dated = self.purchase(self.date)
        empty = self.purchase()
        Purchase.objects.filter(pk=dated.pk).update(order_date=self.date)
        with timezone.override("Asia/Ho_Chi_Minh"):
            sheet = self.workbook("purchases-export")
        self.assertEqual(sheet.max_row, 3)
        rows = {sheet.cell(row=n, column=1).value: n for n in (2, 3)}
        row = rows[dated.pk]
        for column in (5, 6):
            self.assertEqual(sheet.cell(row, column).value, datetime(2026, 1, 2, 0, 30))
            self.assertEqual(sheet.cell(row, column).number_format, "DD/MM/YYYY HH:MM")
        self.assertIsNone(sheet.cell(rows[empty.pk], 6).value)
        self.assertEqual(sheet.cell(rows[empty.pk], 6).number_format, "DD/MM/YYYY HH:MM")

    def test_sales_export_uses_local_time_and_date_format(self):
        sale = Sale.objects.create(customer=self.customer, sub_total=100, grand_total=100, amount_paid=100)
        Sale.objects.filter(pk=sale.pk).update(date_added=self.date)
        with timezone.override("Asia/Ho_Chi_Minh"):
            sheet = self.workbook("sales-export")
        self.assertEqual(sheet.max_row, 2)
        self.assertEqual(sheet.cell(2, 2).value, datetime(2026, 1, 2, 0, 30))
        self.assertEqual(sheet.cell(2, 2).number_format, "DD/MM/YYYY HH:MM")

    def test_empty_purchase_export_has_headers_only(self):
        sheet = self.workbook("purchases-export")
        self.assertEqual(sheet.max_row, 1)
        self.assertEqual(sheet.cell(1, 6).value, "Ngày giao")

    def test_empty_sales_export_has_headers_only(self):
        self.assertEqual(self.workbook("sales-export").max_row, 1)

    def test_exports_still_require_login(self):
        self.client.logout()
        for name in ("sales-export", "purchases-export"):
            with self.subTest(name=name):
                response = self.client.get(reverse(name))
                self.assertEqual(response.status_code, 302)
                self.assertIn("next=", response.url)

    def test_widget_renders_datetime_local_value(self):
        purchase = self.purchase(self.date)
        with timezone.override("UTC"):
            form = PurchaseForm(instance=purchase)
            self.assertIsInstance(form.fields["delivery_date"].widget, forms.DateTimeInput)
            self.assertIn('type="datetime-local"', str(form["delivery_date"]))
            self.assertIn('value="2026-01-01T17:30"', str(form["delivery_date"]))
            self.assertIn("%Y-%m-%dT%H:%M", form.fields["delivery_date"].input_formats)

    def test_edit_form_round_trip_preserves_delivery_date(self):
        purchase = self.purchase(self.date)
        url = reverse("purchase-update", kwargs={"pk": purchase.pk})
        with timezone.override("Asia/Ho_Chi_Minh"):
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            parser = DeliveryInputParser()
            parser.feed(response.content.decode())
            self.assertEqual(parser.value, "2026-01-02T00:30")
            response = self.client.post(url, self.data(parser.value))
            self.assertEqual(response.status_code, 302)
        purchase.refresh_from_db()
        self.assertEqual(purchase.delivery_date, self.date)
        self.assertEqual(purchase.description, "Only description changed")
        self.item.refresh_from_db()
        self.assertEqual(self.item.quantity, 10)

    def test_blank_delivery_date_remains_optional(self):
        purchase = self.purchase()
        response = self.client.post(reverse("purchase-update", kwargs={"pk": purchase.pk}),
                                    self.data(""))
        self.assertEqual(response.status_code, 302)
        purchase.refresh_from_db()
        self.assertIsNone(purchase.delivery_date)

    def test_description_only_edit_preserves_existing_seconds(self):
        original = self.date.replace(second=42, microsecond=123456)
        purchase = self.purchase(original)
        url = reverse("purchase-update", kwargs={"pk": purchase.pk})
        with timezone.override("Asia/Ho_Chi_Minh"):
            parser = DeliveryInputParser()
            parser.feed(self.client.get(url).content.decode())
            self.assertEqual(parser.value, "2026-01-02T00:30")
            response = self.client.post(url, self.data(parser.value))
        self.assertEqual(response.status_code, 302)
        purchase.refresh_from_db()
        self.assertEqual(purchase.delivery_date, original)

    def test_explicit_date_change_and_clear_are_still_saved(self):
        purchase = self.purchase(self.date.replace(second=42))
        url = reverse("purchase-update", kwargs={"pk": purchase.pk})
        with timezone.override("UTC"):
            response = self.client.post(url, self.data("2026-01-01T18:00"))
        self.assertEqual(response.status_code, 302)
        purchase.refresh_from_db()
        self.assertEqual(purchase.delivery_date,
                         datetime(2026, 1, 1, 18, 0, tzinfo=dt_timezone.utc))
        response = self.client.post(url, self.data(""))
        self.assertEqual(response.status_code, 302)
        purchase.refresh_from_db()
        self.assertIsNone(purchase.delivery_date)

    def test_previous_datetime_input_format_remains_accepted(self):
        form = PurchaseForm(data=self.data("2026-01-01 17:30:00"))
        with timezone.override("UTC"):
            self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["delivery_date"], self.date)
