# Bàn giao gather Phase 1

Kiểm tra trong worktree tách từ `2ae7f6e` với dữ liệu contract v1.0 và bản sửa luật gather.

- Suite unittest chạy 70 test, kết quả OK. Trên Windows, đặt `PYTHONPATH=tests;.` và thay launcher `python3` bằng `sys.executable` trong helper của tiến trình test.
- `python .agents/skills/check-contract/check_contract.py --local-python` xác nhận JSONL giống từng byte khi chạy lại cả gather và quan.
- `python tools/check_team.py` nhận đủ 6 thành viên.
- Điều chỉnh kỳ vọng cũ theo các mục 1–4 trong `docs/clarify.md`. Khi đàn cần 3 ô và giỏ còn 2, headless phát `hold_full`, giữ cả hai đàn tại hiện trường và cooldown bằng 0. Oxy chạm 0 ở tick 2 thì ngạt lần đầu ở tick 61. Nếu nổi lên đúng lúc sắp ngạt thì được hồi oxy.
