# Bằng chứng Smoke & Determinism — Phase 3 (Contract v1.2)

## 1. Kết quả toàn bộ Unit & Integration Test + Contract Check

```text
Ran 140 tests in 33.610s

OK
MODE: Contract command
[PASS] gather: identical bytes
[PASS] quan: identical bytes
RESULT: PASS
```

## 2. Smoke `--mode day --days 1 --ticks 22200` trên Contract v1.2 (bật đủ `burn`, `snake`, `current`)

Lệnh chạy 2 lần độc lập với `--seed 7` và so sánh byte-for-byte:

```text
rc=0,0 time=2.121s same=True
end={'type': 'end', 'ticks': 22200, 'sim_tick': 22200, 'mode': 'day', 'state': 'finished', 'reason': 'days_complete', 'money': 0, 'earned': 0, 'reputation': 3.0, 'score': 300, 'days_completed': 1}
```

- Thời gian chạy 1 Ngày trọn vẹn (22.200 tick): **2.121s** (đạt yêu cầu `<= 20s`).
- Tính tất định (determinism): **byte-identical** (`same=True`).

## 3. Smoke bàn giao file kho v1.2 & từ chối kho đếm (mã thoát 2)

Đã kiểm chứng tự động trong `tests/test_phase3_v12.py::HeadlessAndDayV12Test`:
- `gather` cập bến ở frame 0 với `I1 (ca_linh, fresh: 100)` ghi file kho `{"items":[{"id":"I1","kind":"ca_linh","fresh":99.99166666666666}]}`.
- `quan --inventory inv.json --ticks 0` nạp đúng `stock` khớp từng `id`, `kind`, `fresh`.
- `quan --inventory old_count_dict.json --ticks 0` (với `{"items":{"ca_linh":1}}`) thoát **mã 2** trước khi ghi output.
- `--mode day --days 2` bàn giao cùng tick không hao thêm, Shop hiển thị mảng cá thể không hao, sang Ngày 2 cấp ID mới `I2` liên tục.
