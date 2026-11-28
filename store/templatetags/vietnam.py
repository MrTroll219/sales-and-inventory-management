from django import template
from django.utils import timezone
from zoneinfo import ZoneInfo
from store.money import format_vnd

register = template.Library()


@register.filter
def vnd(value):
    return format_vnd(value)


@register.filter
def vn_datetime(value):
    if value is None:
        return ''
    if timezone.is_aware(value):
        value = timezone.localtime(value, ZoneInfo('Asia/Ho_Chi_Minh'))
    return value.strftime('%d/%m/%Y %H:%M')
