# ADR-0001: Chuyển đổi sang Kho Cá Thể & Độ Tươi (Contract v1.2 — Phase 3)

- **Trạng thái:** Chấp nhận (Phase 3 — TICKET-03)
- **Ngày, người quyết:** 21/11/2026 — Nhóm Nicecentt (`capkhai`, `nhungvo631-stack`, `chur04`, `duhocsinh4to10`, `thanhhy98`, `VThanh-Huy`)

## 1. Bối cảnh
Change Request TICKET-03 (“Mùa Nước Nổi”) thay thế kho đếm theo loại (`{"items":{"ca_loc":1}}`) bằng kho cá thể có id và độ tươi (`{"items":[{"id":"I1","kind":"ca_loc","fresh":100}]}`), áp dụng hao tươi theo tick ở cả `gather` (`0.5/s`) và `quan` (`0.25/s`), ngưỡng ươn `fresh < 30`, giữ chỗ theo danh sách id cá thể và chốt `base_price` theo trung bình độ tươi khi bắt đầu nấu.

## 2. Quyết định kỹ thuật
1. **Biểu diễn số học chính xác (`chonoi/freshness.py`):**
   - Dùng `Fraction` / quy đổi chính xác (`240` đơn vị/điểm tươi: `100.0 = 24000`, ngưỡng ươn `< 7200`, trừ `2` đơn vị/tick ở `gather` và `1` đơn vị/tick ở `quan`) khi tính hao tươi, so ngưỡng `< 30` trước khi làm tròn, và tính `base_price = floor(price * avg_fresh / 100)`.
   - Khi ghi JSON kho (`--inventory-out`): xuất `fresh` giữ đủ độ chính xác (số nguyên nếu chẵn, tối đa 6 chữ số thập phân nếu lẻ) để khi `quan --inventory` đọc lại không làm lệch nhánh tại ngưỡng `30`.
2. **Schema & Tương thích phiên bản (`contract_version`):**
   - `chonoi/inventory.py` hỗ trợ chọn schema theo `contract_version`: v1.2 chỉ chấp nhận mảng cá thể `{id, kind, fresh}`, trả mã `2` cho file kho đếm cũ, id trùng, kind lạ hoặc `fresh` ngoài `[0, 100]`.
   - Mọi cá thể mới cấp id qua `IdAllocator.new("I")` (tăng liên tục xuyên pha và Ngày trong `--mode day`).
3. **Thứ tự tích hợp để `main` luôn xanh:**
   - **Bước 1 (Adapter & Freshness helper):** Tạo `chonoi/freshness.py`, cập nhật `chonoi/inventory.py`, `chonoi/contract.py` (chấp nhận cả `"1.1"` và `"1.2"` cùng `tuning.freshness`).
   - **Bước 2 (Song song 3 lát):**
     - `gather` (`gather.py`, `gather_monsters.py`): `hold` là mảng cá thể, hao tươi đầu bước, phát `spoiled`, `lost` LIFO là mảng cá thể.
     - `quan` & `day` (`quan.py`, `quan_customers.py`, `quan_service.py`, `day.py`, `day_config.py`, `scenario.py`, `headless.py`): `stock` là mảng cá thể, `reserved` là mảng id, hao tươi đầu bước + giữ lại 1 lần khi ươn, `base_price` theo trung bình fresh, `cook_started.items` là mảng cá thể sắp `(kind, id)`.
     - `client/ui` (`live.py`, `web/index.html`): đọc mảng cá thể cho `hold`/`stock`, hiển thị độ tươi & cảnh báo hàng ươn.
   - **Bước 3 (Bật v1.2 đồng bộ):** Đổi `game.contract.json` sang `"contract_version": "1.2"`, cập nhật `docs/contracts/inventory.sample.json`, `CHANGELOG.md` (breaking changes), chạy smoke 2 tiến trình + `--mode day` + regression, chốt `docs/verification/phase-3.md` và gắn tag `phase-3`.

## 3. Bảng phân tích tác động (Impact Matrix)

| Module | File cần đổi | Test bị ảnh hưởng | Người phụ trách |
|---|---|---|---|
| **Adapter & Freshness** | `chonoi/freshness.py` (mới), `chonoi/inventory.py`, `chonoi/contract.py`, `game.contract.json`, `docs/contracts/inventory.sample.json`, `docs/contracts/README.md` | `test_smoke_p1.py` (cập nhật schema kho cá thể + test kho đếm mã `2`), `test_monsters.py` (contract `1.2`) | Nhung (`nhungvo631-stack`) + Khải (`capkhai`) |
| **Lặn & Hái (`gather`)** | `chonoi/sim/gather.py`, `chonoi/sim/gather_monsters.py` | `test_gather.py` (cập nhật `hold`/`lost` cá thể + thêm test hao tươi, ngưỡng `30`, `spoiled`, LIFO), `test_monsters.py` (`lost` cá thể) | Khải (`capkhai`) |
| **Quán & Vòng ngày (`quan`, `day`, `scenario`)** | `chonoi/sim/quan.py`, `chonoi/sim/quan_customers.py`, `chonoi/sim/quan_service.py`, `chonoi/sim/day.py`, `chonoi/sim/day_config.py`, `chonoi/scenario.py`, `chonoi/headless.py` | `test_quan_service.py`, `test_chur04_phase2.py`, `test_python_starter_units.py` (chuyển fixture sang mảng cá thể + thêm test `spoiled` giữ lại 1 lần, `base_price` theo fresh, `day` cấp id xuyên Ngày) | Chủ (`chur04`) |
| **Giao diện (`client/ui`)** | `chonoi/live.py`, `chonoi/web/index.html` | `test_ui_live.py`, `test_live.py` (đọc `hold`/`stock` mảng cá thể, hiển thị độ tươi & hàng ươn) | Đạt (`duhocsinh4to10`) |
| **QA & Bằng chứng** | `tests/test_phase3_freshness.py` (mới), `docs/proof/phase-3/`, `docs/verification/phase-3.md` | Smoke bàn giao kho `gather → quan`, kiểm ngưỡng `fresh=30`, giữ lại 1 lần, chốt giá, kho đếm mã `2`, regression P1–P2 | Thành (`thanhhy98`) |
| **Harness, Changelog & Mở rộng** | `CHANGELOG.md`, `AGENTS.md`, `.agents/skills/`, `README.md`, `docs/standup.md`, `docs/retro.md`, `docs/ai-usage-log.md` | Nâng `check-contract` & `prepare-proof` kiểm v1.2 + `--mode day`; bật ≥ 2 mở rộng (`burn` + `snake`) + bằng chứng README | Huy (`VThanh-Huy`) |
