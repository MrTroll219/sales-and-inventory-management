# 02. ĐẶC TẢ YÊU CẦU BẢO TRÌ

Bộ tài liệu môn Bảo trì phần mềm – Project 2. Đề tài: **Bảo trì và hoàn thiện hệ thống quản lý bán hàng và tồn kho trên nền tảng Django**.

Phạm vi khảo sát là bản ứng dụng `123101a`, được đóng gói trong tag `v1-bao-tri` ở commit `1b06b13`; nhánh tài liệu kế thừa tag này. Các số liệu lấy từ `docs/BAO_CAO_TONG_HOP.md` và hồ sơ `evidence/final/`, không phải một lần chạy test mới của nhánh tài liệu. Mã FR/NFR/TC trong bộ tài liệu là định danh truy vết do tài liệu này quy định, không phải tên yêu cầu có sẵn trong code.


## 1. Quy ước và phạm vi đặc tả

Mỗi mệnh đề “phải” là tiêu chí kiểm chứng được tổng hợp từ yêu cầu/tiêu chí chấp nhận và hành vi đã được ghi nhận. FR mô tả chức năng; NFR mô tả tính nguyên tử, tính toàn vẹn, bảo mật, tương thích hoặc khả năng kiểm thử. Những chính sách thay đổi theo thời gian được nêu rõ mốc: tiền cent ở HC03/DP02, tiền nguyên VND ở bản cuối. Không biến các giả định chưa xác nhận cho vận hành thật thành quyết định đã được ký duyệt.

Tác nhân bao gồm người dùng đăng nhập, quản lý có quyền sửa hàng, nhân viên được cấp quyền hủy, superuser, người vận hành và CI. Phân quyền cụ thể của từng trang dùng mixin/decorator trong source; “quản lý” trong use case không tạo thêm một role model mới.

## 2. HC01 – Tồn kho phiếu nhập

| Mã | Đặc tả chức năng |
| --- | --- |
| FR-HC01-1 | Tạo phiếu số lượng 10 từ tồn 0 phải làm tồn bằng 10, không phải 20. |
| FR-HC01-2 | Sửa số lượng 10 thành 4 phải đưa phần tồn tương ứng về 4; lưu không đổi hoặc chỉ sửa mô tả không làm tăng kho. |
| FR-HC01-3 | Đổi mặt hàng phải thu hồi lượng cũ khỏi hàng cũ và cộng lượng mới vào hàng mới. |
| FR-HC01-4 | Khi việc giảm/đổi làm âm tồn, hệ thống phải báo lỗi trên form và giữ nguyên phiếu cùng tồn kho. |
| FR-HC01-5 | Thành tiền phiếu nhập được tính bằng đơn giá nhân số lượng. |

| Mã | Đặc tả phi chức năng |
| --- | --- |
| NFR-HC01-1 | Giao dịch nhập phải atomic; sử dụng khóa bản ghi và/hoặc F() để tránh ghi đè số dư. |
| NFR-HC01-2 | Không đổi schema ở mốc HC01; ba test HC01 trong P0 phải chuyển PASS. |
| NFR-HC01-3 | Không tự sửa số tồn lịch sử trên dữ liệu thật; đối soát chỉ là bước được cung cấp để người vận hành xem xét. |

**Nguồn:** [prompt HC01](../../../huong-dan-va-prompt-codex.md), [báo cáo HC01](../HC01.md). **Truy vết kiểm thử:** TC-HC01-* trong 04_KIEM_THU.md; không phải mỗi mệnh đề đều có một test độc lập, một test có thể chứng minh nhiều mệnh đề.

## 3. HC02 – Excel và ngày giao

| Mã | Đặc tả chức năng |
| --- | --- |
| FR-HC02-1 | to_excel_datetime phải trả None khi đầu vào None và giữ nguyên datetime naive. |
| FR-HC02-2 | Datetime aware phải được chuyển sang giờ cần hiển thị trước khi bỏ tzinfo. |
| FR-HC02-3 | Hai export phải dùng chung tiện ích cho ngày bán, ngày nhập và ngày giao; ô ngày giao NULL để trống. |
| FR-HC02-4 | Form sửa phiếu phải render value YYYY-MM-DDTHH:MM và nhận lại giá trị này mà không mất ngày giao. |
| FR-HC02-5 | Không có giao dịch vẫn xuất được file chỉ có dòng tiêu đề. |

