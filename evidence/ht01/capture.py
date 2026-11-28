"""HT01: visual/Excel proof using an isolated SQLite DB, never the shop database."""
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
    with TemporaryDirectory(prefix='ht01-evidence-') as folder:
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
from transactions.services.stock import save_item
u=get_user_model().objects.create_user(username='ht01-evidence',is_staff=True,is_superuser=True)
c=Category.objects.create(name='Vật tư văn phòng')
v=Vendor.objects.create(name='NCC Bình Minh')
for name,qty,level in [('Giấy A4',3,5),('Bút bi',5,5),('Sổ tay',6,5),('Tắt cảnh báo',0,0),('Mực máy in',1,10)]:
    save_item(dict(name=name,description='Dữ liệu thử HT01',category=c,vendor=v,price=1000,quantity=qty,min_stock_level=level))
client=Client(); client.force_login(u)
print(json.dumps(dict(session=client.cookies['sessionid'].value)))
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
                response=page.goto(base+'/products/low-stock/',wait_until='domcontentloaded')
                assert response.status==200
                assert page.locator('tbody tr[data-item-id]').count()==3
                page.screenshot(path=str(out/'low_stock_list.png'),full_page=True)
                (out/'low_stock_list.txt').write_text(page.locator('body').inner_text(),encoding='utf-8')
                response=page.goto(base+'/',wait_until='domcontentloaded')
                assert response.status==200
                card=page.locator('#low-stock-card')
                assert card.inner_text()=='Cần nhập hàng: 3'
                card.screenshot(path=str(out/'dashboard_card.png'))
                page.screenshot(path=str(out/'dashboard.png'),full_page=True)
                response=context.request.get(base+'/products/low-stock/export/')
                assert response.status==200
                content=response.body(); (out/'low_stock.xlsx').write_bytes(content)
                book=load_workbook(BytesIO(content))
                sheets={sheet.title:[dict(cell=c.coordinate,value=c.value.isoformat() if isinstance(c.value,datetime) else c.value,number_format=c.number_format) for row in sheet.iter_rows() for c in row] for sheet in book}
                book.close()
                (out/'excel_cells.json').write_text(json.dumps(dict(commit=commit,files=sheets),ensure_ascii=False,indent=2),encoding='utf-8')
                (out/'capture.json').write_text(json.dumps(dict(commit=commit,urls=[base+'/products/low-stock/',base+'/'],http_status=200,count=3,external_requests='blocked',database='isolated temporary SQLite'),indent=2),encoding='utf-8')
                browser.close()
        finally:
            process.terminate(); process.wait(timeout=10); server_log.close()


if __name__=='__main__': main()
