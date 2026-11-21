"""Ticket-02: vòng ngày, kế hoạch và Shop. Pause do runner.Session xử lý.

Không thêm tick giới thiệu vào headless: mỗi lần đổi pha dựng ngay pha mới
với phase_tick=0, chỉ chạy gameplay từ bước sau. UI tự trình bày intro/result.
"""

import copy

from ..errors import BadInput
from ..freshness import is_v12, public_item
from ..ids import sort_by_id
from .day_config import plans, validate_day_scenario
from .gather import GatherSim
from .quan import QuanSim


class DaySim:
    mode = "day"

    def __init__(self, tuning, scenario, streams, ids, days=1):
        if isinstance(days, bool) or not isinstance(days, int) or not 1 <= days <= 5:
            raise BadInput("days phải là số nguyên trong [1, 5]")
        self.tuning = tuning
        self.v12 = is_v12(tuning)
        self.scenario = validate_day_scenario(scenario, tuning)
        self.rng, self.ids = streams, ids
        self.days = days
        state = self.scenario.get("day", {})
        self.plans = plans(tuning, state.get("day_plan"))
        if any(day not in self.plans for day in range(1, days + 1)):
            raise BadInput("day_plan thiếu Ngày cần chạy")
        self.money = state.get("money", 0)
        self.earned = state.get("earned", 0)
        self.reputation = state.get("reputation", tuning["quan"]["reputation_initial"])
        self.upgrades = dict(state.get("upgrades", {}))
        self.active_upgrades = {}
        self.day = 1
        self.days_completed = 0
        self.done, self.reason = False, None
        self.stock = [] if self.v12 else {}
        self.initial_events = []
        self._start_day(self.initial_events)

    @property
    def time_left_ticks(self):
        return self.shop_left if self.phase == "shop" else self.current.time_left_ticks

    def _event(self, name, data=None):
        return {"phase": self.phase, "day": self.day, "name": name, "data": {} if data is None else data}

    def _start_day(self, events):
        self.phase, self.phase_tick = "gather", 0
        self.active_upgrades = dict(self.upgrades)
        self.stock = [] if self.v12 else {}
        self.day_plan = copy.deepcopy(self.plans[self.day])
        effective = copy.deepcopy(self.tuning)
        for name, field in (("oxygen", "oxygen_max_s"), ("hp", "hp_max")):
            level = self.active_upgrades.get(name, 0)
            if level:
                effective["gather"][field] = effective["shop"]["upgrades"][name][level - 1][field]
        # Ngữ cảnh day được truyền trước khi dựng quái (M2 từ Ngày 3); Ngày 2+ cấp id mới cho hold.
        self.current = GatherSim(
            effective,
            copy.deepcopy(self.scenario.get("gather", {})),
            self.rng,
            self.ids,
            day=self.day,
            reallocate_hold_ids=(self.day > 1),
        )
        self._carry_into_phase()
        events.extend([self._event("day_start"), self._event("day_plan", {
            "dishes": dict(self.day_plan["dishes"]), "ingredients": dict(self.day_plan["ingredients"])}),
            self._event("phase_start")])

    def _carry_into_phase(self):
        self.current.money, self.current.earned, self.current.reputation = self.money, self.earned, self.reputation

    def _start_quan(self, events):
        from ..scenario import validate_phase_block

        self.stock = self.current.inventory_items()
        effective = copy.deepcopy(self.tuning)
        effective["menu"] = {dish: effective["menu"][dish] for dish in self.day_plan["dishes"]}
        block = copy.deepcopy(self.scenario.get("quan", {}))
        block["stock"] = copy.deepcopy(self.stock) if self.v12 else dict(self.stock)
        block["reputation"] = self.reputation
        # Kiểm khách/bếp/món trên kho thực khi mở quán, như mục 4.3.
        validate_phase_block(block, "quan", self.tuning)
        self.current = QuanSim(effective, block, self.rng, self.ids, inventory=None)
        self._carry_into_phase()
        self.phase, self.phase_tick = "quan", 0
        events.append(self._event("phase_start"))

    def _start_shop(self, events):
        if self.v12:
            self.stock = [public_item(it) for it in sort_by_id(self.current.stock)]
        else:
            self.stock = {k: v for k, v in self.current.stock.items() if v > 0}
        self.phase, self.phase_tick = "shop", 0
        self.shop_left = self.tuning["shop"]["max_ticks"]
        events.append(self._event("phase_start"))

    def snapshot(self):
        if self.phase != "shop":
            detail = self.current.snapshot()
        elif self.v12:
            detail = {"stock": copy.deepcopy(self.stock)}
        else:
            detail = {"stock": dict(sorted(self.stock.items()))}
        return {**detail, "day": self.day, "day_plan": copy.deepcopy(self.day_plan),
                "upgrades": dict(self.upgrades), "active_upgrades": dict(self.active_upgrades)}

    def step(self, inp):
        if self.done:
            return []
        self.phase_tick += 1
        if self.phase == "shop":
            return self._step_shop(inp)
        events = [self._event(name, data) for name, data in self.current.step(inp)]
        self.money, self.earned, self.reputation = self.current.money, self.current.earned, self.current.reputation
        if self.current.done:
            if self.phase == "gather":
                self._start_quan(events)
            else:
                self._start_shop(events)
        return events

    def _buy(self, action, events):
        upgrades = self.tuning["shop"]["upgrades"]
        reason = None
        if action not in upgrades:
            reason = "unknown"
        else:
            level = self.upgrades.get(action, 0)
            if level >= len(upgrades[action]):
                reason = "max_level"
            else:
                offer = upgrades[action][level]
                if self.money < offer["price"]:
                    reason = "funds"
                else:
                    self.money -= offer["price"]
                    self.upgrades[action] = offer["level"]
                    events.append(self._event("bought", {"upgrade": action, "level": offer["level"],
                                                         "price": offer["price"], "money": self.money}))
        if reason:
            events.append(self._event("buy_failed", {"action": action, "reason": reason}))

    def _step_shop(self, inp):
        events = []
        self.shop_left = max(0, self.shop_left - 1)
        if inp.buy is not None:
            self._buy(inp.buy, events)
        if inp.pressed("shop_done") or self.shop_left == 0:
            events.append(self._event("shop_end", {"reason": "done" if inp.pressed("shop_done") else "time"}))
            self.days_completed += 1
            if self.days_completed == self.days:
                self.done, self.reason = True, "days_complete"
            else:
                self.day += 1
                self._start_day(events)
        return events
