from store.money import VNDField, to_vnd, MAX_MONEY
from django.db import models
from django.conf import settings
from django.db.models import F
from django.db.models.functions import Round
from django.core.validators import MinValueValidator, MaxValueValidator
from django_extensions.db.fields import AutoSlugField

from store.models import Item
from accounts.models import Vendor, Customer

DELIVERY_CHOICES = [("P", "Pending"), ("S", "Successful")]


class Sale(models.Model):
    """
    Represents a sale transaction involving a customer.
    """

    date_added = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Sale Date"
    )
    customer = models.ForeignKey(
        Customer,
        on_delete=models.DO_NOTHING,
        db_column="customer"
    )
    sub_total = VNDField(
        max_digits=15, validators=[MinValueValidator(0)],
        decimal_places=0,
        default=0
    )
    grand_total = VNDField(
        max_digits=15, validators=[MinValueValidator(0)],
        decimal_places=0,
        default=0
    )
    tax_amount = VNDField(
        max_digits=15, validators=[MinValueValidator(0)],
        decimal_places=0,
        default=0
    )
    tax_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)])
    amount_paid = VNDField(
        max_digits=15, validators=[MinValueValidator(0)],
        decimal_places=0,
        default=0
    )
    amount_change = VNDField(
        max_digits=15, validators=[MinValueValidator(0)],
        decimal_places=0,
        default=0
    )

    class Meta:
        db_table = "sales"
        verbose_name = "Sale"
        verbose_name_plural = "Sales"
        constraints = [
            models.CheckConstraint(condition=models.Q(sub_total__gte=0), name='sale_subtotal_nonnegative'),
            models.CheckConstraint(condition=models.Q(grand_total__gte=0), name='sale_grand_nonnegative'),
            models.CheckConstraint(condition=models.Q(tax_amount__gte=0), name='sale_tax_nonnegative'),
            models.CheckConstraint(condition=models.Q(amount_paid__gte=0), name='sale_paid_nonnegative'),
            models.CheckConstraint(condition=models.Q(amount_change__gte=0), name='sale_change_nonnegative'),
            models.CheckConstraint(condition=models.Q(tax_percentage__gte=0, tax_percentage__lte=100), name='sale_tax_percentage_range'),
            # TU03: all money is integral; keep the two F identities at whole-dong scale.
            models.CheckConstraint(condition=models.Q(grand_total=Round(F('sub_total') + F('tax_amount'), 0)), name='sale_grand_matches_parts'),
            models.CheckConstraint(condition=models.Q(amount_change=Round(F('amount_paid') - F('grand_total'), 0)), name='sale_change_matches_payment'),
            models.CheckConstraint(condition=models.Q(sub_total=Round(models.F('sub_total'), 0), sub_total__lte=MAX_MONEY), name='sale_sub_total_vnd_int'),
            models.CheckConstraint(condition=models.Q(tax_amount=Round(models.F('tax_amount'), 0), tax_amount__lte=MAX_MONEY), name='sale_tax_amount_vnd_int'),
            models.CheckConstraint(condition=models.Q(grand_total=Round(models.F('grand_total'), 0), grand_total__lte=MAX_MONEY), name='sale_grand_total_vnd_int'),
            models.CheckConstraint(condition=models.Q(amount_paid=Round(models.F('amount_paid'), 0), amount_paid__lte=MAX_MONEY), name='sale_amount_paid_vnd_int'),
            models.CheckConstraint(condition=models.Q(amount_change=Round(models.F('amount_change'), 0), amount_change__lte=MAX_MONEY), name='sale_amount_change_vnd_int'),
        ]

    def __str__(self):
        """
        Returns a string representation of the Sale instance.
        """
        return (
            f"Sale ID: {self.id} | "
            f"Grand Total: {self.grand_total} | "
            f"Date: {self.date_added}"
        )

    def sum_products(self):
        """
        Returns the total quantity of products in the sale.
        """
        return sum(detail.quantity for detail in self.saledetail_set.all())


