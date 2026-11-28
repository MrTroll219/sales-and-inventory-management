# DP01 – Bằng chứng trước/sau

Base: b72bf15 (DP02). Code/test sau: 281f824. Kiểm chứng ngày 28/11/2026.
[CI thành công](https://github.com/MrTroll219/sales-and-inventory-management/actions/runs/46125322513).

| Môi trường | Kết quả |
|---|---|
| Baseline Windows Python3.12.10 / SQLite | Ran 124 tests in 12.538s; OK |
| Sau Windows Python3.12.10 / SQLite | Ran 151 tests in 18.533s; OK |
| Sau CI Python3.10.22 / PostgreSQL16.16 | Ran 151 tests in 13.906s; OK |
| Sau CI Python3.12.16 / PostgreSQL16.16 | Ran 151 tests in 8.469s; OK |

| Kịch bản | Trước, theo mã b72bf15 | Sau / bằng chứng |
|---|---|---|
| Ghi tồn | Purchase.save và SaleCreateView có SQL cộng/trừ; form Item save trực tiếp | Chỉ stock.py viết quantity; architecture test PASS |
| SaleCreateView | 62 dòng | 21 dòng; view_lines.txt |
| Tạo phiếu 3 khi tồn10 | Tồn13, không có sổ | Tồn13, PURCHASE_IN delta3/after13 |
| Sửa phiếu3 thành5 | Tồn15, không có sổ | Tồn15, PURCHASE_EDIT delta2/after15 |
| Sửa mô tả | Tồn giữ nguyên | Giữ nguyên, không thêm movement giả |
| Xóa phiếu3 khi tồn13 | Xóa chứng từ, tồn vẫn13 | Tồn10, PURCHASE_DELETE delta-3, giữ ref_id |
| Xóa phiếu10 khi tồn5 | Không kiểm tra thiếu kho lúc xóa | Từ chối, chứng từ/tồn/sổ giữ nguyên |
| Bán2x100, thuế10%, trả250 | Tổng220, thừa30 theo HC03 | Giữ tổng220/thừa30; SALE_OUT -2 và user |
| Ghi sổ lỗi sau F update | Chưa có sổ | Rollback tồn và chứng từ |
| Item tồn7 trước DP01 | Không có opening ledger | Migration giữ tồn7, mở sổ delta7/after7 |
| Cache bị lệch10→7 trong DB test | Chưa có command | Lệnh đọc không ghi; --fix trả10, ledger vẫn10, lần2 không ghi thêm |

27 test mới ở test_dp01_services.py (23), test_dp01_architecture.py (3),
test_dp01_opening.py (1). Các trường hợp trước dựa trên mã base, không tuyên bố
đã chụp UI DP01 trước/sau. Cách tái hiện UI đầy đủ trong docs/DP01.md.

## Test cũ không đổi kỳ vọng

- 124 test cũ vẫn PASS; chỉ bốn file được đổi lời gọi theo xác nhận người dùng.
- [Danh sách từng test/helper](TEST_CU_KHONG_DOI_KY_VONG.md).
- [Diff từng hunk trước/sau](legacy_calls_diff.patch).
- [Hash và đếm AST assertions](legacy_assertions.json): 88 lời gọi assertion giữ
  nguyên; mọi literal dữ liệu giống base. Test cũ khác không thay đổi.
- dp02_constraints_unchanged.txt: Meta của Sale/SaleDetail/Purchase giữ nguyên AST.
- Không skip/xóa test. Log lỗi hai fixture DP01 mới đã sửa được giữ riêng.

## Hồi quy triển khai

ci-final/compose-health-persistence/ chứa log và ảnh login: db/web/nginx healthy,
login qua nginx200; MEDIA image/jpeg200 đúng2902 byte; dữ liệu DB/MEDIA còn sau
down/up; production check --deploy SSL=true: 0 issues. Container chạy trên CI Linux.

## Phạm vi dữ liệu

Không migrate hoặc chạy reconcile_stock --fix trên dữ liệu thật. Opening migration
chỉ ghi sổ ban đầu, không thay số tồn hiện có. Reconcile repair là delta nghiệp vụ0
để không làm lệch SUM(delta); policy và rủi ro ghi rõ trong docs/DP01.md.
