# TICKET-03 – Change Request “Mùa Nước Nổi” (Phase 3)

> **35 phút (1:55–2:30)** · **Test Contract v1.2** · Hạn đẩy tag `phase-3`: **2:30**.

Tháng Tám âm lịch, nước lũ về, cá linh nhiều. Trời nóng làm nguyên liệu mau ươn. Khách hàng muốn biết độ tươi của từng nguyên liệu, từ lúc Út Sen lấy được đến khi đưa vào bếp. **[THAY THẾ]** đánh dấu các luật đổi so với bản đang chạy.

---

## 1. Lõi (mọi nhóm) – Độ tươi

### [THAY THẾ] Kho đếm theo loại → kho cá thể

```json
{"items":[{"id":"I1","kind":"ca_linh","fresh":100},{"id":"I2","kind":"ca_loc","fresh":97.5}]}
```

- File có đúng khóa gốc `items`, giá trị là mảng cá thể `{id, kind, fresh}`. Kho rỗng là `{"items":[]}`. `id` là chuỗi duy nhất, khác rỗng; `kind` thuộc danh mục nguyên liệu; `fresh` hữu hạn trong `[0,100]`. Cấp `I1, I2, ...` theo thứ tự vào giỏ, tiếp tục tăng xuyên pha và Ngày, kể cả khi cá thể trước đó đã dùng hoặc bỏ. LIFO khi mất hàng vẫn theo thứ tự vào giỏ.
- Bên đọc chọn schema theo `contract_version`. Contract v1.2 trả mã `2` cho file kho đếm hoặc sai schema, kind lạ, id trùng, `fresh` ngoài miền. Kho quán nhận nguyên số lượng, id và độ tươi, kể cả hàng ươn. Sức chứa giỏ chỉ áp lên giỏ.
- `gather --inventory-out` ghi đúng một lần khi có `gather_end`. Dùng file tạm cùng thư mục rồi thay thế nguyên tử. Ngất ghi kho rỗng. Nếu chạm giới hạn `--ticks` trước `gather_end`, giữ nguyên đường dẫn đích. Xuất file theo id, đủ độ chính xác khi đọc lại để giữ giá trị và nhánh ở ngưỡng `30`. `gather_end.data.inventory` theo cùng schema.
- Trong `day`, bàn giao trong cùng tick chuyển pha, hàng không hao thêm, ca quán chạy từ bước sau. Nếu có Chợ Chú Sáu, hàng mua nhập riêng vào kho quán Ngày kế với `fresh: 100`, tách khỏi `gather_end.inventory` và dùng id mới. Hàng thô ở Shop hoặc chờ nhập không hao tươi. Khi người chơi bán, lấy cá thể chưa ươn tươi nhất của loại, hòa theo id.

### Độ tươi, giữ chỗ và giá

| Quy tắc | Cách xử lý |
|---|---|
| **Hàng mới** | `fresh = 100` lúc bắt/hái, bắt đầu hao từ bước sau. |
| **Hao tươi** | Giỏ giảm `0.5/s`, kho quán giảm `0.25/s` kể cả hàng đang giữ chỗ. Mỗi giây `60 tick`, kẹp đáy `0`. Pause dừng hao tươi. Món chín không hao. |
| **Ươn** | `fresh < 30`, vẫn chiếm ô, không dùng nấu. Phát `spoiled` đúng một lần khi đi từ `≥ 30` xuống `< 30`. Nếu nhiều cá thể cùng vượt ngưỡng, phát theo id. So ngưỡng trước làm tròn. |
| **[THAY THẾ] Giữ theo lượng → giữ theo id** | Mỗi loại trong công thức lấy các cá thể khả dụng tươi nhất, hòa theo id. Nếu phần giữ có cá thể vừa ươn, nhả **toàn bộ** phần giữ của đơn và thử giữ lại **đúng một lần**. Xử lý các đơn bị ảnh hưởng theo `order_tick` rồi id bàn. Không đủ thì đơn thường chuyển `unfulfillable`, khách chờ tới hạn. |
| **[THAY THẾ] Giá niêm yết → giá theo tươi** | Khi bắt đầu nấu, tiêu đúng các id đang giữ và chốt `base_price = floor(giá niêm yết × trung bình fresh của các cá thể dùng / 100)`. Nếu đủ điều kiện boa, áp `floor(tiền món × 0.2)` trên giá đã chốt. Điểm vẫn là `earned + 100 × floor(reputation)`. |
| **HUD** | Cho người chơi đọc được độ tươi hoặc nhận ra hàng ươn bằng số, thanh, nhãn hoặc biểu tượng. |

