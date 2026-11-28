from decimal import Decimal
from django.test import TestCase
from store.forms import ItemForm
from store.models import Item, Category
from transactions.tests.dp02_support import ConstraintCase, constraint_test


class ItemConstraintTests(ConstraintCase):
    test_price_nonnegative = constraint_test('item', {'price': -1}, 'item_price_nonnegative')
    test_quantity_nonnegative = constraint_test('item', {'quantity': -1}, 'item_quantity_nonnegative')


class ItemDecimalTests(TestCase):
    def test_decimal_round_trip_and_form_errors(self):
        category = Category.objects.create(name='DP02 form')
        item = Item.objects.create(name='Price', category=category, price=Decimal('0.10') + Decimal('0.20'))
        item.refresh_from_db()
        self.assertEqual(item.price, Decimal('0'))
        self.assertIsInstance(item.price, Decimal)
        form = ItemForm(data={'name': 'Invalid', 'category': category.pk, 'description': 'Test',
                              'quantity': -1, 'price': '-0.01'})
        self.assertFalse(form.is_valid())
        self.assertIn('price', form.errors)
        self.assertIn('quantity', form.errors)
