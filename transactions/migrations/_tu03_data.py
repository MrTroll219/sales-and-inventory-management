"""Frozen TU03 conversion policy; do not change with future runtime policies."""
from decimal import Decimal, DecimalException, ROUND_HALF_UP
from ._dp02_data import MONEY, flush_deferred_constraints

MAX = Decimal('999999999999999')


def whole(value):
    return Decimal(str(value)).quantize(Decimal('1'), rounding=ROUND_HALF_UP)


def audit(apps, connection, *, project=True):
    violations = []
    q = connection.ops.quote_name
    with connection.cursor() as cursor:
        tables = set(connection.introspection.table_names(cursor))
        for (app, name), money_fields in MONEY.items():
            model = apps.get_model(app, name)
            if model._meta.db_table not in tables:
                continue
            fields = list(money_fields)
            if name in ('Item', 'Purchase', 'SaleDetail', 'Invoice'): fields.append('quantity')
            if name == 'Sale': fields.append('tax_percentage')
            columns = [model._meta.pk.column] + [model._meta.get_field(f).column for f in fields]
            cursor.execute('SELECT '+', '.join(map(q, columns))+' FROM '+q(model._meta.db_table))
            for row in cursor.fetchall():
                values = {}
                for field, raw in zip(fields, row[1:]):
                    reason = None
                    try:
                        number = Decimal(str(raw))
                        if not number.is_finite(): reason = 'must be finite'
                        elif field == 'quantity':
                            minimum = 1 if name in ('Purchase', 'SaleDetail') else 0
                            if number != number.to_integral_value() or not minimum <= number <= 2147483647:
                                reason = 'quantity must be a whole integer in range; never rounded'
                        elif field == 'tax_percentage':
                            if not 0 <= number <= 100: reason = 'tax percentage outside [0,100]'
                        elif number < 0 or number > MAX or whole(number) > MAX:
                            reason = 'money outside VND range'
                        elif not project and number != whole(number):
                            reason = 'VND money must be integral'
                        if not reason:
                            values[field] = whole(number) if field in money_fields else number
                    except (ValueError, TypeError, DecimalException): reason = 'invalid numeric value'
                    if reason:
                        violations.append(dict(model=f'{app}.{name}', pk=row[0], field=field, value=str(raw), reason=reason))
                if name == 'Sale':
                    for target, left, right, sign in [('grand_total','sub_total','tax_amount',1),
                                                     ('amount_change','amount_paid','grand_total',-1)]:
                        if all(f in values for f in (target,left,right)) and values[target] != values[left]+sign*values[right]:
                            violations.append(dict(model='transactions.Sale', pk=row[0], field=target,
                                reason=f'rounded VND identity conflict: {target} != {left} {"+" if sign==1 else "-"} {right}'))
    return dict(safe_to_migrate=not violations, violations=violations)


def guard(apps, schema_editor):
    import json
    report = audit(apps, schema_editor.connection)
    if not report['safe_to_migrate']:
        raise RuntimeError('TU03 preflight failed; review data, no automatic repair: '+json.dumps(report))


def stage(apps, schema_editor, app_label):
    q = schema_editor.connection.ops.quote_name
    for (app, name), fields in MONEY.items():
        if app != app_label: continue
        model = apps.get_model(app, name)
        with schema_editor.connection.cursor() as cursor:
            cursor.execute('SELECT '+', '.join(map(q, ['id', *fields]))+' FROM '+q(model._meta.db_table))
            rows = cursor.fetchall()
        for pk, *values in rows:
            model.objects.using(schema_editor.connection.alias).filter(pk=pk).update(
                **{f'tu03_{f}': whole(v) for f,v in zip(fields,values)})
    flush_deferred_constraints(schema_editor)


def copy(apps, schema_editor, app_label):
    from django.db.models import F
    for (app,name), fields in MONEY.items():
        if app != app_label: continue
        apps.get_model(app,name).objects.using(schema_editor.connection.alias).update(
            **{f:F(f'tu03_{f}') for f in fields})
    flush_deferred_constraints(schema_editor)
