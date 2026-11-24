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
        with urlopen('http://127.0.0.1:8000/accounts/login/', timeout=10) as response:
            assert response.status == 200
            (OUT / 'login_http.txt').write_text('HTTP 200\n', encoding='utf-8')
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
        run('persistence', 'exec', '-T', 'web', 'python', 'manage.py', 'shell', '-c',
            "from pathlib import Path; from django.conf import settings; from store.models import Item; "
            "assert Item.objects.get(name='TU02-persistence').quantity==7; "
            "assert Path(settings.MEDIA_ROOT,'tu02-proof.txt').read_text()=='TU02 media persisted'; "
            "print('DATABASE_AND_MEDIA_PERSISTENCE_PASS')")
    finally:
        run('compose_logs', 'logs', '--no-color', '--tail', '120')


if __name__ == '__main__':
    main()
