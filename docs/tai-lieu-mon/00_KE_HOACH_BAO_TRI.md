# 00. KẾ HOẠCH BẢO TRÌ PHẦN MỀM

Đề tài: **Bảo trì và hoàn thiện hệ thống quản lý bán hàng và tồn kho trên nền tảng Django**. Kế hoạch này hệ thống hóa quy trình đã áp dụng trong bài tập Project 2 và các bước nhóm còn phải chuẩn bị để bàn giao. Nó không thay thế báo cáo kết quả kiểm chứng. Thông tin nhân sự, lịch cam kết và chi phí thực tế cần nhóm xác nhận; các ước lượng bên dưới chỉ phục vụ lập kế hoạch học thuật.

## Hồ sơ tài liệu và hướng dẫn đọc

Tài liệu được biên soạn cho nhóm bảo trì, người phản biện và giảng viên học phần Bảo trì phần mềm. Người đọc nghiệp vụ tập trung vào hiện trạng, hành vi mong muốn và bằng chứng; người triển khai đọc thêm kiến trúc, migration và ràng buộc. Phạm vi là 11 yêu cầu trên hệ thống bán hàng và tồn kho Django; không bổ sung chức năng ngoài phạm vi đã thực hiện.

| Phiên bản | Ngày | Người chuẩn bị | Nội dung cập nhật |
|---|---|---|---|
| 1.0 | 28/11/2026 | Nhóm Nguyễn Đức Khang, Châu Trường Phúc, Nguyễn Trường Thịnh | Hồ sơ kỹ thuật và bản Word ban đầu, commit 31668be |
| 1.1 | 28/11/2026 | Nhóm Nguyễn Đức Khang, Châu Trường Phúc, Nguyễn Trường Thịnh | Bổ sung cấu trúc theo mẫu Project 2, xuất Word A4; chưa có chữ ký phê duyệt của nhóm |

Quy ước: **[GIỮ]** là nội dung kế thừa; **[SỬA]** là điều chỉnh chức năng đang có; **[MỚI]** là nội dung bổ sung. Mã HC/TU/HT/DP liên kết yêu cầu bảo trì; FR/NFR là tiêu chí chức năng/phi chức năng; TC là trường hợp kiểm thử. Những mã FR/NFR/TC được đặt trong bộ hồ sơ này, không giả định phần mềm gốc đã có đặc tả với các mã tương tự.

| Thuật ngữ | Giải thích |
|---|---|
| Baseline | Mốc đối chiếu cố định v0-goc; không đồng nhất với main hiện tại của tác giả |
| Migration / preflight | Chuyển schema, dữ liệu / kiểm tra dữ liệu trước chuyển đổi |
| Atomic / rollback | Ghi toàn bộ giao dịch hoặc phục hồi toàn bộ khi thất bại |
| Ledger / StockMovement | Sổ ghi biến động tồn kho dùng để đối soát |
| CI / coverage | Kiểm chứng tự động / tỷ lệ dòng mã được thực thi, không đồng nghĩa chứng minh hết lỗi |

Nguồn biểu mẫu: bộ Project 2 do môn học cung cấp, gồm Yeucau_Project2.pdf, KehoachBT.pdf, Phantichsutacdong.pdf, DactaYCTD.pdf, ThietkeYCTD.pdf, Tài liệu kiểm thử.docx và Vidu_Dacta_Thietke.pdf. Mẫu kiểm thử ghi học kỳ 3 năm 2024–2025; đây là thông tin của mẫu, không dùng làm học kỳ thực tế của nhóm. Ngày và người phê duyệt nghiệp vụ chưa có hồ sơ riêng, không suy diễn từ trạng thái test PASS.

## 1. Giới thiệu và mục tiêu

Sản phẩm nguồn mở sales-and-inventory-management của munuhee được fork tại MrTroll219/sales-and-inventory-management. Đường cơ sở là tag v0-goc, commit 038cbd5a7e3f4bdfab96f7f9d61016d1d2ea2dc4. Mục tiêu bảo trì là sửa sai tồn và tiền, thích ứng nền tảng và Việt Nam, bổ sung hỗ trợ nhập hàng/lọc/hủy đơn, giảm rủi ro phát sinh bằng dịch vụ kho và ràng buộc dữ liệu.

