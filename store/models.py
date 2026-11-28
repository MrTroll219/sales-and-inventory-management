from django.db.models.functions import Round
from store.money import VNDField, to_vnd, MAX_MONEY
"""
Module: models.py

Contains Django models for handling categories, items, and deliveries.

This module defines the following classes:
- Category: Represents a category for items.
- Item: Represents an item in the inventory.
- Delivery: Represents a delivery of an item to a customer.

Each class provides specific fields and methods for handling related data.
"""

from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.urls import reverse
from django.forms import model_to_dict
from django_extensions.db.fields import AutoSlugField
from phonenumber_field.modelfields import PhoneNumberField
from accounts.models import Vendor


class Category(models.Model):
    """
    Represents a category for items.
    """
    name = models.CharField(max_length=50)
    slug = AutoSlugField(unique=True, populate_from='name')

    def __str__(self):
        """
        String representation of the category.
        """
        return f"Category: {self.name}"

    class Meta:
        verbose_name_plural = 'Categories'


class ItemQuerySet(models.QuerySet):
    def needs_restock(self):
        return self.filter(min_stock_level__gt=0, quantity__lte=models.F('min_stock_level'))

    def restock_list(self):
        return self.needs_restock().select_related('category', 'vendor').annotate(
            shortage=models.F('min_stock_level') - models.F('quantity')
        ).order_by('-shortage', 'name', 'pk')


class Item(models.Model):
    """
    Represents an item in the inventory.
    """
    slug = AutoSlugField(unique=True, populate_from='name')
    name = models.CharField(max_length=50)
    description = models.TextField(max_length=256)
    category = models.ForeignKey(Category, on_delete=models.CASCADE)
    quantity = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    min_stock_level = models.PositiveIntegerField(default=0, verbose_name='Tồn tối thiểu',
        validators=[MinValueValidator(0), MaxValueValidator(2147483647)])
    price = VNDField(max_digits=15, decimal_places=0, default=0, validators=[MinValueValidator(0)])
    expiring_date = models.DateTimeField(null=True, blank=True)
    vendor = models.ForeignKey(Vendor, on_delete=models.SET_NULL, null=True)
    objects = ItemQuerySet.as_manager()

    @property
    def needs_restock(self):
        return self.min_stock_level > 0 and self.quantity <= self.min_stock_level

    @property
    def stock_shortage(self):
        return max(self.min_stock_level - self.quantity, 0)

    @property
    def suggested_order_qty(self):
        return max(self.min_stock_level * 2 - self.quantity, 0)

    def __str__(self):
        """
        String representation of the item.
        """
        return (
            f"{self.name} - Category: {self.category}, "
            f"Quantity: {self.quantity}"
        )

    def get_absolute_url(self):
        """
        Returns the absolute URL for an item detail view.
        """
        return reverse('item-detail', kwargs={'slug': self.slug})

    def to_json(self):
        product = model_to_dict(self)
        product['id'] = self.id
        product['text'] = self.name
        product['category'] = self.category.name
        product['quantity'] = 1
        product['total_product'] = 0
        return product

    class Meta:
        ordering = ['name']
        verbose_name_plural = 'Items'
        constraints = [
            models.CheckConstraint(condition=models.Q(price__gte=0), name='item_price_nonnegative'),
            models.CheckConstraint(condition=models.Q(quantity__gte=0), name='item_quantity_nonnegative'),
            models.CheckConstraint(condition=models.Q(price=Round(models.F('price'), 0), price__lte=MAX_MONEY), name='item_price_vnd_int'),
        ]


class Delivery(models.Model):
    """
    Represents a delivery of an item to a customer.
    """
    item = models.ForeignKey(
        Item, blank=True, null=True, on_delete=models.SET_NULL
    )
    customer_name = models.CharField(max_length=30, blank=True, null=True)
    phone_number = PhoneNumberField(blank=True, null=True)
    location = models.CharField(max_length=20, blank=True, null=True)
    date = models.DateTimeField()
    is_delivered = models.BooleanField(
        default=False, verbose_name='Is Delivered'
    )

    def __str__(self):
        """
        String representation of the delivery.
        """
        return (
            f"Delivery of {self.item} to {self.customer_name} "
            f"at {self.location} on {self.date}"
        )
