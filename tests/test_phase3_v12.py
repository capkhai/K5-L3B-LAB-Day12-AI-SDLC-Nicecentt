"""Kiểm thử đầy đủ Phase 3 (Contract v1.2 — Mùa Nước Nổi): Quán, bàn giao file, vòng ngày `day`, pause, giá theo độ tươi."""

import copy
import json
import unittest

from chonoi.contract import load_contract
from chonoi.errors import BadInput
from chonoi.inputs import InputState
from chonoi.runner import Session
from helpers import Workdir, close, events, frames, read_jsonl, run_headless, snapshots, write_json


def _inp(*edges, move=(0.0, 0.0), buy=None):
    return InputState(move, {e: True for e in edges}, set(edges), buy=buy)


class QuanFreshnessV12Test(unittest.TestCase):
    def setUp(self):
        self.tuning = copy.deepcopy(load_contract()["tuning"])

    def test_exact_threshold_30_spoils_by_id_order_and_boundary_stays_fresh(self):
        # 30.0 -> 30 - 1/240 (<30) => ươn ở bước 1, phát theo id tự nhiên (I2 trước I10)
        # 30 + 1/240 -> đúng 30.0 ở bước 1 (CHƯA ươn), chỉ ươn ở bước 2
        s = Session("quan", self.tuning, {
            "random_customers": False,
            "stock": [
                {"id": "I10", "kind": "ca_loc", "fresh": 30},
                {"id": "I2", "kind": "bong_sung", "fresh": 30},
                {"id": "I3", "kind": "ca_loc", "fresh": 30 + 1 / 240},
            ],
        }, 1)
        r1 = s.step(_inp())
        self.assertEqual(
            [(e["name"], e["data"]) for e in r1],
            [
                ("spoiled", {"item_id": "I2", "kind": "bong_sung", "location": "stock"}),
                ("spoiled", {"item_id": "I10", "kind": "ca_loc", "location": "stock"}),
            ],
        )
        # Bước 2: I3 vượt 30 -> ươn đúng một lần; I2 và I10 KHÔNG phát lại
        r2 = s.step(_inp())
        self.assertEqual(
            [(e["name"], e["data"]) for e in r2],
            [("spoiled", {"item_id": "I3", "kind": "ca_loc", "location": "stock"})],
        )
        self.assertEqual(s.step(_inp()), [])

    def test_spoiled_reservation_releases_all_and_rereserves_once_by_order_key(self):
        # C1 (order_tick=0, T1) gọi canh_chua_ca_loc (ca_loc + bong_dien_dien), đang giữ I1(fresh=30) & I2(fresh=80)
        # C2 (order_tick=1, T2) gọi ca_loc_nuong_trui (ca_loc), đang giữ I3(fresh=30)
        # Trong kho có I4(ca_loc, fresh=90) khả dụng.
        # Bước 1: I1 và I3 đều ươn -> C1 xử lý trước: nhả I1 & I2, thử giữ lại -> lấy I4(ca_loc,90) + I2(bong_dien_dien,80) -> reserved!
        # Tiếp theo C2 xử lý: nhả I3, không còn ca_loc chưa ươn -> chuyển unfulfillable (chờ tới hạn).
        s = Session("quan", self.tuning, {
            "random_customers": False,
            "stock": [
                {"id": "I1", "kind": "ca_loc", "fresh": 30},
                {"id": "I2", "kind": "bong_dien_dien", "fresh": 80},
                {"id": "I3", "kind": "ca_loc", "fresh": 30},
                {"id": "I4", "kind": "ca_loc", "fresh": 90},
            ],
            "customers": [
                {"id": "C2", "table_id": "T2", "dish_id": "ca_loc_nuong_trui", "order_tick": 1, "reserved": ["I3"]},
                {"id": "C1", "table_id": "T1", "dish_id": "canh_chua_ca_loc", "order_tick": 0, "reserved": ["I1", "I2"]},
            ],
        }, 1)
        rows = s.step(_inp())
        # Phát hết spoiled theo id (I1, I3) trước khi xử lý giữ chỗ
        self.assertEqual([e["data"]["item_id"] for e in rows if e["name"] == "spoiled"], ["I1", "I3"])
        custs = {c["id"]: c for c in s.snapshot()["customers"]}
        self.assertEqual(custs["C1"]["order_status"], "reserved")
        self.assertEqual(custs["C1"]["reserved"], ["I2", "I4"])
        self.assertEqual(custs["C2"]["order_status"], "unfulfillable")
        self.assertEqual(custs["C2"]["reserved"], [])

    def test_auto_reserve_picks_freshest_then_smallest_id_and_locks_fresh_price(self):
        # Kho có I10(ca_loc, 80), I2(ca_loc, 80), I3(ca_loc, 60), I4(bong_dien_dien, 70)
        # C1 gọi canh_chua_ca_loc (90k) bỏ trống reserved -> phải chọn I2 (tươi nhất 80, hòa id chọn I2 < I10) và I4 (70)
        s = Session("quan", self.tuning, {
            "random_customers": False,
            "player": {"pos": [2, 8]},
            "stock": [
                {"id": "I10", "kind": "ca_loc", "fresh": 80},
                {"id": "I2", "kind": "ca_loc", "fresh": 80},
                {"id": "I3", "kind": "ca_loc", "fresh": 60},
                {"id": "I4", "kind": "bong_dien_dien", "fresh": 70},
            ],
            "customers": [{"id": "C1", "table_id": "T1", "dish_id": "canh_chua_ca_loc"}],
        }, 1)
        self.assertEqual(s.snapshot()["customers"][0]["reserved"], ["I2", "I4"])

        # Nhấn interact ở bước 1 -> I2 còn 80 - 1/240, I4 còn 70 - 1/240; avg < 75 -> floor(90 * avg / 100) = 67
        rows = s.step(_inp("interact"))
        self.assertEqual([e["name"] for e in rows], ["cook_started"])
        data = rows[0]["data"]
        # items sắp theo kind rồi id: bong_dien_dien (I4) trước ca_loc (I2)
        self.assertEqual([(it["kind"], it["id"]) for it in data["items"]], [("bong_dien_dien", "I4"), ("ca_loc", "I2")])
        self.assertEqual(data["base_price"], 67)
        # Đã tiêu đúng I2 và I4 khỏi kho; I3 và I10 còn lại
        self.assertEqual([it["id"] for it in s.snapshot()["stock"]], ["I3", "I10"])

        # Nấu xong (480 tick) -> bưng -> phục vụ -> ăn -> trả tiền: tip tính trên base_price=67 -> floor(67*0.2)=13 -> tổng 80
        for _ in range(479):
            s.step(_inp())
        ready_pick = s.step(_inp("interact"))
        self.assertEqual([e["name"] for e in ready_pick], ["dish_ready", "dish_picked"])
        s.sim.pos = [9.0, 2.0]
        served = s.step(_inp("interact"))
        self.assertEqual(served[0]["name"], "served")
        self.assertEqual(served[0]["data"]["base_price"], 67)
        self.assertEqual(served[0]["data"]["tip"], 13)

    def test_pause_freezes_freshness_in_gather_and_quan(self):
        for mode, sc in (
            ("gather", {"hold": [{"id": "I1", "kind": "ca_loc", "fresh": 30}], "random_fish": False, "monsters": []}),
            ("quan", {"stock": [{"id": "I1", "kind": "ca_loc", "fresh": 30}], "random_customers": False}),
        ):
            with self.subTest(mode=mode):
                s = Session(mode, self.tuning, sc, 1)
                self.assertEqual([e["name"] for e in s.step(_inp("pause"))], ["paused"])
                for _ in range(20):
                    self.assertEqual(s.step(_inp()), [])
                container = s.snapshot()["hold" if mode == "gather" else "stock"]
                self.assertEqual(container[0]["fresh"], 30)
                resumed = s.step(_inp("pause"))
                self.assertEqual([e["name"] for e in resumed[:2]], ["resumed", "spoiled"])

    def test_bad_v12_quan_scenarios_raise(self):
        bad_cases = [
            {"stock": [{"id": "I1", "kind": "ca_loc", "fresh": 29.5}],
             "customers": [{"id": "C1", "table_id": "T1", "dish_id": "ca_loc_nuong_trui", "reserved": ["I1"]}]},
            {"stock": [{"id": "I1", "kind": "ca_loc", "fresh": 100}],
             "customers": [
                 {"id": "C1", "table_id": "T1", "dish_id": "ca_loc_nuong_trui", "reserved": ["I1"]},
                 {"id": "C2", "table_id": "T2", "dish_id": "ca_loc_nuong_trui", "reserved": ["I1"]},
             ]},
            {"stock": [{"id": "I1", "kind": "bong_sung", "fresh": 100}],
             "customers": [{"id": "C1", "table_id": "T1", "dish_id": "ca_loc_nuong_trui", "reserved": ["I1"]}]},
        ]
        for block in bad_cases:
            with self.subTest(block=block), self.assertRaises(BadInput):
                Session("quan", self.tuning, {**block, "random_customers": False}, 1)


