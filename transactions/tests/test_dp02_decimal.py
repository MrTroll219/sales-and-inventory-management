from decimal import Decimal
from django.test import SimpleTestCase
from transactions.forms import PurchaseForm
from transactions.models import Sale
from transactions.pricing import MAX_MONEY, SaleInputError, compute_sale_totals
from transactions.tests.dp02_support import ConstraintCase, constraint_test


class TransactionConstraintTests(ConstraintCase):
    test_purchase_price_nonnegative = constraint_test('purchase', {'price': -1}, 'purchase_price_nonnegative')
    test_purchase_total_nonnegative = constraint_test('purchase', {'total_value': -1}, 'purchase_total_nonnegative')
    test_purchase_quantity_positive = constraint_test('purchase', {'quantity': 0}, 'purchase_quantity_positive')
    test_sale_subtotal_nonnegative = constraint_test('sale', {'sub_total': -1}, 'sale_subtotal_nonnegative')
    test_sale_grand_nonnegative = constraint_test('sale', {'grand_total': -1}, 'sale_grand_nonnegative')
    test_sale_tax_nonnegative = constraint_test('sale', {'tax_amount': -1}, 'sale_tax_nonnegative')
    test_sale_paid_nonnegative = constraint_test('sale', {'amount_paid': -1}, 'sale_paid_nonnegative')
    test_sale_change_nonnegative = constraint_test('sale', {'amount_change': -1}, 'sale_change_nonnegative')
    test_sale_tax_percentage_lower = constraint_test('sale', {'tax_percentage': -1}, 'sale_tax_percentage_range')
    test_sale_tax_percentage_upper = constraint_test('sale', {'tax_percentage': 101}, 'sale_tax_percentage_range')
    test_sale_grand_matches_parts = constraint_test('sale', {'grand_total': 111, 'amount_change': 9}, 'sale_grand_matches_parts')
    test_sale_change_matches_payment = constraint_test('sale', {'amount_change': 9}, 'sale_change_matches_payment')
    test_detail_price_nonnegative = constraint_test('detail', {'price': -1}, 'sale_detail_price_nonnegative')
    test_detail_total_nonnegative = constraint_test('detail', {'total_detail': -1}, 'sale_detail_total_nonnegative')
    test_detail_quantity_positive = constraint_test('detail', {'quantity': 0}, 'sale_detail_quantity_positive')

    def test_database_accepts_exact_cent_identities(self):
        for subtotal, tax, paid in [('0.10', '0.20', '1.00'), ('59.97', '4.20', '70.00'),
                ('99999999.99', '0', '100000000'), ('9999999999999.99', '0', '9999999999999.99')]:
            with self.subTest(subtotal=subtotal):
                sub, amount, payment = map(Decimal, (subtotal, tax, paid))
                grand = sub + amount
                Sale.objects.filter(pk=self.sale.pk).update(sub_total=sub, tax_amount=amount,
                    grand_total=grand, amount_paid=payment, amount_change=payment-grand)
                self.sale.refresh_from_db()
                self.assertEqual(self.sale.grand_total, grand)
                self.assertEqual(self.sale.amount_change, payment-grand)

    def test_purchase_form_rejects_nonpositive_quantity_and_negative_price(self):
        form = PurchaseForm(data={'item': self.item.pk, 'vendor': self.purchase.vendor_id,
            'price': '-1', 'quantity': 0, 'delivery_status': 'P'})
        self.assertFalse(form.is_valid())
        self.assertTrue({'price', 'quantity'} <= set(form.errors))


class DecimalPricingTests(SimpleTestCase):
    def test_decimal_examples_and_legacy_float_compatibility(self):
        for price in (Decimal('19.99'), 19.99):
            self.assertEqual(compute_sale_totals([{'id': 1, 'price': price, 'quantity': 3}], 0, 60)['grand_total'], Decimal('59.97'))
        result = compute_sale_totals([{'id': 1, 'price': Decimal('0.1'), 'quantity': 1},
            {'id': 2, 'price': Decimal('0.2'), 'quantity': 1}], 0, 1)
        self.assertEqual(result['sub_total'], Decimal('0.30'))

    def test_money_limit_matches_decimal_15_2_and_overflow_is_rejected(self):
        result = compute_sale_totals([{'id': 1, 'price': MAX_MONEY, 'quantity': 1}], 0, MAX_MONEY)
        self.assertEqual(result['grand_total'], MAX_MONEY)
        for price, quantity, tax, paid in [(MAX_MONEY+1, 1, 0, MAX_MONEY),
            (MAX_MONEY, 2, 0, MAX_MONEY), (MAX_MONEY, 1, 1, MAX_MONEY), (1, 1, 0, MAX_MONEY+1)]:
            with self.subTest(price=price, quantity=quantity, tax=tax), self.assertRaises(SaleInputError):
                compute_sale_totals([{'id': 1, 'price': price, 'quantity': quantity}], tax, paid)

    def test_tax_precision_matches_schema(self):
        with self.assertRaises(SaleInputError):
            compute_sale_totals([{'id': 1, 'price': 100, 'quantity': 1}], '1.001', 200)
