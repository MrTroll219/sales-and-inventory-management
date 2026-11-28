"""Shared valid fixtures and DB-level assertions for DP02 constraints."""
from transactions.services.purchases import create_purchase, update_purchase
from transactions.tests.purchase_api import purchase_data
from decimal import Decimal
from django.db import IntegrityError, connection, transaction
from django.test import TestCase
from accounts.models import Customer, Vendor
from store.models import Category, Item
from transactions.models import Sale, SaleDetail, Purchase
from invoice.models import Invoice
from bills.models import Bill


class ConstraintCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        category = Category.objects.create(name='DP02')
        cls.item = Item.objects.create(name='Decimal', category=category, quantity=20, price=Decimal('19.99'))
        vendor = Vendor.objects.create(name='DP02 vendor')
        customer = Customer.objects.create(first_name='DP02')
        cls.sale = Sale.objects.create(customer=customer, sub_total=100, tax_amount=10,
            tax_percentage=10, grand_total=110, amount_paid=120, amount_change=10)
        cls.detail = SaleDetail.objects.create(sale=cls.sale, item=cls.item, price=100, quantity=1, total_detail=100)
        cls.purchase = create_purchase(dict(item=cls.item, vendor=vendor, price=Decimal('5'), quantity=2))
        cls.invoice = Invoice.objects.create(customer_name='DP02', contact_number='123', item=cls.item,
            price_per_item=Decimal('19.99'), quantity=3, shipping=Decimal('0.03'))
        cls.bill = Bill.objects.create(institution_name='DP02', payment_details='Cash', amount=Decimal('10'))

    def assert_blocked(self, obj, changes, constraint_name):
        with connection.cursor() as cursor:
            constraints = connection.introspection.get_constraints(cursor, obj._meta.db_table)
        self.assertTrue(constraints[constraint_name]['check'])
        with self.assertRaises(IntegrityError), transaction.atomic():
            type(obj).objects.filter(pk=obj.pk).update(**changes)


def constraint_test(attribute, changes, constraint_name):
    def test(self):
        self.assert_blocked(getattr(self, attribute), changes, constraint_name)
    test.__doc__ = f'Database rejects {changes} with {constraint_name} installed.'
    return test
