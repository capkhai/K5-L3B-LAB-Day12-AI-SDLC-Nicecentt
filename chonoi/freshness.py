"""Phase 3 (Contract v1.2): độ tươi, kho cá thể, số học chính xác ở ngưỡng 30 và chốt giá.

Dùng `Fraction` để tránh sai số dấu phẩy động ở ngưỡng `fresh < 30` và phép `floor(price * avg_fresh / 100)`.
Tự động bắt chính xác bội số của `1/240` khi đọc lại từ JSON (do gather trừ `2/240` và quán trừ `1/240` mỗi tick).
"""

import math
from fractions import Fraction

from .ids import id_key, sort_by_id

UNITS_PER_POINT = 240


def is_v12(tuning: dict) -> bool:
    return isinstance(tuning, dict) and isinstance(tuning.get("freshness"), dict)


def to_frac(val) -> Fraction:
    """Chuyển int/float/Fraction sang Fraction chính xác; khớp bội số 1/240 nếu sai khác < 1e-9."""
    if isinstance(val, Fraction):
        return val
    if isinstance(val, int) and not isinstance(val, bool):
        return Fraction(val, 1)
    f = float(val)
    k = round(f * UNITS_PER_POINT)
    if abs(f - k / UNITS_PER_POINT) < 1e-9:
        return Fraction(k, UNITS_PER_POINT)
    return Fraction(str(val))


def frac_to_number(frac: Fraction):
    if frac.denominator == 1:
        return int(frac.numerator)
    return float(frac)


def item_frac(item: dict) -> Fraction:
    if "_f" in item:
        return item["_f"]
    f = to_frac(item["fresh"])
    item["_f"] = f
    return f


def make_item(ident: str, kind: str, fresh=100) -> dict:
    f = to_frac(fresh)
    return {"id": ident, "kind": kind, "fresh": frac_to_number(f), "_f": f}


def public_item(item: dict) -> dict:
    return {"id": item["id"], "kind": item["kind"], "fresh": frac_to_number(item_frac(item))}


def clone_item(item: dict, new_id: str = None) -> dict:
    f = item_frac(item)
    return {
        "id": item["id"] if new_id is None else new_id,
        "kind": item["kind"],
        "fresh": frac_to_number(f),
        "_f": f,
    }


def is_spoiled(item: dict, spoiled_below=30) -> bool:
    return item_frac(item) < to_frac(spoiled_below)


def decay_items(items: list, decay_per_s, tick_hz, spoiled_below, location: str, events: list) -> list:
    """Hao tươi toàn bộ cá thể trong `items`, phát `spoiled` theo thứ tự id. Trả danh sách id vừa ươn."""
    if not items:
        return []
    step_decay = to_frac(decay_per_s) / to_frac(tick_hz)
    threshold = to_frac(spoiled_below)
    zero = Fraction(0)
    newly_spoiled = []
    for it in items:
        prev = item_frac(it)
        nxt = prev - step_decay
        if nxt < zero:
            nxt = zero
        it["_f"] = nxt
        it["fresh"] = frac_to_number(nxt)
        if prev >= threshold and nxt < threshold:
            newly_spoiled.append(it)
    newly_spoiled = sort_by_id(newly_spoiled)
    for it in newly_spoiled:
        events.append(("spoiled", {
            "item_id": it["id"],
            "kind": it["kind"],
            "location": location,
        }))
    return [it["id"] for it in newly_spoiled]


def fresh_base_price(menu_price: int, used_items: list) -> int:
    """Chốt base_price = floor(menu_price * avg_fresh / 100) bằng số học chính xác."""
    if not used_items:
        return int(menu_price)
    total_fresh = sum((item_frac(it) for it in used_items), Fraction(0))
    exact = Fraction(int(menu_price), 1) * total_fresh / Fraction(100 * len(used_items), 1)
    return int(math.floor(exact))


def sort_items_by_kind_then_id(items: list) -> list:
    return sorted(items, key=lambda it: (it["kind"], id_key(it["id"])))