| Mã | Đặc tả phi chức năng |
| --- | --- |
| NFR-HC02-1 | Cột ngày Excel dùng DD/MM/YYYY HH:MM; không để lỗi None gây HTTP 500. |
| NFR-HC02-2 | Giữ login_required cho export; test không cần mạng. |
| NFR-HC02-3 | Không đổi schema; việc chọn timezone toàn hệ thống thuộc TU03, không được lẫn với mốc HC02. |

**Nguồn:** [prompt HC02](../../../huong-dan-va-prompt-codex.md), [báo cáo HC02](../HC02.md). **Truy vết kiểm thử:** TC-HC02-* trong 04_KIEM_THU.md; không phải mỗi mệnh đề đều có một test độc lập, một test có thể chứng minh nhiều mệnh đề.

## 4. HC03 – Tính tiền máy chủ

| Mã | Đặc tả chức năng |
| --- | --- |
| FR-HC03-1 | Đơn giá phải lấy từ Item.price trong DB; price do client gửi không được dùng làm nguồn tính tiền. |
| FR-HC03-2 | Gộp các dòng trùng item trước kiểm tra tồn; quantity phải nguyên dương, thuế trong khoảng 0 đến 100. |
| FR-HC03-3 | Tính sub_total, tax_amount, grand_total, amount_change tại máy chủ theo thuế cộng thêm. |
| FR-HC03-4 | Thanh toán thiếu, tổng khai sai hoặc dữ liệu đầu vào sai phải trả JSON lỗi 400 và không thay DB. |
| FR-HC03-5 | AJAX chưa đăng nhập phải nhận JSON 401; request thường chuyển đến login. |
| FR-HC03-6 | Khách không có last_name vẫn render được trang tạo đơn. |

| Mã | Đặc tả phi chức năng |
| --- | --- |
| NFR-HC03-1 | Tạo Sale, SaleDetail và trừ kho phải nằm trong cùng atomic transaction. |
| NFR-HC03-2 | Tính bằng Decimal; mốc HC03 làm tròn cent và dung sai 0.01, bản cuối áp VND và dung sai 0 theo TU03. |
| NFR-HC03-3 | CSRF vẫn được giữ; không coi lỗi hạ tầng bất ngờ là lỗi dữ liệu đã được xử lý. |

**Nguồn:** [prompt HC03](../../../huong-dan-va-prompt-codex.md), [báo cáo HC03](../HC03.md). **Truy vết kiểm thử:** TC-HC03-* trong 04_KIEM_THU.md; không phải mỗi mệnh đề đều có một test độc lập, một test có thể chứng minh nhiều mệnh đề.

## 5. TU01 – Nâng Django 5.2

| Mã | Đặc tả chức năng |
| --- | --- |
| FR-TU01-1 | Phiên bản chạy phải là Django 5.2.x; phiên bản đã được kiểm chứng trong dự án là 5.2.19. |
| FR-TU01-2 | collectstatic dùng CompressedManifestStaticFilesStorage phải tạo staticfiles.json và asset băm. |
| FR-TU01-3 | Storage mặc định phải tiếp tục lưu/đọc media. |
| FR-TU01-4 | Cung cấp preflight chỉ đọc phát hiện email trùng kể cả chuỗi rỗng, email quá 150 và tên quá 30 ký tự. |
| FR-TU01-5 | Migration accounts/0002 chạy được trên DB trống và dữ liệu demo hợp lệ, không tự gộp/sửa dữ liệu. |

| Mã | Đặc tả phi chức năng |
| --- | --- |
| NFR-TU01-1 | check và makemigrations --check --dry-run phải sạch từ TU01 trở đi. |
| NFR-TU01-2 | Suite chạy với DeprecationWarning/PendingDeprecationWarning là lỗi; không phát sinh lỗi tương thích từ mã dự án. |
| NFR-TU01-3 | Không nâng phụ thuộc ngoài phần bắt buộc; phải ghi đúng giới hạn Python/DB đã kiểm tại từng mốc. |

