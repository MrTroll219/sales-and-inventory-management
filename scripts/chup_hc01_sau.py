"""HC01 UI evidence on a disposable worktree, never the main database.

Run with the test venv python and --worktree pointing to ../sim-hc01 at HEAD.
Requires Playwright/Chromium. Server is terminated even if capture fails.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from urllib.request import urlopen
from datetime import datetime
from zoneinfo import ZoneInfo

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "evidence" / "hc01" / "sau"
BASE = "http://127.0.0.1:8002"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--worktree", type=Path, required=True)
    args = parser.parse_args()
    worktree = args.worktree.resolve()
    if worktree == ROOT or worktree.name != "sim-hc01":
        raise RuntimeError("Use a separate sim-hc01 worktree only")
    if (worktree / "db.sqlite3").exists():
        raise RuntimeError("Demo database must be new")
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=worktree, text=True).strip()
    env = dict(os.environ, SECRET_KEY="test", PYTHONUTF8="1")
    OUT.mkdir(parents=True, exist_ok=True)

    def manage(*commands):
        return subprocess.check_output([sys.executable, "manage.py", *commands],
                                       cwd=worktree, env=env, text=True, encoding="utf-8")

    def snapshot():
        result = manage("shell", "-c", "import json; from store.models import Item; "
                        "from transactions.models import Purchase; print(json.dumps({"
                        "'stock':Item.objects.get(pk=1).quantity,"
                        "'purchases':list(Purchase.objects.values('id','quantity','total_value'))},default=str))")
        return json.loads(result.strip().splitlines()[-1])

    (OUT / "migrate.txt").write_text(manage("migrate"), encoding="utf-8")
    manage("shell", "-c", f"exec(open({str(ROOT / 'scripts' / 'p0b_seed.py')!r},encoding='utf-8').read())")
    records = []
    with (OUT / "server.txt").open("w", encoding="utf-8") as log:
        process = subprocess.Popen([sys.executable, "-u", "manage.py", "runserver",
                                    "127.0.0.1:8002", "--noreload"], cwd=worktree,
                                   env=env, stdout=log, stderr=log,
                                   creationflags=subprocess.CREATE_NO_WINDOW)
        try:
            for attempt in range(40):
                try:
                    with urlopen(BASE + "/accounts/login/", timeout=2) as response:
                        if response.status == 200:
                            break
                except OSError:
                    time.sleep(0.25)
            else:
                raise RuntimeError("Demo server not ready")
            with sync_playwright() as pw:
                browser = pw.chromium.launch()
                page = browser.new_page(viewport={"width": 1366, "height": 900})

                def visit(path):
                    return page.goto(BASE + path, wait_until="load").status

                def capture(filename, scenario, http, expected_stock):
                    state = snapshot()
                    assert state["stock"] == expected_stock, state
                    stamp = datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).isoformat(timespec="seconds")
                    page.evaluate("""label=>{
                        document.querySelector('#hc01-banner')?.remove();
                        const b=document.createElement('div');b.id='hc01-banner';b.textContent=label;
                        b.style.cssText='position:relative;z-index:2147483647;padding:10px;background:#162b49;color:white;font:14px monospace';
                        document.body.prepend(b);
                    }""", f"HC01 {commit[:7]} | {scenario} | {stamp}")
                    page.screenshot(path=str(OUT / filename), full_page=True)
                    records.append(dict(image=filename, scenario=scenario, http=http,
                                        url=page.url, database=state, timestamp=stamp))
                    print(filename, http, state, flush=True)

                def submit():
                    with page.expect_navigation(wait_until="load") as response:
                        page.locator('button[type="submit"].btn-primary').click()
                    return response.value.status

                visit("/accounts/login/")
                page.locator('[name="username"]').fill("demo")
                page.locator('[name="password"]').fill("Demo@12345")
                with page.expect_navigation(wait_until="load"):
                    page.locator('button[type="submit"]').click()
                status = visit("/products/")
                capture("01_ton_ban_dau.png", "Tồn ban đầu 0", status, 0)
                visit("/transactions/new-purchase/")
                page.locator('[name="item"]').select_option("1")
                page.locator('[name="vendor"]').select_option("1")
                page.locator('[name="quantity"]').fill("10")
                page.locator('[name="price"]').fill("5")
                page.locator('[name="description"]').fill("HC01 demo")
                page.locator('[name="delivery_date"]').fill("2026-11-24T09:00")
                assert submit() == 200
                status = visit("/products/")
                capture("02_ton_sau_tao.png", "Nhập 10, tồn đúng 10", status, 10)
                visit("/transactions/purchase/1/update/")
                page.locator('[name="description"]').fill("HC01 chỉ sửa mô tả")
                assert submit() == 200
                status = visit("/products/")
                capture("03_ton_sau_sua_mo_ta.png", "Chỉ sửa mô tả, tồn vẫn 10", status, 10)
                visit("/transactions/purchase/1/update/")
                page.locator('[name="quantity"]').fill("15")
                assert submit() == 200
                status = visit("/products/")
                capture("04_ton_sau_tang.png", "Đổi 10→15, tồn đúng 15", status, 15)
                visit("/transactions/purchase/1/update/")
                page.locator('[name="quantity"]').fill("4")
                assert submit() == 200
                status = visit("/products/")
                capture("05_ton_sau_giam.png", "Đổi 15→4, tồn đúng 4", status, 4)
                visit("/transactions/new-sale/")
                result = page.evaluate("""async()=>{
                    const token=document.querySelector('[name="csrfmiddlewaretoken"]').value;
                    const r=await fetch('/transactions/new-sale/',{method:'POST',headers:{
                        'Content-Type':'application/json','X-CSRFToken':token,
                        'X-Requested-With':'XMLHttpRequest'},body:JSON.stringify({customer:1,
                        sub_total:300,grand_total:300,tax_percentage:0,tax_amount:0,
                        amount_paid:300,amount_change:0,items:[{id:1,price:100,quantity:3,total_item:300}]})});
                    return {http:r.status,body:await r.json()};
                }""")
                assert result["http"] == 200 and result["body"]["status"] == "success"
                visit("/transactions/purchase/1/update/")
                page.locator('[name="quantity"]').fill("1")
                status = submit()
                assert status == 200 and "sẽ âm" in page.locator("body").inner_text()
                capture("06_tu_choi_am_kho.png", "Đã bán 3; giảm phiếu 4→1 bị từ chối", status, 1)
                assert snapshot()["purchases"][0]["quantity"] == 4
                status = visit("/products/")
                capture("07_kho_khong_doi_sau_tu_choi.png", "Sau từ chối, tồn vẫn 1", status, 1)
                browser.close()
            (OUT / "observations.json").write_text(json.dumps({"commit":commit,
                "records":records}, ensure_ascii=False, indent=2), encoding="utf-8")
        finally:
            process.terminate()
            process.wait(timeout=15)


if __name__ == "__main__":
    main()
