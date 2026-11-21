"""Phase 2, lát 2: Cá Sấu Năm Chèo (`M1`/`M2`) và luật thủy quái chung (Contract v1.1).

Mục 1.2, 4.3, 4.4, 4.5 của `docs/prd-phase-2.md`:
  - `patrol`: đi 1.0 m/s tới waypoint đích, đến nơi đổi sang waypoint kia cho bước sau.
  - `chase`: khi người chơi ở `d >= depths[0]` và cách `<= detect_radius`, đuổi theo `chase_speed`;
             rời chase về `patrol` khi cách `> exit_radius` hoặc người chơi lên `d < depths[0]`.
  - Va chạm: sau khi cả hai di chuyển, nếu khoảng cách `<= hit_radius`, người chơi ở `d >= depths[0]`
             và `invuln_ticks == 0`: tối đa 1 hit/bước (gần nhất, hòa theo id), mất 1 Máu,
             bỏ `floor(len(hold) * loss_ratio)` theo LIFO, đặt bất tử `invuln_ticks` (90).
  - `recoil`: con gây hit lùi `recoil_ticks` (60) bước từ bước sau theo hướng xa người chơi đã chốt
              lúc chạm (trùng tâm dùng `+x`), mỗi bước `recoil_dist / recoil_ticks`, không gây hit;
              hết recoil về `patrol` và xét phát hiện/chạm từ bước kế.
  - Máu chạm 0 -> `faint(cause="monster")` + `gather_end("fainted")`, return True ngay.
"""

import math

from ..freshness import public_item
from ..ids import id_key, sort_by_id


def init_monsters(sim, scenario: dict, day=None) -> list:
    """Khởi tạo danh sách thủy quái theo scenario hoặc bố trí chuẩn theo Ngày (`sim.day`)."""
    eff_day = sim.day if day is None else int(day)
    cfg = sim.t.get("monsters", {})
    if "monsters" in scenario:
        src = scenario["monsters"]
    else:
        src = [
            sp for sp in cfg.get("spawns", [])
            if int(sp.get("from_day", 1)) <= eff_day
        ]
    monsters = []
    for m in src:
        wps = [[float(c) for c in wp] for wp in m["waypoints"]]
        recoil_dir = [float(c) for c in m["recoil_dir"]] if m.get("recoil_dir") is not None else None
        monsters.append({
            "id": m["id"],
            "kind": m["kind"],
            "pos": [float(c) for c in m["pos"]],
            "waypoints": wps,
            "target_idx": int(m.get("target_idx", 1)),
            "state": m.get("state", "patrol"),
            "state_ticks_left": int(m.get("state_ticks_left", 0)),
            "recoil_dir": recoil_dir,
        })
        sim.ids.reserve(m["id"])
    return monsters


def snapshot_monsters(sim) -> list:
    return [
        {
            "id": m["id"],
            "kind": m["kind"],
            "pos": list(m["pos"]),
            "waypoints": [list(wp) for wp in m["waypoints"]],
            "target_idx": m["target_idx"],
            "state": m["state"],
            "state_ticks_left": m["state_ticks_left"],
            "recoil_dir": list(m["recoil_dir"]) if m["recoil_dir"] is not None else None,
        }
        for m in sort_by_id(sim.monsters)
    ]


