"""Phase 3, lát 3: kho cá thể, giữ chỗ và độ tươi trong quán.

Fraction giữ nhánh ở ngưỡng 30 và phép floor chính xác qua nhiều tick.
Giá theo độ tươi là giả định được người dùng cho phép, xem docs/clarify.md.
"""

import math
from fractions import Fraction

from ..errors import BadInput
from ..ids import id_key, sort_by_id


def ingredient_kinds(tuning):
    kinds = {kind for dish in tuning["menu"].values() for kind in dish["recipe"]}
    kinds.update(tuning.get("gather", {}).get("fish_yield", {}))
    kinds.update(node["kind"] for node in tuning.get("gather", {}).get("nodes", []))
    return kinds


def validate_stock(items, kinds):
    if not isinstance(items, list):
        raise BadInput("stock v1.2 phải là mảng cá thể, không nhận kho đếm")
    seen, result = set(), []
    for item in items:
        if not isinstance(item, dict) or set(item) != {"id", "kind", "fresh"}:
            raise BadInput("cá thể cần đúng id, kind, fresh")
        ident, kind, fresh = item["id"], item["kind"], item["fresh"]
        if not isinstance(ident, str) or not ident or ident in seen:
            raise BadInput("id cá thể phải khác rỗng và duy nhất trong kho")
        if not isinstance(kind, str) or kind not in kinds:
            raise BadInput("kind cá thể không hợp lệ")
        if isinstance(fresh, bool) or not isinstance(fresh, (int, float)) or not math.isfinite(fresh) or not 0 <= fresh <= 100:
            raise BadInput("fresh phải hữu hạn trong [0,100]")
        seen.add(ident)
        result.append(dict(item))
    return result


