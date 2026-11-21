"""Cửa sổ chơi trực tiếp bằng TRÌNH DUYỆT (Phase 2 — v1.1 UI), chỉ dùng thư viện chuẩn Python.

    python3 -m chonoi.live --mode gather|quan|day [--days 5] [--seed N] [--port 8000] [--extra-content]

Máy chủ HTTP nhỏ (ThreadingHTTPServer) phục vụ `chonoi/web/index.html`, sprite assets và các API:
    GET  /state   -> snapshot JSON hiện tại + `meta`, `menu`, `events`, `screen`, `paused`, `shop`, `day_plan`
    POST /input   -> {"move": [a, b], "interact": bool, "catch": bool, "pause": bool, "shop_done": bool, "buy": str|null}
    POST /action  -> {"action": "start"|"pause"|"resume"|"menu"|"exit"|"skip_intro"|"open_shop"|"buy"|"shop_done", ...}
    POST /restart -> chơi lại từ đầu (cùng seed, cùng scenario)

Mô phỏng chạy 60 tick/s trong một luồng nền, dùng CÙNG lớp sim như headless (qua `runner.Session`).
Chế độ `--mode day` tự dùng `runner.Session("day", ...)` khi lõi `chonoi/sim/day.py` có mặt, hoặc ghép
`GatherSim` + `QuanSim` + Shop tạm ở live để chạy trọn vòng Ngày 1..5 mà không đụng tới headless.
"""

import argparse
import copy
import json
import math
import os
import random
import sys
import threading
import time
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .contract import load_contract
from .errors import BadInput
from .freshness import is_spoiled, is_v12, item_frac, make_item, public_item
from .ids import id_key, sort_by_id
from .inputs import LiveInputs
from .inventory import KINDS_P2, read_inventory
from .runner import Session
from .scenario import load_scenario
from .sim.quan import QuanSim

WEB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web")
EXTRA_CONTENT_PATH = os.path.join(os.path.dirname(WEB_DIR), "extra_content.json")
TICK_S = 1.0 / 60.0
MAX_BODY = 4096
RECENT_EVENTS = 60
DAY_INTRO_TICKS = 240      # 4 giây (bấm phím để bỏ qua)
EVENING_INTRO_TICKS = 210  # 3.5 giây (bấm phím để bỏ qua)
SHOP_DEFAULT_TICKS = 600   # 10 giây (bản live không tự đóng Shop để người chơi thong thả nói chuyện Anh Ba)
MARKET_SELL_PRICES = {
    "ca_loc": 20,
    "ca_linh": 8,
    "ca_keo": 10,
    "bong_dien_dien": 5,
    "bong_sung": 5,
    "keo_neo": 5,
    "ca_ro_dong": 14,
    "rau_muong": 5,
}
MARKET_MAX_BUYS_PER_DAY = 3
MARKET_MAX_BUY_PER_KIND = 2

# Vật phẩm dưới nước & sứa (chỉ chạy ở chế độ live, tắt hoàn toàn ở headless để bảo toàn Test Contract)
PICKUP_RADIUS = 1.85
JELLYFISH_RADIUS = 1.55
OXYGEN_TANK_RESTORE_RATIO = 0.35
FINS_DURATION_TICKS = 600        # 10s tăng tốc (+35%)
FINS_SPEED_MULT = 1.35
SUIT_DURATION_TICKS = 720        # 12s tăng tốc mạnh (+55%) & kháng chậm một phần
SUIT_SPEED_MULT = 1.55
AMULET_DURATION_TICKS = 480      # 8s không mất máu, không hao oxy, miễn nhiễm sứa
JELLY_SLOW_TICKS = 210           # 3.5s bị làm chậm khi chạm sứa
JELLY_SLOW_MULT = 0.52
JELLY_SUIT_SLOW_MULT = 0.72
JELLY_COOLDOWN_TICKS = 90        # 1.5s hồi va chạm mỗi con sứa

LIVE_BUTTONS = ("interact", "catch", "pause", "shop_done", "attack", "photo")


