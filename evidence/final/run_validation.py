"""FINAL: verify an unchanged checkout with a disposable DB, never shop data."""
import argparse
import json
import os
from pathlib import Path
import secrets
import sqlite3
import subprocess
import sys
from tempfile import TemporaryDirectory


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--repo', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    repo, out = args.repo.resolve(), args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    sha = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repo, text=True).strip()
    assert sha == '123101a85ea74091c2863e0a00f952477918d925'
    commands = []
    with TemporaryDirectory(prefix='final-validation-') as directory:
        env = dict(os.environ, DEBUG='true', SECRET_KEY='test', DB_ENGINE='sqlite',
            DB_NAME=str(Path(directory)/'empty.sqlite3'), DJANGO_ENV_FILE=os.devnull,
            DJANGO_SECURE_SSL='false', PYTHONUTF8='1',
            COVERAGE_FILE=str(out/'coverage_final.data'))

        def run(label, argv, settings=None):
            result = subprocess.run([sys.executable, *argv], cwd=repo, env=settings or env,
                capture_output=True, text=True, encoding='utf-8')
            (out/(label+'.txt')).write_text(result.stdout+result.stderr, encoding='utf-8')
            commands.append({'label': label, 'argv': argv, 'exit_code': result.returncode})
            (out/'commands.json').write_text(json.dumps(commands, indent=2), encoding='utf-8')
            print(label, 'exit', result.returncode, flush=True)
            if result.returncode:
                raise RuntimeError('Validation failed: '+label)

        run('runtime', ['-c', 'import sys,django,sqlite3,coverage; print(sys.version); print("Django",django.get_version()); print("SQLite",sqlite3.sqlite_version); print("coverage",coverage.__version__)'])
        run('check', ['manage.py', 'check'])
        production = dict(env, DEBUG='false', SECRET_KEY=secrets.token_urlsafe(64),
            DJANGO_SECURE_SSL='true', SECURE_HSTS_SECONDS='3600',
            SECURE_HSTS_INCLUDE_SUBDOMAINS='true', SECURE_HSTS_PRELOAD='true',
            ALLOWED_HOSTS='inventory.example.invalid',
            CSRF_TRUSTED_ORIGINS='https://inventory.example.invalid')
        run('check_deploy', ['manage.py', 'check', '--deploy'], production)
        run('migrations_check', ['manage.py', 'makemigrations', '--check', '--dry-run'])
        run('migration_plan', ['manage.py', 'migrate', '--plan'])
        run('migrate_empty', ['manage.py', 'migrate', '--noinput'])
        run('showmigrations', ['manage.py', 'showmigrations', '--plan'])
        for command in ('check_decimal_data', 'check_vnd_data', 'reconcile_stock'):
            run(command, ['manage.py', command])
        run('coverage_suite_sqlite', ['-W', 'error::DeprecationWarning', '-W', 'error::PendingDeprecationWarning',
            '-m', 'coverage', 'run', '--source=store,accounts,transactions,invoice,bills',
            '--omit=*/tests/*,*/tests.py,*/migrations/*', 'manage.py', 'test', '.', '-v', '2'])
        run('coverage_report', ['-m', 'coverage', 'report', '-m'])
        run('coverage_json', ['-m', 'coverage', 'json', '-o', str(out/'coverage_final.json')])
        (out/'validation_metadata.json').write_text(json.dumps({
            'source_sha': sha, 'database': 'disposable SQLite, removed after run',
            'coverage_source': ['store', 'accounts', 'transactions', 'invoice', 'bills'],
            'coverage_omit': ['*/tests/*', '*/tests.py', '*/migrations/*'],
            'production_check': {'DEBUG': False, 'SSL': True, 'HSTS': 3600,
                'include_subdomains': True, 'preload': True, 'secret_saved': False},
            'real_database_modified': False}, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
