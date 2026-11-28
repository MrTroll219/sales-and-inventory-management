from store.form_labels import VietnameseFormMixin
from django import forms
from .models import Purchase


class BootstrapMixin(VietnameseFormMixin, forms.ModelForm):
    """
    A mixin to add Bootstrap classes to form fields.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault('class', 'form-control')


class PurchaseForm(BootstrapMixin, forms.ModelForm):
    """
    A form for creating and updating Purchase instances.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Keep existing accepted formats and explicitly support datetime-local.
        field = self.fields['delivery_date']
        field.input_formats = [*field.input_formats, '%Y-%m-%dT%H:%M']

    def clean_delivery_date(self):
        value = self.cleaned_data['delivery_date']
        original = self.instance.delivery_date
        # The requested widget displays minutes. A description-only edit must
        # also preserve seconds/microseconds already stored in older records.
        if value is not None and original is not None:
            if value.replace(second=0, microsecond=0) == original.replace(second=0, microsecond=0):
                return original
        return value

    class Meta:
        model = Purchase
        fields = [
            'item',  'price', 'description', 'vendor',
            'quantity', 'delivery_date', 'delivery_status'
        ]
        widgets = {
            'delivery_date': forms.DateTimeInput(
                format='%Y-%m-%dT%H:%M',
                attrs={
                    'class': 'form-control',
                    'type': 'datetime-local'
                }
            ),
            'description': forms.Textarea(
                attrs={'rows': 1, 'cols': 40}
            ),
            'quantity': forms.NumberInput(
                attrs={'class': 'form-control'}
            ),
            'delivery_status': forms.Select(
                attrs={'class': 'form-control'}
            ),
            'price': forms.NumberInput(
                attrs={'class': 'form-control'}
            ),
        }


class SaleCancellationForm(forms.Form):
    reason = forms.CharField(label='Lý do hủy', min_length=5, strip=True,
        widget=forms.Textarea(attrs={'rows': 4, 'class': 'form-control'}),
        error_messages={'required': 'Vui lòng nhập lý do hủy.',
                        'min_length': 'Lý do hủy phải có ít nhất 5 ký tự.'})
