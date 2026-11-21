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
import os
import sys
import threading
import time
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .contract import load_contract
from .errors import BadInput
from .freshness import is_v12
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
SHOP_DEFAULT_TICKS = 600   # 10 giây (hoặc shop_done)

LIVE_BUTTONS = ("interact", "catch", "pause", "shop_done", "attack", "photo")


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
        self.active_upgrades = {"oxygen": 0, "hp": 0}
        self.pending_upgrades = {"oxygen": 0, "hp": 0}
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
        oxy_bonus = self._shop_cfg["items"]["oxygen"]["bonus"]
        hp_bonus = self._shop_cfg["items"]["hp"]["bonus"]
        t["gather"]["oxygen_max_s"] = t["gather"]["oxygen_max_s"] + oxy_lvl * oxy_bonus
        t["gather"]["hp_max"] = int(t["gather"]["hp_max"] + hp_lvl * hp_bonus)
        return t

    def _build_day_gather_session(self, day: int) -> Session:
        day_tuning = self._tuned_for_day(day)
        self.tuning = day_tuning
        sess = Session("gather", day_tuning, {}, self._seed + day * 101)
        sess.sim.day = day
        sess.sim.money = self.carry_money
        sess.sim.earned = self.carry_earned
        sess.sim.reputation = self.carry_reputation
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
        if self.screen in ("menu", "exited", "summary", "day_result"):
            return
        if self.paused:
            self._outer_tick += 1
            return

        # Intro screens (4s / 3.5s) — dừng khi pause
        if self.screen in ("day_intro", "evening_intro"):
            self._outer_tick += 1
            if self.screen_ticks_left > 0:
                self.screen_ticks_left -= 1
            if self.screen_ticks_left <= 0:
                self._finish_intro_locked()
            return

        # Live Shop countdown (dừng khi pause!)
        if self.screen == "shop" and not self._native_day:
            self._outer_tick += 1
            if self.shop_ticks_left > 0:
                self.shop_ticks_left -= 1
            if self.shop_ticks_left <= 0:
                self._close_shop_locked(reason="time")
            return

        s = self.session
        if s.done:
            return
        self._outer_tick += 1
        for row in s.step(self.inputs.advance()):
            self.events.append(row)
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
        self._emit_live_event("phase_start", {"day": self.day, "phase": "shop"}, phase="shop")

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
            }
            snap["last_gather_inventory"] = self.last_gather_inventory
            snap["last_gather_reason"] = self.last_gather_reason
            snap["last_day_summary"] = self.last_day_summary
            if self.mode == "day" and self.screen == "shop":
                snap["phase"] = "shop"
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
        elif path in ("/assets/cho-noi-sprites.png", "/assets/ut-sen-swim.png"):
            try:
                with open(os.path.join(WEB_DIR, path.lstrip("/")), "rb") as f:
                    self._send(200, f.read(), "image/png")
            except OSError:
                self._send(404, b'{"error":"khong co sprite"}')
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