class _LiveUnderwaterExtras:
    """Quản lý vật phẩm hỗ trợ dưới nước (bình oxy mini, chân vịt, đồ lặn, bùa hộ mệnh 8s)
    và sứa làm chậm — thuần lớp live, không sửa GatherSim hay ảnh hưởng headless."""

    def __init__(self, bounds: dict, seed: int, day: int):
        self.x_lo, self.x_hi = float(bounds["x"][0]), float(bounds["x"][1])
        self.d_lo, self.d_hi = float(bounds["d"][0]), float(bounds["d"][1])
        self.rng = random.Random(int(seed) * 997 + int(day) * 131 + 17)
        self._next_pickup_id = 1
        self.pickups = []
        self.respawn_queue = []  # [(ticks_left, kind)]
        self.jellyfish = []
        self.speed_ticks = 0
        self.speed_kind = None
        self.speed_mult = 1.0
        self.amulet_ticks = 0
        self.slow_ticks = 0
        self._spawn_initial(day)

    def _depth_range_for(self, kind: str):
        max_d = max(8.0, self.d_hi - 2.2)
        if kind == "oxygen_tank":
            return (min(6.0, max_d * 0.35), min(25.0, max_d))
        if kind == "fins":
            return (min(6.0, max_d * 0.35), min(17.0, max_d * 0.72))
        if kind == "diving_suit":
            return (min(11.0, max_d * 0.5), min(23.0, max_d * 0.9))
        # amulet: sâu hơn để tạo thưởng xứng đáng
        return (min(14.0, max_d * 0.6), min(26.0, max_d))

    def _new_pickup(self, kind: str, depth_override=None) -> dict:
        d_min, d_max = depth_override if depth_override is not None else self._depth_range_for(kind)
        if d_max < d_min:
            d_min, d_max = 5.0, max(6.0, self.d_hi - 2.0)
        x_lo = min(self.x_hi - 6.0, max(self.x_lo + 12.0, 12.0))
        x_hi = max(x_lo + 2.0, self.x_hi - 6.0)
        px = self.rng.uniform(x_lo, x_hi)
        pd = self.rng.uniform(d_min, d_max)
        pid = f"P{self._next_pickup_id}"
        self._next_pickup_id += 1
        return {"id": pid, "kind": kind, "pos": [px, pd], "phase": self.rng.uniform(0.0, math.tau)}

    def _spawn_initial(self, day: int):
        max_d = max(8.0, self.d_hi - 2.2)
        # Vừa đủ 4 vật phẩm hỗ trợ rải khắp dòng sông (không quá dày)
        self.pickups.append(self._new_pickup("oxygen_tank", (min(11.0, max_d * 0.45), min(22.0, max_d * 0.85))))
        self.pickups.append(self._new_pickup("fins", (min(8.0, max_d * 0.35), min(17.0, max_d * 0.7))))
        self.pickups.append(self._new_pickup("diving_suit", (min(14.0, max_d * 0.55), min(24.0, max_d * 0.92))))
        self.pickups.append(self._new_pickup("amulet", (min(16.0, max_d * 0.62), min(26.0, max_d))))
        # Sứa (4 con cơ bản, từ ngày 3 trở đi có 5 con)
        jelly_count = 5 if day >= 3 else 4
        x_lo = min(self.x_hi - 8.0, max(self.x_lo + 14.0, 14.0))
        x_hi = max(x_lo + 4.0, self.x_hi - 8.0)
        span = (x_hi - x_lo) / max(1, jelly_count)
        for i in range(jelly_count):
            jx = x_lo + span * (i + 0.5) + self.rng.uniform(-span * 0.25, span * 0.25)
            base_d = self.rng.uniform(min(6.0, max_d * 0.35), min(23.0, max_d * 0.88))
            vx = self.rng.choice([-1.0, 1.0]) * self.rng.uniform(0.85, 1.55)
            self.jellyfish.append({
                "id": f"J{i + 1}",
                "pos": [jx, base_d],
                "base_d": base_d,
                "vx": vx,
                "amp": self.rng.uniform(1.1, 2.2),
                "freq": self.rng.uniform(0.9, 1.5),
                "phase": self.rng.uniform(0.0, math.tau),
                "hit_cd": 0,
            })

    def before_sim_step(self, sim):
        if not hasattr(sim, "_live_base_swim_speed"):
            sim._live_base_swim_speed = float(sim.t["swim_speed"])
        base_speed = sim._live_base_swim_speed
        boost = self.speed_mult if self.speed_ticks > 0 else 1.0
        if self.slow_ticks > 0:
            slow = JELLY_SUIT_SLOW_MULT if (self.speed_ticks > 0 and self.speed_kind == "diving_suit") else JELLY_SLOW_MULT
        else:
            slow = 1.0
        sim.t["swim_speed"] = base_speed * boost * slow
        if self.amulet_ticks > 0:
            saved_oxy = sim.oxygen_ticks
            saved_hp = sim.hp
            bumped = False
            if saved_oxy <= 1 and sim.oxygen_max >= 2:
                sim.oxygen_ticks = 2
                bumped = True
            sim.invuln_ticks = max(sim.invuln_ticks, 2)
            return (saved_oxy, saved_hp, bumped)
        return None

    def after_sim_step(self, sim, saved_amulet, emit_event):
        if saved_amulet is not None:
            saved_oxy, saved_hp, bumped = saved_amulet
            if bumped and not sim._at_surface():
                sim.oxygen_ticks = saved_oxy
            else:
                sim.oxygen_ticks = max(sim.oxygen_ticks, saved_oxy)
            sim.hp = max(sim.hp, saved_hp)
            sim.zero_oxy_ticks = 0
            self.amulet_ticks = max(0, self.amulet_ticks - 1)
            if self.amulet_ticks == 0:
                emit_event("buff_expired", {"kind": "amulet"}, phase="gather")

        if self.speed_ticks > 0:
            self.speed_ticks -= 1
            if self.speed_ticks == 0:
                expired_kind = self.speed_kind
                self.speed_kind = None
                self.speed_mult = 1.0
                if expired_kind:
                    emit_event("buff_expired", {"kind": expired_kind}, phase="gather")

        if self.slow_ticks > 0:
            self.slow_ticks -= 1

        # Cập nhật chuyển động sứa (trôi ngang + nhấp nhô mềm)
        dt = 1.0 / float(getattr(sim, "tick_hz", 60.0))
        x_min, x_max = self.x_lo + 8.0, self.x_hi - 4.0
        d_min, d_max = 4.5, max(5.5, self.d_hi - 1.8)
        for jf in self.jellyfish:
            if jf["hit_cd"] > 0:
                jf["hit_cd"] -= 1
            jf["phase"] = (jf["phase"] + dt * jf["freq"]) % math.tau
            nx = jf["pos"][0] + jf["vx"] * dt
            if nx <= x_min:
                nx = x_min
                jf["vx"] = abs(jf["vx"])
            elif nx >= x_max:
                nx = x_max
                jf["vx"] = -abs(jf["vx"])
            nd = max(d_min, min(d_max, jf["base_d"] + math.sin(jf["phase"]) * jf["amp"]))
            jf["pos"][0] = nx
            jf["pos"][1] = nd

        # Hồi sinh vật phẩm đã nhặt
        if self.respawn_queue:
            still = []
            for ticks_left, kind in self.respawn_queue:
                if ticks_left <= 1:
                    self.pickups.append(self._new_pickup(kind))
                else:
                    still.append((ticks_left - 1, kind))
            self.respawn_queue = still

        if sim.done:
            return

        # Va chạm nhặt vật phẩm dưới nước
        remaining_pickups = []
        for pk in self.pickups:
            if math.dist(sim.pos, pk["pos"]) <= PICKUP_RADIUS:
                kind = pk["kind"]
                if kind == "oxygen_tank":
                    add_ticks = max(60, int(round(sim.oxygen_max * OXYGEN_TANK_RESTORE_RATIO)))
                    sim.oxygen_ticks = min(sim.oxygen_max, sim.oxygen_ticks + add_ticks)
                    sim.zero_oxy_ticks = 0
                    emit_event("pickup_item", {"id": pk["id"], "kind": kind, "oxy_s": round(add_ticks / 60.0, 1)}, phase="gather")
                elif kind == "fins":
                    if self.speed_ticks > 0 and self.speed_kind == "diving_suit":
                        self.speed_ticks = min(SUIT_DURATION_TICKS + 360, self.speed_ticks + 360)
                    else:
                        self.speed_kind = "fins"
                        self.speed_mult = FINS_SPEED_MULT
                        self.speed_ticks = FINS_DURATION_TICKS
                    emit_event("pickup_item", {"id": pk["id"], "kind": kind, "duration_s": round(FINS_DURATION_TICKS / 60.0, 1)}, phase="gather")
                elif kind == "diving_suit":
                    self.speed_kind = "diving_suit"
                    self.speed_mult = SUIT_SPEED_MULT
                    self.speed_ticks = SUIT_DURATION_TICKS
                    emit_event("pickup_item", {"id": pk["id"], "kind": kind, "duration_s": round(SUIT_DURATION_TICKS / 60.0, 1)}, phase="gather")
                elif kind == "amulet":
                    self.amulet_ticks = AMULET_DURATION_TICKS
                    self.slow_ticks = 0
                    sim.zero_oxy_ticks = 0
                    sim.invuln_ticks = max(sim.invuln_ticks, 2)
                    emit_event("pickup_item", {"id": pk["id"], "kind": kind, "duration_s": round(AMULET_DURATION_TICKS / 60.0, 1)}, phase="gather")
                respawn_lo, respawn_hi = (1560, 2160) if kind == "oxygen_tank" else (2100, 2820) if kind == "fins" else (2520, 3240)
                self.respawn_queue.append((self.rng.randint(respawn_lo, respawn_hi), kind))
            else:
                remaining_pickups.append(pk)
        self.pickups = remaining_pickups

        # Va chạm sứa (làm chậm trừ khi đang có Bùa hộ mệnh)
        for jf in self.jellyfish:
            if jf["hit_cd"] == 0 and math.dist(sim.pos, jf["pos"]) <= JELLYFISH_RADIUS:
                jf["hit_cd"] = JELLY_COOLDOWN_TICKS
                if self.amulet_ticks > 0:
                    emit_event("amulet_block", {"source": "jellyfish", "jellyfish_id": jf["id"]}, phase="gather")
                else:
                    self.slow_ticks = max(self.slow_ticks, JELLY_SLOW_TICKS)
                    emit_event("jellyfish_hit", {"jellyfish_id": jf["id"], "slow_s": round(JELLY_SLOW_TICKS / 60.0, 1)}, phase="gather")

    def snapshot(self) -> dict:
        return {
            "pickups": [
                {"id": p["id"], "kind": p["kind"], "pos": [round(p["pos"][0], 2), round(p["pos"][1], 2)], "phase": round(p["phase"], 2)}
                for p in self.pickups
            ],
            "jellyfish": [
                {"id": j["id"], "pos": [round(j["pos"][0], 2), round(j["pos"][1], 2)], "phase": round(j["phase"], 2)}
                for j in self.jellyfish
            ],
            "buffs": {
                "speed_ticks": self.speed_ticks,
                "speed_kind": self.speed_kind,
                "speed_mult": round(self.speed_mult, 2) if self.speed_ticks > 0 else 1.0,
                "amulet_ticks": self.amulet_ticks,
                "slow_ticks": self.slow_ticks,
            },
        }


