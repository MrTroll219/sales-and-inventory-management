"""Frozen DP02 data rules. Keep stable: migrations and read-only preflight use it."""
from decimal import Decimal, DecimalException, ROUND_HALF_UP

CENT = Decimal('0.01')
MAX_MONEY = Decimal('9999999999999.99')
MONEY = {
    ('store', 'Item'): ('price',),
    ('invoice', 'Invoice'): ('price_per_item', 'shipping', 'total', 'grand_total'),
    ('bills', 'Bill'): ('amount',),
    ('transactions', 'Purchase'): ('price', 'total_value'),
    ('transactions', 'Sale'): ('sub_total', 'tax_amount', 'grand_total', 'amount_paid', 'amount_change'),
    ('transactions', 'SaleDetail'): ('price', 'total_detail'),
}
FLOATS = {
    'store': {'Item': ('price',)},
    'invoice': {'Invoice': ('price_per_item', 'shipping', 'total', 'grand_total')},
    'bills': {'Bill': ('amount',)},
    'transactions': {'Sale': ('tax_percentage',)},
}


def cents(value):
    return Decimal(str(value)).quantize(CENT, rounding=ROUND_HALF_UP)


def audit_data(apps, connection):
    """Use raw SELECTs: avoid DecimalField conversion hiding legacy precision."""
    violations = []
    quote = connection.ops.quote_name
    with connection.cursor() as cursor:
        tables = set(connection.introspection.table_names(cursor))
        for (app, name), money_fields in MONEY.items():
            model = apps.get_model(app, name)
            if model._meta.db_table not in tables:
                continue
            fields = list(money_fields)
            if name in ('Item', 'Purchase', 'SaleDetail', 'Invoice'):
                fields.append('quantity')
            if name == 'Sale':
                fields.append('tax_percentage')
            columns = [model._meta.pk.column] + [model._meta.get_field(f).column for f in fields]
            cursor.execute('SELECT ' + ', '.join(map(quote, columns)) + ' FROM ' + quote(model._meta.db_table))
            for row in cursor.fetchall():
                values = {}
                for field, raw in zip(fields, row[1:]):
                    reason = None
                    try:
                        number = Decimal(str(raw))
                        if not number.is_finite():
                            reason = 'must be finite'
                        elif field == 'quantity':
                            minimum = 1 if name in ('Purchase', 'SaleDetail') else 0
                            if number != number.to_integral_value() or not minimum <= number <= 2147483647:
                                reason = f'must be a whole integer in [{minimum}, 2147483647]; no automatic rounding'
                        elif field == 'tax_percentage':
                            if not 0 <= number <= 100:
                                reason = 'must be between 0 and 100'
                        elif number < 0 or number > MAX_MONEY:
                            reason = f'must be between 0 and {MAX_MONEY}'
                        if not reason:
                            values[field] = cents(raw) if field != 'quantity' else number
                    except (DecimalException, ValueError, TypeError):
                        reason = 'invalid numeric value'
                    if reason:
                        violations.append({'model': f'{app}.{name}', 'pk': row[0], 'field': field,
                                           'value': str(raw), 'reason': reason})
                if name == 'Sale':
                    for target, left, right, sign in (
                        ('grand_total', 'sub_total', 'tax_amount', 1),
                        ('amount_change', 'amount_paid', 'grand_total', -1),
                    ):
                        if all(f in values for f in (target, left, right)):
                            if values[target] != values[left] + sign * values[right]:
                                violations.append({'model': 'transactions.Sale', 'pk': row[0],
                                    'field': target, 'value': str(values[target]),
                                    'reason': f'must equal {left} {"+" if sign == 1 else "-"} {right} after cent conversion'})
    return {'safe_to_migrate': not violations, 'violations': violations}


def assert_clean(apps, schema_editor):
    report = audit_data(apps, schema_editor.connection)
    if not report['safe_to_migrate']:
        import json
        raise RuntimeError('DP02 preflight failed; fix approved data before retrying; no automatic rounding of quantity. '
                           + json.dumps(report, ensure_ascii=False))


def stage_float_values(apps, schema_editor, app_label):
    """Stage Decimal(str(float)), HALF_UP in real Decimal shadow columns."""
    quote = schema_editor.connection.ops.quote_name
    for name, fields in FLOATS[app_label].items():
        model = apps.get_model(app_label, name)
        columns = [model._meta.pk.column] + [model._meta.get_field(f).column for f in fields]
        with schema_editor.connection.cursor() as cursor:
            cursor.execute('SELECT ' + ', '.join(map(quote, columns)) + ' FROM ' + quote(model._meta.db_table))
            rows = cursor.fetchall()
        for pk, *values in rows:
            model.objects.using(schema_editor.connection.alias).filter(pk=pk).update(
                **{f'dp02_{field}': cents(value) for field, value in zip(fields, values)})
    flush_deferred_constraints(schema_editor)


def copy_staged_values(apps, schema_editor, app_label):
    from django.db.models import F
    for name, fields in FLOATS[app_label].items():
        model = apps.get_model(app_label, name)
        model.objects.using(schema_editor.connection.alias).update(
            **{field: F(f'dp02_{field}') for field in fields})
    flush_deferred_constraints(schema_editor)


def flush_deferred_constraints(schema_editor):
    # Validate queued FK events before the following ALTER/DROP COLUMN, keeping
    # the whole migration atomic. This validates constraints; it never disables them.
    if schema_editor.connection.vendor == 'postgresql':
        with schema_editor.connection.cursor() as cursor:
            cursor.execute('SET CONSTRAINTS ALL IMMEDIATE')
