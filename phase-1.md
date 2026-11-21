# Kế hoạch & Chia việc Phase 1 (Nhóm 6 người)

- **Mục tiêu:** Hoàn thành lõi Phase 1 (PRD-0) cho `gather` và `quan`, giữ nguyên Test Contract headless (tất định theo seed), có bộ test kiểm chứng + bằng chứng, điền đủ tài liệu bắt buộc và gắn tag `phase-1` trước mốc **1:00**.

## 1. Bảng chia việc 6 thành viên

| Thành viên (điền tên / handle) | Module & File phụ trách | Đầu việc Phase 1 | Phụ thuộc | Đầu ra / Kiểm chứng |
|---|---|---|---|---|
| **Người 1** (Dev Lead · dự phòng `sim/quan`) | `sim/gather`<br>`chonoi/sim/gather.py` | **Lát 1:** chuyển vùng `dive`/`surface`, oxy dưới nước/mặt nước, `oxygen_empty`, đếm ngạt & `choke` (-1 HP), `faint` (HP = 0 → `gather_end` `reason="fainted"`, giỏ rỗng), giỏ LIFO giới hạn `hold_capacity`.<br>**Lát 2:** hái nút ở mặt nước (`gather`/`hold_full`, đặt `regrow_ticks`), bắt cá khi dưới nước & hết cooldown (`fish_caught`/`hold_full`). | Chốt tên event trong `docs/contracts/README.md` | Unit/headless test cho toàn bộ luật `gather` pass, không làm gãy `test_smoke_p1.py`. |
| **Người 2** (Integrator · dự phòng `sim/gather`) | `sim/quan` (khách & hợp đồng)<br>`chonoi/sim/quan_customers.py`, `chonoi/sim/quan.py`, `chonoi/scenario.py`, `docs/contracts/README.md`, `game.contract.json` | Chốt hợp đồng tích hợp (`docs/contracts/README.md`), cập nhật `team`/`team_size: 6` trong `game.contract.json`.<br>**Lát 3:** khách dựng sẵn từ scenario + giữ chỗ nguyên liệu (`reserved`), khách mới theo lịch (`first_customer_tick`, `customer_interval_s`), `no_dish`, giảm kiên nhẫn & `customer_left`.<br>Bổ sung kiểm tra mâu thuẫn mức luật (mã thoát 2) trong `chonoi/scenario.py`.<br>Gắn tag `phase-1` khi nhánh chính xanh. | Đọc PRD-0 mục D, E, F | `tools/check_team.py` báo OK; test khách, giữ chỗ và scenario lỗi (exit 2) pass. |
| **Người 3** (PO · dự phòng Người 2) | `sim/quan` (bếp & phục vụ)<br>`chonoi/sim/quan_service.py`, `chonoi/sim/quan.py`, `docs/clarify.md` | Đọc PRD-0, hỏi giảng viên & ghi rõ giả định vào `docs/clarify.md`.<br>**Lát 4:** `interact` tối đa 1 lần/tick theo ưu tiên `(khoảng cách, bếp trước bàn, id)`, nấu (`cook_started`, `dish_ready`), bưng (`dish_picked`), phục vụ (`served`), ăn xong trả tiền (`paid`, tip, cập nhật uy tín), hết ca (`quan_end`). | Chốt cấu trúc `customer`/`stove` với Người 2 | Test luồng nấu → bưng → phục vụ → trả tiền + tip + uy tín pass. |
| **Người 4** (Demo Lead · dự phòng `harness/ops`) | `client/ui`<br>`chonoi/web/index.html` (chỉ đọc snapshot) | Nâng cấp giao diện chơi thử `chonoi.live`: hiển thị HUD đầy đủ cho `gather` (oxy, HP, giỏ, thời gian, trạng thái nút/cá) và `quan` (bếp, bàn, khách, kiên nhẫn, món trên tay, tiền, uy tín).<br>Giữ sạch nguyên tắc: không sửa logic sim, sáng tạo hình ảnh tắt hoàn toàn ở headless. | Snapshot schema từ Người 1, 2, 3 | Chạy được `python3 -m chonoi.live --mode gather` và `--mode quan`, chơi thử mượt. |
| **Người 5** (QA Lead · dự phòng `client/ui`) | `qa`<br>`tests/test_gather.py`, `tests/test_quan.py`, `tests/test_scenario_rules.py`, `docs/proof/phase-1/`, `docs/verification/phase-1.md` | Viết test hộp đen (chạy `headless_cmd`) & unit test bám từng AC của PRD-0 (bao gồm determinism 2 lần chạy giống từng byte).<br>Lưu đầu ra mẫu / log test vào `docs/proof/phase-1/` và điền bảng truy vết `docs/verification/phase-1.md` trung thực. | Hợp đồng event từ Người 2 | Toàn bộ `unittest discover -s tests -v` pass; `docs/verification/phase-1.md` đủ link bằng chứng. |
| **Người 6** (Scrum/Release · dự phòng `qa`) | `harness/ops`<br>`AGENTS.md`, `.agents/skills/`, `TEAM.md`, `docs/standup.md`, `docs/ai-usage-log.md`, `CHANGELOG.md`, `CREDITS.md` | Điền `TEAM.md`, cập nhật `AGENTS.md` cho Phase 1, viết tối thiểu 2 skill trong `.agents/skills/` (vd: kiểm tra Test Contract & determinism, tạo proof/verification).<br>Điều phối standup giữa phase (`docs/standup.md`), nhắc cả nhóm ghi `docs/ai-usage-log.md` và `docs/members/<handle>.md` (mỗi người ≥ 3 commit). Hỗ trợ code/test khi có người nghẽn. | Danh sách tên + GitHub handle 6 người | `AGENTS.md` cập nhật, có ≥ 2 skill hoạt động, tài liệu quy trình đầy đủ trước giờ tag. |