class HeadlessAndDayV12Test(unittest.TestCase):
    def test_ticket03_smoke_file_handoff_and_count_dict_rejected_exit_2(self):
        """Smoke chuẩn TICKET-03: gather cập bến tick 0 -> quan --inventory --ticks 0 khớp từng id/kind/fresh; kho đếm -> mã 2."""
        with Workdir() as w:
            sc = write_json(w.path("sc.json"), {"gather": {
                "hold": [{"id": "I1", "kind": "ca_linh", "fresh": 100}],
                "random_fish": False,
                "monsters": [],
            }})
            inp = write_json(w.path("in.json"), frames({"tick": 0, "interact": True}))
            inv = w.path("inv.json")
            code, err = run_headless("--mode", "gather", "--seed", "7", "--ticks", "5",
                                     "--scenario", sc, "--inputs", inp, "--inventory-out", inv, "--out", w.path("g.jsonl"))
            self.assertEqual(code, 0, err)
            with open(inv, encoding="utf-8") as f:
                saved = json.load(f)
            self.assertEqual(len(saved["items"]), 1)
            self.assertEqual(saved["items"][0]["id"], "I1")
            self.assertEqual(saved["items"][0]["kind"], "ca_linh")
            self.assertTrue(close(saved["items"][0]["fresh"], 100 - 0.5 / 60, 1e-6), saved)

            code, err = run_headless("--mode", "quan", "--seed", "7", "--ticks", "0",
                                     "--inventory", inv, "--out", w.path("q.jsonl"))
            self.assertEqual(code, 0, err)
            q_stock = snapshots(read_jsonl(w.path("q.jsonl")))[0]["stock"]
            self.assertEqual(q_stock, saved["items"])

            # File kho đếm v1.0/v1.1 phải bị trả mã thoát 2 ở v1.2
            old_inv = write_json(w.path("old.json"), {"items": {"ca_linh": 1}})
            code_old, _ = run_headless("--mode", "quan", "--seed", "7", "--ticks", "0",
                                       "--inventory", old_inv, "--out", w.path("bad.jsonl"))
            self.assertEqual(code_old, 2)

    def test_day_mode_v12_handoff_shop_no_decay_day2_new_ids_and_deterministic(self):
        with Workdir() as w:
            sc = write_json(w.path("day.json"), {
                "gather": {
                    "hold": [{"id": "I1", "kind": "ca_loc", "fresh": 100}],
                    "random_fish": False,
                    "random_current": False,
                    "monsters": [],
                    "time_left_ticks": 1,
                },
                "quan": {"random_customers": False, "time_left_ticks": 1},
            })
            inp = write_json(w.path("inp.json"), frames(
                {"tick": 2, "shop_done": True},
                {"tick": 3, "shop_done": False},
                {"tick": 5, "shop_done": True},
            ))
            o1, o2 = w.path("d1.jsonl"), w.path("d2.jsonl")
            for out in (o1, o2):
                code, err = run_headless("--mode", "day", "--days", "2", "--seed", "7", "--ticks", "20",
                                         "--scenario", sc, "--inputs", inp, "--snapshot-every", "1", "--out", out)
                self.assertEqual(code, 0, err)
            with open(o1, "rb") as f1, open(o2, "rb") as f2:
                self.assertEqual(f1.read(), f2.read())

            rows = read_jsonl(o1)
            snaps = {s["tick"]: s for s in snapshots(rows)}
            # Tick 0 (Ngày 1 gather): giữ nguyên I1
            self.assertEqual(snaps[0]["hold"][0]["id"], "I1")
            # Tick 1 (chuyển sang quan cùng tick, không hao thêm): I1 mang fresh sau đúng 1 tick gather
            expected_after_g = 100 - 0.5 / 60
            self.assertEqual(snaps[1]["phase"], "quan")
            self.assertEqual(snaps[1]["stock"][0]["id"], "I1")
            self.assertTrue(close(snaps[1]["stock"][0]["fresh"], expected_after_g, 1e-6))
            # Tick 2 (chuyển sang shop): stock là mảng cá thể sau 1 tick quan
            self.assertEqual(snaps[2]["phase"], "shop")
            self.assertTrue(close(snaps[2]["stock"][0]["fresh"], expected_after_g - 0.25 / 60, 1e-6))
            # Tick 3 (Ngày 2 gather): cấp id mới I2 thay vì dùng lại I1!
            self.assertEqual(snaps[3]["day"], 2)
            self.assertEqual(snaps[3]["phase"], "gather")
            self.assertEqual(snaps[3]["hold"][0]["id"], "I2")
            self.assertEqual(snaps[3]["hold"][0]["fresh"], 100)
            self.assertEqual(rows[-1]["days_completed"], 2)
            self.assertEqual(rows[-1]["reason"], "days_complete")


if __name__ == "__main__":
    unittest.main()
