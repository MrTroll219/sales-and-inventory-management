from django.core.exceptions import ValidationError


class InventoryError(ValidationError):
    """Business failure, suitable for a form non-field error."""


class InvalidQuantity(InventoryError):
    pass


class InsufficientStock(InventoryError):
    def __init__(self, item, requested, available):
        self.item, self.requested, self.available = item, requested, available
        super().__init__(f'Không đủ tồn kho: {item.name}; yêu cầu {requested}, còn {available}; tồn kho sẽ âm.')
