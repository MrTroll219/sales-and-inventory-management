# Môi trường vận hành và kiểm thử

Nội dung cho mục **4.4 - Môi trường vận hành và kiểm thử** của Kế hoạch bảo trì.
Ngày kiểm chứng: 24/11/2026; múi giờ bằng chứng Asia/Ho_Chi_Minh (UTC+7).

## Môi trường thực tế đã chạy

| Thành phần | Giá trị đã kiểm tra |
|---|---|
| Hệ điều hành | Windows 11, kernel 10.0.26300; DisplayVersion 26H2; build 26300.9974; EditionID CoreSingleLanguage |
| Python | CPython 3.12.10, 64 bit |
| Django | 5.1, giữ nguyên requirements.txt của baseline |
| SQLite | 3.49.1, database file mới trong worktree dùng chụp UI; in-memory khi chạy test |
| Playwright | 1.65.2, Python package |
| Trình duyệt | Chromium 159.0.8154.6 (Playwright build v1255), headless |
| Viewport / ảnh | 1366×900; full_page=True; ảnh debug có thể dài hơn 900 px |
| HTTP demo | http://127.0.0.1:8001; chỉ localhost; đã dừng sau khi chụp |
| Commit gốc | 038cbd5a7e3f4bdfab96f7f9d61016d1d2ea2dc4 |
| Tag baseline | v0-goc, trỏ nguyên commit gốc |

Windows được nhận diện bằng `platform.platform()` / `platform.win32_ver()` và
registry `HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion`.
Registry ProductName vẫn trả chuỗi Windows 10 Home Single Language; vì vậy ghi
thêm phiên bản kernel/build và kết quả Python nhận diện Windows 11, không chỉ dựa
vào tên sản phẩm trong registry. CIM không truy cập được trong sandbox.

## Các gói chính (pip freeze rút gọn)

```text
Django==5.1
django-autoslug==1.9.9
django-crispy-forms==2.3
django-extensions==3.2.3
django-filter==24.3
django-imagekit==5.0.0
django-phonenumber-field==8.0.0
django-tables2==2.7.0
crispy-bootstrap5==2024.2
openpyxl==3.1.5
playwright==1.65.2
pillow==13.0.0
gunicorn==23.0.0
psycopg2-binary==2.9.11
python-dotenv==1.2.1
whitenoise==6.11.0
tzdata==2026.6
```

Playwright chỉ cài trong venv dành cho bằng chứng; không thêm vào requirements.txt
của ứng dụng. Có psycopg2 không có nghĩa đã kiểm thử với PostgreSQL.
Dockerfile gốc dùng `python:3.10.12-alpine`, CI gốc dùng Python 3.10.
Nhóm đang kiểm thử trên Python 3.12; Python 3.10 và PostgreSQL sẽ kiểm ở TU01/TU02.

## Cách ly dữ liệu và quy ước quản lý cấu hình

- `p0-bang-chung`: test và bằng chứng trước bảo trì (P0, P0b).
- `bao-tri`: nhánh tích hợp, khởi đầu cùng commit P0b.
- `<ma>-<mo-ta>`: nhánh từng yêu cầu; `hc01-ton-kho-phieu-nhap` được tạo từ bao-tri,
  chưa có commit sửa HC01.
- `upstream`: repository gốc munuhee, chỉ dùng đọc; không push.
- `origin`: fork của người dùng sau khi gh đăng nhập và xác minh chủ sở hữu.
- Không mở PR trong P0b. Actions của fork phải tắt trước khi push các nhánh.
- Worktree `../sim-v0-goc` có mã ứng dụng nguyên bản, venv riêng, db.sqlite3 riêng.
  Không dùng db.sqlite3 của repository chính. Worktree tạm được xóa sau khi lưu ảnh.
- Tài khoản demo `demo / Demo@12345` chỉ tồn tại trong database demo bị xóa khi
  dọn worktree; không phải tài khoản triển khai.

## Tái tạo bằng chứng từ PowerShell

Các lệnh dưới chạy từ thư mục repository chính. Thực hiện lại sẽ tạo database demo
mới; không tái sử dụng worktree có dữ liệu nghiệp vụ. Thay đường dẫn Python 3.12
theo máy. Không tạo hoặc sửa `.env` trong repository chính.

```powershell
git worktree add ..\sim-v0-goc v0-goc
& 'C:\Users\ADMIN\AppData\Local\Python\pythoncore-3.12-64\python.exe' -m venv ..\sim-v0-goc\venv
$p0bPython = (Resolve-Path ..\sim-v0-goc\venv\Scripts\python.exe).Path
& $p0bPython -m pip install -r ..\sim-v0-goc\requirements.txt playwright
$env:PLAYWRIGHT_BROWSERS_PATH = 'D:\CT244H BTPM\tmp\playwright-browsers'
& $p0bPython -m playwright install chromium
$env:SECRET_KEY = 'dev-evidence'
$env:PYTHONUTF8 = '1'
$p0bSeed = (Resolve-Path scripts\p0b_seed.py).Path
Push-Location ..\sim-v0-goc
& $p0bPython manage.py migrate
& $p0bPython manage.py shell -c "exec(open(r'$p0bSeed', encoding='utf-8').read())"
Pop-Location
& .\scripts\chay_p0b.ps1
# Kiểm tra đúng worktree tạm và lưu đủ ảnh trước khi dọn:
git worktree list
git -C ..\sim-v0-goc status --short
git worktree remove ..\sim-v0-goc --force
```

Script chụp kiểm tra SHA baseline và database ban đầu rỗng trước khi thao tác.
Phản hồi HC03 được lấy thật từ fetch; panel và banner chỉ là chú giải bằng chứng,
không sửa giá hay số lượng trên trang. `observations.json` lưu số liệu đọc lại từ DB.

## Kết quả và giới hạn

- Đủ 10 ảnh trong `evidence/truoc/`; chỉ mục `BANG_CHUNG_TRUOC.md` giải thích từng ảnh.
- Test P0 vẫn 6 failures, 1 error; lỗi có chủ đích trên bản gốc, không skip/xóa test.
- `manage.py check` sạch; `makemigrations --check --dry-run` vẫn phát hiện accounts
  thiếu migration; chưa sửa ở P0b.
- Phát hiện phụ qua UI: sửa mô tả phiếu nhập làm ngày giao cũ bị rỗng do form gốc;
  snapshot trước/sau lưu trong observations.json. Không sửa ứng dụng để vượt lỗi.
- Các ảnh giữ nguyên lỗi ảnh đại diện mặc định và nhãn tiền Ksh của bản gốc.
- Chưa làm HC01, chưa thay đổi model, migration, view, template hoặc workflow.
