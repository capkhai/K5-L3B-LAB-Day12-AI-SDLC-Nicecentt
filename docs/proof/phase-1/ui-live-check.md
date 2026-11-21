# Bằng chứng kiểm chứng UI chơi trực tiếp — Phase 1 (`client/ui`, `duhocsinh4to10`)

## Phạm vi kiểm chứng
- File nâng cấp: [`chonoi/web/index.html`](../../../chonoi/web/index.html) (chỉ đọc snapshot từ `GET /state`, gửi input qua `POST /input` và `POST /restart`, không chứa logic mô phỏng, tắt hoàn toàn ở `chonoi.headless`).
- Tích hợp tương thích ngược với commit `7a5d7df` (`--extra-content` và sprite atlas `/assets/cho-noi-sprites.png` có fallback vector khi chưa có ảnh).

## Tính năng HUD đã hiển thị
- **`gather` (Buổi sáng):** đồng hồ đếm ngược, thanh Oxy (phân vùng mặt nước / dưới nước / cạn oxy + thanh đếm ngạt `zero_oxy_ticks`), tim Máu (`hp/hp_max`, trạng thái `invuln_ticks`), giỏ LIFO từng ô có đánh dấu đỉnh mới nhất + cảnh báo đầy giỏ, trạng thái nút hái (vòng đếm ngược mọc lại `regrow_ticks`), đàn cá (kèm sản lượng `fish_yield`), tọa độ & tốc độ, hồi chiêu `catch_cd_ticks`, gợi ý phím `[E]`/`[Space]`.
- **`quan` (Buổi tối):** đồng hồ ca, tiền / thu nhập / uy tín (5 sao) / điểm, món đang cầm trên tay (`hand`), trạng thái bếp (`idle`/`cooking` có thanh tiến độ/`ready` có `ready_ticks`/`burned`), bàn & khách (gọi món, thanh kiên nhẫn kèm mốc boa `tip_min_patience_ratio`, tiến độ ăn `eat_ticks_left`), kho nguyên liệu (gồm phần giữ chỗ `reserved` nếu có) và thực đơn nhanh (tự mở rộng thêm 3 món khi có `--extra-content`).
- **Tiện ích chung:** phím `e.code` chống kẹt bộ gõ tiếng Việt (Telex/UniKey), ngăn Nhật ký sự kiện (`H`), âm thanh Web Audio tùy chọn tắt mặc định (`M`), popup sự kiện nổi, modal tổng kết + nút Chơi lại (`R`).

## Kết quả chạy kiểm thử
- `python -m unittest tests.test_smoke_p1 tests.test_python_starter_units tests.test_team_check tests.test_ui_live -v`: **35/35 pass** (không phá Test Contract headless hay tính tất định).
- `python -m unittest tests.test_live -v`: **1/1 pass** (`LiveServerTest.test_state_input_and_clean_stop` kiểm chứng máy chủ HTTP thực phục vụ `/` và `/state`, nhận `/input`).
- `python tools/check_team.py`: `OK: 6 thành viên`.
- Script kiểm thử render JS trên Node v22 (giả lập Canvas2D & DOM cho snapshot `gather`, `quan`, `fainted`, `quan_end`, `--extra-content`, và nhập phím `KeyW` với `key="ư"`): **PASS toàn bộ**.
