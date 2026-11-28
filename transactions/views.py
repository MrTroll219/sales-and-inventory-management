from zoneinfo import ZoneInfo
# Standard library imports
import json
import logging
from decimal import Decimal, DecimalException
from functools import wraps

from django.core.exceptions import ValidationError, PermissionDenied
from django.db import transaction
from django.contrib import messages
from django.db.models import Count, Sum, Q

# Django core imports
from django.http import JsonResponse, HttpResponse, HttpResponseNotAllowed
from django.urls import reverse
from django.shortcuts import render, get_object_or_404

# Class-based views
from django.views.generic import DetailView, ListView
from django.views.generic.edit import CreateView, UpdateView, DeleteView, FormView

# Authentication and permissions
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin

# Third-party packages
from openpyxl import Workbook

# Local app imports
from store.models import Item
from accounts.models import Customer
from .models import Sale, Purchase, SaleDetail
from .forms import PurchaseForm, SaleCancellationForm
from .filters import filtered_transactions, export_filename
from .utils import to_excel_datetime
from .pricing import SaleInputError
from .services.sales import create_sale, SaleLines, cancel_sale
from .services.purchases import create_purchase, update_purchase, delete_purchase
from .services.exceptions import InventoryError
from django.http import HttpResponseRedirect


logger = logging.getLogger(__name__)


def is_ajax(request):
    return request.META.get('HTTP_X_REQUESTED_WITH') == 'XMLHttpRequest'


@login_required
def export_sales_to_excel(request):
    filters, sales = filtered_transactions('sales', request.GET)
    if not filters.is_valid():
        return JsonResponse({'status': 'error', 'errors': filters.form.errors.get_json_data()}, status=400)
    # Create a workbook and select the active worksheet.
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = 'Đơn bán'

    # Define the column headers
    columns = ['Mã', 'Ngày bán', 'Khách hàng', 'Tạm tính (VND)', 'Tổng (VND)',
               'Thuế (VND)', 'Thuế (%)', 'Đã trả (VND)', 'Tiền thừa (VND)', 'Trạng thái']
    worksheet.append(columns)

    for sale in sales:
        worksheet.append([
            sale.id,
            to_excel_datetime(sale.date_added, ZoneInfo('Asia/Ho_Chi_Minh')),
            sale.customer.phone,
            sale.sub_total,
            sale.grand_total,
            sale.tax_amount,
            sale.tax_percentage,
            sale.amount_paid,
            sale.amount_change,
            sale.get_status_display()
        ])
        worksheet.cell(row=worksheet.max_row, column=2).number_format = 'DD/MM/YYYY HH:MM'
        for column in (4, 5, 6, 8, 9):
            worksheet.cell(row=worksheet.max_row, column=column).number_format = '#,##0 "₫"'

    # Set up the response to send the file
    response = HttpResponse(
        content_type=(
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
    )
    response['Content-Disposition'] = 'attachment; filename=' + export_filename('sales', filters)
    workbook.save(response)

    return response


@login_required
def export_purchases_to_excel(request):
    filters, purchases = filtered_transactions('purchases', request.GET)
    if not filters.is_valid():
        return JsonResponse({'status': 'error', 'errors': filters.form.errors.get_json_data()}, status=400)
    # Create a workbook and select the active worksheet.
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = 'Phiếu nhập'

    # Define the column headers
    columns = ['Mã', 'Mặt hàng', 'Mô tả', 'Nhà cung cấp', 'Ngày nhập', 'Ngày giao',
               'Số lượng', 'Trạng thái giao', 'Đơn giá (VND)', 'Thành tiền (VND)']
    worksheet.append(columns)

    for purchase in purchases:
        worksheet.append([
            purchase.id,
            purchase.item.name,
            purchase.description,
            purchase.vendor.name,
            to_excel_datetime(purchase.order_date, ZoneInfo('Asia/Ho_Chi_Minh')),
            to_excel_datetime(purchase.delivery_date, ZoneInfo('Asia/Ho_Chi_Minh')),
            purchase.quantity,
            {'P':'Chờ giao','S':'Đã giao'}.get(purchase.delivery_status, purchase.get_delivery_status_display()),
            purchase.price,
            purchase.total_value
        ])
        for money_column in (9, 10):
            worksheet.cell(row=worksheet.max_row, column=money_column).number_format = '#,##0 "₫"'
        for column in (5, 6):
            worksheet.cell(row=worksheet.max_row, column=column).number_format = 'DD/MM/YYYY HH:MM'

    # Set up the response to send the file
    response = HttpResponse(
        content_type=(
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
    )
    response['Content-Disposition'] = 'attachment; filename=' + export_filename('purchases', filters)
    workbook.save(response)

    return response


class TransactionListMixin:
    transaction_kind = None
    total_field = None

    def get_queryset(self):
        self.transaction_filter, queryset = filtered_transactions(self.transaction_kind, self.request.GET)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        total = Sum(self.total_field, filter=Q(status=Sale.Status.COMPLETED)) if self.transaction_kind == 'sales' else Sum(self.total_field)
        summary = self.object_list.aggregate(filtered_count=Count('pk'), filtered_total=total)
        params = self.request.GET.copy()
        params.pop('page', None)
        context.update(summary)
        context['filtered_total'] = summary['filtered_total'] or Decimal(0)
        context['transaction_filter'] = self.transaction_filter
        context['filter_query'] = params.urlencode()
        return context


class SaleListView(LoginRequiredMixin, TransactionListMixin, ListView):
    """
    View to list all sales with pagination.
    """

    model = Sale
    template_name = "transactions/sales_list.html"
    context_object_name = "sales"
    paginate_by = 10
    transaction_kind = 'sales'
    total_field = 'grand_total'


class SaleDetailView(LoginRequiredMixin, DetailView):
    """
    View to display details of a specific sale.
    """

    model = Sale
    queryset = Sale.objects.select_related('customer', 'cancellation', 'cancellation__cancelled_by')
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
            "active_icon": "sales", "customers": [c.to_select2() for c in Customer.objects.all()],
        })
    if request.method != 'POST':
        return HttpResponseNotAllowed(['GET', 'POST'])
    try:
        data = json.loads(request.body, parse_float=Decimal)
        if not isinstance(data, dict):
            raise SaleInputError("Dữ liệu đơn hàng phải là JSON object.")
        sale = create_sale(data.get('customer'), SaleLines(data.get('items'), data),
                           data.get('tax_percentage', 0), data.get('amount_paid'), request.user)
        return JsonResponse({'status': 'success', 'message': 'Sale created successfully!',
            'redirect': '/transactions/sales/', 'sale_id': sale.pk, 'grand_total': sale.grand_total})
    except Customer.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Khách hàng không tồn tại.'}, status=400)
    except InventoryError as error:
        return JsonResponse({'status': 'error', 'message': '; '.join(error.messages)}, status=400)
    except (ValueError, TypeError, UnicodeDecodeError, DecimalException, OverflowError) as error:
        return JsonResponse({'status': 'error', 'message': str(error)}, status=400)


