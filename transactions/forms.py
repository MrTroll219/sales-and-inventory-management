from django import forms
from .models import Purchase


class BootstrapMixin(forms.ModelForm):
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
