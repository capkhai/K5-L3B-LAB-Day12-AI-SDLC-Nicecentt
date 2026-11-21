"""Phase 3, lát 3: kho cá thể/độ tươi, giữ lại và giá chốt trong quán.

Giá trung bình fresh là giả định do người dùng cho phép, không phải trích PRD.
"""

import copy
import json
from pathlib import Path
import tempfile
import unittest

from chonoi.contract import load_contract
from chonoi.errors import BadInput
from chonoi.inputs import InputState
from chonoi.jsonl import dumps
from chonoi.runner import Session, run
from chonoi.scenario import validate_phase_block
from chonoi.sim.quan_customers import available_stock, cookable_dishes


def tuning():
    config = copy.deepcopy(load_contract()["tuning"])
    config["freshness"] = {"initial": 100, "gather_decay_per_s": 0.5, "quan_decay_per_s": 0.25, "spoiled_below": 30}
    config["quan"]["tables"] = [{"id": "T1", "pos": [9, 2]}, {"id": "T2", "pos": [13, 2]},
                                {"id": "T3", "pos": [9, 6]}, {"id": "T4", "pos": [13, 6]}]
    return config


def item(ident, kind="ca_loc", fresh=100):
    return {"id": ident, "kind": kind, "fresh": fresh}


def customer(ident="C1", table="T1", dish="ca_loc_nuong_trui", **updates):
    return {"id": ident, "table_id": table, "dish_id": dish, **updates}


def action(*edges):
    return InputState((0, 0), {}, set(edges))


