"""Soak headless nhiều Ngày bằng bot tất định (TICKET-04, Contract v1.3).

Cách chạy chuẩn:
    python3 -m chonoi.soak --seed 7 --days 10 --out soak.json

Mỗi Ngày đi qua gather -> quan -> shop; kế hoạch D1-D5 lặp cho Ngày 6-10; tiền, tổng thu,
uy tín, cấp nâng cấp, số Ngày và id cá thể tiếp tục xuyên suốt trong một tiến trình.
"""

import argparse
import json
import math
import os
import sys
import tempfile
import time

from .contract import load_contract
from .errors import BadInput
from .ids import IdAllocator, sort_by_id
from .inputs import InputState
from .rng import Streams
from .sim.day import DaySim


def _dir_to(src, dst):
    dx = dst[0] - src[0]
    dy = dst[1] - src[1]
    dist = math.hypot(dx, dy)
    if dist <= 1e-6:
        return (0.0, 0.0), 0.0
    return (dx / dist, dy / dist), dist


def _bot_gather_input(sim) -> InputState:
    """Bot sáng tất định: hái tối đa 4 nguyên liệu gần nhất trên mặt nước rồi về bến cập bến."""
    g = sim.current
    pos = g.pos
    dock = g.t["dock_pos"]
    dock_r = g.t["dock_radius"]
    inter_r = g.t["interact_radius"]

    # Khi đã có >= 4 món hoặc còn <= 3600 tick -> bơi về bến cập bến
    need_dock = len(g.hold) >= 4 or g.time_left_ticks <= 3600
    if not need_dock:
        ready_nodes = [n for n in sort_by_id(g.nodes) if n["regrow_ticks"] == 0]
        if ready_nodes:
            target = min(ready_nodes, key=lambda n: (math.dist(pos, n["pos"]), n["id"]))
            mv, dist = _dir_to(pos, target["pos"])
            if dist <= inter_r - 0.1 and pos[1] <= g.t["surface_depth"]:
                return InputState((0.0, 0.0), {"interact": True}, {"interact"})
            return InputState(mv, {}, set())

    mv, dist = _dir_to(pos, dock)
    if dist <= dock_r - 0.1:
        return InputState((0.0, 0.0), {"interact": True}, {"interact"})
    return InputState(mv, {}, set())


def _bot_quan_input(sim) -> InputState:
    """Bot tối tất định: giao món đang cầm, bưng món chín, hoặc nấu đơn reserved trên bếp rảnh."""
    q = sim.current
    pos = q.pos
    inter_r = q.t["interact_radius"]

    # 1. Đang cầm món -> đi tới bàn của đúng đơn hàng và giao
    if q.hand is not None:
        cust = next((c for c in q.customers if c["id"] == q.hand["order_id"]), None)
        if cust is not None:
            table = next((tb for tb in q.tables if tb["id"] == cust["table_id"]), None)
            if table is not None:
                mv, dist = _dir_to(pos, table["pos"])
                if dist <= inter_r - 0.1:
                    return InputState((0.0, 0.0), {"interact": True}, {"interact"})
                return InputState(mv, {}, set())

    # 2. Tay trống & có bếp ready -> đi tới bếp đó để bưng
    if q.hand is None:
        ready_stoves = [s for s in sort_by_id(q.stoves) if s["state"] == "ready"]
        if ready_stoves:
            st = min(ready_stoves, key=lambda s: math.dist(pos, s["pos"]))
            mv, dist = _dir_to(pos, st["pos"])
            if dist <= inter_r - 0.1:
                return InputState((0.0, 0.0), {"interact": True}, {"interact"})
            return InputState(mv, {}, set())

    # 3. Có đơn reserved & có bếp idle -> đi tới bếp rảnh để nấu
    has_reserved = any(c["state"] == "waiting" and c["order_status"] == "reserved" for c in q.customers)
    if has_reserved:
        idle_stoves = [s for s in sort_by_id(q.stoves) if s["state"] == "idle"]
        if idle_stoves:
            st = min(idle_stoves, key=lambda s: math.dist(pos, s["pos"]))
            mv, dist = _dir_to(pos, st["pos"])
            if dist <= inter_r - 0.1:
                return InputState((0.0, 0.0), {"interact": True}, {"interact"})
            return InputState(mv, {}, set())

    return InputState((0.0, 0.0), {}, set())


def _bot_shop_input(sim) -> InputState:
    """Bot Shop tất định: mua nâng cấp đầu tiên đủ tiền (oxygen -> hp), sau đó đóng Shop."""
    upgrades = sim.tuning["shop"]["upgrades"]
    for key in ("oxygen", "hp"):
        lvl = sim.upgrades.get(key, 0)
        tiers = upgrades.get(key, [])
        if lvl < len(tiers) and sim.money >= tiers[lvl]["price"]:
            return InputState((0.0, 0.0), {}, set(), buy=key)
    return InputState((0.0, 0.0), {"shop_done": True}, {"shop_done"})


def run_soak(seed: int, days: int) -> dict:
    t0 = time.perf_counter()
    contract = load_contract()
    tuning = contract["tuning"]
    mult = tuning["score"]["reputation_multiplier"]
    sim = DaySim(tuning, {}, Streams(seed), IdAllocator(), days=days, allow_extended_days=True)

    results = []
    crashes = 0
    max_ticks = days * 23_000
    ticks = 0

    try:
        while not sim.done and ticks < max_ticks:
            ticks += 1
            if sim.phase == "gather":
                inp = _bot_gather_input(sim)
            elif sim.phase == "quan":
                inp = _bot_quan_input(sim)
            else:
                inp = _bot_shop_input(sim)
            evs = sim.step(inp)
            for ev in evs:
                if ev["name"] == "shop_end":
                    results.append({
                        "day": ev["day"],
                        "earned": sim.earned,
                        "reputation": round(sim.reputation, 3),
                        "score": sim.earned + mult * math.floor(sim.reputation),
                    })
    except Exception:
        crashes += 1

    duration_s = round(time.perf_counter() - t0, 3)
    return {
        "days": days,
        "days_completed": sim.days_completed,
        "crashes": crashes,
        "results": results,
        "duration_s": duration_s,
    }


def _write_json_atomic(path: str, payload: dict):
    parent = os.path.dirname(os.path.abspath(path))
    os.makedirs(parent, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".soak-", suffix=".tmp", dir=parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))
            f.write("\n")
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="chonoi.soak", description="Soak headless nhiều Ngày (Contract v1.3).")
    p.add_argument("--seed", required=True, type=int)
    p.add_argument("--days", required=True, type=int)
    p.add_argument("--out", required=True)
    a = p.parse_args(argv)
    try:
        if a.days < 1:
            raise BadInput("--days phải >= 1")
        payload = run_soak(a.seed, a.days)
        _write_json_atomic(a.out, payload)
    except BadInput as e:
        sys.stderr.write(f"đầu vào sai: {e}\n")
        return 2
    except OSError as e:
        sys.stderr.write(f"lỗi ghi: {e}\n")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