**Nguồn:** [prompt TU01](../../../huong-dan-va-prompt-codex.md), [báo cáo TU01](../TU01.md). **Truy vết kiểm thử:** TC-TU01-* trong 04_KIEM_THU.md; không phải mỗi mệnh đề đều có một test độc lập, một test có thể chứng minh nhiều mệnh đề.

## 6. TU02 – Docker, PostgreSQL16, nginx/MEDIA

| Mã | Đặc tả chức năng |
| --- | --- |
| FR-TU02-1 | Đọc DEBUG, SECRET_KEY, hosts/origins, DB và MEDIA_ROOT từ env; DB_* ưu tiên hơn AZURE_POSTGRESQL_* tương ứng. |
| FR-TU02-2 | Thiếu key hoặc key production yếu phải bị từ chối; SSL=true bật redirect/cookie/HSTS/proxy header. |
| FR-TU02-3 | Build image thu static một lần; khởi động chạy migrate rồi Gunicorn user app, không chạy collectstatic lại. |
| FR-TU02-4 | nginx phục vụ /images/ từ media read-only; cổng public thuộc nginx, web chỉ expose nội bộ. |
| FR-TU02-5 | DB/media phải còn sau down/up không xóa volume; avatar mặc định chỉ copy khi thiếu. |
| FR-TU02-6 | Khi test không có staticfiles, dùng StaticFilesStorage; production vẫn dùng manifest. |

| Mã | Đặc tả phi chức năng |
| --- | --- |
| NFR-TU02-1 | check --deploy với cấu hình SSL thử đúng phải 0 issues; HTTP nội bộ là ngoại lệ lab có chủ đích. |
| NFR-TU02-2 | CI chạy PostgreSQL16 và SQLite với Python 3.10/3.12, không tự deploy; workflow cũ chỉ manual. |
| NFR-TU02-3 | Phải công bố nơi thực sự chạy container; bằng chứng CI không đồng nghĩa đã triển khai VPS thật. |

**Nguồn:** [prompt TU02](../../../huong-dan-va-prompt-codex.md), [báo cáo TU02](../TU02.md). **Truy vết kiểm thử:** TC-TU02-* trong 04_KIEM_THU.md; không phải mỗi mệnh đề đều có một test độc lập, một test có thể chứng minh nhiều mệnh đề.

## 7. DP02 – Decimal và ràng buộc

| Mã | Đặc tả chức năng |
| --- | --- |
| FR-DP02-1 | Chuyển trường tiền Float sang Decimal qua Decimal(str(...)), round HALF_UP; nâng trường tiền cũ 10,2 thành 15,2 ở mốc DP02. |
| FR-DP02-2 | Invoice.quantity phải là số nguyên không âm; dữ liệu lẻ/âm phải bị chặn trước chuyển, không tự làm tròn. |
| FR-DP02-3 | DB phải chặn giá/tổng/tiền trả âm, thuế ngoài [0,100], Item.quantity âm, Purchase/SaleDetail.quantity không dương. |
| FR-DP02-4 | DB phải giữ grand_total=sub_total+tax_amount và amount_change=amount_paid−grand_total. |
| FR-DP02-5 | Preflight chỉ đọc và migration phải dừng với lỗi rõ khi dữ liệu không hợp lệ; các giá trị demo hợp lệ được chuyển có kiểm chứng. |

| Mã | Đặc tả phi chức năng |
| --- | --- |
| NFR-DP02-1 | Mỗi CHECK có test IntegrityError trên SQLite và PostgreSQL16; không chỉ dựa vào form. |
| NFR-DP02-2 | Giữ nguyên độ chặt hồi quy cũ; migration có thể replay từ schema v0. |
| NFR-DP02-3 | Coverage transactions tại mốc DP02 phải đạt ngưỡng 70% nêu trong prompt; số đo được dẫn nguồn, không tính test/migration. |

**Nguồn:** [prompt DP02](../../../huong-dan-va-prompt-codex.md), [báo cáo DP02](../DP02.md). **Truy vết kiểm thử:** TC-DP02-* trong 04_KIEM_THU.md; không phải mỗi mệnh đề đều có một test độc lập, một test có thể chứng minh nhiều mệnh đề.

## 8. DP01 – Tách dịch vụ kho, sổ kho

