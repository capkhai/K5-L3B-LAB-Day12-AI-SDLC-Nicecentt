# Standup giữa phase (mỗi người một dòng, 2–3 phút)

| Phase | Người | Đã xong | Sắp làm | Vướng gì |
|---|---|---|---|---|
| 1 | `capkhai` | Chốt kickoff (`TEAM.md`, kế hoạch, hợp đồng), cài đủ Lát 1 & Lát 2 `chonoi/sim/gather.py` khớp PRD-0 + `tests/test_gather.py`, giải quyết conflict gộp `nhungvo` & `duhocsinh` lên `main`. | Chốt bằng chứng tổng hợp + tag `phase-1`, triển khai tiếp Phase 2 (cá bơi/sinh). | Nhánh `nhungvo` ban đầu lệch schema với `chur04`, đã đồng bộ xong và pass toàn bộ test. |
| 1 (cập nhật công việc 21/11/2026, không ghi nhận cuộc họp thực tế) | `chur04` | Lát 4 + 28 test + bằng chứng; clarify đã đối chiếu PRD | Bàn giao Nhung tích hợp lịch khách, QA review trên main | Lát 3 chưa có lịch sinh khách/validation schema đầy đủ; tránh giảm timer/dọn đơn hai lần; chưa commit/push/tag mới |
| 2 (cập nhật kỹ thuật 21/11/2026, không ghi nhận cuộc họp) | `chur04` | Backend day/Shop/pause/quán + burn; 104 test đạt và proof CLI trên fixture | Ghép cấu hình/Gather của Nhung/Khải và UI của Đạt, QA kiểm lại main | Manifest chung còn 1.0; ca proof tắt cá tự động, chưa kiểm cá/quái/FPS; chưa commit/push/tag mới |
