"""Kiểm thử 3 phần mở rộng của nhóm Nicecentt: `current` (Dòng nước lũ), `snake` (Rắn Hổ Mây M3), `burn` (Cháy món)."""

import copy
import unittest

from chonoi.contract import load_contract
from chonoi.inputs import InputState
from chonoi.runner import Session
from helpers import Workdir, close, events, read_jsonl, run_headless, snapshots, write_json


def _idle():
    return InputState((0.0, 0.0), {"interact": False, "catch": False}, set())


def _press(btn):
    return InputState((0.0, 0.0), {btn: True}, {btn})


class ManifestExtensionsTest(unittest.TestCase):
    def test_manifest_declares_all_three_extensions(self):
        contract = load_contract()
        exts = contract.get("extensions", [])
        self.assertIn("burn", exts)
        self.assertIn("snake", exts)
        self.assertIn("current", exts)
        self.assertEqual(contract["tuning"]["quan"]["burn_s"], 20)
        self.assertIn("ran", contract["tuning"]["gather"]["monsters"]["species"])
        self.assertEqual(contract["tuning"]["gather"]["current"], {
            "interval_ticks": 1800,
            "duration_ticks": 480,
            "warning_ticks": 120,
            "min_depth": 10,
            "speed": 1.5,
        })


class CurrentExtensionTest(unittest.TestCase):
    def setUp(self):
        self.tuning = copy.deepcopy(load_contract()["tuning"])

    def test_warning_start_ticks_left_force_and_elapsed_end(self):
        # Dùng interval nhỏ hơn trong bản sao tuning để test toàn bộ chu kỳ từng tick thật chặt
        self.tuning["gather"]["current"] = {
            "interval_ticks": 10,
            "duration_ticks": 4,
            "warning_ticks": 2,
            "min_depth": 10,
            "speed": 1.5,
        }
        sc = {
            "player": {"pos": [50, 10], "oxygen_ticks": 1800},
            "monsters": [],
            "random_fish": False,
            "current_direction": 1,
        }
        s = Session("gather", self.tuning, sc, 7)
        self.assertIsNone(s.snapshot()["current"])

        all_events = []
        snaps = {0: s.snapshot()}
        for t in range(1, 16):
            all_events.extend(s.step(_idle()))
            snaps[t] = s.snapshot()

        # Warning ở t = 10 - 2 = 8
        warns = [e for e in all_events if e["name"] == "current_warning"]
        self.assertEqual(len(warns), 1)
        self.assertEqual(warns[0]["tick"], 8)
        self.assertEqual(warns[0]["data"], {"starts_at_phase_tick": 10})
        self.assertIsNone(snaps[8]["current"])
        self.assertIsNone(snaps[9]["current"])

        # Start ở t = 10, kéo dài 4 tick (10, 11, 12, 13); snapshot đếm cả tick vừa chụp -> 4, 3, 2, 1
        starts = [e for e in all_events if e["name"] == "current_start"]
        self.assertEqual(len(starts), 1)
        self.assertEqual(starts[0]["tick"], 10)
        self.assertEqual(starts[0]["data"], {"direction": 1, "duration_ticks": 4})
        self.assertEqual(snaps[10]["current"], {"direction": 1, "ticks_left": 4})
        self.assertEqual(snaps[11]["current"], {"direction": 1, "ticks_left": 3})
        self.assertEqual(snaps[12]["current"], {"direction": 1, "ticks_left": 2})
        self.assertEqual(snaps[13]["current"], {"direction": 1, "ticks_left": 1})

        # Lực 1.5 m/s = 0.025 m/tick áp đúng 4 lần (từ tick 10..13), KHÔNG tích lũy vào vel
        self.assertTrue(close(snaps[9]["player"]["pos"][0], 50.0, 1e-9))
        self.assertTrue(close(snaps[10]["player"]["pos"][0], 50.025, 1e-9))
        self.assertTrue(close(snaps[13]["player"]["pos"][0], 50.100, 1e-9))
        self.assertEqual(snaps[13]["player"]["vel"], [0.0, 0.0])

        # Kết thúc ở tick 14 (10 + 4) trước di chuyển -> KHÔNG cộng thêm lực ở tick 14
        ends = [e for e in all_events if e["name"] == "current_end"]
        self.assertEqual(len(ends), 1)
        self.assertEqual(ends[0]["tick"], 14)
        self.assertEqual(ends[0]["data"], {"direction": 1, "reason": "elapsed"})
        self.assertIsNone(snaps[14]["current"])
        self.assertTrue(close(snaps[14]["player"]["pos"][0], 50.100, 1e-9))

    def test_depth_gate_uses_start_of_step_depth_and_clamps_bounds(self):
        self.tuning["gather"]["current"] = {
            "interval_ticks": 2,
            "duration_ticks": 3,
            "warning_ticks": 1,
            "min_depth": 10,
            "speed": 6.0,  # 0.1 m/tick
        }
        self.tuning["gather"]["ramp_max_ticks"] = 0
        # Trường hợp 1: d đầu bước = 9.99 (< 10), bơi xuống qua 10 trong bước -> KHÔNG bị đẩy ở bước này
        sc1 = {
            "player": {"pos": [50, 9.99]},
            "monsters": [],
            "random_fish": False,
            "current_direction": 1,
        }
        s1 = Session("gather", self.tuning, sc1, 1)
        s1.step(_idle())  # tick 1
        s1.step(InputState((0.0, 1.0), {}, set()))  # tick 2: current starts, start_d=9.99 < 10
        self.assertTrue(s1.snapshot()["player"]["pos"][1] > 10.0)
        self.assertTrue(close(s1.snapshot()["player"]["pos"][0], 50.0, 1e-9))
        # Bước 3: start_d > 10 -> bị đẩy +0.1
        s1.step(_idle())
        self.assertTrue(close(s1.snapshot()["player"]["pos"][0], 50.1, 1e-9))

        # Trường hợp 2: chặn mép trái x = 0 khi dòng -1
        sc2 = {
            "player": {"pos": [0.05, 12.0]},
            "monsters": [],
            "random_fish": False,
            "current_direction": -1,
        }
        s2 = Session("gather", self.tuning, sc2, 1)
        s2.step(_idle())
        s2.step(_idle())
        self.assertEqual(s2.snapshot()["player"]["pos"][0], 0.0)

    def test_phase_end_emits_current_end_before_faint_and_gather_end(self):
        self.tuning["gather"]["current"] = {
            "interval_ticks": 2,
            "duration_ticks": 10,
            "warning_ticks": 1,
            "min_depth": 10,
            "speed": 1.5,
        }
        # 1) Ngất do ngạt ngay bước 2 khi dòng đang chạy -> current_end(phase_end) trước faint và gather_end
        sc_faint = {
            "player": {"pos": [50, 12], "hp": 1, "oxygen_ticks": 0, "zero_oxy_ticks": 58},
            "monsters": [],
            "random_fish": False,
            "current_direction": -1,
        }
        sf = Session("gather", self.tuning, sc_faint, 1)
        sf.step(_idle())  # tick 1: zero_oxy_ticks -> 59
        rows_faint = sf.step(_idle())  # tick 2: current_start -> force -> choke -> current_end(phase_end) -> faint -> gather_end
        self.assertEqual(
            [e["name"] for e in rows_faint],
            ["current_start", "choke", "current_end", "faint", "gather_end"],
        )
        self.assertEqual(rows_faint[2]["data"], {"direction": -1, "reason": "phase_end"})
        self.assertTrue(close(sf.snapshot()["player"]["pos"][0], 50.0 - 0.025, 1e-9))

        # 2) Bước bắt đầu dòng trùng bước cuối ca (time_left_ticks == 2) -> vẫn có lực, rồi current_end(phase_end) trước gather_end
        sc_time = {
            "player": {"pos": [50, 12]},
            "time_left_ticks": 2,
            "monsters": [],
            "random_fish": False,
            "current_direction": 1,
        }
        st = Session("gather", self.tuning, sc_time, 1)
        st.step(_idle())
        rows_time = st.step(_idle())
        self.assertEqual([e["name"] for e in rows_time], ["current_start", "current_end", "gather_end"])
        self.assertEqual(rows_time[1]["data"], {"direction": 1, "reason": "phase_end"})
        self.assertTrue(close(st.snapshot()["player"]["pos"][0], 50.025, 1e-9))

        # 3) Cập bến sớm khi dòng đang chạy -> current_end(phase_end) trước gather_end
        sc_dock = {
            "player": {"pos": [2, 0]},
            "monsters": [],
            "random_fish": False,
            "current_direction": 1,
        }
        sd = Session("gather", self.tuning, sc_dock, 1)
        sd.step(_idle())  # tick 1
        rows_dock = sd.step(_press("interact"))  # tick 2: current_start -> dock -> current_end(phase_end) -> gather_end
        self.assertEqual([e["name"] for e in rows_dock], ["current_start", "current_end", "gather_end"])
        self.assertEqual(rows_dock[1]["data"], {"direction": 1, "reason": "phase_end"})

    def test_random_current_false_disables_schedule(self):
        self.tuning["gather"]["current"] = {
            "interval_ticks": 5,
            "duration_ticks": 3,
            "warning_ticks": 1,
            "min_depth": 10,
            "speed": 1.5,
        }
        s = Session("gather", self.tuning, {
            "player": {"pos": [50, 12]},
            "monsters": [],
            "random_fish": False,
            "random_current": False,
        }, 1)
        evs = []
        for _ in range(15):
            evs.extend(s.step(_idle()))
        self.assertEqual([e for e in evs if e["name"].startswith("current_")], [])
        self.assertIsNone(s.snapshot()["current"])

    def test_headless_standard_schedule_1680_1800_2280_and_cli_cutoff(self):
        with Workdir() as w:
            sc = write_json(w.path("sc.json"), {"gather": {
                "player": {"pos": [2, 0]},
                "monsters": [],
                "random_fish": False,
                "current_direction": -1,
            }})
            # 1) Chạy qua trọn chu kỳ đầu tiên (1680 warning, 1800 start, 2280 end) + xác minh tất định
            o1, o2 = w.path("c1.jsonl"), w.path("c2.jsonl")
            for out in (o1, o2):
                code, err = run_headless("--mode", "gather", "--seed", "42", "--ticks", "2285",
                                         "--scenario", sc, "--snapshot-every", "1800", "--out", out)
                self.assertEqual(code, 0, err)
            with open(o1, "rb") as f1, open(o2, "rb") as f2:
                self.assertEqual(f1.read(), f2.read())
            rows = read_jsonl(o1)
            cur_evs = [e for e in events(rows) if e["name"].startswith("current_")]
            self.assertEqual(
                [(e["tick"], e["name"], e["data"]) for e in cur_evs],
                [
                    (1680, "current_warning", {"starts_at_phase_tick": 1800}),
                    (1800, "current_start", {"direction": -1, "duration_ticks": 480}),
                    (2280, "current_end", {"direction": -1, "reason": "elapsed"}),
                ],
            )
            snaps = {s["tick"]: s for s in snapshots(rows)}
            self.assertEqual(snaps[1800]["current"], {"direction": -1, "ticks_left": 480})

            # 2) Giới hạn CLI --ticks 1810 chỉ cắt mô phỏng, KHÔNG phát current_end
            o_cut = w.path("cut.jsonl")
            code, err = run_headless("--mode", "gather", "--seed", "42", "--ticks", "1810",
                                     "--scenario", sc, "--snapshot-every", "10000", "--out", o_cut)
            self.assertEqual(code, 0, err)
            cut_rows = read_jsonl(o_cut)
            self.assertEqual(events(cut_rows, "current_end"), [])
            self.assertEqual(snapshots(cut_rows)[-1]["current"], {"direction": -1, "ticks_left": 470})

    def test_invalid_current_scenario_exits_2(self):
        with Workdir() as w:
            for bad in ({"current_direction": 0}, {"current_direction": True}, {"random_current": "no"}):
                sc = write_json(w.path("bad.json"), {"gather": bad})
                code, _ = run_headless("--mode", "gather", "--seed", "1", "--ticks", "0",
                                       "--scenario", sc, "--out", w.path("out.jsonl"))
                self.assertEqual(code, 2, bad)


