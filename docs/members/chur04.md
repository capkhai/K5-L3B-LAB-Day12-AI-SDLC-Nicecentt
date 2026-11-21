# chur04 — Vũ Văn Chủ — Phase 1

- Phần việc đã thực hiện với Codex: lát 4 bếp → bưng → phục vụ → thanh toán, tiền/boa/uy tín, dọn đơn/đóng ca; nối `QuanSim.step`, bổ sung 28 test và [bằng chứng](../proof/phase-1/chur04-service.md). Vai PO: đối chiếu PRD-0 người dùng cung cấp, trả lời 8 câu trong [clarify](../clarify.md).
- Lát Phase 1 sau đó đã được merge qua PR #2, commit merge `52f0245` (đối chiếu git log). Yêu cầu ≥3 commit có nội dung trong cả buổi lab chưa được kiểm đếm tại đây.
- Review: Codex đã rà code, thứ tự event, payload và test; chưa có review chéo của thành viên nhóm, cần cập nhật link sau khi thực hiện.
- AI sai ở đâu: helper tạo customer trong test ban đầu truyền trùng `dish_id`, gây TypeError; sửa helper để trường fixture ghi đè mặc định. Bộ test chạy lại đạt. Lỗi `python3` trên Windows được tách khỏi lỗi luật, không đổi assertion để làm xanh.
- Điều học được để tự xác nhận: timer và tương tác cùng tick quyết định deadline; phải giữ `order_id` cùng món, chốt boa lúc phục vụ và chỉ thu tiền/cộng uy tín sau đó.

## Phase 2 — cập nhật 21/11/2026

- Thực hiện với Codex: vòng ngày, Shop, pause, input/CLI, kế hoạch ngày, quán chọn ghế nhỏ nhất và burn; [bằng chứng](../proof/phase-2/chur04/README.md).
- 34 test mới, toàn bộ 104 test đạt. Manifest chính còn v1.0; smoke day dùng cấu hình fixture trong bản sao, chưa xác nhận cả Phase 2.
- AI sai: tool proof ban đầu thiếu repo root trong sys.path; đã sửa và chạy lại đủ suite/CLI.
- Bàn giao: đã ghi điểm nối Nhung/Đạt trong clarify. Chưa có review chéo, commit/push/tag mới; giữ nhánh `2A202603873_VuVanChu`.
- Điều học được: tách tick ngoài khỏi gameplay, giữ ngữ cảnh event khi đổi pha, tách cấp đã mua khỏi cấp đang áp dụng.

## Phase 3 — lát 3 Quán

- Thực hiện với Codex: kho cá thể, hao tươi, giữ lại bằng id, giá chốt theo giả định người dùng cho phép, tích hợp burn và JSONL. [Bằng chứng](../proof/phase-3/chur04/README.md).
- 32 test mới; 136 test toàn repo đạt. Đã kiểm ngưỡng 30 và lỗi đổi số chính xác sang float làm hiển thị lại 30; giữ đủ precision khi xuất JSONL.
- Chưa ghép file/day/Gather/HUD v1.2. Chưa có human review; người dùng tự commit, không có commit/push/tag tự động.
