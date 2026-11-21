# Retro nhóm

## Phase 2 (nhanh)
- Ghi nhận kỹ thuật của chur04 (21/11/2026), chưa thay biên bản retro nhóm thực tế.
- Điều tốt: Session dùng chung cho headless/live; fixture cho phép kiểm đổi pha, Shop và pause trước khi các lát khác tích hợp; 104 test đạt.
- Điều vướng: manifest chung còn v1.0 trong khi backend cần dữ liệu v1.1; không thể dùng kết quả fixture để xác nhận toàn engine và UI. Giao diện giữa các lát phải ghi rõ để tránh xử lý timer hai lần.
- 1 hành động cho Phase 3: chur04 phối hợp Nhung chốt các điểm nối trong docs/clarify.md và cùng QA chạy lại day mặc định trên cấu hình/main đã tích hợp trước khi xác nhận tag tiếp theo.

## Phase 3 (nhanh — sau lần đổi schema kho v1.1 → v1.2)
- **Điều tốt:** Viết ADR (`docs/adr/0001-phase3-item-freshness-v12.md`) và hỗ trợ song song hai phiên bản trong `chonoi/freshness.py` + `chonoi/inventory.py` trước khi bật `contract_version: "1.2"` giúp nhánh `main` không bao giờ vỡ trong lúc chuyển đổi. Dùng số học chính xác `Fraction` giúp tránh hoàn toàn sai số dấu phẩy động ở ngưỡng `fresh < 30` và phép `floor` chốt giá. Hoàn thành thêm 3 mở rộng (`burn`, `snake`, `current`) với 140/140 test PASS và `--mode day --days 1` đạt `2.121s` (byte-tất định).
- **Điều vướng:** Breaking change từ kho đếm sang kho cá thể ảnh hưởng trực tiếp tới 8 file test P1/P2 và giao diện `index.html`/`live.py`, phải rà soát từng fixture và giải trình rõ trong `CHANGELOG.md`. Ngoài ra, việc ghép nhánh của các thành viên vào `main` ở phút cuối dễ bị trễ nhịp nếu mỗi người đẩy gần hạn tag.
- **1 hành động cho Phase 4:** Trước khi đóng gói Release `v1.0.0` và tag `phase-4`, gom đầy đủ bài phản hồi thành viên (`docs/members/nhungvo631-stack.md`, `docs/members/VThanh-Huy.md`), chốt retro tổng kết nhóm và chạy lại toàn bộ bộ test + smoke live/headless trên cùng commit bàn giao.

## Phase 4 (cuối)
- **Rà lại hành động đã chốt ở Phase 2:**
  - *Hành động P2:* `chur04` phối hợp `nhungvo631-stack` chốt các điểm nối trong `docs/clarify.md` và cùng QA chạy lại `--mode day` trên `main` đã tích hợp trước khi gắn tag.
  - *Kết quả rà soát:* **Đã làm phần lớn.** Các điểm nối `Session`/`DaySim`/`QuanSim`/`GatherSim` đã được ghi rõ trong `docs/clarify.md` và tích hợp xanh tại tag `phase-2` (`e274616`), đồng thời kiểm chạy trọn 1 Ngày headless 22.200 tick dưới 3s (byte-tất định). Tuy nhiên ở Phase 3, việc gom PR chéo giữa các nhánh vẫn còn lệch nhịp sát hạn tag nên người tích hợp phải tự hoàn thiện nốt v1.2 trên `main` để kịp bàn giao.
- **Điều tốt:**
  - Kiến trúc tách lõi mô phỏng thuần Python stdlib (`chonoi/`) khỏi giao diện Web Canvas (`chonoi/web/index.html`) giúp cả headless, live, benchmark `1280×720` và soak 10 Ngày đều chạy ổn định trên mọi hệ điều hành mà không cần `pip install`.
  - Viết ADR và bộ test hộp đen + đơn vị tăng dần qua 4 phase (**77 → 119 → 140 → 143 test PASS**) kèm `check-contract` giúp phát hiện lỗi ngay khi chạm vào biên số liệu.
  - Hoàn thành đủ 3/2 mở rộng (`burn`, `snake`, `current`), benchmark đạt **680.55 avg FPS / 304.91 p1_low / 10.07 ms load**, soak 10 Ngày đạt **10/10 ngày, 0 crash**.
- **Điều tệ / cần sửa:**
  - Hai thành viên (`nhungvo631-stack`, `VThanh-Huy`) chưa hoàn tất file phản tư `docs/members/<handle>.md` trên `main`, và có 2 commit ban đầu chưa cấu hình đúng git user (`unknown`).
  - Breaking change kho cá thể v1.2 ảnh hưởng nhiều test cũ; nếu có helper tạo fixture theo phiên bản ngay từ Phase 1 thì tốc độ migrate sẽ nhanh hơn gấp đôi.
- **Số liệu đóng góp & sử dụng AI:**
  - Commit trên `main` (trước commit chốt `phase-4`): `capkhai` (30+), `Hai Duong` / `nhungvo631-stack` (9), `DATIENNGUYEN` / `duhocsinh4to10` (5), `Nguyen Minh Thanh` / `thanhhy98` (4), `VThanh-Huy` (3), `chuvv` / `chur04` (3 — cộng nhánh `2A202603873_VuVanChu` đã hoàn thành thêm lát quán v1.2).
  - Cách đọc code của nhau: đối chiếu diff PR trực tiếp khi xử lý conflict (`gather.py`, `quan_service.py`, `index.html`, `scenario.py`) và chạy chung bộ `unittest` + `check-contract`.
  - Token ước tính (ghi nhận tại `docs/ai-usage-log.md`): `capkhai` ~250k token (Antigravity Gemini qua 4 phase), `duhocsinh4to10` ~100k token (Antigravity Gemini), `chur04` (Codex) & `thanhhy98` (Copilot SDK) không hiển thị bộ đếm token.
- **Một lần AI sai và cách nhóm phát hiện:**
  - Ở Phase 3 khi viết test kiểm chứng từng tick cho mở rộng dòng nước lũ (`current`), `GatherSim.snapshot()` trả trực tiếp tham chiếu danh sách `self.pos` thay vì `list(self.pos)`, khiến mọi snapshot lưu lại ở các tick trước đều bị ghi đè thành vị trí cuối cùng (`50.100`). Bộ test biên `tests/test_extensions.py` phát hiện ngay lỗi này ở tick 9; nhóm sửa bằng cách sao chép `list(self.pos)`/`list(self.vel)` trong cả `GatherSim.snapshot()` và `QuanSim.snapshot()`.
- **Nếu làm lại, đổi gì:**
  - Thiết lập quy tắc merge nhỏ theo chu kỳ 15 phút/lần ngay từ đầu mỗi phase (không dồn PR ở 5 phút cuối), chuẩn hóa cấu hình `git config user.name/email` ngay lúc kickoff, và tách helper tạo fixture kho/scenario để đổi schema mượt hơn.
