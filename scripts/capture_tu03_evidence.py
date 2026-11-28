"""TU03: visual/Excel proof using an isolated SQLite DB, never the shop database."""
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
    args=parser.parse_args()
    repo=args.repo.resolve(); out=args.out.resolve(); out.mkdir(parents=True,exist_ok=True)
    if not (repo/'manage.py').is_file(): raise RuntimeError('Not a Django checkout')
    commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip()
    with TemporaryDirectory(prefix='tu03-evidence-') as folder:
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
u=get_user_model().objects.create_user(username='tu03-evidence',is_staff=True,is_superuser=True)
c=Category.objects.create(name='Dữ liệu thử TU03')
v=Vendor.objects.create(name='Nhà cung cấp thử')
i=save_item(dict(name='Sản phẩm thử',description='TU03 evidence',category=c,vendor=v,price=33333,quantity=10))
p=create_purchase(dict(item=i,vendor=v,price=1000,quantity=2))
customer=Customer.objects.create(first_name='Khách',last_name='thử')
s=create_sale(customer.pk,[dict(id=i.pk,quantity=3)],10,110000,u)
stamp=datetime(2026,1,1,17,30,tzinfo=timezone.utc)
Sale.objects.filter(pk=s.pk).update(date_added=stamp)
Purchase.objects.filter(pk=p.pk).update(order_date=stamp)
client=Client(); client.force_login(u)
print(json.dumps(dict(sale_id=s.pk,purchase_id=p.pk,session=client.cookies['sessionid'].value)))
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
                response=page.goto(base+f"/transactions/sale/{seed['sale_id']}/",wait_until='domcontentloaded')
                if response.status!=200: raise RuntimeError(f'Receipt HTTP{response.status}')
                page.evaluate("label => {let d=document.createElement('div');d.textContent=label;d.style='background:#fff3cd;padding:12px;font:16px sans-serif';document.getElementById('wrapper').prepend(d)}",'TU03 | '+out.name+' | '+commit)
                page.screenshot(path=str(out/'sale_detail.png'),full_page=True)
                (out/'sale_detail.txt').write_text(page.locator('body').inner_text(),encoding='utf-8')
                sheets={}
                for name in ('sales','purchases'):
                    response=context.request.get(base+f'/transactions/{name}/export/')
                    if response.status!=200: raise RuntimeError(f'{name} Excel HTTP{response.status}')
                    content=response.body(); (out/f'{name}.xlsx').write_bytes(content)
                    workbook=load_workbook(BytesIO(content)); sheet=workbook.active
                    sheets[name]=[dict(cell=c.coordinate,value=c.value.isoformat() if isinstance(c.value,datetime) else c.value,
                                      number_format=c.number_format) for row in sheet.iter_rows() for c in row]
                    workbook.close()
                (out/'excel_cells.json').write_text(json.dumps(dict(commit=commit,files=sheets),ensure_ascii=False,indent=2),encoding='utf-8')
                browser.close()
        finally:
            process.terminate(); process.wait(timeout=10); server_log.close()


if __name__=='__main__': main()
