"""Test luật buổi sáng (`gather`) — Lát 1 & Lát 2 (PRD-0) + Cá bơi/sinh (Phase 2 v1.1)."""

import copy
import json
import math
import unittest

from chonoi.inputs import InputState
from chonoi.runner import Session
from helpers import Workdir, close, events, frames, read_jsonl, run_headless, snapshots, write_json


def _load_tuning():
    with open("game.contract.json", encoding="utf-8") as f:
        return json.load(f)["tuning"]


def _tuning_gather():
    return _load_tuning()["gather"]


def _v11_tuning():
    tuning = copy.deepcopy(_load_tuning())
    g = tuning["gather"]
    g["fish_initial"] = 8
    g["fish_speed"] = 1.5
    g["fish_turn_ticks"] = 120
    g["fish_max"] = 12
    g["fish_spawn_ticks"] = 360
    g["fish_spawn_clearance"] = 1.0
    g["fish_x"] = [4, 96]
    g["fish_depths"] = {"ca_linh": [3, 12], "ca_loc": [8, 20], "ca_keo": [22, 28]}
    g["fish_spawn_x"] = [15, 30, 45, 60, 75, 90]
    g["fish_spawn_depths"] = {"ca_linh": [5, 10], "ca_loc": [10, 16], "ca_keo": [24, 27]}
    g["fish_weights"] = {"ca_linh": 0.4, "ca_loc": 0.3, "ca_keo": 0.3}
    g["fish_yield"] = {"ca_linh": 3, "ca_loc": 1, "ca_keo": 2}
    g["nodes"] = [
        {"id": "N1", "kind": "bong_dien_dien", "pos": [12, 0]},
        {"id": "N2", "kind": "bong_dien_dien", "pos": [28, 0]},
        {"id": "N3", "kind": "bong_sung", "pos": [44, 0]},
        {"id": "N4", "kind": "bong_sung", "pos": [60, 0]},
        {"id": "N5", "kind": "keo_neo", "pos": [76, 0]},
        {"id": "N6", "kind": "keo_neo", "pos": [90, 0]},
    ]
    return tuning


