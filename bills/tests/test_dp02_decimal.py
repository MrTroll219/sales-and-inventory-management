from decimal import Decimal
from django.forms import modelform_factory
from bills.models import Bill
from transactions.tests.dp02_support import ConstraintCase, constraint_test


class BillDecimalTests(ConstraintCase):
    test_amount_nonnegative = constraint_test('bill', {'amount': -1}, 'bill_amount_nonnegative')

    def test_amount_round_trip_and_form_error(self):
        self.bill.amount = Decimal('0.10') + Decimal('0.20')
        self.bill.save()
        self.bill.refresh_from_db()
        self.assertEqual(self.bill.amount, Decimal('0'))
        form = modelform_factory(Bill, fields=['institution_name', 'payment_details', 'amount'])(
            data={'institution_name': 'Invalid', 'payment_details': 'Cash', 'amount': '-0.01'})
        self.assertFalse(form.is_valid())
        self.assertIn('amount', form.errors)
