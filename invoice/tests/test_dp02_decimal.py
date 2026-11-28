from decimal import Decimal
from django.core.exceptions import ValidationError
from django.forms import modelform_factory
from invoice.models import Invoice
from transactions.tests.dp02_support import ConstraintCase, constraint_test


class InvoiceDecimalTests(ConstraintCase):
    test_price_nonnegative = constraint_test('invoice', {'price_per_item': -1}, 'invoice_price_nonnegative')
    test_shipping_nonnegative = constraint_test('invoice', {'shipping': -1}, 'invoice_shipping_nonnegative')
    test_total_nonnegative = constraint_test('invoice', {'total': -1}, 'invoice_total_nonnegative')
    test_grand_nonnegative = constraint_test('invoice', {'grand_total': -1}, 'invoice_grand_nonnegative')
    test_quantity_nonnegative = constraint_test('invoice', {'quantity': -1}, 'invoice_quantity_nonnegative')

    def test_save_uses_exact_decimal_totals(self):
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.total, Decimal('60'))
        self.assertEqual(self.invoice.grand_total, Decimal('60.00'))
        self.assertIsInstance(self.invoice.quantity, int)

    def test_save_rounds_half_up_and_supports_legacy_float_inputs(self):
        self.invoice.price_per_item = 1.005
        self.invoice.shipping = 0.105
        self.invoice.quantity = 3
        self.invoice.save()
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.price_per_item, Decimal('1'))
        self.assertEqual(self.invoice.total, Decimal('3'))
        self.assertEqual(self.invoice.grand_total, Decimal('3'))

    def test_partial_save_keeps_computed_totals_consistent(self):
        self.invoice.quantity = 4
        self.invoice.save(update_fields=['quantity'])
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.total, Decimal('80'))
        self.assertEqual(self.invoice.grand_total, Decimal('80'))

    def test_fractional_or_negative_quantity_is_not_rounded(self):
        for quantity in (1.5, -1, 'NaN', 'Infinity'):
            with self.subTest(quantity=quantity), self.assertRaises(ValidationError):
                self.invoice.quantity = quantity
                self.invoice.save()

    def test_model_form_reports_money_and_integer_errors(self):
        form = modelform_factory(Invoice, fields=['customer_name', 'contact_number', 'item',
            'price_per_item', 'quantity', 'shipping'])(data={'customer_name': 'Invalid',
            'contact_number': '123', 'item': self.item.pk, 'price_per_item': '-1', 'quantity': '1.5', 'shipping': '-1'})
        self.assertFalse(form.is_valid())
        self.assertTrue({'price_per_item', 'quantity', 'shipping'} <= set(form.errors))
