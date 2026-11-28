"""HT02: visual/Excel proof using an isolated SQLite DB, never the shop database."""
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
    parser.add_argument('--expected',required=True,type=int)
    args=parser.parse_args()
    repo=args.repo.resolve(); out=args.out.resolve(); out.mkdir(parents=True,exist_ok=True)
    if not (repo/'manage.py').is_file(): raise RuntimeError('Not a Django checkout')
    commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip()
    with TemporaryDirectory(prefix='ht02-evidence-') as folder:
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
from transactions.models import Sale,Purchase
from transactions.services.stock import save_item
from transactions.services.sales import create_sale
from transactions.services.purchases import create_purchase
u=get_user_model().objects.create_user(username='ht02-evidence',is_staff=True,is_superuser=True)
c=Category.objects.create(name='Vật tư thử HT02')
v=Vendor.objects.create(name='Nhà cung cấp A')
vb=Vendor.objects.create(name='Nhà cung cấp B')
i=save_item(dict(name='Giấy',description='Dữ liệu thử HT02',category=c,vendor=v,price=1000,quantity=100))
a=Customer.objects.create(first_name='An',last_name='Nguyễn',phone='0901111111')
b=Customer.objects.create(first_name='Bình',phone='0902222222')
stamps=['2026-10-31T16:59:59+00:00','2026-10-31T17:00:00+00:00','2026-11-30T16:59:00+00:00','2026-11-30T17:00:00+00:00','2026-11-15T10:00:00+00:00']
for index,text in enumerate(stamps):
    s=create_sale(a.pk if index in (0,1,2) else b.pk,[dict(id=i.pk,quantity=index+1)],0,1000*(index+1),u)
    p=create_purchase(dict(item=i,vendor=v if index in (0,1,2) else vb,price=1000,quantity=index+1))
    Sale.objects.filter(pk=s.pk).update(date_added=datetime.fromisoformat(text))
    Purchase.objects.filter(pk=p.pk).update(order_date=datetime.fromisoformat(text))
client=Client(); client.force_login(u)
print(json.dumps(dict(session=client.cookies['sessionid'].value,customer=a.pk,vendor=v.pk)))
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
                sheets={}
                captures=[]
                for kind,field in [('sales','customer'),('purchases','vendor')]:
                    query=f"date_from=01%2F11%2F2026&date_to=30%2F11%2F2026&{field}={seed[field]}"
                    url=base+f'/transactions/{kind}/?'+query
                    response=page.goto(url,wait_until='domcontentloaded')
                    assert response.status==200
                    assert page.locator('tbody tr').count()==args.expected
                    page.screenshot(path=str(out/f'{kind}_list.png'),full_page=True)
                    (out/f'{kind}_list.txt').write_text(page.locator('body').inner_text(),encoding='utf-8')
                    if args.expected==2:
                        assert page.locator('#filter-summary').inner_text()=='Số giao dịch: 2 — Tổng tiền: 5.000 ₫'
                        assert page.locator('input[name=date_from]').input_value()=='01/11/2026'
                    response=context.request.get(base+f'/transactions/{kind}/export/?'+query)
                    assert response.status==200
                    content=response.body(); (out/f'{kind}.xlsx').write_bytes(content)
                    book=load_workbook(BytesIO(content)); sheet=book.active
                    assert sheet.max_row-1==args.expected
                    sheets[kind]=[dict(cell=c.coordinate,value=c.value.isoformat() if isinstance(c.value,datetime) else c.value,number_format=c.number_format) for row in sheet.iter_rows() for c in row]
                    book.close()
                    captures.append(dict(url=url,list_rows=args.expected,excel_rows=args.expected,filename=response.headers['content-disposition'],status=200))
                (out/'excel_cells.json').write_text(json.dumps(dict(commit=commit,files=sheets),ensure_ascii=False,indent=2),encoding='utf-8')
                (out/'capture.json').write_text(json.dumps(dict(commit=commit,captures=captures,external_requests='blocked',database='isolated temporary SQLite'),indent=2),encoding='utf-8')
                browser.close()
        finally:
            process.terminate(); process.wait(timeout=10); server_log.close()


if __name__=='__main__': main()
