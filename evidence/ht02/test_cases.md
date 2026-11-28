# HT02 – Bảng 25 test mới

File chung: `transactions/tests/test_ht02_filters.py`, lớp `TransactionFilterTests`.

| TC | Tên test | Dữ liệu vào | Mong đợi | Thực tế | Đạt |
|---|---|---|---|---|---|
| HT02-01 | test_vietnam_date_bounds_include_last_microsecond_exclude_next_midnight | 5 mốc UTC, 01–30/11 VN | Có đầu ngày và 23:59:59.999999; loại 00:00 hôm sau | Đúng mong đợi | PASS |
| HT02-02 | test_date_from_and_date_to_work_independently | Chỉ date_from hoặc date_to | Lọc độc lập đúng tập | Đúng mong đợi | PASS |
| HT02-03 | test_same_day_range_includes_2359_vietnam | 30/11–30/11 | Chỉ giao dịch cuối ngày 30/11 | Đúng mong đợi | PASS |
| HT02-04 | test_iso_dates_equal_vietnamese_dates | ISO và dd/mm/yyyy | Hai cách nhập trả cùng tập | Đúng mong đợi | PASS |
| HT02-05 | test_customer_and_combined_date_customer | customer A, rồi ngày + A | 3 dòng toàn kỳ, 2 dòng tháng 11 | Đúng mong đợi | PASS |
| HT02-06 | test_customer_search_full_name_phone_and_nullable_last_name | Tên đầy đủ, sđt, last_name NULL | Đúng khách; tìm không có trả rỗng | Đúng mong đợi | PASS |
| HT02-07 | test_money_range_is_inclusive_and_combines_with_customer | min/max, min riêng, max riêng | So sánh VND bao gồm hai biên | Đúng mong đợi | PASS |
| HT02-08 | test_purchase_vendor_item_status_and_combination | vendor, item, P/S, bộ lọc kết hợp | Đúng tập phiếu nhập | Đúng mong đợi | PASS |
| HT02-09 | test_no_parameters_returns_all_newest_first_in_list_and_excel | Không tham số | 5 dòng mới nhất trước; tên file cũ | Đúng mong đợi | PASS |
| HT02-10 | test_equal_timestamps_have_stable_pk_tiebreak | 5 đơn trùng timestamp | PK giảm dần để ổn định phân trang | Đúng mong đợi | PASS |
| HT02-11 | test_every_valid_filter_exports_exact_list_queryset | 4 tổ hợp sale/purchase | ID và số dòng Excel bằng toàn queryset list | Đúng mong đợi | PASS |
| HT02-12 | test_count_and_money_are_for_full_filtered_set | 3 giao dịch tháng 11 | Count 3, tổng 10.000 ₫ | Đúng mong đợi | PASS |
| HT02-13 | test_pagination_and_export_links_keep_query_and_totals_include_all_pages | 14 sale khách A, trang 2 | 4 dòng trang 2; tổng cả tập 17.000 ₫; Excel 14 dòng | Đúng mong đợi | PASS |
| HT02-14 | test_purchase_pagination_keeps_vendor_item_and_status | 13 purchase phù hợp, trang 2 | Giữ vendor/item/status; tổng 14.000 ₫ | Đúng mong đợi | PASS |
| HT02-15 | test_reversed_dates_show_error_and_export_400_not_all_data | date_from > date_to | Form lỗi, count 0, export JSON 400 | Đúng mong đợi | PASS |
| HT02-16 | test_invalid_parameters_are_errors_never_500 | customer=abc, min=xyz, NaN, âm/lẻ, ID quá lớn, ngày sai | Không 500; form lỗi, count 0, export 400 | Đúng mong đợi | PASS |
| HT02-17 | test_reversed_money_range_is_validation_error | min=3000,max=2000 | Hiện lỗi khoảng tiền | Đúng mong đợi | PASS |
| HT02-18 | test_blank_and_unknown_parameters_preserve_unfiltered_results | Trống hoặc key không hỗ trợ | Không thêm điều kiện, vẫn 5 dòng | Đúng mong đợi | PASS |
| HT02-19 | test_empty_result_has_zero_summary_and_header_only_excel | Từ 2030 không dữ liệu | Count/tổng 0, Excel chỉ tiêu đề | Đúng mong đợi | PASS |
| HT02-20 | test_filenames_include_normalized_date_range | Hai đầu hoặc chỉ đầu khoảng ngày | Filename ISO chuẩn hóa; phía thiếu là all | Đúng mong đợi | PASS |
| HT02-21 | test_excel_keeps_vietnam_time_headers_and_vnd_formats | UTC 16:59 ngày 30/11 | Excel 23:59 giờ VN, header (VND), number_format ₫ | Đúng mong đợi | PASS |
| HT02-22 | test_exports_use_one_joined_query_independent_of_row_count | Export 1 dòng và 5 dòng, cả hai loại | assertNumQueries(1) cho mỗi export | Đúng mong đợi | PASS |
| HT02-23 | test_list_querysets_join_related_objects_without_n_plus_one | Đọc customer/item/vendor từ queryset | assertNumQueries(1), không N+1 | Đúng mong đợi | PASS |
| HT02-24 | test_anonymous_cannot_list_or_export | Chưa đăng nhập, 4 URL | Redirect login | Đúng mong đợi | PASS |
| HT02-25 | test_filtering_and_export_never_write_inventory_or_ledger | Lọc/xuất cả hai loại | Quantity và số StockMovement không thay đổi | Đúng mong đợi | PASS |
