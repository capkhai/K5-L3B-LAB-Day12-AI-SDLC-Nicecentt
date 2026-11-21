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
- Rà lại hành động Phase 2: đã làm chưa? vì sao?
- Điều tốt / điều tệ:
- Số liệu: số commit theo người, cách đọc code của nhau, token theo người:
- Một lần AI sai và cách nhóm phát hiện:
- Nếu làm lại, đổi gì:
