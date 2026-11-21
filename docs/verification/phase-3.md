# Phase 3 — kiểm chứng phần Quán (chur04)

Mã Q bên dưới là nhóm kiểm chứng nội bộ theo ticket được cung cấp, không phải mã AC do giảng viên cấp. Kết quả thuộc working tree, chưa phải commit gắn tag.

| Nhóm kiểm | Bằng chứng | Kết quả |
|---|---|---|
| Q1: stock cá thể/id/fresh, giữ cả hàng ươn, giữ chỗ bằng id, không trùng/thiếu công thức | test_quan_freshness: construct, missing/explicit reservations, bad stock/reserved | Đạt |
| Q2: hao tươi/giới hạn 0, ngưỡng 30 chính xác, spoiled theo id trước chín/cháy, không lặp event | test_quan_freshness: exact_30, threshold_tick, spoiled_order, float rendering | Đạt |
| Q3: phần giữ ươn thì thử đủ công thức lại theo thứ tự, không giữ một phần/chiếm đơn khác | test_quan_freshness: retry/release cases | Đạt theo cách chốt trong clarify |
| Q4: nấu tiêu cá thể, items kind/id, giá chốt/boa/thanh toán, burn và pause | test_quan_freshness: cook, exact_floor, frozen_price, served_paid, burn, paused | Đạt; công thức giá là giả định được người dùng cho phép |
| Q5: JSONL giữ fresh đủ chính xác, tọa độ vẫn 3 số, tất định | Hai run runner API + test JSONL | Đạt |
| Regression | [136 test](../proof/phase-3/chur04/tests.txt), không sửa test cũ | Đạt với launcher Python cục bộ trên Windows |
| File kho/day/Gather/HUD v1.2 và tag toàn nhóm | Chưa tích hợp các lát tương ứng | Chưa xác nhận |

Lệnh chạy lại, output, hash và giới hạn: [bàn giao Quán](../proof/phase-3/chur04/README.md). Bắt buộc kiểm lại file/day trên main sau khi ghép schema mới trước khi xác nhận DoD.
