"""PRD-0 D/E/F, lát 4: kiểm hành vi biên và tiền qua cùng Session/headless."""

import copy
import subprocess
import sys
import unittest
from pathlib import Path

from chonoi.contract import load_contract
from chonoi.errors import BadInput
from chonoi.inputs import InputPlayer, InputState
from chonoi.runner import Session

from helpers import Workdir, events, read_jsonl, write_json

ROOT = Path(__file__).resolve().parents[1]
DISH = "ca_loc_nuong_trui"


def customer(ident="C1", table="T1", **updates):
    return {"id": ident, "table_id": table, "dish_id": DISH, **updates}


def payload(order="C1", dish=DISH, price=60):
    return {"order_id": order, "dish_id": dish, "base_price": price}


class Service(unittest.TestCase):
    def setUp(self):
        self.tuning = copy.deepcopy(load_contract()["tuning"])
        self.tuning.pop("freshness", None)

    def session(self, scenario=None):
        block = {"random_customers": False, "stock": {"ca_loc": 1},
                 "player": {"pos": [2, 8]}, "customers": [customer()]}
        block.update(scenario or {})
        return Session("quan", self.tuning, block, 7)

    def step(self, sess, press=False, move=(0, 0)):
        return sess.step(InputState(move, {}, {"interact"} if press else set()))

    def carrying(self, patience=3600, **updates):
        block = {"stock": {}, "hand": payload(), "player": {"pos": [9, 2]},
                 "customers": [customer(order_status="assigned", patience_ticks_left=patience)]}
        block.update(updates)
        return self.session(block)

    def test_cook_pick_serve_pay_and_score_at_exact_ticks(self):
        s = self.session()
        rows = self.step(s, True)
        self.assertEqual(rows[0]["data"], {"stove_id": "B1", "order_id": "C1", "dish_id": DISH,
                                          "items": ["ca_loc"], "base_price": 60})
        self.assertEqual(s.sim.stock["ca_loc"], 0)
        self.assertEqual(s.sim.customers[0]["reserved"], {})
        self.assertEqual(s.sim.customers[0]["order_status"], "assigned")
        for _ in range(359):
            self.assertEqual(self.step(s), [])
        rows = self.step(s, True)
        self.assertEqual([(r["tick"], r["name"]) for r in rows], [(361, "dish_ready"), (361, "dish_picked")])
        self.assertEqual(s.sim.hand, payload())
        self.assertEqual(s.sim.stoves[0]["state"], "idle")
        s.sim.pos = [9, 2]
        self.assertEqual(self.step(s, True)[0]["name"], "served")
        self.assertEqual(s.sim.customers[0]["eat_ticks_left"], 600)
        self.assertEqual(s.sim.money, 0, "thu tiền sau khi ăn")
        for _ in range(599):
            self.assertEqual(self.step(s), [])
        paid = self.step(s)[0]
        self.assertEqual(paid["data"], {"order_id": "C1", "table_id": "T1", "base_price": 60,
                                         "tip": 12, "amount": 72, "reason": "finished_eating"})
        self.assertEqual((s.sim.money, s.sim.earned, s.sim.shift_earned), (72, 72, 72))
        self.assertAlmostEqual(s.sim.reputation, 3.2)
        self.assertEqual(s.snapshot()["score"], 372)
        self.assertEqual(s.snapshot()["tables"][0]["customer_id"], None)
        self.assertEqual(self.step(s), [], "không trả tiền hai lần")

    def test_ready_age_starts_on_next_tick_and_does_not_burn(self):
        s = self.session({"customers": [customer(order_status="assigned")], "stock": {},
                          "stoves": [{"id": "B1", "state": "cooking", "dish": payload(), "cook_ticks_left": 1}]})
        self.assertEqual(self.step(s)[0]["name"], "dish_ready")
        self.assertEqual(s.sim.stoves[0]["ready_ticks"], 0)
        for _ in range(10):
            self.step(s)
        self.assertEqual(s.sim.stoves[0]["ready_ticks"], 10)
        self.assertEqual(s.sim.stoves[0]["state"], "ready")

    def test_holding_interact_does_not_repeat(self):
        s = self.session()
        player = InputPlayer([{"tick": 0, "interact": True}])
        rows = []
        for tick in range(362):
            rows.extend(s.step(player.advance(tick)))
        self.assertEqual([r["name"] for r in rows], ["cook_started", "dish_ready"])
        self.assertIsNone(s.sim.hand)

    def test_target_priority_stove_before_table_and_no_fallback(self):
        s = self.carrying(player={"pos": [8, 2]}, stoves=[{"id": "B1", "pos": [7, 2]}])
        self.assertEqual(self.step(s, True), [])
        self.assertIsNotNone(s.sim.hand, "bếp idle không có đơn reserved; không fallback sang bàn")

    def test_nearer_table_wins_over_stove(self):
        s = self.carrying(player={"pos": [8, 2]}, stoves=[{"id": "B1", "pos": [6.5, 2]}])
        self.assertEqual(self.step(s, True)[0]["name"], "served")

    def test_target_tie_uses_natural_id_and_only_one_action(self):
        self.tuning["quan"]["stoves"] = [{"id": "B10", "pos": [2, 8]}, {"id": "B2", "pos": [2, 8]}]
        s = self.session()
        rows = self.step(s, True)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["data"]["stove_id"], "B2")

    def test_exact_radius_and_outside(self):
        # Đứng phía trái B1 [2,8] để không rơi vào bán kính bếp B2 [5,8] (v1.1)
        for distance, expected in ((1.5, ["cook_started"]), (1.500001, [])):
            with self.subTest(distance=distance):
                s = self.session({"player": {"pos": [2 - distance, 8]}})
                self.assertEqual([r["name"] for r in self.step(s, True)], expected)

    def test_movement_happens_before_interaction(self):
        self.tuning["quan"]["ramp_max_ticks"] = 0
        s = self.session({"player": {"pos": [3.55, 8]}})
        self.assertEqual(self.step(s, True, (-1, 0))[0]["name"], "cook_started")

    def test_oldest_order_then_table_id_not_customer_id(self):
        self.tuning["quan"]["tables"] = [{"id": "T10", "pos": [9, 2]}, {"id": "T2", "pos": [10, 2]}]
        for ticks, expected in (((0, 1), "C1"), ((1, 0), "C10"), ((0, 0), "C10")):
            with self.subTest(ticks=ticks):
                s = self.session({"stock": {"ca_loc": 2}, "customers": [
                    customer("C1", "T10", order_tick=ticks[0]), customer("C10", "T2", order_tick=ticks[1])]})
                self.assertEqual(self.step(s, True)[0]["data"]["order_id"], expected)

    def test_cook_items_sorted_and_only_reserved_quantities_consumed(self):
        s = self.session({"stock": {"ca_linh": 6, "bong_dien_dien": 2},
                          "customers": [customer(dish_id="lau_ca_linh_dien_dien")]})
        data = self.step(s, True)[0]["data"]
        self.assertEqual(data["items"], ["bong_dien_dien", "ca_linh", "ca_linh", "ca_linh"])
        self.assertEqual(s.snapshot()["stock"], {"bong_dien_dien": 1, "ca_linh": 3})

    def test_idle_stove_can_cook_while_hand_is_full(self):
        self.tuning["quan"]["tables"].append({"id": "T2", "pos": [10, 2]})
        s = self.carrying(player={"pos": [2, 8]}, stock={"ca_loc": 1}, customers=[
            customer(order_status="assigned"), customer("C2", "T2")])
        self.assertEqual(self.step(s, True)[0]["data"]["order_id"], "C2")
        self.assertEqual(s.sim.hand, payload())

    def test_full_hand_cannot_pick_another_dish(self):
        self.tuning["quan"]["tables"].append({"id": "T2", "pos": [10, 2]})
        s = self.carrying(player={"pos": [2, 8]}, customers=[customer(order_status="assigned"),
            customer("C2", "T2", order_status="assigned")],
            stoves=[{"id": "B1", "state": "ready", "dish": payload("C2")}])
        self.assertEqual(self.step(s, True), [])
        self.assertEqual(s.sim.hand, payload())
        self.assertEqual(s.sim.stoves[0]["dish"], payload("C2"))

    def test_correct_dish_for_wrong_order_is_not_served(self):
        self.tuning["quan"]["tables"].append({"id": "T2", "pos": [15, 2]})
        s = self.session({"stock": {"ca_loc": 1}, "player": {"pos": [9, 2]}, "hand": payload("C2"),
                          "customers": [customer(), customer("C2", "T2", order_status="assigned")]})
        self.assertEqual(self.step(s, True), [])
        self.assertEqual(s.sim.customers[0]["state"], "waiting")

    def test_tip_threshold_after_countdown_and_floor(self):
        self.tuning["quan"]["tip_rate"] = 0.29
        for before, tip in ((1801, 17), (1800, 0)):
            with self.subTest(before=before):
                s = self.carrying(before)
                data = self.step(s, True)[0]["data"]
                self.assertEqual(data["tip"], tip)
                self.assertEqual(data["patience_ticks_left"], before - 1)

    def test_tip_decimal_floor_is_not_reduced_by_binary_float(self):
        self.tuning["quan"]["tip_rate"] = 0.29
        s = self.carrying(hand=payload(price=100))
        self.assertEqual(self.step(s, True)[0]["data"]["tip"], 29)

    def test_can_serve_exact_patience_deadline(self):
        s = self.carrying(1)
        rows = self.step(s, True)
        self.assertEqual([r["name"] for r in rows], ["served"])
        self.assertEqual(rows[0]["data"]["tip"], 0)
        self.assertEqual(s.sim.customers[0]["state"], "eating")

    def test_tip_is_frozen_at_service_and_reputation_changes_only_at_payment(self):
        s = self.carrying(1801, reputation=4.9)
        self.step(s, True)
        self.assertEqual(s.sim.customers[0]["tip"], 12)
        self.assertEqual(s.sim.reputation, 4.9)
        s.sim.time_left_ticks = 1
        self.step(s)
        self.assertEqual(s.sim.money, 72)
        self.assertEqual(s.sim.reputation, 5)

    def test_no_tip_payment_does_not_add_reputation(self):
        s = self.carrying(2)
        self.step(s, True)
        s.sim.time_left_ticks = 1
        self.step(s)
        self.assertEqual(s.sim.money, 60)
        self.assertEqual(s.sim.reputation, 3)

    def test_closing_serves_then_pays_immediately_then_ends_once(self):
        s = self.carrying(time_left_ticks=1)
        rows = self.step(s, True)
        self.assertEqual([r["name"] for r in rows], ["served", "paid", "quan_end"])
        self.assertEqual(rows[1]["data"]["reason"], "closing")
        self.assertEqual(rows[2]["data"], {"reason": "time", "money": 72, "earned": 72,
                                          "shift_earned": 72, "reputation": 3.2})
        self.assertTrue(s.done)
        self.assertEqual(self.step(s, True), [])
        self.assertEqual(s.sim.money, 72)

    def test_natural_eating_completion_at_closing_has_finished_reason(self):
        s = self.session({"stock": {}, "time_left_ticks": 1, "customers": [customer(
            state="eating", order_status="served", eat_ticks_left=1, base_price=60, tip=12)]})
        self.assertEqual(self.step(s)[0]["data"]["reason"], "finished_eating")

    def test_departure_cleans_cooking_ready_or_hand_without_refund(self):
        for location in ("cooking", "ready", "hand"):
            with self.subTest(location=location):
                block = {"stock": {}, "customers": [customer(order_status="assigned", patience_ticks_left=1)]}
                if location == "hand":
                    block["hand"] = payload()
                else:
                    block["stoves"] = [{"id": "B1", "state": location, "dish": payload(),
                                         "cook_ticks_left": 2 if location == "cooking" else 0}]
                s = self.session(block)
                self.assertEqual(self.step(s)[0]["data"]["reason"], "patience")
                self.assertEqual(s.sim.customers, [])
                self.assertIsNone(s.sim.hand)
                self.assertEqual(s.sim.stoves[0]["state"], "idle")
                self.assertEqual(s.sim.stock, {})
                self.assertEqual(s.sim.reputation, 2.5)

    def test_waiting_departure_at_closing_releases_raw_stock_without_penalty(self):
        s = self.session({"time_left_ticks": 1, "customers": [customer(patience_ticks_left=1)]})
        self.assertEqual([r["name"] for r in self.step(s)], ["customer_left", "quan_end"])
        self.assertEqual(s.sim.stock, {"ca_loc": 1})
        self.assertEqual(s.sim.reputation, 3)

    def test_customer_settlement_order_is_table_id(self):
        self.tuning["quan"]["tables"] = [{"id": "T10", "pos": [9, 2]}, {"id": "T2", "pos": [10, 2]}]
        s = self.session({"stock": {}, "time_left_ticks": 1, "customers": [
            customer("C1", "T10", state="eating", order_status="served", eat_ticks_left=2, base_price=60, tip=0),
            customer("C10", "T2", order_status="unfulfillable")]})
        self.assertEqual([(r["name"], r["data"].get("table_id")) for r in self.step(s)],
                         [("customer_left", "T2"), ("paid", "T10"), ("quan_end", None)])

    def test_patience_penalty_clamps_reputation(self):
        s = self.session({"reputation": 0.1, "customers": [customer(patience_ticks_left=1)]})
        self.step(s)
        self.assertEqual(s.sim.reputation, 0)

    def test_fixture_is_not_mutated_and_can_restart(self):
        scenario = {"stock": {"ca_loc": 1}, "customers": [customer()], "player": {"pos": [2, 8]}}
        original = copy.deepcopy(scenario)
        s = self.session(scenario)
        self.step(s, True)
        self.assertEqual(scenario, original)
        self.assertEqual(self.session(scenario).snapshot()["customers"][0]["reserved"], {"ca_loc": 1})

    def test_contradictory_service_fixtures_are_rejected(self):
        cases = [
            {"hand": "ca_loc_nuong_trui"},
            {"hand": payload("C9")},
            {"customers": [customer(order_status="assigned")]},
            {"customers": [customer(reserved={"ca_loc": 2})]},
            {"stock": {}},
            {"customers": [customer(state="eating", order_status="served", eat_ticks_left=1)]},
            {"stoves": [{"id": "B1", "state": "cooking", "dish": payload(), "cook_ticks_left": 0}]},
            {"customers": [customer(order_status="assigned")], "hand": payload(),
             "stoves": [{"id": "B1", "state": "ready", "dish": payload()}]},
            {"customers": [customer(order_status="assigned")], "hand": payload(dish="goi_bong_sung")},
        ]
        for block in cases:
            with self.subTest(block=block), self.assertRaises(BadInput):
                self.session(block)


