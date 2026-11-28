import ast
from pathlib import Path
from django.test import SimpleTestCase

ROOT = Path(__file__).resolve().parents[2]


def forbidden_writes(source):
    errors = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, (ast.Assign, ast.AugAssign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                if isinstance(target, ast.Attribute) and target.attr == 'quantity':
                    owner = ast.unparse(target.value).split('.')[-1]
                    if owner in ('item', 'stock', 'product'):
                        errors.append(node.lineno)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr == 'update' and any(k.arg == 'quantity' for k in node.keywords):
                errors.append(node.lineno)
            if node.func.attr == 'create' and 'Item.objects' in ast.unparse(node.func):
                if any(k.arg == 'quantity' for k in node.keywords): errors.append(node.lineno)
            if node.func.attr == 'bulk_update' and any(isinstance(n, ast.Constant) and n.value == 'quantity'
                                                     for n in ast.walk(node)):
                errors.append(node.lineno)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'setattr':
            if len(node.args) > 1 and isinstance(node.args[1], ast.Constant) and node.args[1].value == 'quantity':
                errors.append(node.lineno)
    return errors


class InventoryArchitectureTests(SimpleTestCase):
    def test_only_stock_module_explicitly_writes_item_quantity(self):
        violations = []
        for app in ('store', 'accounts', 'transactions', 'invoice', 'bills', 'InventoryMS'):
            for path in (ROOT / app).rglob('*.py'):
                relative = path.relative_to(ROOT)
                if 'tests' in relative.parts or 'migrations' in relative.parts or path.name == 'tests.py':
                    continue
                if relative.as_posix() == 'transactions/services/stock.py': continue
                for line in forbidden_writes(path.read_text(encoding='utf-8')):
                    violations.append(f'{relative}:{line}')
        self.assertEqual(violations, [])

    def test_architecture_guard_detects_each_supported_bypass(self):
        for source in ('item.quantity = 3', 'stock.quantity += 1',
                       'Item.objects.filter(pk=1).update(quantity=3)',
                       'Item.objects.create(quantity=5)',
                       "Item.objects.bulk_update(items, ['quantity'])", "setattr(item, 'quantity', 2)"):
            with self.subTest(source=source): self.assertTrue(forbidden_writes(source))

    def test_public_mutating_services_are_atomic(self):
        for name in ('stock', 'purchases', 'sales'):
            tree = ast.parse((ROOT / 'transactions/services' / f'{name}.py').read_text(encoding='utf-8'))
            for function in tree.body:
                if isinstance(function, ast.FunctionDef) and not function.name.startswith('_'):
                    with self.subTest(function=function.name):
                        self.assertIn('transaction.atomic', [ast.unparse(d) for d in function.decorator_list])
