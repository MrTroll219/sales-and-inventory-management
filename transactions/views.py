# Standard library imports
import json
import logging
from decimal import Decimal, DecimalException
from functools import wraps

from django.core.exceptions import ValidationError

# Django core imports
from django.http import JsonResponse, HttpResponse, HttpResponseNotAllowed
from django.urls import reverse
from django.shortcuts import render
from django.db import transaction
from django.db.models import F

# Class-based views
from django.views.generic import DetailView, ListView
from django.views.generic.edit import CreateView, UpdateView, DeleteView

# Authentication and permissions
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin

# Third-party packages
from openpyxl import Workbook

# Local app imports
from store.models import Item
from accounts.models import Customer
from .models import Sale, Purchase, SaleDetail
from .forms import PurchaseForm
from .utils import to_excel_datetime
from .pricing import (SaleInputError, positive_integer, compute_sale_totals,
                      check_client_total)


logger = logging.getLogger(__name__)


def is_ajax(request):
    return request.META.get('HTTP_X_REQUESTED_WITH') == 'XMLHttpRequest'


@login_required
def export_sales_to_excel(request):
    # Create a workbook and select the active worksheet.
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = 'Sales'

    # Define the column headers
    columns = [
        'ID', 'Date', 'Customer', 'Sub Total',
        'Grand Total', 'Tax Amount', 'Tax Percentage',
        'Amount Paid', 'Amount Change'
    ]
    worksheet.append(columns)

    # Fetch sales data
    sales = Sale.objects.all()

    for sale in sales:
        worksheet.append([
            sale.id,
            to_excel_datetime(sale.date_added),
            sale.customer.phone,
            sale.sub_total,
            sale.grand_total,
            sale.tax_amount,
            sale.tax_percentage,
            sale.amount_paid,
            sale.amount_change
        ])
        worksheet.cell(row=worksheet.max_row, column=2).number_format = 'DD/MM/YYYY HH:MM'

    # Set up the response to send the file
    response = HttpResponse(
        content_type=(
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
    )
    response['Content-Disposition'] = 'attachment; filename=sales.xlsx'
    workbook.save(response)

    return response


@login_required
def export_purchases_to_excel(request):
    # Create a workbook and select the active worksheet.
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = 'Purchases'

    # Define the column headers
    columns = [
        'ID', 'Item', 'Description', 'Vendor', 'Order Date',
        'Delivery Date', 'Quantity', 'Delivery Status',
        'Price per item (Ksh)', 'Total Value'
    ]
    worksheet.append(columns)

    # Fetch purchases data
    purchases = Purchase.objects.all()

    for purchase in purchases:
        worksheet.append([
            purchase.id,
            purchase.item.name,
            purchase.description,
            purchase.vendor.name,
            to_excel_datetime(purchase.order_date),
            to_excel_datetime(purchase.delivery_date),
            purchase.quantity,
            purchase.get_delivery_status_display(),
            purchase.price,
            purchase.total_value
        ])
        for column in (5, 6):
            worksheet.cell(row=worksheet.max_row, column=column).number_format = 'DD/MM/YYYY HH:MM'

    # Set up the response to send the file
    response = HttpResponse(
        content_type=(
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
    )
    response['Content-Disposition'] = 'attachment; filename=purchases.xlsx'
    workbook.save(response)

    return response


class SaleListView(LoginRequiredMixin, ListView):
    """
    View to list all sales with pagination.
    """

    model = Sale
    template_name = "transactions/sales_list.html"
    context_object_name = "sales"
    paginate_by = 10
    ordering = ['date_added']


class SaleDetailView(LoginRequiredMixin, DetailView):
    """
    View to display details of a specific sale.
    """

    model = Sale
    template_name = "transactions/saledetail.html"


def sale_login_required(view):
    """Use Django login redirects, with an explicit JSON 401 for AJAX callers."""
    protected = login_required(view)

    @wraps(view)
    def check(request, *args, **kwargs):
        if is_ajax(request) and not request.user.is_authenticated:
            return JsonResponse({"status": "error", "message": "Vui lòng đăng nhập."}, status=401)
        return protected(request, *args, **kwargs)
    return check


@sale_login_required
def SaleCreateView(request):
    if request.method == 'GET':
        return render(request, "transactions/sale_create.html", {
            "active_icon": "sales",
            "customers": [c.to_select2() for c in Customer.objects.all()],
        })
    if request.method != 'POST':
        return HttpResponseNotAllowed(['GET', 'POST'])
    try:
        data = json.loads(request.body, parse_float=Decimal)
        if not isinstance(data, dict):
            raise SaleInputError("Dữ liệu đơn hàng phải là JSON object.")
        customer_id = positive_integer(data.get('customer'), 'customer', maximum=9223372036854775807)
        raw_lines = data.get('items')
        if not isinstance(raw_lines, list) or not raw_lines:
            raise SaleInputError("Đơn hàng phải có ít nhất một mặt hàng.")
        quantities, client_lines = {}, []
        for line in raw_lines:
            if not isinstance(line, dict):
                raise SaleInputError("Mỗi dòng hàng phải là JSON object.")
            item_id = positive_integer(line.get('id'), 'id', maximum=9223372036854775807)
            quantity = positive_integer(line.get('quantity'), 'quantity')
            quantities[item_id] = positive_integer(quantities.get(item_id, 0) + quantity, 'quantity')
            client_lines.append((line, item_id, quantity))

        with transaction.atomic():
            customer = Customer.objects.get(pk=customer_id)
            items = {item.pk: item for item in Item.objects.select_for_update()
                     .filter(pk__in=sorted(quantities)).order_by('pk')}
            if set(items) != set(quantities):
                raise SaleInputError("Có mặt hàng không tồn tại.")
            totals = compute_sale_totals([
                {'id': item_id, 'price': items[item_id].price, 'quantity': quantity}
                for item_id, quantity in quantities.items()
            ], data.get('tax_percentage', 0), data.get('amount_paid'))
            prices = {line['id']: line['price'] for line in totals['lines']}
            for line, item_id, quantity in client_lines:
                check_client_total(line, 'total_item', prices[item_id] * quantity)
            for field in ('sub_total', 'grand_total'):
                check_client_total(data, field, totals[field])
            for item_id, quantity in quantities.items():
                if items[item_id].quantity < quantity:
                    raise SaleInputError(f"Không đủ tồn kho: {items[item_id].name}.")
            # All input checks finish before the first Sale/SaleDetail/stock write.
            new_sale = Sale.objects.create(customer=customer, **{
                key: value for key, value in totals.items() if key != 'lines'
            })
            for line in totals['lines']:
                changed = Item.objects.filter(pk=line['id'], quantity__gte=line['quantity']).update(
                    quantity=F('quantity') - line['quantity'])
                if not changed:
                    raise SaleInputError(f"Không đủ tồn kho: {items[line['id']].name}.")
                SaleDetail.objects.create(sale=new_sale, item=items[line['id']],
                                          price=line['price'], quantity=line['quantity'],
                                          total_detail=line['total_detail'])
        return JsonResponse({'status': 'success', 'message': 'Sale created successfully!',
                             'redirect': '/transactions/sales/', 'sale_id': new_sale.pk,
                             'grand_total': totals['grand_total']})
    except Customer.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Khách hàng không tồn tại.'}, status=400)
    except (ValueError, TypeError, UnicodeDecodeError, DecimalException, OverflowError) as error:
        return JsonResponse({'status': 'error', 'message': str(error)}, status=400)


class SaleDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    """
    View to delete a sale.
    """

    model = Sale
    template_name = "transactions/saledelete.html"

    def get_success_url(self):
        """
        Redirect to the sales list after successful deletion.
        """
        return reverse("saleslist")

    def test_func(self):
        """
        Allow deletion only for superusers.
        """
        return self.request.user.is_superuser


class PurchaseListView(LoginRequiredMixin, ListView):
    """
    View to list all purchases with pagination.
    """

    model = Purchase
    template_name = "transactions/purchases_list.html"
    context_object_name = "purchases"
    paginate_by = 10


class PurchaseDetailView(LoginRequiredMixin, DetailView):
    """
    View to display details of a specific purchase.
    """

    model = Purchase
    template_name = "transactions/purchasedetail.html"


class PurchaseCreateView(LoginRequiredMixin, CreateView):
    """
    View to create a new purchase.
    """

    model = Purchase
    form_class = PurchaseForm
    template_name = "transactions/purchases_form.html"

    def get_success_url(self):
        """
        Redirect to the purchases list after successful form submission.
        """
        return reverse("purchaseslist")


class PurchaseUpdateView(LoginRequiredMixin, UpdateView):
    """
    View to update an existing purchase.
    """

    model = Purchase
    form_class = PurchaseForm
    template_name = "transactions/purchases_form.html"

    def form_valid(self, form):
        try:
            return super().form_valid(form)
        except ValidationError as error:
            # Purchase.save has already rolled back the purchase and stock rows.
            form.add_error(None, error)
            return self.form_invalid(form)

    def get_success_url(self):
        """
        Redirect to the purchases list after successful form submission.
        """
        return reverse("purchaseslist")


class PurchaseDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    """
    View to delete a purchase.
    """

    model = Purchase
    template_name = "transactions/purchasedelete.html"

    def get_success_url(self):
        """
        Redirect to the purchases list after successful deletion.
        """
        return reverse("purchaseslist")

    def test_func(self):
        """
        Allow deletion only for superusers.
        """
        return self.request.user.is_superuser
