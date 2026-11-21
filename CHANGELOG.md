# Changelog
## Unreleased

- Phase 3, lát 3 (`chur04`): thêm adapter Quán cho kho cá thể `{id,kind,fresh}`, giữ chỗ bằng id, hao tươi/`spoiled`, thử giữ lại và tiêu đúng cá thể khi nấu. Giá chốt theo giả định PO: `floor(giá menu × fresh trung bình / 100)`.
- Breaking change khi ghép v1.2: `quan.stock` đổi từ map đếm sang mảng cá thể, `customers[].reserved` đổi thành mảng id, `cook_started.items` đổi thành mảng cá thể; fixture phải đổi theo. JSONL giữ đủ độ chính xác của `fresh` tại ngưỡng 30.
- Nhánh legacy P1/P2 vẫn được giữ khi chưa có `tuning.freshness`; manifest chung chưa chuyển sang v1.2. Adapter file kho, Gather, day/Shop và HUD cần ghép ở các lát tương ứng.

- Phase 1 (`chur04`): triển khai bếp, bưng payload theo đơn, phục vụ, tiền/boa/uy tín và dọn quán khi hết ca; nối vào `QuanSim` theo thứ tự tick của PRD-0.
- Thêm 28 test lát 4, fixture/input/output headless tất định, câu trả lời PO và tài liệu bàn giao tích hợp.
