"""Nạp và kiểm scenario (Contract D). Trả về dict của đúng khối theo mode.

KHUNG: kiểm cú pháp, id trùng, bộ đếm âm, khoang vượt sức chứa, trường lạ.
TODO(nhóm): bổ sung kiểm mâu thuẫn mức luật mà nhóm cần (khách giữ chỗ quá kho, đơn assigned
phải có đúng một món, khách eating thiếu giá/tip...) — xem PRD-0 mục D và 'Mâu thuẫn -> mã 2'.
"""

import json

from .errors import BadInput
from .freshness import is_v12
from .inventory import KINDS_P2, validate_item_list, validate_items

GATHER_KEYS = {"player", "hold", "nodes", "fish", "random_fish", "monsters", "time_left_ticks",
               "random_current", "current_direction"}
GATHER_PLAYER_KEYS = {"pos", "vel", "heading_deg", "hp", "oxygen_ticks", "zero_oxy_ticks",
                      "invuln_ticks", "catch_cd_ticks"}
NODE_KINDS = ("bong_dien_dien", "bong_sung", "keo_neo")
FISH_KINDS = ("ca_linh", "ca_loc", "ca_keo")
QUAN_PLAYER_KEYS = {"pos", "vel"}
QUAN_KEYS = {"player", "stock", "hand", "stoves", "tables", "customers", "random_customers",
             "reputation", "time_left_ticks"}


def _check_ids(name, arr):
    if not isinstance(arr, list):
        raise BadInput(f"{name} phải là mảng")
    seen = set()
    for e in arr:
        if not isinstance(e, dict) or not isinstance(e.get("id"), str) or not e["id"]:
            raise BadInput(f"{name}: mỗi phần tử cần id (chuỗi khác rỗng)")
        if e["id"] in seen:
            raise BadInput(f"{name}: id trùng {e['id']}")
        seen.add(e["id"])


def load_scenario(path, mode: str, tuning: dict) -> dict:
    if path is None:
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError) as e:
        raise BadInput(f"không đọc được scenario {path}: {e}")
    if mode == "day":
        from .sim.day_config import validate_day_scenario
        return validate_day_scenario(data, tuning)
    if not isinstance(data, dict) or not set(data) <= {"gather", "quan"}:
        raise BadInput("scenario chỉ được có khối 'gather' hoặc 'quan'")
    if set(data) - {mode}:
        raise BadInput(f"khối sai mode: chạy --mode {mode} chỉ nhận khối '{mode}'")
    block = data.get(mode, {})
    validate_phase_block(block, mode, tuning)
    return block


def validate_phase_block(block, mode, tuning):
    """Điểm nối dùng chung cho mode độc lập và template/đổi pha trong day."""
    if not isinstance(block, dict):
        raise BadInput(f"khối {mode} phải là object")
    allowed = GATHER_KEYS if mode == "gather" else QUAN_KEYS
    extra = set(block) - allowed
    if extra:
        raise BadInput(f"trường lạ/chưa hỗ trợ trong {mode}: {sorted(extra)}")
    dur = int(round(tuning[mode]["duration_s"] * 60))
    if "time_left_ticks" in block:
        t = block["time_left_ticks"]
        if isinstance(t, bool) or not isinstance(t, int) or not (1 <= t <= dur):
            raise BadInput(f"time_left_ticks phải là số nguyên trong [1, {dur}]")
    if mode == "gather":
        _validate_gather(block, tuning)
    else:
        _validate_quan(block, tuning)


def _num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _nonneg_int(name, v):
    if isinstance(v, bool) or not isinstance(v, int) or v < 0:
        raise BadInput(f"{name} phải là số nguyên không âm")


def _pos(name, pos, bounds, axes=("x", "d")):
    if not (isinstance(pos, list) and len(pos) == 2 and all(_num(c) for c in pos)):
        raise BadInput(f"{name} phải là [{axes[0]}, {axes[1]}]")
    for c, axis in zip(pos, axes):
        lo, hi = bounds[axis]
        if not (lo <= c <= hi):
            raise BadInput(f"{name} nằm ngoài vùng nước ({axis} ∈ [{lo}, {hi}])")


