"""Test-call adapter: preserve HC01 inputs/update_fields while testing services."""
def purchase_data(purchase, update_fields=None):
    fields = ['item_id', 'vendor_id', 'description', 'quantity', 'price', 'delivery_date', 'delivery_status']
    if update_fields is not None:
        fields = [f for f in fields if f in update_fields or f.removesuffix('_id') in update_fields]
    return {field: getattr(purchase, field) for field in fields}
