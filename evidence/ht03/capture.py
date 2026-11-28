"""HT03: visual/Excel proof using an isolated SQLite DB, never the shop database."""
import argparse
from datetime import datetime
from io import BytesIO
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import time
from urllib.request import urlopen
from openpyxl import load_workbook
from playwright.sync_api import sync_playwright


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--repo',required=True,type=Path)
    parser.add_argument('--out',required=True,type=Path)
    parser.add_argument('--port',required=True,type=int)
    parser.add_argument('--mode',choices=['before','after'],required=True)
    args=parser.parse_args()
    repo=args.repo.resolve(); out=args.out.resolve(); out.mkdir(parents=True,exist_ok=True)
    if not (repo/'manage.py').is_file(): raise RuntimeError('Not a Django checkout')
    commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip()
    with TemporaryDirectory(prefix='ht03-evidence-') as folder:
        env=dict(os.environ,DEBUG='true',SECRET_KEY='test',DB_ENGINE='sqlite',
            DB_NAME=str(Path(folder)/'proof.sqlite3'),DJANGO_ENV_FILE=os.devnull,
            DJANGO_SECURE_SSL='false',ALLOWED_HOSTS='127.0.0.1,localhost',
            MEDIA_ROOT=str(Path(folder)/'media'),PYTHONUTF8='1')
        def manage(label,*argv):
            result=subprocess.run([sys.executable,'manage.py',*argv],cwd=repo,env=env,
                text=True,encoding='utf-8',capture_output=True)
            if label!='seed': (out/f'{label}.txt').write_text(result.stdout+result.stderr,encoding='utf-8')
            if result.returncode: raise RuntimeError(f'{label} failed: {result.stderr}')
            return result.stdout
        manage('migrate','migrate','--noinput')
        manage('collectstatic','collectstatic','--noinput')
        code="""
import json
from datetime import datetime,timezone
from django.contrib.auth import get_user_model
from django.test import Client
from store.models import Category
from django.conf import settings
from scripts.seed_default_media import seed_default_media
seed_default_media(settings.MEDIA_ROOT)
from accounts.models import Customer,Vendor
from transactions.models import Sale
from transactions.services.stock import save_item
from transactions.services.sales import create_sale
from transactions.services.purchases import create_purchase
u=get_user_model().objects.create_user(username='ht03-evidence',is_staff=True,is_superuser=True)
c=Category.objects.create(name='HT03 thử')
v=Vendor.objects.create(name='Nhà cung cấp thử')
a=save_item(dict(name='Sản phẩm A',description='HT03',category=c,vendor=v,price=1000,quantity=0,min_stock_level=8))
b=save_item(dict(name='Sản phẩm B',description='HT03',category=c,vendor=v,price=2000,quantity=0,min_stock_level=7))
for i in (a,b):create_purchase(dict(item=i,vendor=v,price=i.price,quantity=10))
customer=Customer.objects.create(first_name='Khách thử',last_name='HT03')
sale=create_sale(customer.pk,[dict(id=a.pk,quantity=2),dict(id=b.pk,quantity=3)],0,8000,u)
Sale.objects.filter(pk=sale.pk).update(date_added=datetime(2026,1,1,17,30,tzinfo=timezone.utc))
client=Client(); client.force_login(u)
print(json.dumps(dict(session=client.cookies['sessionid'].value,sale_id=sale.pk)))
"""
        seed=json.loads(manage('seed','shell','-c',code).splitlines()[-1])
        server_log=(out/'server.txt').open('w',encoding='utf-8')
        process=subprocess.Popen([sys.executable,'manage.py','runserver',f'127.0.0.1:{args.port}','--noreload'],
            cwd=repo,env=env,stdout=server_log,stderr=subprocess.STDOUT,
            creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        base=f'http://127.0.0.1:{args.port}'
        try:
            for attempt in range(60):
                try:
                    with urlopen(base+'/accounts/login/',timeout=1) as r:
                        if r.status==200: break
                except Exception: time.sleep(.25)
            else: raise RuntimeError('Server did not start')
            with sync_playwright() as pw:
                browser=pw.chromium.launch()
                context=browser.new_context(viewport={'width':1366,'height':900})
                # Offline capture: local assets only; external CDN failures cannot hide requests.
                context.route('**/*',lambda route: route.continue_() if route.request.url.startswith(base) else route.abort())
                context.add_cookies([dict(name='sessionid',value=seed['session'],url=base)])
                page=context.new_page()
                url=base+f"/transactions/sale/{seed['sale_id']}/"
                response=page.goto(url,wait_until='domcontentloaded')
                assert response.status==200
                page.screenshot(path=str(out/'sale_detail_before_cancel.png'),full_page=True)
                (out/'sale_detail_before_cancel.txt').write_text(page.locator('body').inner_text(),encoding='utf-8')
                page.goto(base+'/transactions/sales/',wait_until='domcontentloaded')
                page.screenshot(path=str(out/'sale_list_before_cancel.png'),full_page=True)
                if args.mode=='after':
                    page.goto(url,wait_until='domcontentloaded')
                    page.locator('#cancel-sale').click()
                    page.wait_for_url(base+f"/transactions/sale/{seed['sale_id']}/cancel/")
                    page.locator('textarea[name=reason]').wait_for(state='visible')
                    page.screenshot(path=str(out/'cancel_form.png'),full_page=True)
                    page.locator('textarea[name=reason]').fill('Khách đổi nhu cầu HT03')
                    page.get_by_role('button',name='Xác nhận hủy đơn',exact=True).click()
                    page.wait_for_url(url)
                    assert page.locator('#sale-status-panel').inner_text().find('Khách đổi nhu cầu HT03')>=0
                    assert page.locator('#cancel-sale').count()==0
                    page.screenshot(path=str(out/'sale_detail_cancelled.png'),full_page=True)
                    (out/'sale_detail_cancelled.txt').write_text(page.locator('body').inner_text(),encoding='utf-8')
                    page.goto(base+'/transactions/sales/?status=CANCELLED',wait_until='domcontentloaded')
                    assert page.locator('tbody tr').count()==1
                    assert page.locator('#filter-summary').inner_text()=='Số giao dịch: 1 — Tổng tiền: 0 ₫'
                    page.screenshot(path=str(out/'sale_list_cancelled.png'),full_page=True)
                    response=context.request.get(base+'/transactions/sales/export/?status=CANCELLED')
                    assert response.status==200
                    content=response.body();(out/'cancelled_sales.xlsx').write_bytes(content)
                    book=load_workbook(BytesIO(content));sheet=book.active
                    assert sheet.cell(2,10).value=='Đã hủy'
                    cells=[dict(cell=c.coordinate,value=c.value.isoformat() if isinstance(c.value,datetime) else c.value,number_format=c.number_format) for row in sheet.iter_rows() for c in row]
                    (out/'excel_cells.json').write_text(json.dumps(cells,ensure_ascii=False,indent=2),encoding='utf-8');book.close()
                    manage('reconcile_stock','reconcile_stock')
                snapshot_code="""
import json
from store.models import Item
from transactions.models import Sale,StockMovement
from django.apps import apps
s=Sale.objects.get(pk=SALE_ID)
try:
    model=apps.get_model('transactions','SaleCancellation')
    history=list(model.objects.values('sale_reference','reason','cancelled_by__username','restored_items'))
except LookupError:
    history=[]
print(json.dumps(dict(status=getattr(s,'status',None),items=list(Item.objects.order_by('pk').values('id','name','quantity')),history=history,cancel_movements=list(StockMovement.objects.filter(reason='SALE_CANCEL').values('item_id','delta','ref_id'))),ensure_ascii=False))
""".replace('SALE_ID',str(seed['sale_id']))
                snapshot=json.loads(manage('snapshot_raw','shell','-c',snapshot_code).splitlines()[-1])
                assert [r['quantity'] for r in snapshot['items']]==([10,10] if args.mode=='after' else [8,7])
                (out/'snapshot.json').write_text(json.dumps(snapshot,ensure_ascii=False,indent=2),encoding='utf-8')
                (out/'capture.json').write_text(json.dumps(dict(commit=commit,url=url,http_status=200,mode=args.mode,external_requests='blocked',database='isolated temporary SQLite'),indent=2),encoding='utf-8')
                browser.close()
        finally:
            process.terminate(); process.wait(timeout=10); server_log.close()


if __name__=='__main__': main()
