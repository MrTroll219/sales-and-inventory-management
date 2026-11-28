from django.contrib import admin
from .models import Sale, SaleDetail, Purchase, StockMovement, SaleCancellation
from django.core.exceptions import PermissionDenied
from django.db import transaction


@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    """
    Admin interface configuration for the Sale model.
    """
    list_display = (
        'id',
        'customer',
        'date_added',
        'grand_total',
        'amount_paid',
        'amount_change',
        'status'
    )
    search_fields = ('customer__name', 'id')
    list_filter = ('date_added', 'customer', 'status')
    ordering = ('-date_added',)
    readonly_fields = ('date_added', 'status')
    date_hierarchy = 'date_added'

    def save_model(self, request, obj, form, change):
        """
        Save the Sale instance, overriding the default save behavior.
        """
        super().save_model(request, obj, form, change)


    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser and (obj is None or obj.status == Sale.Status.CANCELLED)

    def get_actions(self, request):
        actions = super().get_actions(request)
        actions.pop('delete_selected', None)
        return actions

    @transaction.atomic
    def delete_model(self, request, obj):
        sale = Sale.objects.select_for_update().get(pk=obj.pk)
        if not self.has_delete_permission(request, sale):
            raise PermissionDenied('Chỉ superuser được xóa đơn đã hủy.')
        sale.delete()

    @transaction.atomic
    def delete_queryset(self, request, queryset):
        rows = list(queryset.select_for_update())
        if not request.user.is_superuser or any(row.status != Sale.Status.CANCELLED for row in rows):
            raise PermissionDenied('Chỉ superuser được xóa đơn đã hủy.')
        for row in rows:
            row.delete()


@admin.register(SaleDetail)
class SaleDetailAdmin(admin.ModelAdmin):
    """
    Admin interface configuration for the SaleDetail model.
    """
    list_display = (
        'id',
        'sale',
        'item',
        'price',
        'quantity',
        'total_detail'
    )
    search_fields = ('sale__id', 'item__name')
    list_filter = ('sale', 'item')
    ordering = ('sale', 'item')

    def save_model(self, request, obj, form, change):
        """
        Save the SaleDetail instance, overriding the default save behavior.
        """
        super().save_model(request, obj, form, change)


@admin.register(Purchase)
class PurchaseAdmin(admin.ModelAdmin):
    """
    Admin interface configuration for the Purchase model.
    """
    list_display = (
        'slug',
        'item',
        'vendor',
        'order_date',
        'delivery_date',
        'quantity',
        'price',
        'total_value',
        'delivery_status'
    )
    search_fields = ('item__name', 'vendor__name', 'slug')
    list_filter = ('order_date', 'vendor', 'delivery_status')
    ordering = ('-order_date',)
    readonly_fields = ('total_value',)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = ('item', 'delta', 'quantity_after', 'reason', 'ref_type', 'ref_id', 'created_at', 'created_by')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(SaleCancellation)
class SaleCancellationAdmin(admin.ModelAdmin):
    list_display = ('sale_reference', 'sale', 'cancelled_by', 'cancelled_at', 'reason')
    readonly_fields = ('sale', 'sale_reference', 'reason', 'cancelled_by', 'cancelled_at', 'restored_items')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
