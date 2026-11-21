"""File kho v1.0 (Contract G): {"items": {id: số nguyên >= 0}}.

Đọc: từ chối sai schema / id lạ / số âm (BadInput -> mã 2).
Ghi: bỏ mục bằng 0, qua file tạm cùng thư mục rồi thay thế, byte-ổn-định.
"""

import json
import math
import os
import tempfile

from .errors import BadInput
from .freshness import make_item, public_item
from .ids import sort_by_id

KINDS_P1 = ("ca_loc", "ca_linh", "bong_dien_dien", "bong_sung")
KINDS_P2 = (*KINDS_P1, "ca_keo", "keo_neo")


def validate_items(items, kinds=KINDS_P2):
    if not isinstance(items, dict):
        raise BadInput("items phải là object")
    out = {}
    for k, v in items.items():
        if k not in kinds:
            raise BadInput(f"nguyên liệu lạ: {k}")
        if isinstance(v, bool) or not isinstance(v, int) or v < 0:
            raise BadInput(f"số lượng không hợp lệ cho {k}: {v!r}")
        if v > 0:
            out[k] = v
    return out


def validate_item_list(items, kinds=KINDS_P2) -> list:
    """Kiểm mảng cá thể v1.2: [{id, kind, fresh}], id duy nhất, fresh hữu hạn trong [0, 100]."""
    if not isinstance(items, list):
        raise BadInput("items v1.2 phải là mảng cá thể [{id, kind, fresh}]")
    seen = set()
    out = []
    for idx, it in enumerate(items):
        if not isinstance(it, dict) or set(it) != {"id", "kind", "fresh"}:
            raise BadInput(f"items[{idx}]: phải có đúng 3 khóa id, kind, fresh")
        ident, kind, fresh = it["id"], it["kind"], it["fresh"]
        if not isinstance(ident, str) or not ident:
            raise BadInput(f"items[{idx}].id phải là chuỗi khác rỗng")
        if ident in seen:
            raise BadInput(f"items: id trùng {ident}")
        seen.add(ident)
        if not isinstance(kind, str) or kind not in kinds:
            raise BadInput(f"items.{ident}: nguyên liệu lạ {kind!r}")
        if isinstance(fresh, bool) or not isinstance(fresh, (int, float)) or not math.isfinite(fresh) or not (0 <= fresh <= 100):
            raise BadInput(f"items.{ident}.fresh phải là số hữu hạn trong [0, 100]")
        out.append(make_item(ident, kind, fresh))
    return out


def read_inventory(path: str, kinds=KINDS_P2, version=None):
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError) as e:
        raise BadInput(f"không đọc được file kho {path}: {e}")
    if not isinstance(data, dict) or set(data.keys()) != {"items"}:
        raise BadInput("file kho chỉ được có khóa gốc 'items'")
    if version in ("1.2", "1.3"):
        return validate_item_list(data["items"], kinds)
    return validate_items(data["items"], kinds)


def hold_to_items(hold: list):
    """Khoang -> object đếm (v1.0/v1.1) hoặc mảng cá thể sắp theo id (v1.2)."""
    if hold and isinstance(hold[0], dict):
        return [public_item(it) for it in sort_by_id(hold)]
    counts = {}
    for k in hold:
        counts[k] = counts.get(k, 0) + 1
    return {k: counts[k] for k in sorted(counts)}


def write_inventory(path: str, items):
    if isinstance(items, list):
        payload = [public_item(it) for it in sort_by_id(items)]
    else:
        payload = {k: items[k] for k in sorted(items) if items[k] > 0}
    d = os.path.dirname(os.path.abspath(path))
    fd, tmp = tempfile.mkstemp(prefix=".inv-", suffix=".tmp", dir=d)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            json.dump({"items": payload}, f, ensure_ascii=False, separators=(",", ":"))
            f.write("\n")
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise
