# Bằng chứng HC02 sau sửa

Commit ứng dụng: `4ec1d81670a212fd7a6a482561c262c593a8ef54`.
Múi giờ ứng dụng vẫn UTC; banner ảnh dùng UTC+7.

| Ảnh | Kịch bản | HTTP |
|---|---|---|
| [01_xuat_excel_thanh_cong.png](01_xuat_excel_thanh_cong.png) | Excel có phiếu thiếu ngày, HTTP 200 | 200 |
| [02_form_hien_dung_ngay_giao.png](02_form_hien_dung_ngay_giao.png) | Form giữ ngày 2026-11-24T09:00 | 200 |
| [03_sau_luu_ngay_giao_van_con.png](03_sau_luu_ngay_giao_van_con.png) | Chỉ sửa mô tả: ngày giao vẫn còn | 200 |

## File Excel tải thật và đọc bằng openpyxl

File: [purchases.xlsx](purchases.xlsx). 1 dòng tiêu đề + 2 dòng dữ liệu.

| Ô | Giá trị đọc được | Định dạng |
|---|---|---|
| E2 | 2026-11-24 08:38:47.837000 | DD/MM/YYYY HH:MM |
| F2 | 2026-11-24 09:00:00 | DD/MM/YYYY HH:MM |
| E3 | 2026-11-24 08:38:47.988000 | DD/MM/YYYY HH:MM |
| F3 | (rỗng / None) | DD/MM/YYYY HH:MM |

Ngày giao DB trước lưu: `2026-11-24 09:00:00+00:00`.
Ngày giao DB sau lưu: `2026-11-24 09:00:00+00:00` (giữ nguyên).
Chỉ sửa description; không điền lại ô ngày, không sửa DOM giá trị form.
Ảnh 01 thêm panel từ HTTP và các ô đọc trong file tải thật; không dựng dữ liệu giả.
Script tự dừng server. Worktree/database demo được dọn sau kiểm tra ảnh.
