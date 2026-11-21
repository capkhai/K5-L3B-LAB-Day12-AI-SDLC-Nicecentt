"""Test Phase 3 (Contract v1.2): độ tươi, kho cá thể, ngưỡng 30, LIFO cá thể và chốt giá."""

import copy
import json
import unittest
from fractions import Fraction

from chonoi.contract import load_contract
from chonoi.errors import BadInput
from chonoi.freshness import fresh_base_price, item_frac, make_item
from chonoi.ids import IdAllocator
from chonoi.inputs import InputState
from chonoi.inventory import read_inventory, write_inventory
from chonoi.rng import Streams
from chonoi.runner import Session
from chonoi.sim.gather import GatherSim
from helpers import Workdir, write_json


def _v12_tuning():
    tuning = copy.deepcopy(load_contract()["tuning"])
    tuning["freshness"] = {
        "initial": 100,
        "gather_decay_per_s": 0.5,
        "quan_decay_per_s": 0.25,
        "spoiled_below": 30,
    }
    return tuning


def _inp(interact=False, catch=False):
    edges = set()
    if interact:
        edges.add("interact")
    if catch:
        edges.add("catch")
    return InputState((0.0, 0.0), {"interact": interact, "catch": catch}, edges)


class GatherFreshnessV12Test(unittest.TestCase):
    def test_spoiled_at_exact_threshold_30_and_id_order(self):
        tuning = _v12_tuning()
        sc = {
            "hold": [
                {"id": "I10", "kind": "ca_loc", "fresh": 30},
                {"id": "I2", "kind": "ca_linh", "fresh": 30},
            ],
            "random_fish": False,
            "monsters": [],
        }
        s = Session("gather", tuning, sc, 1)
        rows1 = s.step(_inp())
        spoiled = [r for r in rows1 if r["name"] == "spoiled"]
        self.assertEqual(len(spoiled), 2)
        self.assertEqual([e["data"]["item_id"] for e in spoiled], ["I2", "I10"])
        self.assertEqual(spoiled[0]["data"], {"item_id": "I2", "kind": "ca_linh", "location": "hold"})
        self.assertEqual(spoiled[0]["tick"], 1)
        # Không phát spoiled lần hai ở bước 2
        rows2 = s.step(_inp())
        self.assertEqual([r for r in rows2 if r["name"] == "spoiled"], [])

    def test_new_item_starts_at_100_decays_next_tick_and_exact_240_boundary(self):
        tuning = _v12_tuning()
        sc = {
            "player": {"pos": [15, 5]},
            "fish": [{"id": "F1", "kind": "ca_linh", "pos": [15, 5]}],
            "random_fish": False,
            "monsters": [],
        }
        s = Session("gather", tuning, sc, 1)
        rows1 = s.step(_inp(catch=True))
        self.assertEqual([r["name"] for r in rows1], ["fish_caught"])
        hold1 = s.snapshot()["hold"]
        self.assertEqual(hold1, [
            {"id": "I1", "kind": "ca_linh", "fresh": 100},
            {"id": "I2", "kind": "ca_linh", "fresh": 100},
            {"id": "I3", "kind": "ca_linh", "fresh": 100},
        ])
        # Bước 2 mới bắt đầu hao (-0.5/s = -1/120 = -2/240)
        s.step(_inp())
        self.assertEqual(item_frac(s.sim.hold[0]), Fraction(23998, 240))

        # Biên chính xác: 30 + 2/240 -> bước 1 còn đúng 30 (chưa ươn), bước 2 < 30 (ươn)
        sc_b = {
            "hold": [{"id": "I1", "kind": "ca_loc", "fresh": 30 + 2 / 240}],
            "random_fish": False,
            "monsters": [],
        }
        sb = Session("gather", tuning, sc_b, 1)
        self.assertEqual([r for r in sb.step(_inp()) if r["name"] == "spoiled"], [])
        self.assertEqual(len([r for r in sb.step(_inp()) if r["name"] == "spoiled"]), 1)

    def test_monster_hit_and_faint_lost_are_lifo_item_objects(self):
        tuning = _v12_tuning()
        sc = {
            "player": {"pos": [60, 20], "hp": 1},
            "hold": [
                {"id": "I1", "kind": "ca_loc", "fresh": 90},
                {"id": "I2", "kind": "bong_sung", "fresh": 80},
                {"id": "I3", "kind": "ca_keo", "fresh": 70},
            ],
            "monsters": [{"id": "M1", "kind": "ca_sau", "pos": [60, 20], "waypoints": [[60, 20], [64, 20]]}],
            "random_fish": False,
        }
        s = Session("gather", tuning, sc, 1)
        rows = s.step(_inp())
        by_name = {r["name"]: r["data"] for r in rows}
        self.assertEqual(len(by_name["monster_hit"]["lost"]), 1)
        self.assertEqual(by_name["monster_hit"]["lost"][0]["id"], "I3")
        self.assertEqual([x["id"] for x in by_name["faint"]["lost"]], ["I2", "I1"])
        self.assertEqual(by_name["gather_end"]["inventory"], {"items": []})

    def test_inventory_v12_roundtrip_and_rejects_count_schema(self):
        with Workdir() as w:
            p = w.path("inv12.json")
            raw_items = [
                make_item("I10", "ca_loc", Fraction(7202, 240)),
                make_item("I2", "ca_linh", 100),
            ]
            write_inventory(p, raw_items)
            with open(p, encoding="utf-8") as f:
                saved = json.load(f)
            self.assertEqual([x["id"] for x in saved["items"]], ["I2", "I10"])
            loaded = read_inventory(p, version="1.2")
            self.assertEqual(item_frac(loaded[1]), Fraction(7202, 240))

            # File kho đếm cũ -> BadInput (exit 2) ở v1.2
            old = write_json(w.path("old.json"), {"items": {"ca_loc": 1}})
            with self.assertRaises(BadInput):
                read_inventory(old, version="1.2")
            # Id trùng hoặc fresh ngoài [0, 100] -> BadInput
            dup = write_json(w.path("dup.json"), {"items": [
                {"id": "I1", "kind": "ca_loc", "fresh": 50},
                {"id": "I1", "kind": "ca_loc", "fresh": 60},
            ]})
            with self.assertRaises(BadInput):
                read_inventory(dup, version="1.2")
            oob = write_json(w.path("oob.json"), {"items": [{"id": "I1", "kind": "ca_loc", "fresh": 100.1}]})
            with self.assertRaises(BadInput):
                read_inventory(oob, version="1.2")

    def test_fresh_base_price_exact_floor_and_reallocate_ids(self):
        items = [make_item("I1", "ca_linh", 100), make_item("I2", "ca_linh", 50),
                 make_item("I3", "ca_linh", 50), make_item("I4", "bong_dien_dien", 50)]
        self.assertEqual(fresh_base_price(120, items), 75)
        # Không bị sai số nhị phân ở 29/100 * 100 = 29
        self.assertEqual(fresh_base_price(100, [make_item("I1", "ca_loc", 29)]), 29)

        ids = IdAllocator()
        ids.reserve("I5")
        tuning = _v12_tuning()
        g = GatherSim(
            tuning,
            {"hold": [{"id": "I1", "kind": "ca_loc", "fresh": 88}], "random_fish": False, "monsters": []},
            Streams(1), ids, day=2, reallocate_hold_ids=True,
        )
        self.assertEqual(g.snapshot()["hold"], [{"id": "I6", "kind": "ca_loc", "fresh": 88}])


if __name__ == "__main__":
    unittest.main()