class HeadlessService(unittest.TestCase):
    def run_cli(self, *args):
        return subprocess.run([sys.executable, "-m", "chonoi.headless", *args], cwd=ROOT, capture_output=True)

    def test_real_headless_service_flow_is_byte_deterministic(self):
        proof = ROOT / "docs" / "proof" / "phase-1"
        with Workdir() as w:
            sc_v12 = write_json(w.path("sc-v12.json"), {"quan": {
                "player": {"pos": [2, 8]},
                "stock": [{"id": "I1", "kind": "ca_loc", "fresh": 100}],
                "customers": [{"id": "C1", "table_id": "T1", "dish_id": "ca_loc_nuong_trui"}],
                "random_customers": False,
                "time_left_ticks": 1171,
            }})
            outputs = []
            for i in range(2):
                out = w.path(f"service-{i}.jsonl")
                result = self.run_cli("--mode", "quan", "--seed", "7", "--ticks", "1200",
                    "--scenario", sc_v12,
                    "--inputs", str(proof / "chur04-service-inputs.json"), "--snapshot-every", "360", "--out", out)
                self.assertEqual(result.returncode, 0, result.stderr)
                outputs.append(Path(out).read_bytes())
            self.assertEqual(*outputs)
            rows = read_jsonl(w.path("service-0.jsonl"))
            self.assertEqual([(r["tick"], r["name"]) for r in events(rows)], [
                (1, "cook_started"), (361, "dish_ready"), (361, "dish_picked"),
                (571, "served"), (1171, "paid"), (1171, "quan_end")])
            # v1.2: ở tick 1 I1 hao 1/240 -> base_price = floor(60 * (100 - 1/240)/100) = 59, tip = floor(59*0.2) = 11 -> 70
            self.assertEqual((rows[-1]["money"], rows[-1]["score"], rows[-1]["reason"]), (70, 370, "time"))

    def test_bad_payload_exits_2_before_output_is_written(self):
        with Workdir() as w:
            scenario = write_json(w.path("bad.json"), {"quan": {"hand": payload("C9")}})
            out = w.path("out.jsonl")
            Path(out).write_text("unchanged", encoding="utf-8")
            result = self.run_cli("--mode", "quan", "--seed", "1", "--ticks", "0", "--scenario", scenario, "--out", out)
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertEqual(Path(out).read_text(encoding="utf-8"), "unchanged")


if __name__ == "__main__":
    unittest.main()
