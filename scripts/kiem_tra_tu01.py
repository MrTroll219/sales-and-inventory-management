"""TU01 evidence: isolated empty/demo DB upgrades and three browser pages.

Run with tu01-venv python; requires fresh sim-tu01-truoc / sim-tu01-sau worktrees.
No command below reads or migrates the primary repository database.
"""
import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from urllib.request import urlopen
from zoneinfo import ZoneInfo

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "evidence" / "tu01"
BOOTSTRAP = """
import os,sys
os.environ.setdefault('DJANGO_SETTINGS_MODULE','InventoryMS.settings')
from django.conf import settings
settings.DATABASES={'default':{'ENGINE':'django.db.backends.sqlite3','NAME':sys.argv[1]}}
from django.core.management import execute_from_command_line
execute_from_command_line(['manage.py']+sys.argv[2:])
"""
SNAPSHOT = """
import json
from accounts.models import Profile,Customer,Vendor
from store.models import Item,Category
from transactions.models import Purchase,Sale,SaleDetail
result={}
for model,fields in [(Profile,['id','email','first_name','last_name']),
 (Item,['id','name','quantity','price']),(Purchase,['id','quantity','total_value']),
 (Sale,['id','sub_total','tax_amount','grand_total','amount_change']),
 (SaleDetail,['id','quantity','price','total_detail']),
 (Customer,['id','first_name','last_name']),(Vendor,['id','name']),(Category,['id','name'])]:
 result[model.__name__]=list(model.objects.order_by('pk').values(*fields))
print(json.dumps(result,default=str))
"""
SEED_BUSINESS = """
import json
from decimal import Decimal
from accounts.models import Profile,Vendor
from store.models import Item
from transactions.models import Purchase
from transactions.views import SaleCreateView
from django.contrib.auth import get_user_model
from django.test import RequestFactory
Profile.objects.filter(user__username='demo').update(email='demo@example.invalid',first_name='Demo',last_name='User')
Purchase.objects.create(item=Item.objects.get(pk=1),vendor=Vendor.objects.get(pk=1),quantity=10,price=Decimal('5.00'))
request=RequestFactory().post('/transactions/new-sale/',data=json.dumps({'customer':1,'tax_percentage':10,
 'amount_paid':250,'items':[{'id':1,'quantity':2}]}),content_type='application/json',HTTP_X_REQUESTED_WITH='XMLHttpRequest')
request.user=get_user_model().objects.get(username='demo')
response=SaleCreateView(request)
assert response.status_code==200,response.content
"""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--before-python", type=Path, required=True)
    args = parser.parse_args()
    before = (ROOT.parent / "sim-tu01-truoc").resolve()
    after = (ROOT.parent / "sim-tu01-sau").resolve()
    for folder, name in ((before, "sim-tu01-truoc"), (after, "sim-tu01-sau")):
        if folder == ROOT or folder.name != name or not folder.is_dir():
            raise RuntimeError("Expected isolated TU01 worktrees")
    legacy = before / "legacy.sqlite3"
    upgraded = after / "demo.sqlite3"
    empty = after / "db.sqlite3"
    if any(p.exists() for p in (legacy, upgraded, empty)):
        raise RuntimeError("Use fresh demo databases, not existing data")
    env = dict(os.environ, SECRET_KEY="test", PYTHONUTF8="1")
    (OUT / "migration").mkdir(parents=True, exist_ok=True)
    (OUT / "sau").mkdir(exist_ok=True)

    def command(python, folder, database, *commands):
        return [str(python), "-u", "-c", BOOTSTRAP, str(database), *commands]

    def run(python, folder, database, label, *commands):
        result = subprocess.run(command(python, folder, database, *commands), cwd=folder,
                                env=env, capture_output=True, text=True, encoding="utf-8")
        (OUT / "migration" / (label + ".txt")).write_text(result.stdout + result.stderr, encoding="utf-8")
        if result.returncode:
            raise RuntimeError(f"{label}: exit {result.returncode}; see evidence log")
        return result.stdout

    def seed(python, folder, database, label):
        source = ROOT / "scripts" / "p0b_seed.py"
        run(python, folder, database, label + "_seed", "shell", "-c",
            f"exec(open({str(source)!r},encoding='utf-8').read())")
        run(python, folder, database, label + "_business", "shell", "-c", SEED_BUSINESS)

    def snapshot(python, folder, database, label):
        text = run(python, folder, database, label, "shell", "-c", SNAPSHOT)
        return json.loads(text.strip().splitlines()[-1])

    run(args.before_python, before, legacy, "demo_51_migrate", "migrate", "--noinput")
    seed(args.before_python, before, legacy, "demo_51")
    old = snapshot(args.before_python, before, legacy, "demo_before")
    shutil.copy2(legacy, upgraded)
    run(sys.executable, after, upgraded, "demo_preflight", "check_profile_data")
    run(sys.executable, after, upgraded, "demo_52_migrate", "migrate", "--noinput")
    new = snapshot(sys.executable, after, upgraded, "demo_after")
    assert old == new, "Demo data changed unexpectedly during migration"
    assert new["Item"][0]["quantity"] == 8 and new["Sale"][0]["grand_total"] == "220.00"

    run(sys.executable, after, empty, "empty_52_migrate", "migrate", "--noinput")
    run(sys.executable, after, empty, "empty_preflight", "check_profile_data")
    empty_state = snapshot(sys.executable, after, empty, "empty_after")
    assert all(not rows for rows in empty_state.values())
    summary = {"demo_migrate": "PASS", "demo_data_unchanged": old == new,
               "empty_migrate": "PASS", "empty_tables": all(not r for r in empty_state.values()),
               "counts": {model: len(rows) for model, rows in new.items()},
               "sample_item": new["Item"][0], "sample_sale": new["Sale"][0]}
    (OUT / "migration_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print("MIGRATION", json.dumps(summary, ensure_ascii=False), flush=True)

    # The empty-db migration has been proven; populate only this disposable DB for UI.
    seed(sys.executable, after, empty, "ui_52")
    run(sys.executable, after, empty, "ui_collectstatic", "collectstatic", "--noinput")
    manifest = json.loads((after / "staticfiles/staticfiles.json").read_text(encoding="utf-8"))
    assert manifest["paths"]
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=after, text=True).strip()
    base = "http://127.0.0.1:8005"
    records = []
    with (OUT / "sau" / "server.txt").open("w", encoding="utf-8") as log:
        process = subprocess.Popen(command(sys.executable, after, empty, "runserver", "127.0.0.1:8005", "--noreload"),
                                   cwd=after, env=env, stdout=log, stderr=log,
                                   creationflags=subprocess.CREATE_NO_WINDOW)
        try:
            for attempt in range(40):
                try:
                    with urlopen(base + "/accounts/login/", timeout=2) as response:
                        if response.status == 200: break
                except OSError:
                    time.sleep(0.25)
            else:
                raise RuntimeError("Demo server not ready")
            with sync_playwright() as pw:
                browser = pw.chromium.launch()
                page = browser.new_page(viewport={"width": 1366, "height": 900})
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.goto(base + "/accounts/login/", wait_until="load")
                page.locator('[name="username"]').fill("demo")
                page.locator('[name="password"]').fill("Demo@12345")
                with page.expect_navigation(wait_until="load"):
                    page.locator('button[type="submit"]').click()
                for path, image, title in [("/", "01_dashboard.png", "Dashboard"),
                    ("/transactions/new-sale/", "02_tao_don_ban.png", "Tạo đơn bán"),
                    ("/transactions/purchases/", "03_danh_sach_phieu_nhap.png", "Danh sách phiếu nhập")]:
                    response = page.goto(base + path, wait_until="load")
                    assert response.status == 200
                    # Let Chart.js finish its initial animation before capturing.
                    page.wait_for_timeout(1500)
                    stamp = datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).isoformat(timespec="seconds")
                    page.evaluate("""label=>{const b=document.createElement('div');b.textContent=label;
                      b.style.cssText='position:relative;z-index:2147483647;padding:10px;background:#162b49;color:white;font:14px monospace';
                      document.body.prepend(b);} """, f"TU01 Django 5.2.19 | {commit[:7]} | {title} | {stamp}")
                    page.screenshot(path=str(OUT / "sau" / image), full_page=True)
                    records.append({"image": image, "url": page.url, "http": response.status, "timestamp": stamp})
                    print(image, response.status, flush=True)
                browser.close()
            (OUT / "sau" / "observations.json").write_text(json.dumps({"commit":commit,"django":"5.2.19",
                "pages":records,"page_errors":errors},ensure_ascii=False,indent=2),encoding="utf-8")
        finally:
            process.terminate()
            process.wait(timeout=15)


if __name__ == "__main__":
    main()
