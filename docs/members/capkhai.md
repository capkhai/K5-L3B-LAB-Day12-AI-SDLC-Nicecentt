# capkhai — phản tư cá nhân

- **Tôi đã làm:** Chốt kickoff (`TEAM.md`, `game.contract.json`, `docs/plan/phase-1.md`, `docs/contracts/README.md`, `docs/clarify.md` — `f200323`); thêm `--extra-content` tắt ở headless (`7a5d7df`) và sprite/animation bơi (`351535b`); cài đặt Lát 1 & Lát 2 `chonoi/sim/gather.py` và `tests/test_gather.py` (`774b41d`, `1a4de23`); xử lý conflict tích hợp nhánh `nhungvo` (`c0684fc`) và `duhocsinh` vào `main`.
- **Tôi đã review:** Đối chiếu diff Lát 3 (`nhungvo`) với Lát 4 (`chur04`) và HUD/UI (`duhocsinh`), phát hiện lệch tên trường `dish`/`dish_id`, `patience_ticks`/`patience_ticks_left`, trùng trừ timer kiên nhẫn, và giữ nguyên animation bơi khi gộp `index.html`.
- **AI sai ở đâu và tôi phát hiện thế nào:** Khi chưa có toàn văn PRD-0, AI cài `gather.py` cho lấy 1 phần đàn `ca_linh` khi giỏ thiếu chỗ và đếm ngạt trễ 1 tick; phát hiện ngay khi đọc lại `docs/clarify.md` (#1–#4) của PO và sửa khớp 100% PRD-0.
- **Điều tôi học được:** Khóa sớm schema giữa các lát trong 15 phút đầu và có test hộp đen headless giúp phát hiện lệch hợp đồng cực nhanh khi tích hợp nhóm 6 người.
