# CHANGELOG

## [1.0.0] — Phase 4: Phát hành `v1.0.0` (`phase-4`, Contract `v1.3`)

### Thêm mới
- **Contract `v1.3`** ([`game.contract.json`](game.contract.json)): khai báo `bench_cmd` (`python3 -m chonoi.bench`) và `soak_cmd` (`python3 -m chonoi.soak`); gameplay, tuning, kho cá thể và JSONL giữ nguyên theo v1.2.
- **Benchmark có render `1280×720`** (`chonoi/bench.py`): đo cảnh buổi sáng lõi (Út Sen đứng yên ở bến, độ tươi, cá bơi, Cá Sấu Năm Chèo, hiệu ứng mặc định) với 3s làm nóng + 30s đo, xuất đủ 5 trường `avg_fps`, `p1_low_fps`, `frames`, `measured_s`, `load_ms` sang JSON.
- **Soak headless nhiều Ngày** (`chonoi/soak.py` + `DaySim(allow_extended_days=True)`): bot tất định chơi liên tục 10 Ngày (`gather -> quan -> shop`), lặp kế hoạch D1–D5 ở Ngày 6–10, giữ xuyên suốt tiền, tổng thu, uy tín, nâng cấp, số Ngày và ID cá thể.
- **Khả năng tiếp cận & Cảnh báo** (`chonoi/web/index.html`): đủ 3 cảnh báo bằng chữ và biểu tượng (`🐊 THỦY QUÁI!`, `🫧 OXY SẮP HẾT!` / `💨 HẾT HƠI!`, `💢 KHÁCH SẮP GIẬN!`) và **Chế độ tương phản cao (High Contrast)** (phím `C`, nút trên HUD & menu Pause, lưu trong `localStorage`).
- **Đóng gói & Pháp lý:** thêm `LICENSE` (MIT), rà soát `CREDITS.md`, thêm `tools/build_release.py` (tạo gói `chonoi-v1.0.0.zip` & `.tar.gz`), cập nhật `README.md` chạy từ clone sạch trong ≤ 3 lệnh, và hoàn thiện `docs/verification/phase-4.md`, `docs/retro.md`.

### Kiểm thử bổ sung
- `tests/test_phase4_v13.py`: kiểm Contract `v1.3`, `bench_cmd` (định dạng 5 trường + exit 2 với tham số sai), `soak_cmd` 10 Ngày tất định (`crashes == 0`, `days_completed == 10`, lặp kế hoạch D1–D5).
- `tests/test_ui_live.py`: kiểm sự hiện diện đủ 3 cảnh báo và chế độ tương phản cao trong `chonoi/web/index.html`.

---

## [0.3.0] — Phase 3: Mùa Nước Nổi (`phase-3`, Contract `v1.2`)

### Breaking Changes (Contract `1.1` → `1.2`)
- **`game.contract.json`**: nâng `contract_version` lên `"1.2"`, thêm khối `tuning.freshness` (`100 / 0.5 / 0.25 / 30`) và khai báo 3 mở rộng `"extensions": ["burn", "snake", "current"]`.
- **Schema kho cá thể:** đổi file kho, `gather.hold`, `quan.stock`, Shop `stock` từ map đếm sang mảng cá thể `[{"id": "I1", "kind": "...", "fresh": ...}]` (kho rỗng `{"items": []}`); file kho đếm v1.0/v1.1 trả mã thoát `2`.
- **Độ tươi, giữ chỗ & chốt giá:** `chonoi/freshness.py` dùng `Fraction` cho ngưỡng `fresh < 30` và `base_price = floor(menu_price * avg_fresh / 100)`; phát `spoiled` theo id; đơn có cá thể giữ vừa ươn nhả toàn bộ và thử giữ lại đúng 1 lần theo `(order_tick, table_id)`; `cook_started.data.items` sắp theo `(kind, id)`; `monster_hit`/`faint` rơi mảng cá thể LIFO.
- **3 phần mở rộng (`extensions`):** `current` (`chonoi/sim/gather_current.py`), `snake` (`M3` loài `ran`), `burn` (`quan.burn_s: 20`).
- **HUD v1.2:** hiển thị độ tươi (%) và cảnh báo hàng ươn (`ƯƠN`, `HÀNG ƯƠN`).

### Lý do cập nhật test cũ P1/P2
- `tests/test_smoke_p1.py`, `tests/test_gather.py`, `tests/test_monsters.py`, `tests/test_extensions.py`, `tests/test_ui_live.py`, `tests/test_python_starter_units.py`: chuyển fixture `hold`/`stock`/`reserved`/file kho rỗng sang schema mảng cá thể v1.2+ và kỳ vọng `M3` khi bật `snake`.
- `tests/test_quan_service.py`: `Service` tách `freshness` để giữ nguyên 25 test đơn vị v1.1; `HeadlessService` cập nhật kịch bản sang v1.2 (`money=70, score=370` do hao `1/240` ở tick 1).
- `tests/test_chur04_phase2.py`: `phase2_contract()` tách `freshness` để giữ nguyên bộ regression v1.1.

---

## [0.2.0] — Phase 2: Một ngày ở chợ nổi (`phase-2`, Contract `v1.1`)

- Chốt số liệu chuẩn v1.1: 6 nguyên liệu, 6 nút hái `N1–N6`, 6 món, 2 bếp `B1–B2`, 4 bàn `T1–T4`, 5 Ngày `day_plan`, Shop (`oxygen`, `hp`).
- Triển khai đàn cá bơi & sinh theo lịch (`chonoi/sim/gather_fish.py`), Cá Sấu Năm Chèo `M1`/`M2` + Máu/bất tử/recoil/LIFO (`chonoi/sim/gather_monsters.py`), vòng ngày & Shop (`chonoi/sim/day.py`, `day_config.py`), Pause toàn cục (`chonoi/runner.py`), và giao diện 6 màn hình + HUD v1.1 (`chonoi/live.py`, `chonoi/web/index.html`).

---

## [0.1.0] — Phase 1: MVP hai buổi (`phase-1`, Contract `v1.0`)

- Hoàn thiện vòng lặp Lặn & Hái (`chonoi/sim/gather.py`) và Mở Quán (`chonoi/sim/quan.py`, `quan_customers.py`, `quan_service.py`), bàn giao kho qua file `--inventory-out` / `--inventory`, giao diện trình duyệt (`chonoi/live.py`, `chonoi/web/index.html`) cùng sprite màu nước + `--extra-content`, và bộ skill harness (`check-contract`, `prepare-proof`).
