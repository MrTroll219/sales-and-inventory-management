"""HC03 browser evidence on a fresh ../sim-hc03 worktree database only."""
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

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "evidence" / "hc03" / "sau"
BASE = "http://127.0.0.1:8004"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--worktree", type=Path, required=True)
    worktree = parser.parse_args().worktree.resolve()
    if worktree == ROOT or worktree.name != "sim-hc03" or (worktree / "db.sqlite3").exists():
        raise RuntimeError("Use a new disposable sim-hc03 worktree database")
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=worktree, text=True).strip()
    env = dict(os.environ, SECRET_KEY="test", PYTHONUTF8="1")
    OUT.mkdir(parents=True, exist_ok=True)

    def manage(*args):
        return subprocess.check_output([sys.executable, "manage.py", *args], cwd=worktree,
                                       env=env, text=True, encoding="utf-8")

    def snapshot():
        result = manage("shell", "-c", "import json; from store.models import Item; "
                        "from transactions.models import Sale,SaleDetail; print(json.dumps({"
                        "'stock':Item.objects.get(pk=1).quantity,"
                        "'sales':list(Sale.objects.values('id','sub_total','tax_amount','grand_total','amount_change')),"
                        "'details':list(SaleDetail.objects.values('sale_id','price','quantity','total_detail'))},default=str))")
        return json.loads(result.strip().splitlines()[-1])

    (OUT / "migrate.txt").write_text(manage("migrate"), encoding="utf-8")
    manage("shell", "-c", f"exec(open({str(ROOT / 'scripts' / 'p0b_seed.py')!r},encoding='utf-8').read())")
    manage("shell", "-c", "from accounts.models import Customer,Vendor; from store.models import Item; "
           "from transactions.models import Purchase; from decimal import Decimal; "
           "Purchase.objects.create(item=Item.objects.get(pk=1),vendor=Vendor.objects.get(pk=1),"
           "quantity=5,price=Decimal('5.00')); Customer.objects.create(first_name='Khach thieu ho',last_name=None)")
    records = []
    with (OUT / "server.txt").open("w", encoding="utf-8") as log:
        process = subprocess.Popen([sys.executable, "-u", "manage.py", "runserver",
                                    "127.0.0.1:8004", "--noreload"], cwd=worktree, env=env,
                                   stdout=log, stderr=log, creationflags=subprocess.CREATE_NO_WINDOW)
        try:
            for attempt in range(40):
                try:
                    with urlopen(BASE + "/accounts/login/", timeout=2) as response:
                        if response.status == 200: break
                except OSError:
                    time.sleep(0.25)
            else:
                raise RuntimeError("Demo server did not start")
            with sync_playwright() as pw:
                browser = pw.chromium.launch()
                context = browser.new_context(viewport={"width": 1366, "height": 900})
                page = context.new_page()
                page_errors = []
                page.on("pageerror", lambda error: page_errors.append(str(error)))

                def visit(path):
                    return page.goto(BASE + path, wait_until="load").status

                def panel(target, title, response):
                    target.evaluate("""({title,response})=>{
                        document.querySelector('#hc03-response')?.remove();
                        const p=document.createElement('pre');p.id='hc03-response';
                        p.style.cssText='position:relative;z-index:2147483646;margin:16px;padding:16px;border:2px solid #a33;background:#fff7e8;color:#111;font:17px monospace;white-space:pre-wrap';
                        p.textContent=title+'\\n'+JSON.stringify(response,null,2);document.body.prepend(p);
                    }""", {"title":title,"response":response})

                def capture(target, filename, scenario, http, response=None):
                    stamp = datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).isoformat(timespec="seconds")
                    target.evaluate("""label=>{
                        document.querySelector('#hc03-banner')?.remove();
                        const b=document.createElement('div');b.id='hc03-banner';b.textContent=label;
                        b.style.cssText='position:relative;z-index:2147483647;padding:10px;background:#162b49;color:white;font:14px monospace';
                        document.body.prepend(b);
                    }""", f"HC03 {commit[:7]} | {scenario} | {stamp}")
                    target.screenshot(path=str(OUT / filename), full_page=True)
                    records.append(dict(image=filename,scenario=scenario,http=http,response=response,
                                        database=snapshot(),url=target.url,timestamp=stamp))
                    print(filename,http,records[-1]["database"],flush=True)

                def fetch(target, payload):
                    return target.evaluate("""async data=>{
                        const token=document.querySelector('[name="csrfmiddlewaretoken"]').value;
                        const r=await window.fetch('/transactions/new-sale/',{method:'POST',
                          headers:{'Content-Type':'application/json','X-CSRFToken':token,
                          'X-Requested-With':'XMLHttpRequest'},body:JSON.stringify(data)});
                        return {http:r.status,body:await r.json()};
                    }""", payload)

                visit("/accounts/login/")
                page.locator('[name="username"]').fill("demo")
                page.locator('[name="password"]').fill("Demo@12345")
                with page.expect_navigation(wait_until="load"):
                    page.locator('button[type="submit"]').click()
                status = visit("/transactions/new-sale/")
                assert status == 200 and page.get_by_text("Tax (%)",exact=True).count() == 1
                capture(page,"07_hc03_trang_tao_don.png","Trang tạo đơn, thuế cộng thêm",status)

                # Execute the SAME console script as P0b, with actual local fixture IDs.
                before = snapshot()
                messages = []
                page.on("console",lambda message:messages.append(message.text))
                script=(ROOT / "scripts" / "hc03_console.js").read_text(encoding="utf-8")
                page.evaluate(script.replace("<ITEM_ID>","1").replace("<CUSTOMER_ID>","1"))
                status=int(next(m for m in messages if m.startswith("HC03 BEFORE/AFTER HTTP")).split()[-1])
                response=next(json.loads(m) for m in messages if m.startswith('{"status"'))
                assert status==400 and response["status"]=="error" and snapshot()==before
                panel(page,"CÙNG request giả tiền ở P0b | HTTP 400 | DB không đổi",response)
                capture(page,"08_hc03_tong_tien_gia_400.png","Giá 0.01 / tổng 1 bị từ chối",status,response)

                # Actual UI flow verifies Select2, quantity changes, JS tax and submit.
                visit("/transactions/new-sale/")
                page.locator('#customer').select_option("2")  # Customer.last_name=None.
                page.locator('#select2-searchbox_items-container').click()
                page.locator('input.select2-search__field').fill("Nước")
                page.locator('.select2-results__option[role="option"]').filter(has_text="Nước suối").click()
                page.locator('#table_items input[name="quantity"]').fill("2")
                page.locator('#table_items input[name="quantity"]').dispatch_event("change")
                page.locator('#tax_percentage').fill("10")
                page.locator('#tax_percentage').dispatch_event("change")
                assert page.locator('#sub_total').input_value()=="200"
                assert page.locator('#tax_amount').input_value()=="20"
                assert page.locator('#grand_total').input_value()=="220"
                page.locator('#amount_paid').fill("250")
                with page.expect_response(lambda r:r.url.endswith('/transactions/new-sale/')
                                           and r.request.method=='POST') as submitted:
                    page.get_by_role('button',name='Create Sale',exact=True).click()
                response=submitted.value.json()
                assert submitted.value.status==200 and response["status"]=="success",response
                state=snapshot()
                assert state["stock"]==3 and state["sales"][0]["grand_total"]=="220.00"
                status=visit(f"/transactions/sale/{response['sale_id']}/")
                assert "Ksh 220.00" in page.locator('.body-ticket').inner_text()
                capture(page,"09_hc03_chi_tiet_don_dung.png","2×100=200; thuế10%=20; tổng220",status,response)

                anonymous=browser.new_context(viewport={"width":1366,"height":900})
                anon=anonymous.new_page()
                redirect=anonymous.request.get(BASE+'/transactions/new-sale/',max_redirects=0)
                assert redirect.status==302
                anon.goto(BASE+'/transactions/new-sale/',wait_until="load")  # Login page gives CSRF.
                assert '/login/' in anon.url and not any(c['name']=='sessionid' for c in anonymous.cookies())
                valid={"customer":1,"amount_paid":200,"items":[{"id":1,"price":100,"quantity":2,"total_item":200}],
                       "sub_total":200,"grand_total":200,"tax_percentage":0,"amount_change":0}
                before=snapshot();result=fetch(anon,valid)
                assert result['http']==401 and result['body']['status']=='error' and snapshot()==before
                panel(anon,"KHÔNG đăng nhập | GET302 → login | AJAX401 | DB không đổi",result)
                capture(anon,"10_hc03_chua_dang_nhap_401.png","Anonymous bị chặn, có CSRF hợp lệ",401,result)

                visit('/transactions/new-sale/')
                negative=json.loads(json.dumps(valid));negative['items'][0]['quantity']=-3
                before=snapshot();result=fetch(page,negative)
                assert result['http']==400 and result['body']['status']=='error' and snapshot()==before
                panel(page,"Số lượng -3 | HTTP400 | DB không đổi",result)
                capture(page,"11_hc03_so_luong_am_400.png","Số lượng âm bị từ chối",400,result)
                browser.close()
            (OUT / 'observations.json').write_text(json.dumps({'commit':commit,'records':records,
                'page_errors':page_errors},ensure_ascii=False,indent=2),encoding='utf-8')
            lines=["# HC03 - Bằng chứng trước/sau","",f"Commit ứng dụng: `{commit}`.",
                   "Ban đầu: Item.price=100, tồn5; database demo riêng, không dùng dữ liệu thật.",
                   "", "| Ảnh sau (sau/) | Kịch bản | Trước P0b | Sau HC03 |",
                   "|---|---|---|---|"]
            before_text=['Trang tạo đơn, nhãn Tax Inclusive','HTTP200/success, lưu tổng1',
                         'Đơn giả tiền có tổng1','Anonymous tạo đơn success','HTTP500 do CHECK quantity']
            for record,old in zip(records,before_text):
                lines.append(f"| [{record['image']}](sau/{record['image']}) | {record['scenario']} | {old} | HTTP{record['http']} |")
            lines += ["", "- Ảnh07–10 đối chiếu với evidence/truoc/07–10; ảnh11 bổ sung số lượng âm.",
                      "- Ảnh08 chạy nguyên scripts/hc03_console.js, chỉ thay ID; nhận HTTP400, không tạo đơn/trừ kho.",
                      "- Đơn hợp lệ được tạo bằng UI thật: chọn sản phẩm, quantity2, tax10%, trả250; JS hiển thị200/20/220; DB lưu tiền thừa30, tồn5→3.",
                      "- Khách đơn hợp lệ có last_name=None; trang và chọn khách hoạt động.",
                      "- Anonymous GET trang tạo đơn trả302 sang login; lấy CSRF từ form login để POST AJAX, nhận401, DB không đổi.",
                      "- Quantity=-3 trả400, DB không đổi. Snapshot trong sau/observations.json.",
                      "- Panel chỉ hiển thị phản hồi HTTP thật; không sửa giá trị nghiệp vụ trên trang.",
                      "- Múi giờ banner UTC+7; ứng dụng vẫn UTC. Server tự dừng; worktree demo được dọn sau kiểm tra."]
            (ROOT / 'evidence' / 'hc03' / 'BANG_CHUNG_SAU.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
        finally:
            process.terminate();process.wait(timeout=15)


if __name__=='__main__':
    main()
