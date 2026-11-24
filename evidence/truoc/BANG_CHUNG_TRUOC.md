# Bằng chứng trước bảo trì (P0b)

- Mã ứng dụng: `038cbd5a7e3f4bdfab96f7f9d61016d1d2ea2dc4`, tag `v0-goc`.
- Chromium: `159.0.8154.6`; viewport 1366×900; full_page=True.
- Thời gian trên ảnh: Asia/Ho_Chi_Minh (UTC+7).
- Chỉ chèn dải định danh và phản hồi HTTP thực nhận; không sửa giá trị giao diện.
- Database demo độc lập; không phải dữ liệu repository chính.

| Ảnh | Kịch bản | Mong đợi | Thực tế | HTTP |
|---|---|---|---|---|
| [01_hc01_ton_ban_dau.png](01_hc01_ton_ban_dau.png) | Tồn ban đầu | 0 | 0 | 200 |
| [02_hc01_tao_phieu_nhap.png](02_hc01_tao_phieu_nhap.png) | Điền phiếu nhập | 10 sản phẩm, giá nhập 5 | Form đã điền, chưa lưu | 200 |
| [03_hc01_ton_sau_tao.png](03_hc01_ton_sau_tao.png) | Tạo phiếu nhập 10 | Kho 10 | Kho 20 | 200 |
| [04_hc01_ton_sau_sua_mo_ta.png](04_hc01_ton_sau_sua_mo_ta.png) | Chỉ sửa mô tả | Kho vẫn 10 | Kho 30 | 200 |
| [05_hc02_phieu_khong_ngay_giao.png](05_hc02_phieu_khong_ngay_giao.png) | Phiếu thứ hai để trống ngày giao | Ngày giao rỗng | Ngày giao None | 200 |
| [06_hc02_loi_500_xuat_excel.png](06_hc02_loi_500_xuat_excel.png) | Xuất Excel thiếu ngày giao | HTTP 200, ô ngày rỗng | AttributeError: NoneType has no attribute tzinfo | 500 |
| [07_hc03_trang_tao_don.png](07_hc03_trang_tao_don.png) | Mở trang tạo đơn | Form tạo đơn | Form tạo đơn | 200 |
| [08_hc03_phan_hoi_success.png](08_hc03_phan_hoi_success.png) | Gửi giá 0.01, tổng 1 cho 2 sản phẩm giá 100 | HTTP 400, không tạo đơn | HTTP 200, success | 200 |
| [09_hc03_chi_tiet_don_sai.png](09_hc03_chi_tiet_don_sai.png) | Chi tiết đơn giả tiền | Tổng đúng 200.00 | Grand Total Ksh 1.00 | 200 |
| [10_hc03_chua_dang_nhap.png](10_hc03_chua_dang_nhap.png) | Tạo đơn không đăng nhập (có CSRF) | Redirect/401/403, không tạo đơn | HTTP 200, success | 200 |

## Diễn giải

- HC01: khởi đầu 0; tạo phiếu 10 → 20; chỉ sửa mô tả → 30.
- HC02: phiếu thứ hai quantity=10, ngày giao trống; kho tăng từ 30 lên 50 do lỗi baseline.
- HC03: Item.price=100; gửi đơn 2 sản phẩm tổng giả 1; DB lưu tổng 1.00, giá dòng 0.01, kho 50→48.
- Chưa đăng nhập: context mới không có sessionid; gửi request hợp lệ, có CSRF; HTTP 200/success, kho 48→46.
- Mã HTTP của ảnh 02 là GET form; các ảnh danh sách sau lưu là GET cuối sau redirect.
- Ảnh 06 là trang debug thật trả 500; ảnh 08/10 thêm panel từ phản hồi thực nhận.
- `observations.json` lưu snapshot DB đọc sau mỗi ảnh để đối chứng.
- Phát hiện thêm: khi chỉ sửa mô tả phiếu 1, input datetime-local của form gốc không giữ ngày giao; sau lưu delivery_date từ 2026-11-24 09:00 UTC thành None. Không sửa hay can thiệp form để vượt lỗi này. Vì vậy cả hai phiếu ở ảnh 05 đều hiện None; lỗi xuất Excel gặp ngay phiếu 1.
- Chưa có bằng chứng sau sửa; HC01 và các yêu cầu khác chưa thực hiện.
