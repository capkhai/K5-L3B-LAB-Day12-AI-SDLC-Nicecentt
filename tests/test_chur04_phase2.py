"""Ticket-02: kiểm lát day/Shop/pause/quán độc lập với cá/quái đang tích hợp."""

import copy
import json
import pathlib
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

from chonoi.contract import load_contract
from chonoi.errors import BadInput
from chonoi.inputs import BUTTONS_V11, InputPlayer, InputState, LiveInputs, load_frames
from chonoi.runner import Session, run
from chonoi.sim.day_config import plans
from chonoi.sim.quan_customers import cookable_dishes
from helpers import Workdir, read_jsonl, write_json

ROOT = pathlib.Path(__file__).resolve().parents[1]


def phase2_contract():
    contract = copy.deepcopy(load_contract())
    overlay = json.loads((ROOT / "tests/fixtures/phase2-day-data.json").read_text(encoding="utf-8"))
    for key, data in overlay.items():
        if key in ("gather", "quan"):
            contract["tuning"][key].update(data)
        else:
            contract["tuning"][key] = data
    contract["contract_version"] = "1.1"
    contract["tuning"].pop("freshness", None)
    return contract


def inp(*edges, buy=None):
    return InputState((0, 0), {}, set(edges), buy=buy)


def quick_scenario(**state):
    return {"day": state, "gather": {"random_fish": False, "time_left_ticks": 1},
            "quan": {"random_customers": False, "time_left_ticks": 1}}


class Inputs11(unittest.TestCase):
    def test_buy_is_per_frame_and_buttons_keep_edges_across_phases(self):
        player = InputPlayer([{"tick": 0, "interact": True, "buy": "oxygen"},
                              {"tick": 2, "shop_done": True}, {"tick": 3, "shop_done": False}])
        self.assertTrue(player.advance(0).pressed("interact"))
        self.assertIsNone(player.advance(1).buy)
        self.assertFalse(player.advance(2).pressed("interact"))
        self.assertFalse(player.advance(3).pressed("shop_done"))

    def test_v11_loader_accepts_new_buttons_and_rejects_bad_types(self):
        with Workdir() as w:
            valid = {"tick": 0, "pause": True, "shop_done": False, "attack": True, "photo": True, "buy": "hp"}
            path = write_json(w.path("inputs.json"), {"frames": [valid]})
            self.assertEqual(load_frames(path, BUTTONS_V11), [valid])
            for change in ({"buy": ""}, {"buy": 1}, {"pause": 1}, {"photo": None}, {"unknown": True}):
                with self.subTest(change=change), self.assertRaises(BadInput):
                    load_frames(write_json(path, {"frames": [{**valid, **change}]}), BUTTONS_V11)

    def test_live_buy_is_consumed_once(self):
        live = LiveInputs()
        live.set(pause=True, buy="oxygen")
        first = live.advance()
        self.assertTrue(first.pressed("pause"))
        self.assertEqual(first.buy, "oxygen")
        self.assertIsNone(live.advance().buy)


