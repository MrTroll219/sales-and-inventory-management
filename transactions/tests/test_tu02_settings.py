"""TU02 configuration checks run isolated from ambient .env and real databases."""
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from scripts.container_healthcheck import main as probe_health
from scripts.seed_default_media import seed_default_media

ROOT = Path(__file__).resolve().parents[2]
TEST_KEY = "TU02-test-only-0123456789-ABCDEFGHIJKLMNOPQRSTUVWXYZ-abcdefghijk"
INSPECT = """
import json,sys
sys.argv=['manage.py',sys.argv[1]]
from InventoryMS import settings as s
print(json.dumps({'debug':s.DEBUG,'hosts':s.ALLOWED_HOSTS,'origins':s.CSRF_TRUSTED_ORIGINS,
 'db':s.DATABASES['default'],'media':str(s.MEDIA_ROOT),'testing':s.TESTING,
 'storage':s.STORAGES,'ssl':s.SECURE_SSL_REDIRECT,'session_secure':s.SESSION_COOKIE_SECURE,
 'csrf_secure':s.CSRF_COOKIE_SECURE,'hsts':s.SECURE_HSTS_SECONDS,'proxy':s.SECURE_PROXY_SSL_HEADER,
 'subdomains':s.SECURE_HSTS_INCLUDE_SUBDOMAINS,'preload':s.SECURE_HSTS_PRELOAD},default=str))
"""