| Mã | Đặc tả chức năng |
| --- | --- |
| FR-DP01-1 | adjust_stock là điểm ghi số dư duy nhất, không cho âm và ghi movement với delta, số dư sau, reference, actor. |
| FR-DP01-2 | Tạo/sửa/xóa phiếu nhập phải đi qua service; sửa áp chênh lệch, đổi item xử lý cả hai số dư. |
| FR-DP01-3 | Xóa phiếu phải trừ lượng đã nhập; nếu gây âm thì từ chối và rollback. |
| FR-DP01-4 | Tạo đơn bán dùng compute_sale_totals của HC03, ghi Sale/Detail và SALE_OUT trong cùng transaction. |
| FR-DP01-5 | Purchase.save chỉ tính total_value, không thay kho. |
| FR-DP01-6 | reconcile_stock mặc định chỉ đọc; --fix mới đưa cache về ledger, không tạo lượng nhập/xuất giả và phải idempotent. |

| Mã | Đặc tả phi chức năng |
| --- | --- |
| NFR-DP01-1 | Mọi hàm service public có transaction.atomic; khóa item theo thứ tự ổn định và dùng F(). |
| NFR-DP01-2 | Có test kiến trúc phát hiện các kiểu ghi Item.quantity ngoài stock.py; không xem test tĩnh là chặn mọi SQL thủ công. |
| NFR-DP01-3 | Hồi quy cũ giữ kỳ vọng; thay lời gọi test sang service chỉ theo chấp thuận đã ghi trong docs/DP01.md. |

**Nguồn:** [prompt DP01](../../../huong-dan-va-prompt-codex.md), [báo cáo DP01](../DP01.md). **Truy vết kiểm thử:** TC-DP01-* trong 04_KIEM_THU.md; không phải mỗi mệnh đề đều có một test độc lập, một test có thể chứng minh nhiều mệnh đề.

## 9. TU03 – Giờ Việt Nam, tiếng Việt, VND

| Mã | Đặc tả chức năng |
| --- | --- |
| FR-TU03-1 | TIME_ZONE=Asia/Ho_Chi_Minh, LANGUAGE_CODE=vi, CURRENCY_CODE=VND; USE_TZ=True và DB giữ thời điểm aware. |
| FR-TU03-2 | to_vnd dùng ROUND_HALF_UP tới đồng; format_vnd(1250000) trả 1.250.000 ₫. |
| FR-TU03-3 | Đơn 3×33333, thuế 10% phải có sub 99999, thuế 10000, tổng 109999. |
| FR-TU03-4 | Các trường tiền dùng Decimal(15,0); MAX_MONEY=999999999999999; tax_percentage giữ scale 2. |
| FR-TU03-5 | Form từ chối giá 1000.5 với thông báo tiếng Việt; chấp nhận biểu diễn 1000.00 vì giá trị là số nguyên. |
| FR-TU03-6 | Export UTC 2026-01-01 17:30 phải hiển thị 02/01/2026 00:30, tiền numeric định dạng ₫. |
| FR-TU03-7 | Tổng client phải khớp chính xác, dung sai 0; migration không quy đổi tỷ giá Ksh/VND. |

| Mã | Đặc tả phi chức năng |
| --- | --- |
| NFR-TU03-1 | Preflight/migration dừng nếu round làm sai identities; không tắt CHECK hoặc tự tính lại hóa đơn lịch sử. |
| NFR-TU03-2 | Giữ độ chặt 22 CHECK DP02, bổ sung 15 CHECK miền VND và xác minh trên hai backend. |
| NFR-TU03-3 | Các nhãn chính theo tiếng Việt; không khẳng định mọi trang phụ đã Việt hóa hoàn toàn. |

**Nguồn:** [prompt TU03](../../../huong-dan-va-prompt-codex.md), [báo cáo TU03](../TU03.md). **Truy vết kiểm thử:** TC-TU03-* trong 04_KIEM_THU.md; không phải mỗi mệnh đề đều có một test độc lập, một test có thể chứng minh nhiều mệnh đề.

## 10. HT01 – Ngưỡng tồn tối thiểu

