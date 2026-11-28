"""HT02: one validated filtering path for transaction lists and exports."""
from datetime import datetime, time, timezone as utc
from decimal import Decimal
from zoneinfo import ZoneInfo

import django_filters
from django import forms
from django.db.models import Q, Value
from django.db.models.functions import Concat

from accounts.models import Customer, Vendor
from store.models import Item
from store.money import MAX_MONEY
from .models import Sale, Purchase


VN_TIMEZONE = ZoneInfo('Asia/Ho_Chi_Minh')


class TransactionFilterForm(forms.Form):
    def clean(self):
        data = super().clean()
        start, end = data.get('date_from'), data.get('date_to')
        if start and end and start > end:
            self.add_error('date_to', 'Ngày kết thúc phải bằng hoặc sau ngày bắt đầu.')
        for field, value in (('date_from', start), ('date_to', end)):
            if value:
                try:
                    datetime.combine(value, time.min, VN_TIMEZONE).astimezone(utc.utc)
                except (OverflowError, ValueError):
                    self.add_error(field, 'Ngày nằm ngoài khoảng thời gian được hỗ trợ.')
        minimum, maximum = data.get('min'), data.get('max')
        if minimum is not None and maximum is not None and minimum > maximum:
            self.add_error('max', 'Tổng tiền tối đa phải bằng hoặc lớn hơn tối thiểu.')
        return data


def date_filter(label, method):
    return django_filters.DateFilter(label=label, method=method,
        input_formats=['%d/%m/%Y', '%Y-%m-%d'],
        widget=forms.DateInput(format='%d/%m/%Y', attrs={'placeholder': 'dd/mm/yyyy'}))


class TransactionFilter(django_filters.FilterSet):
    date_from = date_filter('Từ ngày', 'filter_date_from')
    date_to = date_filter('Đến ngày (bao gồm)', 'filter_date_to')
    date_field = None

    def filter_date_from(self, queryset, name, value):
        return queryset.filter(**{self.date_field + '__gte': datetime.combine(value, time.min, VN_TIMEZONE)})

    def filter_date_to(self, queryset, name, value):
        # Inclusive last microsecond; no next-day overflow on 31/12/9999.
        return queryset.filter(**{self.date_field + '__lte': datetime.combine(value, time.max, VN_TIMEZONE)})

    class Meta:
        form = TransactionFilterForm
        fields = []


class SaleFilter(TransactionFilter):
    date_field = 'date_added'
    status = django_filters.ChoiceFilter(label='Trạng thái đơn', choices=Sale.Status.choices)
    customer = django_filters.ModelChoiceFilter(label='Khách hàng', queryset=Customer.objects.order_by('first_name', 'pk'))
    q = django_filters.CharFilter(label='Tên / số điện thoại khách', method='search_customer', max_length=256)
    min = django_filters.NumberFilter(field_name='grand_total', lookup_expr='gte', label='Tổng tiền từ (VND)',
        min_value=Decimal(0), max_value=MAX_MONEY, max_digits=15, decimal_places=0)
    max = django_filters.NumberFilter(field_name='grand_total', lookup_expr='lte', label='Tổng tiền đến (VND)',
        min_value=Decimal(0), max_value=MAX_MONEY, max_digits=15, decimal_places=0)

    def search_customer(self, queryset, name, value):
        return queryset.alias(customer_full_name=Concat('customer__first_name', Value(' '), 'customer__last_name')).filter(
            Q(customer_full_name__icontains=value) | Q(customer__phone__icontains=value))

    class Meta(TransactionFilter.Meta):
        model = Sale


class PurchaseFilter(TransactionFilter):
    date_field = 'order_date'
    vendor = django_filters.ModelChoiceFilter(label='Nhà cung cấp', queryset=Vendor.objects.order_by('name', 'pk'))
    item = django_filters.ModelChoiceFilter(label='Mặt hàng', queryset=Item.objects.select_related('category').order_by('name', 'pk'))
    delivery_status = django_filters.ChoiceFilter(label='Trạng thái giao',
        choices=[('P', 'Chờ giao'), ('S', 'Đã giao')])

    class Meta(TransactionFilter.Meta):
        model = Purchase


def filtered_transactions(kind, params):
    """Return (filter, queryset); invalid input never silently exports all rows."""
    if kind == 'sales':
        filters = SaleFilter(params, queryset=Sale.objects.select_related('customer').order_by('-date_added', '-pk'))
    elif kind == 'purchases':
        filters = PurchaseFilter(params, queryset=Purchase.objects.select_related('item', 'vendor').order_by('-order_date', '-pk'))
    else:
        raise ValueError('Unknown transaction kind')
    return filters, filters.qs if filters.is_valid() else filters.queryset.none()


def export_filename(kind, filters):
    data = filters.form.cleaned_data
    start, end = data.get('date_from'), data.get('date_to')
    if not start and not end:
        return kind + '.xlsx'
    return f"{kind}_{start.isoformat() if start else 'all'}_{end.isoformat() if end else 'all'}.xlsx"
