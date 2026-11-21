# Quán Ăn Chợ Nổi — Release `v1.0.0` (Team Nicecentt)

Bản phát hành hoàn chỉnh của **Quán Ăn Chợ Nổi** theo **Test Contract `v1.3`** (Day 12 — AI SDLC).

## Điểm mới nổi bật
- **Đầy đủ vòng chơi 5 Ngày:** `DayIntro → Lặn & Hái → EveningIntro → Mở Quán → DayResult → Shop → Summary`, kèm Pause toàn cục (`Esc`/`P`) và nâng cấp Bình Oxy / Áo Phao.
- **Độ tươi & kho cá thể (Contract v1.2+):** theo dõi từng cá thể `{id, kind, fresh}`, hao tươi chính xác bằng `Fraction` ở ngưỡng `fresh < 30`, giữ chỗ theo id (tươi nhất trước, hòa theo id), nhả & giữ lại đúng 1 lần khi hàng ươn, chốt giá `floor(menu_price * avg_fresh / 100)`, từ chối kho đếm cũ bằng mã thoát `2`.
- **3 phần mở rộng (`extensions: ["burn", "snake", "current"]`):** Dòng nước lũ (`current`), Rắn Hổ Mây `M3` (`snake`) và Cháy món (`burn`).
- **Benchmark & Soak (Contract v1.3):**
  - `python3 -m chonoi.bench --seed 42 --duration 30 --out bench.json` → **680.55 avg FPS**, **304.91 1% low FPS**, **10.07 ms load** (`1280×720`).
  - `python3 -m chonoi.soak --seed 7 --days 10 --out soak.json` → **10/10 Ngày, 0 crash, 4.68s**, tất định 100%.
- **Khả năng tiếp cận (Accessibility):** đủ 3 cảnh báo bằng chữ & biểu tượng (`🐊 THỦY QUÁI!`, `🫧 OXY SẮP HẾT!` / `💨 HẾT HƠI!`, `💢 KHÁCH SẮP GIẬN!`) và **Chế độ tương phản cao** (phím `C` hoặc nút `🌓 Tương phản`).
- **Sáng tạo của nhóm:** `--extra-content` (tắt ở headless) với nguyên liệu/món miền Tây mở rộng và bộ sprite màu nước + animation bơi 6 khung hình.

## Cách chạy nhanh (≤ 3 lệnh, không cần `pip install`)
Yêu cầu **Python 3.10+** và trình duyệt web hiện đại:

```bash
unzip chonoi-v1.0.0.zip && cd chonoi-v1.0.0
python3 -m chonoi.live --mode day
```

Hoặc từ repo sạch:
```bash
git clone https://github.com/capkhai/K5-L3B-LAB-Day12-AI-SDLC-Nicecentt.git
cd K5-L3B-LAB-Day12-AI-SDLC-Nicecentt
python3 -m chonoi.live --mode day
```

## Kiểm chứng
- **143 / 143** unit & integration tests PASS (`31.756s`).
- `check-contract` PASS (`gather` & `quan` byte-identical).

## Giới hạn đã biết
- Chưa cài đặt hai mở rộng tùy chọn phụ là `reservations` và `leaderboard` / phụ đề SFX (nhóm 6 người đã hoàn thành 3/2 mở rộng tối thiểu: `burn`, `snake`, `current`).
- `tests/test_live.py` cần quyền mở cổng loopback cục bộ (`127.0.0.1`), không chạy được trong môi trường sandbox chặn socket; toàn bộ 143 test còn lại (bao gồm `test_ui_live.py`) chạy ổn định không cần mạng.
- Bản phản tư cá nhân của 2 thành viên (`nhungvo631-stack`, `VThanh-Huy`) cần được các thành viên tự bổ sung vào `docs/members/`.