| Mã | Đặc tả chức năng |
| --- | --- |
| FR-HT01-1 | needs_restock đúng khi min_stock_level>0 và quantity<=min_stock_level. |
| FR-HT01-2 | Tồn 3/5 và 5/5 được liệt kê; 6/5 không; ngưỡng 0 luôn tắt. |
| FR-HT01-3 | Sắp theo mức thiếu giảm dần; hiển thị tên, danh mục, tồn, ngưỡng, thiếu, đề xuất và NCC. |
| FR-HT01-4 | Dashboard đếm đúng tập; sidebar có link; danh sách sản phẩm làm nổi bật dòng cần nhập. |
| FR-HT01-5 | Nút tạo phiếu nhập truyền ?item=<id> để chọn sẵn item; GET không tự ghi kho/phiếu. |
| FR-HT01-6 | Xuất toàn bộ danh sách cần nhập ra Excel, không chỉ trang hiện tại. |

| Mã | Đặc tả phi chức năng |
| --- | --- |
| NFR-HT01-1 | Danh sách/export yêu cầu đăng nhập; ngưỡng nguyên không âm, mặc định 0 cho dữ liệu cũ. |
| NFR-HT01-2 | Sửa riêng ngưỡng đi qua save_item nhưng không ghi quantity hoặc tạo bút toán kho. |
| NFR-HT01-3 | Sau bán/nhập/hủy phải phản ánh số dư hiện tại mà không cần lưu trạng thái cần nhập riêng. |

**Nguồn:** [prompt HT01](../../../huong-dan-va-prompt-codex.md), [báo cáo HT01](../HT01.md). **Truy vết kiểm thử:** TC-HT01-* trong 04_KIEM_THU.md; không phải mỗi mệnh đề đều có một test độc lập, một test có thể chứng minh nhiều mệnh đề.

## 11. HT02 – Lọc và xuất giao dịch

| Mã | Đặc tả chức năng |
| --- | --- |
| FR-HT02-1 | Sale lọc theo date_added: date_from/date_to, customer, q tên/sđt và min/max grand_total. |
| FR-HT02-2 | Purchase lọc theo order_date, vendor, item và delivery_status. |
| FR-HT02-3 | Ngày cuối bao gồm 23:59 giờ Việt Nam và loại 00:00 ngày tiếp theo; nhận dd/mm/yyyy và ISO. |
| FR-HT02-4 | List/export gọi chung filtered_transactions; số dòng Excel bằng toàn tập đã lọc, không có tham số thì xuất tất cả. |
| FR-HT02-5 | Giữ query string khi chuyển trang/xuất; filename có khoảng ngày đã chuẩn hóa. |
| FR-HT02-6 | Ngày đảo, ID/tiền/ngày sai phải hiện lỗi; export trả JSON 400 thay vì xuất tất cả. |

| Mã | Đặc tả phi chức năng |
| --- | --- |
| NFR-HT02-1 | Mới nhất trước, tie-break pk giảm; select_related tránh N+1 khi xuất. |
| NFR-HT02-2 | Tổng/count tính trước phân trang; export không mang giới hạn trang. |
| NFR-HT02-3 | Không thay schema và không ghi quantity/ledger; sau HT03 tổng Sale chỉ tính đơn COMPLETED. |

**Nguồn:** [prompt HT02](../../../huong-dan-va-prompt-codex.md), [báo cáo HT02](../HT02.md). **Truy vết kiểm thử:** TC-HT02-* trong 04_KIEM_THU.md; không phải mỗi mệnh đề đều có một test độc lập, một test có thể chứng minh nhiều mệnh đề.

## 12. HT03 – Hủy đơn, lịch sử, hoàn kho

| Mã | Đặc tả chức năng |
| --- | --- |
| FR-HT03-1 | Sale có COMPLETED/CANCELLED, đơn cũ mặc định COMPLETED. |
| FR-HT03-2 | Chỉ actor active là staff/superuser được hủy; reason ít nhất 5 ký tự sau trim. |
| FR-HT03-3 | Hủy A×2+B×3 phải hoàn A+2/B+3, ghi SALE_CANCEL và một audit đúng người/lý do/thời điểm. |
| FR-HT03-4 | Hủy lần hai phải báo SaleAlreadyCancelled và không thay kho/audit/ledger. |
| FR-HT03-5 | Detail/list hiển thị status, ẩn nút sau hủy; lịch sử hiển thị giờ Việt Nam. |
| FR-HT03-6 | Dashboard/tổng doanh thu loại CANCELLED; export giữ dòng lịch sử có cột trạng thái; filter thêm status. |
| FR-HT03-7 | Route xóa dùng int pk, chỉ superuser xóa đơn đã hủy; giữ audit với sale_reference sau xóa. |
| FR-HT03-8 | reconcile_stock không trừ đơn CANCELLED khi đối chiếu chứng từ. |

