import json
from django.apps import apps
from django.core.management.base import BaseCommand, CommandError
from django.db import connections
from django.db.migrations.recorder import MigrationRecorder
from transactions.migrations._tu03_data import audit


class Command(BaseCommand):
    help = 'Read-only TU03 preflight; no exchange rate and no data repair.'

    def add_arguments(self, parser):
        parser.add_argument('--database', default='default')

    def handle(self, *args, **options):
        connection = connections[options['database']]
        applied = MigrationRecorder(connection).applied_migrations()
        report = audit(apps, connection, project=('transactions','0006_tu03_vnd') not in applied)
        self.stdout.write(json.dumps(report, ensure_ascii=False, indent=2))
        if not report['safe_to_migrate']:
            raise CommandError('TU03 preflight failed; no data changed.')
