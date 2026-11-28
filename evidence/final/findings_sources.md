## docs/DP01.md:225

  row locks. Chưa kiểm thử tải đồng thời thực tế.
- Item.get_absolute_url gọi item-detail và log Bill.slug là lỗi tồn đọng đã ghi ở
  DP02; không sửa trong DP01.

## docs/DP02.md:196

- Không tự sửa dữ liệu thật. Không thay Purchase.save()/SaleCreateView, không làm DP01.
- Bill.slug có log cảnh báo cũ khi populate_from date chưa có lúc insert; không sửa
  ngoài phạm vi DP02. Các test không skip và không sửa kỳ vọng để xanh.
- Item.get_absolute_url() còn gọi tên URL item-detail trong khi route hiện dùng
  product-detail; ghi nhận lỗi có sẵn, không sửa trong DP02.

Tham khảo xử lý sự kiện constraint chờ trong transaction:
[PostgreSQL16 SET CONSTRAINTS](https://www.postgresql.org/docs/16/sql-set-constraints.html).

## docs/DP02.md:198

  ngoài phạm vi DP02. Các test không skip và không sửa kỳ vọng để xanh.
- Item.get_absolute_url() còn gọi tên URL item-detail trong khi route hiện dùng
  product-detail; ghi nhận lỗi có sẵn, không sửa trong DP02.

Tham khảo xử lý sự kiện constraint chờ trong transaction:
[PostgreSQL16 SET CONSTRAINTS](https://www.postgresql.org/docs/16/sql-set-constraints.html).

## docs/HC01.md:165

  bước HC03/DP01. Xóa phiếu hoàn kho để DP01.
- Lỗi phụ đã biết: form datetime-local làm mất ngày giao khi chỉ sửa mô tả;
  WhiteNoise cảnh báo thiếu staticfiles; HC02/HC03 vẫn còn. Không sửa các lỗi đó.

## docs/HT01.md:143

- Giả định: đề xuất `max(min_stock_level*2-quantity,0)` nhằm đưa tồn về 2 lần ngưỡng; không tự tạo phiếu, không điền số lượng/giá/nhà cung cấp. Tồn bằng ngưỡng vẫn cảnh báo dù cột thiếu bằng 0; nhập đủ để hết cảnh báo phải làm tồn lớn hơn ngưỡng. Ngưỡng 0 luôn tắt cảnh báo.
- Phát hiện thêm (không sửa): Item.get_absolute_url gọi item-detail trong khi route là product-detail; cảnh báo/log Bill.slug với populate_from date; cột nhãn đơn giá của purchases_list dùng total_value; thông tin công ty demo và một số phần giao diện cũ phụ thuộc CDN còn tồn tại từ trước.
- Khi test không có staticfiles, WhiteNoise vẫn phát UserWarning “No directory at .../staticfiles/”; không phải test lỗi và không thay đổi cấu hình ngoài HT01.

## docs/HT02.md:157

- Giả định: khoảng tiền là grand_total, tổng phiếu nhập là total_value; hai biên ngày đều tính ngày lịch Việt Nam; query không được hỗ trợ bỏ qua; tham số đã biết sai thì không hiển thị/xuất dữ liệu; chỉ lọc trạng thái giao P/S, không lọc trạng thái đơn của HT03.
- Phát hiện thêm (không sửa): cột nhãn đơn giá trong purchases_list đang hiển thị total_value; Item.get_absolute_url gọi item-detail thay vì product-detail; log Bill.slug; nhãn tiếng Anh/định dạng phần giao diện cũ phụ thuộc CDN.
- Tiện ích Excel cũ/openpyxl làm tròn đến mili giây khi đọc lại: timestamp 23:59:59.999999 có thể hiện 00:00 hôm sau trong file, trong khi điều kiện lọc vẫn đúng theo timestamp DB. Không thay tiện ích chung ngoài phạm vi HT02.
- WhiteNoise UserWarning khi test không có staticfiles vẫn tồn tại từ trước; không ảnh hưởng kết quả suite.

## docs/HT03.md:205

- Ghi trực tiếp DB hoặc ORM ngoài service vẫn có thể phá tương quan status/audit; không thêm trigger xuyên bảng hoặc chặn mọi thao tác ORM. Admin status readonly và audit chỉ xem; các đường ghi nghiệp vụ dùng service.
- Phát hiện thêm (không sửa): Item.get_absolute_url route item-detail; log Bill.slug; cột đơn giá purchases_list hiển thị total_value; SaleAdmin.search_fields cũ dùng customer__name không tồn tại; thông tin công ty demo/CDN/nhãn tiếng Anh cũ; SaleDetail admin cũ còn cho sửa trực tiếp.
- Giới hạn openpyxl mili giây và WhiteNoise UserWarning khi thiếu staticfiles giữ nguyên như HT02.
- Không tích hợp bao-tri, không mở PR; dừng sau HT03.

## docs/TU03.md:231

- Windows chưa có Docker; container/PostgreSQL16 kiểm chứng trên CI Linux.
- Phát hiện thêm, không sửa: route item-detail của Item.get_absolute_url, log
  Bill.slug, cột nhãn đơn giá của purchases_list dùng total_value, thông tin địa chỉ/
  điện thoại mẫu của tác giả trên receipt. Một số trang phụ/nhãn vai trò còn tiếng Anh;
  TU03 này Việt hóa nhãn chính, không thay toàn bộ catalog hay dữ liệu doanh nghiệp.

Tài liệu chính thức đối chiếu:
[Django DecimalField](https://docs.djangoproject.com/en/5.2/ref/models/fields/#decimalfield),

## docs/TU03.md:232

- Phát hiện thêm, không sửa: route item-detail của Item.get_absolute_url, log
  Bill.slug, cột nhãn đơn giá của purchases_list dùng total_value, thông tin địa chỉ/
  điện thoại mẫu của tác giả trên receipt. Một số trang phụ/nhãn vai trò còn tiếng Anh;
  TU03 này Việt hóa nhãn chính, không thay toàn bộ catalog hay dữ liệu doanh nghiệp.

Tài liệu chính thức đối chiếu:
[Django DecimalField](https://docs.djangoproject.com/en/5.2/ref/models/fields/#decimalfield),
[Django timezone](https://docs.djangoproject.com/en/5.2/topics/i18n/timezones/),
