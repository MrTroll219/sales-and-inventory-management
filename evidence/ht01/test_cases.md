# HT01 – 21 test mới

Mỗi TC dưới đây PASS trên local SQLite và cả 4 matrix jobs SQLite/PostgreSQL16 Python3.10/3.12. Assertion đầy đủ nằm trong file tương ứng, kết quả thực tế trong suite.txt của từng job.

| TC | Test (file::class.method) | Kết quả |
|---|---|---|
| HT01-01 | store/tests/test_ht01_restock.py::RestockTests.test_boundaries_match_queryset_and_property | PASS |
| HT01-02 | store/tests/test_ht01_restock.py::RestockTests.test_zero_threshold_disables_warning_for_any_nonnegative_stock | PASS |
| HT01-03 | store/tests/test_ht01_restock.py::RestockTests.test_shortage_and_suggested_quantity_follow_formula | PASS |
| HT01-04 | store/tests/test_ht01_restock.py::RestockTests.test_large_threshold_formula_does_not_overflow_postgres_integer | PASS |
| HT01-05 | store/tests/test_ht01_restock.py::RestockTests.test_list_orders_by_shortage_descending | PASS |
| HT01-06 | store/tests/test_ht01_restock.py::RestockTests.test_sale_enters_list_and_purchase_to_target_leaves_it | PASS |
| HT01-07 | store/tests/test_ht01_restock.py::RestockTests.test_dashboard_count_and_link_match_list | PASS |
| HT01-08 | store/tests/test_ht01_restock.py::RestockTests.test_anonymous_list_export_and_dashboard_redirect | PASS |
| HT01-09 | store/tests/test_ht01_restock.py::RestockTests.test_purchase_prefill_is_initial_only_and_does_not_write | PASS |
| HT01-10 | store/tests/test_ht01_restock.py::RestockTests.test_invalid_prefill_is_ignored_without_server_error | PASS |
| HT01-11 | store/tests/test_ht01_restock.py::RestockTests.test_threshold_form_rejects_negative_fractional_and_overflow | PASS |
| HT01-12 | store/tests/test_ht01_restock.py::RestockTests.test_threshold_negative_is_rejected_by_model_and_database | PASS |
| HT01-13 | store/tests/test_ht01_restock.py::RestockTests.test_edit_threshold_only_does_not_change_stock_or_ledger | PASS |
| HT01-14 | store/tests/test_ht01_restock.py::RestockTests.test_threshold_edit_does_not_overwrite_stock_changed_after_form_validation | PASS |
| HT01-15 | store/tests/test_ht01_restock.py::RestockTests.test_omitted_threshold_preserves_old_value_and_new_item_defaults_to_zero | PASS |
| HT01-16 | store/tests/test_ht01_restock.py::RestockTests.test_product_edit_page_shows_threshold_and_can_disable_it | PASS |
| HT01-17 | store/tests/test_ht01_restock.py::RestockTests.test_only_low_stock_product_rows_are_highlighted | PASS |
| HT01-18 | store/tests/test_ht01_restock.py::RestockTests.test_excel_matches_live_list_has_vietnamese_headers_and_vn_timestamp | PASS |
| HT01-19 | store/tests/test_ht01_restock.py::RestockTests.test_empty_list_and_excel_are_valid | PASS |
| HT01-20 | store/tests/test_ht01_restock.py::RestockTests.test_export_includes_items_beyond_list_pagination_and_missing_vendor | PASS |
| HT01-21 | store/tests/test_ht01_migration.py::MinStockMigrationTests.test_existing_items_get_zero_threshold_without_stock_or_price_changes | PASS |