def _parse_shop_catalog(tuning: dict) -> dict:
    """Đọc cấu hình Shop từ game.contract.json v1.1 nếu có; nếu còn v1.0 thì dùng mặc định an toàn."""
    shop = tuning.get("shop") if isinstance(tuning.get("shop"), dict) else {}

    def _entry(key, default_costs, default_bonus, label, unit):
        upgrades = shop.get("upgrades") if isinstance(shop.get("upgrades"), dict) else {}
        if isinstance(upgrades.get(key), list) and upgrades[key]:
            tiers = sorted(upgrades[key], key=lambda item: item.get("level", 0))
            costs = [int(item["price"]) for item in tiers]
            bonus = default_bonus
            if key == "oxygen" and "oxygen_max_s" in tiers[0]:
                base = tuning.get("gather", {}).get("oxygen_max_s", 30)
                bonus = int(tiers[0]["oxygen_max_s"]) - int(base)
            elif key == "hp" and "hp_max" in tiers[0]:
                base = tuning.get("gather", {}).get("hp_max", 3)
                bonus = int(tiers[0]["hp_max"]) - int(base)
            return {"id": key, "label": label, "unit": unit, "costs": costs, "bonus": bonus, "max_level": len(costs)}
        raw = shop.get(key)
        if not isinstance(raw, dict):
            raw = (shop.get("items") or {}).get(key) if isinstance(shop.get("items"), dict) else None
        costs = list(default_costs)
        bonus = default_bonus
        max_lvl = len(costs)
        if isinstance(raw, dict):
            if isinstance(raw.get("costs"), list) and raw["costs"]:
                costs = [int(c) for c in raw["costs"]]
                max_lvl = len(costs)
            elif isinstance(raw.get("prices"), list) and raw["prices"]:
                costs = [int(c) for c in raw["prices"]]
                max_lvl = len(costs)
            elif isinstance(raw.get("price"), (int, float)):
                base = int(raw["price"])
                max_lvl = int(raw.get("max_level", raw.get("max", 2)))
                step = int(raw.get("price_step", base))
                costs = [base + i * step for i in range(max_lvl)]
            for bkey in ("bonus_s", "oxygen_bonus_s", "bonus_hp", "hp_bonus", "delta", "bonus"):
                if isinstance(raw.get(bkey), (int, float)):
                    bonus = raw[bkey]
                    break
            if isinstance(raw.get("max_level"), int):
                max_lvl = raw["max_level"]
        return {"id": key, "label": label, "unit": unit, "costs": costs, "bonus": bonus, "max_level": max_lvl}

    dur_ticks = int(round(shop.get("duration_s", SHOP_DEFAULT_TICKS / 60.0) * 60))
    if isinstance(shop.get("max_ticks"), int):
        dur_ticks = shop["max_ticks"]
    elif isinstance(shop.get("duration_ticks"), int):
        dur_ticks = shop["duration_ticks"]
    return {
        "duration_ticks": max(60, dur_ticks),
        "items": {
            "oxygen": _entry("oxygen", [100, 200], 10, "Bình Oxy", "+{bonus}s oxy tối đa"),
            "hp": _entry("hp", [120, 240], 1, "Tăng Máu", "+{bonus} Máu tối đa"),
            "bag": {"id": "bag", "label": "Balo Lặn", "unit": "+{bonus} ô giỏ", "costs": [150, 350], "bonus": 4, "max_level": 2},
        },
    }


def _day_plan_for(tuning: dict, day: int) -> dict:
    """Lấy danh sách món & nguyên liệu mục tiêu của Má Tư cho Ngày `day` từ tuning (hoặc fallback từ menu)."""
    menu = tuning.get("menu", {})
    raw_plan = tuning.get("day_plan")
    dishes = []
    title = f"Ngày {day}"
    if isinstance(raw_plan, list) and 1 <= day <= len(raw_plan):
        entry = raw_plan[day - 1]
        if isinstance(entry, dict):
            dishes = list(entry.get("dishes") or entry.get("menu") or [])
            title = entry.get("title") or entry.get("note") or title
        elif isinstance(entry, list):
            dishes = list(entry)
    elif isinstance(raw_plan, dict):
        entry = raw_plan.get(str(day)) or raw_plan.get(f"D{day}") or raw_plan.get(f"day_{day}")
        if isinstance(entry, dict):
            dishes = list(entry.get("dishes") or entry.get("menu") or [])
            title = entry.get("title") or entry.get("note") or title
        elif isinstance(entry, list):
            dishes = list(entry)
    dishes = [d for d in dishes if d in menu]
    if not dishes:
        all_dishes = list(menu.keys())
        count = min(len(all_dishes), 2 + day)
        dishes = all_dishes[:max(1, count)]
    needed = {}
    for dish_id in dishes:
        recipe = (menu.get(dish_id) or {}).get("recipe") or {}
        for kind, qty in recipe.items():
            needed[kind] = needed.get(kind, 0) + int(qty)
    return {"day": day, "title": title, "dishes": dishes, "needed": needed}


def _try_native_day_session(tuning, scenario, seed, days):
    """Giao diện live dùng trình điều phối 6 màn hình (Menu/DayIntro/EveningIntro/DayResult/Shop/Summary)
    bọc trực tiếp Session('gather') và Session('quan'); headless `--mode day` chạy thẳng DaySim."""
    return None