class GatherSlice1Test(unittest.TestCase):
    def test_dive_and_surface_events(self):
        with Workdir() as w:
            sc = write_json(w.path("sc.json"), {"gather": {"player": {"pos": [20, 0]}}})
            inp = write_json(w.path("in.json"), frames(
                {"tick": 0, "move": [0, 1]},
                {"tick": 30, "move": [0, -1]},
            ))
            code, err = run_headless("--mode", "gather", "--seed", "1", "--ticks", "80",
                                     "--scenario", sc, "--inputs", inp, "--snapshot-every", "1",
                                     "--out", w.path("o.jsonl"))
            self.assertEqual(code, 0, err)
            rows = read_jsonl(w.path("o.jsonl"))
            dives = events(rows, "dive")
            surfaces = events(rows, "surface")
            self.assertEqual(len(dives), 1)
            self.assertEqual(len(surfaces), 1)
            self.assertGreater(dives[0]["data"]["pos"][1], _tuning_gather()["surface_depth"])
            self.assertLessEqual(surfaces[0]["data"]["pos"][1], _tuning_gather()["surface_depth"])
            self.assertLess(dives[0]["tick"], surfaces[0]["tick"])

    def test_oxygen_drain_and_refill_clamped(self):
        g = _tuning_gather()
        omax = int(round(g["oxygen_max_s"] * 60))
        refill = int(g["oxygen_refill_per_tick"])
        with Workdir() as w:
            sc = write_json(w.path("sc.json"), {"gather": {"player": {"pos": [20, 5], "oxygen_ticks": 100}}})
            code, err = run_headless("--mode", "gather", "--seed", "1", "--ticks", "10",
                                     "--scenario", sc, "--snapshot-every", "1", "--out", w.path("drain.jsonl"))
            self.assertEqual(code, 0, err)
            snaps = snapshots(read_jsonl(w.path("drain.jsonl")))
            self.assertEqual(snaps[-1]["player"]["oxygen_ticks"], 90)

            sc2 = write_json(w.path("sc2.json"), {"gather": {"player": {"pos": [20, 0], "oxygen_ticks": omax - 10}}})
            code, err = run_headless("--mode", "gather", "--seed", "1", "--ticks", "5",
                                     "--scenario", sc2, "--snapshot-every", "1", "--out", w.path("refill.jsonl"))
            self.assertEqual(code, 0, err)
            snaps2 = {r["tick"]: r for r in snapshots(read_jsonl(w.path("refill.jsonl")))}
            self.assertEqual(snaps2[1]["player"]["oxygen_ticks"], min(omax, omax - 10 + refill))
            self.assertEqual(snaps2[5]["player"]["oxygen_ticks"], omax)

    def test_oxygen_empty_choke_counts_zero_tick_and_surface_resets(self):
        g = _tuning_gather()
        choke_iv = int(g["choke_interval_ticks"])
        with Workdir() as w:
            # Oxy chạm 0 ở tick 2 -> zero_oxy_ticks tăng ngay ở tick 2 -> choke đầu ở tick 2 + 59
            sc = write_json(w.path("sc.json"), {"gather": {
                "player": {"pos": [20, 5], "oxygen_ticks": 2, "hp": 3, "invuln_ticks": 90},
            }})
            code, err = run_headless("--mode", "gather", "--seed", "1", "--ticks", str(2 + choke_iv + 2),
                                     "--scenario", sc, "--snapshot-every", "1", "--out", w.path("o.jsonl"))
            self.assertEqual(code, 0, err)
            rows = read_jsonl(w.path("o.jsonl"))
            empties = events(rows, "oxygen_empty")
            chokes = events(rows, "choke")
            self.assertEqual(len(empties), 1)
            self.assertEqual(empties[0]["tick"], 2)
            self.assertEqual(empties[0]["data"], {"oxygen_ticks": 0})
            self.assertEqual(len(chokes), 1)
            self.assertEqual(chokes[0]["tick"], 2 + choke_iv - 1)
            self.assertEqual(chokes[0]["data"], {"hp": 2})

            # Lên mặt nước reset zero_oxy_ticks ngay cả đúng tick đáng lẽ ngạt
            sc2 = write_json(w.path("sc2.json"), {"gather": {
                "player": {"pos": [20, 0.52], "vel": [0, -4.0], "oxygen_ticks": 0, "zero_oxy_ticks": 59, "hp": 3},
            }})
            inp = write_json(w.path("in.json"), frames({"tick": 0, "move": [0, -1]}))
            code, err = run_headless("--mode", "gather", "--seed", "1", "--ticks", "5",
                                     "--scenario", sc2, "--inputs", inp, "--out", w.path("o2.jsonl"))
            self.assertEqual(code, 0, err)
            rows2 = read_jsonl(w.path("o2.jsonl"))
            self.assertEqual(events(rows2, "choke"), [])
            last_p = snapshots(rows2)[-1]["player"]
            self.assertEqual(last_p["zero_oxy_ticks"], 0)
            self.assertGreater(last_p["oxygen_ticks"], 0)

    def test_faint_clears_hold_lifo_and_writes_empty_inventory(self):
        with Workdir() as w:
            sc = write_json(w.path("sc.json"), {"gather": {
                "player": {"pos": [20, 5], "oxygen_ticks": 0, "zero_oxy_ticks": 59, "hp": 1},
                "hold": ["ca_loc", "bong_sung"],
                "time_left_ticks": 1,
            }})
            inv = w.path("inv.json")
            code, err = run_headless("--mode", "gather", "--seed", "1", "--ticks", "10",
                                     "--scenario", sc, "--inventory-out", inv, "--out", w.path("o.jsonl"))
            self.assertEqual(code, 0, err)
            rows = read_jsonl(w.path("o.jsonl"))
            names = [e["name"] for e in events(rows)]
            self.assertEqual(names, ["choke", "faint", "gather_end"])
            faint_ev = events(rows, "faint")[0]
            self.assertEqual(faint_ev["data"], {"cause": "choke", "lost": ["bong_sung", "ca_loc"], "hp": 0})
            end_ev = events(rows, "gather_end")[0]
            self.assertEqual(end_ev["data"]["reason"], "fainted")
            self.assertEqual(end_ev["data"]["inventory"], {"items": {}})
            self.assertEqual(rows[-1]["reason"], "fainted")
            self.assertEqual(snapshots(rows)[-1]["hold"], [])
            with open(inv, encoding="utf-8") as f:
                self.assertEqual(json.load(f), {"items": {}})


