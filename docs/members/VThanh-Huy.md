# Đóng góp cá nhân — Võ Thanh Huy

- **Mã học viên:** 2A202603879
- **GitHub:** `VThanh-Huy`
- **Nhóm:** Nicecentt
- **Vai trò:** Người 6 — Scrum / Release / Harness / Ops
- **Phạm vi:** Phase 1 và Phase 2

## 1. Công việc đã thực hiện

### Phase 1 — Thiết lập quy trình và Harness

- Xây dựng và cập nhật `AGENTS.md`, quy định cách AI Agent phối hợp trong nhóm.
- Xây dựng skill `check-contract` để chạy kiểm thử headless cho `gather`, `quan` và kiểm tra tính tất định (determinism).
- Xây dựng skill `prepare-proof` để thu thập kết quả unit tests, JSONL, log và SHA-256.
- Kiểm tra kết quả thực tế trước khi bàn giao.
- Tạo PR #4 cho phần công việc Phase 1, đã được merge vào `main`.

### Phase 2 — Nâng cấp cho Test Contract v1.1

- Đồng bộ nhánh `VoThanhHuy` với phiên bản Phase 2 của nhóm.
- Nâng cấp `check-contract` hỗ trợ `--phase2`, kiểm tra thêm chế độ `day`.
- Nâng cấp `prepare-proof` để chạy kiểm thử và tạo bằng chứng Phase 2.
- Bổ sung tùy chọn `--local-python` cho môi trường Windows.
- Kiểm tra Gather, Quan và Day với cùng seed để xác nhận determinism.
- Kiểm tra Day kết thúc đúng trạng thái và thời gian chạy không vượt quá 20 giây.
- Cập nhật tài liệu của hai skill, `AGENTS.md`, nhật ký sử dụng AI và standup.

## 2. Kết quả kiểm thử

Trên Test Contract v1.1:

| Nội dung | Kết quả |
|---|---|
| Unit Tests | 120/120 PASS |
| Gather determinism | PASS |
| Quan determinism | PASS |
| Day determinism | PASS |
| Day hoàn thành đúng trạng thái | PASS |
| Giới hạn thời gian 20 giây | PASS |
| Launcher theo Test Contract | PASS |
| Overall Harness | PASS |

**Bằng chứng:**

`docs/proof/phase-2/harness/20261121-153002-657367/`

Bộ bằng chứng gồm `report.md`, `test-output.txt`, JSONL và log thực thi.

Lưu ý: Harness PASS không đồng nghĩa toàn bộ Acceptance Criteria đã đạt. QA vẫn cần đánh giá từng yêu cầu.

## 3. Khó khăn và cách xử lý

**Vấn đề 1 — Python trên Windows**

Test Contract sử dụng `python3`, trong khi Windows ban đầu không nhận diện đúng lệnh này, dẫn đến mã lỗi `9009` và 31/120 unit tests thất bại.

**Cách xử lý:** Cấu hình môi trường để `python3` gọi được Python 3.14.2, sau đó chạy lại toàn bộ kiểm thử. Kết quả cuối cùng đạt 120/120 tests PASS, không cần sửa Test Contract.

**Vấn đề 2 — Quản lý phiên bản Git**

Nhánh cá nhân ban đầu ở phiên bản Phase 1, trong khi `main` đã tích hợp Phase 2.

**Cách xử lý:** Đồng bộ nhánh cá nhân với `origin/main`, kiểm tra các file thay đổi và chỉ stage những file thuộc phạm vi Harness/Ops.

**Vấn đề 3 — Kiểm chứng kết quả AI**

Khi xây dựng các script, một số thay đổi ban đầu chưa hoàn chỉnh và cần sửa sau khi chạy kiểm thử.

**Cách xử lý:** Sử dụng traceback, unittest, kết quả thực thi và `git diff` để đối chiếu thay vì tin hoàn toàn vào code do AI tạo ra.

## 4. Các file đóng góp chính

- `AGENTS.md`
- `.agents/skills/check-contract/SKILL.md`
- `.agents/skills/check-contract/check_contract.py`
- `.agents/skills/prepare-proof/SKILL.md`
- `.agents/skills/prepare-proof/prepare_proof.py`
- `docs/ai-usage-log.md`
- `docs/standup.md`
- `docs/proof/phase-2/harness/20261121-153002-657367/`

## 5. Bài học rút ra

- Test Contract là cơ sở chung giúp các thành viên tích hợp và kiểm thử độc lập.
- Determinism giúp kiểm tra cùng đầu vào có tạo ra kết quả giống nhau hay không.
- Bằng chứng kiểm thử phải xuất phát từ lần chạy thực tế.
- Khi sử dụng AI để viết code, cần tự đọc, kiểm tra và xác nhận kết quả.
- Cần kiểm tra kỹ các file trước khi commit để tránh ảnh hưởng công việc của thành viên khác.