class LiveGame:
    """Một lượt chơi + luồng nền bước 60 tick/s. Mọi truy cập trạng thái đi qua khóa."""

    def __init__(self, mode, tuning, scenario, seed, inventory=None, inventory_out=None,
                 days=5, start_at_menu=None):
        self._base_tuning = copy.deepcopy(tuning)
        self._scenario = copy.deepcopy(scenario or {})
        self._seed = seed
        self._initial_inventory = copy.deepcopy(inventory) if inventory is not None else None
        self.mode = mode
        self.tuning = copy.deepcopy(tuning)
        self.inventory_out = inventory_out
        self.days_total = max(1, min(5, int(days)))
        self._start_at_menu = (mode == "day") if start_at_menu is None else bool(start_at_menu)
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread = None
        self._reset()

    def _reset(self):
        self.tuning = copy.deepcopy(self._base_tuning)
        self.inputs = LiveInputs(buttons=LIVE_BUTTONS)
        self.events = []
        self._saved = False
        self.error = None
        self.paused = False
        self._outer_tick = 0
        self.day = 1
        self.days_completed = 0
        self.active_upgrades = {"oxygen": 0, "hp": 0, "bag": 0}
        self.pending_upgrades = {"oxygen": 0, "hp": 0, "bag": 0}
        self._shop_cfg = _parse_shop_catalog(self.tuning)
        self.shop_ticks_left = 0
        self.last_gather_inventory = {"items": [] if is_v12(self.tuning) else {}}
        self.last_gather_reason = None
        self.last_day_summary = None
        self.carry_money = 0
        self.carry_earned = 0
        self.carry_reputation = self.tuning["quan"]["reputation_initial"]
        self._native_day = False
        self._prev_pause_held = False
        self._prev_shop_done_held = False
        self._shop_open = False
        self.screen_ticks_left = 0
        self.market_buys_today = 0
        self.market_buys_by_kind = {}
        self.shop_last_note = ""
        self.market_last_note = ""
        self._underwater = None

        if self.mode == "day":
            native = _try_native_day_session(self.tuning, self._scenario, self._seed, self.days_total)
            if native is not None:
                self._native_day = True
                self.session = native
                self.screen = "menu" if self._start_at_menu else "day_intro"
                self.screen_ticks_left = 0 if self._start_at_menu else DAY_INTRO_TICKS
            else:
                self.session = self._build_day_gather_session(day=1)
                self.screen = "menu" if self._start_at_menu else "day_intro"
                self.screen_ticks_left = 0 if self._start_at_menu else DAY_INTRO_TICKS
        else:
            self.session = Session(self.mode, self.tuning, self._scenario, self._seed, self._initial_inventory)
            if self.mode == "gather":
                self._underwater = _LiveUnderwaterExtras(self.tuning["gather"]["bounds"], self._seed, day=1)
            self.screen = "menu" if self._start_at_menu else "playing"
            self.screen_ticks_left = 0

    def _emit_live_event(self, name: str, data: dict, phase: str = None):
        ph = phase or getattr(self.session.sim, "phase", self.mode)
        self.events.append({"type": "event", "tick": self._outer_tick, "phase": ph, "name": name, "data": data})
        del self.events[:-RECENT_EVENTS]

    def _tuned_for_day(self, day: int) -> dict:
        t = copy.deepcopy(self._base_tuning)
        oxy_lvl = self.active_upgrades.get("oxygen", 0)
        hp_lvl = self.active_upgrades.get("hp", 0)
        bag_lvl = self.active_upgrades.get("bag", 0)
        oxy_bonus = self._shop_cfg["items"]["oxygen"]["bonus"]
        hp_bonus = self._shop_cfg["items"]["hp"]["bonus"]
        bag_bonus = self._shop_cfg["items"]["bag"]["bonus"]
        t["gather"]["oxygen_max_s"] = t["gather"]["oxygen_max_s"] + oxy_lvl * oxy_bonus
        t["gather"]["hp_max"] = int(t["gather"]["hp_max"] + hp_lvl * hp_bonus)
        t["gather"]["hold_capacity"] = int(t["gather"]["hold_capacity"] + bag_lvl * bag_bonus)
        return t

    def _build_day_gather_session(self, day: int) -> Session:
        day_tuning = self._tuned_for_day(day)
        # Chế độ live --mode day: tăng nhẹ (~1.45x trọng số, tức +3–8% xác suất) cho loài cá nằm trong thực đơn hôm nay
        plan = _day_plan_for(day_tuning, day)
        fw = day_tuning.get("gather", {}).get("fish_weights")
        if isinstance(fw, dict) and fw:
            needed_fish = {k for k in plan.get("needed", {}) if k in fw}
            if needed_fish and len(needed_fish) < len(fw):
                boosted = {
                    k: float(w) * (1.45 if k in needed_fish else 1.0)
                    for k, w in fw.items()
                }
                total_w = sum(boosted.values())
                if total_w > 0:
                    day_tuning["gather"]["fish_weights"] = {k: round(v / total_w, 4) for k, v in boosted.items()}
        self.tuning = day_tuning
        sess = Session("gather", day_tuning, {}, self._seed + day * 101)
        sess.sim.day = day
        sess.sim.money = self.carry_money
        sess.sim.earned = self.carry_earned
        sess.sim.reputation = self.carry_reputation
        self._underwater = _LiveUnderwaterExtras(day_tuning["gather"]["bounds"], self._seed, day=day)
        return sess

    def _build_day_quan_session(self, day: int, inv_items) -> Session:
        day_tuning = self._tuned_for_day(day)
        plan = _day_plan_for(day_tuning, day)
        # Trong chế độ day, lọc thực đơn theo day_plan của Ngày hiện tại
        filtered_menu = {k: v for k, v in day_tuning["menu"].items() if k in plan["dishes"]}
        if filtered_menu:
            day_tuning["menu"] = filtered_menu
        self.tuning = day_tuning
        inv_copy = copy.deepcopy(inv_items) if isinstance(inv_items, list) else dict(inv_items)
        sess = Session("quan", day_tuning, {}, self._seed + day * 202, inventory=inv_copy)
        sess.sim.money = self.carry_money
        sess.sim.earned = self.carry_earned
        sess.sim.reputation = self.carry_reputation
        self._underwater = None
        return sess

    # --- luồng nền ----------------------------------------------------------------
    def start(self):
        self._thread = threading.Thread(target=self._loop, name="chonoi-sim", daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)

    def _loop(self):
        nxt = time.perf_counter()
        while not self._stop.is_set():
            nxt += TICK_S
            with self._lock:
                try:
                    self._tick_once()
                except Exception:  # luật của nhóm lỗi: báo ra terminal + client, dừng bước (restart để chơi lại)
                    self.error = traceback.format_exc()
                    sys.stderr.write(self.error)
                    self.session.sim.done = True
                    self.session.sim.reason = "error"
            delay = nxt - time.perf_counter()
            if delay > 0:
                self._stop.wait(delay)
            elif delay < -0.25:  # chạy chậm quá thì bỏ bù, tránh chạy dồn
                nxt = time.perf_counter()

    def _tick_once(self):
        if self.screen in ("menu", "exited", "summary", "day_result", "market"):
            return
        if self.paused:
            self._outer_tick += 1
            return

        # Intro screens — dừng khi pause; không tự skip đột ngột khi đã hết đếm để người chơi kịp đọc thoại Má Tư
        if self.screen in ("day_intro", "evening_intro"):
            self._outer_tick += 1
            if self.screen_ticks_left > 0:
                self.screen_ticks_left -= 1
            return

        # Live Shop: giữ bộ đếm hiển thị tương thích test nhưng KHÔNG tự đóng ép người chơi (bỏ giới hạn thời gian)
        if self.screen == "shop" and not self._native_day:
            self._outer_tick += 1
            if self.shop_ticks_left > 0:
                self.shop_ticks_left -= 1
            return

        s = self.session
        if s.done:
            return
        self._outer_tick += 1
        uw = self._underwater if getattr(s.sim, "mode", None) == "gather" else None
        saved_amulet = uw.before_sim_step(s.sim) if uw is not None else None
        for row in s.step(self.inputs.advance()):
            self.events.append(row)
        if uw is not None:
            uw.after_sim_step(s.sim, saved_amulet, self._emit_live_event)
        del self.events[:-RECENT_EVENTS]

        if s.done:
            if self.mode == "day" and not self._native_day:
                self._advance_live_day_phase_locked()
            elif not self._saved:
                self._saved = True
                if self.inventory_out:
                    try:
                        s.write_inventory_if_done(self.inventory_out)
                    except OSError as e:
                        sys.stderr.write(f"lỗi ghi kho: {e}\n")

    def _finish_intro_locked(self):
        if self.screen == "day_intro":
            self.screen = "playing"
            self.screen_ticks_left = 0
            self._emit_live_event("day_start", {"day": self.day, "plan": _day_plan_for(self._base_tuning, self.day)}, phase="gather")
        elif self.screen == "evening_intro":
            self.screen = "playing"
            self.screen_ticks_left = 0
            self._emit_live_event("phase_start", {"day": self.day, "phase": "quan"}, phase="quan")

    def _advance_live_day_phase_locked(self):
        sim = self.session.sim
        if sim.mode == "gather":
            items = sim.inventory_items()
            self.last_gather_inventory = {"items": items}
            self.last_gather_reason = sim.reason
            self.carry_money = sim.money
            self.carry_earned = sim.earned
            self.carry_reputation = sim.reputation
            self.market_buys_today = 0
            self.market_buys_by_kind = {}
            self.market_last_note = ""
            self.session = self._build_day_quan_session(self.day, items)
            self.inputs = LiveInputs(buttons=LIVE_BUTTONS)
            self.screen = "evening_intro"
            self.screen_ticks_left = EVENING_INTRO_TICKS
        elif sim.mode == "quan":
            self.carry_money = sim.money
            self.carry_earned = sim.earned
            self.carry_reputation = sim.reputation
            self.days_completed = self.day
            self.last_day_summary = {
                "day": self.day,
                "shift_earned": getattr(sim, "shift_earned", 0),
                "money": sim.money,
                "earned": sim.earned,
                "reputation": sim.reputation,
                "score": self.session.snapshot().get("score", 0),
                "reason": sim.reason,
            }
            if self.day >= self.days_total:
                self.screen = "summary"
                self._emit_live_event("day_end", {"day": self.day, "reason": "days_complete"}, phase="quan")
            else:
                self.screen = "day_result"

    def _open_shop_locked(self):
        if self.mode != "day" or self._native_day:
            return
        self.screen = "shop"
        self._shop_open = True
        self.shop_ticks_left = self._shop_cfg["duration_ticks"]
        self.shop_last_note = ""
        self._emit_live_event("phase_start", {"day": self.day, "phase": "shop"}, phase="shop")

    def _market_state_locked(self) -> dict:
        plan = _day_plan_for(self._base_tuning, self.day)
        needed_kinds = set(plan["needed"].keys())
        sim = self.session.sim
        spoiled_below = self.tuning.get("freshness", {}).get("spoiled_below", 30)
        stock_items = sim.stock if getattr(sim, "mode", None) == "quan" else []
        sellable = {}
        if isinstance(stock_items, list):
            for it in stock_items:
                k = it["kind"]
                if k not in needed_kinds and not is_spoiled(it, spoiled_below):
                    sellable[k] = sellable.get(k, 0) + 1
        elif isinstance(stock_items, dict):
            for k, qty in stock_items.items():
                if k not in needed_kinds and qty > 0:
                    sellable[k] = qty
        buyable = {}
        for k in sorted(needed_kinds):
            base = MARKET_SELL_PRICES.get(k, 10)
            bought_k = self.market_buys_by_kind.get(k, 0)
            rem_k = max(0, min(MARKET_MAX_BUY_PER_KIND - bought_k, MARKET_MAX_BUYS_PER_DAY - self.market_buys_today))
            buyable[k] = {"price": int(base * 1.5), "remaining": rem_k, "bought": bought_k}
        return {
            "open": self.screen == "market",
            "needed_kinds": sorted(needed_kinds),
            "sell_prices": dict(MARKET_SELL_PRICES),
            "sellable": sellable,
            "buyable": buyable,
            "buys_used": self.market_buys_today,
            "buys_max": MARKET_MAX_BUYS_PER_DAY,
            "buys_per_kind_max": MARKET_MAX_BUY_PER_KIND,
            "last_note": self.market_last_note,
        }

    def _market_sell_locked(self, kind: str) -> dict:
        if self.screen != "market" or self.paused:
            return {"ok": False, "reason": "market_closed"}
        sim = self.session.sim
        if getattr(sim, "mode", None) != "quan":
            return {"ok": False, "reason": "wrong_phase"}
        plan = _day_plan_for(self._base_tuning, self.day)
        if kind in plan["needed"]:
            self.market_last_note = "Ông Năm: Món này có trong thực đơn tối nay đó cháu, giữ lại mà nấu nghe!"
            return {"ok": False, "reason": "in_plan"}
        price = MARKET_SELL_PRICES.get(kind, 5)
        spoiled_below = self.tuning.get("freshness", {}).get("spoiled_below", 30)
        if isinstance(sim.stock, list):
            cands = [it for it in sim.stock if it["kind"] == kind and not is_spoiled(it, spoiled_below)]
            if not cands:
                self.market_last_note = "Ông Năm: Trong giỏ không còn hàng tươi loại này để bán rồi cháu ơi!"
                return {"ok": False, "reason": "out_of_stock"}
            cands.sort(key=lambda it: (-item_frac(it), id_key(it["id"])))
            chosen = cands[0]
            sim.stock.remove(chosen)
            self.last_gather_inventory = {"items": [public_item(it) for it in sort_by_id(sim.stock)]}
        else:
            if sim.stock.get(kind, 0) <= 0:
                return {"ok": False, "reason": "out_of_stock"}
            sim.stock[kind] -= 1
            if sim.stock[kind] <= 0:
                del sim.stock[kind]
            self.last_gather_inventory = {"items": dict(sim.stock)}
        self.carry_money += price
        self.carry_earned += price
        sim.money = self.carry_money
        sim.earned = self.carry_earned
        self.market_last_note = f"Ông Năm: Ông mua giùm cháu 1 phần (+{price}k), tiền tươi thóc thật nè!"
        self._emit_live_event("vendor_trade", {"action": "sell", "kind": kind, "price": price, "money": self.carry_money}, phase="market")
        return {"ok": True, "action": "sell", "kind": kind, "price": price, "money": self.carry_money}

    def _market_buy_locked(self, kind: str) -> dict:
        if self.screen != "market" or self.paused:
            return {"ok": False, "reason": "market_closed"}
        sim = self.session.sim
        if getattr(sim, "mode", None) != "quan":
            return {"ok": False, "reason": "wrong_phase"}
        plan = _day_plan_for(self._base_tuning, self.day)
        if kind not in plan["needed"]:
            self.market_last_note = "Ông Năm: Chợ ông chỉ bán đồ đúng thực đơn bữa nay thôi cháu!"
            return {"ok": False, "reason": "not_in_plan"}
        if self.market_buys_today >= MARKET_MAX_BUYS_PER_DAY:
            self.market_last_note = f"Ông Năm: Bữa nay ông chia tối đa {MARKET_MAX_BUYS_PER_DAY} phần thôi, mai cháu chịu khó lặn tiếp nghe!"
            return {"ok": False, "reason": "daily_limit"}
        if self.market_buys_by_kind.get(kind, 0) >= MARKET_MAX_BUY_PER_KIND:
            self.market_last_note = f"Ông Năm: Loại này ông chỉ nhường tối đa {MARKET_MAX_BUY_PER_KIND} phần mỗi ngày thôi cháu!"
            return {"ok": False, "reason": "kind_limit"}
        price = int(MARKET_SELL_PRICES.get(kind, 10) * 1.5)
        if self.carry_money < price:
            self.market_last_note = "Ông Năm: Chưa đủ tiền rồi cháu ơi, bán bớt đồ dư hoặc đợi tối bán hàng nha!"
            return {"ok": False, "reason": "funds"}
        self.carry_money -= price
        sim.money = self.carry_money
        self.market_buys_today += 1
        self.market_buys_by_kind[kind] = self.market_buys_by_kind.get(kind, 0) + 1
        if isinstance(sim.stock, list):
            new_id = sim.ids.new("I")
            sim.stock.append(make_item(new_id, kind, self.tuning.get("freshness", {}).get("initial", 100)))
            self.last_gather_inventory = {"items": [public_item(it) for it in sort_by_id(sim.stock)]}
        else:
            sim.stock[kind] = sim.stock.get(kind, 0) + 1
            self.last_gather_inventory = {"items": dict(sim.stock)}
        self.market_last_note = f"Ông Năm: Hàng tươi 100% ông mới kéo lưới lên (-{price}k), mang về nấu ngon nha cháu!"
        self._emit_live_event("vendor_trade", {"action": "buy", "kind": kind, "price": price, "money": self.carry_money}, phase="market")
        return {"ok": True, "action": "buy", "kind": kind, "price": price, "money": self.carry_money}

    def _buy_upgrade_locked(self, item_id: str) -> dict:
        if self.screen != "shop" or self.paused:
            return {"ok": False, "reason": "shop_closed"}
        catalog = self._shop_cfg["items"]
        if item_id not in catalog:
            self._emit_live_event("buy_failed", {"item": item_id, "reason": "unknown_item"}, phase="shop")
            return {"ok": False, "reason": "unknown_item"}
        spec = catalog[item_id]
        cur_lvl = self.pending_upgrades.get(item_id, self.active_upgrades.get(item_id, 0))
        if cur_lvl >= spec["max_level"]:
            self._emit_live_event("buy_failed", {"item": item_id, "reason": "max_level"}, phase="shop")
            return {"ok": False, "reason": "max_level"}
        cost = spec["costs"][min(cur_lvl, len(spec["costs"]) - 1)]
        if self.carry_money < cost:
            self._emit_live_event("buy_failed", {"item": item_id, "cost": cost, "money": self.carry_money, "reason": "insufficient_money"}, phase="shop")
            return {"ok": False, "reason": "insufficient_money"}
        self.carry_money -= cost
        self.session.sim.money = self.carry_money
        self.pending_upgrades[item_id] = cur_lvl + 1
        self.shop_last_note = f"Anh Ba: Xong liền! Đã nâng cấp {spec['label']} lên Lv.{cur_lvl + 1} — mai ra sông khỏe re luôn Út Sen!"
        self._emit_live_event("bought", {"item": item_id, "level": cur_lvl + 1, "cost": cost, "money": self.carry_money}, phase="shop")
        return {"ok": True, "item": item_id, "level": cur_lvl + 1, "cost": cost}

    def _close_shop_locked(self, reason: str = "shop_done"):
        if self.screen != "shop":
            return
        self._shop_open = False
        self.shop_ticks_left = 0
        self._emit_live_event("shop_end", {"day": self.day, "reason": reason, "upgrades": dict(self.pending_upgrades)}, phase="shop")
        # Nâng cấp áp dụng từ đầu Ngày kế tiếp
        self.active_upgrades = dict(self.pending_upgrades)
        self.day += 1
        self.session = self._build_day_gather_session(self.day)
        self.inputs = LiveInputs(buttons=LIVE_BUTTONS)
        self.screen = "day_intro"
        self.screen_ticks_left = DAY_INTRO_TICKS

    # --- API cho handler -----------------------------------------------------------
    def state_json(self) -> bytes:
        with self._lock:
            snap = self.session.snapshot()
            active_mode = snap.get("mode", self.session.mode)
            meta_key = active_mode if active_mode in self.tuning else ("gather" if "gather" in self.tuning else "quan")
            snap["meta"] = self.tuning[meta_key]
            snap["menu"] = self.tuning.get("menu", {})
            snap["full_menu"] = self._base_tuning.get("menu", {})
            snap["events"] = list(self.events)
            snap["finished"] = self.session.done if self.mode != "day" else (self.screen == "summary")
            snap["reason"] = (
                "days_complete" if (self.mode == "day" and self.screen == "summary")
                else (self.session.sim.reason if self.session.done else None)
            )
            snap["error"] = self.error
            snap["live_mode"] = self.mode
            snap["screen"] = self.screen
            snap["screen_ticks_left"] = self.screen_ticks_left
            snap["paused"] = self.paused
            snap["day"] = getattr(self.session.sim, "day", self.day)
            snap["days_total"] = self.days_total
            snap["days_completed"] = getattr(self.session.sim, "days_completed", self.days_completed)
            snap["day_plan"] = _day_plan_for(self._base_tuning, snap["day"])
            snap["active_upgrades"] = dict(getattr(self.session.sim, "active_upgrades", self.active_upgrades))
            snap["shop"] = {
                "open": self.screen == "shop",
                "ticks_left": self.shop_ticks_left,
                "ticks_max": self._shop_cfg["duration_ticks"],
                "active_upgrades": dict(self.active_upgrades),
                "pending_upgrades": dict(self.pending_upgrades),
                "catalog": self._shop_cfg["items"],
                "last_note": self.shop_last_note,
            }
            snap["market"] = self._market_state_locked()
            if active_mode == "gather" and self._underwater is not None:
                snap.update(self._underwater.snapshot())
            snap["last_gather_inventory"] = self.last_gather_inventory
            snap["last_gather_reason"] = self.last_gather_reason
            snap["last_day_summary"] = self.last_day_summary
            if self.mode == "day" and self.screen in ("shop", "market", "evening_intro"):
                if self.screen == "shop":
                    snap["phase"] = "shop"
                elif self.screen == "market":
                    snap["phase"] = "market"
                snap["money"] = self.carry_money
                snap["earned"] = self.carry_earned
                snap["reputation"] = self.carry_reputation
            return json.dumps(snap, ensure_ascii=False, separators=(",", ":")).encode("utf-8")

    def set_input(self, body: dict):
        move = body.get("move")
        if move is not None:
            ok = (isinstance(move, list) and len(move) == 2 and
                  all(isinstance(c, (int, float)) and not isinstance(c, bool) and abs(c) <= 1 for c in move))
            if not ok:
                raise ValueError("move phải là [a, b] trong [-1, 1]")
        buttons = {}
        for b in LIVE_BUTTONS:
            if b in body:
                if not isinstance(body[b], bool):
                    raise ValueError(f"{b} phải là boolean")
                buttons[b] = body[b]
        buy = body.get("buy")
        if buy is not None and not isinstance(buy, str):
            raise ValueError("buy phải là chuỗi hoặc null")
        with self._lock:
            if "pause" in buttons:
                if buttons["pause"] and not self._prev_pause_held and self.screen not in ("menu", "exited", "summary"):
                    self.paused = not self.paused
                    self._emit_live_event("pause" if self.paused else "resumed", {"screen": self.screen})
                self._prev_pause_held = buttons["pause"]
            if "shop_done" in buttons:
                if buttons["shop_done"] and not self._prev_shop_done_held and self.screen == "shop" and not self.paused:
                    self._close_shop_locked(reason="shop_done")
                self._prev_shop_done_held = buttons["shop_done"]
            if buy and self.screen == "shop" and not self.paused:
                self._buy_upgrade_locked(buy)
            self.inputs.set(move, **buttons)

    def perform_action(self, body: dict) -> dict:
        act = body.get("action")
        if not isinstance(act, str):
            raise ValueError("action phải là chuỗi")
        with self._lock:
            if act == "start":
                if self.screen in ("menu", "exited", "summary"):
                    self._start_at_menu = False
                    self._reset()
                    if self.mode == "day":
                        self.screen = "day_intro"
                        self.screen_ticks_left = DAY_INTRO_TICKS
                    else:
                        self.screen = "playing"
                return {"ok": True, "screen": self.screen}
            if act == "skip_intro":
                if self.screen in ("day_intro", "evening_intro") and not self.paused:
                    self._finish_intro_locked()
                return {"ok": True, "screen": self.screen}
            if act == "open_shop":
                if self.screen == "day_result":
                    self._open_shop_locked()
                return {"ok": True, "screen": self.screen}
            if act == "buy":
                item = body.get("item")
                if not isinstance(item, str):
                    raise ValueError("item phải là chuỗi")
                return self._buy_upgrade_locked(item)
            if act == "shop_done":
                if self.screen == "shop" and not self.paused:
                    self._close_shop_locked(reason="shop_done")
                return {"ok": True, "screen": self.screen}
            if act == "pause":
                if self.screen not in ("menu", "exited", "summary") and not self.paused:
                    self.paused = True
                    self._emit_live_event("pause", {"screen": self.screen})
                return {"ok": True, "paused": self.paused}
            if act == "resume":
                if self.paused:
                    self.paused = False
                    self._emit_live_event("resumed", {"screen": self.screen})
                return {"ok": True, "paused": self.paused}
            if act == "toggle_pause":
                if self.screen not in ("menu", "exited", "summary"):
                    self.paused = not self.paused
                    self._emit_live_event("pause" if self.paused else "resumed", {"screen": self.screen})
                return {"ok": True, "paused": self.paused}
            if act == "close_quan":
                if (self.screen == "playing" and not self.paused
                        and getattr(self.session.sim, "mode", None) == "quan" and not self.session.done):
                    self.session.sim.time_left_ticks = 1
                    self._tick_once()
                    return {"ok": True, "screen": self.screen}
                return {"ok": False, "screen": self.screen}
            if act == "drop_hold_item":
                sim = self.session.sim
                if getattr(sim, "mode", None) != "gather" or self.session.done:
                    return {"ok": False, "reason": "wrong_phase"}
                item_id = body.get("item_id")
                idx = body.get("index")
                if isinstance(item_id, str):
                    pos = next((i for i, it in enumerate(sim.hold) if isinstance(it, dict) and it.get("id") == item_id), None)
                    if pos is None:
                        return {"ok": False, "reason": "not_found"}
                    removed = sim.hold.pop(pos)
                    self._emit_live_event("item_dropped", {"item_id": item_id, "kind": removed["kind"]}, phase="gather")
                    return {"ok": True, "hold_count": len(sim.hold)}
                if isinstance(idx, int) and not isinstance(idx, bool) and 0 <= idx < len(sim.hold):
                    removed = sim.hold.pop(idx)
                    kind = removed["kind"] if isinstance(removed, dict) else removed
                    self._emit_live_event("item_dropped", {"index": idx, "kind": kind}, phase="gather")
                    return {"ok": True, "hold_count": len(sim.hold)}
                return {"ok": False, "reason": "not_found"}
            if act == "open_market":
                if self.mode == "day" and self.screen == "evening_intro" and not self.paused:
                    self.screen = "market"
                    self.market_last_note = ""
                    self._emit_live_event("phase_start", {"day": self.day, "phase": "market"}, phase="market")
                    return {"ok": True, "screen": self.screen}
                return {"ok": False, "screen": self.screen}
            if act == "market_sell":
                kind = body.get("kind")
                if not isinstance(kind, str):
                    raise ValueError("kind phải là chuỗi")
                return self._market_sell_locked(kind)
            if act == "market_buy":
                kind = body.get("kind")
                if not isinstance(kind, str):
                    raise ValueError("kind phải là chuỗi")
                return self._market_buy_locked(kind)
            if act == "close_market":
                if self.screen == "market" and not self.paused:
                    self.screen = "playing"
                    self.screen_ticks_left = 0
                    self._emit_live_event("phase_start", {"day": self.day, "phase": "quan"}, phase="quan")
                    return {"ok": True, "screen": self.screen}
                return {"ok": False, "screen": self.screen}
            if act == "menu":
                self.paused = False
                self.screen = "menu"
                return {"ok": True, "screen": self.screen}
            if act == "exit":
                self.paused = False
                self.screen = "exited"
                return {"ok": True, "screen": self.screen}
            raise ValueError(f"action không hỗ trợ: {act}")

    def restart(self):
        with self._lock:
            self._start_at_menu = False
            self._reset()


