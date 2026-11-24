# P0 - Chạy lại bằng chứng trên bản gốc

Nhánh: `p0-bang-chung`. Tag cục bộ `v0-goc` trỏ tới
`038cbd5a7e3f4bdfab96f7f9d61016d1d2ea2dc4`.
Không thay đổi logic ứng dụng. Chỉ thêm test, script, bằng chứng và bỏ
`transactions/tests.py` rỗng để không trùng module với package `transactions/tests/`.
Đây là ngoại lệ cần thiết đối với giới hạn đường dẫn P0, đã được Prompt chung
cho phép. Nếu giữ file rỗng, `manage.py test .` báo ImportError lúc discovery.

## Môi trường đã dùng

- Windows, Python 3.12.10, Django 5.1, SQLite in-memory khi test.
- Môi trường ảo: `D:\CT244H BTPM\tmp\p0-venv` (ngoài repository).
- Dependencies trực tiếp giữ đúng `requirements.txt`; bản đầy đủ trong `p0_dependencies.txt`.
- Chưa kiểm tra Python 3.10, PostgreSQL, Docker hoặc giao diện trình duyệt.

## Chạy bằng PowerShell từ thư mục repository

```powershell
$env:SECRET_KEY='p0-test-only-not-for-deployment'
$env:PYTHONUTF8='1'
$pythonP0='D:\CT244H BTPM\tmp\p0-venv\Scripts\python.exe'
& $pythonP0 manage.py test transactions.tests.test_hc_regression -v 2
& $pythonP0 manage.py check
& $pythonP0 manage.py makemigrations --check --dry-run
& $pythonP0 manage.py test .
```

Trên máy khác, tạo venv với Python 3.12, cài `pip install -r requirements.txt`,
rồi thay biến `$pythonP0` bằng đường dẫn python của venv đó.
Không dùng `set SECRET_KEY=...` của cmd.exe trong PowerShell.

## Kết quả đã chạy

| Test (tiền tố test_) | Mong đợi | Thực tế trên bản gốc | Kết quả |
|---|---|---|---|
| hc01_tao_phieu_nhap_chi_cong_mot_lan | Kho 10 | Kho 20 | FAIL |
| hc01_sua_mo_ta_khong_doi_ton | Kho 10 | Kho 30 | FAIL |
| hc01_sua_qua_form_tang_so_luong | Kho 15 | Kho 35; form lưu thành công | FAIL |
| hc02_xuat_excel_khi_khong_co_ngay_giao | HTTP 200, Excel mở được, ngày giao rỗng | AttributeError tại delivery_date.tzinfo | ERROR |
| hc03_tu_choi_tong_tien_gia | HTTP 400, không ghi DB, kho 5 | HTTP 200, tạo 1 Sale + 1 SaleDetail, kho 3 | FAIL |
| hc03_yeu_cau_dang_nhap | Chặn người chưa đăng nhập, không ghi DB | HTTP 200, tạo 1 Sale + 1 SaleDetail, kho 3 | FAIL |
| hc03_so_luong_am | HTTP 400, không ghi DB, kho 5 | HTTP 500; rollback thành công, kho 5 | FAIL |

Mỗi test độc lập, không chạy nối tiếp trên cùng một phiếu nhập.
Số 35 ở test sửa số lượng là kho 20 sau tạo + 15 lúc cập nhật.
`ERROR` ở HC02 do Django test client ném lại exception của view; đây là lỗi
ứng dụng tại thao tác xuất Excel, không phải lỗi chuẩn bị fixture.

`p0_truoc.txt`: toàn bộ output 7 test, exit code 1 có chủ đích.
`p0_suite.txt`: toàn bộ suite sau khi bỏ file test rỗng; cùng 6 FAIL, 1 ERROR.
`p0_check.txt`: System check identified no issues (0 silenced).
`p0_migrations.txt`: phát hiện accounts/0002 còn thiếu, không tạo migration ở P0.

## Thu ảnh giao diện bằng dữ liệu demo riêng

Chưa có ảnh chụp UI trong P0 này. Các bước sau là hướng dẫn kiểm tay, không phải
khẳng định đã thao tác trình duyệt.

1. Dùng database demo mới, chạy migrate và createsuperuser; khởi động runserver.
   Không dùng dữ liệu cửa hàng thật. Đăng nhập tại `/accounts/login/`.
2. Tạo nhà cung cấp và danh mục, tạo sản phẩm giá 100, tồn 0 qua các mục giao diện.
3. HC01: mở `/transactions/new-purchase/`, nhập 10, lưu rồi chụp tồn 20.
   Mở `/transactions/purchase/<ID>/update/`, sửa mô tả, lưu, chụp tồn 30.
   Để so test tăng số lượng: dùng sản phẩm/phiếu mới, đổi 10 thành 15; kho 35.
4. HC02: để trống ngày giao phiếu nhập; truy cập
   `/transactions/purchases/export/`, chụp trang lỗi. Nếu cần tách biệt HC01,
   vẫn ghi rõ tồn kho bị sai sẵn trên baseline.
5. HC03: tạo sản phẩm demo khác giá 100, tồn 5 và khách có cả first_name/last_name.
   Mở `/transactions/new-sale/`, thay hai ID trong `scripts/hc03_console.js`,
   dán script vào Console. Chụp HTTP 200/success và đơn tại `/transactions/sales/`.
   Script sẽ tạo đơn và giảm kho trên bản lỗi; chỉ dùng bản demo cục bộ.
6. Khi sửa từng HC, chạy lại cùng test và kịch bản tương ứng để thu bằng chứng sau.

## Phát hiện thêm / giới hạn

- Thiếu migration accounts cho email, first_name, last_name (log đã lưu).
- WhiteNoise cảnh báo chưa có thư mục staticfiles khi test; không làm test fail.
- Fixture đặt last_name khách hàng để tránh lỗi phụ trong get_full_name của bản gốc.
- Không sửa workflow, fork, push hoặc merge lên GitHub; remote vẫn là repo gốc.
- Không chạy sửa tồn kho hoặc migration ngoài phạm vi P0.
