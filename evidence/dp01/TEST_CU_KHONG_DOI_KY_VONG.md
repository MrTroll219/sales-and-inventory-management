# DP01 – Chứng minh chỉ đổi lời gọi test

Base: b72bf15. Mọi assertion và mọi literal dữ liệu của bốn file cũ giữ nguyên.

| File | Hàm/test đổi lời gọi | Assertions của file cũ/mới | Literal dữ liệu |
|---|---|---|---|
| transactions/tests/test_hc01_purchase_stock.py | PurchaseStockTests.purchase | 33/33, AST giống nhau | Giữ nguyên |
| transactions/tests/test_hc01_purchase_stock.py | PurchaseStockTests.test_reduce_quantity_changes_stock_by_difference | 33/33, AST giống nhau | Giữ nguyên |
| transactions/tests/test_hc01_purchase_stock.py | PurchaseStockTests.test_change_item_moves_old_and_new_quantities | 33/33, AST giống nhau | Giữ nguyên |
| transactions/tests/test_hc01_purchase_stock.py | PurchaseStockTests.test_repeated_unchanged_save_does_not_add_stock | 33/33, AST giống nhau | Giữ nguyên |
| transactions/tests/test_hc01_purchase_stock.py | PurchaseStockTests.test_stale_purchase_uses_current_database_quantity | 33/33, AST giống nhau | Giữ nguyên |
| transactions/tests/test_hc01_purchase_stock.py | PurchaseStockTests.test_reduce_below_sold_stock_rolls_back_purchase | 33/33, AST giống nhau | Giữ nguyên |
| transactions/tests/test_hc01_purchase_stock.py | PurchaseStockTests.test_change_item_with_consumed_stock_rolls_back_both_items | 33/33, AST giống nhau | Giữ nguyên |
| transactions/tests/test_hc01_purchase_stock.py | PurchaseStockTests.test_partial_description_save_ignores_unsaved_stock_fields | 33/33, AST giống nhau | Giữ nguyên |
| transactions/tests/test_hc01_purchase_stock.py | PurchaseStockTests.test_partial_quantity_save_updates_total_value | 33/33, AST giống nhau | Giữ nguyên |
| transactions/tests/test_hc01_purchase_stock.py | PurchaseStockTests.test_price_only_change_does_not_change_stock | 33/33, AST giống nhau | Giữ nguyên |
| transactions/tests/test_hc01_purchase_stock.py | PurchaseStockTests.test_empty_update_fields_does_not_save_or_change_stock | 33/33, AST giống nhau | Giữ nguyên |
| transactions/tests/test_hc01_purchase_stock.py | PurchaseStockTests.test_delivery_status_does_not_change_stock_policy | 33/33, AST giống nhau | Giữ nguyên |
| transactions/tests/test_hc_regression.py | MaintenanceRegressionTests.create_purchase | 12/12, AST giống nhau | Giữ nguyên |
| transactions/tests/test_hc_regression.py | MaintenanceRegressionTests.test_hc01_sua_mo_ta_khong_doi_ton | 12/12, AST giống nhau | Giữ nguyên |
| transactions/tests/test_hc02_dates.py | ExportAndFormTests.purchase | 40/40, AST giống nhau | Giữ nguyên |
| transactions/tests/dp02_support.py | ConstraintCase.setUpTestData | 3/3, AST giống nhau | Giữ nguyên |

Diff từng lời gọi nằm trong [legacy_calls_diff.patch](legacy_calls_diff.patch).
Các helper purchase()/create_purchase()/ConstraintCase.setUpTestData thay API tạo dữ liệu; các test gọi helper giữ nguyên thân hàm/assertions.
Không sửa fixture migration TU01/DP02. Test migration DP01 mới tự phục hồi schema của chính nó.
