# TU01 - Bằng chứng trước/sau

| Hạng mục | Trước TU01 | Sau TU01 |
|---|---|---|
| Django | 5.1 | 5.2.19 |
| Toàn suite | 60 tests, OK | 66 tests, OK, warnings-as-errors |
| Manifest staticfiles.json | 0 | 1, 150 mục |
| makemigrations --check --dry-run | Thiếu accounts/0002 | No changes detected |
| Migration DB trống | Chưa áp dụng0002 | Thành công |
| Migration DB demo5.1 | Có dữ liệu HC01/HC03 | Thành công, các trường ở8 bảng đối chiếu giữ nguyên |
| Python3.10 | Không có runtime | Chưa kiểm3.10 |

## Ảnh sau nâng, Django5.2.19

- [Dashboard](sau/01_dashboard.png): HTTP200, biểu đồ và bảng điều khiển hiển thị.
- [Tạo đơn bán](sau/02_tao_don_ban.png): HTTP200, nhãn Tax (%) và form hiển thị.
- [Danh sách phiếu nhập](sau/03_danh_sach_phieu_nhap.png): HTTP200, bảng và nút thao tác hiển thị.

Ảnh có commit triển khai0b15930, thời gian UTC+7; Playwright page_errors=[].
Log kiểm thử và collectstatic nằm cùng thư mục này; migration_summary.json đối chiếu
DB demo. Các lệnh preflight chỉ đọc và cách xử lý dữ liệu có vấn đề nằm ở docs/TU01.md.
Không commit thư mục staticfiles, không áp dụng migration trên DB chính/dữ liệu thật.
Trên checkout mới cần collectstatic trước test render HTML. Lần thử đầu thiếu
manifest có5 ERROR, được giữ trong sau_strict_initial.txt; sau build static66 test PASS.
