# HC03 - Bằng chứng trước/sau

Commit ứng dụng: `8a9aecf5b16726c8a2fe88b20e0206306783da54`.
Ban đầu: Item.price=100, tồn5; database demo riêng, không dùng dữ liệu thật.

| Ảnh sau (sau/) | Kịch bản | Trước P0b | Sau HC03 |
|---|---|---|---|
| [07_hc03_trang_tao_don.png](sau/07_hc03_trang_tao_don.png) | Trang tạo đơn, thuế cộng thêm | Trang tạo đơn, nhãn Tax Inclusive | HTTP200 |
| [08_hc03_tong_tien_gia_400.png](sau/08_hc03_tong_tien_gia_400.png) | Giá 0.01 / tổng 1 bị từ chối | HTTP200/success, lưu tổng1 | HTTP400 |
| [09_hc03_chi_tiet_don_dung.png](sau/09_hc03_chi_tiet_don_dung.png) | 2×100=200; thuế10%=20; tổng220 | Đơn giả tiền có tổng1 | HTTP200 |
| [10_hc03_chua_dang_nhap_401.png](sau/10_hc03_chua_dang_nhap_401.png) | Anonymous bị chặn, có CSRF hợp lệ | Anonymous tạo đơn success | HTTP401 |
| [11_hc03_so_luong_am_400.png](sau/11_hc03_so_luong_am_400.png) | Số lượng âm bị từ chối | HTTP500 do CHECK quantity | HTTP400 |

- Ảnh07–10 đối chiếu với evidence/truoc/07–10; ảnh11 bổ sung số lượng âm.
- Ảnh08 chạy nguyên scripts/hc03_console.js, chỉ thay ID; nhận HTTP400, không tạo đơn/trừ kho.
- Đơn hợp lệ được tạo bằng UI thật: chọn sản phẩm, quantity2, tax10%, trả250; JS hiển thị200/20/220; DB lưu tiền thừa30, tồn5→3.
- Khách đơn hợp lệ có last_name=None; trang và chọn khách hoạt động.
- Anonymous GET trang tạo đơn trả302 sang login; lấy CSRF từ form login để POST AJAX, nhận401, DB không đổi.
- Quantity=-3 trả400, DB không đổi. Snapshot trong sau/observations.json.
- Panel chỉ hiển thị phản hồi HTTP thật; không sửa giá trị nghiệp vụ trên trang.
- Múi giờ banner UTC+7; ứng dụng vẫn UTC. Server tự dừng; worktree demo được dọn sau kiểm tra.
