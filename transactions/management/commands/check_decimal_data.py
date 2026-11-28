"""DP02: inspect existing data with read-only SQL before any migrations."""
import json
from django.apps import apps
from django.core.management.base import BaseCommand, CommandError
from django.db import connections
from transactions.migrations._dp02_data import audit_data


class Command(BaseCommand):
    help = 'Read-only DP02 preflight: money, quantities and sale identities; never repairs data.'

    def add_arguments(self, parser):
        parser.add_argument('--database', default='default')

    def handle(self, *args, **options):
        connection = connections[options['database']]
        from django.db.migrations.recorder import MigrationRecorder
        if ('transactions', '0006_tu03_vnd') in MigrationRecorder(connection).applied_migrations():
            from transactions.migrations._tu03_data import audit
            report = audit(apps, connection, project=False)
        else:
            report = audit_data(apps, connection)  # Keep the DP02 historical contract intact.
        self.stdout.write(json.dumps(report, ensure_ascii=False, indent=2))
        if not report['safe_to_migrate']:
            raise CommandError('DP02 preflight failed; review listed rows before migrate. No data changed.')
