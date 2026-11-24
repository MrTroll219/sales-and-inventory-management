"""HC02: run with the test venv on a NEW ../sim-hc02 worktree database."""
import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from urllib.request import urlopen
from zoneinfo import ZoneInfo

from openpyxl import load_workbook
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "evidence" / "hc02" / "sau"
BASE = "http://127.0.0.1:8003"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--worktree", type=Path, required=True)
    worktree = parser.parse_args().worktree.resolve()
    if worktree == ROOT or worktree.name != "sim-hc02" or (worktree / "db.sqlite3").exists():
        raise RuntimeError("Use a fresh sim-hc02 worktree, never the main database")
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=worktree, text=True).strip()
    env = dict(os.environ, SECRET_KEY="test", PYTHONUTF8="1")
    OUT.mkdir(parents=True, exist_ok=True)

    def manage(*args):
        return subprocess.check_output([sys.executable, "manage.py", *args], cwd=worktree,
                                       env=env, text=True, encoding="utf-8")

    def snapshot():
        result = manage("shell", "-c", "import json; from transactions.models import Purchase; "
                        "print(json.dumps(list(Purchase.objects.values('id','description',"
                        "'delivery_date','quantity')),default=str))")
        return json.loads(result.strip().splitlines()[-1])

    (OUT / "migrate.txt").write_text(manage("migrate"), encoding="utf-8")
    manage("shell", "-c", f"exec(open({str(ROOT / 'scripts' / 'p0b_seed.py')!r},encoding='utf-8').read())")
    records = []
    with (OUT / "server.txt").open("w", encoding="utf-8") as log:
        process = subprocess.Popen([sys.executable, "-u", "manage.py", "runserver",
                                    "127.0.0.1:8003", "--noreload"], cwd=worktree, env=env,
                                   stdout=log, stderr=log, creationflags=subprocess.CREATE_NO_WINDOW)
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

                def submit():
                    with page.expect_navigation(wait_until="load") as response:
                        page.locator('button[type="submit"].btn-primary').click()
                    assert response.value.status == 200 and page.url.endswith("/transactions/purchases/")

                def capture(filename, title, http):
                    stamp = datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).isoformat(timespec="seconds")
                    page.evaluate("""label=>{
                        document.querySelector('#hc02-banner')?.remove();
                        const b=document.createElement('div');b.id='hc02-banner';b.textContent=label;
                        b.style.cssText='position:relative;z-index:2147483647;padding:10px;background:#162b49;color:white;font:14px monospace';
                        document.body.prepend(b);
                    }""", f"HC02 {commit[:7]} | {title} | {stamp}")
                    page.screenshot(path=str(OUT / filename), full_page=True)
                    records.append(dict(image=filename, scenario=title, http=http,
                                        url=page.url, timestamp=stamp, database=snapshot()))
                    print(filename, http, records[-1]["database"], flush=True)

                visit("/accounts/login/")
                page.locator('[name="username"]').fill("demo")
                page.locator('[name="password"]').fill("Demo@12345")
                with page.expect_navigation(wait_until="load"):
                    page.locator('button[type="submit"]').click()
                for date in ("2026-11-24T09:00", ""):
                    visit("/transactions/new-purchase/")
                    page.locator('[name="item"]').select_option("1")
                    page.locator('[name="vendor"]').select_option("1")
                    page.locator('[name="quantity"]').fill("10")
                    page.locator('[name="price"]').fill("5")
                    page.locator('[name="description"]').fill("HC02 có ngày" if date else "HC02 thiếu ngày")
                    page.locator('[name="delivery_date"]').fill(date)
                    submit()
                before = snapshot()
                with page.expect_download() as download, page.expect_response(
                    lambda r: r.url.endswith("/transactions/purchases/export/")
                ) as export_response:
                    page.locator('a[href="/transactions/purchases/export/"]').click()
                assert export_response.value.status == 200
                download.value.save_as(str(OUT / "purchases.xlsx"))
                workbook = load_workbook(OUT / "purchases.xlsx")
                sheet = workbook.active
                cells = [list(row) for row in sheet.iter_rows(values_only=True)]
                assert sheet.max_row == 3
                assert cells[1][5] == datetime(2026, 11, 24, 9, 0) and cells[2][5] is None
                formats = {f"{col}{row}": sheet[f"{col}{row}"].number_format
                           for col in ("E", "F") for row in (2, 3)}
                workbook.close()
                preview = {"http": 200, "file": "purchases.xlsx", "data_rows": 2,
                           "E2": str(cells[1][4]), "F2": str(cells[1][5]),
                           "F3": None, "F3_note": "Ô ngày giao rỗng; openpyxl trả None"}
                page.evaluate("""data=>{
                    const panel=document.createElement('pre');panel.id='hc02-export';
                    panel.style.cssText='position:relative;z-index:2147483646;padding:16px;margin:16px;background:#e9fff0;color:#111;border:2px solid green;font:16px monospace;white-space:pre-wrap';
                    panel.textContent='Tải Excel THỰC thành công; kiểm tra file bằng openpyxl\\n'+JSON.stringify(data,null,2);
                    document.body.prepend(panel);
                }""", preview)
                capture("01_xuat_excel_thanh_cong.png", "Excel có phiếu thiếu ngày, HTTP 200", 200)
                visit("/transactions/purchase/1/update/")
                field = page.locator('[name="delivery_date"]')
                assert field.input_value() == "2026-11-24T09:00"
                capture("02_form_hien_dung_ngay_giao.png", "Form giữ ngày 2026-11-24T09:00", 200)
                page.locator('[name="description"]').fill("HC02 chỉ sửa mô tả")
                submit()
                after = snapshot()
                assert before[0]["delivery_date"] == after[0]["delivery_date"] == "2026-11-24 09:00:00+00:00"
                capture("03_sau_luu_ngay_giao_van_con.png", "Chỉ sửa mô tả: ngày giao vẫn còn", 200)
                browser.close()
            output = {"commit":commit,"records":records,"excel_cells":cells,
                      "excel_formats":formats,"date_before":before[0]["delivery_date"],
                      "date_after":after[0]["delivery_date"]}
            (OUT / "observations.json").write_text(json.dumps(output,ensure_ascii=False,
                                                               indent=2,default=str),encoding="utf-8")
            lines = ["# Bằng chứng HC02 sau sửa", "", f"Commit ứng dụng: `{commit}`.",
                     "Múi giờ ứng dụng vẫn UTC; banner ảnh dùng UTC+7.", "",
                     "| Ảnh | Kịch bản | HTTP |", "|---|---|---|"]
            lines += [f"| [{r['image']}]({r['image']}) | {r['scenario']} | {r['http']} |" for r in records]
            lines += ["", "## File Excel tải thật và đọc bằng openpyxl", "",
                      "File: [purchases.xlsx](purchases.xlsx). 1 dòng tiêu đề + 2 dòng dữ liệu.",
                      "", "| Ô | Giá trị đọc được | Định dạng |", "|---|---|---|"]
            for row in (2,3):
                for column,index in (("E",4),("F",5)):
                    value=cells[row-1][index]
                    lines.append(f"| {column}{row} | {value if value is not None else '(rỗng / None)'} | {formats[f'{column}{row}']} |")
            lines += ["", f"Ngày giao DB trước lưu: `{before[0]['delivery_date']}`.",
                      f"Ngày giao DB sau lưu: `{after[0]['delivery_date']}` (giữ nguyên).",
                      "Chỉ sửa description; không điền lại ô ngày, không sửa DOM giá trị form.",
                      "Ảnh 01 thêm panel từ HTTP và các ô đọc trong file tải thật; không dựng dữ liệu giả.",
                      "Script tự dừng server. Worktree/database demo được dọn sau kiểm tra ảnh."]
            (OUT / "BANG_CHUNG_SAU.md").write_text("\n".join(lines)+"\n",encoding="utf-8")
        finally:
            process.terminate()
            process.wait(timeout=15)


if __name__ == "__main__":
    main()
