# Day 12 — AI SDLC: Quán Ăn Chợ Nổi

> **Làm theo nhóm 4–6 người** · Dùng AI để xây game 2D qua **4 phase** trong **3 giờ**: Út Sen lặn bắt cá, hái rau trên mặt nước rồi tối mở quán phục vụ khách.
> **Yêu cầu từng phase mở đúng mốc giờ tại lab board:** **[Chợ Nổi Lab](https://claude.ai/artifact/E35v787wSx2wDgPTNhMVDg)** (cần đăng nhập claude.ai; có trợ giảng AI cho từng phase).

## Bắt buộc (chỉ có thế)

Cách làm việc kỹ thuật là **tự do** (push thẳng, nhánh + PR, pair, có hay không CI…). Cái bắt buộc:

1. **Một repo chung:** trưởng nhóm **fork** repo này, đặt tên `K5-L3B-LAB-Day12-AI-SDLC-<ten-nhom>`, thêm mọi thành viên làm collaborator (*Settings → Collaborators*, quyền Write) và để repo **public** (giảng viên xem được, không cần mời).
2. **Cả nhóm cùng commit** bằng tài khoản GitHub của mình, mỗi người **≥ 3 commit có nội dung** (làm cặp thì ghi `Co-authored-by:`).
3. **Điền [`TEAM.md`](TEAM.md):** danh sách thành viên + thỏa thuận làm việc nhóm; sửa `team_size` trong [`game.contract.json`](game.contract.json). Commit của người không có trong `TEAM.md` không được tính.
4. **Gắn tag** `phase-1` … `phase-4` đúng hạn; chạy được tại từng tag.
5. **Ghi chép tối thiểu:** `docs/verification/phase-n.md`, `docs/clarify.md`, `docs/ai-usage-log.md`, `docs/retro.md`, `docs/members/<handle>.md`.

## Bắt đầu nhanh

```bash
git clone <fork-của-nhóm> && cd <fork-của-nhóm>
PYTHONPATH=tests:. python3 -m unittest discover -s tests -v        # smoke test
python3 -m chonoi.live --mode gather                                # chơi thử trên trình duyệt (tùy chọn)
```

Game cần chế độ **headless** theo Test Contract (`python3 -m chonoi.headless --mode gather|quan …`) để được chạy và chấm tự động. **Công nghệ không ràng buộc**: khung Python trong `chonoi/` chỉ là gợi ý, chi tiết ở [`docs/STARTER.md`](docs/STARTER.md).

## Tự do sáng tạo

Ngoài phần đề yêu cầu, nhóm được **thêm** nhân vật, loài cá/cây, sinh vật, món, bản đồ, cơ chế, câu chuyện, đồ họa, âm nhạc… với ba điều kiện: **không phá phần cố định** (tắt ở headless), ghi mục **"Sáng tạo của nhóm"** trong README của nhóm, và **làm lõi đúng trước**.

## Sáng tạo của nhóm

Bản trình duyệt có thêm cá kèo, cá rô đồng, kèo nèo và rau muống, cùng ba công thức cá kèo kho tộ, canh chua cá rô kèo nèo và rau muống xào. Dữ liệu nằm trong `chonoi/extra_content.json`. Bật bằng `python -m chonoi.live --mode gather --extra-content` hoặc dùng `--mode quan` để nạp thực đơn mở rộng.

## Mở rộng đã hoàn thành (`extensions`)

Nhóm **Nicecentt** (6 thành viên — yêu cầu tối thiểu 2 mở rộng) đã hoàn thành **3 mở rộng**, khai mã tại gốc [`game.contract.json`](game.contract.json) (`"extensions": ["burn", "snake", "current"]`):

1. **`current` — Dòng nước lũ (Phase 3):** Lịch chu kỳ `1800 * k` tick, cảnh báo trước 120 tick (`current_warning`), chảy 480 tick (`current_start`), cộng lực `1.5 m/s` theo trục `x` khi độ sâu đầu bước `d >= 10` (chặn mép, không cộng vào `player.vel`), kết thúc `current_end(elapsed)` ở `t + 480` hoặc `current_end(phase_end)` trước `faint`/`gather_end` khi ca kết thúc sớm. Hỗ trợ `gather.random_current` và `gather.current_direction` trong scenario.
2. **`snake` — Rắn Hổ Mây (`M3`, Phase 2):** Xuất hiện từ Ngày 1 ở `[72, 14] ↔ [76, 14]`, `d ∈ [8, 20]`, tuần tra `1.0 m/s`, đuổi `3.5 m/s` trong `<= 8 m` khi `d >= 8`, rời đuổi khi `> 16 m` hoặc `d < 8`, dùng chung luật va chạm/LIFO/recoil.
3. **`burn` — Cháy món (Phase 2):** `quan.burn_s: 20` (`1200` tick). Đúng `1200` tick vẫn bưng được; từ tick `1201` phát `dish_burnt`, trả bếp về `idle`, không hoàn nguyên liệu và thử giữ chỗ lại ngay (`reserved` nếu còn hàng, `unfulfillable` nếu thiếu).

- Test tự động: [`tests/test_extensions.py`](tests/test_extensions.py) và [`tests/test_chur04_phase2.py`](tests/test_chur04_phase2.py) (`Quan11`).
- Bằng chứng chi tiết: [`docs/proof/phase-3/extensions.md`](docs/proof/phase-3/extensions.md).

## Lịch 3 giờ

| Mốc | Phase | Hạn tag |
|---|---|---|
| 0:00 | Phase 1 (PRD-0) | `phase-1` trước 1:00 |
| 1:00 | Phase 2 | `phase-2` trước 1:55 |
| 1:55 | Phase 3 | `phase-3` trước 2:30 |
| 2:30 | Phase 4 | `phase-4` + Release `v1.0.0` trước 3:00 |

Hết giờ mỗi phase thì gắn tag rồi đi tiếp; chỗ chưa xong ghi trung thực trong bằng chứng.

## Đánh giá (100 điểm)

| Hạng mục | Điểm |
|---|---|
| Test tự động ẩn (headless, gồm kiểm tra lại phase trước) | 25 |
| Làm việc nhóm (một repo chung, chia việc, tích hợp, đổi yêu cầu) | 25 |
| Kiểm chứng & bằng chứng | 15 |
| Harness AI (AGENTS.md, skill, nhật ký dùng AI) | 10 |
| Đánh giá & retro | 10 |
| Chất lượng sản phẩm (đúng yêu cầu, mở rộng/sáng tạo) | 10 |
| Demo | 5 |

## Quy định

- Dùng AI thoải mái; **không sao chép repo của nhóm khác**; bằng chứng phải thật.
- Nhân vật, bối cảnh là bản gốc của lab; asset ngoài chỉ dùng CC0/CC-BY/MIT hoặc tự tạo, ghi nguồn trong `CREDITS.md`. Không commit API key, token, `.env`.
