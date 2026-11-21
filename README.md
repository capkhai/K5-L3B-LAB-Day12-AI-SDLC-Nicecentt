# Quán Ăn Chợ Nổi — Release `v1.0.0` (Team Nicecentt)

> **Day 12 — AI SDLC** · Game 2D hai buổi **Lặn & Hái → Mở Quán → Shop**, hỗ trợ **Contract `v1.3`**, độ tươi cá thể, 3 phần mở rộng (`burn`, `snake`, `current`), benchmark có render `1280×720` và soak 10 Ngày tất định.

## Chạy nhanh từ clone sạch (≤ 3 lệnh — macOS / Linux)

**Yêu cầu môi trường:** Python **3.10+** (chỉ dùng thư viện chuẩn, **không cần `pip install`**, trình duyệt hiện đại cho chế độ chơi trực tiếp).

```bash
git clone https://github.com/capkhai/K5-L3B-LAB-Day12-AI-SDLC-Nicecentt.git
cd K5-L3B-LAB-Day12-AI-SDLC-Nicecentt
python3 -m chonoi.live --mode day
```

Mở địa chỉ `http://127.0.0.1:8000/` in trên terminal (có thể dùng `--mode gather` hoặc `--mode quan`).

> **Windows PowerShell:** thay `python3` bằng `python`: `python -m chonoi.live --mode day`.

## Điều khiển & Khả năng tiếp cận (Accessibility)

- **Di chuyển:** `WASD` hoặc phím mũi tên
- **Tương tác / Hái / Cập bến / Nấu / Bưng / Phục vụ:** `E`
- **Bắt cá (dưới nước):** `Space`
- **Tạm dừng (dừng toàn bộ bộ đếm, kể cả Shop):** `Esc` hoặc `P`
- **Chơi lại từ đầu:** `R`
- **Chế độ tương phản cao (High Contrast):** nhấn `C` hoặc nút `🌓 Tương phản` trên thanh HUD / menu Pause
- **3 cảnh báo trực quan bằng chữ & biểu tượng:**
  - `🐊 THỦY QUÁI!` (+ viền tím khi thủy quái gần)
  - `🫧 OXY SẮP HẾT!` (< 25% oxy) và `💨 HẾT HƠI!` (oxy = 0)
  - `💢 KHÁCH SẮP GIẬN! (T1…)` (khách còn < 25% kiên nhẫn)

## Lệnh kiểm thử, Headless, Benchmark & Soak

### 1. Chạy toàn bộ test (macOS / Linux)
```bash
PYTHONPATH=tests:. python3 -m unittest discover -s tests -p "test_*.py" -v
python3 .agents/skills/check-contract/check_contract.py
```

*(Windows PowerShell: `$env:PYTHONPATH = "tests;."; python -m unittest tests/test_phase4_v13.py tests/test_phase3_v12.py tests/test_extensions.py tests/test_gather_v12.py tests/test_gather.py tests/test_monsters.py tests/test_chur04_phase2.py tests/test_quan_service.py tests/test_smoke_p1.py tests/test_ui_live.py tests/test_python_starter_units.py tests/test_team_check.py -v`)*

### 2. Chế độ Headless (Contract `v1.3`)
```bash
python3 -m chonoi.headless --mode gather --seed 1 --ticks 600 --out gather.jsonl
python3 -m chonoi.headless --mode quan --seed 1 --ticks 600 --out quan.jsonl
python3 -m chonoi.headless --mode day --days 1 --seed 7 --ticks 22200 --out day.jsonl
```

### 3. Benchmark có render `1280×720` (3s làm nóng + 30s đo)
```bash
python3 -m chonoi.bench --seed 42 --duration 30 --out bench.json
```

### 4. Soak Headless 10 Ngày (lặp kế hoạch D1–D5 cho D6–D10)
```bash
python3 -m chonoi.soak --seed 7 --days 10 --out soak.json
```

### 5. Đóng gói bản phát hành
```bash
python3 tools/build_release.py
```

## Mở rộng đã hoàn thành (`extensions`)

Nhóm **Nicecentt** (6 thành viên — yêu cầu tối thiểu 2 mở rộng) đã hoàn thành **3 mở rộng**, khai báo tại gốc [`game.contract.json`](game.contract.json) (`"extensions": ["burn", "snake", "current"]`):

1. **`current` — Dòng nước lũ (Phase 3):** Chu kỳ `1800 * k` tick, cảnh báo trước 120 tick (`current_warning`), chảy 480 tick (`current_start`), cộng lực `1.5 m/s` theo trục `x` khi độ sâu đầu bước `d >= 10`, kết thúc `current_end(elapsed)` hoặc `current_end(phase_end)`. Hỗ trợ `gather.random_current` và `gather.current_direction`.
2. **`snake` — Rắn Hổ Mây (`M3`, Phase 2):** Xuất hiện từ Ngày 1 ở `[72, 14] ↔ [76, 14]`, `d ∈ [8, 20]`, tuần tra `1.0 m/s`, đuổi `3.5 m/s` trong `<= 8 m`, rời đuổi khi `> 16 m` hoặc `d < 8`.
3. **`burn` — Cháy món (Phase 2):** `quan.burn_s: 20` (`1200` tick). Đúng `1200` tick vẫn bưng được; từ tick `1201` phát `dish_burnt`, trả bếp về `idle` và thử giữ chỗ lại ngay.

- Test tự động: [`tests/test_extensions.py`](tests/test_extensions.py), [`tests/test_chur04_phase2.py`](tests/test_chur04_phase2.py) (`Quan11`).
- Bằng chứng: [`docs/proof/phase-3/extensions.md`](docs/proof/phase-3/extensions.md).

## Sáng tạo của nhóm

Bản trình duyệt có thêm cá kèo, cá rô đồng, kèo nèo và rau muống, cùng ba công thức cá kèo kho tộ, canh chua cá rô kèo nèo và rau muống xào (dữ liệu tại `chonoi/extra_content.json`), kèm bộ sprite màu nước và animation bơi 6 khung hình (`chonoi/web/assets/`). Bật bằng `python3 -m chonoi.live --mode gather --extra-content`; mặc định **tắt hoàn toàn ở chế độ headless** để giữ nguyên 100% Test Contract.

## Tài liệu & Truy vết

- Danh sách nhóm: [`TEAM.md`](TEAM.md) · Phản tư cá nhân: `docs/members/`
- Thay đổi theo từng phase: [`CHANGELOG.md`](CHANGELOG.md)
- Xác minh theo phase: [`docs/verification/phase-1.md`](docs/verification/phase-1.md) · [`phase-2.md`](docs/verification/phase-2.md) · [`phase-3.md`](docs/verification/phase-3.md) · [`phase-4.md`](docs/verification/phase-4.md)
- Retro & Nhật ký AI: [`docs/retro.md`](docs/retro.md) · [`docs/ai-usage-log.md`](docs/ai-usage-log.md) · [`docs/clarify.md`](docs/clarify.md)
- Giấy phép & Nguồn tài sản: [`LICENSE`](LICENSE) · [`CREDITS.md`](CREDITS.md)
