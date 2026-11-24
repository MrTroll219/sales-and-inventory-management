from django.core.exceptions import ValidationError
from django.db import models, router, transaction
from django.db.models import F
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
    sub_total = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.0
    )
    grand_total = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.0
    )
    tax_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.0
    )
    tax_percentage = models.FloatField(default=0.0)
    amount_paid = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.0
    )
    amount_change = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.0
    )

    class Meta:
        db_table = "sales"
        verbose_name = "Sale"
        verbose_name_plural = "Sales"

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
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )
    quantity = models.PositiveIntegerField()
    total_detail = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        db_table = "sale_details"
        verbose_name = "Sale Detail"
        verbose_name_plural = "Sale Details"

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
    quantity = models.PositiveIntegerField(default=0)
    delivery_status = models.CharField(
        choices=DELIVERY_CHOICES,
        max_length=1,
        default="P",
        verbose_name="Delivery Status",
    )
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.0,
        verbose_name="Price per item (Ksh)",
    )
    total_value = models.DecimalField(max_digits=10, decimal_places=2)

    def save(self, force_insert=False, force_update=False, using=None, update_fields=None):
        """HC01: persist the purchase and its stock delta in one transaction."""
        using = using or router.db_for_write(type(self), instance=self)
        kwargs = {"force_insert": force_insert, "force_update": force_update, "using": using}
        if update_fields is not None:
            update_fields = set(update_fields)
            if not update_fields:
                return

        with transaction.atomic(using=using):
            previous = (
                type(self).objects.using(using).select_for_update()
                .filter(pk=self.pk).values("item_id", "quantity", "price").first()
                if self.pk is not None else None
            )
            item_id, quantity, price = self.item_id, self.quantity, self.price
            if previous is not None and update_fields is not None:
                # save(update_fields=...) must not apply changes excluded from SQL.
                if not {"item", "item_id"} & update_fields:
                    item_id = previous["item_id"]
                if "quantity" not in update_fields:
                    quantity = previous["quantity"]
                if "price" not in update_fields:
                    price = previous["price"]
            self.total_value = price * quantity
            if update_fields is not None:
                if {"price", "quantity"} & update_fields:
                    update_fields.add("total_value")
                kwargs["update_fields"] = update_fields

            deltas = {item_id: quantity}
            if previous is not None:
                old_id = previous["item_id"]
                deltas[old_id] = deltas.get(old_id, 0) - previous["quantity"]
            # Serialize changes to each stock row in deterministic order.
            for stock_id in sorted(deltas):
                delta = deltas[stock_id]
                if not delta:
                    continue
                stock = Item.objects.using(using).select_for_update().get(pk=stock_id)
                changed = Item.objects.using(using).filter(
                    pk=stock_id, quantity__gte=-delta,
                ).update(quantity=F("quantity") + delta)
                if not changed:
                    raise ValidationError(
                        f"Không thể cập nhật phiếu nhập: tồn kho của {stock.name} "
                        "sẽ âm. Hàng của phiếu này có thể đã được bán."
                    )
            super().save(**kwargs)
        # A caller may have supplied a stale cached Item; do not expose its old stock.
        self._state.fields_cache.pop("item", None)

    def __str__(self):
        """
        Returns a string representation of the Purchase instance.
        """
        return str(self.item.name)

    class Meta:
        ordering = ["order_date"]
