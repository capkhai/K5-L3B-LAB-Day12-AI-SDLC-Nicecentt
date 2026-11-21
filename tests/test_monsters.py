"""Test Phase 2, lát 2: Cá Sấu Năm Chèo (M1/M2), Máu, bất tử 90 tick, rơi LIFO, recoil 60 tick và ngất."""

import json
import math
import unittest

from chonoi.contract import load_contract
from chonoi.inputs import InputState
from chonoi.inventory import read_inventory
from chonoi.runner import Session
from chonoi.sim.gather import GatherSim
from chonoi.ids import IdAllocator
from chonoi.rng import Streams
from helpers import Workdir, close, events, read_jsonl, run_headless, snapshots, write_json


def _idle():
    return InputState((0.0, 0.0), {"interact": False, "catch": False}, set())


class GatherMonstersTest(unittest.TestCase):
    def test_contract_v11_has_core_phase2_values(self):
        contract = load_contract()
        self.assertIn(contract["contract_version"], ("1.1", "1.2", "1.3"))
        tuning = contract["tuning"]
        self.assertEqual(len(tuning["quan"]["stoves"]), 2)
        self.assertEqual(len(tuning["quan"]["tables"]), 4)
        self.assertEqual(len(tuning["menu"]), 6)
        self.assertEqual(len(tuning["day_plan"]), 5)
        self.assertIn("shop", tuning)

    def test_inventory_accepts_new_v11_ingredients(self):
        with Workdir() as w:
            p = write_json(w.path("inv.json"), {"items": {"ca_keo": 2, "keo_neo": 1}})
            self.assertEqual(read_inventory(p), {"ca_keo": 2, "keo_neo": 1})
            p12 = write_json(w.path("inv12.json"), {"items": [
                {"id": "I1", "kind": "ca_keo", "fresh": 100},
                {"id": "I2", "kind": "keo_neo", "fresh": 90},
            ]})
            self.assertEqual([it["kind"] for it in read_inventory(p12, version="1.2")], ["ca_keo", "keo_neo"])

    def test_day_spawns_m1_on_day1_and_m1_m2_on_day3(self):
        contract = load_contract()
        tuning = contract["tuning"]
        has_snake = "snake" in contract.get("extensions", [])
        day1_expected = ["M1", "M3"] if has_snake else ["M1"]
        day3_expected = ["M1", "M2", "M3"] if has_snake else ["M1", "M2"]
        g1 = GatherSim(tuning, {}, Streams(1), IdAllocator(), day=1)
        self.assertEqual([m["id"] for m in g1.snapshot()["monsters"]], day1_expected)
        g2 = GatherSim(tuning, {}, Streams(1), IdAllocator(), day=2)
        self.assertEqual([m["id"] for m in g2.snapshot()["monsters"]], day1_expected)
        g3 = GatherSim(tuning, {}, Streams(1), IdAllocator(), day=3)
        self.assertEqual([m["id"] for m in g3.snapshot()["monsters"]], day3_expected)

    def test_patrol_speed_and_waypoint_toggle(self):
        tuning = load_contract()["tuning"]
        # M1 xuất phát [60, 24], waypoints [[60,24],[64,24]], tốc độ 1.0 m/s -> 240 tick tới [64, 24]
        s = Session("gather", tuning, {"player": {"pos": [2, 0]}, "random_fish": False}, 1)
        for _ in range(60):
            s.step(_idle())
        m = s.snapshot()["monsters"][0]
        self.assertEqual(m["state"], "patrol")
        self.assertTrue(close(m["pos"][0], 61.0, 0.02), m)
        for _ in range(180):
            s.step(_idle())
        m = s.snapshot()["monsters"][0]
        self.assertTrue(close(m["pos"][0], 64.0, 0.02), m)
        self.assertEqual(m["target_idx"], 0)

    def test_chase_enter_exit_and_depth_threshold(self):
        tuning = load_contract()["tuning"]
        # Người chơi ở d = 9.5 (< 10) ngay gần M1 -> KHÔNG chase
        sc_shallow = {
            "player": {"pos": [60, 9.5]},
            "monsters": [{"id": "M1", "kind": "ca_sau", "pos": [60, 12], "waypoints": [[60, 12], [64, 12]]}],
            "random_fish": False,
        }
        s = Session("gather", tuning, sc_shallow, 1)
        s.step(_idle())
        self.assertEqual(s.snapshot()["monsters"][0]["state"], "patrol")

        # Người chơi ở d = 10, cách 8m (<= 10m) -> chuyển chase ở 3.0 m/s
        sc_chase = {
            "player": {"pos": [52, 10]},
            "monsters": [{"id": "M1", "kind": "ca_sau", "pos": [60, 10], "waypoints": [[60, 10], [64, 10]]}],
            "random_fish": False,
        }
        s2 = Session("gather", tuning, sc_chase, 1)
        s2.step(_idle())
        m2 = s2.snapshot()["monsters"][0]
        self.assertEqual(m2["state"], "chase")
        self.assertTrue(close(m2["pos"][0], 60.0 - 3.0 / 60.0, 1e-4), m2)

        # Cách > 16m -> quay lại patrol
        sc_exit = {
            "player": {"pos": [40, 15]},
            "monsters": [{"id": "M1", "kind": "ca_sau", "pos": [60, 15], "waypoints": [[60, 15], [64, 15]], "state": "chase"}],
            "random_fish": False,
        }
        s3 = Session("gather", tuning, sc_exit, 1)
        s3.step(_idle())
        self.assertEqual(s3.snapshot()["monsters"][0]["state"], "patrol")

    def test_hit_lifo_drop_invuln_recoil_and_no_hit_during_invuln(self):
        with Workdir() as w:
            # 5 món trong giỏ -> mất floor(5/2) = 2 món theo LIFO (nhặt sau mất trước)
            sc = write_json(w.path("sc.json"), {"gather": {
                "player": {"pos": [60, 20], "hp": 3},
                "hold": [
                    {"id": "I1", "kind": "ca_loc", "fresh": 100},
                    {"id": "I2", "kind": "bong_sung", "fresh": 100},
                    {"id": "I3", "kind": "ca_linh", "fresh": 100},
                    {"id": "I4", "kind": "ca_keo", "fresh": 100},
                    {"id": "I5", "kind": "keo_neo", "fresh": 100},
                ],
                "monsters": [{"id": "M1", "kind": "ca_sau", "pos": [61, 20], "waypoints": [[60, 20], [64, 20]]}],
                "random_fish": False,
            }})
            code, err = run_headless("--mode", "gather", "--seed", "1", "--ticks", "65",
                                     "--scenario", sc, "--snapshot-every", "1", "--out", w.path("o.jsonl"))
            self.assertEqual(code, 0, err)
            rows = read_jsonl(w.path("o.jsonl"))
            hits = events(rows, "monster_hit")
            self.assertEqual(len(hits), 1)
            self.assertEqual(hits[0]["tick"], 1)
            self.assertEqual(hits[0]["data"]["monster_id"], "M1")
            self.assertEqual(hits[0]["data"]["hp"], 2)
            self.assertEqual(hits[0]["data"]["pos"], [60, 20])
            self.assertEqual([(it["id"], it["kind"]) for it in hits[0]["data"]["lost"]],
                             [("I5", "keo_neo"), ("I4", "ca_keo")])
            snaps = {r["tick"]: r for r in snapshots(rows)}
            self.assertEqual([it["kind"] for it in snaps[1]["hold"]], ["ca_loc", "bong_sung", "ca_linh"])
            self.assertEqual(snaps[1]["player"]["invuln_ticks"], 90)
            m1 = snaps[1]["monsters"][0]
            self.assertEqual(m1["state"], "recoil")
            self.assertEqual(m1["state_ticks_left"], 60)
            # Sau 60 bước recoil (từ bước 2 đến bước 61): lùi 2m về +x rồi về patrol
            m61 = snaps[61]["monsters"][0]
            self.assertEqual(m61["state"], "patrol")
            self.assertEqual(m61["state_ticks_left"], 0)
            self.assertTrue(close(m61["pos"][0], m1["pos"][0] + 2.0, 0.02), (m1["pos"], m61["pos"]))

    def test_same_pos_recoil_uses_plus_x_and_monster_faint_clears_hold(self):
        with Workdir() as w:
            sc = write_json(w.path("sc.json"), {"gather": {
                "player": {"pos": [60, 20], "hp": 1},
                "hold": [
                    {"id": "I1", "kind": "ca_loc", "fresh": 100},
                    {"id": "I2", "kind": "bong_sung", "fresh": 100},
                    {"id": "I3", "kind": "ca_keo", "fresh": 100},
                ],
                "monsters": [{"id": "M1", "kind": "ca_sau", "pos": [60, 20], "waypoints": [[60, 20], [64, 20]]}],
                "random_fish": False,
            }})
            inv = w.path("inv.json")
            code, err = run_headless("--mode", "gather", "--seed", "1", "--ticks", "5",
                                     "--scenario", sc, "--inventory-out", inv, "--out", w.path("o.jsonl"))
            self.assertEqual(code, 0, err)
            rows = read_jsonl(w.path("o.jsonl"))
            names = [e["name"] for e in events(rows)]
            self.assertEqual(names, ["monster_hit", "faint", "gather_end"])
            # 3 món -> hit mất floor(3/2)=1 (I3 ca_keo), faint mất 2 món còn lại theo LIFO (I2 bong_sung, I1 ca_loc)
            self.assertEqual([(it["id"], it["kind"]) for it in events(rows, "monster_hit")[0]["data"]["lost"]],
                             [("I3", "ca_keo")])
            faint = events(rows, "faint")[0]["data"]
            self.assertEqual(faint["cause"], "monster")
            self.assertEqual(faint["hp"], 0)
            self.assertEqual([(it["id"], it["kind"]) for it in faint["lost"]],
                             [("I2", "bong_sung"), ("I1", "ca_loc")])
            self.assertEqual(snapshots(rows)[-1]["monsters"][0]["recoil_dir"], [1, 0])
            with open(inv, encoding="utf-8") as f:
                self.assertEqual(json.load(f), {"items": []})

    def test_invalid_monster_scenario_exits_2(self):
        with Workdir() as w:
            out = w.path("o.jsonl")
            bad_cases = [
                {"monsters": [{"id": "M1", "kind": "rong", "pos": [60, 20], "waypoints": [[60, 20], [64, 20]]}]},
                {"monsters": [{"id": "M1", "kind": "ca_sau", "pos": [60, 20], "waypoints": [[60, 20]]}]},
                {"monsters": [{"id": "M1", "kind": "ca_sau", "pos": [60, 20], "waypoints": [[60, 20], [64, 20]],
                               "state": "recoil", "state_ticks_left": 0, "recoil_dir": [1, 0]}]},
                {"monsters": [{"id": "M1", "kind": "ca_sau", "pos": [60, 20], "waypoints": [[60, 20], [64, 20]],
                               "state": "recoil", "state_ticks_left": 10, "recoil_dir": [2, 0]}]},
            ]
            for block in bad_cases:
                sc = write_json(w.path("sc.json"), {"gather": block})
                code, _ = run_headless("--mode", "gather", "--seed", "1", "--ticks", "0", "--scenario", sc, "--out", out)
                self.assertEqual(code, 2, block)


if __name__ == "__main__":
    unittest.main()