class SnakeExtensionTest(unittest.TestCase):
    def setUp(self):
        self.tuning = copy.deepcopy(load_contract()["tuning"])

    def test_m3_spawns_day1_patrols_and_chases_with_ran_rules(self):
        # M3 xuất hiện từ Ngày 1 ở [72, 14] <-> [76, 14], d in [8, 20]
        s = Session("gather", self.tuning, {"player": {"pos": [2, 0]}, "random_fish": False, "random_current": False}, 1)
        m3 = next(m for m in s.snapshot()["monsters"] if m["id"] == "M3")
        self.assertEqual(m3["kind"], "ran")
        self.assertEqual(m3["pos"], [72.0, 14.0])
        self.assertEqual(m3["waypoints"], [[72.0, 14.0], [76.0, 14.0]])

        # Người chơi ở d = 7.5 (< 8) cách 6.5m -> KHÔNG chase
        s_shallow = Session("gather", self.tuning, {
            "player": {"pos": [72, 7.5]},
            "monsters": [{"id": "M3", "kind": "ran", "pos": [72, 14], "waypoints": [[72, 14], [76, 14]]}],
            "random_fish": False, "random_current": False,
        }, 1)
        s_shallow.step(_idle())
        self.assertEqual(s_shallow.snapshot()["monsters"][0]["state"], "patrol")

        # Người chơi ở d = 8.0 cách 6.0m (<= 8m) -> CHASE với tốc độ 3.5 m/s
        s_chase = Session("gather", self.tuning, {
            "player": {"pos": [66, 8.0]},
            "monsters": [{"id": "M3", "kind": "ran", "pos": [72, 8.0], "waypoints": [[72, 14], [76, 14]]}],
            "random_fish": False, "random_current": False,
        }, 1)
        s_chase.step(_idle())
        m_chase = s_chase.snapshot()["monsters"][0]
        self.assertEqual(m_chase["state"], "chase")
        self.assertTrue(close(m_chase["pos"][0], 72.0 - 3.5 / 60.0, 1e-4), m_chase)

        # Cách > 16m -> rời chase về patrol
        s_exit = Session("gather", self.tuning, {
            "player": {"pos": [50, 14.0]},
            "monsters": [{"id": "M3", "kind": "ran", "pos": [72, 14.0], "waypoints": [[72, 14], [76, 14]], "state": "chase"}],
            "random_fish": False, "random_current": False,
        }, 1)
        s_exit.step(_idle())
        self.assertEqual(s_exit.snapshot()["monsters"][0]["state"], "patrol")