class DeploymentSettingsTests(SimpleTestCase):
    def environment(self, changes):
        env = {key: value for key, value in os.environ.items()
               if key not in ('SECRET_KEY', 'DEBUG', 'ALLOWED_HOSTS', 'CSRF_TRUSTED_ORIGINS', 'MEDIA_ROOT')
               and not key.startswith(('DB_', 'AZURE_POSTGRESQL_', 'DJANGO_', 'SECURE_'))}
        env.update(SECRET_KEY=TEST_KEY, DJANGO_ENV_FILE=os.devnull, PYTHONUTF8='1')
        for key, value in changes.items():
            if value is None: env.pop(key, None)
            else: env[key] = str(value)
        return env

    def inspect(self, changes=None, command='test', ok=True):
        result = subprocess.run([sys.executable, '-c', INSPECT, command], cwd=ROOT,
                                env=self.environment(changes or {}), capture_output=True,
                                text=True, encoding='utf-8')
        if not ok:
            self.assertNotEqual(result.returncode, 0)
            return result.stderr
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_debug_defaults_false_and_local_sqlite_remains_available(self):
        data = self.inspect()
        self.assertFalse(data['debug'])
        self.assertEqual(data['db']['ENGINE'], 'django.db.backends.sqlite3')
        self.assertEqual(data['hosts'], ['localhost', '127.0.0.1', '[::1]'])

    def test_missing_secret_is_rejected(self):
        self.assertIn('SECRET_KEY is required', self.inspect({'SECRET_KEY': None}, ok=False))

    def test_short_or_weak_production_secret_is_rejected(self):
        for key in ('test', 'x' * 80, 'django-insecure-' + TEST_KEY):
            with self.subTest(key_type=len(key)):
                self.assertIn('SECRET_KEY must contain', self.inspect({'SECRET_KEY': key}, ok=False))

    def test_debug_true_allows_explicit_development_key(self):
        self.assertTrue(self.inspect({'DEBUG': 'true', 'SECRET_KEY': 'dev-only'})['debug'])

    def test_dotenv_is_loaded_without_overriding_process_environment(self):
        with TemporaryDirectory() as folder:
            file = Path(folder) / '.env'
            file.write_text(f'SECRET_KEY={TEST_KEY}\nALLOWED_HOSTS=from-file.invalid\nDEBUG=false\n', encoding='utf-8')
            data = self.inspect({'DJANGO_ENV_FILE': file, 'SECRET_KEY': None})
            self.assertEqual(data['hosts'], ['from-file.invalid'])
            data = self.inspect({'DJANGO_ENV_FILE': file, 'ALLOWED_HOSTS': 'process.invalid'})
            self.assertEqual(data['hosts'], ['process.invalid'])

    def test_generic_database_variables_override_azure_variables(self):
        data = self.inspect({'DB_ENGINE': 'postgresql', 'DB_NAME': 'generic', 'DB_USER': 'generic-user',
            'DB_PASSWORD': 'test-only-password', 'DB_HOST': 'db', 'DB_PORT': '5544',
            'AZURE_POSTGRESQL_DATABASE': 'legacy', 'AZURE_POSTGRESQL_USERNAME': 'old-user',
            'AZURE_POSTGRESQL_PASSWORD': 'old-test-password', 'AZURE_POSTGRESQL_HOST': 'azure.invalid'})
        self.assertEqual(data['db'], {'ENGINE': 'django.db.backends.postgresql', 'NAME': 'generic',
            'USER': 'generic-user', 'PASSWORD': 'test-only-password', 'HOST': 'db', 'PORT': '5544'})

    def test_azure_only_configuration_and_partial_generic_override_work(self):
        changes = {'AZURE_POSTGRESQL_DATABASE': 'legacy', 'AZURE_POSTGRESQL_USERNAME': 'legacy-user',
                   'AZURE_POSTGRESQL_PASSWORD': 'legacy-test-password', 'AZURE_POSTGRESQL_HOST': 'azure.invalid'}
        self.assertEqual(self.inspect(changes)['db']['NAME'], 'legacy')
        self.assertEqual(self.inspect(dict(changes, DB_USER='new-user'))['db']['USER'], 'new-user')
        self.assertEqual(self.inspect(dict(changes, DB_ENGINE='sqlite'))['db']['ENGINE'], 'django.db.backends.sqlite3')

    def test_missing_postgres_fields_and_invalid_engine_are_rejected(self):
        self.assertIn('requires DB_NAME', self.inspect({'DB_ENGINE': 'postgresql'}, ok=False))
        self.assertIn('DB_ENGINE must', self.inspect({'DB_ENGINE': 'unknown'}, ok=False))

    def test_hosts_origins_and_media_are_environment_driven(self):
        data = self.inspect({'ALLOWED_HOSTS': ' example.invalid, localhost, ',
                             'CSRF_TRUSTED_ORIGINS': ' https://example.invalid, ',
                             'MEDIA_ROOT': '/custom/media'})
        self.assertEqual(data['hosts'], ['example.invalid', 'localhost'])
        self.assertEqual(data['origins'], ['https://example.invalid'])
        self.assertEqual(data['media'].replace('\\', '/'), '/custom/media')

    def test_ssl_true_sets_https_cookie_hsts_and_proxy_flags(self):
        data = self.inspect({'DJANGO_SECURE_SSL': 'true'})
        self.assertTrue(data['ssl'] and data['session_secure'] and data['csrf_secure'])
        self.assertEqual(data['hsts'], 3600)
        self.assertEqual(data['proxy'], ['HTTP_X_FORWARDED_PROTO', 'https'])
        self.assertEqual(self.inspect({'DJANGO_SECURE_SSL': 'true', 'SECURE_HSTS_SECONDS': '31536000'})['hsts'], 31536000)

    def test_http_lab_disables_https_specific_flags(self):
        data = self.inspect({'DJANGO_SECURE_SSL': 'false'})
        self.assertFalse(data['ssl'] or data['session_secure'] or data['csrf_secure'])
        self.assertEqual(data['hsts'], 0)
        self.assertIsNone(data['proxy'])

    def test_invalid_boolean_or_negative_hsts_is_rejected(self):
        self.assertIn('DEBUG must', self.inspect({'DEBUG': 'nonsense'}, ok=False))
        for value in ('-1', 'bad'):
            with self.subTest(value=value):
                self.assertIn('SECURE_HSTS_SECONDS', self.inspect({'DJANGO_SECURE_SSL': 'true', 'SECURE_HSTS_SECONDS': value}, ok=False))

    def test_test_storage_is_plain_and_production_storage_is_manifest(self):
        self.assertEqual(self.inspect(command='test')['storage']['staticfiles']['BACKEND'],
                         'django.contrib.staticfiles.storage.StaticFilesStorage')
        self.assertEqual(self.inspect(command='collectstatic')['storage']['staticfiles']['BACKEND'],
                         'whitenoise.storage.CompressedManifestStaticFilesStorage')

    def test_production_deploy_check_has_zero_issues(self):
        env = self.environment({'DJANGO_SECURE_SSL': 'true', 'ALLOWED_HOSTS': 'example.invalid',
            'CSRF_TRUSTED_ORIGINS': 'https://example.invalid', 'SECURE_HSTS_INCLUDE_SUBDOMAINS': 'true',
            'SECURE_HSTS_PRELOAD': 'true'})
        result = subprocess.run([sys.executable, 'manage.py', 'check', '--deploy'], cwd=ROOT,
                                env=env, capture_output=True, text=True, encoding='utf-8')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('System check identified no issues', result.stdout + result.stderr)


