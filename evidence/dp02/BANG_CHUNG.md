# DP02 – Bằng chứng trước/sau

Base bao-tri: 723a835212325c3875cb10942c4b220380b2444d, đã có HC01–HC03/TU01/TU02.
Code/test sau: 696107d6b464c0f294efc7a3d2b3c0fb8d281ac1.
Hoàn tất kiểm chứng: 28/11/2026. Không dùng DB thật để migrate/ghi dữ liệu.

## Suite và môi trường

| Mốc | Môi trường | Kết quả |
|---|---|---|
| Trước sửa, 24/11 | Python3.12.10, SQLite, Django5.2.19 | Ran 85 tests in 8.526s; OK |
| Sau sửa, 28/11 | Python3.12.10, SQLite, coverage7.17.5 | Ran 124 tests in 18.350s; OK |
| Sau sửa, CI | Python3.10.22, PostgreSQL16.16, Django5.2.19 | Ran 124 tests in 7.523s; OK |
| Sau sửa, CI | Python3.12.16, PostgreSQL16.16, Django5.2.19 | Ran 124 tests in 7.456s; OK |

[CI cuối PASS](https://github.com/MrTroll219/sales-and-inventory-management/actions/runs/46121655950).
Log đầy đủ ở truoc_suite.txt, sau_suite_sqlite.txt và ci-final/postgres16-python*/.
check.txt và migrations_check.txt: 0 issues / No changes detected.

## Coverage line theo app

| App | Trước | Sau |
|---|---|---|
| store | 75.27% (210/279) | 75.44% (212/281) |
| transactions | 89.93% (366/407) | 90.42% (387/428) |
| invoice | 87.21% (75/86) | 92.08% (93/101) |
| bills | 91.67% (66/72) | 92.00% (69/75) |

Cùng source và omit tests/migrations; không tính code test vào mẫu số.
File report -m và JSON gốc: truoc_coverage.*, sau_coverage.*, coverage_summary.json.
Baseline là code bao-tri tại SHA trên, đo trước mọi thay đổi DP02.

## Các kịch bản

| Kịch bản | Trước | Sau / test chứng minh |
|---|---|---|
| Trường giá Item/Bill/Invoice | FloatField | Decimal(15,2), test round-trip |
| Item legacy price=1.005 | Float gốc | 1.01; DecimalMigrationTests.test_legacy_demo_migrates_with_half_up_decimal_values_preserved |
| Bill legacy amount=2.675 | Float gốc | 2.68; cùng test migration |
| Invoice legacy quantity=3.0 | Float | int 3, tiền lịch sử giữ theo round cent |
| Invoice quantity=1.5 hoặc -1 | Schema Float chấp nhận | Preflight và migration chặn, DB test giữ nguyên giá trị sai, không tự round |
| 0.1+0.2, 3x19.99 | HC03 đã tính Decimal; các schema tiền khác còn Float | 0.30, 59.97; DecimalPricingTests và round-trip |
| Ghi tiền/giá âm hoặc quantity không hợp lệ trực tiếp DB | Thiếu ràng buộc DP02 | IntegrityError, 22 named constraints có mặt trên cả hai engine |
| Sale grand_total lệch 0.01 | Chưa có CHECK identity | IntegrityError: test_sale_grand_matches_parts |
| Sale amount_change lệch 0.01 | Chưa có CHECK identity | IntegrityError: test_sale_change_matches_payment |
| Tổng 0.10+0.20 và biên Decimal15,2 đúng | Chưa có CHECK identity | DB chấp nhận, đúng Decimal sau refresh |
| Invoice partial save quantity | Chưa bảo đảm lưu tổng kèm theo | total/grand_total cập nhật cùng quantity |
| Form nhập tiền âm/Invoice quantity lẻ | Thiếu validator DP02 | Lỗi tại đúng field, không lưu |

Test nằm ở store/tests, bills/tests, invoice/tests và transactions/tests/test_dp02*.
23 test IntegrityError bao phủ 22 constraint (tax range thử hai phía).
Thêm 39 test, giữ nguyên assertions của 85 test cũ. Fixture HC02 thêm paid=100
cho đơn grand=100 để dữ liệu ngày xuất Excel hợp lệ với ràng buộc tiền thừa mới.
Log lỗi fixture ban đầu: initial_fixture_failure.txt.

CI đầu 46120334828: mỗi PG job có 1 ERROR do pending trigger events khi DROP COLUMN
tạm của Invoice. Đã xử lý bằng SET CONSTRAINTS ALL IMMEDIATE sau data writes,
giữ atomic và không tắt constraints. Log lỗi giữ tại ci_initial_failed.txt/ci-initial/.
CI 46121112152 sau sửa migration cũng PASS; CI cuối kiểm chứng thêm test số âm
giữ các tổng liên quan nhất quán. Không skip hoặc đổi kỳ vọng để xanh.

## Cách tự tái hiện trên UI

Trên môi trường demo đã migrate, đăng nhập /accounts/login/:

1. /new-product/: nhập giá -0.01 hoặc tồn -1; form báo lỗi, không lưu.
2. /invoice/new-invoice/: nhập quantity=1.5 hoặc phí âm; form báo lỗi.
3. Cùng URL, nhập đơn giá19.99, quantity3, shipping0.03; tạo hóa đơn rồi xem chi tiết:
   total59.97, grand_total60.00.
4. /bills/new-bill/: amount âm bị từ chối.
5. Các CHECK bypass form/ORM.save được tái hiện bằng test QuerySet.update trên DB test,
   không thử ghi dữ liệu sai trực tiếp lên DB thật.

Đây là hướng dẫn tự kiểm, không tuyên bố đã chụp UI DP02 mới.

## Hồi quy triển khai TU02 và phạm vi

ci-final/compose-health-persistence/: cả db/web/nginx healthy, login200, JPEG200
đúng MIME/bytes trước/sau down/up, DATABASE_AND_MEDIA_PERSISTENCE_PASS,
check --deploy SSL=true: 0 issues. Container chạy trên CI Linux; Windows chưa có Docker.

scope_check.txt xác nhận Purchase.save AST giữ nguyên, SaleCreateView không đổi và
không còn FloatField trong bốn model app tiền. Không tạo migration accounts mới.
Không chuyển nghiệp vụ sang service, không làm DP01 hoặc yêu cầu tiếp theo.
