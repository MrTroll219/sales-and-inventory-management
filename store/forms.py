from .form_labels import VietnameseFormMixin
from django import forms
from .models import Item, Category, Delivery


class ItemForm(VietnameseFormMixin, forms.ModelForm):
    """
    A form for creating or updating an Item in the inventory.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Old clients omit the new field; preserve existing thresholds on edit.
        self.fields['min_stock_level'].required = False

    def clean_min_stock_level(self):
        value = self.cleaned_data['min_stock_level']
        if value is None:
            return self.instance.min_stock_level if self.add_prefix('min_stock_level') not in self.data else 0
        return value

    def save(self, commit=True):
        if not commit:
            return super().save(commit=False)
        if not self.is_valid():
            raise ValueError('Cannot save an invalid Item form.')
        from transactions.services.stock import save_item
        values = dict(self.cleaned_data)
        if self.instance.pk and self.add_prefix('min_stock_level') in self.data and 'quantity' not in self.changed_data:
            values.pop('quantity', None)  # A threshold-only edit is metadata, not a stock adjustment.
        self.instance = save_item(values, self.instance.pk)
        return self.instance

    class Meta:
        model = Item
        fields = [
            'name',
            'description',
            'category',
            'quantity',
            'min_stock_level',
            'price',
            'expiring_date',
            'vendor'
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(
                attrs={
                    'class': 'form-control',
                    'rows': 2
                }
            ),
            'category': forms.Select(attrs={'class': 'form-control'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control'}),
            'min_stock_level': forms.NumberInput(attrs={'class': 'form-control', 'min': '0', 'step': '1'}),
            'price': forms.NumberInput(
                attrs={
                    'class': 'form-control',
                    'step': '1'
                }
            ),
            'expiring_date': forms.DateTimeInput(
                attrs={
                    'class': 'form-control',
                    'type': 'datetime-local'
                }
            ),
            'vendor': forms.Select(attrs={'class': 'form-control'}),
        }


class CategoryForm(VietnameseFormMixin, forms.ModelForm):
    """
    A form for creating or updating category.
    """
    class Meta:
        model = Category
        fields = ['name']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter category name',
                'aria-label': 'Category Name'
            }),
        }
        labels = {
            'name': 'Category Name',
        }


class DeliveryForm(VietnameseFormMixin, forms.ModelForm):
    class Meta:
        model = Delivery
        fields = [
            'item',
            'customer_name',
            'phone_number',
            'location',
            'date',
            'is_delivered'
        ]
        widgets = {
            'item': forms.Select(attrs={
                'class': 'form-control',
                'placeholder': 'Select item',
            }),
            'customer_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter customer name',
            }),
            'phone_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter phone number',
            }),
            'location': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter delivery location',
            }),
            'date': forms.DateTimeInput(attrs={
                'class': 'form-control',
                'placeholder': 'Select delivery date and time',
                'type': 'datetime-local'
            }),
            'is_delivered': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
                'label': 'Mark as delivered',
            }),
        }
