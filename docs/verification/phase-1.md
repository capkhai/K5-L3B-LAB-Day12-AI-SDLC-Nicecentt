# Ma trận truy vết Phase 1

| AC | Cách kiểm chứng | Bằng chứng (link `docs/proof/phase-1/...`) | Kết quả (đạt / chưa đạt — ghi trung thực) |
|---|---|---|---|
| Lát 1 — oxy, ngạt và ngất (`gather`) | `tests/test_gather.py` (`GatherSlice1Test`): `dive`/`surface`, oxy trừ/hồi, ngạt tính ngay bước chạm 0, lên mặt nước reset đúng hạn ngạt, `faint` mất giỏ LIFO và kho rỗng | [Kiểm tra bản bàn giao](../proof/phase-1/gather-handoff.md), [Full run 77/77](../proof/phase-1/harness/20261121-114414-826854/test-output.txt) | Đạt |
| Lát 2 — hái nút, bắt cá, giỏ và cập bến (`gather`) | `tests/test_gather.py` (`GatherSlice2Test`): ưu tiên bến trước hái, hái mặt nước tie-break id + regrow, đủ chỗ cả đàn cá, cooldown chỉ đặt khi bắt thành công | [Kiểm tra bản bàn giao](../proof/phase-1/gather-handoff.md), [Full run 77/77](../proof/phase-1/harness/20261121-114414-826854/test-output.txt) | Đạt |
| Lát 3 — lịch sinh khách, giữ chỗ, `no_dish` và kiểm schema `scenario.py` | `tests/test_python_starter_units.py` (`test_quan_customer_reservation_and_patience`, `test_quan_customer_spawn_and_no_dish`) + `tests/test_smoke_p1.py` | [Full run 77/77](../proof/phase-1/harness/20261121-114414-826854/test-output.txt) | Đạt |
| Lát 4 — PRD F: tương tác bếp/bàn, ưu tiên khoảng cách/bếp/id, nấu/bưng/phục vụ, tip, uy tín, đóng ca | `tests/test_quan_service.py` (28 test unit + headless) | [Log test lát 4](../proof/phase-1/chur04-tests.txt), [Fixture & kết quả](../proof/phase-1/chur04-service.md), [Output JSONL](../proof/phase-1/chur04-service-output.txt) | Đạt |
| Giao diện chơi thử & HUD (`client/ui`) | `tests/test_ui_live.py` (4 test) + `tests/test_live.py` (HTTP server thật) | [Kiểm chứng UI](../proof/phase-1/ui-live-check.md), [Full run 77/77](../proof/phase-1/harness/20261121-114414-826854/test-output.txt) | Đạt |
| Contract v1.0 & tính tất định byte-giống-byte (`gather` + `quan`) | `python .agents/skills/prepare-proof/prepare_proof.py` + `tests/test_smoke_p1.py` (20 test hộp đen) | [Báo cáo Harness & SHA-256](../proof/phase-1/harness/20261121-114414-826854/report.md) | Đạt (`gather` & `quan` trùng SHA-256) |
| PO — chốt câu hỏi theo PRD-0 | Đối chiếu toàn văn PRD-0 | [clarify #1–#8](../clarify.md) | Đạt (đã chốt toàn bộ #1–#8) |
| Harness AI & quản lý nhóm (`AGENTS.md`, ≥ 2 skill, `TEAM.md`) | `python tools/check_team.py` + chạy thật 2 skill `check-contract` và `prepare-proof` | [Báo cáo Harness](../proof/phase-1/harness/20261121-114414-826854/report.md) | Đạt (`OK: 6 thành viên`, 2 skill hoạt động) |

## Đánh giá ngắn
- **Yêu cầu đã đạt:** Toàn bộ 4 lát kỹ thuật (`gather`, `quan_customers`, `quan_service`, `scenario`, `client/ui`) và 2 skill harness đã tích hợp lên `main`, chạy đạt **77/77 unittest** trong `5.025s` (gồm cả `test_live.py` và `test_ui_live.py`), hai chế độ headless `gather` và `quan` đạt tính tất định byte-giống-byte (SHA-256 khớp tuyệt đối).
- **Chưa hoàn thiện / cần chỉnh cho Phase 2:**
  - Phân bố commit theo cá nhân chưa đều ở cuối Phase 1 (`thanhhy98` chưa có commit, commit của `nhungvo631-stack` bị ghi nhận tác giả `unknown` do chưa cấu hình `git config user.name/email`). Cần khắc phục ngay đầu Phase 2 để đủ ≥ 3 commit/người.
  - Cần bổ sung thêm dòng nhật ký AI (`docs/ai-usage-log.md`), standup (`docs/standup.md`) và phản tư cá nhân (`docs/members/<handle>.md`) cho các thành viên còn lại trong các phase tiếp theo.
