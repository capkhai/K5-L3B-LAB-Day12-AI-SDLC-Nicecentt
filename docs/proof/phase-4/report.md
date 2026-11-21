# Báo cáo Kiểm chứng & Artifact — Phase 4 (`v1.0.0`, Contract `v1.3`)

## 1. Regression toàn hệ thống (Phase 1–4) + Contract Check

```text
Ran 144 tests in 26.155s

OK
MODE: Contract command
[PASS] gather: identical bytes
[PASS] quan: identical bytes
RESULT: PASS
```

## 2. Artifact Benchmark có render (`docs/proof/phase-4/bench.json`)

Lệnh: `python3 -m chonoi.bench --seed 42 --duration 30 --out docs/proof/phase-4/bench.json`

```json
{"avg_fps":930.22,"p1_low_fps":438.81,"frames":27907,"measured_s":30.0,"load_ms":18.81}
```

- Cảnh đo mới: buổi sáng lõi (`gather`), độ tươi v1.2+, cá bơi, Cá Sấu Năm Chèo `M1` & Rắn Hổ Mây `M3`, sóng mặt nước, bọt nước và HUD trên framebuffer RGB `1280×720`; Út Sen đứng yên ở bến `[2, 0]`, làm nóng 3s + đo 30s.

## 3. Artifact Soak 10 Ngày (`docs/proof/phase-4/soak.json`)

Lệnh: `python3 -m chonoi.soak --seed 7 --days 10 --out docs/proof/phase-4/soak.json`

```json
{"days":10,"days_completed":10,"crashes":0,"results":[{"day":1,"earned":43,"reputation":3.2,"score":343},{"day":2,"earned":43,"reputation":3.2,"score":343},{"day":3,"earned":86,"reputation":3.4,"score":386},{"day":4,"earned":129,"reputation":3.6,"score":429},{"day":5,"earned":129,"reputation":3.6,"score":429},{"day":6,"earned":172,"reputation":3.8,"score":472},{"day":7,"earned":172,"reputation":3.8,"score":472},{"day":8,"earned":215,"reputation":4.0,"score":615},{"day":9,"earned":258,"reputation":4.2,"score":658},{"day":10,"earned":258,"reputation":4.2,"score":658}],"duration_s":6.876}
```

- Đã xác minh hai lần chạy độc lập trong `tests/test_phase4_v13.py` cho cùng `days_completed=10`, `crashes=0` và `results` giống hệt nhau.

## 4. Bản đóng gói phát hành (`tools/build_release.py`)

- `dist/chonoi-v1.0.0.zip` (`3,907,274` bytes)
- `dist/chonoi-v1.0.0.tar.gz` (`3,895,614` bytes)
- Kiểm tra chạy từ clone sạch: chỉ cần `git clone` → `cd` → `python3 -m chonoi.live --mode day` (3 lệnh, chỉ dùng thư viện chuẩn Python 3.10+).