class ContainerHealthTests(SimpleTestCase):
    def probe(self, secure):
        response = MagicMock()
        response.__enter__.return_value.status = 200
        with patch.dict(os.environ, {'ALLOWED_HOSTS': 'example.invalid,localhost', 'DJANGO_SECURE_SSL': secure}):
            with patch('scripts.container_healthcheck.urlopen', return_value=response) as opener:
                probe_health()
                return opener.call_args.args[0]

    def test_health_probe_uses_allowed_host_in_http_lab(self):
        request = self.probe('false')
        self.assertEqual(request.get_header('Host'), 'example.invalid')
        self.assertIsNone(request.get_header('X-forwarded-proto'))

    def test_health_probe_supplies_https_proxy_header_when_configured(self):
        request = self.probe('true')
        self.assertEqual(request.get_header('X-forwarded-proto'), 'https')


class DefaultMediaTests(SimpleTestCase):
    def test_missing_default_is_seeded_as_valid_jpeg(self):
        from PIL import Image
        with TemporaryDirectory() as folder:
            seed_default_media(folder)
            target = Path(folder, 'profile_pics/default.jpg')
            self.assertEqual(target.read_bytes(), (ROOT / 'static/images/profile_pics/default.jpg').read_bytes())
            with Image.open(target) as image:
                self.assertEqual(image.format, 'JPEG')
                image.verify()

    def test_existing_default_is_never_overwritten(self):
        with TemporaryDirectory() as folder:
            target = Path(folder, 'profile_pics/default.jpg')
            target.parent.mkdir()
            target.write_bytes(b'existing-user-file')
            seed_default_media(folder)
            self.assertEqual(target.read_bytes(), b'existing-user-file')

    def test_local_django_media_is_served_only_when_debug_true(self):
        code = """
import django
django.setup()
from django.test import Client
response=Client().get('/images/profile_pics/default.jpg', HTTP_HOST='localhost')
assert response.status_code == EXPECTED, response.status_code
if EXPECTED == 200:
    from pathlib import Path
    assert b''.join(response.streaming_content) == Path('static/images/profile_pics/default.jpg').read_bytes()
"""
        with TemporaryDirectory() as folder:
            seed_default_media(folder)
            for debug, expected in [('true', 200), ('false', 404)]:
                with self.subTest(debug=debug):
                    env = DeploymentSettingsTests().environment({'DEBUG': debug, 'MEDIA_ROOT': folder,
                        'DJANGO_SETTINGS_MODULE': 'InventoryMS.settings'})
                    result = subprocess.run([sys.executable, '-c', code.replace('EXPECTED', str(expected))],
                        cwd=ROOT, env=env, capture_output=True, text=True, encoding='utf-8')
                    self.assertEqual(result.returncode, 0, result.stderr)
