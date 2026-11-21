"""Kiểm chứng giao diện live (client/ui — Người 4) cho Phase 1 & Phase 2 (`gather`, `quan`, `day`, Shop, Pause, HUD v1.1).

Không mở socket để chạy ổn định trên mọi môi trường (Windows sandbox, local, CI).
"""

import json
import os
import unittest

from chonoi.contract import load_contract
from chonoi.freshness import make_item
from chonoi.live import DAY_INTRO_TICKS, EXTRA_CONTENT_PATH, LiveGame, SHOP_DEFAULT_TICKS, WEB_DIR


class LiveUiContractTest(unittest.TestCase):
    def setUp(self):
        with open(os.path.join(WEB_DIR, "index.html"), encoding="utf-8") as f:
            self.html = f.read()

    def test_index_html_endpoints_canvas_and_typography(self):
        self.assertIn("<canvas", self.html)
        for endpoint in ("/state", "/input", "/action", "/restart"):
            self.assertIn(endpoint, self.html)
        # Yêu cầu Phase 2: chữ không chân >= 18px ở 1280x720, không phụ thuộc CDN ngoài
        self.assertIn("--hud-font: 18px", self.html)
        self.assertNotIn("https://", self.html)
        self.assertNotIn("http://", self.html)

    def test_index_html_covers_phase2_screens_warnings_and_assets(self):
        contract = load_contract()["tuning"]
        with open(EXTRA_CONTENT_PATH, encoding="utf-8") as f:
            extra = json.load(f)
        for kind in ("ca_loc", "ca_linh", "ca_keo", "bong_dien_dien", "bong_sung", "keo_neo",
                     "ca_ro_dong", "rau_muong"):
            self.assertIn(kind, self.html)
        for dish_id in (*contract["menu"].keys(), *extra["menu"].keys()):
            self.assertIn(dish_id, self.html)
        for token in ("day_intro", "evening_intro", "day_result", "shop", "summary",
                      "THỦY QUÁI!", "HẾT HƠI!", "HÀNG ƯƠN", "drawMonster", "pauseModal"):
            self.assertIn(token, self.html)
        self.assertIn("/assets/cho-noi-sprites.png", self.html)
        self.assertIn("/assets/ut-sen-swim.png", self.html)
        self.assertTrue(os.path.isfile(os.path.join(WEB_DIR, "assets", "cho-noi-sprites.png")))
        self.assertTrue(os.path.isfile(os.path.join(WEB_DIR, "assets", "ut-sen-swim.png")))

    def test_live_game_gather_and_quan_snapshot_and_input(self):
        tuning = load_contract()["tuning"]
        g = LiveGame("gather", tuning, {}, seed=1)
        st0 = json.loads(g.state_json())
        self.assertEqual(st0["mode"], "gather")
        self.assertEqual(st0["screen"], "playing")
        self.assertIn("meta", st0)
        self.assertIn("menu", st0)
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

        q_inv = [
            {"id": "I1", "kind": "ca_loc", "fresh": 100},
            {"id": "I2", "kind": "ca_loc", "fresh": 95},
            {"id": "I3", "kind": "bong_sung", "fresh": 90},
            {"id": "I4", "kind": "bong_sung", "fresh": 85},
        ]
        q = LiveGame("quan", tuning, {}, seed=1, inventory=q_inv)
        qs0 = json.loads(q.state_json())
        self.assertEqual(qs0["mode"], "quan")
        self.assertEqual(qs0["stock"], q_inv)
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
        tuning["gather"]["fish_yield"].update(extra["gather"]["fish_yield"])
        scenario = {}
        if isinstance(tuning["gather"]["fish_initial"], list):
            tuning["gather"]["fish_initial"].extend(extra["gather"]["fish_initial"])
        else:
            scenario = {"fish": extra["gather"]["fish_initial"], "random_fish": False}
        g = LiveGame("gather", tuning, scenario, seed=1)
        st = json.loads(g.state_json())
        self.assertTrue({"keo_neo", "rau_muong"} <= {n["kind"] for n in st["nodes"]})
        self.assertTrue({"ca_keo", "ca_ro_dong"} <= {f["kind"] for f in st["fish"]})

    def test_live_day_full_cycle_pause_shop_and_upgrades(self):
        """Kiểm chứng trọn vòng --mode day: Menu -> DayIntro -> Gather -> EveningIntro -> Quan -> DayResult -> Shop -> Day 2 -> Summary."""
        tuning = load_contract()["tuning"]
        g = LiveGame("day", tuning, {}, seed=7, days=2)

        # 1. Bắt đầu ở Menu chính
        st = json.loads(g.state_json())
        self.assertEqual(st["screen"], "menu")
        self.assertEqual(st["day"], 1)
        g._tick_once()
        self.assertEqual(json.loads(g.state_json())["tick"], 0)

        # 2. Nhấn Chơi -> DayIntro (4s = 240 tick) và kiểm Pause dừng timer DayIntro
        g.perform_action({"action": "start"})
        st = json.loads(g.state_json())
        self.assertEqual(st["screen"], "day_intro")
        self.assertEqual(st["screen_ticks_left"], DAY_INTRO_TICKS)
        g.perform_action({"action": "pause"})
        for _ in range(10):
            g._tick_once()
        st = json.loads(g.state_json())
        self.assertTrue(st["paused"])
        self.assertEqual(st["screen_ticks_left"], DAY_INTRO_TICKS)
        g.perform_action({"action": "resume"})
        g.perform_action({"action": "skip_intro"})
        st = json.loads(g.state_json())
        self.assertEqual(st["screen"], "playing")
        self.assertEqual(st["mode"], "gather")
        oxy_day1 = st["player"]["oxygen_max_ticks"]

        # 3. Cập bến ngay tại dock -> chuyển sang EveningIntro với kho mang về (v1.2 cá thể)
        g.session.sim.hold.append(make_item("I1", "ca_loc", 100))
        g.set_input({"interact": True})
        g._tick_once()
        st = json.loads(g.state_json())
        self.assertEqual(st["screen"], "evening_intro")
        self.assertEqual(len(st["last_gather_inventory"]["items"]), 1)
        self.assertEqual(st["last_gather_inventory"]["items"][0]["kind"], "ca_loc")

        # 4. Bỏ qua EveningIntro -> Quan -> hết giờ -> DayResult
        g.perform_action({"action": "skip_intro"})
        st = json.loads(g.state_json())
        self.assertEqual(st["screen"], "playing")
        self.assertEqual(st["mode"], "quan")
        g.session.sim.money = 220
        g.session.sim.earned = 220
        g.session.sim.time_left_ticks = 1
        g._tick_once()
        st = json.loads(g.state_json())
        self.assertEqual(st["screen"], "day_result")
        self.assertEqual(st["days_completed"], 1)

        # 5. Mở Shop: kiểm Pause đóng băng timer Shop, mua oxygen thành công, mua hp thất bại do thiếu tiền
        g.perform_action({"action": "open_shop"})
        st = json.loads(g.state_json())
        self.assertEqual(st["screen"], "shop")
        self.assertEqual(st["shop"]["ticks_left"], SHOP_DEFAULT_TICKS)
        g.perform_action({"action": "pause"})
        for _ in range(20):
            g._tick_once()
        self.assertEqual(json.loads(g.state_json())["shop"]["ticks_left"], SHOP_DEFAULT_TICKS)
        g.perform_action({"action": "resume"})
        g._tick_once()
        self.assertEqual(json.loads(g.state_json())["shop"]["ticks_left"], SHOP_DEFAULT_TICKS - 1)

        buy_ok = g.perform_action({"action": "buy", "item": "oxygen"})
        self.assertTrue(buy_ok["ok"])
        buy_fail = g.perform_action({"action": "buy", "item": "hp"})
        self.assertFalse(buy_fail["ok"])
        self.assertEqual(buy_fail["reason"], "insufficient_money")

        # 6. Đóng Shop -> Ngày 2 với active_upgrades["oxygen"] == 1 (+10s oxy tối đa)
        g.perform_action({"action": "shop_done"})
        st = json.loads(g.state_json())
        self.assertEqual(st["screen"], "day_intro")
        self.assertEqual(st["day"], 2)
        self.assertEqual(st["active_upgrades"]["oxygen"], 1)
        g.perform_action({"action": "skip_intro"})
        st = json.loads(g.state_json())
        self.assertGreater(st["player"]["oxygen_max_ticks"], oxy_day1)

        # 7. Hoàn thành Ngày 2 (ngày cuối với days=2) -> Summary
        g.set_input({"interact": True})
        g._tick_once()
        g.perform_action({"action": "skip_intro"})
        g.session.sim.time_left_ticks = 1
        g._tick_once()
        st = json.loads(g.state_json())
        self.assertEqual(st["screen"], "summary")
        self.assertTrue(st["finished"])
        self.assertEqual(st["reason"], "days_complete")


if __name__ == "__main__":
    unittest.main()