def _validate_gather(b, tuning):
    g = tuning["gather"]
    bounds = g["bounds"]
    kinds = {kind for dish in tuning["menu"].values() for kind in dish["recipe"]}
    node_kinds = {n["kind"] for n in g["nodes"]}
    fish_kinds = set(g["fish_yield"])
    for arr in ("nodes", "fish", "monsters"):
        if arr in b:
            _check_ids(arr, b[arr])
    if "random_fish" in b and not isinstance(b["random_fish"], bool):
        raise BadInput("random_fish phải là boolean")
    if "random_current" in b and not isinstance(b["random_current"], bool):
        raise BadInput("random_current phải là boolean")
    if "current_direction" in b:
        cd = b["current_direction"]
        if isinstance(cd, bool) or not isinstance(cd, int) or cd not in (-1, 1):
            raise BadInput("current_direction phải là -1 hoặc 1")
    if "hold" in b:
        h = b["hold"]
        if is_v12(tuning):
            validate_item_list(h, kinds)
        else:
            if not isinstance(h, list) or any(not isinstance(k, str) or k not in kinds for k in h):
                raise BadInput("hold phải là mảng id nguyên liệu hợp lệ")
        if len(h) > g["hold_capacity"]:
            raise BadInput("hold vượt sức chứa")
    p = b.get("player", {})
    if not isinstance(p, dict):
        raise BadInput("player phải là object")
    extra = set(p) - GATHER_PLAYER_KEYS
    if extra:
        raise BadInput(f"trường lạ/chưa hỗ trợ trong gather.player: {sorted(extra)}")
    if "pos" in p:
        _pos("player.pos", p["pos"], bounds)
    if "vel" in p and not (isinstance(p["vel"], list) and len(p["vel"]) == 2 and all(_num(c) for c in p["vel"])):
        raise BadInput("player.vel phải là [x, d]")
    if "heading_deg" in p and not _num(p["heading_deg"]):
        raise BadInput("player.heading_deg phải là số")
    for key in ("invuln_ticks", "catch_cd_ticks", "zero_oxy_ticks", "oxygen_ticks", "hp"):
        if key in p:
            _nonneg_int(f"player.{key}", p[key])
    omax = int(round(g["oxygen_max_s"] * 60))
    if "oxygen_ticks" in p and p["oxygen_ticks"] > omax:
        raise BadInput("player.oxygen_ticks vượt oxy tối đa")
    if "hp" in p and not (1 <= p["hp"] <= g["hp_max"]):
        raise BadInput("player.hp phải trong [1, hp_max]")
    if "zero_oxy_ticks" in p:
        pos = p.get("pos", g["start_pos"])
        oxy = p.get("oxygen_ticks", omax)
        if p["zero_oxy_ticks"] > 59:
            raise BadInput("player.zero_oxy_ticks phải trong [0, 59]")
        if p["zero_oxy_ticks"] > 0 and not (oxy == 0 and pos[1] > g["surface_depth"]):
            raise BadInput("player.zero_oxy_ticks > 0 chỉ khi oxy = 0 và đang dưới nước")
    for n in b.get("nodes", []):
        if n.get("kind") not in node_kinds:
            raise BadInput(f"nodes.{n['id']}: kind phải là một trong {NODE_KINDS}")
        _pos(f"nodes.{n['id']}.pos", n.get("pos"), bounds)
        if n["pos"][1] != 0:
            raise BadInput(f"nodes.{n['id']}: nút hái nằm ở mặt nước (d = 0)")
        if "regrow_ticks" in n:
            _nonneg_int(f"nodes.{n['id']}.regrow_ticks", n["regrow_ticks"])
    for f in b.get("fish", []):
        if f.get("kind") not in fish_kinds:
            raise BadInput(f"fish.{f['id']}: kind phải là một trong {FISH_KINDS}")
        _pos(f"fish.{f['id']}.pos", f.get("pos"), bounds)
        if f["pos"][1] <= g["surface_depth"]:
            raise BadInput(f"fish.{f['id']}: đàn cá phải ở dưới nước")
        if "heading_deg" in f and not _num(f["heading_deg"]):
            raise BadInput(f"fish.{f['id']}.heading_deg phải là số")
        if "age_ticks" in f:
            _nonneg_int(f"fish.{f['id']}.age_ticks", f["age_ticks"])
    monster_species = set(g.get("monsters", {}).get("species", {}).keys())
    monster_keys = {"id", "kind", "pos", "waypoints", "target_idx", "state", "state_ticks_left", "recoil_dir"}
    for m in b.get("monsters", []):
        extra = set(m) - monster_keys
        if extra:
            raise BadInput(f"monsters.{m['id']}: trường lạ {sorted(extra)}")
        if m.get("kind") not in monster_species:
            raise BadInput(f"monsters.{m['id']}: kind phải là một trong {sorted(monster_species)}")
        _pos(f"monsters.{m['id']}.pos", m.get("pos"), bounds)
        wps = m.get("waypoints")
        if not isinstance(wps, list) or len(wps) != 2:
            raise BadInput(f"monsters.{m['id']}.waypoints phải có đúng 2 điểm")
        for idx, wp in enumerate(wps):
            _pos(f"monsters.{m['id']}.waypoints[{idx}]", wp, bounds)
        if "target_idx" in m:
            if isinstance(m["target_idx"], bool) or m["target_idx"] not in (0, 1):
                raise BadInput(f"monsters.{m['id']}.target_idx phải là 0 hoặc 1")
        state = m.get("state", "patrol")
        if state not in {"patrol", "chase", "recoil", "stunned"}:
            raise BadInput(f"monsters.{m['id']}.state không hợp lệ")
        if "state_ticks_left" in m:
            _nonneg_int(f"monsters.{m['id']}.state_ticks_left", m["state_ticks_left"])
        ticks_left = m.get("state_ticks_left", 0)
        if state in {"recoil", "stunned"} and ticks_left <= 0:
            raise BadInput(f"monsters.{m['id']}: trạng thái {state} cần state_ticks_left > 0")
        rdir = m.get("recoil_dir")
        if state == "recoil":
            if not (isinstance(rdir, list) and len(rdir) == 2 and all(_num(c) for c in rdir)):
                raise BadInput(f"monsters.{m['id']}.recoil_dir phải là vector [x, d] khi recoil")
            norm = (rdir[0] ** 2 + rdir[1] ** 2) ** 0.5
            if abs(norm - 1.0) > 0.05:
                raise BadInput(f"monsters.{m['id']}.recoil_dir phải là vector đơn vị")
        elif rdir is not None:
            raise BadInput(f"monsters.{m['id']}.recoil_dir phải là null ngoài trạng thái recoil")


