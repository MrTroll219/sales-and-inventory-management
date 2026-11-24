"""P0b: capture actual v0-goc UI. Does not modify application code.

Requires a freshly seeded isolated worktree with runserver on localhost:8001.
PowerShell: $env:BASE_URL='http://127.0.0.1:8001'
Set PLAYWRIGHT_BROWSERS_PATH when using a custom browser download directory.
Run using the worktree venv python. Output goes to evidence/truoc/.
"""
import json
import os
from datetime import datetime
from pathlib import Path
import subprocess
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
WORKTREE = Path(os.environ.get("P0B_WORKTREE", ROOT.parent / "sim-v0-goc"))
PYTHON = WORKTREE / "venv" / "Scripts" / "python.exe"
OUT = ROOT / "evidence" / "truoc"
BASE = os.environ.get("BASE_URL", "http://127.0.0.1:8001").rstrip("/")
COMMIT = "038cbd5a7e3f4bdfab96f7f9d61016d1d2ea2dc4"
records = []


def snapshot():
    """Read database values separately to corroborate screenshots and responses."""
    code = (
        "import json; from store.models import Item; "
        "from transactions.models import Sale,SaleDetail,Purchase; "
        "from accounts.models import Customer,Vendor; "
        "print(json.dumps({'items':list(Item.objects.values('id','quantity','price')),"
        "'purchases':list(Purchase.objects.values('id','quantity','description','delivery_date')),"
        "'sales':list(Sale.objects.values('id','grand_total','sub_total')),"
        "'details':list(SaleDetail.objects.values('sale_id','quantity','price')),"
        "'customer_id':Customer.objects.get(first_name='Khach').pk,"
        "'vendor_id':Vendor.objects.get(name='NCC A').pk},default=str))"
    )
    result = subprocess.run([str(PYTHON), "manage.py", "shell", "-c", code],
                            cwd=WORKTREE, capture_output=True, text=True,
                            encoding="utf-8", check=True)
    return json.loads(result.stdout.strip().splitlines()[-1])


def visit(page, path):
    response = page.goto(BASE + path, wait_until="load")
    return response.status


