# capkhai — phản tư cá nhân

- **Tôi đã làm:**
  - **Phase 1:** Chốt kickoff (`TEAM.md`, `game.contract.json`, `docs/plan/phase-1.md`, `docs/contracts/README.md`, `docs/clarify.md` — `f200323`); thêm `--extra-content` tắt ở headless (`7a5d7df`) và sprite/animation bơi (`351535b`); cài đặt Lát 1 & Lát 2 `chonoi/sim/gather.py` và `tests/test_gather.py` (`774b41d`, `1a4de23`); xử lý conflict tích hợp nhánh `nhungvo` (`c0684fc`) và `duhocsinh` vào `main`.
  - **Phase 2:** Tổng hợp `docs/prd-phase-2.md` & `docs/plan/phase-2.md`, nâng `game.contract.json` lên v1.1, cài `chonoi/sim/gather_fish.py` và `chonoi/sim/gather_monsters.py` (Cá Sấu Năm Chèo `M1`/`M2`), tích hợp toàn bộ PR nhóm và chốt tag `phase-2`.
  - **Phase 3:** Viết ADR đổi schema kho (`docs/adr/0001-phase3-item-freshness-v12.md`), hoàn thiện Contract v1.2 (độ tươi `Fraction` trong `chonoi/freshness.py`, kho cá thể ở `inventory.py`/`gather`/`quan`/`day`/HUD `index.html`, `CHANGELOG.md`, `docs/verification/phase-3.md`) và 3 mở rộng (`burn`, `snake` `M3`, `current` Dòng nước lũ) với 140/140 test PASS.
- **Tôi đã review:** Đối chiếu diff Lát 3 (`nhungvo`) với Lát 4 (`chur04`) và HUD/UI (`duhocsinh`), phát hiện lệch tên trường `dish`/`dish_id`, `patience_ticks`/`patience_ticks_left`, trùng trừ timer kiên nhẫn, và giữ nguyên animation bơi khi gộp `index.html`; kiểm tra tính tương thích giữa fixture P2 v1.1 và quy tắc kiểm `extensions` trong `contract.py`.
- **AI sai ở đâu và tôi phát hiện thế nào:**
  - Phase 1: Khi chưa có toàn văn PRD-0, AI cài `gather.py` cho lấy 1 phần đàn `ca_linh` khi giỏ thiếu chỗ và đếm ngạt trễ 1 tick; phát hiện nhờ đối chiếu `docs/clarify.md` (#1–#4) của PO và sửa khớp 100% PRD-0.
  - Phase 2–3: Phát hiện sai số dấu phẩy động `1e-15` làm Cá Sấu đổi waypoint trễ 1 tick ở tick 240 và `GatherSim.snapshot()` trả tham chiếu `self.pos` làm snapshot lưu trong bộ nhớ bị ghi đè khi kiểm thử dòng nước lũ `current`; đã sửa bằng `list(self.pos)` và dùng `Fraction` cho độ tươi.
- **Điều tôi học được:** Khóa sớm schema + viết ADR và hỗ trợ song song hai phiên bản trước khi bật breaking change giúp giữ nhánh `main` luôn xanh và phát hiện lệch hợp đồng cực nhanh khi tích hợp.