| Mã | Đặc tả phi chức năng |
| --- | --- |
| NFR-HT03-1 | Hủy atomic, select_for_update trên Sale, hoàn item theo thứ tự ID ổn định; lỗi bất kỳ phải rollback. |
| NFR-HT03-2 | OneToOne bảo đảm tối đa một audit/đơn còn tồn tại; actor PROTECT và admin audit chỉ đọc. |
| NFR-HT03-3 | Test hai luồng bắt buộc chạy PostgreSQL16; công bố skip duy nhất trên SQLite, không giả định SQLite có row locks. |

**Nguồn:** [prompt HT03](../../../huong-dan-va-prompt-codex.md), [báo cáo HT03](../HT03.md). **Truy vết kiểm thử:** TC-HT03-* trong 04_KIEM_THU.md; không phải mỗi mệnh đề đều có một test độc lập, một test có thể chứng minh nhiều mệnh đề.

## 13. Use case UC-HT01 – Theo dõi hàng cần nhập

**Tác nhân:** quản lý được phép sửa sản phẩm; người dùng đăng nhập xem danh sách. **Tiền điều kiện:** dữ liệu hàng tồn tại, hệ thống đã migrate HT01; các giao dịch kho qua DP01; actor có quyền trang tương ứng.

**Luồng chính:**
1. Quản lý mở sửa hàng, đặt min_stock_level nguyên không âm và lưu.
2. Hệ thống ghi metadata qua save_item, không thay tồn khi chỉ đổi ngưỡng.
3. Người dùng mở dashboard, thấy số hàng cần nhập và chuyển đến /products/low-stock/.
4. Hệ thống lọc min>0 và quantity<=min, sắp theo thiếu giảm dần, hiển thị đề xuất nhập.
5. Người dùng có thể xuất toàn tập hoặc bấm tạo phiếu nhập với item đã chọn ban đầu.
6. Phiếu nhập chỉ được ghi sau khi người dùng xác nhận qua quy trình nhập DP01; tải lại danh sách phản ánh tồn mới.

**Luồng phụ:** chưa đăng nhập thì redirect login; ngưỡng 0 tắt cảnh báo; số âm/lẻ/quá miền bị từ chối; ID item không hợp lệ không được điền sẵn; GET không tự tạo phiếu. Nếu tồn đổi sau khi trang được tải, service kiểm tra số dư hiện tại khi ghi.

**Hậu điều kiện:** ngưỡng đã lưu hoặc lỗi không làm đổi dữ liệu; báo cáo phản ánh số dư lúc query. Mức tồn bằng ngưỡng vẫn được cảnh báo dù cột thiếu là 0; để hết cảnh báo phải vượt ngưỡng.

## 14. Use case UC-HT02 – Lọc và xuất giao dịch

**Tác nhân:** người dùng đăng nhập. **Tiền điều kiện:** có thể có hoặc không có giao dịch; đã áp dụng HC02/TU03 cho định dạng Excel và HT02 cho bộ lọc.

**Luồng chính:**
1. Mở danh sách bán hoặc nhập, nhập khoảng ngày và tiêu chí liên quan.
2. Hệ thống validate form, chuyển biên ngày sang datetime aware giờ Việt Nam.
3. Queryset chung được lọc và sắp mới nhất trước; tính count/tổng trên tập đầy đủ rồi phân trang.
4. Khi chuyển trang, query string được giữ. Người dùng bấm Xuất Excel với cùng tham số.
5. Export gọi cùng hàm filtered_transactions, ghi toàn bộ tập phù hợp, không giới hạn trang, tên file dùng ngày đã validate.

**Luồng phụ:** tham số đã biết sai/đảo khoảng thì list hiện lỗi với tập rỗng và export trả JSON 400; không tham số thì trả toàn bộ; tập rỗng xuất tiêu đề; tham số không được hỗ trợ bị bỏ qua. Sau HT03, status được lọc và tổng doanh thu chỉ tính COMPLETED, còn count theo tập khớp.

