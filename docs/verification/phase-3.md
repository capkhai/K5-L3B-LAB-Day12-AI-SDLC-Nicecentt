# Bảng xác minh Phase 3 — Mùa Nước Nổi (Contract v1.2)

- **Nhánh bàn giao:** `main` (tag `phase-3`)
- **Contract:** `contract_version: "1.2"`, `extensions: ["burn", "snake", "current"]`
- **Tổng hợp kiểm thử:** **140 / 140** unit & integration tests **PASS** (`33.610s`) + `check-contract` **PASS** (`gather` & `quan` identical bytes) + `--mode day --days 1 --ticks 22200` **PASS** (`2.121s`, byte-identical).

## 1. Bảng truy vết AC Phase 3 (Contract v1.2)

| Mã AC | Yêu cầu | Kiểm thử / Bằng chứng | Kết quả |
|---|---|---|---|
| `AC-P3-01` | Manifest `contract_version: "1.2"` + `tuning.freshness {initial:100, gather_decay_per_s:0.5, quan_decay_per_s:0.25, spoiled_below:30}` | `tests/test_extensions.py`, `chonoi/contract.py` | **PASS** |
| `AC-P3-02` | Schema kho cá thể `{"items":[{"id","kind","fresh"}]}`; file kho đếm v1.0/v1.1 trả mã thoát `2` | `tests/test_gather_v12.py`, `tests/test_phase3_v12.py::test_ticket03_smoke_file_handoff_and_count_dict_rejected_exit_2` | **PASS** |
| `AC-P3-03` | Hao tươi giỏ `0.5/s` (`2/240`/tick) và ngưỡng chính xác `fresh < 30` (bắt đầu `30` ươn ở bước 1; `30 + 2/240` chưa ươn ở bước 1) | `tests/test_gather_v12.py::test_gather_exact_threshold_30_and_boundary` | **PASS** |
| `AC-P3-04` | Hao tươi kho quán `0.25/s` (`1/240`/tick), phát hết `spoiled(location="stock")` theo thứ tự id trước khi xử lý giữ chỗ | `tests/test_phase3_v12.py::test_exact_threshold_30_spoils_by_id_order_and_boundary_stays_fresh` | **PASS** |
| `AC-P3-05` | Giữ chỗ theo id cá thể (tươi nhất trước, hòa theo id); cá thể giữ vừa ươn nhả toàn bộ và thử giữ lại đúng 1 lần theo `(order_tick, table_id)`, thiếu thành `unfulfillable` | `tests/test_phase3_v12.py::test_spoiled_reservation_releases_all_and_rereserves_once_by_order_key` | **PASS** |
| `AC-P3-06` | Chốt giá `base_price = floor(menu_price * avg_fresh / 100)` chính xác; `cook_started.data.items` sắp theo `(kind, id)`; boa tính trên `base_price` đã chốt | `tests/test_phase3_v12.py::test_auto_reserve_picks_freshest_then_smallest_id_and_locks_fresh_price`, `tests/test_gather_v12.py` | **PASS** |
| `AC-P3-07` | Rơi hàng `monster_hit` / `faint` theo LIFO dạng mảng cá thể; ngất ghi kho rỗng `{"items":[]}` | `tests/test_gather_v12.py`, `tests/test_gather.py`, `tests/test_monsters.py` | **PASS** |
| `AC-P3-08` | Pause dừng hao tươi ở cả `gather` và `quan` | `tests/test_phase3_v12.py::test_pause_freezes_freshness_in_gather_and_quan` | **PASS** |
| `AC-P3-09` | Smoke 2 tiến trình `gather --inventory-out → quan --inventory --ticks 0` khớp chính xác `id`, `kind`, `fresh` | `tests/test_phase3_v12.py::test_ticket03_smoke_file_handoff_and_count_dict_rejected_exit_2`, `docs/proof/phase-3/smoke-v12.md` | **PASS** |
| `AC-P3-10` | `--mode day` bàn giao kho cá thể trong cùng tick không hao thêm, Shop hiển thị kho thô không hao, Ngày 2+ cấp id mới liên tục, 22.200 tick `< 20s` và byte-tất định | `tests/test_phase3_v12.py::test_day_mode_v12_handoff_shop_no_decay_day2_new_ids_and_deterministic`, `docs/proof/phase-3/smoke-v12.md` | **PASS** |
| `AC-P3-11` | HUD hiển thị độ tươi (%) và cảnh báo hàng ươn (`ƯƠN`, `HÀNG ƯƠN`) ở cả `gather`, `quan` và `evening_intro` | `chonoi/web/index.html`, `tests/test_ui_live.py` | **PASS** |
| `AC-P3-12` | ADR phân tích tác động, `CHANGELOG.md` ghi breaking change + lý do đổi test, cập nhật `docs/clarify.md` & `docs/ai-usage-log.md` | `docs/adr/0001-phase3-item-freshness-v12.md`, `CHANGELOG.md`, `docs/clarify.md`, `docs/ai-usage-log.md` | **PASS** |

## 2. Mở rộng (`extensions` — 3/2 tối thiểu cho nhóm 6 người)

| Mã | Mở rộng | Kiểm thử / Bằng chứng | Kết quả |
|---|---|---|---|
| `EXT-01` | `current` — Dòng nước lũ (Phase 3) | `tests/test_extensions.py::CurrentExtensionTest`, `docs/proof/phase-3/extensions.md` | **PASS** |
| `EXT-02` | `snake` — Rắn Hổ Mây `M3` (Phase 2) | `tests/test_extensions.py::SnakeExtensionTest`, `tests/test_monsters.py` | **PASS** |
| `EXT-03` | `burn` — Cháy món `burn_s: 20` (Phase 2) | `tests/test_extensions.py::BurnExtensionRealContractTest`, `tests/test_chur04_phase2.py::Quan11` | **PASS** |

## 3. Lệnh kiểm chứng

```powershell
$env:PYTHONPATH="tests;."
python -m unittest tests/test_phase3_v12.py tests/test_extensions.py tests/test_gather_v12.py tests/test_gather.py tests/test_monsters.py tests/test_chur04_phase2.py tests/test_quan_service.py tests/test_smoke_p1.py tests/test_ui_live.py tests/test_python_starter_units.py tests/test_team_check.py
python .agents/skills/check-contract/check_contract.py
```
