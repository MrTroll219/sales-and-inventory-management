# BÁO CÁO TỔNG HỢP BẢO TRÌ PHẦN MỀM

Dự án: **MrTroll219/sales-and-inventory-management**, fork từ munuhee. Ngày kiểm chứng: **28/11/2026**, giờ Việt Nam. Báo cáo ghi nhận bằng chứng đã chạy; không thay thế nghiệm thu trên dữ liệu cửa hàng thật.

## 0. Thông tin và phạm vi

- Bản gốc: tag `v0-goc`, SHA `038cbd5a7e3f4bdfab96f7f9d61016d1d2ea2dc4`.
- Bản ứng dụng được kiểm chứng: `bao-tri`, SHA `123101a85ea74091c2863e0a00f952477918d925`.
- Bản đóng gói: tag annotated `v1-bao-tri` trên commit `FINAL: bao cao tong hop`; commit này chỉ thêm báo cáo/bằng chứng. Xem SHA đóng gói bằng `git rev-parse 'v1-bao-tri^{commit}'`; không nhầm với SHA ứng dụng được kiểm chứng ở trên.
- Local: Windows PowerShell, Python 3.12.10, Django 5.2.19, SQLite 3.49.1, coverage 7.17.5. Đo v0 bằng venv Django 5.1 riêng, cùng Python/coverage.
- CI Ubuntu 24.04: Python 3.10.22 và 3.12.16, Django 5.2.19, PostgreSQL 16.16; thêm hai job SQLite và Docker Compose smoke. Windows không có Docker; container chạy thật trên CI, không tuyên bố đã chạy trên máy Windows/VPS thật.
- CI chính xác SHA `123101a`: [run 46141942142](https://github.com/MrTroll219/sales-and-inventory-management/actions/runs/46141942142), event push, branch bao-tri, **5/5 job PASS**. Workflow đã có bao-tri trong trigger nên không cần sửa CI. Lần dispatch thủ công trùng 46142043593 được hủy, không dùng làm bằng chứng thành công.
- FINAL không sửa code nghiệp vụ, test, migration, cấu hình hay remote; không mở PR, không push upstream. Mọi log mới nằm trong `evidence/final/`.

## 1. Kiểm tra cấu hình Git và ancestor

`git fetch --all` thành công. Trước kiểm chứng, local và origin/bao-tri đều đúng `123101a`, cây làm việc sạch; tag v1-bao-tri chưa tồn tại. Kiểm tra `git merge-base --is-ancestor <ref> bao-tri` cho cả local và origin của mỗi nhánh: **24/24 exit 0**. Không thiếu nhánh, không cần merge.

| Mốc/nhánh | SHA cuối | Local ancestor | Origin ancestor |
|---|---|---|---|
| p0-bang-chung | 632c54a | exit 0 | exit 0 |
| hc01-ton-kho-phieu-nhap | 31654e6 | exit 0 | exit 0 |
| hc02-xuat-excel-ngay-giao | 0b62b64 | exit 0 | exit 0 |
| hc03-tinh-tien-may-chu | fbac946 | exit 0 | exit 0 |
| tu01-nang-django-52 | 86e8d04 | exit 0 | exit 0 |
| tu02-trien-khai-docker | 723a835 | exit 0 | exit 0 |
| dp02-decimal-rang-buoc | b72bf15 | exit 0 | exit 0 |
| dp01-tach-nghiep-vu-kho | abcfe86 | exit 0 | exit 0 |
| tu03-viet-nam-vnd | 607c952 | exit 0 | exit 0 |
| ht01-ton-toi-thieu | 35176c4 | exit 0 | exit 0 |
| ht02-loc-giao-dich | b806fd4 | exit 0 | exit 0 |
| ht03-huy-don | 123101a | exit 0 | exit 0 |

P0 là bước chuẩn bị/bằng chứng, không tính vào 11 yêu cầu bảo trì. SHA đầy đủ, mã thoát và output fetch ở `evidence/final/ancestors.json`, `fetch_all.txt`.

## 2. Kết quả kiểm chứng bản cuối

Các lệnh local dùng DB SQLite tạo trong TemporaryDirectory riêng, `DJANGO_ENV_FILE=NUL`, không đọc `.env` thật và không đụng `db.sqlite3` cửa hàng. Coverage tạo DB test riêng của Django. Production check dùng key ngẫu nhiên tạm đủ dài, DEBUG=false, SSL=true, HSTS=3600, include-subdomains/preload=true trên domain thử example.invalid; **không lưu key**. Hai cờ HSTS chỉ được bật thật sau khi xác nhận chính sách domain.

| Lệnh | Kết quả | Log trong evidence/final/ |
|---|---|---|
| python manage.py check | System check identified no issues (0 silenced). | check.txt |
| python manage.py check --deploy | System check identified no issues (0 silenced). | check_deploy.txt |
| python manage.py makemigrations --check --dry-run | No changes detected | migrations_check.txt |
| python manage.py migrate --plan | Kế hoạch phụ thuộc đầy đủ | migration_plan.txt |
| python manage.py migrate --noinput | Thành công trên DB trống; 37 migration gồm 19 của dự án + 18 Django | migrate_empty.txt, showmigrations.txt |
| python manage.py check_decimal_data | safe_to_migrate=true, violations=[] | check_decimal_data.txt |
| python manage.py check_vnd_data | safe_to_migrate=true, violations=[] | check_vnd_data.txt |
| python manage.py reconcile_stock | fix=false, items=[] trên DB trống | reconcile_stock.txt |
| coverage toàn suite | Ran 247 tests in 29.294s; OK (skipped=1) | coverage_suite_sqlite.txt |

Kết quả preflight trên DB trống không chứng minh dữ liệu thật đã hợp lệ. Các test migration dữ liệu có sẵn, rollback, constraints và đối soát sau hủy vẫn chạy trong toàn suite trên SQLite/PostgreSQL16.

Lệnh coverage thực tế:

```powershell
$env:DEBUG="true"; $env:SECRET_KEY="test"; $env:DB_ENGINE="sqlite"; $env:DJANGO_ENV_FILE="NUL"
# DB_NAME và COVERAGE_FILE được runner đặt vào đường dẫn thử riêng.
python -W error::DeprecationWarning -W error::PendingDeprecationWarning -m coverage run --source=store,accounts,transactions,invoice,bills --omit='*/tests/*,*/tests.py,*/migrations/*' manage.py test . -v 2
python -m coverage report -m
python -m coverage json -o evidence/final/coverage_final.json
```

Bộ omit giống DP02; bổ sung accounts vào source để báo đủ năm app. Bốn app còn lại vẫn đo cùng quy tắc. Không tính test/migration vào mẫu số. Runner tái hiện toàn bộ local: `python evidence/final/run_validation.py --repo <checkout-123101a> --out <thu-muc-log>`, tự tạo/xóa DB tạm và key production tạm.

| CI job / đúng SHA 123101a | Runtime | Output thật | Trạng thái |
|---|---|---|---|
| sqlite-python3.10 | Python3.10.22 / SQLite | Ran 247 tests in 18.923s; OK (skipped=1) | PASS |
| sqlite-python3.12 | Python3.12.16 / SQLite | Ran 247 tests in 18.117s; OK (skipped=1) | PASS |
| postgres16-python3.10 | Python3.10.22 / PostgreSQL16.16 | Ran 247 tests in 23.705s; OK | PASS |
| postgres16-python3.12 | Python3.12.16 / PostgreSQL16.16 | Ran 247 tests in 18.091s; OK | PASS |

SQLite bỏ qua **đúng một test HT03 mới về cạnh tranh** vì không hỗ trợ SELECT FOR UPDATE, theo ngoại lệ được duyệt; 214 test cũ không skip. PostgreSQL16 chạy cả 247 test, **không skip**; test hai luồng có một success, một SaleAlreadyCancelled, một audit, hai SALE_CANCEL và kho chỉ hoàn một lần.

Docker smoke cùng run/SHA: `docker compose build` và up thành công, db/web/nginx healthy, login HTTP200 qua nginx, MEDIA image/jpeg HTTP200 đúng bytes, dữ liệu DB/MEDIA còn sau down/up, production SSL `check --deploy` 0 issues. Log/ảnh thật: `evidence/final/ci/compose-health-persistence/` gồm build_up.txt, ps_before.txt, ps_after.txt, login.png, login_http.txt, media_http_before.txt, media_http_after.txt, persistence.txt, production_check_deploy.txt. Không coi kiểm tra HTTPS giả lập trong CI là nghiệm thu chứng chỉ TLS/domain thật.

Metadata CI, SHA/job/step: ci_run.json; lệnh local/mã thoát: commands.json; môi trường không chứa secret: runtime.txt, validation_metadata.json. Coverage chỉ đo local SQLite; không tuyên bố có số đo coverage PostgreSQL.

## 3. Bảng 11 yêu cầu và tiến trình kiểm thử

| Mã | Loại bảo trì | Tên | Nhánh | Commit cuối | Test thêm | Migration | Trạng thái |
|---|---|---|---|---|---|---|---|
| HC01 | Hiệu chỉnh | Tồn kho phiếu nhập | hc01-ton-kho-phieu-nhap | 31654e6 | 14 | Không | Hoàn tất |
| HC02 | Hiệu chỉnh | Excel và ngày giao | hc02-xuat-excel-ngay-giao | 0b62b64 | 15 | Không | Hoàn tất |
| HC03 | Hiệu chỉnh | Tính tiền máy chủ | hc03-tinh-tien-may-chu | fbac946 | 24 | Không | Hoàn tất |
| TU01 | Thích ứng | Nâng Django 5.2 | tu01-nang-django-52 | 86e8d04 | 6 | accounts/0002 | Hoàn tất |
| TU02 | Thích ứng | Docker, PostgreSQL16, nginx/MEDIA | tu02-trien-khai-docker | 723a835 | 19 | Không | Hoàn tất |
| DP02 | Dự phòng | Decimal và ràng buộc | dp02-decimal-rang-buoc | b72bf15 | 39 | store/0002; transactions/0004; invoice/0002; bills/0002 | Hoàn tất |
| DP01 | Dự phòng | Tách dịch vụ kho, sổ kho | dp01-tach-nghiep-vu-kho | abcfe86 | 27 | transactions/0005 | Hoàn tất |
| TU03 | Thích ứng | Giờ Việt Nam, tiếng Việt, VND | tu03-viet-nam-vnd | 607c952 | 17 | store/0003; transactions/0006; invoice/0003; bills/0003 | Hoàn tất |
| HT01 | Hoàn thiện | Ngưỡng tồn tối thiểu | ht01-ton-toi-thieu | 35176c4 | 21 | store/0004 | Hoàn tất |
| HT02 | Hoàn thiện | Lọc và xuất giao dịch | ht02-loc-giao-dich | b806fd4 | 25 | Không | Hoàn tất |
| HT03 | Hoàn thiện | Hủy đơn, lịch sử, hoàn kho | ht03-huy-don | 123101a | 33 | transactions/0007 | Hoàn tất |

“Hoàn tất” là trạng thái triển khai của từng yêu cầu; không có nghĩa suite tại các mốc HC01/HC02 từng xanh. Khi đó lỗi các yêu cầu kế tiếp được giữ làm hồi quy, thể hiện đúng bên dưới. TU02 thêm 19 test gồm 16 ban đầu + 3 test bản vá nginx/MEDIA; 11 yêu cầu thêm 240 test, cộng P0 7 = **247**.

| Mốc | Test thêm | Tổng test | Kết quả tại mốc | Log lịch sử trong evidence/ |
|---|---|---|---|---|
| v0-goc | 0 | 0 | NO TESTS RAN | final/v0_suite.txt |
| P0/P0b | 7 | 7 | 6 FAIL + 1 ERROR | p0b_suite.txt |
| HC01 | 14 | 21 | 3 FAIL + 1 ERROR | hc01/suite.txt |
| HC02 | 15 | 36 | 3 FAIL | hc02/suite.txt |
| HC03 | 24 | 60 | OK | hc03/suite.txt |
| TU01 | 6 | 66 | OK | tu01/sau_strict_suite.txt |
| TU02 | 19 | 85 | OK | tu02/bo-sung/sqlite_suite.txt |
| DP02 | 39 | 124 | OK | dp02/sau_suite_sqlite.txt |
| DP01 | 27 | 151 | OK | dp01/sau_suite_sqlite.txt |
| TU03 | 17 | 168 | OK | tu03/sau_suite_sqlite.txt |
| HT01 | 21 | 189 | OK | ht01/sau_suite_sqlite.txt |
| HT02 | 25 | 214 | OK | ht02/sau_suite_sqlite.txt |
| HT03 | 33 | 247 | OK (SQLite skip 1 concurrency; PG16 không skip) | ht03/sau_suite_sqlite.txt |

Chuỗi tổng số: **0 → 7 → 21 → 36 → 60 → 66 → 85 → 124 → 151 → 168 → 189 → 214 → 247**. TU02 có mốc trung gian 82 trước bản vá MEDIA. Mỗi tổng đã đối chiếu dòng Ran N tests trong log lịch sử; metadata ở test_history.json. Không chạy lại các bản lỗi lịch sử hoặc sửa test để làm xanh trong FINAL.

Lịch sử test từng có thay đổi được ghi tại tài liệu yêu cầu: DP01 chuyển lời gọi kho sang service theo chấp thuận, giữ assertion; TU03 cập nhật 13 test/fixture về VND, dung sai và ngôn ngữ theo chấp thuận, diff riêng đã lưu. FINAL không thay bất kỳ test nào.

## 4. So sánh v0-goc và bản cuối

| Hạng mục | v0-goc | Bản cuối 123101a |
|---|---|---|
| Django | 5.1 | 5.2.19 |
| Python Docker | 3.10.12-alpine | 3.12-slim; CI Python 3.10/3.12 |
| DB | SQLite mặc định, có nhánh cấu hình Azure PostgreSQL nhưng chưa có bằng chứng PG16 | SQLite vẫn mặc định local; Compose PostgreSQL16, CI xác nhận 16.16 |
| Tests | 0; NO TESTS RAN | 247; SQLite 246 PASS + 1 skip được duyệt; PG16 247 PASS |
| Tiền | Float/Decimal hỗn hợp, nhãn Ksh | VND Decimal(15,0), ROUND_HALF_UP, dung sai client 0 |
| Ngày/ngôn ngữ | UTC, en-us | Asia/Ho_Chi_Minh, vi; lưu datetime aware, hiển thị ngày Việt Nam |
| Kho | Cộng lại khi save phiếu, thiếu dịch vụ/sổ nhất quán | Service DP01 + sổ StockMovement; hủy hoàn đúng một lần |
| Giao dịch | Không lọc/export theo GET | Bộ lọc chung list/export, doanh thu loại đơn hủy |
| Triển khai | DEBUG=true, cảnh báo deploy, MEDIA chưa đáp ứng production | Env config, Gunicorn non-root, nginx, volumes, check --deploy 0 trong cấu hình SSL thử |
| Migration dự án | 7 | 19, tăng 12; không đếm helper/_init và migration Django |

### Coverage line theo app

| App | v0 covered/statements | v0 % (chỉ khởi tạo) | Cuối covered/statements | Cuối % |
|---|---|---|---|---|
| store | 208/279 | 74.55% | 364/426 | 85.45% |
| accounts | 196/248 | 79.03% | 221/263 | 84.03% |
| transactions | 157/283 | 55.48% | 818/845 | 96.80% |
| invoice | 75/86 | 87.21% | 96/104 | 92.31% |
| bills | 66/72 | 91.67% | 72/78 | 92.31% |

Tổng cuối **1571/1716 statements = 91,55%**. Đây là line coverage, không phải branch coverage hoặc độ bao phủ mọi luồng UI. **Coverage v0 khác 0 dù có 0 test** vì coverage ghi nhận import, khai báo model/form/admin và startup/system check. Các tỷ lệ v0 chỉ là thực thi khởi tạo, không chứng minh bất kỳ kịch bản nghiệp vụ nào được test. Không dùng chênh lệch này như thước đo chất lượng tuyệt đối.

Đo v0 trên checkout tách biệt đúng tag, Django5.1/Python3.12.10/coverage7.17.5, cùng source/omit; output giữ nguyên `Ran 0 tests ... NO TESTS RAN`. JSON và report đầy đủ ở coverage_v0.json, v0_coverage_report.txt; bản cuối coverage_final.json, coverage_report.txt; bảng tổng hợp coverage_by_app.json/md. Khác phiên bản Django là chủ đích vì đo từng bản với runtime của nó.

### Migration và diff theo app

| App | Migration v0 | Cuối | Tăng |
|---|---|---|---|
| accounts | 1 | 2 | 1 |
| store | 1 | 4 | 3 |
| transactions | 3 | 7 | 4 |
| invoice | 1 | 3 | 2 |
| bills | 1 | 3 | 2 |
| Tổng | 7 | 19 | 12 |

`git diff --stat v0-goc..bao-tri` chạy khi bao-tri còn đúng 123101a: **747 files changed, 39963 insertions(+), 659 deletions(-)**. Bao gồm test, docs, log và ảnh của cả quá trình, không chỉ code nghiệp vụ. Commit FINAL chỉ thêm báo cáo/bằng chứng nên số file sau đóng gói sẽ lớn hơn; không đưa một diff tự tham chiếu vào báo cáo.

| Nhóm/app | File thay đổi | Dòng thêm | Dòng xóa | File nhị phân |
|---|---|---|---|---|
| (root) | 8 | 125 | 8 | 0 |
| .github | 5 | 176 | 43 | 0 |
| InventoryMS | 1 | 82 | 47 | 0 |
| accounts | 22 | 220 | 38 | 0 |
| bills | 11 | 121 | 20 | 0 |
| docs | 13 | 2388 | 0 | 0 |
| evidence | 568 | 30461 | 0 | 65 |
| invoice | 12 | 275 | 46 | 0 |
| nginx | 1 | 32 | 0 | 0 |
| scripts | 12 | 1246 | 0 | 0 |
| static | 2 | 12 | 0 | 1 |
| store | 34 | 694 | 82 | 0 |
| transactions | 58 | 4131 | 375 | 0 |

File chính: InventoryMS/settings.py; Dockerfile/docker-compose.yml/entrypoint.sh/nginx; models/forms/views/templates các app; transactions/services, filters, management commands; store/money.py và templatetags; migration mới; tests.yml. Danh sách đầy đủ ở diff_stat_v0.txt, diff_numstat_v0.txt, diff_by_app.json. Các bảng này là phạm vi source tới 123101a, không gồm artifact FINAL vừa tạo.

## 5. Migration và preflight khi triển khai

### Thứ tự thực tế trên DB trống

Django tự giải dependency, không chạy theo thứ tự alphabet hoặc thứ tự mã yêu cầu. Kế hoạch thực tế của 19 migration dự án (các migration Django xen giữa được giữ trong migration_plan.txt):

```text
accounts.0001_initial
accounts.0002_alter_profile_email_alter_profile_first_name_and_more
store.0001_initial
transactions.0001_initial
transactions.0002_rename_discount_amount_sale_tax_amount_and_more
transactions.0003_alter_purchase_quantity
invoice.0001_initial
bills.0001_initial
transactions.0004_dp02_decimal_constraints
store.0002_dp02_decimal_constraints
transactions.0005_dp01_stock_movement
invoice.0002_dp02_decimal_constraints
bills.0002_dp02_decimal_constraints
bills.0003_tu03_vnd
invoice.0003_tu03_vnd
store.0003_tu03_vnd
store.0004_ht01_min_stock_level
transactions.0006_tu03_vnd
transactions.0007_ht03_sale_cancellation
```

### Nâng DB có dữ liệu từ v0-goc

**Chỉ áp dụng các target lịch sử dưới đây cho bản sao DB v0 chưa nâng. Không chạy lại target 0002/0004/0005 trên DB đã TU03/HT03 vì có thể unapply migration và mất lịch sử.** Xem showmigrations trước. Kiểm thử phục hồi backup và dừng mọi nguồn ghi trước preflight; dùng image cuối nhưng override entrypoint để không tự migrate vượt qua các điểm kiểm tra.

1. Backup DB + MEDIA, xác nhận đúng engine/tên volume, thử restore trên môi trường riêng. Build image, chỉ khởi động db; chưa khởi động web/entrypoint tự migrate.
2. TU01: chạy `check_profile_data` chỉ đọc (email trùng kể cả '', độ dài email/tên); nếu có lỗi dừng, xử lý theo chứng từ/quyết định được duyệt. Sau sạch: migrate accounts/0002.
3. DP02: chạy `check_decimal_data`; chặn số tiền/quantity Invoice lẻ hoặc âm, overflow và bất đẳng thức. Không tự làm tròn quantity, không tắt CHECK. Áp bốn migration DP02 theo dependencies.
4. DP01: migrate transactions/0005, seed opening ledger bằng quantity hiện có; không tự chứng minh hay sửa số liệu lịch sử đã sai. Đối chiếu sổ/chứng từ trước vận hành; chỉ dùng service cho nguồn ghi mới.
5. TU03: chạy `check_vnd_data` trước bất kỳ migration TU03 nào; kiểm tra round nguyên đồng và identities. Nếu round gây xung đột tổng thì dừng; không tự sửa chứng từ hoặc quy đổi tỷ giá. Áp các TU03 rồi HT01/HT03 bằng migrate cuối.
6. Sau migrate: chạy lại hai preflight, check và reconcile_stock **không --fix**; đánh giá chênh với tồn đầu/ADJUST. Không mặc định ledger_minus_trade phải 0 nếu có opening/điều chỉnh; difference so với ledger phải được giải thích. Chỉ nghiệm thu khi đã đối chiếu dữ liệu thật trên bản sao.

Ví dụ cho service web dùng DB PostgreSQL v0 đã restore, db đang healthy; mỗi lệnh phải thành công trước khi chạy tiếp:

```bash
sudo docker compose run --rm --no-deps --entrypoint python web manage.py showmigrations
sudo docker compose run --rm --no-deps --entrypoint python web manage.py check_profile_data
sudo docker compose run --rm --no-deps --entrypoint python web manage.py migrate accounts 0002
sudo docker compose run --rm --no-deps --entrypoint python web manage.py check_decimal_data
sudo docker compose run --rm --no-deps --entrypoint python web manage.py migrate transactions 0004
sudo docker compose run --rm --no-deps --entrypoint python web manage.py migrate store 0002
sudo docker compose run --rm --no-deps --entrypoint python web manage.py migrate invoice 0002
sudo docker compose run --rm --no-deps --entrypoint python web manage.py migrate bills 0002
sudo docker compose run --rm --no-deps --entrypoint python web manage.py migrate transactions 0005
sudo docker compose run --rm --no-deps --entrypoint python web manage.py check_vnd_data
sudo docker compose run --rm --no-deps --entrypoint python web manage.py migrate --noinput
sudo docker compose run --rm --no-deps --entrypoint python web manage.py check_decimal_data
sudo docker compose run --rm --no-deps --entrypoint python web manage.py check_vnd_data
sudo docker compose run --rm --no-deps --entrypoint python web manage.py reconcile_stock
```

Nếu nguồn thật là SQLite, đổi DB_ENGINE sang PostgreSQL **không chuyển dữ liệu**. Cần kế hoạch export/import/đối chiếu riêng trên bản sao; không restore file SQLite vào volume PostgreSQL. FINAL không thực hiện ETL dữ liệu thật. DB trống không chạy các preflight trước tồn tại bảng; chỉ `migrate` đầy đủ rồi kiểm tra như bằng chứng.

## 6. Lỗi tồn đọng, mức độ và đề xuất bảo trì

Gom từ mục Phát hiện thêm/Rủi ro của HC/TU/DP/HT, đối chiếu source cuối. Trích nguồn ở findings_sources.md. Các lỗi đã được bước sau xử lý (accounts/0002, ngày giao None/form, avatar mặc định/MEDIA, sáu deploy warning, slug route xóa Sale) không còn liệt kê là lỗi đang mở.

| ID | Vị trí | Mô tả/tác động | Mức độ | Đề xuất loại bảo trì |
|---|---|---|---|---|
| F01 | store/models.py:89–93 | Item.get_absolute_url gọi item-detail, route thật product-detail; caller có thể NoReverseMatch | Trung bình | HC: sửa route, thêm test URL |
| F02 | bills/models.py:11 | Bill.slug populate_from date có log/cảnh báo khi ngày chưa sẵn lúc insert | Thấp | HC: thống nhất thời điểm sinh slug, test insert |
| F03 | transactions/templates/transactions/purchases_list.html:50 | Cột Đơn giá hiển thị total_value thay vì price; dễ hiểu sai số tiền | Trung bình | HC: sửa mapping và test hiển thị |
| F04 | transactions/admin.py:21 | SaleAdmin.search_fields customer__name không tồn tại, tìm kiếm admin có thể lỗi | Trung bình | HC: dùng first_name/last_name/phone có thật |
| F05 | transactions/admin.py:59–79, SaleAdmin.save_model | SaleDetail admin còn sửa trực tiếp chứng từ; có thể lệch tồn/sổ. SaleAdmin cũng còn đường sửa trực tiếp, dù status/xóa đã được HT03 hạn chế | Cao | DP: chặn đường ghi ngoài dịch vụ hoặc cung cấp service có audit/rollback |
| F06 | store/templates/store/base.html:10,58; templates/form phụ | CDN ngoài, Bootstrap CSS/JS khác thế hệ, nhãn tiếng Anh còn ở trang phụ; phụ thuộc mạng và trải nghiệm chưa đồng nhất | Trung bình | TU: quản lý asset/phụ thuộc; HT: hoàn thiện Việt hóa/UI |
| F07 | transactions/templates/transactions/saledetail.html:333–334 | Địa chỉ/điện thoại công ty demo của tác giả vẫn in trên receipt | Trung bình | TU: cấu hình thông tin doanh nghiệp trước dùng thật |
| F08 | transactions/models.py StockMovement.item; store/models.py Item.category | Quan hệ CASCADE có thể làm mất sổ khi mặt hàng được phép xóa; thay đổi chính sách xóa cần thiết kế riêng | Cao | DP: PROTECT/soft delete và retention/audit |
| F09 | transactions/utils.py + openpyxl | Excel round mili giây; 23:59:59.999999 có thể đọc lại thành 00:00 hôm sau dù query ngày đúng | Trung bình | HC: chốt chính sách precision/round khi xuất và test biên |
| F10 | transactions/views.py export; transactions/filters.py choices | Workbook giữ trong RAM và dropdown tải tập lựa chọn; chưa đo tải dữ liệu lớn | Trung bình, giới hạn hiệu năng | HT/DP: đo tải, streaming/autocomplete nếu cần |
| F11 | Middleware WhiteNoise khi chạy test không có staticfiles | UserWarning về thư mục staticfiles thiếu, suite vẫn PASS; không phải lỗi manifest test đã sửa ở TU02 | Thấp | DP: làm rõ/chỉnh cảnh báo môi trường test khi có yêu cầu |

Các đề xuất ở bảng là việc tương lai, không thực hiện trong FINAL. Các tài liệu TU01/TU02 phản ánh mốc lịch sử; khi triển khai bản cuối dùng tag và hướng dẫn mục 8 thay vì clone nhánh TU02 cũ.

## 7. Giả định và rủi ro tổng hợp

| Yêu cầu | Giả định/chính sách đang áp dụng | Trạng thái cần lưu ý |
|---|---|---|
| HC01 | Phiếu nhập cộng kho ngay khi lưu, không chờ delivery_status; dữ liệu sai cũ không tự chữa | Cần nghiệp vụ xác nhận trước dùng dữ liệu thật |
| HC02 | Excel không giữ tzinfo; datetime-local sửa theo phút, giữ giây cũ khi phút không đổi | TU03 chốt giờ hiển thị Việt Nam; precision Excel còn F09 |
| HC03 | Thuế cộng thêm, giá/tổng do server tính, không tin client | Thuế đã chốt; dung sai 0.01 cũ đã được TU03 thay bằng 0 đồng |
| TU01 | Email Profile unique, max150; tên max30; không tự gộp account trùng | Phải duyệt xử lý dữ liệu vi phạm trước migrate |
| TU02 | HTTP loopback/lab là ngoại lệ có chủ đích; production có proxy TLS tin cậy, key đủ mạnh, volume riêng | Chủ hệ thống xác nhận domain/proxy/HSTS; CI không kiểm chứng VPS thật |
| DP02 | Invoice.quantity nguyên không âm; 0 vẫn hợp lệ; tiền cent được round HALF_UP | Invoice quantity=0 còn cần xác nhận nghiệp vụ; không hỗ trợ hàng cân/lẻ |
| DP01 | Mọi ghi tồn qua service; ledger là nguồn đối soát/sửa cache; opening giữ quantity hiện có | Không dùng --fix thật khi chưa duyệt; opening không sửa lịch sử sai |
| TU03 | Tiền nguyên VND, HALF_UP; không chuyển tỷ giá Ksh→VND, không tính lại hóa đơn cũ | Phải xác nhận ý nghĩa giá gốc; mất phần lẻ là có chủ đích |
| HT01 | Ngưỡng 0 tắt; bằng ngưỡng vẫn cần nhập; đề xuất max(2×min−quantity,0) | Công thức mục tiêu tồn gấp đôi cần quản lý xác nhận; không tự tạo phiếu |
| HT02 | Ngày theo lịch VN, bao gồm ngày cuối; lọc tiền grand_total, tổng nhập total_value; invalid báo lỗi, unknown key bỏ qua | List/export khác request, không có snapshot khi có ghi xen giữa |
| HT03 | User active staff/superuser được hủy; không hoàn tiền; tiền lịch sử giữ nguyên; audit giữ sau xóa bằng SET_NULL + sale_reference | Quyền/retention cần chủ hệ thống xác nhận; tự cộng Excel phải loại CANCELLED |

- **Backup DB và MEDIA, thử restore, dừng mọi nguồn ghi** trước chuyển schema. Kiểm tra dung lượng cột tạm/quét toàn bảng và thời gian downtime trên bản sao đủ lớn.
- DP02 Float→Decimal và TU03 cents→đồng là lượng tử hóa, không đảo ngược đầy đủ. Reverse migration hoặc rollback code không khôi phục phần lẻ; khôi phục backup mới bảo toàn dữ liệu trước chuyển đổi.
- HT03 reverse migration bỏ status/audit; không rollback schema tùy tiện khi đã có đơn hủy. Không đổi/xóa helper migration đã đóng băng.
- Named volumes giữ qua down/up nhưng không thay backup; không dùng `docker compose down -v` trên dữ liệu cần giữ. CI dùng volume thử và tự cleanup, không phải lệnh vận hành.
- PostgreSQL16 đã kiểm chứng hủy hai luồng; không coi đó là load test hoặc chứng minh mọi deadlock. SQLite không có row locks tương đương, có thể database locked khi ghi cạnh tranh.
- Chính sách raw ORM/admin/SQL còn các đường vượt dịch vụ ở F05; cần quản lý quyền và nguồn ghi. Không đưa hệ thống vào dùng thật trước khi nghiệm thu các rủi ro nghiệp vụ quan trọng.
- Chưa chạy migration, sửa dữ liệu, --fix, TLS/domain hay backup/restore trên dữ liệu thật trong các phiên này. Bằng chứng DB trống/test/demo/CI không thay thế việc đó.

## 8. Triển khai mới từ đầu bằng Docker Compose

Đích theo TU02: Ubuntu 24.04, Docker Engine và Compose v2 đã cài, có Git. Hướng dẫn cài Docker chi tiết nằm trong TRIEN_KHAI.md. Các lệnh dưới dành **DB mới**, không dùng để nâng thẳng DB cũ; DB cũ đi theo mục 5 trước khi web tự migrate. Dùng tag cuối thay nhánh TU02 trong tài liệu lịch sử.

### Lấy bản đóng gói và cấu hình lab

```bash
git clone https://github.com/MrTroll219/sales-and-inventory-management.git
cd sales-and-inventory-management
git checkout v1-bao-tri
umask 077
cp .env.example .env
# Sinh secret/password vào file riêng, không đưa giá trị ra log hoặc commit.
sudo docker run --rm -i -v "$PWD:/work" -w /work python:3.12-slim python - <<'PY'
from pathlib import Path
import secrets
p = Path('.env')
s = p.read_text()
s = s.replace('SECRET_KEY=\n', 'SECRET_KEY=' + secrets.token_urlsafe(64) + '\n')
s = s.replace('DB_PASSWORD=\n', 'DB_PASSWORD=' + secrets.token_urlsafe(32) + '\n')
p.write_text(s)
PY
chmod 600 .env
sudo docker compose config --quiet
sudo docker compose build
sudo docker compose up -d --wait --wait-timeout 180
sudo docker compose ps
curl -I http://127.0.0.1:8000/accounts/login/
curl -I http://127.0.0.1:8000/images/profile_pics/default.jpg
sudo docker compose exec web python manage.py createsuperuser
sudo docker compose exec web python manage.py check
sudo docker compose exec web python manage.py makemigrations --check --dry-run
sudo docker compose exec web python manage.py check_decimal_data
sudo docker compose exec web python manage.py check_vnd_data
sudo docker compose exec web python manage.py reconcile_stock
```

Mong đợi db/web/nginx healthy; login 200, JPEG 200 đúng Content-Type. Entrypoint đợi DB, seed ảnh mặc định còn thiếu, check Profile cũ nếu bảng có, migrate rồi chạy Gunicorn non-root. collectstatic chỉ chạy lúc build; WhiteNoise phục vụ static, nginx phục vụ /images/ từ media read-only; web chỉ expose nội bộ.

.env.example dùng DEBUG=false, SSL=false và bind loopback 127.0.0.1:8000 cho lab HTTP nội bộ. Truy cập từ xa bằng SSH tunnel `ssh -L 8000:127.0.0.1:8000 user@server`. Không mở cấu hình lab thành endpoint production công khai.

### Production HTTPS và dữ liệu

- Sửa ALLOWED_HOSTS/CSRF_TRUSTED_ORIGINS theo domain thật; đặt DJANGO_SECURE_SSL=true; giữ secret ngẫu nhiên riêng và password DB đủ mạnh. TLS kết thúc ở reverse proxy tin cậy phía trước nginx; proxy xóa header client và tự đặt X-Forwarded-Proto. Không cho client không tin cậy truy cập trực tiếp qua proxy-header path.
- HSTS thử 3600; chỉ bật include-subdomains/preload khi toàn domain/subdomain đáp ứng chính sách. Khi đã chắc HTTPS ổn định mới tăng 31536000. `check --deploy` 0 issues của CI không tự cấp chứng chỉ hay chứng minh TLS thật hoạt động.
- Sau sửa env: `sudo docker compose up -d --wait`, rồi `sudo docker compose exec web python manage.py check --deploy`; kiểm tra login/CSRF/ảnh/đăng xuất qua HTTPS thật.
- DB dùng pgdata, upload dùng media. Ảnh upload cũ dưới static/images phải được sao lưu và copy đúng đường dẫn tương đối sang media theo TRIEN_KHAI.md; không chuyển toàn bộ logo/static hoặc ghi đè ảnh đích. Entrypoint chỉ tự tạo avatar mặc định thiếu.
- Thử restart trên dữ liệu demo với `sudo docker compose down` rồi `sudo docker compose up -d --wait`; **không thêm -v**. Lập lịch backup, retention và diễn tập restore riêng trước khi nhập dữ liệu thật.
- Nghiệm thu nghiệp vụ: tạo hàng/phiếu nhập/đơn bán, kiểm tra VND/giờ Việt Nam, lọc và export, đặt ngưỡng, hủy đơn, đối soát sổ; xác nhận các giả định mục 7 và xử lý rủi ro cao còn mở.

## 9. Hồ sơ bàn giao và kết luận phạm vi

- `evidence/final/`: toàn bộ log lệnh local, coverage gốc/cuối, metadata ancestor/nhánh, migration plan, lịch sử test, CI đúng SHA và Docker smoke.
- Các ảnh nghiệp vụ theo yêu cầu nằm trong evidence/hc01, hc02, hc03, tu01, tu03, ht01, ht02, ht03; ảnh login container cuối trong evidence/final/ci/compose-health-persistence/login.png.
- 11 yêu cầu đã có commit truy vết và ancestor đầy đủ; bản nguồn 123101a đã vượt các kiểm chứng đã nêu. Tag v1-bao-tri chỉ đóng gói cùng nguồn ứng dụng với báo cáo/bằng chứng mới.
- Người dùng cần kiểm tra fork/tag, duyệt các giả định và lỗi mở, chạy bản sao dữ liệu thật cùng backup/restore và nghiệm thu môi trường production. Không có hành động triển khai dữ liệu thật hoặc PR trong FINAL.