> **Gợi ý số học chính xác:** dùng `240` đơn vị mỗi điểm tươi (`100.0 = 24000`, ngưỡng ươn `< 7200`, trừ `2` đơn vị/tick ở `gather` và `1` đơn vị/tick ở `quan`) để không sai số ở ngưỡng `30` và phép `floor`.

### Thứ tự trong tick

- **Gather:** Đồng hồ, cooldown, hồi nút và độ tươi của hàng có sẵn ở đầu bước → lịch dòng lũ nếu bật → bơi, oxy và ngạt → Lao nếu có, rồi thủy quái/hit → bến trước hái → bắt cá rồi ảnh nếu có → xét hết giờ, nếu còn giờ mới cập nhật cá và sinh thêm. Rơi hàng theo LIFO. Khi ngất, bỏ toàn bộ phần còn lại theo LIFO rồi phát `faint`, `gather_end(fainted)`.
- **Quán:** Đồng hồ và timer → hao tươi kho thô, phát hết `spoiled` theo id rồi mới xử lý giữ chỗ bị ươn → xét món chín/cháy nếu có theo id bếp → di chuyển và tối đa một tương tác → thanh toán, kiên nhẫn/đóng ca → nếu còn giờ, xử lý đặt trước nếu có rồi tới khách thường. Giao đúng tick kiên nhẫn chạm `0` vẫn hợp lệ. Giao đúng tick kết thúc ca được trả ngay.

### Contract v1.2

**[THAY THẾ]** Đặt `contract_version: "1.2"`. Thêm `freshness: {"initial": 100, "gather_decay_per_s": 0.5, "quan_decay_per_s": 0.25, "spoiled_below": 30}`.

- **Scenario:** `gather.hold` và `quan.stock` là mảng cá thể. Trong `day`, Ngày đầu giữ nguyên id trong mẫu `gather.hold`, các Ngày kế cấp id mới theo thứ tự mảng với `kind`/`fresh` ban đầu. `customers[].reserved` là mảng id cá thể. Id vật lý duy nhất giữa các nơi chứa. Phần giữ phải trỏ tới cá thể chưa ươn trong kho, đủ công thức và không dùng chung với đơn khác. Bỏ `reserved` cho đơn `reserved` thì cấp theo `order_tick` rồi id bàn, lấy tươi nhất rồi id nhỏ. Sai hoặc mâu thuẫn → mã `2`. Payload món giữ cấu trúc, `base_price` là giá đã chốt theo fresh.
- **JSONL:** Snapshot `hold`, `stock` (quán và Shop) và `customers[].reserved` theo schema trên. `cook_started.data.items` là mảng cá thể sắp theo `kind` rồi `id`. `lost` trong `monster_hit` / `faint` là mảng cá thể theo thứ tự bỏ LIFO. Event mới `spoiled` có `item_id, kind, location` (`hold` / `stock`). Dung sai quan sát độ tươi `±0.01`. Tick của event biên phải chính xác.

---

## 2. Mở rộng (chọn sau khi lõi v1.2 chạy ổn)

Nhóm 6 người cần **ít nhất 2 mục** tính cả buổi lab, khai mã ở `extensions` trong `game.contract.json` và ghi test/bằng chứng trong `README.md`:
- `current` (Dòng nước lũ): `t = 1800·k`, báo trước `t - 120`, dài `480` tick, `+1.5 m/s` theo `+x`/`-x` khi `d ≥ 10`.
- `reservations` (Khách đặt trước): 2 đơn `R1, R2` mỗi Ngày, giữ bàn `30s`, giá `×1.5`, phạt `-1` uy tín khi fail.
- *(Cùng các mục từ Phase 2: `burn`, `snake`, `weapon`, `net`, `vendor`, `ca_ho`.)*

---

## 3. Định nghĩa hoàn thành (DoD)

- [ ] Contract v1.2 bàn giao kho cá thể qua file và trong `day`. Kho đếm trả mã `2`. Id, độ tươi, hàng ươn, giữ chỗ, giá và JSONL đúng luật.
- [ ] HUD cho thấy độ tươi hoặc hàng ươn. Có test qua ngưỡng, thử giữ lại khi hàng vừa ươn, chốt giá và bàn giao.
- [ ] Có ghi tác động, quyết định đổi schema và thứ tự tích hợp giữ `main` chạy được. Các lát đã tích hợp trong fork chung, có bằng chứng đóng góp của từng người.
- [ ] `CHANGELOG.md` ghi breaking change, regression còn hiệu lực đạt, test thay đổi có lý do. `docs/verification/phase-3.md` và bằng chứng khớp commit gắn tag. Ghi chép làm rõ và nhật ký AI đã cập nhật.
- [ ] Nếu làm mở rộng, có test và bằng chứng cho từng mục.
- [ ] Đẩy `phase-3` trỏ tới commit bàn giao trên `main` chậm nhất **2:30**.
