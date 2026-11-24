"""Desired behavior: these tests intentionally fail on tag v0-goc.

Use an isolated test database. Never seed these cases into a real shop database.
"""

import json
from decimal import Decimal
from io import BytesIO

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from openpyxl import load_workbook

from accounts.models import Customer, Vendor
from store.models import Category, Item
from transactions.models import Purchase, Sale, SaleDetail


class MaintenanceRegressionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(
            username="p0-reviewer", password="p0-test-only-password",
            is_staff=True, is_superuser=True,
        )
        cls.vendor = Vendor.objects.create(name="P0 Vendor")
        cls.customer = Customer.objects.create(
            first_name="P0", last_name="Customer", phone="0900000000",
        )
        cls.category = Category.objects.create(name="P0 Category")
        cls.item = Item.objects.create(
            name="P0 Item", description="Regression fixture",
            category=cls.category, vendor=cls.vendor, quantity=0, price=100,
        )

    def setUp(self):
        self.client.force_login(self.user)

    def create_purchase(self):
        return Purchase.objects.create(
            item=self.item, vendor=self.vendor, quantity=10,
            price=Decimal("100.00"), description="Original",
            delivery_date=None,
        )

    def sale_payload(self, quantity=2):
        return {
            "customer": self.customer.pk,
            "sub_total": 200, "grand_total": 200,
            "tax_percentage": 0, "tax_amount": 0,
            "amount_paid": 200, "amount_change": 0,
            "items": [{
                "id": self.item.pk, "price": 100,
                "quantity": quantity, "total_item": 200,
            }],
        }

    def post_sale(self, payload):
        return self.client.post(
            reverse("sale-create"), data=json.dumps(payload),
            content_type="application/json",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

    def assert_sale_rejected(self, response):
        self.item.refresh_from_db()
        actual = (response.status_code, Sale.objects.count(),
                  SaleDetail.objects.count(), self.item.quantity)
        self.assertEqual(actual, (400, 0, 0, 5),
                         f"Expected HTTP 400 with no writes; got {actual}; "
                         f"response={response.content.decode()}")

    def test_hc01_tao_phieu_nhap_chi_cong_mot_lan(self):
        self.create_purchase()
        self.item.refresh_from_db()
        self.assertEqual(self.item.quantity, 10)

    def test_hc01_sua_mo_ta_khong_doi_ton(self):
        purchase = self.create_purchase()
        purchase.description = "Description edited"
        purchase.save()
        self.item.refresh_from_db()
        self.assertEqual(self.item.quantity, 10)

    def test_hc01_sua_qua_form_tang_so_luong(self):
        purchase = self.create_purchase()
        response = self.client.post(
            reverse("purchase-update", kwargs={"pk": purchase.pk}),
            {"item": self.item.pk, "vendor": self.vendor.pk,
             "quantity": 15, "price": "100.00", "description": "Edited",
             "delivery_date": "", "delivery_status": "P"},
        )
        self.assertEqual(response.status_code, 302,
                         "Valid update must redirect, not fail form validation")
        purchase.refresh_from_db()
        self.assertEqual(purchase.quantity, 15)
        self.item.refresh_from_db()
        self.assertEqual(self.item.quantity, 15)

    def test_hc02_xuat_excel_khi_khong_co_ngay_giao(self):
        self.create_purchase()
        response = self.client.get(reverse("purchases-export"))
        self.assertEqual(response.status_code, 200)
        workbook = load_workbook(BytesIO(response.content))
        try:
            self.assertEqual(workbook.active.max_row, 2)
            self.assertIsNone(workbook.active.cell(row=2, column=6).value)
        finally:
            workbook.close()

    def test_hc03_tu_choi_tong_tien_gia(self):
        Item.objects.filter(pk=self.item.pk).update(quantity=5)
        payload = self.sale_payload()
        payload.update(sub_total=1, grand_total=1)
        payload["items"][0].update(price=0.01, total_item=1)
        self.assert_sale_rejected(self.post_sale(payload))

    def test_hc03_yeu_cau_dang_nhap(self):
        Item.objects.filter(pk=self.item.pk).update(quantity=5)
        self.client.logout()
        response = self.post_sale(self.sale_payload())
        self.item.refresh_from_db()
        actual = (response.status_code, Sale.objects.count(),
                  SaleDetail.objects.count(), self.item.quantity)
        self.assertTrue(
            response.status_code in (301, 302, 401, 403)
            and actual[1:] == (0, 0, 5),
            f"Anonymous sale must be blocked with no writes; got {actual}",
        )

    def test_hc03_so_luong_am(self):
        Item.objects.filter(pk=self.item.pk).update(quantity=5)
        self.assert_sale_rejected(self.post_sale(self.sale_payload(quantity=-3)))
