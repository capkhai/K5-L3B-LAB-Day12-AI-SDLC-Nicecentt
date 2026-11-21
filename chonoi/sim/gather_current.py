"""Mở rộng Phase 3 — Dòng nước lũ (`current`).

Luật theo TICKET-03:
- Với `t = interval_ticks * k` (k >= 1, mặc định 1800 * k):
  - Tại `phase_tick = t - warning_ticks` (1680, 3480...): phát `current_warning(starts_at_phase_tick)`.
  - Trước di chuyển ở `phase_tick = t`: bắt đầu dòng kéo dài `duration_ticks` (480) bước,
    từ `t` đến `t + duration_ticks - 1`. Hướng chọn đều -1 hoặc +1 theo seed (`Streams("current")`)
    trừ khi bị khóa bởi `scenario.current_direction`. Phát `current_start(direction, duration_ticks)`.
- Lực dòng: sau khi người chơi di chuyển, nếu dòng đang chạy và độ sâu đầu bước `start_d >= min_depth`
  (mặc định 10), cộng `direction * speed / tick_hz` vào `pos[0]` rồi chặn mép `bounds.x`.
  Không cộng vào `player.vel`; cá và thủy quái giữ chuyển động riêng.
- Snapshot `current`: `null` hoặc `{"direction": dir, "ticks_left": N}` — đếm cả tick hoạt động
  vừa chụp (`ticks_left == 480` ở tick `t`, `ticks_left == 1` ở tick `t + 479`).
- Kết thúc:
  - Trước di chuyển ở `t + duration_ticks` (khi giảm từ 1 -> 0): phát `current_end(direction, reason="elapsed")`,
    đặt `current = None`, không có lực ở tick đó.
  - Nếu ca kết thúc sớm (`docked`, `time`, `fainted`) trong lúc dòng đang chạy:
    phát `current_end(direction, reason="phase_end")` trước `faint` (nếu có) và trước `gather_end`.
  - Giới hạn CLI `--ticks` chỉ cắt mô phỏng tại trạng thái hiện có.
"""


def init_current(sim, scenario: dict):
    """Khởi tạo cấu hình và trạng thái dòng nước lũ cho GatherSim."""
    cfg = sim.t.get("current")
    if cfg is None:
        return None
    return {
        "enabled": bool(scenario.get("random_current", True)),
        "locked_dir": scenario.get("current_direction"),
        "interval_ticks": int(cfg["interval_ticks"]),
        "duration_ticks": int(cfg["duration_ticks"]),
        "warning_ticks": int(cfg["warning_ticks"]),
        "min_depth": float(cfg["min_depth"]),
        "speed": float(cfg["speed"]),
        "active": None,  # None hoặc {"direction": -1|1, "ticks_left": int}
    }


def snapshot_current(sim):
    """Giá trị trường `current` trong snapshot gather (đếm cả tick hoạt động vừa chụp)."""
    st = sim.current_ctrl
    if st is None or st["active"] is None:
        return None
    return {
        "direction": st["active"]["direction"],
        "ticks_left": st["active"]["ticks_left"],
    }


def step_before_move(sim, events: list):
    """Cập nhật vòng đời dòng nước lũ trước bước di chuyển tại `sim.phase_tick`."""
    st = sim.current_ctrl
    if st is None:
        return

    # 1. Nếu dòng đang chạy từ bước trước: giảm số tick còn lại; chạm 0 thì kết thúc trước di chuyển
    active = st["active"]
    if active is not None:
        active["ticks_left"] -= 1
        if active["ticks_left"] <= 0:
            direction = active["direction"]
            st["active"] = None
            events.append(("current_end", {"direction": direction, "reason": "elapsed"}))

    if not st["enabled"]:
        return

    pt = sim.phase_tick
    interval = st["interval_ticks"]
    warning = st["warning_ticks"]

    # 2. Cảnh báo trước t - warning_ticks (với t = interval * k, k >= 1)
    if warning > 0 and (pt + warning) % interval == 0:
        events.append(("current_warning", {"starts_at_phase_tick": pt + warning}))

    # 3. Bắt đầu dòng mới tại t = interval * k (k >= 1)
    if pt > 0 and pt % interval == 0:
        if st["locked_dir"] is not None:
            direction = int(st["locked_dir"])
        else:
            direction = int(sim.rng.get("current").choice([-1, 1]))
        duration = st["duration_ticks"]
        st["active"] = {"direction": direction, "ticks_left": duration}
        events.append(("current_start", {"direction": direction, "duration_ticks": duration}))


def apply_force(sim, start_d: float):
    """Cộng lực dòng vào `pos[0]` nếu dòng đang hoạt động và `start_d >= min_depth`."""
    st = sim.current_ctrl
    if st is None or st["active"] is None:
        return
    if start_d < st["min_depth"]:
        return
    direction = st["active"]["direction"]
    dx = direction * st["speed"] / sim.tick_hz
    x_lo, x_hi = sim.t["bounds"]["x"]
    sim.pos[0] = max(float(x_lo), min(float(x_hi), sim.pos[0] + dx))


def end_for_phase(sim, events: list):
    """Kết thúc dòng khi ca sáng đóng sớm (`docked`, `time`, `fainted`)."""
    st = sim.current_ctrl
    if st is None or st["active"] is None:
        return
    direction = st["active"]["direction"]
    st["active"] = None
    events.append(("current_end", {"direction": direction, "reason": "phase_end"}))
