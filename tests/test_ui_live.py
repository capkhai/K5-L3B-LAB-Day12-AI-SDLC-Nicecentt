"""Kiểm chứng giao diện live (client/ui — Người 4) và LiveGame cho cả gather, quan và --extra-content.

Không mở socket để chạy ổn định trên mọi môi trường (Windows sandbox, local, CI).
"""

import json
import os
import unittest

from chonoi.contract import load_contract
from chonoi.live import EXTRA_CONTENT_PATH, LiveGame, WEB_DIR


class LiveUiContractTest(unittest.TestCase):
    def setUp(self):
        with open(os.path.join(WEB_DIR, "index.html"), encoding="utf-8") as f:
            self.html = f.read()

    def test_index_html_endpoints_and_canvas(self):
        self.assertIn("<canvas", self.html)
        for endpoint in ("/state", "/input", "/restart"):
            self.assertIn(endpoint, self.html)
        # Không phụ thuộc CDN ngoài (chạy offline hoàn toàn)
        self.assertNotIn("https://", self.html)
        self.assertNotIn("http://", self.html)

    def test_index_html_covers_core_and_extra_content_ids(self):
        contract = load_contract()["tuning"]
        with open(EXTRA_CONTENT_PATH, encoding="utf-8") as f:
            extra = json.load(f)
        for kind in ("ca_loc", "ca_linh", "bong_dien_dien", "bong_sung",
                     "ca_keo", "ca_ro_dong", "keo_neo", "rau_muong"):
            self.assertIn(kind, self.html)
        for dish_id in (*contract["menu"].keys(), *extra["menu"].keys()):
            self.assertIn(dish_id, self.html)
        self.assertIn("/assets/cho-noi-sprites.png", self.html)

    def test_live_game_gather_and_quan_snapshot_and_input(self):
        tuning = load_contract()["tuning"]
        # Gather: bơi sang phải và cập bến -> không lỗi, restart sạch
        g = LiveGame("gather", tuning, {}, seed=1)
        st0 = json.loads(g.state_json())
        self.assertEqual(st0["mode"], "gather")
        self.assertIn("meta", st0)
        self.assertIn("events", st0)
        g.set_input({"move": [1, 0], "interact": False, "catch": False})
        for _ in range(10):
            g._tick_once()
        st1 = json.loads(g.state_json())
        self.assertGreater(st1["player"]["pos"][0], st0["player"]["pos"][0])
        self.assertIsNone(st1["error"])
        g.restart()
        st_reset = json.loads(g.state_json())
        self.assertEqual(st_reset["tick"], 0)
        self.assertEqual(st_reset["player"]["pos"], st0["player"]["pos"])

        # Quan: đi sang trái trong quán và kiểm tra snapshot đầy đủ
        q = LiveGame("quan", tuning, {}, seed=1, inventory={"ca_loc": 2, "bong_sung": 2})
        qs0 = json.loads(q.state_json())
        self.assertEqual(qs0["mode"], "quan")
        self.assertEqual(qs0["stock"], {"bong_sung": 2, "ca_loc": 2})
        self.assertIn("stoves", qs0)
        self.assertIn("tables", qs0)
        self.assertIn("customers", qs0)
        q.set_input({"move": [-1, 0], "interact": False, "catch": False})
        for _ in range(10):
            q._tick_once()
        qs1 = json.loads(q.state_json())
        self.assertLess(qs1["player"]["pos"][0], qs0["player"]["pos"][0])
        self.assertIsNone(qs1["error"])

    def test_live_game_extra_content_snapshot(self):
        tuning = load_contract()["tuning"]
        with open(EXTRA_CONTENT_PATH, encoding="utf-8") as f:
            extra = json.load(f)
        tuning["gather"]["nodes"].extend(extra["gather"]["nodes"])
        tuning["gather"]["fish_initial"].extend(extra["gather"]["fish_initial"])
        tuning["gather"]["fish_yield"].update(extra["gather"]["fish_yield"])
        g = LiveGame("gather", tuning, {}, seed=1)
        st = json.loads(g.state_json())
        node_kinds = {n["kind"] for n in st["nodes"]}
        fish_kinds = {f["kind"] for f in st["fish"]}
        self.assertTrue({"keo_neo", "rau_muong"} <= node_kinds)
        self.assertTrue({"ca_keo", "ca_ro_dong"} <= fish_kinds)


if __name__ == "__main__":
    unittest.main()