**Hậu điều kiện:** không có biến động kho hay ghi giao dịch; Excel và list dùng cùng điều kiện. Chúng là hai request riêng nên không bảo đảm snapshot nếu có giao dịch mới xen giữa.

## 15. Use case UC-HT03 – Hủy đơn bán

**Tác nhân:** user active có is_staff hoặc is_superuser. **Tiền điều kiện:** đơn tồn tại; status COMPLETED; có quyền và token CSRF hợp lệ khi POST. PostgreSQL16 là môi trường đã chứng minh đồng thời.

**Luồng chính:**
1. Actor mở chi tiết hoặc danh sách và chọn Hủy đơn.
2. Hệ thống hiển thị form lý do; actor nhập ít nhất 5 ký tự sau trim rồi xác nhận.
3. Service mở atomic, khóa Sale, kiểm lại quyền/trạng thái; gộp các SaleDetail theo item.
4. Hoàn kho theo thứ tự item, ghi movement SALE_CANCEL tham chiếu Sale và actor.
5. Tạo một SaleCancellation, lưu dữ liệu hoàn, đổi status CANCELLED rồi commit.
6. Trang chi tiết hiện lý do, actor, thời điểm Việt Nam, ẩn nút hủy; dashboard/tổng doanh thu loại đơn, HT01 đọc lại số dư mới.

**Luồng phụ:** chưa đăng nhập redirect; user thường 403; sai CSRF 403; lý do thiếu/ngắn hiện lỗi; không có đơn 404. Nếu đơn đã hủy hoặc luồng thứ hai tới sau khi chờ khóa, báo SaleAlreadyCancelled trước hoàn kho. Lỗi bất kỳ bước ghi nào rollback cả kho, ledger, audit và status. Superuser chỉ được xóa đơn đã hủy; xóa giữ audit bằng SET_NULL và sale_reference, không hoàn thêm.

**Hậu điều kiện:** hoặc hoàn đúng một lần cùng audit/trạng thái nhất quán, hoặc mọi dữ liệu được giữ nguyên. Không tự thực hiện hoàn tiền. Audit giữ dữ liệu item_id/quantity, actor được PROTECT.

## 16. Ràng buộc dữ liệu và quy tắc liên miền

### 16.1. Tiền, thuế và lượng tử hóa

Mốc DP02 chuyển tiền về Decimal(15,2), còn TU03 đổi 15 trường tiền về Decimal(15,0); phần trăm thuế giữ Decimal(5,2). Công thức cuối:

- total_detail = to_vnd(price × quantity); sub_total = tổng dòng hợp lệ.
- tax_amount = to_vnd(sub_total × tax_percentage / 100).
- grand_total = sub_total + tax_amount; amount_change = amount_paid − grand_total.
- amount_paid >= grand_total; thuế trong [0,100]; giá/tổng/tiền trả không âm.
- MAX_MONEY cuối là 999999999999999; to_vnd dùng ROUND_HALF_UP, từ chối NaN/Infinity/bool.
- Không đổi tỷ giá Ksh sang VND; dữ liệu mất phần lẻ sau round không thể được phục hồi chỉ bằng rollback code.

Hai đẳng thức tổng/tiền thừa được giữ bằng CHECK dùng F và Round ở scale tương ứng. TU03 bổ sung CHECK nguyên/range cho miền VND; không nới 22 CHECK DP02. Form từ chối số lẻ, nhưng ở raw SQL PostgreSQL NUMERIC(15,0) có thể chuẩn hóa phần lẻ trước CHECK; không mô tả sai rằng hai backend đều phải IntegrityError cho raw 1000.5. Test TU03 ghi rõ SQLite chặn và PostgreSQL chuẩn hóa thành 1001.

### 16.2. Số lượng, kho và lịch sử

