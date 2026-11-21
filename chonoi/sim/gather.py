"""Buổi sáng — Lặn & Hái (`gather`).

Mặt cắt dòng sông nhìn NGANG: vị trí `[x, d]` (x sang phải, `d` độ sâu hướng xuống, d = 0 là mặt nước).
`move = [x, d]`: thành phần thứ hai DƯƠNG = bơi xuống. Hướng mặt là góc từ +x, dương = xuống.

Phase 1 + Phase 2 lát 1 (`capkhai`):
  - Bơi + tăng/giảm tốc, chặn mép (`d >= 0`), chuyển vùng `dive`/`surface`.
  - Oxy + ngạt (tính ngay bước oxy vừa chạm 0, reset khi oxy > 0 hoặc lên mặt nước, xuyên bất tử),
    ngất (`faint` với `cause`, `lost` LIFO, `hp: 0` + `gather_end("fainted")` kho rỗng).
  - Hái nút mặt nước (bến ưu tiên trước hái, `gather` / `hold_full`, `node_regrown`).
  - Bắt cá dưới nước (cần đủ chỗ cho cả đàn, hồi chiêu tính từ lần bắt thành công, `fish_caught` / `hold_full`).
  - Cá bơi, phản xạ mép/góc, đổi hướng theo seed và sinh theo lịch (`gather_fish.py`).
  - Có sẵn điểm nối cho Cá Sấu (`gather_monsters.py` của lát 2).
"""

import math

from ..freshness import decay_items, is_v12, make_item, public_item
from ..ids import id_key, sort_by_id
from ..inventory import hold_to_items
from . import gather_current, gather_fish
from .ramp import ramp_velocity

TICK = 60.0
AXES = ("x", "d")