class DayAndShop(unittest.TestCase):
    def setUp(self):
        self.tuning = phase2_contract()["tuning"]

    def session(self, scenario=None, days=1):
        return Session("day", self.tuning, quick_scenario() if scenario is None else scenario, 7, days=days)

    def shop(self, **state):
        sess = self.session(quick_scenario(**state), days=2)
        sess.step(inp())
        sess.step(inp())
        self.assertEqual(sess.sim.phase, "shop")
        return sess

    def test_initial_events_and_plan(self):
        sess = self.session()
        self.assertEqual([e["name"] for e in sess.initial_events()], ["day_start", "day_plan", "phase_start"])
        self.assertTrue(all(e["tick"] == 0 and e["day"] == 1 and e["phase"] == "gather" for e in sess.initial_events()))
        snap = sess.snapshot()
        self.assertEqual(snap["phase_tick"], 0)
        self.assertEqual(snap["day_plan"]["ingredients"], {"ca_loc": 3, "bong_sung": 6})

    def test_phase_events_keep_old_context_and_new_snapshot_has_zero_phase_tick(self):
        sess = self.session()
        rows = sess.step(inp())
        self.assertEqual([(e["name"], e["phase"]) for e in rows], [("gather_end", "gather"), ("phase_start", "quan")])
        self.assertEqual((sess.snapshot()["phase"], sess.snapshot()["phase_tick"], sess.snapshot()["time_left_ticks"]), ("quan", 0, 1))
        self.assertEqual(sess.phase_tick, 0)
        self.assertEqual([e["name"] for e in sess.step(inp())], ["quan_end", "phase_start"])
        self.assertEqual(sess.snapshot()["time_left_ticks"], 600)
        self.assertEqual(sess.snapshot()["phase_tick"], 0)

    def test_inventory_handoff_and_surplus_outside_plan(self):
        scenario = quick_scenario()
        scenario["gather"]["hold"] = ["ca_loc", "ca_keo", "keo_neo", "bong_sung", "bong_sung"]
        sess = self.session(scenario)
        sess.step(inp())
        self.assertEqual(sess.snapshot()["stock"], {"ca_loc": 1, "ca_keo": 1, "keo_neo": 1, "bong_sung": 2})
        self.assertEqual(set(sess.sim.current.menu), {"ca_loc_nuong_trui", "goi_bong_sung"})

    def test_faint_still_starts_quan_with_empty_inventory(self):
        scenario = quick_scenario()
        scenario["gather"].update(hold=["ca_loc"], player={"pos": [20, 5], "hp": 1,
            "oxygen_ticks": 0, "zero_oxy_ticks": 59})
        sess = self.session(scenario)
        rows = sess.step(inp())
        self.assertEqual([e["name"] for e in rows], ["choke", "faint", "gather_end", "phase_start"])
        self.assertEqual(sess.snapshot()["stock"], {})
        self.assertEqual(sess.snapshot()["phase"], "quan")

    def test_plans_d1_to_d5_recompute_ingredients(self):
        resolved = plans(self.tuning)
        self.assertEqual(set(resolved), {1, 2, 3, 4, 5})
        self.assertEqual(resolved[5]["ingredients"], {"ca_linh": 5, "ca_keo": 1, "keo_neo": 1, "bong_dien_dien": 2, "ca_loc": 1})
        override = [{"day": 1, "dishes": {"lau_mam": 2}}]
        self.assertEqual(plans(self.tuning, override)[1]["ingredients"]["ca_keo"], 2)

    def test_invalid_scenarios_fail_before_simulation(self):
        bad_states = [{"money": 1}, {"earned": 1}, {"money": 2, "earned": 1},
                      {"money": True, "earned": 2}, {"reputation": float("nan")},
                      {"upgrades": {"hp": 3}}, {"upgrades": {"bad": 0}},
                      {"day_plan": None}, {"day_plan": [{"day": 1, "dishes": {"bad": 1}}]},
                      {"day_plan": [{"day": 1, "dishes": {"ca_loc_nuong_trui": 1}, "ingredients": {"ca_loc": 2}}]},
                      {"day_plan": [{"day": 1, "dishes": {"ca_loc_nuong_trui": 1}}] * 2}]
        for state in bad_states:
            with self.subTest(state=state), self.assertRaises(BadInput):
                self.session(quick_scenario(**state))
        for key in ("stock", "reputation"):
            scenario = quick_scenario()
            scenario["quan"][key] = {} if key == "stock" else 3
            with self.subTest(key=key), self.assertRaises(BadInput):
                self.session(scenario)

    def test_buy_exact_funds_and_active_upgrade_only_next_day(self):
        sess = self.shop(money=200, earned=200)
        score = sess.snapshot()["score"]
        rows = sess.step(inp(buy="oxygen"))
        self.assertEqual(rows[0]["data"], {"upgrade": "oxygen", "level": 1, "price": 200, "money": 0})
        self.assertEqual(sess.snapshot()["upgrades"], {"oxygen": 1})
        self.assertEqual(sess.snapshot()["active_upgrades"], {})
        self.assertEqual(sess.snapshot()["score"], score)
        rows = sess.step(inp("shop_done"))
        self.assertEqual([(e["name"], e["day"], e["phase"]) for e in rows], [
            ("shop_end", 1, "shop"), ("day_start", 2, "gather"), ("day_plan", 2, "gather"), ("phase_start", 2, "gather")])
        self.assertEqual(sess.snapshot()["player"]["oxygen_max_ticks"], 2700)
        self.assertEqual(sess.snapshot()["player"]["oxygen_ticks"], 2700)
        self.assertEqual(sess.snapshot()["active_upgrades"], {"oxygen": 1})
        self.assertEqual(sess.snapshot()["earned"], 200)

    def test_hp_full_on_new_day_and_day_context_passed_to_gather(self):
        sess = self.shop(money=250, earned=250)
        sess.step(inp("shop_done", buy="hp"))
        self.assertEqual((sess.sim.current.day, sess.snapshot()["player"]["hp"], sess.snapshot()["player"]["hp_max"]), (2, 4, 4))

    def test_initial_max_upgrades_apply_and_fixture_honors_them(self):
        scenario = quick_scenario(upgrades={"oxygen": 2, "hp": 2})
        scenario["gather"]["player"] = {"hp": 5, "oxygen_ticks": 3600}
        sess = self.session(scenario)
        self.assertEqual((sess.snapshot()["player"]["hp_max"], sess.snapshot()["player"]["oxygen_max_ticks"]), (5, 3600))

    def test_buy_failed_funds_max_and_unknown_preserve_state(self):
        cases = [({}, "hp", "funds"), ({"upgrades": {"hp": 2}}, "hp", "max_level"), ({}, "banana", "unknown")]
        for state, action, reason in cases:
            with self.subTest(action=action):
                sess = self.shop(**state)
                before = sess.snapshot()
                rows = sess.step(inp(buy=action))
                self.assertEqual(rows[0]["data"], {"action": action, "reason": reason})
                self.assertEqual(sess.snapshot()["money"], before["money"])
                self.assertEqual(sess.snapshot()["upgrades"], before["upgrades"])

    def test_levels_are_bought_in_order(self):
        sess = self.shop(money=600, earned=600)
        self.assertEqual(sess.step(inp(buy="oxygen"))[0]["data"]["price"], 200)
        self.assertEqual(sess.step(inp(buy="oxygen"))[0]["data"]["price"], 400)
        self.assertEqual(sess.sim.upgrades, {"oxygen": 2})
        self.assertEqual(sess.step(inp(buy="oxygen"))[0]["data"]["reason"], "max_level")

    def test_buy_before_done_even_at_shop_deadline(self):
        sess = self.shop(money=200, earned=200)
        for _ in range(599):
            sess.step(inp())
        rows = sess.step(inp("shop_done", buy="oxygen"))
        self.assertEqual([e["name"] for e in rows], ["bought", "shop_end", "day_start", "day_plan", "phase_start"])
        self.assertEqual(rows[1]["data"], {"reason": "done"})
        self.assertEqual(sess.sim.days_completed, 1)

    def test_last_day_is_not_complete_until_shop_closes(self):
        sess = self.session()
        sess.step(inp())
        sess.step(inp())
        self.assertFalse(sess.done)
        for _ in range(600):
            rows = sess.step(inp())
        self.assertEqual(rows[0]["data"], {"reason": "time"})
        self.assertEqual(sess.end_row()["reason"], "days_complete")
        self.assertEqual(sess.end_row()["days_completed"], 1)
        self.assertEqual(sess.end_row()["sim_tick"], 602)

    def test_surplus_is_visible_in_shop_then_discarded_next_day(self):
        scenario = quick_scenario()
        scenario["gather"]["hold"] = ["ca_loc"]
        sess = self.session(scenario, days=2)
        sess.step(inp())
        sess.step(inp())
        self.assertEqual(sess.snapshot()["stock"], {"ca_loc": 1})
        sess.step(inp("shop_done"))
        self.assertEqual(sess.snapshot()["hold"], ["ca_loc"], "fixture được áp lại mỗi Ngày")
        self.assertEqual(sess.sim.stock, {}, "kho dư cũ đã bỏ")

    def test_revenue_and_reputation_persist_across_all_phases(self):
        scenario = quick_scenario(money=200, earned=300, reputation=4)
        scenario["quan"]["customers"] = [{"id": "C1", "table_id": "T1", "dish_id": "ca_loc_nuong_trui",
            "state": "eating", "order_status": "served", "eat_ticks_left": 2, "base_price": 60, "tip": 12}]
        sess = self.session(scenario, days=2)
        sess.step(inp())
        sess.step(inp())
        self.assertEqual((sess.sim.money, sess.sim.earned, sess.sim.reputation), (272, 372, 4.2))
        sess.step(inp("shop_done", buy="oxygen"))
        self.assertEqual((sess.snapshot()["money"], sess.snapshot()["earned"], sess.snapshot()["reputation"]), (72, 372, 4.2))

    def test_five_days_finish_only_after_five_shops(self):
        sess = self.session(days=5)
        starts = []
        for _ in range(15):
            starts.extend(sess.step(inp("shop_done")))
        self.assertTrue(sess.done)
        self.assertEqual(sess.end_row()["days_completed"], 5)
        self.assertEqual([e["day"] for e in starts if e["name"] == "day_start"], [2, 3, 4, 5])

    def test_actions_on_previous_phase_do_not_run_new_phase_same_tick(self):
        sess = self.session()
        sess.step(inp("shop_done", buy="hp"))
        sess.step(inp("shop_done", buy="hp"))
        self.assertEqual(sess.snapshot()["phase"], "shop")
        self.assertEqual(sess.snapshot()["time_left_ticks"], 600)
        self.assertFalse(sess.done)

    def test_paused_shop_ignores_buy_done_and_freezes_timers(self):
        sess = self.shop(money=200, earned=200)
        start = sess.snapshot()
        rows = sess.step(inp("pause", "shop_done", buy="oxygen"))
        self.assertEqual([r["name"] for r in rows], ["paused"])
        sess.step(inp("shop_done", buy="oxygen"))
        snap = sess.snapshot()
        self.assertEqual(snap["time_left_ticks"], start["time_left_ticks"])
        self.assertEqual(snap["sim_tick"], start["sim_tick"])
        self.assertEqual(snap["phase_tick"], 0)
        self.assertEqual(snap["money"], 200)
        self.assertEqual(snap["state"], "paused")
        rows = sess.step(inp("pause", buy="oxygen"))
        self.assertEqual([r["name"] for r in rows], ["resumed", "bought"])
        self.assertEqual(sess.snapshot()["phase_tick"], 1)

    def test_pause_consumes_edges_so_held_actions_do_not_reappear(self):
        sess = self.session()
        player = InputPlayer([{"tick": 0, "pause": True, "interact": True}, {"tick": 1, "pause": False},
                              {"tick": 2, "pause": True}, {"tick": 3, "pause": False}])
        self.assertEqual([e["name"] for e in sess.step(player.advance(0))], ["paused"])
        sess.step(player.advance(1))
        rows = sess.step(player.advance(2))
        self.assertEqual(rows[0]["name"], "resumed")
        end = next(e for e in rows if e["name"] == "gather_end")
        self.assertEqual(end["data"]["reason"], "time", "interact giữ true không có cạnh mới để cập bến")

    def test_pause_in_gather_and_quan_does_not_move_or_count_customer_schedule(self):
        for mode in ("gather", "quan"):
            with self.subTest(mode=mode):
                scenario = {"random_fish": False} if mode == "gather" else {"stock": {"ca_loc": 1}}
                sess = Session(mode, self.tuning, scenario, 1)
                before = copy.deepcopy(sess.snapshot())
                sess.step(InputState((1, 0), {}, {"pause", "interact"}))
                for _ in range(130):
                    sess.step(inp())
                snap = sess.snapshot()
                self.assertEqual(snap["player"], before["player"])
                self.assertEqual(snap["time_left_ticks"], before["time_left_ticks"])
                self.assertEqual((snap["sim_tick"], snap["phase_tick"]), (0, 0))
                self.assertEqual(sess.step(inp("pause"))[0]["name"], "resumed")
                self.assertEqual(sess.snapshot()["sim_tick"], 1)

    def test_pause_freezes_cooking_eating_and_patience_at_their_deadlines(self):
        sess = Session("quan", self.tuning, {"random_customers": False, "stock": {"ca_loc": 1},
            "customers": [
                {"id": "C1", "table_id": "T1", "dish_id": "ca_loc_nuong_trui", "order_status": "assigned"},
                {"id": "C2", "table_id": "T2", "dish_id": "ca_loc_nuong_trui", "order_status": "served",
                 "state": "eating", "eat_ticks_left": 1, "base_price": 60, "tip": 12},
                {"id": "C3", "table_id": "T3", "dish_id": "ca_loc_nuong_trui", "patience_ticks_left": 1}],
            "stoves": [{"id": "B1", "state": "cooking", "cook_ticks_left": 1,
                "dish": {"order_id": "C1", "dish_id": "ca_loc_nuong_trui", "base_price": 60}}]}, 7)
        before = copy.deepcopy(sess.snapshot())
        self.assertEqual([r["name"] for r in sess.step(inp("pause"))], ["paused"])
        for _ in range(100):
            self.assertEqual(sess.step(inp()), [])
        after = sess.snapshot()
        for key in ("stoves", "customers", "time_left_ticks", "money", "reputation"):
            self.assertEqual(before[key], after[key])
        self.assertEqual([r["name"] for r in sess.step(inp("pause"))], ["resumed", "dish_ready", "paid", "customer_left"])

    def test_tick_limit_while_paused_reports_outer_tick_and_zero_gameplay_ticks(self):
        with Workdir() as w:
            path = w.path("paused.txt")
            run("day", self.tuning, quick_scenario(), 7, [{"tick": 0, "pause": True}], 5, path, 2)
            rows = read_jsonl(path)
            self.assertEqual(rows[-1]["ticks"], 5)
            self.assertEqual(rows[-1]["sim_tick"], 0)
            self.assertEqual(rows[-1]["state"], "paused")
            self.assertEqual(rows[-1]["reason"], "tick_limit")
            self.assertEqual(rows[-1]["days_completed"], 0)

    def test_invalid_quan_fixture_is_checked_on_actual_evening_stock(self):
        scenario = quick_scenario()
        scenario["quan"]["customers"] = [{"id": "C1", "table_id": "T1", "dish_id": "ca_loc_nuong_trui"}]
        sess = self.session(scenario)
        with self.assertRaises(BadInput):
            sess.step(inp())

    def test_one_full_day_completes_at_22200_ticks_within_20_seconds(self):
        scenario = {"gather": {"random_fish": False}, "quan": {"random_customers": False}}
        sess = self.session(scenario)
        started = time.perf_counter()
        for _ in range(22200):
            sess.step(inp())
        elapsed = time.perf_counter() - started
        self.assertTrue(sess.done)
        self.assertEqual(sess.end_row()["sim_tick"], 22200)
        self.assertLess(elapsed, 20)


