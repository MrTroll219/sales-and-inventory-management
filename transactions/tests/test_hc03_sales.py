"""HC03: trusted pricing, validation, authentication and atomic stock writes."""
from decimal import Decimal
import json
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, RequestFactory, SimpleTestCase, TestCase
from django.urls import reverse

from accounts.models import Customer
from store.models import Category, Item
from transactions.models import Sale, SaleDetail
from transactions.pricing import SaleInputError, compute_sale_totals
from transactions.views import SaleCreateView


class PricingTests(SimpleTestCase):
    def test_pricing_examples(self):
        cases = [
            ([{"id": 1, "price": 100.0, "quantity": 2}], 0, 200, "200.00", "0.00", "200.00", "0.00"),
            ([{"id": 1, "price": 100.0, "quantity": 2}], 10, 250, "200.00", "20.00", "220.00", "30.00"),
            ([{"id": 1, "price": 19.99, "quantity": 3}], 0, 60, "60", "0", "60", "0"),
            ([{"id": 1, "price": 0.1, "quantity": 1}, {"id": 2, "price": 0.2, "quantity": 1}],
             0, 1, "0", "0", "0", "1"),
            ([{"id": 1, "price": 0.05, "quantity": 1}], 10, 1, "0", "0", "0", "1"),
        ]
        for lines, tax, paid, sub, tax_amount, grand, change in cases:
            with self.subTest(lines=lines, tax=tax):
                result = compute_sale_totals(lines, tax, paid)
                self.assertEqual(tuple(result[k] for k in ("sub_total", "tax_amount", "grand_total", "amount_change")),
                                 tuple(Decimal(v) for v in (sub, tax_amount, grand, change)))

    def test_duplicate_lines_are_grouped(self):
        result = compute_sale_totals([{"id": 1, "price": 100, "quantity": 2},
                                      {"id": 1, "price": 100, "quantity": 1}], 0, 300)
        self.assertEqual(len(result["lines"]), 1)
        self.assertEqual(result["lines"][0]["quantity"], 3)

    def test_unit_price_rounds_half_up_to_existing_cent_precision(self):
        result = compute_sale_totals([{"id": 1, "price": 1.005, "quantity": 2}], 0, 3)
        self.assertEqual(result["lines"][0]["price"], Decimal("1"))
        self.assertEqual(result["grand_total"], Decimal("2"))

    def test_invalid_pricing_values_are_rejected(self):
        for price, quantity, tax, paid in [
            (100, 0, 0, 200), (100, -1, 0, 200), (100, 1.5, 0, 200),
            (100, True, 0, 200), (100, 1, 150, 200), (100, 1, -1, 200),
            (100, 1, "NaN", 200), (100, 1, 0, "Infinity"),
            (100, 1, 0, 99), (-1, 1, 0, 200), ("bad", 1, 0, 200),
            (100, 1, 0, "1e100"),
        ]:
            with self.subTest(price=price, quantity=quantity, tax=tax, paid=paid):
                with self.assertRaises(SaleInputError):
                    compute_sale_totals([{"id": 1, "price": price, "quantity": quantity}], tax, paid)

    def test_empty_and_malformed_lines_are_rejected(self):
        for lines in (None, [], {}, [None], [{"id": 1}]):
            with self.subTest(lines=lines), self.assertRaises(SaleInputError):
                compute_sale_totals(lines, 0, 100)


class SaleCreationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(username="hc03")
        cls.customer = Customer.objects.create(first_name="Khach", last_name="Demo")
        category = Category.objects.create(name="HC03")
        cls.item = Item.objects.create(name="Water", category=category, price=100.0, quantity=5)
        cls.other = Item.objects.create(name="Tea", category=category, price=50.0, quantity=3)

    def setUp(self):
        self.client.force_login(self.user)

    def payload(self):
        return {"customer": self.customer.pk, "amount_paid": 200,
                "items": [{"id": self.item.pk, "quantity": 2}]}

    def post(self, data):
        return self.client.post(reverse("sale-create"), data=json.dumps(data),
                                content_type="application/json", HTTP_X_REQUESTED_WITH="XMLHttpRequest")

    def snapshot(self):
        return (Sale.objects.count(), SaleDetail.objects.count(),
                list(Item.objects.order_by("pk").values_list("quantity", flat=True)))

    def rejected(self, data):
        before = self.snapshot()
        response = self.post(data)
        self.assertEqual(response.status_code, 400, response.content)
        self.assertEqual(response.json()["status"], "error")
        self.assertEqual(self.snapshot(), before)
        return response

    def test_valid_sale_uses_database_price_ignoring_client_price(self):
        data = self.payload()
        data["items"][0]["price"] = 0.01
        response = self.post(data)
        self.assertEqual(response.status_code, 200, response.content)
        sale, detail = Sale.objects.get(), SaleDetail.objects.get()
        self.assertEqual((sale.sub_total, sale.grand_total, sale.amount_change),
                         (Decimal("200.00"), Decimal("200.00"), Decimal("0.00")))
        self.assertEqual((detail.price, detail.quantity, detail.total_detail),
                         (Decimal("100.00"), 2, Decimal("200.00")))
        self.assertEqual(self.snapshot(), (1, 1, [3, 3]))

    def test_additive_tax_and_change_are_calculated_by_server(self):
        data = self.payload()
        data.update(tax_percentage=10, amount_paid=250, tax_amount=999, amount_change=999)
        response = self.post(data)
        self.assertEqual(response.status_code, 200, response.content)
        sale = Sale.objects.get()
        self.assertEqual((sale.tax_amount, sale.grand_total, sale.amount_change),
                         (Decimal("20.00"), Decimal("220.00"), Decimal("30.00")))

    def test_underpayment_is_rejected(self):
        data = self.payload(); data["amount_paid"] = 199
        self.rejected(data)

    def test_duplicate_lines_over_stock_are_rejected_as_a_group(self):
        data = self.payload()
        data.update(amount_paid=600, items=[{"id": self.item.pk, "quantity": 3},
                                          {"id": self.item.pk, "quantity": 3}])
        self.rejected(data)

    def test_duplicate_valid_lines_create_one_detail(self):
        data = self.payload()
        data.update(amount_paid=300, items=[{"id": self.item.pk, "quantity": 2},
                                          {"id": self.item.pk, "quantity": 1}])
        self.assertEqual(self.post(data).status_code, 200)
        self.assertEqual(SaleDetail.objects.count(), 1)
        self.assertEqual(SaleDetail.objects.get().quantity, 3)
        self.assertEqual(self.snapshot(), (1, 1, [2, 3]))

    def test_invalid_tax_values_are_rejected(self):
        for tax in (150, -1, None, True, "NaN", "Infinity", {}, "bad"):
            with self.subTest(tax=tax):
                data = self.payload(); data["tax_percentage"] = tax
                self.rejected(data)

    def test_invalid_quantity_values_are_rejected(self):
        for quantity in (-3, 0, 1.5, True, None, "NaN", "1e100", "bad"):
            with self.subTest(quantity=quantity):
                data = self.payload(); data["items"][0]["quantity"] = quantity
                self.rejected(data)

    def test_invalid_paid_values_are_rejected(self):
        for paid in (None, True, -1, "NaN", "Infinity", "1e100", {}, "bad"):
            with self.subTest(paid=paid):
                data = self.payload(); data["amount_paid"] = paid
                self.rejected(data)

    def test_invalid_customer_or_item_ids_are_rejected(self):
        for key in ("customer", "id"):
            for value in (None, -1, True, "bad", "1e100", 999999):
                with self.subTest(key=key, value=value):
                    data = self.payload()
                    if key == "customer": data[key] = value
                    else: data["items"][0][key] = value
                    self.rejected(data)

    def test_missing_or_invalid_json_shapes_are_rejected(self):
        for data in (None, [], "hello", 42, {}, {"customer": self.customer.pk, "items": []},
                     {"customer": self.customer.pk, "items": [None]},
                     {"customer": self.customer.pk, "items": [{}]}):
            with self.subTest(data=data): self.rejected(data)
        for raw in (b"{broken", b"", b"\xff"):
            with self.subTest(raw=raw):
                before = self.snapshot()
                response = self.client.post(reverse("sale-create"), data=raw,
                                            content_type="application/json",
                                            HTTP_X_REQUESTED_WITH="XMLHttpRequest")
                self.assertEqual(response.status_code, 400)
                self.assertEqual(self.snapshot(), before)

    def test_client_total_mismatches_report_expected_value(self):
        for field in ("sub_total", "grand_total", "total_item"):
            with self.subTest(field=field):
                data = self.payload()
                target = data["items"][0] if field == "total_item" else data
                target[field] = 1
                response = self.rejected(data)
                self.assertIn("200 ₫", response.json()["message"])

    def test_one_cent_tolerance_still_stores_server_totals(self):
        data = self.payload()
        data.update(sub_total="199.99", grand_total="200.01")
        data["items"][0]["total_item"] = "200.01"
        self.assertEqual(self.post(data).status_code, 400)
        self.assertEqual(Sale.objects.count(), 0)

    def test_multiple_items_decrement_correct_stock(self):
        data = self.payload()
        data.update(amount_paid=250, items=[{"id": self.item.pk, "quantity": 2},
                                          {"id": self.other.pk, "quantity": 1}])
        self.assertEqual(self.post(data).status_code, 200)
        self.assertEqual(self.snapshot(), (1, 2, [3, 2]))

    def test_database_failure_after_stock_write_rolls_back_all(self):
        request = RequestFactory().post(reverse("sale-create"), data=json.dumps(self.payload()),
                                        content_type="application/json",
                                        HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        request.user = self.user
        before = self.snapshot()
        with patch.object(SaleDetail.objects, "create", side_effect=RuntimeError("storage failed")):
            with self.assertRaises(RuntimeError): SaleCreateView(request)
        self.assertEqual(self.snapshot(), before)

    def test_ajax_anonymous_is_json_401_with_no_writes(self):
        self.client.logout()
        before = self.snapshot()
        response = self.post(self.payload())
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["status"], "error")
        self.assertEqual(self.snapshot(), before)

    def test_regular_anonymous_requests_redirect_to_login(self):
        self.client.logout()
        for method in ("get", "post"):
            with self.subTest(method=method):
                response = getattr(self.client, method)(reverse("sale-create"))
                self.assertEqual(response.status_code, 302)
                self.assertIn("login", response.url)
        self.assertEqual(self.snapshot(), (0, 0, [5, 3]))

    def test_anonymous_ajax_with_real_csrf_token_is_401(self):
        client = Client(enforce_csrf_checks=True)
        client.get("/accounts/login/")
        before = self.snapshot()
        response = client.post(reverse("sale-create"), data=json.dumps(self.payload()),
                               content_type="application/json", HTTP_X_REQUESTED_WITH="XMLHttpRequest",
                               HTTP_X_CSRFTOKEN=client.cookies["csrftoken"].value)
        self.assertEqual(response.status_code, 401)
        self.assertEqual(self.snapshot(), before)

    def test_page_renders_customer_without_last_name_and_tax_label(self):
        for last_name in (None, ""):
            with self.subTest(last_name=last_name):
                self.customer.last_name = last_name
                self.customer.save()
                self.assertEqual(self.customer.get_full_name(), "Khach")
                self.assertEqual(str(self.customer), "Khach")
                response = self.client.get(reverse("sale-create"))
                self.assertContains(response, "Khach")
                self.assertContains(response, "Thuế (%)")
                self.assertNotContains(response, "Tax Inclusive")

    def test_unsupported_method_is_405(self):
        self.assertEqual(self.client.put(reverse("sale-create")).status_code, 405)
        self.assertEqual(self.snapshot(), (0, 0, [5, 3]))
