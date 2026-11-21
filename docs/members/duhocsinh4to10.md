# duhocsinh4to10 — phản tư cá nhân (≤ 200 từ)

- **Tôi đã làm:** Phụ trách `client/ui` và Demo Lead Phase 1 — nâng cấp [`chonoi/web/index.html`](../../chonoi/web/index.html) (HUD đầy đủ cho `gather` và `quan`, giỏ LIFO, mốc boa trên thanh kiên nhẫn, nhật ký sự kiện `H`, chống kẹt phím Telex), hợp nhất tương thích `--extra-content` và sprite atlas từ `7a5d7df`, thêm [`tests/test_ui_live.py`](../../tests/test_ui_live.py) và bằng chứng [`docs/proof/phase-1/ui-live-check.md`](../proof/phase-1/ui-live-check.md). *(Cập nhật link commit sau khi push.)*
- **Tôi đã review:** Đọc diff `f200323` (kickoff/contract) và `7a5d7df` (`--extra-content`, sprite atlas ở `live.py` và `index.html`) để gộp sạch không mất code đồng đội.
- **AI sai ở đâu và tôi phát hiện thế nào:** Bản nâng cấp đầu thiếu 2 nguyên liệu và 3 món mới từ `7a5d7df` và fallback sprite; phát hiện nhờ `git fetch` + `git show` trước khi merge.
- **Điều tôi học được:** Giữ `client/ui` chỉ đọc snapshot giúp tự do cải tiến HUD/đồ họa mà không phá Test Contract headless.