class SaleCancelView(LoginRequiredMixin, UserPassesTestMixin, FormView):
    template_name = 'transactions/sale_cancel.html'
    form_class = SaleCancellationForm

    def test_func(self):
        return self.request.user.is_staff or self.request.user.is_superuser

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['sale'] = get_object_or_404(Sale, pk=self.kwargs['pk'])
        return context

    def form_valid(self, form):
        try:
            cancel_sale(self.kwargs['pk'], self.request.user, form.cleaned_data['reason'])
        except Sale.DoesNotExist:
            get_object_or_404(Sale, pk=self.kwargs['pk'])
        except ValidationError as error:
            form.add_error(None, error)
            return self.form_invalid(form)
        messages.success(self.request, 'Đã hủy đơn và hoàn kho thành công.')
        return HttpResponseRedirect(reverse('sale-detail', kwargs={'pk': self.kwargs['pk']}))

    def form_invalid(self, form):
        messages.error(self.request, 'Không thể hủy đơn. Vui lòng kiểm tra lý do và trạng thái đơn.')
        return super().form_invalid(form)


class SaleDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    """
    View to delete a sale.
    """

    model = Sale
    template_name = "transactions/saledelete.html"

    def get_object(self, queryset=None):
        sale = super().get_object(queryset)
        if sale.status != Sale.Status.CANCELLED:
            raise PermissionDenied('Chỉ được xóa đơn đã hủy.')
        return sale

    @transaction.atomic
    def form_valid(self, form):
        sale = Sale.objects.select_for_update().get(pk=self.object.pk)
        if sale.status != Sale.Status.CANCELLED:
            raise PermissionDenied('Chỉ được xóa đơn đã hủy.')
        sale.delete()
        messages.success(self.request, 'Đã xóa đơn đã hủy; lịch sử hủy vẫn được giữ.')
        return HttpResponseRedirect(self.get_success_url())

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


class PurchaseListView(LoginRequiredMixin, TransactionListMixin, ListView):
    """
    View to list all purchases with pagination.
    """

    model = Purchase
    template_name = "transactions/purchases_list.html"
    context_object_name = "purchases"
    transaction_kind = "purchases"
    total_field = "total_value"
    paginate_by = 10


class PurchaseDetailView(LoginRequiredMixin, DetailView):
    """
    View to display details of a specific purchase.
    """

    model = Purchase
    template_name = "transactions/purchasedetail.html"


class PurchaseServiceMixin:
    def form_valid(self, form):
        try:
            if self.object is None:
                self.object = create_purchase(form.cleaned_data)
            else:
                self.object = update_purchase(self.object.pk, form.cleaned_data)
            return HttpResponseRedirect(self.get_success_url())
        except ValidationError as error:
            form.add_error(None, error)
            return self.form_invalid(form)


class PurchaseCreateView(PurchaseServiceMixin, LoginRequiredMixin, CreateView):
    """
    View to create a new purchase.
    """

    model = Purchase
    form_class = PurchaseForm
    template_name = "transactions/purchases_form.html"

    def get_initial(self):
        initial = super().get_initial()
        try:
            item_id = int(self.request.GET.get('item', ''))
        except (ValueError, TypeError):
            return initial
        if 0 < item_id <= 9223372036854775807 and Item.objects.filter(pk=item_id).exists():
            initial['item'] = item_id
        return initial

    def get_success_url(self):
        """
        Redirect to the purchases list after successful form submission.
        """
        return reverse("purchaseslist")


class PurchaseUpdateView(PurchaseServiceMixin, LoginRequiredMixin, UpdateView):
    """
    View to update an existing purchase.
    """

    model = Purchase
    form_class = PurchaseForm
    template_name = "transactions/purchases_form.html"


    def get_success_url(self):
        """
        Redirect to the purchases list after successful form submission.
        """
        return reverse("purchaseslist")


class PurchaseDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    def form_valid(self, form):
        try:
            delete_purchase(self.object.pk)
            return HttpResponseRedirect(self.get_success_url())
        except InventoryError as error:
            form.add_error(None, error)
            return self.form_invalid(form)

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
