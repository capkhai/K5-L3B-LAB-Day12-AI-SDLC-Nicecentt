# Phase 3 — Lát 3: Quán / chur04

Ngày kiểm chứng: 21/11/2026. Baseline `16ec94c`, nhánh `2A202603873_VuVanChu`. Người dùng chọn lát Quán và tự commit.

## Kết quả

- **32 test mới đạt, 136/136 test toàn repo đạt.** [Log đầy đủ](tests.txt).
- Kho vật lý giữ id/kind/fresh và cả hàng ươn; giữ chỗ theo id, không trùng đơn, lấy tươi nhất rồi id nhỏ.
- Hao tươi đúng đầu bước Quán; tất cả spoiled theo id trước chín/cháy/interact. Hàng fresh=30 ươn ở bước 1; fresh=30.25 chạm 30 ở tick 60 và ươn ở tick 61. Không phát spoiled lặp lại.
- Đơn có hàng vừa ươn nhả toàn bộ phần giữ rồi thử cấp lại công thức, không giữ một phần và không lấy phần của đơn chưa bị ảnh hưởng. Thiếu thì unfulfillable và tiếp tục chờ.
- Nấu tiêu đúng cá thể, event items theo kind/id, giá được chốt sau hao tươi; phục vụ/boa/thanh toán dùng giá đã chốt. Burn có thể giữ và nấu lại; không hoàn hàng đã dùng. Pause không hao tươi.
- Hai output runner cùng seed/input giống từng byte. [Run 1](quan-run1.txt), [run 2](quan-run2.txt). SHA-256: `93471dddd7369d08a8473bb7e2e63070a634097beb9ff56281fd25fae1a689d3`.
- Skill nhóm check-contract đã chạy --local-python: gather/quan legacy tất định, PASS. Không tuyên bố đây là kiểm CLI v1.2.
- Test cũ không bị sửa. Suite cũ chạy bằng launcher Python hiện có trên Windows thay alias python3 trong tiến trình kiểm; assertion và manifest giữ nguyên.

## Giả định giá — cần giữ rõ khi review

Ticket đính kèm thiếu công thức giá. Người dùng cho phép tự đề xuất. Triển khai **floor(giá menu × fresh trung bình / 100)** (100 đọc từ freshness.initial). Đây không phải trích dẫn PRD hay trả lời giảng viên. Chi tiết các giả định nằm trong [clarify](../../../clarify.md).

Trong ca mẫu, C1 giữ I1 fresh=30. Bước 1: I1 ươn, C1 giữ lại I2, sau đó nấu I2 ở fresh=79.99583333333334, chốt giá 47. Giao đủ kiên nhẫn được boa 9, thu 56; reputation=3.2, score=356.

| Tick | Sự kiện |
|---|---|
| 1 | spoiled(I1), cook_started(I2, base_price=47) |
| 361 | dish_ready, dish_picked |
| 571 | served(base_price=47, tip=9) |
| 1171 | paid(amount=56), quan_end |

## Chạy lại

```powershell
python -m unittest discover -s tests -p test_quan_freshness.py -v
```

Để chạy lại ca bằng API runner (cùng mô phỏng mà headless/live sử dụng), từ gốc repo:

```powershell
@'
import json
from pathlib import Path
from chonoi.runner import run
p = Path('docs/proof/phase-3/chur04')
tuning = json.loads((p / 'tuning.json').read_text(encoding='utf-8'))
scenario = json.loads((p / 'scenario.json').read_text(encoding='utf-8'))['quan']
frames = json.loads((p / 'inputs.json').read_text(encoding='utf-8'))['frames']
run('quan', tuning, scenario, 7, frames, 1200, 'quan-freshness.jsonl', 360)
'@ | python -
```

[Tóm tắt JSON](summary.json), [tuning fixture](tuning.json), [scenario](scenario.json), [inputs](inputs.json).

## Phạm vi chưa ghép

Đây là bằng chứng Quán qua Session/runner API. Manifest gốc còn 1.0; schema file kho v1.2, CLI chọn schema theo version, Gather, day/Shop, HUD và đặt trước thuộc các lát khác, chưa được xác nhận ở đây. Chưa có kiểm file gather → quan bằng schema mới hoặc smoke day v1.2. `tuning.freshness` là điểm bật adapter Quán trong lúc tích hợp; không tự nhận toàn Phase 3 đã hoàn tất.

Chưa stage, commit, push hoặc tag. Bằng chứng thuộc working tree, không giả nhận đã chạy trên commit bàn giao/tag.