Phạm vi gồm 3 yêu cầu hiệu chỉnh HC01–HC03, 3 thích ứng TU01–TU03, 3 hoàn thiện HT01–HT03, 2 dự phòng DP01–DP02. P0 là hoạt động khảo sát, tạo bằng chứng lỗi và test hồi quy; không tính thành yêu cầu bảo trì thứ mười hai. Phạm vi dự án bao gồm cải thiện và tài liệu bàn giao; triển khai trên dữ liệu thật, chuyển tiền theo tỷ giá, vận hành máy chủ công cộng và huấn luyện người dùng thật chưa được nghiệm thu.

## 2. Tài liệu tham khảo và định nghĩa

Các thuật ngữ được giải thích ở hồ sơ tài liệu. Nguồn xác thực kết quả là docs/BAO_CAO_TONG_HOP.md, docs/HC01.md đến docs/HT03.md, evidence/final/ và lịch sử Git. Bộ mẫu môn học được cung cấp trong Project 2; không giả định mẫu có tác giả hoặc số hiệu phiên bản ngoài thông tin thể hiện trên tệp.

## 3. Tổ chức bảo trì và kênh giao tiếp

| Vai trò | Trách nhiệm | Kênh và sản phẩm giao tiếp |
|---|---|---|
| Chủ cửa hàng giả lập | Đề xuất HC01, HC03, HT03; xem tác động tới tồn/tiền/hủy | Phiếu yêu cầu, bước nghiệm thu nghiệp vụ |
| Nhân viên kho / kế toán giả lập | Đề xuất HC02, HT01, HT02 | Mô tả tình huống nhập/lọc/xuất, ảnh và workbook |
| Quản trị hệ thống giả lập | Đề xuất TU01–TU03; xác nhận môi trường | Nhật ký cấu hình, kiểm chứng CI/Docker |
| Điều phối bảo trì | Tiếp nhận, gán mã, phân công, quản lý thay đổi | Hồ sơ yêu cầu và bảng công việc nhóm |
| Người phân tích / thiết kế | Khang phụ trách phân tích; Phúc phụ trách thiết kế. So sánh phương án, đặc tả và thiết kế. | Tài liệu 01–03; nhận xét review |
| Người thực hiện / kiểm thử | Phúc phụ trách thực hiện; Thịnh phụ trách kiểm thử và báo cáo. Kiểm chứng và tổng hợp hồ sơ. | Commit, test, evidence và tài liệu 04 |
| Nhóm duyệt thay đổi | Quyết định phạm vi và bàn giao | Bảng phê duyệt; tên và ngày ký do nhóm điền |

Một thành viên có thể kiêm nhiều vai trò; nếu người viết tự kiểm tra phải ghi rõ, không tuyên bố kiểm thử độc lập khi không có người thứ hai. Giao tiếp kỹ thuật qua Git và tài liệu; trao đổi của nhóm qua kênh nhóm tự xác nhận. Không có bằng chứng họp, thời lượng họp hoặc chữ ký thì không ghi là đã thực hiện.

## 4. Kế hoạch làm việc và tài nguyên

### 4.1. Gói công việc và mốc kiểm soát

Thứ tự dưới đây khớp lịch sử đã thực hiện. Cột điều kiện kết thúc là mốc kỹ thuật, không phải ngày cam kết hoặc số giờ thực tế. Nhóm ghi người chịu trách nhiệm và ngày thực tế vào bảng phân công trong bản báo cáo ghép.

| Gói | Công việc và đầu ra | Vai trò phụ trách | Điều kiện kết thúc |
|---|---|---|---|
| P0 | Cài baseline, tái hiện hạn chế, ghi 7 test | Khảo sát và kiểm thử | Bằng chứng lỗi có mốc v0-goc |
| HC01–HC03 | Sửa kho, Excel, máy chủ tính tiền | Phát triển và kiểm thử | 7 test hồi quy P0 chuyển PASS sau HC03 |
| TU01–TU02 | Nâng Django, cấu hình Docker/nginx/PostgreSQL | Vận hành và phát triển | Migration sạch, CI và smoke có log |
| DP02 | Decimal và constraint, preflight | Thiết kế dữ liệu | Migration thử, kiểm chứng hai DB |
| DP01 | Tập trung dịch vụ kho, sổ biến động | Thiết kế và phát triển | Test kiến trúc và rollback đạt |
| TU03 | Giờ Việt Nam, VND, giao diện chính | Phát triển và kiểm thử | Tiền nguyên, export đúng giờ, migration đạt |
| HT01–HT03 | Ngưỡng, lọc, hủy và audit | Phát triển và kiểm thử | Chức năng và test đồng thời được kiểm chứng |
| FINAL | Kiểm chứng tích hợp, tài liệu, bàn giao | Điều phối và kiểm thử | Log cuối, báo cáo, tag v1-bao-tri |
| Nộp môn | Bổ sung thông tin nhóm, slide và demo | Toàn nhóm | File Word A4 đầy đủ; slide, demo do nhóm hoàn thiện |

