from django import forms
from django.conf import settings

LABELS = {'name':'Tên', 'description':'Mô tả', 'category':'Danh mục', 'quantity':'Số lượng',
    'price':'Đơn giá (VND)', 'expiring_date':'Hạn sử dụng', 'vendor':'Nhà cung cấp',
    'item':'Mặt hàng', 'customer_name':'Tên khách hàng', 'contact_number':'Số điện thoại',
    'price_per_item':'Đơn giá (VND)', 'shipping':'Phí vận chuyển (VND)', 'delivery_date':'Ngày giao',
    'delivery_status':'Trạng thái giao', 'institution_name':'Đơn vị', 'phone_number':'Số điện thoại',
    'email':'Email', 'address':'Địa chỉ', 'payment_details':'Thông tin thanh toán',
    'amount':'Số tiền (VND)', 'status':'Đã thanh toán', 'location':'Địa chỉ giao',
    'date':'Ngày giờ', 'is_delivered':'Đã giao hàng'}


def localize_form(form):
    for name, field in form.fields.items():
        field.label = LABELS.get(name, field.label)
        if name == 'delivery_status':
            field.choices = [(key, {'P':'Chờ giao', 'S':'Đã giao'}.get(key, label)) for key,label in field.choices]
        if isinstance(field, forms.DateTimeField):
            field.input_formats = list(dict.fromkeys([*field.input_formats, *settings.DATETIME_INPUT_FORMATS]))
        elif isinstance(field, forms.DateField):
            field.input_formats = list(dict.fromkeys([*field.input_formats, *settings.DATE_INPUT_FORMATS]))
    return form


class VietnameseFormMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        localize_form(self)


class VietnameseFormViewMixin:
    def get_form(self, form_class=None):
        return localize_form(super().get_form(form_class))