def capture(page, filename, hc, scenario, expected, actual, http):
    stamp = datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).isoformat(timespec="seconds")
    # Evidence annotations only; never change application data or page values.
    page.evaluate("""label => {
        document.querySelector('#p0b-banner')?.remove();
        const banner = document.createElement('div');
        banner.id='p0b-banner'; banner.textContent=label;
        banner.style.cssText='position:relative;z-index:2147483647;padding:10px;'
          +'background:#162b49;color:white;font:14px monospace;';
        document.body.prepend(banner);
    }""", f"v0-goc {COMMIT[:7]} | {hc} | {stamp}")
    page.screenshot(path=str(OUT / filename), full_page=True)
    records.append(dict(image=filename, hc=hc, scenario=scenario, expected=expected,
                        actual=actual, http=http, timestamp=stamp, url=page.url,
                        database=snapshot()))
    print(f"{filename}: HTTP {http}; {actual}", flush=True)
    (OUT / "observations.json").write_text(
        json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")


def show_response(page, title, response):
    page.evaluate("""({title,response}) => {
        document.querySelector('#p0b-response')?.remove();
        const panel=document.createElement('pre'); panel.id='p0b-response';
        panel.style.cssText='position:relative;z-index:2147483646;'
          +'margin:16px;padding:18px;border:3px solid #b52828;'
          +'background:#fff8e8;color:#111;font:18px monospace;white-space:pre-wrap;';
        panel.textContent=title+'\\n'+JSON.stringify(response,null,2);
        document.body.prepend(panel);
    }""", {"title": title, "response": response})


def fill_purchase(page, ids, dated=True):
    visit(page, "/transactions/new-purchase/")
    page.locator('[name="item"]').select_option(str(ids["item_id"]))
    page.locator('[name="vendor"]').select_option(str(ids["vendor_id"]))
    page.locator('[name="price"]').fill("5")
    page.locator('[name="quantity"]').fill("10")
    page.locator('[name="description"]').fill("P0b có ngày giao" if dated else "P0b không ngày giao")
    page.locator('[name="delivery_date"]').fill("2026-11-24T09:00" if dated else "")
    page.locator('[name="delivery_status"]').select_option("P")


def submit_purchase(page):
    with page.expect_navigation(wait_until="load") as nav:
        page.locator('button[type="submit"].btn-primary').click()
    assert nav.value.status == 200 and page.url.endswith("/transactions/purchases/"), page.url


def stock_on_page(page):
    row = page.locator("tbody tr").filter(has_text="Nước suối")
    return int(row.locator("td").nth(2).inner_text())


def write_index(browser_version):
    lines = ["# Bằng chứng trước bảo trì (P0b)", "",
             f"- Mã ứng dụng: `{COMMIT}`, tag `v0-goc`.",
             f"- Chromium: `{browser_version}`; viewport 1366×900; full_page=True.",
             "- Thời gian trên ảnh: Asia/Ho_Chi_Minh (UTC+7).",
             "- Chỉ chèn dải định danh và phản hồi HTTP thực nhận; không sửa giá trị giao diện.",
             "- Database demo độc lập; không phải dữ liệu repository chính.", "",
             "| Ảnh | Kịch bản | Mong đợi | Thực tế | HTTP |",
             "|---|---|---|---|---|"]
    for r in records:
        lines.append(f"| [{r['image']}]({r['image']}) | {r['scenario']} | {r['expected']} | {r['actual']} | {r['http']} |")
    lines += ["", "## Diễn giải", "",
              "- HC01: khởi đầu 0; tạo phiếu 10 → 20; chỉ sửa mô tả → 30.",
              "- HC02: phiếu thứ hai quantity=10, ngày giao trống; kho tăng từ 30 lên 50 do lỗi baseline.",
              "- HC03: Item.price=100; gửi đơn 2 sản phẩm tổng giả 1; DB lưu tổng 1.00, giá dòng 0.01, kho 50→48.",
              "- Chưa đăng nhập: context mới không có sessionid; gửi request hợp lệ, có CSRF; HTTP 200/success, kho 48→46.",
              "- Mã HTTP của ảnh 02 là GET form; các ảnh danh sách sau lưu là GET cuối sau redirect.",
              "- Ảnh 06 là trang debug thật trả 500; ảnh 08/10 thêm panel từ phản hồi thực nhận.",
              "- `observations.json` lưu snapshot DB đọc sau mỗi ảnh để đối chứng.",
              "- Phát hiện thêm: khi chỉ sửa mô tả phiếu 1, input datetime-local của form gốc không giữ ngày giao; sau lưu delivery_date từ 2026-11-24 09:00 UTC thành None. Không sửa hay can thiệp form để vượt lỗi này. Vì vậy cả hai phiếu ở ảnh 05 đều hiện None; lỗi xuất Excel gặp ngay phiếu 1.",
              "- Chưa có bằng chứng sau sửa; HC01 và các yêu cầu khác chưa thực hiện."]
    (OUT / "BANG_CHUNG_TRUOC.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    if urlparse(BASE).hostname not in ("127.0.0.1", "localhost", "::1"):
        raise RuntimeError("P0b is restricted to localhost disposable demo")
    current = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=WORKTREE, text=True).strip()
    if current != COMMIT:
        raise RuntimeError("Worktree must be the exact baseline commit")
    initial = snapshot()
    if initial["purchases"] or initial["sales"] or initial["items"][0]["quantity"] != 0:
        raise RuntimeError("Freshly seed a NEW demo database before taking evidence")
    ids = {"item_id": initial["items"][0]["id"], "vendor_id": initial["vendor_id"],
           "customer_id": initial["customer_id"]}
    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        context = browser.new_context(viewport={"width": 1366, "height": 900}, locale="en-US")
        page = context.new_page()
        page.set_default_navigation_timeout(60000)
        try:
            visit(page, "/accounts/login/")
            page.locator('[name="username"]').fill("demo")
            page.locator('[name="password"]').fill("Demo@12345")
            with page.expect_navigation(wait_until="load"):
                page.locator('button[type="submit"]').click()
            status = visit(page, "/products/")
            assert stock_on_page(page) == 0
            capture(page, "01_hc01_ton_ban_dau.png", "HC01", "Tồn ban đầu", "0", "0", status)
            fill_purchase(page, ids)
            capture(page, "02_hc01_tao_phieu_nhap.png", "HC01", "Điền phiếu nhập", "10 sản phẩm, giá nhập 5", "Form đã điền, chưa lưu", 200)
            submit_purchase(page)
            status = visit(page, "/products/")
            assert stock_on_page(page) == 20
            capture(page, "03_hc01_ton_sau_tao.png", "HC01", "Tạo phiếu nhập 10", "Kho 10", "Kho 20", status)
            purchase_id = snapshot()["purchases"][0]["id"]
            visit(page, f"/transactions/purchase/{purchase_id}/update/")
            page.locator('[name="description"]').fill("P0b chỉ sửa mô tả")
            submit_purchase(page)
            status = visit(page, "/products/")
            assert stock_on_page(page) == 30
            capture(page, "04_hc01_ton_sau_sua_mo_ta.png", "HC01", "Chỉ sửa mô tả", "Kho vẫn 10", "Kho 30", status)
            fill_purchase(page, ids, dated=False)
            submit_purchase(page)
            status = visit(page, "/transactions/purchases/")
            capture(page, "05_hc02_phieu_khong_ngay_giao.png", "HC02", "Phiếu thứ hai để trống ngày giao", "Ngày giao rỗng", "Ngày giao None", status)
            status = visit(page, "/transactions/purchases/export/")
            assert status == 500 and "AttributeError" in page.locator("body").inner_text()
            capture(page, "06_hc02_loi_500_xuat_excel.png", "HC02", "Xuất Excel thiếu ngày giao", "HTTP 200, ô ngày rỗng", "AttributeError: NoneType has no attribute tzinfo", status)
            status = visit(page, "/transactions/new-sale/")
            capture(page, "07_hc03_trang_tao_don.png", "HC03", "Mở trang tạo đơn", "Form tạo đơn", "Form tạo đơn", status)
            logs = []
            page.on("console", lambda message: logs.append(message.text))
            script = (ROOT / "scripts" / "hc03_console.js").read_text(encoding="utf-8")
            script = script.replace("<ITEM_ID>", str(ids["item_id"])).replace("<CUSTOMER_ID>", str(ids["customer_id"]))
            page.evaluate(script)
            http_line = next(line for line in logs if line.startswith("HC03 BEFORE/AFTER HTTP"))
            sale_http = int(http_line.split()[-1])
            sale_response = next(json.loads(line) for line in logs if line.startswith('{"status"'))
            assert sale_http == 200 and sale_response["status"] == "success"
            show_response(page, f"Phản hồi THỰC từ request giả tiền | HTTP {sale_http}", sale_response)
            capture(page, "08_hc03_phan_hoi_success.png", "HC03", "Gửi giá 0.01, tổng 1 cho 2 sản phẩm giá 100", "HTTP 400, không tạo đơn", "HTTP 200, success", sale_http)
            sale = snapshot()["sales"][-1]
            assert sale["grand_total"] == "1.00"
            status = visit(page, f"/transactions/sale/{sale['id']}/")
            assert page.locator(".body-ticket").get_by_text("Ksh 1.00", exact=True).count() > 0
            capture(page, "09_hc03_chi_tiet_don_sai.png", "HC03", "Chi tiết đơn giả tiền", "Tổng đúng 200.00", "Grand Total Ksh 1.00", status)
            anonymous = browser.new_context(viewport={"width": 1366, "height": 900})
            anon_page = anonymous.new_page()
            visit(anon_page, "/transactions/new-sale/")
            assert not any(c["name"] == "sessionid" for c in anonymous.cookies())
            result = anon_page.evaluate("""async ids => {
                const token = document.querySelector('[name="csrfmiddlewaretoken"]').value;
                const response = await fetch('/transactions/new-sale/', {
                  method:'POST', credentials:'same-origin',
                  headers:{'Content-Type':'application/json','X-CSRFToken':token,
                           'X-Requested-With':'XMLHttpRequest'},
                  body:JSON.stringify({customer:ids.customer_id,sub_total:200,
                    grand_total:200,tax_amount:0,tax_percentage:0,amount_paid:200,
                    amount_change:0,items:[{id:ids.item_id,price:100,quantity:2,total_item:200}]})
                });
                return {http:response.status,body:await response.json()};
            }""", ids)
            assert result["http"] == 200 and result["body"]["status"] == "success"
            show_response(anon_page, "Context KHÔNG đăng nhập, không sessionid | Phản hồi THỰC", result)
            capture(anon_page, "10_hc03_chua_dang_nhap.png", "HC03", "Tạo đơn không đăng nhập (có CSRF)", "Redirect/401/403, không tạo đơn", "HTTP 200, success", result["http"])
            write_index(browser.version)
            print(f"Chromium {browser.version}; captured {len(records)} screenshots", flush=True)
        except Exception:
            # Preserve any unexpected UI error without altering application code.
            page.screenshot(path=str(OUT / "unexpected_ui_state.png"), full_page=True)
            raise
        finally:
            browser.close()


if __name__ == "__main__":
    main()