class GatherSlice2Test(unittest.TestCase):
    def test_gather_node_tiebreak_regrow_and_surface_only(self):
        g = _tuning_gather()
        regrow_ticks = int(round(g["regrow_s"] * 60))
        with Workdir() as w:
            sc = write_json(w.path("sc.json"), {"gather": {
                "player": {"pos": [20, 0]},
                "nodes": [
                    {"id": "N10", "kind": "bong_sung", "pos": [21, 0]},
                    {"id": "N2", "kind": "bong_dien_dien", "pos": [19, 0]},
                ],
                "random_fish": False,
            }})
            inp = write_json(w.path("in.json"), frames({"tick": 0, "interact": True}))
            code, err = run_headless("--mode", "gather", "--seed", "1", "--ticks", str(regrow_ticks + 2),
                                     "--scenario", sc, "--inputs", inp, "--out", w.path("o.jsonl"))
            self.assertEqual(code, 0, err)
            rows = read_jsonl(w.path("o.jsonl"))
            ge = events(rows, "gather")
            self.assertEqual(len(ge), 1)
            self.assertEqual(ge[0]["data"], {"node_id": "N2", "kind": "bong_dien_dien", "amount": 1})
            self.assertEqual(snapshots(rows)[-1]["hold"], ["bong_dien_dien"])
            regrown = events(rows, "node_regrown")
            self.assertEqual(len(regrown), 1)
            self.assertEqual(regrown[0]["data"]["node_id"], "N2")
            self.assertEqual(regrown[0]["tick"], 1 + regrow_ticks)

            sc_under = write_json(w.path("sc_under.json"), {"gather": {
                "player": {"pos": [12, 1.0]},
                "nodes": [{"id": "N1", "kind": "bong_dien_dien", "pos": [12, 0]}],
                "random_fish": False,
            }})
            code, err = run_headless("--mode", "gather", "--seed", "1", "--ticks", "2",
                                     "--scenario", sc_under, "--inputs", inp, "--out", w.path("u.jsonl"))
            self.assertEqual(code, 0, err)
            self.assertEqual(events(read_jsonl(w.path("u.jsonl")), "gather"), [])

    def test_gather_node_hold_full_keeps_node_ready(self):
        cap = int(_tuning_gather()["hold_capacity"])
        with Workdir() as w:
            sc = write_json(w.path("sc.json"), {"gather": {
                "player": {"pos": [12, 0]},
                "hold": ["ca_loc"] * cap,
                "nodes": [{"id": "N1", "kind": "bong_dien_dien", "pos": [12, 0]}],
                "random_fish": False,
            }})
            inp = write_json(w.path("in.json"), frames({"tick": 0, "interact": True}))
            code, err = run_headless("--mode", "gather", "--seed", "1", "--ticks", "2",
                                     "--scenario", sc, "--inputs", inp, "--out", w.path("o.jsonl"))
            self.assertEqual(code, 0, err)
            rows = read_jsonl(w.path("o.jsonl"))
            self.assertEqual(events(rows, "gather"), [])
            hf = events(rows, "hold_full")
            self.assertEqual(len(hf), 1)
            self.assertEqual(hf[0]["data"], {"action": "gather", "node_id": "N1", "required": 1, "free": 0})
            self.assertTrue(snapshots(rows)[-1]["nodes"][0]["ready"])

    def test_dock_has_priority_over_gather(self):
        with Workdir() as w:
            sc = write_json(w.path("sc.json"), {"gather": {
                "player": {"pos": [2, 0]},
                "nodes": [{"id": "N1", "kind": "bong_dien_dien", "pos": [2, 0]}],
                "random_fish": False,
            }})
            inp = write_json(w.path("in.json"), frames({"tick": 0, "interact": True}))
            code, err = run_headless("--mode", "gather", "--seed", "1", "--ticks", "5",
                                     "--scenario", sc, "--inputs", inp, "--out", w.path("o.jsonl"))
            self.assertEqual(code, 0, err)
            rows = read_jsonl(w.path("o.jsonl"))
            self.assertEqual(events(rows, "gather"), [])
            self.assertEqual(events(rows, "gather_end")[0]["data"]["reason"], "docked")

    def test_catch_fish_requires_full_yield_and_cooldown_only_on_success(self):
        g = _tuning_gather()
        cap = int(g["hold_capacity"])
        cd = int(round(g["catch_cooldown_s"] * 60))
        with Workdir() as w:
            sc = write_json(w.path("sc.json"), {"gather": {
                "player": {"pos": [15, 5]},
                "fish": [
                    {"id": "F1", "kind": "ca_linh", "pos": [15, 5]},
                    {"id": "F2", "kind": "ca_loc", "pos": [15.5, 5]},
                ],
                "random_fish": False,
            }})
            inp = write_json(w.path("in.json"), frames(
                {"tick": 0, "catch": True},
                {"tick": 1, "catch": False},
                {"tick": 5, "catch": True},
                {"tick": 6, "catch": False},
                {"tick": cd, "catch": True},
            ))
            code, err = run_headless("--mode", "gather", "--seed", "1", "--ticks", str(cd + 2),
                                     "--scenario", sc, "--inputs", inp, "--snapshot-every", "1",
                                     "--out", w.path("o.jsonl"))
            self.assertEqual(code, 0, err)
            rows = read_jsonl(w.path("o.jsonl"))
            caught = events(rows, "fish_caught")
            self.assertEqual(len(caught), 2)
            self.assertEqual(caught[0]["data"], {"fish_id": "F1", "kind": "ca_linh", "yield": 3})
            self.assertEqual(caught[1]["data"], {"fish_id": "F2", "kind": "ca_loc", "yield": 1})
            self.assertEqual(snapshots(rows)[-1]["hold"], ["ca_linh", "ca_linh", "ca_linh", "ca_loc"])
            self.assertEqual(snapshots(rows)[-1]["fish"], [])

            sc_surf = write_json(w.path("sc_surf.json"), {"gather": {
                "player": {"pos": [15, 0.5]},
                "fish": [{"id": "F1", "kind": "ca_loc", "pos": [15, 1.0]}],
            }})
            inp_once = write_json(w.path("in1.json"), frames({"tick": 0, "catch": True}))
            code, err = run_headless("--mode", "gather", "--seed", "1", "--ticks", "2",
                                     "--scenario", sc_surf, "--inputs", inp_once, "--out", w.path("s.jsonl"))
            self.assertEqual(code, 0, err)
            self.assertEqual(events(read_jsonl(w.path("s.jsonl")), "fish_caught"), [])

            # Giỏ còn 2 chỗ, bắt ca_linh (yield=3) -> phải đủ chỗ cho cả đàn: hold_full, giữ cá, không cooldown
            sc_part = write_json(w.path("sc_part.json"), {"gather": {
                "player": {"pos": [15, 5]},
                "hold": ["ca_loc"] * (cap - 2),
                "fish": [
                    {"id": "F1", "kind": "ca_linh", "pos": [15, 5]},
                    {"id": "F2", "kind": "ca_loc", "pos": [15.5, 5]},
                ],
                "random_fish": False,
            }})
            inp_once = write_json(w.path("in1.json"), frames({"tick": 0, "catch": True}))
            code, err = run_headless("--mode", "gather", "--seed", "1", "--ticks", "2",
                                     "--scenario", sc_part, "--inputs", inp_once, "--out", w.path("p.jsonl"))
            self.assertEqual(code, 0, err)
            rows_p = read_jsonl(w.path("p.jsonl"))
            self.assertEqual(events(rows_p, "fish_caught"), [])
            hf = events(rows_p, "hold_full")
            self.assertEqual(len(hf), 1)
            self.assertEqual(hf[0]["data"], {"action": "catch", "fish_id": "F1", "required": 3, "free": 2})
            last_snap = snapshots(rows_p)[-1]
            self.assertEqual(last_snap["hold"], ["ca_loc"] * (cap - 2))
            self.assertEqual(len(last_snap["fish"]), 2)
            self.assertEqual(last_snap["player"]["catch_cd_ticks"], 0)