class _Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    game: LiveGame = None  # gán trên lớp con trong LiveServer

    def log_message(self, fmt, *args):  # yên lặng
        pass

    def _send(self, code, body: bytes, ctype="application/json; charset=utf-8"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path == "/state":
            self._send(200, self.game.state_json())
        elif path in ("/", "/index.html"):
            try:
                with open(os.path.join(WEB_DIR, "index.html"), "rb") as f:
                    self._send(200, f.read(), "text/html; charset=utf-8")
            except OSError:
                self._send(404, b'{"error":"thieu index.html"}')
        elif path in ("/assets/cho-noi-sprites.png", "/assets/ut-sen-swim.png", "/assets/customers-sheet.png",
                      "/assets/ut-sen-walk.png", "/assets/portraits-sheet.png",
                      "/assets/thuy-quai.png", "/assets/song-nuoc.png"):
            try:
                with open(os.path.join(WEB_DIR, path.lstrip("/")), "rb") as f:
                    self._send(200, f.read(), "image/png")
            except OSError:
                self._send(404, b'{"error":"khong co sprite"}')
        elif path == "/assets/title-bg.jpg":
            try:
                with open(os.path.join(WEB_DIR, "assets", "title-bg.jpg"), "rb") as f:
                    self._send(200, f.read(), "image/jpeg")
            except OSError:
                self._send(404, b'{"error":"khong co title bg"}')
        else:
            self._send(404, b'{"error":"khong co"}')

    def do_POST(self):
        path = self.path.split("?", 1)[0]
        try:
            n = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            n = -1
        if n < 0 or n > MAX_BODY:
            self._send(400, b'{"error":"body sai"}')
            return
        raw = self.rfile.read(n) if n else b""
        try:
            if path == "/input":
                body = json.loads(raw.decode("utf-8") or "{}")
                if not isinstance(body, dict):
                    raise ValueError("body phải là object")
                self.game.set_input(body)
                self._send(200, b'{"ok":true}')
            elif path == "/action":
                body = json.loads(raw.decode("utf-8") or "{}")
                if not isinstance(body, dict):
                    raise ValueError("body phải là object")
                res = self.game.perform_action(body)
                self._send(200, json.dumps(res, ensure_ascii=False).encode("utf-8"))
            elif path == "/restart":
                self.game.restart()
                self._send(200, b'{"ok":true}')
            else:
                self._send(404, b'{"error":"khong co"}')
        except (ValueError, UnicodeDecodeError) as e:
            self._send(400, json.dumps({"error": str(e)}).encode("utf-8"))


class LiveServer:
    """Máy chủ + mô phỏng. port=0 -> cổng ngẫu nhiên (đọc `.port`)."""

    def __init__(self, game: LiveGame, host="127.0.0.1", port=8000):
        handler = type("Handler", (_Handler,), {"game": game})
        self.game = game
        self.httpd = ThreadingHTTPServer((host, port), handler)
        self.httpd.daemon_threads = True
        self.host = host
        self.port = self.httpd.server_address[1]
        self._thread = None

    @property
    def url(self):
        return f"http://{self.host}:{self.port}/"

    def start(self):
        self.game.start()
        self._thread = threading.Thread(target=self.httpd.serve_forever, name="chonoi-http", daemon=True)
        self._thread.start()

    def stop(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        if self._thread:
            self._thread.join(timeout=2)
        self.game.stop()


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="chonoi.live", description="Chơi trực tiếp trên trình duyệt (Phase 2).")
    p.add_argument("--mode", required=True, choices=["gather", "quan", "day"])
    p.add_argument("--days", type=int, default=5, help="chỉ với --mode day: số ngày (1..5)")
    p.add_argument("--seed", type=int, default=1)
    p.add_argument("--port", type=int, default=8000, help="0 = cổng ngẫu nhiên")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--scenario")
    p.add_argument("--extra-content", action="store_true", help="bật nguyên liệu và món ăn mở rộng")
    p.add_argument("--inventory", help="chỉ với quan: nạp kho từ file")
    p.add_argument("--inventory-out", dest="inventory_out", help="chỉ với gather: ghi kho khi kết thúc buổi")
    a = p.parse_args(argv)
    try:
        if not (1 <= a.days <= 5):
            raise BadInput("--days phải nằm trong [1, 5]")
        if a.inventory and a.mode != "quan":
            raise BadInput("--inventory chỉ dùng với quan")
        if a.inventory_out and a.mode != "gather":
            raise BadInput("--inventory-out chỉ dùng với gather")
        contract = load_contract()
        version = contract.get("contract_version")
        tuning = contract["tuning"]
        inventory_kinds = KINDS_P2
        if a.extra_content:
            with open(EXTRA_CONTENT_PATH, encoding="utf-8") as content_file:
                extra = json.load(content_file)
            gather = tuning["gather"]
            extra_gather = extra["gather"]
            existing_node_ids = {n["id"] for n in gather["nodes"]}
            for node in extra_gather["nodes"]:
                if node["id"] not in existing_node_ids:
                    gather["nodes"].append(node)
                    existing_node_ids.add(node["id"])
            if isinstance(gather["fish_initial"], list):
                gather["fish_initial"].extend(extra_gather["fish_initial"])
            else:
                for kind in extra_gather["fish_yield"]:
                    gather.setdefault("fish_depths", {}).setdefault(kind, [6, 18])
                    gather.setdefault("fish_spawn_depths", {}).setdefault(kind, [10, 16])
                    gather.setdefault("fish_weights", {}).setdefault(kind, 0.15)
            gather["fish_yield"].update(extra_gather["fish_yield"])
            tuning["menu"].update(extra["menu"])
            inventory_kinds = tuple(dict.fromkeys(
                inventory_kinds
                + tuple(extra_gather["fish_yield"])
                + tuple(node["kind"] for node in extra_gather["nodes"])
            ))
        scenario = load_scenario(a.scenario, a.mode, tuning) if a.scenario else {}
        inventory = read_inventory(a.inventory, inventory_kinds, version=version) if a.inventory else None
        if inventory is not None and "stock" in scenario:
            raise BadInput("vừa có quan.stock vừa có --inventory")
        game = LiveGame(a.mode, tuning, scenario, a.seed, inventory, a.inventory_out, days=a.days)
        server = LiveServer(game, a.host, a.port)
    except BadInput as e:
        sys.stderr.write(f"đầu vào sai: {e}\n")
        return 2
    except OSError as e:
        sys.stderr.write(f"không mở được cổng {a.port}: {e}\n")
        return 1
    server.start()
    print(f"Mở trình duyệt tại {server.url}  (chế độ {a.mode}, seed {a.seed}). Ctrl+C để dừng.", flush=True)
    try:
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        server.stop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