class Quan11(unittest.TestCase):
    def setUp(self):
        self.tuning = phase2_contract()["tuning"]

    def test_four_tables_choose_smallest_free_id_and_reserve_correctly(self):
        sess = Session("quan", self.tuning, {"stock": {"ca_loc": 20}}, 7)
        events = []
        for _ in range(2820):
            events.extend(sess.step(inp()))
        arrivals = [e for e in events if e["name"] == "customer_arrived"]
        self.assertEqual([e["data"]["table_id"] for e in arrivals], ["T1", "T2", "T3", "T4"])
        self.assertEqual(set(arrivals[0]["data"]), {"order_id", "table_id", "dish_id"})
        self.assertEqual(len(sess.snapshot()["stoves"]), 2)
        self.assertEqual(len(sess.snapshot()["tables"]), 4)

    def test_independent_quan_uses_six_recipes_and_day_does_not_limit_servings(self):
        stock = {"ca_loc": 20, "ca_linh": 20, "ca_keo": 20, "keo_neo": 20, "bong_dien_dien": 20, "bong_sung": 20}
        sess = Session("quan", self.tuning, {"stock": stock}, 7)
        self.assertEqual(len(cookable_dishes(sess.sim)), 6)
        scenario = quick_scenario(day_plan=[{"day": 1, "dishes": {"ca_loc_nuong_trui": 1}}])
        scenario["gather"]["hold"] = ["ca_loc"] * 4
        scenario["quan"] = {"time_left_ticks": 3000}
        day = Session("day", self.tuning, scenario, 7)
        day.step(inp())
        rows = []
        for _ in range(2820):
            rows.extend(day.step(inp()))
        arrivals = [r for r in rows if r["name"] == "customer_arrived"]
        self.assertEqual(len(arrivals), 4)
        self.assertTrue(all(r["data"]["dish_id"] == "ca_loc_nuong_trui" for r in arrivals))

    def burn_fixture(self, *, stock=0, age=1199):
        self.tuning["quan"]["burn_s"] = 20
        return Session("quan", self.tuning, {"player": {"pos": [2, 8]}, "stock": {"ca_loc": stock},
            "random_customers": False, "customers": [{"id": "C1", "table_id": "T1", "dish_id": "ca_loc_nuong_trui", "order_status": "assigned"}],
            "stoves": [{"id": "B1", "state": "ready", "ready_ticks": age,
                        "dish": {"order_id": "C1", "dish_id": "ca_loc_nuong_trui", "base_price": 60}}]}, 7)

    def test_burn_exact_1200_is_still_pickable(self):
        sess = self.burn_fixture()
        self.assertEqual([r["name"] for r in sess.step(inp("interact"))], ["dish_picked"])

    def test_burn_after_1200_releases_stove_and_keeps_waiting_without_refund(self):
        sess = self.burn_fixture(age=1200)
        rows = sess.step(inp("interact"))
        self.assertEqual([r["name"] for r in rows], ["dish_burnt"])
        self.assertEqual(rows[0]["data"]["order_status"], "unfulfillable")
        self.assertEqual(sess.sim.stoves[0]["state"], "idle")
        self.assertEqual(sess.sim.stock["ca_loc"], 0)
        self.assertEqual(sess.sim.customers[0]["state"], "waiting")

    def test_burn_reserves_again_then_same_tick_can_start_cooking(self):
        sess = self.burn_fixture(stock=1, age=1200)
        rows = sess.step(inp("interact"))
        self.assertEqual([r["name"] for r in rows], ["dish_burnt", "cook_started"])
        self.assertEqual(rows[0]["data"]["order_status"], "reserved")
        self.assertEqual(sess.sim.stock["ca_loc"], 0)


