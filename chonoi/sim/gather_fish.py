"""Phase 2, lát 1 (capkhai): đàn cá bơi, phản xạ mép/góc và sinh cá theo lịch (Contract v1.1).

Tương thích ngược với v1.0: khi `fish_initial` là danh sách (v1.0) và thiếu khóa bơi/sinh,
đàn cá giữ đứng yên như Phase 1. Khi `game.contract.json` chuyển sang v1.1 (`fish_initial` là số nguyên
và có `fish_speed`, `fish_depths`, ...), tự động bật đầy đủ sinh đầu ca, bơi, đổi hướng và sinh định kỳ.
"""

import math

from ..ids import sort_by_id


def _has_v11_fish_config(t: dict) -> bool:
    return "fish_speed" in t and "fish_depths" in t and "fish_x" in t


def _has_v11_spawn_config(t: dict) -> bool:
    return "fish_spawn_x" in t and "fish_spawn_depths" in t and "fish_weights" in t


def init_fish(sim, scenario: dict) -> list:
    """Khởi tạo danh sách đàn cá theo scenario và tuning (v1.0 hoặc v1.1)."""
    t = sim.t
    sim.random_fish = bool(scenario.get("random_fish", True))
    if "fish" in scenario:
        fish = [
            {
                "id": f["id"],
                "kind": f["kind"],
                "pos": [float(c) for c in f["pos"]],
                "heading_deg": float(f.get("heading_deg", 0.0)),
                "age_ticks": int(f.get("age_ticks", 0)),
            }
            for f in scenario["fish"]
        ]
        for f in fish:
            sim.ids.reserve(f["id"])
        return fish

    if not sim.random_fish:
        return []

    initial = t["fish_initial"]
    if isinstance(initial, list):
        fish = [
            {
                "id": f["id"],
                "kind": f["kind"],
                "pos": [float(c) for c in f["pos"]],
                "heading_deg": float(f.get("heading_deg", 0.0)),
                "age_ticks": int(f.get("age_ticks", 0)),
            }
            for f in initial
        ]
        for f in fish:
            sim.ids.reserve(f["id"])
        return fish

    # v1.1: sinh `fish_initial` đàn ở các điểm hình học khác nhau
    fish = []
    count = int(initial)
    occupied_pts = set()
    for _ in range(count):
        school = _pick_and_create_school(sim, fish, occupied_pts=occupied_pts)
        if school is None:
            break
        occupied_pts.add((school["pos"][0], school["pos"][1]))
        fish.append(school)
    return fish


def step_swim(sim):
    """Mọi đàn cá bơi một bước theo thứ tự id (chỉ chạy khi random_fish=True và có cấu hình v1.1)."""
    t = sim.t
    if not sim.random_fish or not _has_v11_fish_config(t):
        return
    speed = float(t["fish_speed"])
    step_dist = speed / sim.tick_hz
    turn_ticks = int(t.get("fish_turn_ticks", 120))
    x_lo, x_hi = float(t["fish_x"][0]), float(t["fish_x"][1])
    depths_map = t["fish_depths"]
    rng_turn = sim.rng.get("fish_turn")

    for f in sort_by_id(sim.fish):
        step_num = f["age_ticks"] + 1
        if turn_ticks > 0 and step_num % turn_ticks == 0:
            f["heading_deg"] = rng_turn.uniform(0.0, 360.0) % 360.0

        rad = math.radians(f["heading_deg"])
        vx = math.cos(rad)
        vd = math.sin(rad)
        d_lo, d_hi = float(depths_map[f["kind"]][0]), float(depths_map[f["kind"]][1])

        nx, vx, fx = _reflect_axis(f["pos"][0], vx * step_dist, vx, x_lo, x_hi)
        nd, vd, fd = _reflect_axis(f["pos"][1], vd * step_dist, vd, d_lo, d_hi)
        f["pos"] = [nx, nd]
        if fx or fd:
            f["heading_deg"] = math.degrees(math.atan2(vd, vx)) % 360.0
        f["age_ticks"] = step_num


def step_spawn(sim, events: list):
    """Sinh tối đa 1 đàn cá tại phase_tick = fish_spawn_ticks * k (k >= 1)."""
    t = sim.t
    if not sim.random_fish or not _has_v11_spawn_config(t):
        return
    spawn_ticks = int(t.get("fish_spawn_ticks", 360))
    if spawn_ticks <= 0 or sim.phase_tick <= 0 or sim.phase_tick % spawn_ticks != 0:
        return
    fish_max = int(t.get("fish_max", 12))
    if len(sim.fish) >= fish_max:
        return
    school = _pick_and_create_school(sim, sim.fish)
    if school is None:
        return
    sim.fish.append(school)
    events.append(("fish_spawned", {
        "id": school["id"],
        "kind": school["kind"],
        "pos": list(school["pos"]),
    }))


def _pick_and_create_school(sim, existing_fish: list, occupied_pts=None):
    t = sim.t
    if not _has_v11_spawn_config(t):
        return None
    clearance = float(t.get("fish_spawn_clearance", 1.0))
    spawn_xs = [float(x) for x in t["fish_spawn_x"]]
    spawn_depths = t["fish_spawn_depths"]
    weights = t["fish_weights"]

    eligible_by_kind = {}
    for kind in sorted(weights):
        if float(weights[kind]) <= 0:
            continue
        pts = []
        for x in spawn_xs:
            for d in spawn_depths.get(kind, []):
                pt = (x, float(d))
                if occupied_pts is not None and pt in occupied_pts:
                    continue
                if all(math.dist(pt, f["pos"]) > clearance for f in existing_fish):
                    pts.append(pt)
        if pts:
            eligible_by_kind[kind] = pts

    if not eligible_by_kind:
        return None

    rng = sim.rng.get("fish_spawn")
    kinds = sorted(eligible_by_kind)
    total_w = sum(float(weights[k]) for k in kinds)
    r = rng.random() * total_w
    chosen_kind = kinds[-1]
    acc = 0.0
    for k in kinds:
        acc += float(weights[k])
        if r < acc:
            chosen_kind = k
            break

    pts = eligible_by_kind[chosen_kind]
    x, d = pts[rng.randrange(len(pts))]
    heading = rng.uniform(0.0, 360.0) % 360.0
    fid = sim.ids.new("F")
    return {
        "id": fid,
        "kind": chosen_kind,
        "pos": [x, d],
        "heading_deg": heading,
        "age_ticks": 0,
    }


def _reflect_axis(pos: float, delta: float, vel_comp: float, lo: float, hi: float):
    """Di chuyển trên 1 trục và phản xạ phần quãng đường vượt mép (kể cả chạm đúng mép)."""
    if hi <= lo:
        return lo, 0.0, True
    nxt = pos + delta
    flipped = False
    while nxt < lo or nxt > hi:
        if nxt < lo:
            nxt = lo + (lo - nxt)
            vel_comp = -vel_comp
            flipped = True
        elif nxt > hi:
            nxt = hi - (nxt - hi)
            vel_comp = -vel_comp
            flipped = True
    if nxt == lo and vel_comp < 0.0:
        vel_comp = -vel_comp
        flipped = True
    elif nxt == hi and vel_comp > 0.0:
        vel_comp = -vel_comp
        flipped = True
    return nxt, vel_comp, flipped