class SaleDetail(models.Model):
    """
    Represents details of a specific sale, including item and quantity.
    """

    sale = models.ForeignKey(
        Sale,
        on_delete=models.CASCADE,
        db_column="sale",
        related_name="saledetail_set"
    )
    item = models.ForeignKey(
        Item,
        on_delete=models.DO_NOTHING,
        db_column="item"
    )
    price = VNDField(
        max_digits=15, validators=[MinValueValidator(0)],
        decimal_places=0
    )
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    total_detail = VNDField(max_digits=15, validators=[MinValueValidator(0)], decimal_places=0)

    class Meta:
        db_table = "sale_details"
        verbose_name = "Sale Detail"
        verbose_name_plural = "Sale Details"
        constraints = [
            models.CheckConstraint(condition=models.Q(price__gte=0), name='sale_detail_price_nonnegative'),
            models.CheckConstraint(condition=models.Q(total_detail__gte=0), name='sale_detail_total_nonnegative'),
            models.CheckConstraint(condition=models.Q(quantity__gt=0), name='sale_detail_quantity_positive'),
            models.CheckConstraint(condition=models.Q(price=Round(models.F('price'), 0), price__lte=MAX_MONEY), name='saledetail_price_vnd_int'),
            models.CheckConstraint(condition=models.Q(total_detail=Round(models.F('total_detail'), 0), total_detail__lte=MAX_MONEY), name='saledetail_total_detail_vnd_int'),
        ]

    def __str__(self):
        """
        Returns a string representation of the SaleDetail instance.
        """
        return (
            f"Detail ID: {self.id} | "
            f"Sale ID: {self.sale.id} | "
            f"Quantity: {self.quantity}"
        )


class Purchase(models.Model):
    """
    Represents a purchase of an item,
    including vendor details and delivery status.
    """

    slug = AutoSlugField(unique=True, populate_from="vendor")
    item = models.ForeignKey(Item, on_delete=models.CASCADE)
    description = models.TextField(max_length=300, blank=True, null=True)
    vendor = models.ForeignKey(
        Vendor, related_name="purchases", on_delete=models.CASCADE
    )
    order_date = models.DateTimeField(auto_now_add=True)
    delivery_date = models.DateTimeField(
        blank=True, null=True, verbose_name="Delivery Date"
    )
    quantity = models.PositiveIntegerField(default=0, validators=[MinValueValidator(1)])
    delivery_status = models.CharField(
        choices=DELIVERY_CHOICES,
        max_length=1,
        default="P",
        verbose_name="Delivery Status",
    )
    price = VNDField(
        max_digits=15, validators=[MinValueValidator(0)],
        decimal_places=0,
        default=0,
        verbose_name="Price per item (VND)",
    )
    total_value = VNDField(max_digits=15, validators=[MinValueValidator(0)], decimal_places=0)

    def save(self, *args, **kwargs):
        """DP01: compute value only; inventory is owned by services."""
        self.price = to_vnd(self.price)
        self.total_value = to_vnd(self.price * self.quantity)
        if kwargs.get('update_fields') is not None:
            changed = set(kwargs['update_fields'])
            if changed & {'quantity', 'price'}:
                kwargs['update_fields'] = changed | {'total_value'}
        return super().save(*args, **kwargs)

    def __str__(self):
        """
        Returns a string representation of the Purchase instance.
        """
        return str(self.item.name)

    class Meta:
        ordering = ["order_date"]
        constraints = [
            models.CheckConstraint(condition=models.Q(price__gte=0), name='purchase_price_nonnegative'),
            models.CheckConstraint(condition=models.Q(total_value__gte=0), name='purchase_total_nonnegative'),
            models.CheckConstraint(condition=models.Q(quantity__gt=0), name='purchase_quantity_positive'),
            models.CheckConstraint(condition=models.Q(price=Round(models.F('price'), 0), price__lte=MAX_MONEY), name='purchase_price_vnd_int'),
            models.CheckConstraint(condition=models.Q(total_value=Round(models.F('total_value'), 0), total_value__lte=MAX_MONEY), name='purchase_total_value_vnd_int'),
        ]


class StockMovement(models.Model):
    class Reason(models.TextChoices):
        PURCHASE_IN = 'PURCHASE_IN', 'Purchase in'
        PURCHASE_EDIT = 'PURCHASE_EDIT', 'Purchase edit'
        PURCHASE_DELETE = 'PURCHASE_DELETE', 'Purchase delete'
        SALE_OUT = 'SALE_OUT', 'Sale out'
        SALE_CANCEL = 'SALE_CANCEL', 'Sale cancel'
        ADJUST = 'ADJUST', 'Adjustment'

    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name='stock_movements')
    delta = models.IntegerField()
    quantity_after = models.PositiveIntegerField()
    reason = models.CharField(max_length=20, choices=Reason.choices)
    ref_type = models.CharField(max_length=50, blank=True)
    ref_id = models.CharField(max_length=64, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        ordering = ['pk']
        constraints = [models.CheckConstraint(condition=models.Q(reason__in=[
            'PURCHASE_IN', 'PURCHASE_EDIT', 'PURCHASE_DELETE', 'SALE_OUT', 'SALE_CANCEL', 'ADJUST']),
            name='stock_movement_valid_reason')]