class FreshQuan(unittest.TestCase):
    def setUp(self):
        self.tuning = tuning()

    def session(self, stock=None, customers=None, **updates):
        scenario = {"stock": [item("I1")] if stock is None else stock,
                    "customers": [customer()] if customers is None else customers,
                    "player": {"pos": [2, 8]}, "random_customers": False, **updates}
        return Session("quan", self.tuning, scenario, 7)

    def test_construct_keeps_ids_freshness_and_rotten_items_without_decay(self):
        stock = [item("I10", fresh=12), item("I2", fresh=97.5)]
        sess = self.session(stock, [])
        self.assertEqual(sess.snapshot()["stock"], [item("I2", fresh=97.5), item("I10", fresh=12)])
        self.assertEqual(sess.sim.ids.new("I"), "I11")
        self.assertEqual(available_stock(sess.sim), {"ca_loc": 1})

    def test_missing_stock_defaults_to_empty_array(self):
        sess = Session("quan", self.tuning, {"random_customers": False}, 7)
        self.assertEqual(sess.snapshot()["stock"], [])

    def test_exact_30_spoils_first_tick_and_is_retained_in_stock(self):
        sess = self.session([item("I1", fresh=30)], [])
        rows = sess.step(action())
        self.assertEqual(rows, [{"type": "event", "tick": 1, "phase": "quan", "name": "spoiled",
                                 "data": {"item_id": "I1", "kind": "ca_loc", "location": "stock"}}])
        self.assertLess(sess.snapshot()["stock"][0]["fresh"], 30)
        self.assertEqual(available_stock(sess.sim), {})
        self.assertEqual(sess.step(action()), [], "spoiled không lặp lại")

    def test_threshold_tick_uses_exact_fraction_not_float_drift(self):
        sess = self.session([item("I1", fresh=30.25)], [])
        for _ in range(60):
            self.assertEqual(sess.step(action()), [])
        self.assertEqual(sess.snapshot()["stock"][0]["fresh"], 30)
        self.assertEqual(available_stock(sess.sim), {"ca_loc": 1})
        self.assertEqual(sess.step(action())[0]["tick"], 61)

    def test_json_float_does_not_round_a_spoiled_fraction_back_to_30(self):
        sess = self.session([item("I1", fresh=30.004166666666666)], [])
        self.assertEqual(sess.step(action())[0]["name"], "spoiled")
        snapshot = json.loads(dumps(sess.snapshot()))
        self.assertLess(snapshot["stock"][0]["fresh"], 30)

    def test_small_menu_price_can_floor_to_zero_and_still_form_valid_payload(self):
        self.tuning["freshness"]["quan_decay_per_s"] = 0
        self.tuning["menu"]["ca_loc_nuong_trui"]["price"] = 1
        sess = self.session([item("I1", fresh=50)])
        self.assertEqual(sess.step(action("interact"))[0]["data"]["base_price"], 0)
        scenario = {"stock": [], "customers": [customer(order_status="assigned")], "stoves": [{
            "id": "B1", "state": "cooking", "cook_ticks_left": 1, "dish": sess.sim.stoves[0]["dish"]}]}
        validate_phase_block(scenario, "quan", self.tuning)
        resumed = Session("quan", self.tuning, scenario, 7)
        self.assertEqual(resumed.step(action())[0]["name"], "dish_ready")

    def test_spoiled_events_sorted_before_ready_dishes(self):
        sess = self.session([item("I10", fresh=30), item("I2", fresh=30)],
            [customer(order_status="assigned")], stoves=[{"id": "B1", "state": "cooking", "cook_ticks_left": 1,
                "dish": {"order_id": "C1", "dish_id": "ca_loc_nuong_trui", "base_price": 42}}])
        rows = sess.step(action())
        self.assertEqual([r["name"] for r in rows], ["spoiled", "spoiled", "dish_ready"])
        self.assertEqual([r["data"]["item_id"] for r in rows[:2]], ["I2", "I10"])

    def test_already_spoiled_does_not_emit_and_decay_clamps_to_zero(self):
        sess = self.session([item("I1", fresh=0.001), item("I2", fresh=20)], [])
        self.assertEqual(sess.step(action()), [])
        self.assertEqual(sess.snapshot()["stock"][0]["fresh"], 0)

    def test_missing_reservation_selects_freshest_then_natural_id(self):
        sess = self.session([item("I10", fresh=90), item("I2", fresh=90), item("I1", fresh=80)])
        self.assertEqual(sess.snapshot()["customers"][0]["reserved"], ["I2"])

    def test_missing_reservations_follow_oldest_order_then_table_id(self):
        sess = self.session([item("I1", fresh=80), item("I2", fresh=90), item("I3", fresh=100)], [
            customer("C1", "T3", order_tick=0), customer("C2", "T2", order_tick=0), customer("C3", "T1", order_tick=1)])
        by_id = {c["id"]: c["reserved"] for c in sess.snapshot()["customers"]}
        self.assertEqual(by_id, {"C1": ["I2"], "C2": ["I3"], "C3": ["I1"]})

    def test_explicit_reservation_is_not_stolen_by_automatic_allocation(self):
        sess = self.session([item("I1", fresh=100), item("I2", fresh=80)], [
            customer("C1", "T1", order_tick=0), customer("C2", "T2", order_tick=1, reserved=["I1"])])
        self.assertEqual([c["reserved"] for c in sess.snapshot()["customers"]], [["I2"], ["I1"]])

    def test_recipe_reservation_is_atomic_and_excludes_other_orders(self):
        stock = [item("I1", "bong_sung"), item("I2", "bong_sung"), item("I3", "bong_sung", 29)]
        sess = self.session(stock, [customer(dish="goi_bong_sung")])
        self.assertEqual(sess.snapshot()["customers"][0]["reserved"], ["I1", "I2"])
        self.assertNotIn("goi_bong_sung", cookable_dishes(sess.sim))
        with self.assertRaises(BadInput):
            self.session(stock, [customer(dish="goi_bong_sung"), customer("C2", "T2", dish="goi_bong_sung")])

    def test_reserved_spoil_retries_full_recipe_before_interact(self):
        sess = self.session([item("I1", fresh=30), item("I2", fresh=80)], [customer(reserved=["I1"])])
        rows = sess.step(action("interact"))
        self.assertEqual([r["name"] for r in rows], ["spoiled", "cook_started"])
        self.assertEqual(rows[1]["data"]["items"][0]["id"], "I2")
        self.assertEqual(sess.snapshot()["stock"][0]["id"], "I1")
        self.assertEqual(sess.snapshot()["customers"][0]["reserved"], [])

    def test_failed_retry_releases_whole_recipe_without_partial_holds(self):
        sess = self.session([item("I1", "bong_sung", 30), item("I2", "bong_sung", 80)], [customer(dish="goi_bong_sung")])
        rows = sess.step(action("interact"))
        self.assertEqual([r["name"] for r in rows], ["spoiled"])
        c = sess.snapshot()["customers"][0]
        self.assertEqual((c["order_status"], c["reserved"], c["state"]), ("unfulfillable", [], "waiting"))
        self.assertEqual(available_stock(sess.sim), {"bong_sung": 1})

    def test_all_affected_orders_release_before_retry_in_order(self):
        sess = self.session([item("I1", "bong_sung", 30), item("I2", "bong_sung", 80),
                             item("I3", "bong_sung", 30), item("I4", "bong_sung", 90)], [
            customer("C1", "T1", dish="goi_bong_sung", reserved=["I1", "I2"]),
            customer("C2", "T2", dish="goi_bong_sung", reserved=["I3", "I4"])])
        rows = sess.step(action())
        self.assertEqual([r["data"]["item_id"] for r in rows], ["I1", "I3"])
        c1, c2 = sess.snapshot()["customers"]
        self.assertEqual(c1["reserved"], ["I2", "I4"])
        self.assertEqual((c2["order_status"], c2["reserved"]), ("unfulfillable", []))

    def test_retry_cannot_take_an_unaffected_reservation(self):
        sess = self.session([item("I1", fresh=30), item("I2", fresh=80)], [
            customer("C1", "T1", reserved=["I1"]), customer("C2", "T2", reserved=["I2"])])
        sess.step(action())
        self.assertEqual(sess.snapshot()["customers"][0]["order_status"], "unfulfillable")
        self.assertEqual(sess.snapshot()["customers"][1]["reserved"], ["I2"])

    def test_customer_spawn_reserves_ids_and_does_not_use_rotten_items(self):
        sess = self.session([item("I1", fresh=100), item("I2", fresh=29)], [], random_customers=True)
        rows = []
        for _ in range(120):
            rows.extend(sess.step(action()))
        self.assertEqual([r["name"] for r in rows], ["customer_arrived"])
        c = sess.snapshot()["customers"][0]
        self.assertEqual(c["reserved"], ["I1"])
        self.assertEqual(c["patience_ticks_left"], 3600)
        self.assertEqual(available_stock(sess.sim), {})

    def test_only_rotten_stock_emits_no_dish_at_customer_tick(self):
        sess = self.session([item("I1", fresh=29)], [], random_customers=True)
        rows = []
        for _ in range(120):
            rows.extend(sess.step(action()))
        self.assertEqual([r["name"] for r in rows], ["no_dish"])

    def test_cook_consumes_reserved_items_and_locks_price_after_this_ticks_decay(self):
        sess = self.session([item("I1", fresh=80), item("I2", fresh=100)], [customer(reserved=["I1"])])
        started = sess.step(action("interact"))[0]
        self.assertEqual(started["data"]["base_price"], 47, "80 giảm 1/240 trước nấu: floor(60×fresh/100)=47")
        self.assertEqual(started["data"]["items"], [item("I1", fresh=80 - 1 / 240)])
        self.assertEqual(sess.sim.stoves[0]["dish"]["base_price"], 47)
        self.assertEqual([i["id"] for i in sess.snapshot()["stock"]], ["I2"])
        frozen = copy.deepcopy(started["data"]["items"])
        for _ in range(360):
            sess.step(action())
        self.assertEqual(sess.sim.stoves[0]["dish"]["base_price"], 47)
        self.assertEqual(started["data"]["items"], frozen)

    def test_exact_floor_and_average_for_multiple_ingredients(self):
        self.tuning["freshness"]["quan_decay_per_s"] = 0
        sess = self.session([item("I10", "bong_sung", 90), item("I2", "bong_sung", 80)],
                            [customer(dish="goi_bong_sung")])
        event = sess.step(action("interact"))[0]
        self.assertEqual(event["data"]["base_price"], 34)
        self.assertEqual([i["id"] for i in event["data"]["items"]], ["I2", "I10"])

    def test_fraction_floor_does_not_lose_integer_at_exact_threshold(self):
        self.tuning["menu"]["ca_loc_nuong_trui"]["price"] = 100
        sess = self.session([item("I1", fresh=50.25)])
        for _ in range(59):
            sess.step(action())
        self.assertEqual(sess.step(action("interact"))[0]["data"]["base_price"], 50)

    def test_served_and_paid_use_frozen_price_and_tip(self):
        self.tuning["freshness"]["quan_decay_per_s"] = 0
        sess = self.session([item("I1", fresh=80)])
        sess.step(action("interact"))
        for _ in range(359):
            sess.step(action())
        self.assertEqual([r["name"] for r in sess.step(action("interact"))], ["dish_ready", "dish_picked"])
        sess.sim.pos = [9, 2]
        served = sess.step(action("interact"))[0]
        self.assertEqual((served["data"]["base_price"], served["data"]["tip"]), (48, 9))
        sess.sim.time_left_ticks = 1
        rows = sess.step(action())
        self.assertEqual(rows[0]["data"]["amount"], 57)
        self.assertEqual(sess.sim.money, 57)
        self.assertEqual(sess.sim.reputation, 3.2)

    def test_burn_retries_with_fresh_ids_and_no_refund(self):
        self.tuning["quan"]["burn_s"] = 20
        sess = self.session([item("I1", fresh=80)], [customer(order_status="assigned")],
            stoves=[{"id": "B1", "state": "ready", "ready_ticks": 1200,
                     "dish": {"order_id": "C1", "dish_id": "ca_loc_nuong_trui", "base_price": 60}}])
        rows = sess.step(action("interact"))
        self.assertEqual([r["name"] for r in rows], ["dish_burnt", "cook_started"])
        self.assertEqual(rows[0]["data"]["order_status"], "reserved")
        self.assertEqual(rows[1]["data"]["items"][0]["id"], "I1")
        self.assertEqual(sess.snapshot()["stock"], [])

    def test_burn_cannot_reserve_rotten_items(self):
        self.tuning["quan"]["burn_s"] = 20
        sess = self.session([item("I1", fresh=30)], [customer(order_status="assigned")],
            stoves=[{"id": "B1", "state": "ready", "ready_ticks": 1200,
                     "dish": {"order_id": "C1", "dish_id": "ca_loc_nuong_trui", "base_price": 60}}])
        rows = sess.step(action("interact"))
        self.assertEqual([r["name"] for r in rows], ["spoiled", "dish_burnt"])
        self.assertEqual(rows[1]["data"]["order_status"], "unfulfillable")

    def test_leaving_releases_ids_and_keeps_raw_items(self):
        sess = self.session([item("I1")], [customer(patience_ticks_left=1)])
        self.assertEqual(sess.step(action())[0]["name"], "customer_left")
        self.assertEqual(sess.sim.customers, [])
        self.assertEqual(available_stock(sess.sim), {"ca_loc": 1})
        self.assertEqual(len(sess.snapshot()["stock"]), 1)

    def test_closing_still_cooks_before_customer_leaves_and_does_not_refund(self):
        sess = self.session([item("I1")], time_left_ticks=1)
        self.assertEqual([r["name"] for r in sess.step(action("interact"))], ["cook_started", "customer_left", "quan_end"])
        self.assertEqual(sess.snapshot()["stock"], [])
        self.assertEqual(sess.sim.reputation, 3)

    def test_paused_quan_does_not_decay_or_spoil(self):
        sess = self.session([item("I1", fresh=30)])
        sess.step(action("pause"))
        for _ in range(120):
            self.assertEqual(sess.step(action()), [])
        self.assertEqual(sess.snapshot()["stock"][0]["fresh"], 30)
        self.assertEqual([r["name"] for r in sess.step(action("pause"))], ["resumed", "spoiled"])

    def test_snapshot_does_not_alias_stock_and_restart_does_not_mutate_fixture(self):
        stock = [item("I1")]
        customers = [customer()]
        before = copy.deepcopy((stock, customers))
        sess = self.session(stock, customers)
        snapshot = sess.snapshot()
        sess.step(action("interact"))
        self.assertEqual(snapshot["stock"], [item("I1")])
        self.assertEqual((stock, customers), before)

    def test_bad_stock_or_reservation_raises_bad_input(self):
        invalid_stock = [{"ca_loc": 1}, [item("I1"), item("I1")], [item("", fresh=100)],
                         [item("I1", fresh=True)], [item("I1", fresh=float("nan"))],
                         [item("I1", fresh=101)], [item("I1", fresh=-1)], [item("I1", kind="unknown")],
                         [{**item("I1"), "extra": 1}]]
        for stock in invalid_stock:
            with self.subTest(stock=stock), self.assertRaises(BadInput):
                self.session(stock, [])
        for reserved in ({"ca_loc": 1}, ["I9"], ["I1", "I1"], ["I2"], [], [1]):
            with self.subTest(reserved=reserved), self.assertRaises(BadInput):
                self.session([item("I1"), item("I2", fresh=29)], [customer(reserved=reserved)])
        with self.assertRaises(BadInput):
            self.session([item("I1")], [customer(reserved=["I1"]), customer("C2", "T2", reserved=["I1"])])

    def test_scenario_validator_accepts_new_schema_and_rejects_old(self):
        validate_phase_block({"stock": [item("I1")], "customers": [customer(reserved=["I1"])]}, "quan", self.tuning)
        for block in ({"stock": {"ca_loc": 1}}, {"customers": [customer(reserved={"ca_loc": 1})]}):
            with self.subTest(block=block), self.assertRaises(BadInput):
                validate_phase_block(block, "quan", self.tuning)

    def test_jsonl_keeps_fresh_precision_and_regular_coordinate_rounding(self):
        value = 29.999999999
        row = json.loads(dumps({"item": item("I1", fresh=value), "pos": [1.123456, 2.123456]}))
        self.assertEqual(row["item"]["fresh"], value)
        self.assertLess(row["item"]["fresh"], 30)
        self.assertEqual(row["pos"], [1.123, 2.123])

    def test_runner_jsonl_is_byte_deterministic_with_spoil_and_reallocation(self):
        scenario = {"stock": [item("I1", fresh=30), item("I2", fresh=80)], "customers": [customer(reserved=["I1"])],
                    "random_customers": False, "player": {"pos": [2, 8]}, "time_left_ticks": 3}
        with tempfile.TemporaryDirectory() as tmp:
            outputs = []
            for number in (1, 2):
                path = Path(tmp) / f"out-{number}.txt"
                run("quan", self.tuning, scenario, 7, [{"tick": 0, "interact": True}], 3, path, 1)
                outputs.append(path.read_bytes())
            self.assertEqual(*outputs)
            rows = [json.loads(line) for line in outputs[0].splitlines()]
            self.assertEqual([r["name"] for r in rows if r["type"] == "event"], ["spoiled", "cook_started", "customer_left", "quan_end"])


if __name__ == "__main__":
    unittest.main()