class GatherPhase2FishTest(unittest.TestCase):
    def _idle(self):
        return InputState((0.0, 0.0), {"interact": False, "catch": False}, set())

    def test_v11_initial_8_schools_distinct_points_and_deterministic(self):
        tuning = _v11_tuning()
        s1 = Session("gather", tuning, {}, 42)
        s2 = Session("gather", tuning, {}, 42)
        f1 = s1.snapshot()["fish"]
        f2 = s2.snapshot()["fish"]
        self.assertEqual(len(f1), 8)
        self.assertEqual(f1, f2)
        pts = {tuple(f["pos"]) for f in f1}
        self.assertEqual(len(pts), 8)
        self.assertTrue(all(f["kind"] in ("ca_linh", "ca_loc", "ca_keo") for f in f1))

    def test_v11_fish_swim_speed_reflection_corner_and_turn_at_120(self):
        tuning = _v11_tuning()
        # 1) Bơi ngang đúng 1.5 m/s trong 60 tick
        sc = {"fish": [{"id": "F1", "kind": "ca_linh", "pos": [20, 6], "heading_deg": 0}], "random_fish": True}
        s = Session("gather", tuning, sc, 7)
        for _ in range(60):
            s.step(self._idle())
        pos = s.snapshot()["fish"][0]["pos"]
        self.assertTrue(close(pos[0], 21.5, 0.01), pos)
        self.assertTrue(close(pos[1], 6.0, 0.01), pos)

        # 2) Phản xạ mép phải x=96 và đảo thành phần x
        sc_edge = {"fish": [{"id": "F1", "kind": "ca_linh", "pos": [95.99, 6], "heading_deg": 0}], "random_fish": True}
        s_edge = Session("gather", tuning, sc_edge, 7)
        s_edge.step(self._idle())
        f = s_edge.snapshot()["fish"][0]
        self.assertTrue(close(f["pos"][0], 95.985, 1e-4), f)
        self.assertTrue(close(f["heading_deg"], 180.0, 0.1), f)

        # 3) Chạm góc (x=96, d=12) đảo cả hai thành phần (45° -> 225°)
        sc_corner = {"fish": [{"id": "F1", "kind": "ca_linh", "pos": [95.99, 11.99], "heading_deg": 45}], "random_fish": True}
        s_corner = Session("gather", tuning, sc_corner, 7)
        s_corner.step(self._idle())
        fc = s_corner.snapshot()["fish"][0]
        self.assertLessEqual(fc["pos"][0], 96.0)
        self.assertLessEqual(fc["pos"][1], 12.0)
        self.assertTrue(close(fc["heading_deg"], 225.0, 0.1), fc)

        # 4) Đổi hướng theo seed ở bước bơi thứ 120 (trước khi di chuyển)
        sc_turn = {"fish": [{"id": "F1", "kind": "ca_loc", "pos": [50, 14], "heading_deg": 0, "age_ticks": 119}],
                   "random_fish": True}
        s_turn = Session("gather", tuning, sc_turn, 99)
        s_turn.step(self._idle())
        ft = s_turn.snapshot()["fish"][0]
        self.assertNotAlmostEqual(ft["heading_deg"], 0.0, places=3)

        # 5) random_fish: false -> cá fixture đứng yên, không bơi/sinh
        sc_static = {"fish": [{"id": "F1", "kind": "ca_loc", "pos": [50, 14], "heading_deg": 0}], "random_fish": False}
        s_static = Session("gather", tuning, sc_static, 7)
        for _ in range(400):
            s_static.step(self._idle())
        self.assertEqual(s_static.snapshot()["fish"][0]["pos"], [50.0, 14.0])
        self.assertEqual(len(s_static.snapshot()["fish"]), 1)

    def test_v11_fish_spawn_schedule_cap_and_new_school_swims_next_tick(self):
        tuning = _v11_tuning()
        s = Session("gather", tuning, {}, 12)
        spawn_events = []
        for _ in range(360 * 6):
            rows = s.step(self._idle())
            for r in rows:
                if r["name"] == "fish_spawned":
                    spawn_events.append(r)
        # Bắt đầu 8 đàn, trần 12 -> chỉ sinh tối đa 4 đàn ở tick 360, 720, 1080, 1440
        self.assertEqual([e["tick"] for e in spawn_events], [360, 720, 1080, 1440])
        self.assertEqual(len(s.snapshot()["fish"]), 12)

        # Cá mới sinh tại tick 360 giữ nguyên vị trí ở tick 360 và bắt đầu bơi từ tick 361
        s_one = Session("gather", tuning, {"fish": [], "random_fish": True}, 5)
        for _ in range(360):
            rows = s_one.step(self._idle())
        ev = [r for r in rows if r["name"] == "fish_spawned"][0]
        snap_360 = s_one.snapshot()["fish"][0]
        self.assertEqual(snap_360["pos"], ev["data"]["pos"])
        s_one.step(self._idle())
        snap_361 = s_one.snapshot()["fish"][0]
        self.assertNotEqual(snap_361["pos"], snap_360["pos"])


if __name__ == "__main__":
    unittest.main()
