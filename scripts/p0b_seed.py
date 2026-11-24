"""Run via manage.py shell in a NEW disposable v0-goc worktree only."""
import json
from django.contrib.auth import get_user_model
from accounts.models import Customer, Vendor
from store.models import Category, Item
from transactions.models import Purchase, Sale

if Item.objects.exists() or Purchase.objects.exists() or Sale.objects.exists():
    raise RuntimeError("Refusing to seed a database containing business data")

get_user_model().objects.create_superuser(
    username="demo", email="demo@example.invalid", password="Demo@12345",
)
category = Category.objects.create(name="Đồ uống")
vendor = Vendor.objects.create(name="NCC A")
item = Item.objects.create(name="Nước suối", description="Dữ liệu demo P0b",
                           category=category, vendor=vendor, quantity=0, price=100)
customer = Customer.objects.create(first_name="Khach", last_name="Demo",
                                   phone="0900000000")
print(json.dumps({"item_id": item.pk, "vendor_id": vendor.pk,
                  "customer_id": customer.pk}, ensure_ascii=False))