class FreshStock:
    def __init__(self, sim, tuning, items):
        self.sim = sim
        config = tuning["freshness"]
        if not isinstance(config, dict):
            raise BadInput("freshness phải là object")
        for key in ("initial", "gather_decay_per_s", "quan_decay_per_s", "spoiled_below"):
            value = config.get(key)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
                raise BadInput(f"freshness.{key}: cần số hữu hạn không âm")
        if not 0 < config["initial"] <= 100 or not 0 <= config["spoiled_below"] <= config["initial"]:
            raise BadInput("freshness: initial/spoiled_below không hợp lệ")
        self.items = validate_stock(items, ingredient_kinds(tuning))
        self.values = {item["id"]: Fraction(str(item["fresh"])) for item in self.items}
        self.threshold = Fraction(str(config["spoiled_below"]))
        self.initial = Fraction(str(config["initial"]))
        self.decay = Fraction(str(config["quan_decay_per_s"])) / sim.tick_hz
        for item in self.items:
            sim.ids.reserve(item["id"])

    def snapshot(self):
        return [dict(item) for item in sort_by_id(self.items)]

    def reserved_ids(self):
        return {ident for c in self.sim.customers if c["order_status"] == "reserved" for ident in c["reserved"]}

    def available_counts(self):
        held = self.reserved_ids()
        counts = {}
        for item in self.items:
            if item["id"] not in held and self.values[item["id"]] >= self.threshold:
                counts[item["kind"]] = counts.get(item["kind"], 0) + 1
        return counts

    def select(self, recipe, excluded=None):
        held = self.reserved_ids() if excluded is None else excluded
        selected = []
        for kind, count in sorted(recipe.items()):
            candidates = [item for item in self.items if item["kind"] == kind and item["id"] not in held
                          and self.values[item["id"]] >= self.threshold]
            candidates.sort(key=lambda item: (-self.values[item["id"]], id_key(item["id"])))
            if len(candidates) < count:
                return None
            selected.extend(item["id"] for item in candidates[:count])
        return sorted(selected, key=id_key)

    def validate_reservation(self, customer, claimed):
        reserved = customer["reserved"]
        if not isinstance(reserved, list) or any(not isinstance(ident, str) or not ident for ident in reserved):
            raise BadInput("reserved v1.2 phải là mảng id cá thể")
        if len(reserved) != len(set(reserved)) or set(reserved) & claimed:
            raise BadInput("cá thể bị giữ trùng trong/cùng các đơn")
        by_id = {item["id"]: item for item in self.items}
        counts = {}
        for ident in reserved:
            if ident not in by_id or self.values[ident] < self.threshold:
                raise BadInput("reserved phải trỏ tới cá thể chưa ươn có thật trong stock")
            kind = by_id[ident]["kind"]
            counts[kind] = counts.get(kind, 0) + 1
        if counts != self.sim.menu[customer["dish_id"]]["recipe"]:
            raise BadInput("reserved không đủ/khác công thức")
        claimed.update(reserved)

    def prepare_reservations(self):
        from .quan_service import order_key

        ordered = sorted(self.sim.customers, key=order_key)
        claimed = set()
        # Phần giữ tường minh là quyền đã có; không cấp thiếu rồi chiếm của đơn khác.
        for c in ordered:
            if c["order_status"] == "reserved" and "reserved" in c:
                self.validate_reservation(c, claimed)
            elif c["order_status"] != "reserved":
                c.setdefault("reserved", [])
                if not isinstance(c["reserved"], list) or c["reserved"]:
                    raise BadInput("đơn không reserved phải có reserved:[]")
        for c in ordered:
            if c["order_status"] == "reserved" and "reserved" not in c:
                selected = self.select(self.sim.menu[c["dish_id"]]["recipe"], excluded=claimed)
                if selected is None:
                    raise BadInput("fixture reserved vượt nguyên liệu còn tươi trong kho")
                c["reserved"] = selected
                claimed.update(selected)

    def reserve_again(self, customer):
        customer.update(order_status="unfulfillable", reserved=[])
        selected = self.select(self.sim.menu[customer["dish_id"]]["recipe"])
        if selected is not None:
            customer.update(order_status="reserved", reserved=selected)

    def step(self, events):
        from .quan_service import order_key

        spoiled = set()
        for item in sort_by_id(self.items):
            ident = item["id"]
            old = self.values[ident]
            fresh = max(Fraction(0), old - self.decay)
            self.values[ident] = fresh
            visible = float(fresh)
            # Không để phép đổi sang JSON float đưa hàng đã ươn trở lại đúng 30.
            if fresh < self.threshold and visible >= float(self.threshold):
                visible = math.nextafter(float(self.threshold), -math.inf)
            item["fresh"] = visible
            if old >= self.threshold and fresh < self.threshold:
                spoiled.add(ident)
                events.append(("spoiled", {"item_id": ident, "kind": item["kind"], "location": "stock"}))
        affected = sorted([c for c in self.sim.customers if c["order_status"] == "reserved"
                           and spoiled.intersection(c["reserved"])], key=order_key)
        # Phát hết spoiled trước, nhả toàn bộ đơn bị ảnh hưởng rồi mới cấp lại theo thứ tự.
        for c in affected:
            c.update(order_status="unfulfillable", reserved=[])
        for c in affected:
            self.reserve_again(c)

    def consume(self, customer):
        self.validate_reservation(customer, set())
        reserved = set(customer["reserved"])
        selected = [dict(item) for item in self.items if item["id"] in reserved]
        selected.sort(key=lambda item: (item["kind"], id_key(item["id"])))
        average = sum((self.values[item["id"]] for item in selected), Fraction(0)) / len(selected)
        base_price = self.sim.menu[customer["dish_id"]]["price"]
        # Giả định được người dùng cho phép: giá thực đơn × trung bình fresh / initial.
        price = int(base_price * average // self.initial)
        self.items[:] = [item for item in self.items if item["id"] not in reserved]
        for ident in reserved:
            del self.values[ident]
        return selected, price
