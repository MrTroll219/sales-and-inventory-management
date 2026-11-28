"""Shared date conversion for HC02 Excel exports."""
from django.utils import timezone


def to_excel_datetime(value, tz=None):
    """Excel stores naive datetimes; convert aware values to local time first."""
    if value is None:
        return None
    if timezone.is_aware(value):
        return timezone.localtime(value, tz).replace(tzinfo=None)
    return value