class HeadlessDay(unittest.TestCase):
    def test_real_cli_in_isolated_v11_workspace_is_deterministic(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = pathlib.Path(tmp)
            shutil.copytree(ROOT / "chonoi", work / "chonoi", ignore=shutil.ignore_patterns("__pycache__", "web"))
            contract = phase2_contract()
            write_json(work / "game.contract.json", contract)
            scenario = quick_scenario(money=200, earned=200)
            write_json(work / "scenario.json", scenario)
            write_json(work / "inputs.json", {"frames": [{"tick": 2, "buy": "oxygen", "shop_done": True},
                                                        {"tick": 3, "shop_done": False}, {"tick": 5, "shop_done": True}]})
            command = [sys.executable, "-m", "chonoi.headless", "--mode", "day", "--days", "2", "--seed", "7",
                       "--ticks", "20", "--scenario", "scenario.json", "--inputs", "inputs.json", "--snapshot-every", "10"]
            outputs = []
            for i in range(2):
                path = work / f"out-{i}.txt"
                result = subprocess.run([*command, "--out", str(path)], cwd=work, capture_output=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                outputs.append(path.read_bytes())
            self.assertEqual(*outputs)
            rows = read_jsonl(work / "out-0.txt")
            snaps = [r for r in rows if r["type"] == "snapshot"]
            self.assertEqual([(r["tick"], r["phase"], r["phase_tick"]) for r in snaps], [
                (0, "gather", 0), (1, "quan", 0), (2, "shop", 0), (3, "gather", 0), (4, "quan", 0), (5, "shop", 0), (6, "shop", 1)])
            self.assertEqual(rows[-1]["days_completed"], 2)
            self.assertEqual((rows[-1]["money"], rows[-1]["earned"], rows[-1]["reason"]), (0, 200, "days_complete"))

    def test_invalid_cli_flags_are_rejected_before_output(self):
        with Workdir() as w:
            for mode, extra in (("quan", ["--days", "1"]), ("day", ["--days", "0"]), ("day", ["--days", "6"]),
                                ("day", ["--inventory", "missing.json"]), ("day", ["--inventory-out", "missing.json"])):
                with self.subTest(mode=mode, extra=extra):
                    output = pathlib.Path(w.path("out.txt"))
                    result = subprocess.run([sys.executable, "-m", "chonoi.headless", "--mode", mode, "--seed", "1",
                        "--ticks", "0", "--out", str(output), *extra], cwd=ROOT, capture_output=True)
                    self.assertEqual(result.returncode, 2, result.stderr)
                    self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
