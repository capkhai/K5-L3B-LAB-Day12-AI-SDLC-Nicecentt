# Bằng chứng Mở rộng (`extensions`) — Nhóm Nicecentt

- **Manifest:** `game.contract.json` → `"extensions": ["burn", "snake", "current"]`
- **Yêu cầu đề bài (nhóm 6 người):** tối thiểu 2 mở rộng → nhóm hoàn thành **3 mở rộng**.

## 1. Danh mục mở rộng & mã nguồn

| Mã | Tên mở rộng | Khóa manifest | Mã nguồn | Test |
|---|---|---|---|---|
| `current` | Dòng nước lũ (Phase 3) | `tuning.gather.current` (`interval_ticks: 1800, duration_ticks: 480, warning_ticks: 120, min_depth: 10, speed: 1.5`) | `chonoi/sim/gather_current.py`, `chonoi/sim/gather.py`, `chonoi/scenario.py`, `chonoi/contract.py` | `tests/test_extensions.py::CurrentExtensionTest` |
| `snake` | Rắn Hổ Mây `M3` (Phase 2) | `tuning.gather.monsters.species.ran`, `spawns` thêm `M3` (`from_day: 1`, `[72,14] ↔ [76,14]`, `d ∈ [8,20]`) | `chonoi/sim/gather_monsters.py`, `chonoi/contract.py` | `tests/test_extensions.py::SnakeExtensionTest`, `tests/test_monsters.py` |
| `burn` | Cháy món (Phase 2) | `tuning.quan.burn_s: 20` | `chonoi/sim/quan_service.py`, `chonoi/contract.py` | `tests/test_extensions.py::BurnExtensionRealContractTest`, `tests/test_chur04_phase2.py::Quan11` |

## 2. Lệnh kiểm chứng

```powershell
$env:PYTHONPATH="tests;."
python -m unittest tests/test_extensions.py tests/test_gather_v12.py tests/test_gather.py tests/test_monsters.py tests/test_chur04_phase2.py tests/test_quan_service.py tests/test_smoke_p1.py tests/test_ui_live.py tests/test_python_starter_units.py tests/test_team_check.py -v
python .agents/skills/check-contract/check_contract.py
```

## 3. Các kịch bản biên đã kiểm thử

### `current` (Dòng nước lũ)
- Cảnh báo `current_warning(starts_at_phase_tick=1800)` đúng tại tick `1680`.
- Bắt đầu `current_start(direction, duration_ticks=480)` trước di chuyển tại tick `1800`; snapshot `current.ticks_left` đếm cả tick vừa chụp (`480` tại tick `1800`, `1` tại tick `2279`).
- Lực `1.5 m/s` (`0.025 m/tick`) chỉ cộng vào `pos[0]` khi `d` **đầu bước** `>= 10`, chặn mép `bounds.x`, không cộng vào `player.vel`.
- Kết thúc `current_end(reason="elapsed")` trước di chuyển tại tick `2280`, không còn lực ở tick `2280`, snapshot `current: null`.
- Kết thúc sớm (`docked`, `time`, `fainted`) phát `current_end(reason="phase_end")` trước `faint` (nếu có) và trước `gather_end`; bước bắt đầu dòng trùng bước cuối ca vẫn áp lực.
- Giới hạn CLI `--ticks 1810` cắt mô phỏng tại trạng thái hiện có (`ticks_left: 470`), không phát `current_end`.
- Scenario hỗ trợ `random_current: false` và `current_direction: -1 | 1`; đầu vào sai trả mã thoát `2`.
- Hai lần chạy headless cùng seed `42` cho đầu ra JSONL **giống nhau từng byte**.

### `snake` (Rắn Hổ Mây `M3`)
- Xuất hiện từ Ngày 1 ở `[72, 14]`, tuần tra `[72, 14] ↔ [76, 14]` tốc độ `1.0 m/s`.
- Người chơi ở `d < 8` không kích hoạt đuổi; ở `d >= 8` và khoảng cách `<= 8 m` chuyển `chase` tốc độ `3.5 m/s`; rời `chase` khi `> 16 m` hoặc `d < 8`.

### `burn` (Cháy món)
- Kiểm chạy headless trực tiếp trên `game.contract.json` (`burn_s: 20`):
  - `ready_ticks = 1199` → bước kế thành `1200`: vẫn bưng được (`dish_picked`).
  - `ready_ticks = 1200` → bước kế thành `1201`: phát `dish_burnt`, bếp về `idle`, giữ chỗ lại ngay (`order_status: "reserved"`) và nấu lại được ngay cùng tick khi nhấn tương tác (`cook_started`).
