"""HC01 stock deltas, database atomicity and user-visible validation."""
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import TestCase
from django.urls import reverse

from accounts.models import Vendor
from store.models import Category, Item
from transactions.models import Purchase


class PurchaseStockTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(username="hc01", is_superuser=True)
        cls.vendor = Vendor.objects.create(name="HC01 vendor")
        cls.category = Category.objects.create(name="HC01 category")
        cls.item = Item.objects.create(name="A", category=cls.category, price=100, quantity=0)
        cls.other = Item.objects.create(name="B", category=cls.category, price=200, quantity=7)

    def purchase(self):
        return Purchase.objects.create(item=self.item, vendor=self.vendor,
                                       quantity=10, price=Decimal("5.00"))

    def quantities(self):
        return tuple(Item.objects.get(pk=pk).quantity for pk in (self.item.pk, self.other.pk))

    def form_data(self, item_id, quantity):
        return {"item": item_id, "vendor": self.vendor.pk, "quantity": quantity,
                "price": "5.00", "description": "Updated", "delivery_date": "",
                "delivery_status": "P"}

    def test_reduce_quantity_changes_stock_by_difference(self):
        purchase = self.purchase()
        purchase.quantity = 4
        purchase.save()
        self.assertEqual(self.quantities(), (4, 7))
        purchase.refresh_from_db()
        self.assertEqual(purchase.total_value, Decimal("20.00"))

    def test_change_item_moves_old_and_new_quantities(self):
        purchase = self.purchase()
        purchase.item = self.other
        purchase.quantity = 6
        purchase.save()
        self.assertEqual(self.quantities(), (0, 13))
        purchase.refresh_from_db()
        self.assertEqual((purchase.item_id, purchase.quantity), (self.other.pk, 6))

    def test_repeated_unchanged_save_does_not_add_stock(self):
        purchase = self.purchase()
        purchase.save()
        purchase.save()
        self.assertEqual(self.quantities(), (10, 7))

    def test_stale_purchase_uses_current_database_quantity(self):
        purchase = self.purchase()
        stale = Purchase.objects.get(pk=purchase.pk)
        purchase.quantity = 15
        purchase.save()
        stale.quantity = 12
        stale.save()
        self.assertEqual(self.quantities(), (12, 7))

    def test_stale_item_cache_does_not_overwrite_other_purchases(self):
        # Reusing the same in-memory Item must not overwrite the persisted balance.
        self.purchase()
        self.purchase()
        self.assertEqual(self.quantities(), (20, 7))

    def test_reduce_below_sold_stock_rolls_back_purchase(self):
        purchase = self.purchase()
        Item.objects.filter(pk=self.item.pk).update(quantity=2)  # 8 already sold
        purchase.quantity = 1
        with self.assertRaisesMessage(ValidationError, "sẽ âm"):
            purchase.save()
        purchase.refresh_from_db()
        self.assertEqual((purchase.quantity, purchase.total_value), (10, Decimal("50.00")))
        self.assertEqual(self.quantities(), (2, 7))

    def test_form_shows_validation_error_without_database_writes(self):
        purchase = self.purchase()
        Item.objects.filter(pk=self.item.pk).update(quantity=2)
        self.client.force_login(self.user)
        response = self.client.post(reverse("purchase-update", kwargs={"pk": purchase.pk}),
                                    self.form_data(self.item.pk, 1))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "sẽ âm")
        self.assertTrue(response.context["form"].non_field_errors())
        purchase.refresh_from_db()
        self.assertEqual((purchase.quantity, purchase.description), (10, None))
        self.assertEqual(self.quantities(), (2, 7))

    def test_change_item_with_consumed_stock_rolls_back_both_items(self):
        # Move from the higher PK to lower PK: the target is credited first.
        # Failure to debit the source must roll back that credit too.
        purchase = Purchase.objects.create(item=self.other, vendor=self.vendor,
                                           quantity=10, price=Decimal("5.00"))
        Item.objects.filter(pk=self.other.pk).update(quantity=3)
        purchase.item = self.item
        purchase.quantity = 4
        with self.assertRaises(ValidationError):
            purchase.save()
        purchase.refresh_from_db()
        self.assertEqual(purchase.item_id, self.other.pk)
        self.assertEqual(purchase.quantity, 10)
        self.assertEqual(self.quantities(), (0, 3))

    def test_purchase_insert_failure_rolls_back_stock(self):
        # Exercise failure AFTER the F() stock update, not just validation first.
        with patch("django.db.models.Model.save", side_effect=IntegrityError("save failed")):
            with self.assertRaises(IntegrityError):
                self.purchase()
        self.assertEqual(Purchase.objects.count(), 0)
        self.assertEqual(self.quantities(), (0, 7))

    def test_partial_description_save_ignores_unsaved_stock_fields(self):
        purchase = self.purchase()
        purchase.item = self.other
        purchase.quantity = 99
        purchase.description = "Description only"
        purchase.save(update_fields=["description"])
        purchase.refresh_from_db()
        self.assertEqual((purchase.item_id, purchase.quantity), (self.item.pk, 10))
        self.assertEqual(purchase.total_value, Decimal("50.00"))
        self.assertEqual(self.quantities(), (10, 7))

    def test_partial_quantity_save_updates_total_value(self):
        purchase = self.purchase()
        purchase.quantity = 4
        purchase.save(update_fields=["quantity"])
        purchase.refresh_from_db()
        self.assertEqual(purchase.total_value, Decimal("20.00"))
        self.assertEqual(self.quantities(), (4, 7))

    def test_price_only_change_does_not_change_stock(self):
        purchase = self.purchase()
        purchase.price = Decimal("7.00")
        purchase.save(update_fields=["price"])
        purchase.refresh_from_db()
        self.assertEqual(purchase.total_value, Decimal("70.00"))
        self.assertEqual(self.quantities(), (10, 7))

    def test_empty_update_fields_does_not_save_or_change_stock(self):
        purchase = self.purchase()
        purchase.quantity = 20
        purchase.save(update_fields=[])
        purchase.refresh_from_db()
        self.assertEqual(purchase.quantity, 10)
        self.assertEqual(self.quantities(), (10, 7))

    def test_delivery_status_does_not_change_stock_policy(self):
        purchase = self.purchase()
        self.assertEqual(self.quantities(), (10, 7))  # Pending still counts.
        purchase.delivery_status = "S"
        purchase.save()
        self.assertEqual(self.quantities(), (10, 7))
