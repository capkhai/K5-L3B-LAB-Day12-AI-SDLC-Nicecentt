"""Phase 1, lát 4 (chur04): bếp, bưng, phục vụ và kết toán theo PRD-0 D/E/F.

Các hàm nhận QuanSim để lát khách có thể dùng chung trạng thái, không nhân đôi luật.
Stock là tồn vật lý, gồm nguyên liệu reserved; chỉ trừ stock khi bắt đầu nấu.
"""

import math
from decimal import Decimal, ROUND_FLOOR

from ..errors import BadInput
from ..ids import id_key, sort_by_id


def prepare_customers(sim):
    """Chuẩn hóa fixture cho lát dịch vụ; lát 3 bổ sung validation/lịch sinh khách.

    Cấp phần giữ thiếu theo order_tick rồi id bàn. Kiểm các liên kết món ngay
    khi dựng sim, trước khi runner mở output, kể cả --ticks 0.
    """
    for c in sim.customers:
        c.setdefault("state", "waiting")
        c.setdefault("order_tick", 0)
        c.setdefault("order_status", "reserved")
        c.setdefault("patience_ticks_left", sim.patience_max_ticks)
        c.setdefault("eat_ticks_left", 0)
        if not isinstance(c.get("dish_id"), str) or c["dish_id"] not in sim.menu:
            raise BadInput(f"customers.{c['id']}: dish_id không hợp lệ")
        for key in ("order_tick", "patience_ticks_left", "eat_ticks_left"):
            value = c[key]
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise BadInput(f"customers.{c['id']}.{key}: cần số nguyên không âm")
    if sim.fresh_stock is not None:
        sim.fresh_stock.prepare_reservations()
    else:
        available = dict(sim.stock)
        for c in sorted(sim.customers, key=order_key):
            if c["order_status"] == "reserved":
                recipe = sim.menu[c["dish_id"]]["recipe"]
                c.setdefault("reserved", dict(recipe))
                if c["reserved"] != recipe or any(available.get(k, 0) < n for k, n in recipe.items()):
                    raise BadInput(f"customers.{c['id']}: giữ chỗ khác công thức hoặc quá tồn")
                for k, n in recipe.items():
                    available[k] = available.get(k, 0) - n
            else:
                c.setdefault("reserved", {})
                if c["reserved"]:
                    raise BadInput(f"customers.{c['id']}: đơn không reserved phải có phần giữ rỗng")
    by_id = {c["id"]: c for c in sim.customers}
    assigned = {}
    for stove in sim.stoves:
        state = stove["state"]
        if state not in ("idle", "cooking", "ready"):
            raise BadInput(f"stoves.{stove['id']}: state không hợp lệ")
        for key in ("cook_ticks_left", "ready_ticks"):
            value = stove[key]
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise BadInput(f"stoves.{stove['id']}.{key}: cần số nguyên không âm")
        if state == "idle":
            if stove["dish"] is not None or stove["cook_ticks_left"] or stove["ready_ticks"]:
                raise BadInput(f"stoves.{stove['id']}: bếp idle có món/timer")
        elif ((state == "cooking" and (stove["cook_ticks_left"] <= 0 or stove["ready_ticks"]))
              or (state == "ready" and stove["cook_ticks_left"])):
            raise BadInput(f"stoves.{stove['id']}: timer không khớp state")
        else:
            _check_payload(stove["dish"], by_id, assigned, allow_zero=sim.fresh_stock is not None)
    if sim.hand is not None:
        _check_payload(sim.hand, by_id, assigned, allow_zero=sim.fresh_stock is not None)
    for c in sim.customers:
        status, state = c["order_status"], c["state"]
        if status not in ("reserved", "assigned", "unfulfillable", "served") or state not in ("waiting", "eating"):
            raise BadInput(f"customers.{c['id']}: trạng thái không hợp lệ")
        if state == "eating":
            if status != "served" or c["eat_ticks_left"] <= 0:
                raise BadInput(f"customers.{c['id']}: eating cần served và timer ăn dương")
            for key in ("base_price", "tip"):
                value = c.get(key)
                minimum = 1 if key == "base_price" and sim.fresh_stock is None else 0
                if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
                    raise BadInput(f"customers.{c['id']}.{key}: giá/boa chưa chốt hợp lệ")
        elif status == "served" or c["eat_ticks_left"]:
            raise BadInput(f"customers.{c['id']}: khách waiting không được served/đang ăn")
        if (status == "assigned") != (c["id"] in assigned):
            raise BadInput(f"customers.{c['id']}: assigned cần đúng một món ở bếp hoặc tay")