### 4.2. Ước lượng phục vụ lập kế hoạch

Các khoảng công sức cho từng phương án nằm ở tài liệu 01. Đơn vị là giờ công; không phải thời gian thực hiện đo được từ Git. Ngày commit không chứng minh số giờ làm việc. Lịch hoàn thành của nhóm phải được xác lập sau khi phân công và xác định thời gian sẵn có.

Chi phí dự kiến được biểu diễn bằng C = H × R + I, với H là giờ công theo phương án, R là đơn giá giờ công do nhóm xác nhận và I là chi phí hạ tầng thực tế. Chưa có R và hóa đơn I nên không đưa tổng tiền VND. Không tự quy chi phí nhân công bằng 0 chỉ vì đây là bài tập.

### 4.3. Tóm tắt tài nguyên

| Nguồn lực | Cách sử dụng và giới hạn |
|---|---|
| Nhân sự | Cần năng lực Django/ORM, Git, test, migration, Docker; số người và tên theo nhóm thực tế |
| Máy tính | Môi trường local Windows PowerShell đã ghi trong evidence; không suy ra mọi máy nhóm giống nhau |
| Kiểm thử | Local SQLite và CI PostgreSQL16; Python 3.10/3.12 theo log cuối |
| Công cụ | Git/gh, Django, coverage, openpyxl, Playwright, Docker Compose, nginx, PostgreSQL; phiên bản đối chiếu báo cáo tổng hợp |
| Quyền truy cập | Push fork origin; không push upstream munuhee; không đưa secret thật vào Git |
| Dữ liệu | DB thử tách biệt; backup DB và MEDIA trước migration thật; không dùng --fix trên dữ liệu thật khi chưa có phê duyệt |
| Học và hỗ trợ | Người mới đọc docs/TRIEN_KHAI.md và tài liệu 01–04; chưa có hồ sơ huấn luyện người dùng thật |

## 5. Quy trình bảo trì

Quy trình được tổ chức theo tiếp nhận → phân tích → đặc tả/thiết kế → thực hiện → kiểm chứng → bàn giao. Đây là quy trình nội bộ áp dụng cho bài tập, không tuyên bố chứng nhận tuân thủ tiêu chuẩn quốc tế.

| Giai đoạn | Đầu vào | Công việc kiểm soát | Đầu ra |
|---|---|---|---|
| Khảo sát | Baseline, hướng dẫn sử dụng | Cài riêng, tái hiện lỗi, không sửa trước khi ghi bằng chứng | P0, ảnh/log và hiện trạng |
| Tiếp nhận | Phiếu khách hàng giả lập | Gán HC/TU/HT/DP, xác định ưu tiên và phạm vi | Phiếu tiếp nhận |
| Phân tích | Source, dữ liệu, ràng buộc | Ít nhất hai phương án, tác động, ước lượng, chọn phương án | Tài liệu 01 và quyết định phạm vi |
| Đặc tả/thiết kế | Yêu cầu được chọn | FR/NFR, trước/sau, giao diện, dữ liệu, truy vết | Tài liệu 02–03 |
| Thực hiện | Nhánh yêu cầu, thiết kế | Commit theo mã, migration, không sửa ngoài phạm vi | Source và test có truy vết |
| Kiểm chứng | Bản thay đổi, TC | Check, migration sạch, suite, CI, bằng chứng | Tài liệu 04 và log thật |
| Bàn giao | Bản tích hợp đã kiểm | Fast-forward theo phạm vi được duyệt, gắn tag, hướng dẫn | Fork, v1-bao-tri, báo cáo và rủi ro còn mở |

