# CHANGELOG

## [1.2.0] — Phase 3: Mùa Nước Nổi (`phase-3`)

### Breaking Changes (Contract `1.1` → `1.2`)
- **`game.contract.json`**:
  - Nâng `"contract_version"` lên `"1.2"`.
  - Thêm khối `tuning.freshness`: `{"initial": 100, "gather_decay_per_s": 0.5, "quan_decay_per_s": 0.25, "spoiled_below": 30}`.
  - Khai báo 3 mở rộng tại gốc manifest: `"extensions": ["burn", "snake", "current"]`.
- **Schema file kho (`--inventory` / `--inventory-out`) và `gather_end.data.inventory`**:
  - Đổi từ kho đếm `{"items": {"ca_loc": 1}}` sang kho cá thể `{"items": [{"id": "I1", "kind": "ca_loc", "fresh": 100}]}` (kho rỗng `{"items": []}`).
  - Ở `contract_version: "1.2"`, file kho đếm v1.0/v1.1 bị từ chối với **mã thoát 2**.
- **Schema Scenario & Snapshot**:
  - `gather.hold`, `quan.stock`, Shop `stock` đổi sang mảng cá thể `[{"id", "kind", "fresh"}]`.
  - `quan.customers[].reserved` đổi từ map đếm sang mảng id cá thể `["I1", ...]`.
  - `cook_started.data.items` đổi sang mảng cá thể đã tiêu, sắp theo `(kind, id)`.
  - `monster_hit.data.lost` và `faint.data.lost` đổi sang mảng cá thể theo thứ tự bỏ LIFO.
  - Thêm event `spoiled` (`{item_id, kind, location}` với `location` là `"hold"` hoặc `"stock"`).
- **Luật mới**:
  - Hàng mới có `fresh = 100`, hao `0.5/s` (`2/240`/tick) ở `gather` và `0.25/s` (`1/240`/tick) ở `quan` (kể cả hàng đang giữ chỗ); pause dừng hao tươi; món chín và hàng ở Shop không hao.
  - `fresh < 30` là ươn (so chính xác bằng `Fraction` trước làm tròn), phát `spoiled` đúng 1 lần theo thứ tự id; đơn có cá thể giữ vừa ươn nhả toàn bộ phần giữ và thử giữ lại đúng 1 lần theo `(order_tick, table_id)`, thiếu thì chuyển `unfulfillable`.
  - Khi bắt đầu nấu, chốt `base_price = floor(menu_price * avg_fresh / 100)` bằng số học chính xác; boa tính trên `base_price` đã chốt.

### Mở rộng đã bật (`extensions`)
- **`current`** (Dòng nước lũ): `tuning.gather.current`, scenario `random_current` / `current_direction`, events `current_warning`, `current_start`, `current_end`.
- **`snake`** (Rắn Hổ Mây `M3`): `tuning.gather.monsters.species.ran` + `M3` từ Ngày 1.
- **`burn`** (Cháy món): `tuning.quan.burn_s: 20` (`1200` tick).

### Hướng dẫn cập nhật fixture (v1.1 → v1.2)
- Đổi `gather.hold: ["ca_loc"]` → `[{"id": "I1", "kind": "ca_loc", "fresh": 100}]`.
- Đổi `quan.stock: {"ca_loc": 1}` → `[{"id": "I1", "kind": "ca_loc", "fresh": 100}]`.
- Đổi `customers[].reserved: {"ca_loc": 1}` → `["I1"]` (hoặc bỏ trống để tự cấp cá thể tươi nhất, hòa theo id).
- File kho rỗng đổi `{"items": {}}` → `{"items": []}`.

### Các test cũ cập nhật vì luật mới (có lý do)
- `tests/test_smoke_p1.py`: cập nhật `contract_version() in ("1.1", "1.2")`, đổi fixture `hold`/file kho rỗng và kỳ vọng `test_time_ends_gather_and_keeps_hold` + `test_inv_01_gather_writes_inventory_quan_reads_it` sang schema cá thể v1.2.
- `tests/test_gather.py`, `tests/test_monsters.py`, `tests/test_extensions.py`, `tests/test_ui_live.py`, `tests/test_python_starter_units.py`: đổi fixture `hold`/`stock`/`reserved` sang mảng cá thể v1.2 và kiểm `lost` theo mảng cá thể LIFO + `M3` khi bật `snake`.
- `tests/test_quan_service.py`: `Service` tách `freshness` khỏi bản sao tuning để giữ nguyên 25 test đơn vị P1/P2; `HeadlessService` cập nhật kịch bản headless sang v1.2 (ở tick 1 hao `1/240` → `base_price = 59`, `tip = 11`, `money = 70`, `score = 370`).
- `tests/test_chur04_phase2.py`: `phase2_contract()` bỏ `freshness` để giữ nguyên bộ regression v1.1 (40+ test).