def _check_payload(dish, customers, assigned, allow_zero=False):
    if not isinstance(dish, dict) or set(dish) != {"order_id", "dish_id", "base_price"}:
        raise BadInput("payload món phải có đúng order_id, dish_id, base_price")
    order_id = dish["order_id"]
    if not isinstance(order_id, str) or order_id not in customers:
        raise BadInput("payload món tham chiếu đơn không tồn tại")
    c = customers[order_id]
    price = dish["base_price"]
    if (c["order_status"] != "assigned" or c["state"] != "waiting"
            or dish["dish_id"] != c["dish_id"] or isinstance(price, bool)
            or not isinstance(price, int) or price < (0 if allow_zero else 1) or order_id in assigned):
        raise BadInput(f"món không khớp đơn assigned hoặc trùng món: {order_id}")
    assigned[order_id] = dish


def order_key(customer):
    return customer["order_tick"], id_key(customer["table_id"])


def advance_timers(sim):
    """Bước F.1: chỉ giảm timer đã có ở đầu bước, không giảm timer vừa tạo."""
    for stove in sort_by_id(sim.stoves):
        if stove["state"] == "cooking":
            stove["cook_ticks_left"] = max(0, stove["cook_ticks_left"] - 1)
        elif stove["state"] == "ready":
            stove["ready_ticks"] += 1
    for customer in sort_by_id(sim.customers):
        key = "eat_ticks_left" if customer["state"] == "eating" else "patience_ticks_left"
        customer[key] = max(0, customer[key] - 1)


def ready_dishes(sim, events):
    for stove in sort_by_id(sim.stoves):
        if stove["state"] == "cooking" and stove["cook_ticks_left"] == 0:
            stove["state"] = "ready"
            stove["ready_ticks"] = 0
            events.append(("dish_ready", _dish_event(stove)))
        burn_s = sim.t.get("burn_s")
        if (burn_s is not None and stove["state"] == "ready"
                and stove["ready_ticks"] > int(round(burn_s * sim.tick_hz))):
            _burn_dish(sim, stove, events)


def _burn_dish(sim, stove, events):
    from .quan_customers import available_stock

    data = _dish_event(stove)
    _reset_stove(stove)
    customer = next(c for c in sim.customers if c["id"] == data["order_id"])
    if sim.fresh_stock is not None:
        sim.fresh_stock.reserve_again(customer)
    else:
        customer.update(order_status="unfulfillable", reserved={})
        available = available_stock(sim)
        recipe = sim.menu[customer["dish_id"]]["recipe"]
        if all(available.get(kind, 0) >= count for kind, count in recipe.items()):
            customer.update(order_status="reserved", reserved=dict(recipe))
    events.append(("dish_burnt", dict(data, order_status=customer["order_status"])))


def interact(sim, events):
    """Chọn một đối tượng trước, rồi thử một hành động; không fallback."""
    candidates = []
    for priority, entities in enumerate((sim.stoves, sim.tables)):
        for entity in sort_by_id(entities):
            distance = math.dist(sim.pos, entity["pos"])
            if distance <= sim.t["interact_radius"]:
                candidates.append((distance, priority, id_key(entity["id"]), entity))
    if not candidates:
        return
    _, priority, _, target = min(candidates, key=lambda item: item[:3])
    if priority == 0:
        _interact_stove(sim, target, events)
    else:
        _serve(sim, target, events)


def _dish_event(stove):
    dish = stove["dish"]
    return {"stove_id": stove["id"], "order_id": dish["order_id"], "dish_id": dish["dish_id"]}


def _reset_stove(stove):
    stove.update(state="idle", dish=None, cook_ticks_left=0, ready_ticks=0)


def _interact_stove(sim, stove, events):
    if stove["state"] == "ready" and sim.hand is None:
        data = _dish_event(stove)
        sim.hand = stove["dish"]
        _reset_stove(stove)
        events.append(("dish_picked", data))
    elif stove["state"] == "idle":
        orders = [c for c in sim.customers if c["state"] == "waiting" and c["order_status"] == "reserved"]
        if not orders:
            return
        customer = min(orders, key=order_key)
        dish_id = customer["dish_id"]
        if sim.fresh_stock is not None:
            items, price = sim.fresh_stock.consume(customer)
        else:
            recipe = customer["reserved"]
            # Validation của fixture/lát khách bảo đảm phần giữ có đủ tồn vật lý.
            if any(sim.stock.get(kind, 0) < count for kind, count in recipe.items()):
                raise BadInput("nguyên liệu giữ chỗ không còn trong kho")
            items = [kind for kind in sorted(recipe) for _ in range(recipe[kind])]
            for kind, count in recipe.items():
                sim.stock[kind] -= count
            price = sim.menu[dish_id]["price"]
        customer.update(order_status="assigned", reserved=[] if sim.fresh_stock is not None else {})
        stove.update(state="cooking", dish={"order_id": customer["id"], "dish_id": dish_id, "base_price": price},
                     cook_ticks_left=int(round(sim.menu[dish_id]["cook_s"] * sim.tick_hz)), ready_ticks=0)
        events.append(("cook_started", dict(_dish_event(stove), items=items, base_price=price)))


def _serve(sim, table, events):
    if sim.hand is None:
        return
    for customer in sort_by_id(sim.customers):
        if (customer["table_id"] == table["id"] and customer["id"] == sim.hand["order_id"]
                and customer["state"] == "waiting" and customer["order_status"] == "assigned"):
            dish = sim.hand
            price = dish["base_price"]
            eligible = customer["patience_ticks_left"] / sim.patience_max_ticks >= sim.t["tip_min_patience_ratio"]
            tip = int((Decimal(price) * Decimal(str(sim.t["tip_rate"]))).to_integral_value(rounding=ROUND_FLOOR)) if eligible else 0
            customer.update(state="eating", order_status="served", eat_ticks_left=sim.eat_ticks,
                            base_price=price, tip=tip)
            sim.hand = None
            events.append(("served", {"order_id": customer["id"], "table_id": table["id"],
                                      "dish_id": dish["dish_id"], "patience_ticks_left": customer["patience_ticks_left"],
                                      "base_price": price, "tip": tip}))
            return


def discard_order(sim, customer):
    """Dùng khi lát khách hủy đơn: nhả giữ thô, hủy món, không hoàn hàng đã nấu."""
    customer["reserved"] = [] if sim.fresh_stock is not None else {}
    for stove in sort_by_id(sim.stoves):
        if stove["dish"] is not None and stove["dish"]["order_id"] == customer["id"]:
            _reset_stove(stove)
    if sim.hand is not None and sim.hand["order_id"] == customer["id"]:
        sim.hand = None


def settle_customers(sim, events):
    """Bước F.4: thanh toán/rời bàn theo id bàn; hết ca dọn trước quan_end."""
    closing = sim.time_left_ticks == 0
    for customer in sort_by_id(sim.customers, key=lambda c: c["table_id"]):
        eating = customer["state"] == "eating"
        if eating and (customer["eat_ticks_left"] == 0 or closing):
            amount = customer["base_price"] + customer["tip"]
            sim.money += amount
            sim.earned += amount
            sim.shift_earned += amount
            if customer["tip"] > 0:
                sim.reputation = _clamp_reputation(sim, sim.reputation + sim.t["tip_reputation"])
            events.append(("paid", {"order_id": customer["id"], "table_id": customer["table_id"],
                                    "base_price": customer["base_price"], "tip": customer["tip"], "amount": amount,
                                    "reason": "finished_eating" if customer["eat_ticks_left"] == 0 else "closing"}))
        elif not eating and (customer["patience_ticks_left"] == 0 or closing):
            if not closing:
                sim.reputation = _clamp_reputation(sim, sim.reputation + sim.t["left_reputation_delta"])
            events.append(("customer_left", {"order_id": customer["id"], "table_id": customer["table_id"],
                                             "reason": "closing" if closing else "patience", "reputation": sim.reputation}))
        else:
            continue
        discard_order(sim, customer)
        sim.customers.remove(customer)


def _clamp_reputation(sim, value):
    return max(sim.t["reputation_min"], min(sim.t["reputation_max"], value))