class GatherSim:
    mode = "gather"
    phase = "gather"

    def __init__(self, tuning, scenario, streams, ids, day=1, oxygen_max_s=None, hp_max=None,
                 reallocate_hold_ids=False):
        t = tuning["gather"]
        self.t = t
        self.tuning = tuning
        self.v12 = is_v12(tuning)
        self.freshness_cfg = tuning.get("freshness") or {}
        self.tick_hz = float(tuning.get("tick_hz", TICK))
        self.day = int(day)
        self.rng = streams
        self.ids = ids
        self.phase_tick = 0
        p = scenario.get("player", {})
        self.pos = [float(c) for c in p.get("pos", t["start_pos"])]
        self.vel = [float(c) for c in p.get("vel", [0.0, 0.0])]
        self._tgt = None
        self._ramp_left = 0
        self.heading = float(p.get("heading_deg", t["start_heading_deg"]))
        eff_oxy_s = t["oxygen_max_s"] if oxygen_max_s is None else oxygen_max_s
        eff_hp_max = t["hp_max"] if hp_max is None else hp_max
        self.oxygen_max = int(round(eff_oxy_s * self.tick_hz))
        self.oxygen_ticks = p.get("oxygen_ticks", self.oxygen_max)
        self.hp_max = int(eff_hp_max)
        self.hp = p.get("hp", self.hp_max)
        self.zero_oxy_ticks = p.get("zero_oxy_ticks", 0)
        self.invuln_ticks = p.get("invuln_ticks", 0)
        self.catch_cd_ticks = p.get("catch_cd_ticks", 0)
        raw_hold = list(scenario.get("hold", []))
        if self.v12:
            self.hold = []
            for entry in raw_hold:
                if isinstance(entry, dict):
                    ident = ids.new("I") if reallocate_hold_ids else entry["id"]
                    if not reallocate_hold_ids:
                        ids.reserve(ident)
                    self.hold.append(make_item(ident, entry["kind"], entry["fresh"]))
                else:
                    self.hold.append(make_item(ids.new("I"), entry, self.freshness_cfg.get("initial", 100)))
        else:
            self.hold = raw_hold  # thứ tự nhặt, cuối mảng là mới nhất (LIFO)
        self.time_left_ticks = scenario.get("time_left_ticks", int(round(t["duration_s"] * self.tick_hz)))
        src_nodes = scenario["nodes"] if "nodes" in scenario else t["nodes"]
        self.nodes = [{"id": n["id"], "kind": n["kind"], "pos": [float(c) for c in n["pos"]],
                       "regrow_ticks": n.get("regrow_ticks", 0)} for n in src_nodes]
        for n in self.nodes:
            ids.reserve(n["id"])
        self.fish = gather_fish.init_fish(self, scenario)
        self.monsters = []
        self._monster_mod = _load_monster_module()
        if self._monster_mod is not None and ("monsters" in t or "monsters" in scenario):
            self.monsters = self._monster_mod.init_monsters(self, scenario, self.day)
        self.current_ctrl = gather_current.init_current(self, scenario)
        self.money = 0
        self.earned = 0
        self.reputation = tuning["quan"]["reputation_initial"]
        self.done = False
        self.reason = None

    # --- giao diện cho runner -------------------------------------------------
    def inventory_items(self):
        if self.v12:
            return [public_item(it) for it in sort_by_id(self.hold)]
        return hold_to_items(self.hold)

    def snapshot(self) -> dict:
        hold_snap = [public_item(it) for it in self.hold] if self.v12 else list(self.hold)
        snap = {
            "player": {"pos": list(self.pos), "vel": list(self.vel), "heading_deg": self.heading,
                       "oxygen_ticks": self.oxygen_ticks, "oxygen_max_ticks": self.oxygen_max,
                       "hp": self.hp, "hp_max": self.hp_max, "zero_oxy_ticks": self.zero_oxy_ticks,
                       "invuln_ticks": self.invuln_ticks, "catch_cd_ticks": self.catch_cd_ticks,
                       "at_surface": self._at_surface()},
            "hold": hold_snap, "hold_count": len(self.hold),
            "hold_capacity": self.t["hold_capacity"],
            "nodes": [{"id": n["id"], "pos": list(n["pos"]), "kind": n["kind"],
                       "ready": n["regrow_ticks"] == 0, "regrow_ticks": n["regrow_ticks"]}
                      for n in sort_by_id(self.nodes)],
            "fish": [{"id": f["id"], "pos": list(f["pos"]), "kind": f["kind"], "heading_deg": f["heading_deg"]}
                     for f in sort_by_id(self.fish)],
        }
        if self._monster_mod is not None and ("monsters" in self.t or self.monsters):
            snap["monsters"] = self._monster_mod.snapshot_monsters(self)
        if self.current_ctrl is not None:
            snap["current"] = gather_current.snapshot_current(self)
        return snap

    # --- một bước (đúng thứ tự PRD-0, Phase 2 mục 4.5 & Phase 3 TICKET-03) ------
    def step(self, inp):
        if self.done:
            return []
        events = []
        self.phase_tick += 1
        # 1. đồng hồ, cooldown, giảm bất tử, hồi nút và hao tươi hàng có sẵn ở đầu bước
        self.time_left_ticks = max(0, self.time_left_ticks - 1)
        self.invuln_ticks = max(0, self.invuln_ticks - 1)
        self.catch_cd_ticks = max(0, self.catch_cd_ticks - 1)
        for n in sort_by_id(self.nodes):
            if n["regrow_ticks"] > 0:
                n["regrow_ticks"] -= 1
                if n["regrow_ticks"] == 0:
                    events.append(("node_regrown", {"node_id": n["id"]}))
        if self.v12 and self.hold:
            decay_items(
                self.hold,
                self.freshness_cfg["gather_decay_per_s"],
                self.tick_hz,
                self.freshness_cfg["spoiled_below"],
                "hold",
                events,
            )
        # 2. dòng nước lũ (trước di chuyển) + bơi + lực dòng + chặn mép + phân vùng + oxy / ngạt / ngất
        gather_current.step_before_move(self, events)
        was_at_surface = self._at_surface()
        start_d = self.pos[1]
        self._move(inp)
        gather_current.apply_force(self, start_d)
        now_at_surface = self._at_surface()
        if was_at_surface and not now_at_surface:
            events.append(("dive", {"pos": list(self.pos)}))
        elif not was_at_surface and now_at_surface:
            events.append(("surface", {"pos": list(self.pos)}))
        if self._step_oxygen(now_at_surface, events):
            return events
        # 3. quái vật (nếu lát 2 đã nối gather_monsters)
        if self._monster_mod is not None and self.monsters:
            if self._monster_mod.step_monsters(self, events):
                return events
        # 4. tương tác: bến trước, rồi hái
        if inp.pressed("interact"):
            if self._in_dock():
                self._finish("docked", events)
                return events
            if self._at_surface():
                self._try_gather_node(events)
        # 5. bắt cá (theo vị trí cá TRƯỚC khi cá bơi)
        if inp.pressed("catch"):
            if self.catch_cd_ticks == 0 and not self._at_surface():
                self._try_catch_fish(events)
        # 6. xét hết giờ
        if self.time_left_ticks <= 0:
            self._finish("time", events)
            return events
        # 7. còn giờ -> cá bơi và sinh thêm theo lịch
        gather_fish.step_swim(self)
        gather_fish.step_spawn(self, events)
        return events

    # --- tiện ích ---------------------------------------------------------------
    def _at_surface(self) -> bool:
        return self.pos[1] <= self.t["surface_depth"]

    def _in_dock(self) -> bool:
        return math.dist(self.pos, self.t["dock_pos"]) <= self.t["dock_radius"]

    def _hold_space(self) -> int:
        return max(0, int(self.t["hold_capacity"]) - len(self.hold))

    def _add_to_hold(self, kind: str, count: int):
        if self.v12:
            initial = self.freshness_cfg.get("initial", 100)
            for _ in range(count):
                self.hold.append(make_item(self.ids.new("I"), kind, initial))
        else:
            self.hold.extend([kind] * count)

    def _faint(self, cause: str, events: list):
        """Ngất: mất toàn bộ giỏ còn lại (LIFO), phát current_end (nếu có) + faint + gather_end(fainted)."""
        gather_current.end_for_phase(self, events)
        if self.v12:
            lost = [public_item(it) for it in reversed(self.hold)]
        else:
            lost = list(reversed(self.hold))
        self.hold.clear()
        events.append(("faint", {"cause": cause, "lost": lost, "hp": 0}))
        self._finish("fainted", events)

    def _try_gather_node(self, events: list):
        radius = float(self.t["interact_radius"])
        cands = [
            (math.dist(self.pos, n["pos"]), id_key(n["id"]), n)
            for n in self.nodes
            if n["regrow_ticks"] == 0 and math.dist(self.pos, n["pos"]) <= radius
        ]
        if not cands:
            return
        cands.sort(key=lambda item: (item[0], item[1]))
        node = cands[0][2]
        yield_amt = int(self.t["node_yield"])
        free = self._hold_space()
        if free < yield_amt:
            events.append(("hold_full", {
                "action": "gather",
                "node_id": node["id"],
                "required": yield_amt,
                "free": free,
            }))
            return
        self._add_to_hold(node["kind"], yield_amt)
        node["regrow_ticks"] = int(round(self.t["regrow_s"] * self.tick_hz))
        events.append(("gather", {"node_id": node["id"], "kind": node["kind"], "amount": yield_amt}))

    def _try_catch_fish(self, events: list):
        radius = float(self.t["catch_radius"])
        cands = [
            (math.dist(self.pos, f["pos"]), id_key(f["id"]), f)
            for f in self.fish
            if math.dist(self.pos, f["pos"]) <= radius
        ]
        if not cands:
            return
        cands.sort(key=lambda item: (item[0], item[1]))
        fish = cands[0][2]
        yield_amt = int(self.t["fish_yield"][fish["kind"]])
        free = self._hold_space()
        if free < yield_amt:
            events.append(("hold_full", {
                "action": "catch",
                "fish_id": fish["id"],
                "required": yield_amt,
                "free": free,
            }))
            return
        self._add_to_hold(fish["kind"], yield_amt)
        self.fish.remove(fish)
        self.catch_cd_ticks = int(round(self.t["catch_cooldown_s"] * self.tick_hz))
        events.append(("fish_caught", {"fish_id": fish["id"], "kind": fish["kind"], "yield": yield_amt}))

    def _step_oxygen(self, now_at_surface: bool, events: list) -> bool:
        """Cập nhật oxy, ngạt và ngất theo độ sâu cuối bước. Trả True nếu đã ngất."""
        if now_at_surface:
            refill = int(self.t["oxygen_refill_per_tick"])
            self.oxygen_ticks = min(self.oxygen_max, self.oxygen_ticks + refill)
            self.zero_oxy_ticks = 0
            return False
        prev_oxy = self.oxygen_ticks
        if self.oxygen_ticks > 0:
            self.oxygen_ticks -= 1
            if self.oxygen_ticks == 0:
                events.append(("oxygen_empty", {"oxygen_ticks": 0}))
        if self.oxygen_ticks > 0:
            self.zero_oxy_ticks = 0
            return False
        # Dưới nước với oxy == 0 (tính cả bước vừa chạm 0)
        self.zero_oxy_ticks += 1
        if self.zero_oxy_ticks >= int(self.t["choke_interval_ticks"]):
            self.zero_oxy_ticks = 0
            self.hp = max(0, self.hp - 1)
            events.append(("choke", {"hp": self.hp}))
            if self.hp <= 0:
                self._faint("choke", events)
                return True
        return False

    def _finish(self, reason, events):
        gather_current.end_for_phase(self, events)
        self.done = True
        self.reason = reason
        events.append(("gather_end", {"reason": reason, "inventory": {"items": self.inventory_items()}}))

    def _move(self, inp):
        speed = self.t["swim_speed"]
        mx, md = inp.move
        self.vel = ramp_velocity(self, (mx * speed, md * speed), int(self.t["ramp_max_ticks"]))
        if (mx, md) != (0.0, 0.0):
            self.heading = math.degrees(math.atan2(md, mx)) % 360
        b = self.t["bounds"]
        for i, axis in enumerate(AXES):
            self.pos[i] += self.vel[i] / self.tick_hz
            lo, hi = b[axis]
            if self.pos[i] <= lo:
                self.pos[i] = lo
                self.vel[i] = max(0.0, self.vel[i])
            elif self.pos[i] >= hi:
                self.pos[i] = hi
                self.vel[i] = min(0.0, self.vel[i])


def _load_monster_module():
    try:
        from . import gather_monsters
        return gather_monsters
    except ImportError:
        return None