## 2. Nhịp triển khai 60 phút Phase 1

- **0:00 – 0:15 (Kickoff):** Điền `TEAM.md` + `game.contract.json` (`check_team.py` pass); Người 2 chốt `docs/contracts/README.md`; Người 3 chốt câu hỏi PRD-0 vào `docs/clarify.md`.
- **0:15 – 0:45 (Code song song):** Người 1 làm `gather.py`, Người 2 & 3 tách hàm ở `quan_customers.py` / `quan_service.py` rồi nối vào `quan.py`, Người 4 làm UI, Người 5 viết test theo AC, Người 6 dựng skill & harness.
- **0:35 (Standup 2 phút):** Mỗi người ghi 1 dòng vào `docs/standup.md`; ai vướng > 10 phút gọi người dự phòng.
- **0:45 – 0:55 (Tích hợp & Kiểm chứng):** Gộp code vào `main`, chạy toàn bộ test + headless smoke, xuất `docs/proof/phase-1/` và hoàn thiện `docs/verification/phase-1.md`.
- **0:55 – 1:00 (Đóng Phase 1):** Cập nhật `docs/ai-usage-log.md`, `CHANGELOG.md`; Người 2 (Integrator) kiểm tra nhánh chính xanh và gắn tag `phase-1`.

## 3. Rủi ro & Cách giảm thiểu

- **Xung đột Git giữa Người 2 và Người 3 trong `quan.py`:** Tách logic ra `quan_customers.py` và `quan_service.py`; `quan.py` chỉ điều phối thứ tự gọi trong `step()`.
- **Sai khác giữa code và test ẩn:** Không hard-code số liệu ngoài `game.contract.json`; mọi RNG đi qua `Streams`; sắp danh sách bằng `sort_by_id`.
- **Thiếu commit cá nhân hoặc sai `TEAM.md`:** Người 6 kiểm tra `python tools/check_team.py` và số commit từng thành viên vào phút 0:45.