## 6. Quản lý cấu hình

v0-goc là mốc gốc bất biến; nhánh từng yêu cầu ghi riêng thay đổi; bao-tri tích hợp; tai-lieu-mon-hoc phục vụ hồ sơ học phần. Trạng thái code được kiểm chứng cuối là 123101a, tag đóng gói v1-bao-tri ở 1b06b13. Không đổi số này thành SHA tài liệu mới hoặc coi commit tài liệu là một lần chạy suite mới.

Mỗi đề xuất phải có mã, phân tích phạm vi, đặc tả, thiết kế và bằng chứng tương ứng. Commit mã nguồn mang tiền tố mã yêu cầu; tài liệu mang DOC. Thay đổi ngoài phạm vi ghi vào danh sách tồn đọng. Trước khi nhập nhánh phải kiểm ancestor và khả năng fast-forward; khi không thỏa thì dừng đánh giá, không tự gộp bất chấp xung đột. Secret lấy từ biến môi trường; dữ liệu thử và volume thật được phân biệt.

## 7. Quản lý chất lượng và rủi ro

Tiêu chuẩn nội bộ: test không cần mạng ở phần logic; không xóa/skip test để che lỗi; thay đổi schema có migration; không thay kỳ vọng cũ nếu chưa có chấp thuận; log thật giữ nguyên kết quả. Ngoại lệ lịch sử gồm đổi lời gọi test ở DP01 và kỳ vọng VND ở TU03 đã được ghi trong hồ sơ yêu cầu; không xem đó là quyền sửa tùy ý các test khác.

Tài liệu Word dùng Times New Roman, A4; có bìa, mục lục, phân công, phiên bản và nguồn. Review hồ sơ kiểm tính nhất quán mã yêu cầu, dữ liệu, test, số liệu và giới hạn. Rủi ro chính là mất phần lẻ khi chuyển tiền, dữ liệu thật không sạch, gián đoạn khi chuyển schema, thiếu backup, nguồn ghi vượt service và giả định nghiệp vụ chưa xác nhận. Biện pháp: sao lưu/thử khôi phục, preflight chỉ đọc, cửa sổ dừng ghi, thử trên bản sao và xác nhận quyền hủy/giá trị quantity=0 trước dùng thật.

## 8. Bàn giao và công việc nhóm còn phải xác nhận

Bàn giao gồm báo cáo Word A4, các tài liệu nguồn, mã trên fork, test/evidence, hướng dẫn triển khai. Nhóm còn phải xác nhận học kỳ, phân công và đánh giá đóng góp thật; chuẩn bị PowerPoint và kịch bản demo theo đề. Không ghi đã nộp elcit hoặc đã trình bày khi chưa thực hiện.

## Nguồn tham chiếu

- Bộ Project 2: Yeucau_Project2.pdf, KehoachBT.pdf và các mẫu tài liệu trong cùng thư mục; môn học cung cấp.
- [Báo cáo tổng hợp](../BAO_CAO_TONG_HOP.md), [môi trường baseline](../KE_HOACH_MOI_TRUONG.md), [hướng dẫn triển khai](../TRIEN_KHAI.md).
- [Metadata yêu cầu](../../evidence/final/requirements.json), [tiến trình test](../../evidence/final/test_history.json), [kết quả CI](../../evidence/final/ci_run.json).

- Bộ biểu mẫu Project 2 do học phần cung cấp: kế hoạch, phân tích tác động, đặc tả, thiết kế, kiểm thử; đối chiếu các mục tương ứng trong bản cập nhật 1.1.

- Thông tin trường theo trang bìa mẫu Tài liệu kiểm thử.docx; lớp CT244H – Bảo trì phần mềm theo người dùng; giảng viên Ph.D Huỳnh Quang Nghi và thành viên Nguyễn Đức Khang (B2303874), Châu Trường Phúc (B2303892), Nguyễn Trường Thịnh (B2303905) theo trang bìa DMTHINH.docx do người dùng cung cấp.

- Phân công theo xác nhận của người dùng trong phiên làm việc: Khang — phân tích; Phúc — thực hiện và thiết kế; Thịnh — kiểm thử và báo cáo. Mức hoàn thành, trách nhiệm và ngày phê duyệt chưa được nhóm đánh giá.
