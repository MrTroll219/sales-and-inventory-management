"""TU02: disposable GitHub CI Compose proof, never targets an existing .env."""
from pathlib import Path
import os
import secrets
import subprocess
from urllib.request import urlopen

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'reports' / 'compose'


def main():
    if os.environ.get('GITHUB_ACTIONS') != 'true':
        raise RuntimeError('This destructive disposable smoke test runs only in GitHub Actions')
    if (ROOT / '.env').exists():
        raise RuntimeError('Refusing to overwrite an existing .env')
    OUT.mkdir(parents=True, exist_ok=True)
    env = (ROOT / '.env.example').read_text(encoding='utf-8')
    env = env.replace('SECRET_KEY=\n', f'SECRET_KEY={secrets.token_urlsafe(64)}\n')
    env = env.replace('DB_PASSWORD=\n', f'DB_PASSWORD={secrets.token_urlsafe(32)}\n')
    (ROOT / '.env').write_text(env, encoding='utf-8')

    def run(label, *args):
        result = subprocess.run(['docker', 'compose', *args], cwd=ROOT,
                                capture_output=True, text=True)
        (OUT / f'{label}.txt').write_text(result.stdout + result.stderr, encoding='utf-8')
        print(label, 'exit', result.returncode, flush=True)
        if result.returncode:
            raise RuntimeError(f'{label} failed; see uploaded report')
        return result.stdout

    try:
        run('config', 'config', '--quiet')
        run('build_up', 'up', '-d', '--build', '--wait', '--wait-timeout', '180')
        run('ps_before', 'ps')
        run('nginx_config', 'exec', '-T', 'nginx', 'nginx', '-t')
        with urlopen('http://127.0.0.1:8000/accounts/login/', timeout=10) as response:
            assert response.status == 200
            assert response.headers.get('Server', '').startswith('nginx/')
            (OUT / 'login_http.txt').write_text('HTTP 200 via nginx\n', encoding='utf-8')
        expected_image = (ROOT / 'static/images/profile_pics/default.jpg').read_bytes()

        def check_image(filename, label):
            with urlopen(f'http://127.0.0.1:8000/images/{filename}', timeout=10) as response:
                assert response.status == 200
                assert response.headers.get_content_type() == 'image/jpeg'
                assert response.read() == expected_image
                assert response.headers.get('Server', '').startswith('nginx/')
                (OUT / f'{label}.txt').write_text(
                    f'HTTP 200 via nginx; Content-Type: image/jpeg; bytes match ({len(expected_image)})\n',
                    encoding='utf-8')

        check_image('profile_pics/default.jpg', 'default_image')
        run('seed_image', 'exec', '-T', 'web', 'python', '-c',
            "from pathlib import Path; import os; "
            "Path(os.environ['MEDIA_ROOT'],'tu02-upload.jpg').write_bytes("
            "Path('static/images/profile_pics/default.jpg').read_bytes())")
        check_image('tu02-upload.jpg', 'media_http_before')
        run('production_check_deploy', 'exec', '-T',
            '-e', 'DJANGO_SECURE_SSL=true', '-e', 'SECURE_HSTS_INCLUDE_SUBDOMAINS=true',
            '-e', 'SECURE_HSTS_PRELOAD=true', 'web', 'python', 'manage.py', 'check', '--deploy')
        # Run Django with SSL=true temporarily: a forwarded HTTPS request must stay 200.
        (ROOT / '.env').write_text(env.replace('DJANGO_SECURE_SSL=false', 'DJANGO_SECURE_SSL=true'), encoding='utf-8')
        run('ssl_up', 'up', '-d', '--wait', '--wait-timeout', '180')
        from urllib.request import Request
        with urlopen(Request('http://127.0.0.1:8000/accounts/login/',
                             headers={'X-Forwarded-Proto': 'https'}), timeout=10) as response:
            assert response.status == 200
            assert 'max-age=3600' in response.headers['Strict-Transport-Security']
            (OUT / 'forwarded_https.txt').write_text('HTTP 200; forwarded HTTPS; HSTS max-age=3600\n', encoding='utf-8')
        (ROOT / '.env').write_text(env, encoding='utf-8')
        run('http_lab_up', 'up', '-d', '--wait', '--wait-timeout', '180')
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            page = browser.new_page(viewport={'width': 1366, 'height': 900})
            response = page.goto('http://127.0.0.1:8000/accounts/login/', wait_until='load')
            assert response.status == 200
            page.screenshot(path=str(OUT / 'login.png'), full_page=True)
            browser.close()
        run('seed', 'exec', '-T', 'web', 'python', 'manage.py', 'shell', '-c',
            "from pathlib import Path; from django.conf import settings; "
            "from store.models import Category,Item; "
            "c=Category.objects.create(name='TU02-persistence'); "
            "Item.objects.create(name='TU02-persistence',category=c,quantity=7,price=3); "
            "Path(settings.MEDIA_ROOT,'tu02-proof.txt').write_text('TU02 media persisted'); print('SEEDED')")
        # Intentionally no -v: both named volumes must survive this restart.
        run('down_keep_volumes', 'down')
        run('up_again', 'up', '-d', '--wait', '--wait-timeout', '180')
        run('ps_after', 'ps')
        check_image('tu02-upload.jpg', 'media_http_after')
        check_image('profile_pics/default.jpg', 'default_image_after')
        run('persistence', 'exec', '-T', 'web', 'python', 'manage.py', 'shell', '-c',
            "from pathlib import Path; from django.conf import settings; from store.models import Item; "
            "assert Item.objects.get(name='TU02-persistence').quantity==7; "
            "assert Path(settings.MEDIA_ROOT,'tu02-proof.txt').read_text()=='TU02 media persisted'; "
            "print('DATABASE_AND_MEDIA_PERSISTENCE_PASS')")
    finally:
        run('compose_logs', 'logs', '--no-color', '--tail', '120')


if __name__ == '__main__':
    main()