def step_monsters(sim, events: list) -> bool:
    """Cập nhật quái theo id rồi xét tối đa 1 hit. Trả True nếu người chơi ngất."""
    cfg = sim.t.get("monsters", {})
    species_map = cfg.get("species", {})
    bx_lo, bx_hi = float(sim.t["bounds"]["x"][0]), float(sim.t["bounds"]["x"][1])
    bd_lo, bd_hi = float(sim.t["bounds"]["d"][0]), float(sim.t["bounds"]["d"][1])

    no_hit_ids = set()

    # 1. Cập nhật di chuyển & trạng thái theo thứ tự id
    for m in sort_by_id(sim.monsters):
        sp = species_map[m["kind"]]
        d_lo = max(bd_lo, float(sp["depths"][0]))
        d_hi = min(bd_hi, float(sp["depths"][1]))
        state = m["state"]

        if state == "stunned":
            no_hit_ids.add(m["id"])
            m["state_ticks_left"] = max(0, m["state_ticks_left"] - 1)
            if m["state_ticks_left"] == 0:
                m["state"] = "patrol"
            continue

        if state == "recoil":
            no_hit_ids.add(m["id"])
            step_len = float(sp["recoil_dist"]) / max(1, int(sp["recoil_ticks"]))
            dx, dd = m["recoil_dir"] if m["recoil_dir"] is not None else (1.0, 0.0)
            m["pos"] = _clamp_pos(
                m["pos"][0] + dx * step_len,
                m["pos"][1] + dd * step_len,
                bx_lo, bx_hi, d_lo, d_hi,
            )
            m["state_ticks_left"] = max(0, m["state_ticks_left"] - 1)
            if m["state_ticks_left"] == 0:
                m["state"] = "patrol"
                m["recoil_dir"] = None
            continue

        # patrol hoặc chase: xét chuyển trạng thái trước khi di chuyển
        dist_p = math.dist(m["pos"], sim.pos)
        player_in_depth = sim.pos[1] >= float(sp["depths"][0])
        if state == "patrol":
            if player_in_depth and dist_p <= float(sp["detect_radius"]):
                m["state"] = "chase"
        elif state == "chase":
            if dist_p > float(sp["exit_radius"]) or not player_in_depth:
                m["state"] = "patrol"

        if m["state"] == "patrol":
            wp = m["waypoints"][m["target_idx"]]
            step_len = float(sp["patrol_speed"]) / sim.tick_hz
            orig_dist = math.dist(m["pos"], wp)
            if orig_dist <= step_len + 1e-9:
                m["pos"] = _clamp_pos(wp[0], wp[1], bx_lo, bx_hi, d_lo, d_hi)
                m["target_idx"] = 1 - m["target_idx"]
            else:
                ratio = step_len / orig_dist
                nx = m["pos"][0] + (wp[0] - m["pos"][0]) * ratio
                nd = m["pos"][1] + (wp[1] - m["pos"][1]) * ratio
                m["pos"] = _clamp_pos(nx, nd, bx_lo, bx_hi, d_lo, d_hi)
        else:  # chase
            step_len = float(sp["chase_speed"]) / sim.tick_hz
            orig_dist = math.dist(m["pos"], sim.pos)
            if orig_dist <= step_len:
                m["pos"] = _clamp_pos(sim.pos[0], sim.pos[1], bx_lo, bx_hi, d_lo, d_hi)
            else:
                ratio = step_len / orig_dist
                nx = m["pos"][0] + (sim.pos[0] - m["pos"][0]) * ratio
                nd = m["pos"][1] + (sim.pos[1] - m["pos"][1]) * ratio
                m["pos"] = _clamp_pos(nx, nd, bx_lo, bx_hi, d_lo, d_hi)

    # 2. Xét tối đa một hit (nếu hết bất tử)
    if sim.invuln_ticks > 0:
        return False

    cands = []
    for m in sim.monsters:
        if m["id"] in no_hit_ids or m["state"] not in ("patrol", "chase"):
            continue
        sp = species_map[m["kind"]]
        if sim.pos[1] < float(sp["depths"][0]):
            continue
        dist = math.dist(m["pos"], sim.pos)
        if dist <= float(sp["hit_radius"]):
            cands.append((dist, id_key(m["id"]), m, sp))

    if not cands:
        return False

    cands.sort(key=lambda item: (item[0], item[1]))
    _, _, attacker, sp = cands[0]

    sim.hp = max(0, sim.hp - 1)
    loss_ratio = float(cfg.get("loss_ratio", 0.5))
    drop_count = math.floor(len(sim.hold) * loss_ratio)
    raw_lost = [sim.hold.pop() for _ in range(drop_count)]
    lost = [public_item(it) if isinstance(it, dict) else it for it in raw_lost]
    sim.invuln_ticks = int(cfg.get("invuln_ticks", 90))

    dx = attacker["pos"][0] - sim.pos[0]
    dd = attacker["pos"][1] - sim.pos[1]
    norm = math.hypot(dx, dd)
    recoil_dir = [dx / norm, dd / norm] if norm > 1e-12 else [1.0, 0.0]
    attacker["state"] = "recoil"
    attacker["state_ticks_left"] = int(sp["recoil_ticks"])
    attacker["recoil_dir"] = recoil_dir

    events.append(("monster_hit", {
        "monster_id": attacker["id"],
        "hp": sim.hp,
        "lost": lost,
        "pos": list(sim.pos),
    }))

    if sim.hp <= 0:
        sim._faint("monster", events)
        return True
    return False


def _clamp_pos(x: float, d: float, x_lo: float, x_hi: float, d_lo: float, d_hi: float) -> list:
    return [max(x_lo, min(x_hi, x)), max(d_lo, min(d_hi, d))]