class BurnExtensionRealContractTest(unittest.TestCase):
    def test_burn_active_in_real_game_contract_via_headless(self):
        with Workdir() as w:
            # ready_ticks = 1199 -> sau bước 1 thành 1200 -> vẫn bưng được (dish_picked)
            sc_ok = write_json(w.path("ok.json"), {"quan": {
                "player": {"pos": [2, 8]},
                "stock": [],
                "random_customers": False,
                "customers": [{"id": "C1", "table_id": "T1", "dish_id": "ca_loc_nuong_trui", "order_status": "assigned"}],
                "stoves": [{"id": "B1", "state": "ready", "ready_ticks": 1199,
                            "dish": {"order_id": "C1", "dish_id": "ca_loc_nuong_trui", "base_price": 60}}],
            }})
            inp_e = write_json(w.path("inp.json"), {"frames": [{"tick": 0, "interact": True}]})
            code, err = run_headless("--mode", "quan", "--seed", "7", "--ticks", "1",
                                     "--scenario", sc_ok, "--inputs", inp_e, "--out", w.path("ok.jsonl"))
            self.assertEqual(code, 0, err)
            self.assertEqual([e["name"] for e in events(read_jsonl(w.path("ok.jsonl")))], ["dish_picked"])

            # ready_ticks = 1200 -> sau bước 1 thành 1201 (> 1200) -> cháy món, giữ lại được nếu kho còn hàng chưa ươn
            sc_burn = write_json(w.path("burn.json"), {"quan": {
                "player": {"pos": [2, 8]},
                "stock": [{"id": "I1", "kind": "ca_loc", "fresh": 100}],
                "random_customers": False,
                "customers": [{"id": "C1", "table_id": "T1", "dish_id": "ca_loc_nuong_trui", "order_status": "assigned"}],
                "stoves": [{"id": "B1", "state": "ready", "ready_ticks": 1200,
                            "dish": {"order_id": "C1", "dish_id": "ca_loc_nuong_trui", "base_price": 60}}],
            }})
            code, err = run_headless("--mode", "quan", "--seed", "7", "--ticks", "1",
                                     "--scenario", sc_burn, "--inputs", inp_e, "--out", w.path("burn.jsonl"))
            self.assertEqual(code, 0, err)
            evs = events(read_jsonl(w.path("burn.jsonl")))
            self.assertEqual([e["name"] for e in evs], ["dish_burnt", "cook_started"])
            self.assertEqual(evs[0]["data"]["order_status"], "reserved")


if __name__ == "__main__":
    unittest.main()