def _validate_quan(b, tuning):
    fresh_mode = is_v12(tuning)
    kinds = {kind for dish in tuning["menu"].values() for kind in dish["recipe"]}
    for arr in ("stoves", "tables", "customers"):
        if arr in b:
            _check_ids(arr, b[arr])
    if "stock" in b:
        if fresh_mode:
            validate_item_list(b["stock"], kinds)
        else:
            validate_items(b["stock"], kinds)
    p = b.get("player", {})
    if not isinstance(p, dict) or set(p) - QUAN_PLAYER_KEYS:
        raise BadInput("quan.player chỉ có pos và vel")
    qb = tuning["quan"]["bounds"]
    if "pos" in p:
        _pos("player.pos", p["pos"], qb, axes=("x", "z"))
    if "vel" in p and not (isinstance(p["vel"], list) and len(p["vel"]) == 2 and all(_num(c) for c in p["vel"])):
        raise BadInput("player.vel phải là [x, z]")
    if "random_customers" in b and not isinstance(b["random_customers"], bool):
        raise BadInput("random_customers phải là boolean")
    if "hand" in b and b["hand"] is not None:
        _check_dish_payload("quan.hand", b["hand"], tuning["menu"], allow_zero=fresh_mode)
    if "reputation" in b:
        r = b["reputation"]
        q = tuning["quan"]
        if not _num(r) or not (q["reputation_min"] <= r <= q["reputation_max"]):
            raise BadInput("reputation nằm ngoài [reputation_min, reputation_max]")
    table_ids = [c.get("table_id") for c in b.get("customers", [])]
    known = {t["id"] for t in tuning["quan"]["tables"]} | {t.get("id") for t in b.get("tables", [])}
    menu = tuning["menu"]
    for stove in b.get("stoves", []):
        extra = set(stove) - {"id", "pos", "state", "dish", "cook_ticks_left", "ready_ticks"}
        if extra:
            raise BadInput(f"trường lạ/chưa hỗ trợ trong stoves.{stove['id']}: {sorted(extra)}")
        if "pos" in stove:
            _pos(f"stoves.{stove['id']}.pos", stove["pos"], qb, axes=("x", "z"))
        if "state" in stove and stove["state"] not in {"idle", "cooking", "ready"}:
            raise BadInput(f"stoves.{stove['id']}: state không hợp lệ")
        for key in ("cook_ticks_left", "ready_ticks"):
            if key in stove:
                _nonneg_int(f"stoves.{stove['id']}.{key}", stove[key])
        if "dish" in stove and stove["dish"] is not None:
            _check_dish_payload(f"stoves.{stove['id']}.dish", stove["dish"], menu, allow_zero=fresh_mode)
    for table in b.get("tables", []):
        extra = set(table) - {"id", "pos"}
        if extra:
            raise BadInput(f"trường lạ/chưa hỗ trợ trong tables.{table['id']}: {sorted(extra)}")
        if "pos" in table:
            _pos(f"tables.{table['id']}.pos", table["pos"], qb, axes=("x", "z"))
    customer_keys = {
        "id", "table_id", "dish_id", "state", "order_tick", "order_status",
        "patience_ticks_left", "eat_ticks_left", "reserved", "base_price", "tip",
    }
    stock = validate_item_list(b.get("stock", []), kinds) if fresh_mode else validate_items(b.get("stock", {}), kinds)
    reserved_totals = {}
    for c in b.get("customers", []):
        extra = set(c) - customer_keys
        if extra:
            raise BadInput(f"trường lạ/chưa hỗ trợ trong customers.{c['id']}: {sorted(extra)}")
        if not isinstance(c.get("table_id"), str) or c["table_id"] not in known:
            raise BadInput(f"customers.{c['id']}: table_id phải là bàn có thật")
        if "dish_id" in c and (not isinstance(c["dish_id"], str) or c["dish_id"] not in menu):
            raise BadInput(f"customers.{c['id']}: dish_id không có trong menu")
        if "state" in c and c["state"] not in {"waiting", "eating"}:
            raise BadInput(f"customers.{c['id']}: state không hợp lệ")
        if "order_status" in c and c["order_status"] not in {"reserved", "assigned", "unfulfillable", "served"}:
            raise BadInput(f"customers.{c['id']}: order_status không hợp lệ")
        for key in ("order_tick", "patience_ticks_left", "eat_ticks_left"):
            if key in c:
                _nonneg_int(f"customers.{c['id']}.{key}", c[key])
        if "reserved" in c:
            if fresh_mode:
                reserved = c["reserved"]
                if (not isinstance(reserved, list)
                        or any(not isinstance(iid, str) or not iid for iid in reserved)
                        or len(reserved) != len(set(reserved))):
                    raise BadInput(f"customers.{c['id']}.reserved v1.2 phải là mảng id cá thể duy nhất")
                continue
            if not isinstance(c["reserved"], dict):
                raise BadInput(f"customers.{c['id']}.reserved phải là object")
            try:
                reserved = validate_items(c["reserved"], kinds)
            except BadInput as e:
                raise BadInput(f"customers.{c['id']}.reserved: {e}")
            for kind, count in reserved.items():
                reserved_totals[kind] = reserved_totals.get(kind, 0) + count
                if "stock" in b and reserved_totals[kind] > stock.get(kind, 0):
                    raise BadInput("khách giữ chỗ vượt số nguyên liệu trong kho")
    if len(table_ids) != len(set(table_ids)):
        raise BadInput("hai khách cùng bàn")


def _check_dish_payload(name, dish, menu, allow_zero=False):
    if not isinstance(dish, dict) or set(dish) != {"order_id", "dish_id", "base_price"}:
        raise BadInput(f"{name}: payload món phải có đúng order_id, dish_id, base_price")
    if not isinstance(dish["order_id"], str) or not dish["order_id"]:
        raise BadInput(f"{name}.order_id không hợp lệ")
    if not isinstance(dish["dish_id"], str) or dish["dish_id"] not in menu:
        raise BadInput(f"{name}.dish_id không có trong menu")
    price = dish["base_price"]
    if isinstance(price, bool) or not isinstance(price, int) or price < (0 if allow_zero else 1):
        raise BadInput(f"{name}.base_price không hợp lệ")
