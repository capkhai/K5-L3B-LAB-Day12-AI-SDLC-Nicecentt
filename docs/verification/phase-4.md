# Bảng xác minh Phase 4 — Phát hành `v1.0.0` (Contract `v1.3`)

- **Nhánh bàn giao:** `main` (tag `phase-4` & GitHub Release `v1.0.0`)
- **Contract:** `contract_version: "1.3"`, `bench_cmd: "python3 -m chonoi.bench"`, `soak_cmd: "python3 -m chonoi.soak"`, `extensions: ["burn", "snake", "current"]`.
- **Tổng hợp kiểm thử:** **143 / 143** test **PASS** (`31.756s`) + `check-contract` **PASS** (`gather` & `quan` identical bytes).

## 1. Bảng truy vết AC Phase 4 (`AC-P4-xx`)

| Mã AC | Yêu cầu | Kiểm thử / Bằng chứng | Kết quả |
|---|---|---|---|
| `AC-P4-01` | Manifest `contract_version: "1.3"`, khai đúng `bench_cmd` và `soak_cmd`; giữ nguyên gameplay/tuning/kho/JSONL v1.2 | `game.contract.json`, `chonoi/contract.py`, `tests/test_phase4_v13.py::test_contract_v13_declares_bench_and_soak_cmds` | **PASS** |
| `AC-P4-02` | Benchmark có render `1280×720` (`--seed 42 --duration 30`), làm nóng 3s + đo 30s, xuất đủ 5 trường JSON (`avg_fps`, `p1_low_fps`, `frames`, `measured_s`, `load_ms`) | `docs/proof/phase-4/bench.json` (`avg_fps=680.55`, `p1_low_fps=304.91`, `frames=20417`, `measured_s=30.001`, `load_ms=10.07`), `tests/test_phase4_v13.py` | **PASS** |
| `AC-P4-03` | Soak headless 10 Ngày (`--seed 7 --days 10`), lặp kế hoạch D1–D5 ở Ngày 6–10, `days_completed=10`, `crashes=0`, tất định mọi trường gameplay | `docs/proof/phase-4/soak.json` (`days_completed=10`, `crashes=0`, `earned=258`, `reputation=4.2`, `score=658`, `duration_s=4.68`), `tests/test_phase4_v13.py` | **PASS** |
| `AC-P4-04` | Đủ 3 cảnh báo bằng chữ & biểu tượng (Thủy quái gần, Oxy sắp hết/cạn, Khách sắp giận) + Chế độ tương phản cao (High Contrast) | `chonoi/web/index.html`, `tests/test_ui_live.py::test_index_html_covers_phase2_screens_warnings_and_assets` | **PASS** |
| `AC-P4-05` | Chạy từ clone sạch trong `<= 3` lệnh (macOS/Linux); `README.md` đủ yêu cầu môi trường, điều khiển, test, headless, bench, soak | `README.md` (`git clone` → `cd` → `python3 -m chonoi.live --mode day`), stdlib Python 3.10+ không cần `pip install` | **PASS** |
| `AC-P4-06` | Regression P1–P3 còn hiệu lực đạt toàn bộ (`gather`, `quan`, `day`, `freshness v1.2`, `burn`/`snake`/`current`, `ui_live`, `check-contract`) | **143 / 143** test PASS (`31.756s`) + `check-contract` PASS (`docs/proof/phase-4/report.md`) | **PASS** |
| `AC-P4-07` | Đóng gói phát hành, Release notes, `CHANGELOG.md` đủ 4 phase, rà `CREDITS.md` và `LICENSE` | `tools/build_release.py` (`dist/chonoi-v1.0.0.zip`, `.tar.gz`), `docs/release-notes-v1.0.0.md`, `CHANGELOG.md`, `CREDITS.md`, `LICENSE` | **PASS** |
| `AC-P4-08` | Retro cuối rà hành động P2, cập nhật `docs/clarify.md`, `docs/ai-usage-log.md`, `AGENTS.md`, `docs/members/capkhai.md` | `docs/retro.md`, `docs/clarify.md`, `docs/ai-usage-log.md`, `AGENTS.md`, `docs/members/` | **PASS** |

## 2. Báo cáo chỉ số Benchmark & Soak (`docs/proof/phase-4/`)

| Hạng mục | Chỉ số đo được | Mốc báo cáo | Đánh giá |
|---|---|---|---|
| `avg_fps` (`1280×720`, 30s) | **680.55 FPS** | `>= 60 FPS` | **ĐẠT** |
| `p1_low_fps` (1% chậm nhất) | **304.91 FPS** | `>= 30 FPS` | **ĐẠT** |
| `load_ms` | **10.07 ms** | `<= 10.000 ms` | **ĐẠT** |
| Soak 10 Ngày (`--seed 7`) | **10/10 ngày, 0 crash, 4.68s** | `days_completed=10, crashes=0` | **ĐẠT** |
