"""Buổi tối — Mở Quán. KHUNG: đi lại, chặn biên, đồng hồ, kho nạp từ file/scenario.

Lát 3 (nhungvo631-stack): quan_customers.py xử lý lịch sinh khách, chọn món đủ kho, giữ chỗ và no_dish.
Lát 4 (chur04): quan_service.py xử lý timer, bếp, bưng, phục vụ, tiền và dọn đơn.
"""

from ..freshness import is_v12, make_item, public_item
from ..ids import sort_by_id
from .ramp import ramp_velocity
from . import quan_customers, quan_service

TICK = 60.0


class QuanSim:
    mode = "quan"
    phase = "quan"

    def __init__(self, tuning, scenario, streams, ids, inventory=None):
        t = tuning["quan"]
        self.t = t
        self.v12 = is_v12(tuning)
        self.freshness_cfg = tuning.get("freshness") or {}
        self.menu = tuning["menu"]
        self.tick_hz = tuning["tick_hz"]
        self.patience_max_ticks = int(round(t["patience_s"] * self.tick_hz))
        self.eat_ticks = int(round(t["eat_s"] * self.tick_hz))
        self.phase_tick = 0
        self.rng = streams
        self.ids = ids
        p = scenario.get("player", {})
        self.pos = list(p.get("pos", t["start_pos"]))
        self.vel = [float(c) for c in p.get("vel", [0.0, 0.0])]
        self._tgt = None
        self._ramp_left = 0
        # kho: --inventory HOẶC scenario.stock (cả hai -> cli đã báo mã 2)
        if self.v12:
            raw_stock = inventory if inventory is not None else scenario.get("stock", [])
            self.stock = [make_item(it["id"], it["kind"], it["fresh"]) for it in raw_stock]
            for it in self.stock:
                ids.reserve(it["id"])
        else:
            self.stock = dict(inventory if inventory is not None else scenario.get("stock", {}))
        self.hand = dict(scenario["hand"]) if isinstance(scenario.get("hand"), dict) else scenario.get("hand")
        self.time_left_ticks = scenario.get("time_left_ticks", int(round(t["duration_s"] * 60)))
        self.reputation = scenario.get("reputation", t["reputation_initial"])
        self.stoves = [dict(s, state=s.get("state", "idle"), dish=s.get("dish"),
                            cook_ticks_left=s.get("cook_ticks_left", 0), ready_ticks=s.get("ready_ticks", 0))
                       for s in self._merge(t["stoves"], scenario.get("stoves", []))]
        self.tables = self._merge(t["tables"], scenario.get("tables", []))
        self.customers = [dict(c) for c in scenario.get("customers", [])]
        for stove in self.stoves:
            if isinstance(stove["dish"], dict):
                stove["dish"] = dict(stove["dish"])
        quan_service.prepare_customers(self)
        for e in self.customers:
            ids.reserve(e["id"])
        self.customer_spawner = quan_customers.CustomerSpawner(self, scenario)
        self.money = 0
        self.earned = 0
        self.shift_earned = 0
        self.done = False
        self.reason = None

    @staticmethod
    def _merge(defaults, updates):
        by_id = {d["id"]: dict(d) for d in defaults}
        for u in updates:
            if u["id"] not in by_id:
                from ..errors import BadInput
                raise BadInput(f"id bếp/bàn không tồn tại: {u['id']}")
            by_id[u["id"]].update(u)
        return sort_by_id(list(by_id.values()))

    def snapshot(self) -> dict:
        occupied = {c["table_id"]: c["id"] for c in self.customers}
        stock_snap = (
            [public_item(it) for it in sort_by_id(self.stock)]
            if self.v12
            else {k: self.stock[k] for k in sorted(self.stock) if self.stock[k] > 0}
        )
        return {
            "player": {"pos": list(self.pos)},
            "stock": stock_snap,
            "hand": dict(self.hand) if isinstance(self.hand, dict) else self.hand,
            "stoves": [{k: (dict(s[k]) if k == "dish" and isinstance(s.get(k), dict) else s.get(k))
                        for k in ("id", "pos", "state", "dish", "cook_ticks_left", "ready_ticks")}
                       for s in sort_by_id(self.stoves)],
            "tables": [{"id": tb["id"], "pos": list(tb["pos"]), "customer_id": occupied.get(tb["id"])}
                       for tb in sort_by_id(self.tables)],
            "customers": [
                {k: (list(v) if isinstance(v, list) else dict(v) if isinstance(v, dict) else v)
                 for k, v in c.items()}
                for c in sort_by_id(self.customers)
            ],
        }

    def step(self, inp):
        if self.done:
            return []
        events = []
        self.phase_tick += 1
        self.time_left_ticks = max(0, self.time_left_ticks - 1)
        quan_service.advance_timers(self)
        if self.v12:
            quan_service.decay_stock_and_recheck_reservations(self, events)
        quan_service.ready_dishes(self, events)
        self._move(inp)
        if inp.pressed("interact"):
            quan_service.interact(self, events)
        quan_service.settle_customers(self, events)
        if self.time_left_ticks <= 0:
            self.done = True
            self.reason = "time"
            events.append(("quan_end", {"reason": "time", "money": self.money, "earned": self.earned,
                                        "shift_earned": self.shift_earned, "reputation": self.reputation}))
        else:
            self.customer_spawner.step(events)
        return events

    def _move(self, inp):
        speed = self.t["walk_speed"]
        mx, mz = inp.move
        self.vel = ramp_velocity(self, (mx * speed, mz * speed), int(self.t.get("ramp_max_ticks", 6)))
        b = self.t["bounds"]
        for i, axis in enumerate(("x", "z")):
            self.pos[i] += self.vel[i] / TICK
            lo, hi = b[axis]
            if self.pos[i] <= lo:
                self.pos[i], self.vel[i] = lo, max(0.0, self.vel[i])
            elif self.pos[i] >= hi:
                self.pos[i], self.vel[i] = hi, min(0.0, self.vel[i])
