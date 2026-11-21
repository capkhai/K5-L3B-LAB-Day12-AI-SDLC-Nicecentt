# thanhhy98 — phản tư cá nhân (≤ 200 từ)

- **Tôi đã làm:** Phụ trách QA Lead Phase 1 — chạy toàn bộ `unittest`, chạy `check-contract` và `prepare-proof`, xác minh determinism byte-giống-byte của `gather`/`quan`, lưu báo cáo và log vào [`docs/proof/phase-1/harness/20261121-115821-788296/`](../proof/phase-1/harness/20261121-115821-788296/report.md), đồng thời đối chiếu matrix [`docs/verification/phase-1.md`](../verification/phase-1.md).
- **Tôi đã review:** Mặt QA của Phase 1 gồm test gather, quan, scenario, smoke/integration, UI và Test Contract; không sửa luật mô phỏng hoặc contract.
- **AI sai ở đâu và tôi phát hiện thế nào:** AI không thay số liệu hay khoanh vùng kết quả; mọi kết luận đều dựa trên mã exit thực tế, test log và SHA-256 trong thư mục proof.
- **Điều tôi học được:** Bằng chứng handover cần vừa xanh, vừa được truy vết: test output + snapshot determinism + liên kết matrix mới là phần bắt buộc.

## Phase 2

- **Tôi đã làm:** Chạy regression P1/P2 đầy đủ, smoke `day`, kiểm determinism hai tiến trình và tích hợp kho gather → quan. Khi suite chặn bởi `NameError` trong constructor `GatherSim`, đã xác nhận traceback và vá điểm khởi tạo thiếu tham số trước khi chạy lại.
- **Tôi đã review:** Kết quả `111/111 unittest`, hai lần chạy `day` trùng SHA-256, full-day 22.200 tick trong `0.422347 s`, và hai tiến trình kho khớp.
- **AI sai ở đâu và tôi phát hiện thế nào:** Không giả nhận manifest/engine đã hoàn thành v1.1; bằng chứng backend chỉ dùng fixture `random_fish=false` và ghi rõ chưa kiểm cá/quái/UI/manifest chung.
- **Điều tôi học được:** QA phải tách regression khả thi khỏi phần chưa tích hợp, lưu kết quả thực tế và không thay test chỉ để làm suite xanh.

## Phase 3

- **Tôi đã làm:** Phụ trách QA Lead Contract v1.2; đối chiếu smoke bàn giao kho cá thể, ngưỡng độ tươi `fresh=30`, kho đếm cũ và bài kiểm tra hai Ngày.
- **Tôi đã review:** Toàn bộ regression P1–P3, `check-contract`, smoke 2 tiến trình và determinism của `gather`/`quan`; truy vết kết quả trong `docs/verification/phase-3.md`.
- **AI sai ở đâu và tôi phát hiện thế nào:** Không coi manifest đã đổi là bằng chứng gameplay đã xanh; chỉ chốt PASS khi test, smoke và proof thực tế đều khớp Contract v1.2.
- **Điều tôi học được:** Bảng truy vết phải ghi riêng AC, lệnh, artifact và kết quả thực tế để người khác có thể tái hiện.

## Phase 4

- **Tôi phụ trách:** QA/Verification cho Contract v1.3 và phát hành `v1.0.0`.
- **Tôi đã làm:** Chạy regression P1–P4, kiểm `test_phase4_v13.py`, xác minh benchmark/soak và đối chiếu artifact đóng gói.
- **Tôi đã review:** Manifest v1.3, bench `1280×720`, soak 10 Ngày, cảnh báo/UI accessibility và các bằng chứng trong `docs/proof/phase-4/`.
- **AI sai ở đâu và tôi phát hiện thế nào:** Không thay test hay contract để biến lỗi thành PASS; mọi kết luận chỉ dựa trên exit code, JSON và test log thực tế.
- **Điều tôi học được:** Chốt release chỉ khi đủ test, determinism, benchmark, soak và package artifact cùng xanh.
