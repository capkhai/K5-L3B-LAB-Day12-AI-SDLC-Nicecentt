# Kế hoạch Phase 4 — Phát hành `v1.0.0` (Contract `v1.3`)

- **Thời lượng:** 30 phút (2:30–3:00) · **Hạn tag `phase-4` & GitHub Release `v1.0.0`:** 3:00.

## Phân công vai trò

| Vai | Phụ trách | Phạm vi & Sản phẩm |
|---|---|---|
| **Bench / Soak / Release** | `capkhai` | Nâng `game.contract.json` v1.3 (`bench_cmd`, `soak_cmd`), xây `chonoi/bench.py` (render `1280×720`), `chonoi/soak.py` (10 ngày lặp D1–D5), `tools/build_release.py`, `LICENSE`, `README.md`, `CHANGELOG.md`, gắn tag `phase-4` & Release `v1.0.0`. |
| **UI / Accessibility** | `duhocsinh4to10` (hỗ trợ tích hợp: `capkhai`) | 3 cảnh báo chữ/biểu tượng (Thủy quái, Oxy sắp hết/cạn, Khách sắp giận) + Chế độ tương phản cao (High Contrast) trong `chonoi/web/index.html`. |
| **QA / Verification** | `thanhhy98` (hỗ trợ chạy xác minh: `capkhai`) | Chạy regression P1–P3 + `test_phase4_v13.py`, lưu artifact `docs/proof/phase-4/{bench.json,soak.json,report.md}`, lập ma trận `docs/verification/phase-4.md`. |
| **Retro / Clarify / Harness** | `chur04`, `nhungvo631-stack`, `VThanh-Huy` | Rà hành động retro P2 trong `docs/retro.md`, cập nhật `docs/clarify.md`, `docs/ai-usage-log.md`, `AGENTS.md`, hoàn thiện phản tư cá nhân `docs/members/<handle>.md`. |
