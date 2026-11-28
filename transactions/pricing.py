"""HC03: pure validation and Decimal pricing; callers supply database prices."""
from decimal import Decimal, DecimalException, ROUND_HALF_UP

from store.money import to_vnd, format_vnd, MAX_MONEY, INTEGER_MESSAGE

TAX_UNIT = Decimal("0.01")



class SaleInputError(ValueError):
    """Invalid sale input, safe to report as HTTP 400."""


def decimal_value(value, name):
    if isinstance(value, bool) or not isinstance(value, (str, int, float, Decimal)):
        raise SaleInputError(f"{name} phải là số hợp lệ.")
    try:
        result = Decimal(str(value))
    except DecimalException as error:
        raise SaleInputError(f"{name} phải là số hợp lệ.") from error
    if not result.is_finite():
        raise SaleInputError(f"{name} phải là số hữu hạn.")
    return result


def positive_integer(value, name, maximum=2147483647):
    result = decimal_value(value, name)
    if result < 1 or result > maximum or result != result.to_integral_value():
        raise SaleInputError(f"{name} phải là số nguyên dương không quá {maximum}.")
    return int(result)


def money(value, name, *, strict=False):
    result = decimal_value(value, name)
    if result < 0 or result > MAX_MONEY:
        raise SaleInputError(f"{name} phải từ 0 đến {MAX_MONEY}.")
    try:
        whole = to_vnd(result)
        if strict and whole != result:
            raise SaleInputError(INTEGER_MESSAGE)
        return whole
    except DecimalException as error:
        raise SaleInputError(f"{name} không hợp lệ.") from error


def check_client_total(data, field, expected):
    """Client totals are optional assertions, never the source of stored values."""
    if field in data:
        actual = decimal_value(data[field], field)
        if actual < 0 or actual > MAX_MONEY or actual != expected:
            raise SaleInputError(f"{field} không khớp; giá trị đúng là {format_vnd(expected)}.")


def compute_sale_totals(lines, tax_percentage, amount_paid):
    """Price canonical lines {id, price FROM DB, quantity}; no ORM/network access.

    Prices and money use whole VND with ROUND_HALF_UP. Duplicate IDs are aggregated.
    Client prices must be replaced by locked Item.price before calling this function.
    """
    if not isinstance(lines, list) or not lines:
        raise SaleInputError("Đơn hàng phải có ít nhất một mặt hàng.")
    tax_percentage = decimal_value(tax_percentage, "tax_percentage")
    if not 0 <= tax_percentage <= 100:
        raise SaleInputError("tax_percentage phải từ 0 đến 100.")
    if tax_percentage != tax_percentage.quantize(TAX_UNIT, rounding=ROUND_HALF_UP):
        raise SaleInputError("tax_percentage chỉ được có tối đa 2 chữ số thập phân.")
    grouped = {}
    for line in lines:
        if not isinstance(line, dict) or not {"id", "price", "quantity"} <= line.keys():
            raise SaleInputError("Dòng hàng thiếu id, price hoặc quantity.")
        item_id = positive_integer(line["id"], "id", maximum=9223372036854775807)
        quantity = positive_integer(line["quantity"], "quantity")
        # Decimal from Item.price; legacy float callers remain supported via str.
        try:
            price = money(Decimal(str(line["price"])), "price")
        except DecimalException as error:
            raise SaleInputError("price phải là số hợp lệ.") from error
        if item_id not in grouped:
            grouped[item_id] = {"id": item_id, "price": price, "quantity": 0}
        elif grouped[item_id]["price"] != price:
            raise SaleInputError("Các dòng cùng mặt hàng phải có cùng giá DB.")
        grouped[item_id]["quantity"] = positive_integer(
            grouped[item_id]["quantity"] + quantity, "quantity")
    result_lines = []
    for item_id in sorted(grouped):
        line = grouped[item_id]
        line["total_detail"] = money(line["price"] * line["quantity"], "total_detail")
        result_lines.append(line)
    sub_total = money(sum(line["total_detail"] for line in result_lines), "sub_total")
    tax_amount = money(sub_total * tax_percentage / 100, "tax_amount")
    grand_total = money(sub_total + tax_amount, "grand_total")
    amount_paid = money(amount_paid, "amount_paid", strict=True)
    if amount_paid < grand_total:
        raise SaleInputError(f"amount_paid không đủ; cần ít nhất {grand_total:.2f}.")
    return {"lines": result_lines, "sub_total": sub_total, "tax_percentage": tax_percentage,
            "tax_amount": tax_amount, "grand_total": grand_total,
            "amount_paid": amount_paid, "amount_change": amount_paid - grand_total}