- Item.quantity >= 0; Purchase.quantity và SaleDetail.quantity > 0; Invoice.quantity nguyên không âm, bao gồm 0 theo giả định DP02 còn cần xác nhận nghiệp vụ.
- Chỉ adjust_stock được phép ghi Item.quantity trong các đường ghi ứng dụng đã tổ chức; transaction và StockMovement đi cùng nhau. Kiểm tra kiến trúc không thay thế việc quản lý quyền SQL/admin.
- Tạo/sửa/xóa phiếu dùng delta; đổi hàng xử lý cả hai mặt hàng; không cho rút quá số còn lại.
- Ledger là nguồn đối soát cache; opening/ADJUST có thể giải thích khác biệt so với nhập−bán. Sau HT03 chỉ trừ đơn COMPLETED khi đối chiếu chứng từ.
- Một Sale còn tồn tại có tối đa một SaleCancellation qua OneToOne; audit có thể sale=NULL sau xóa nhưng giữ sale_reference. reason không rỗng/ngắn, cancelled_by PROTECT.
- min_stock_level mặc định 0; needs_restock và đề xuất không ghi một trạng thái kho thứ hai.

### 16.3. Thời gian và truy cập

USE_TZ=True, TIME_ZONE Việt Nam; không cộng thủ công bảy giờ vào DB. Datetime được localtime trước khi bỏ tzinfo để ghi Excel. Khoảng lọc ngày gồm đầu ngày đến microsecond cuối ngày địa phương. Login/CSRF/quyền hủy/xóa phải được thực thi ở server, không chỉ ẩn nút.

## 17. Các giả định đã áp dụng và giới hạn chấp thuận

Những quy tắc đã được chốt trong yêu cầu và triển khai gồm thuế cộng thêm, tiền VND HALF_UP, dung sai 0, sử dụng dịch vụ kho, ngưỡng 0 tắt và điều kiện bằng ngưỡng vẫn cảnh báo. Đó là chính sách đã áp dụng cho bài tập. Không suy ra từ việc có code rằng mọi giả định vận hành đã được bên nghiệp vụ ký duyệt.

Các giả định được nguồn ghi rõ cần người vận hành/chủ hệ thống xác nhận trước dữ liệu thật: Invoice.quantity=0; nhập kho ngay khi lưu dù còn chờ giao; ledger là chuẩn khi --fix; công thức mục tiêu tồn gấp đôi ngưỡng; quyền hủy staff/superuser và chính sách giữ audit sau xóa; ý nghĩa giá mẫu Ksh không quy đổi; proxy TLS/domain/HSTS. Mục 7 báo cáo tổng hợp là danh mục đầy đủ theo từng yêu cầu. Bộ tài liệu không tự xác nhận thay cho chủ hệ thống.

Không sửa dữ liệu thật, chạy --fix, cấp quyền mới hoặc triển khai production trong công việc soạn tài liệu. Các mã FR/NFR là phương tiện truy vết cho nghiệm thu, không phải đề xuất mở rộng phạm vi đã làm.

## Nguồn tham chiếu

- [docs/BAO_CAO_TONG_HOP.md](../../docs/BAO_CAO_TONG_HOP.md)
- [docs/HC01.md](../../docs/HC01.md)
- [docs/HC02.md](../../docs/HC02.md)
- [docs/HC03.md](../../docs/HC03.md)
- [docs/TU01.md](../../docs/TU01.md)
- [docs/TU02.md](../../docs/TU02.md)
- [docs/DP02.md](../../docs/DP02.md)
- [docs/DP01.md](../../docs/DP01.md)
- [docs/TU03.md](../../docs/TU03.md)
- [docs/HT01.md](../../docs/HT01.md)
- [docs/HT02.md](../../docs/HT02.md)
- [docs/HT03.md](../../docs/HT03.md)
- [store/money.py](../../store/money.py)
- [transactions/pricing.py](../../transactions/pricing.py)
- [transactions/services/stock.py](../../transactions/services/stock.py)
- [transactions/services/purchases.py](../../transactions/services/purchases.py)
- [transactions/services/sales.py](../../transactions/services/sales.py)
- [transactions/filters.py](../../transactions/filters.py)
- [transactions/models.py](../../transactions/models.py)
- [transactions/tests/test_tu03_vnd.py](../../transactions/tests/test_tu03_vnd.py)
- [../huong-dan-va-prompt-codex.md](../../../huong-dan-va-prompt-codex.md): phần C, các mục Hiện trạng, Yêu cầu và Tiêu chí chấp nhận. Tệp ở thư mục cha, không thuộc Git của repo; liên kết có hiệu lực trong workspace đã cung cấp.
