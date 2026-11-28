from django.db.models.functions import Round
from store.money import VNDField, to_vnd, MAX_MONEY
from django.db import models
from django.core.validators import MinValueValidator
from django.core.exceptions import ValidationError
from decimal import Decimal
from django_extensions.db.fields import AutoSlugField

from store.models import Item


class Invoice(models.Model):
    """
    Represents an invoice for a purchased item.

    Attributes:
        slug (str): Unique slug based on the date.
        date (datetime): Date of invoice creation.
        customer_name (str): Name of the customer.
        contact_number (str): Customer's contact number.
        item (ForeignKey): The invoiced item.
        price_per_item (Decimal): Price per item.
        quantity (int): Number of whole units purchased.
        shipping (Decimal): Shipping charges.
        total (Decimal): Total before shipping.
        grand_total (Decimal): Total including shipping.
    """

    slug = AutoSlugField(unique=True, populate_from='date')
    date = models.DateTimeField(
        auto_now=True,
        verbose_name='Date (e.g., 2022/11/22)'
    )
    customer_name = models.CharField(max_length=30)
    contact_number = models.CharField(max_length=13)
    item = models.ForeignKey(Item, on_delete=models.CASCADE)
    price_per_item = VNDField(max_digits=15, decimal_places=0, validators=[MinValueValidator(0)], verbose_name='Price Per Item (VND)')
    quantity = models.PositiveIntegerField(default=0, validators=[MinValueValidator(0)])
    shipping = VNDField(max_digits=15, decimal_places=0, validators=[MinValueValidator(0)], verbose_name='Shipping and Handling')
    total = VNDField(
        max_digits=15, decimal_places=0, validators=[MinValueValidator(0)],
        verbose_name='Total Amount (VND)', editable=False
    )
    grand_total = VNDField(
        max_digits=15, decimal_places=0, validators=[MinValueValidator(0)],
        verbose_name='Grand Total (VND)', editable=False
    )

    def save(self, *args, **kwargs):
        """
        Update total and grand_total before saving.
        """
        quantity = Decimal(str(self.quantity))
        if not quantity.is_finite() or quantity < 0 or quantity > 2147483647 or quantity != quantity.to_integral_value():
            raise ValidationError({'quantity': 'Quantity must be a nonnegative whole integer; no automatic rounding.'})
        self.quantity = int(quantity)
        self.price_per_item = to_vnd(self.price_per_item)
        self.shipping = to_vnd(self.shipping)
        self.total = to_vnd(self.quantity * self.price_per_item)
        self.grand_total = to_vnd(self.total + self.shipping)
        if kwargs.get('update_fields') is not None:
            changed = set(kwargs['update_fields'])
            if changed & {'quantity', 'price_per_item', 'shipping'}:
                kwargs['update_fields'] = changed | {'total', 'grand_total'}
        return super().save(*args, **kwargs)

    def __str__(self):
        """
        Return the invoice's slug.
        """
        return self.slug

    class Meta:
        constraints = [
            models.CheckConstraint(condition=models.Q(price_per_item__gte=0), name='invoice_price_nonnegative'),
            models.CheckConstraint(condition=models.Q(shipping__gte=0), name='invoice_shipping_nonnegative'),
            models.CheckConstraint(condition=models.Q(total__gte=0), name='invoice_total_nonnegative'),
            models.CheckConstraint(condition=models.Q(grand_total__gte=0), name='invoice_grand_nonnegative'),
            models.CheckConstraint(condition=models.Q(quantity__gte=0), name='invoice_quantity_nonnegative'),
            models.CheckConstraint(condition=models.Q(price_per_item=Round(models.F('price_per_item'), 0), price_per_item__lte=MAX_MONEY), name='invoice_price_per_item_vnd_int'),
            models.CheckConstraint(condition=models.Q(shipping=Round(models.F('shipping'), 0), shipping__lte=MAX_MONEY), name='invoice_shipping_vnd_int'),
            models.CheckConstraint(condition=models.Q(total=Round(models.F('total'), 0), total__lte=MAX_MONEY), name='invoice_total_vnd_int'),
            models.CheckConstraint(condition=models.Q(grand_total=Round(models.F('grand_total'), 0), grand_total__lte=MAX_MONEY), name='invoice_grand_total_vnd_int'),
        ]
