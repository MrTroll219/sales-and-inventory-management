"""TU03: shared runtime VND arithmetic, formatting and form/field policy."""
from decimal import Decimal, DecimalException, ROUND_HALF_UP
from django import forms
from django.core.exceptions import ValidationError
from django.db import models

VND_UNIT = Decimal('1')
MAX_MONEY = Decimal('999999999999999')
INTEGER_MESSAGE = 'Số tiền VND phải là số nguyên'


def to_vnd(value):
    if isinstance(value, bool):
        raise ValueError('Số tiền không hợp lệ')
    try:
        number = Decimal(str(value))
        if not number.is_finite():
            raise ValueError('Số tiền phải hữu hạn')
        return number.quantize(VND_UNIT, rounding=ROUND_HALF_UP)
    except (DecimalException, TypeError):
        raise ValueError('Số tiền không hợp lệ')


def format_vnd(value):
    return f'{to_vnd(value):,.0f}'.replace(',', '.') + ' ₫'


class VNDFormField(forms.DecimalField):
    def to_python(self, value):
        value = super().to_python(value)
        if value is not None:
            whole = to_vnd(value)
            if value != whole:
                raise ValidationError(INTEGER_MESSAGE, code='vnd_integer')
            return whole  # Accept old input "5.00" because its numeric value is integral.
        return value


class VNDField(models.DecimalField):
    """Decimal(15,0), with the same whole-VND rule in every generated ModelForm."""
    def formfield(self, **kwargs):
        kwargs.setdefault('form_class', VNDFormField)
        return super().formfield(**kwargs)

    def get_db_prep_value(self, value, connection, prepared=False):
        value = self.to_python(value)
        if value is not None:
            value = to_vnd(value)
        return connection.ops.adapt_decimalfield_value(value, self.max_digits, self.decimal_places)
