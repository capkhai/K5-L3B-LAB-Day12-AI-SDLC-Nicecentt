# Clarify — câu hỏi và câu trả lời (PO ghi, cả nhóm dùng chung)

> PO: Vũ Văn Chủ (`chur04`). Đối chiếu ngày 21/11/2026 với toàn văn PRD-0 Phase 1 do người dùng cung cấp trong phiên làm việc. Các câu dưới đây đã có câu trả lời trực tiếp trong PRD; không ghi nhận là giảng viên/Anh Năm đã trả lời. Không còn giả định ở các câu #1–#8.

| # | Ngày giờ | Câu hỏi | Trả lời / giả định | Ai quyết |
|---|---|---|---|---|
| 1 | 21/11/2026 | **Gather — Bắt cá khi giỏ gần đầy:** nhận một phần hay từ chối cả đàn? | PRD F/Gather: phải nhận đủ yield; thiếu chỗ thì `hold_full`, giữ cá và cooldown, không thử đàn khác. | PRD-0 F; PO đối chiếu |
| 2 | 21/11/2026 | **Gather — Cooldown `catch`:** bắt trượt/đầy giỏ có hồi chiêu không? | Chỉ đặt cooldown sau khi bắt thành công. Bắt trượt/đầy giỏ không đặt cooldown. | PRD-0 F; PO đối chiếu |
| 3 | 21/11/2026 | **Gather — Oxy & ngạt:** đếm lúc oxy vừa về 0? nổi lên reset không? | Tăng ngạt ngay bước oxy vừa chạm 0; ngạt đầu ở t+59 nếu bắt đầu đếm từ 0. Nổi lên hồi oxy và reset ngạt ngay, kể cả đúng tick đáng lẽ ngạt. | PRD-0 F; PO đối chiếu |
| 4 | 21/11/2026 | **Gather — Schema sự kiện:** key chính xác là gì? | `dive/surface`: pos; `oxygen_empty`: oxygen_ticks:0; `choke`: hp; `faint`: cause:"choke",lost,hp:0; `gather`: node_id,kind,amount; `fish_caught`: fish_id,kind,yield; `hold_full`: action,node_id hoặc fish_id,required,free. `lost` theo LIFO. | PRD-0 E; PO đối chiếu |
| 5 | 21/11/2026 | **Quan — Khách chọn món & `no_dish`:** stream nào? có trừ uy tín khi thiếu món? | PRD không khóa tên stream, chỉ yêu cầu seeded RNG nhất quán, chọn đều từ các món đủ kho khả dụng, duyệt id món theo Unicode. Không có bàn thì bỏ lượt; có bàn nhưng không có món thì `no_dish` với data `{}`, không tạo khách/giữ chỗ, không giảm uy tín. Nhung chọn tên stream qua `Streams`. | PRD-0 E/F; PO đối chiếu; tên stream thuộc lát 3 |
| 6 | 21/11/2026 | **Quan — `interact` bếp/bàn:** thứ tự lấy đơn và có được nấu khi đang bưng? | Chọn đối tượng theo (khoảng cách, bếp trước bàn, id), tính cả mép; chọn rồi không tương tác được thì bỏ lượt. Bếp idle lấy đơn reserved cũ nhất theo order_tick rồi id bàn; không có điều kiện tay trống khi bắt đầu nấu. Bếp ready chỉ cho bưng nếu tay trống. Mỗi cạnh lên tối đa một tương tác. | PRD-0 F; PO đối chiếu |
| 7 | 21/11/2026 | **Quan — Tiền, tip & uy tín:** làm tròn và thời điểm cộng? | Chốt ở lúc phục vụ: floor(base_price × tip_rate) nếu tỷ lệ kiên nhẫn sau giảm timer đạt ngưỡng (bao gồm bằng); ngược lại tip=0. Phục vụ ở tick kiên nhẫn=0/hết ca vẫn được. Chỉ tip dương mới cộng tip_reputation khi thu tiền, kẹp min/max; không cộng uy tín khi vừa phục vụ. | PRD-0 E/F; PO đối chiếu |
| 8 | 21/11/2026 | **Scenario `quan`:** payload, khách, giữ chỗ và mâu thuẫn? | Món `{order_id,dish_id,base_price}`, order_id=id khách. Khách mặc định waiting/order_tick=0/order_status=reserved/kiên nhẫn đầy. Thiếu reserved thì cấp theo công thức, thứ tự order_tick rồi id bàn; stock gồm phần giữ. Assigned có đúng một món ở bếp hoặc tay, giữ rỗng; eating phải served, timer ăn dương và base_price,tip đã chốt. Unfulfillable còn waiting, giữ rỗng, không món. Mã 2 cho món/liên kết/trạng thái/timer sai, giữ sai/quá kho, cùng đơn ở tay và bếp. Lát 3 bổ sung kiểm schema đầy đủ ở scenario.py. | PRD-0 D; PO đối chiếu |

## Bàn giao lát 4 cho Nhung / QA

- Triển khai: `chonoi/sim/quan_service.py`; điều phối: `QuanSim.step()`. Không đổi `game.contract.json`, schema kho hoặc `docs/contracts/`.
- Thứ tự đã nối: tăng phase_tick và giảm ca → `advance_timers` (nấu/ăn/kiên nhẫn) → `ready_dishes` → di chuyển → một `interact` → `settle_customers` → `quan_end` nếu hết giờ. Lát 3 nối sinh khách ở cuối bước khi còn giờ; khách mới không được giảm timer hoặc tương tác ngay bước sinh.
- `prepare_customers` hiện cấp mặc định/giữ chỗ fixture và kiểm liên kết món để chạy được lát 4 độc lập. Nhung có thể chuyển phần chuẩn hóa sang `quan_customers.py`; không cấp giữ lần hai.
- `advance_timers` và `settle_customers` hiện đã giảm kiên nhẫn, xử lý bỏ đi/hủy món, nhả giữ thô và kẹp uy tín để các biên phục vụ/đóng ca đúng PRD. Khi tích hợp lát 3, gọi các hàm này đúng một lần mỗi bước. `discard_order` dùng chung để bỏ món khi khách rời, không hoàn nguyên liệu đã nấu.
- `cook_started`, `dish_ready`, `dish_picked` có stove_id,order_id,dish_id; bắt đầu nấu thêm items (mảng kind đã sắp),base_price. `served` có order_id,table_id,dish_id,patience_ticks_left,base_price,tip. `paid` có order_id,table_id,base_price,tip,amount,reason (finished_eating/closing).
- Đóng ca: khách ăn hết đúng bước đó trả với finished_eating; khách còn ăn (kể cả vừa phục vụ) trả với closing; khách waiting rời với closing và không bị trừ uy tín. Xử lý theo id bàn, sau đó mới quan_end; không sinh khách ở bước đóng ca.
- Test/bằng chứng: [chur04-service.md](proof/phase-1/chur04-service.md). Sinh khách tự động và kiểm toàn bộ schema scenario còn thuộc lát 3; chưa đánh dấu toàn Phase 1 hoàn tất.

## Phase 2 — PO đối chiếu TICKET-02 (21/11/2026)

Nguồn: [toàn văn ticket người dùng cung cấp](prd-phase-2.md). Các quyết định dưới đây dựa trực tiếp vào ticket, không ghi nhận đã trao đổi với giảng viên/Anh Năm.

| Vấn đề | Kết luận / căn cứ |
|---|---|
| Intro/result có chiếm tick headless không? | Không thêm pha gameplay intro/result. Mục 4.4 chỉ có gather/quan/shop; mục 4.5 đổi pha cùng tick, pha mới chạy từ bước sau. 180s + 180s + 600 tick Shop = 22.200 tick. UI của Đạt trình bày các màn giới thiệu/kết quả. |
| Khi nào một Ngày được tính xong? | Chỉ khi Shop đóng, kể cả Ngày cuối. `days_completed` tăng khi `shop_end`; đủ `--days` thì `days_complete`. |
| Pause xử lý buy và cạnh nút thế nào? | Xét pause trước. Bước vào pause chỉ tăng tick ngoài. InputPlayer vẫn cập nhật chốt, mọi cạnh/buy trong pause bị bỏ; giữ nút qua pause/đổi pha không sinh cạnh mới. Bước resume chạy gameplay ngay. |
| Buy gặp shop_done hoặc hết giờ cùng bước? | Mua trước rồi mới đóng Shop. shop_done thắng lý do time ở bước cuối. Mua trừ money, giữ earned/điểm; cấp hiển thị ngay, active_upgrades chỉ đổi khi dựng Ngày mới. |
| Kế hoạch có giới hạn số món bán không? | Không. Số suất chỉ tính mục tiêu thu gom; menu quán trong day lọc theo id món của kế hoạch rồi lọc tồn khả dụng. Mode quan độc lập dùng toàn menu cấu hình. |
| Chọn bàn ngẫu nhiên hay theo id? | Bàn trống id nhỏ nhất. Đã bỏ RNG chọn bàn và bỏ khóa reserved thừa trong event customer_arrived để khớp schema E của P1 còn hiệu lực. |
| Kho dư và fixture nhiều Ngày? | Stock dư hiển thị trong Shop rồi bỏ khi dựng Ngày mới. gather/quan là template được sao lại mỗi Ngày; hold khai trong fixture xuất hiện lại đúng template, không phải kho dư được giữ. |
| Fixture quán trong day kiểm lúc nào? | Cấm quan.stock/reputation ngay khi nạp. Khách/giữ chỗ/món được kiểm trên kho bàn giao và menu kế hoạch thật khi mở quán; lỗi mức này có thể xuất hiện sau khi output buổi sáng đã được ghi, đúng mục 4.3. |
| Cháy món: 1200 hay 1201? | Đúng 1200 vẫn bưng được; >1200 mới cháy. Xét theo id bếp trước di chuyển/interact, không hoàn nguyên liệu, thử giữ công thức lại ngay, có thể nấu lại cùng tick nếu được chọn. Mặc định burn_s=null; manifest phải khai extensions chứa burn mới nhận burn_s hữu hạn. |

### Điểm nối đã triển khai và phạm vi cần ghép

- `Session(..., days=1)` và `run(..., days=1)` giữ tương thích lời gọi P1. `Session` có tick, sim_tick, phase_tick, paused; snapshot trong day lấy phase_tick từ DaySim. `Session.initial_events()` trả day_start/day_plan/phase_start ở tick 0; headless tự ghi chúng trước snapshot 0.
- `InputState(..., buy=None)`, `BUTTONS_V11`, `load_frames(path, buttons=BUTTONS_V11)`; buy chỉ có ở frame khai báo. Giữ default loader V10 để không làm đổi nghĩa test P1 cũ; headless chọn bộ nút theo contract_version. `LiveInputs` hỗ trợ nút V11 và buy dùng một lần.
- `DaySim.current` là GatherSim/QuanSim hiện tại; `DaySim.phase` là gather/quan/shop. Snapshot Shop có stock, time_left_ticks và các trường chung cùng day/day_plan/upgrades/active_upgrades. Event đổi pha giữ phase/day cũ cho sự kiện kết thúc, phase/day mới cho sự kiện bắt đầu.
- **Đạt/UI:** mở rộng live CLI nhận mode day/days, lấy meta theo session.sim.phase (Shop dùng tuning.shop), đưa `session.initial_events()` vào event buffer khi reset và chuyển pause/shop_done/buy vào LiveInputs. UI chỉ đọc snapshot; không tạo tick gameplay cho intro/result, không gọi riêng sim.step bên ngoài Session. Chưa sửa live.py/index.html trong lát này.
- **Khải/Nhung:** GatherSim nhận thêm keyword `day=1`, đặt self.day trước khi dựng nội dung để init_monsters dùng đúng Ngày; day truyền số Ngày hiện tại. Ngoài điểm nối này không sửa oxy/bắt cá/cá bơi/quái. Chuẩn hóa theo ticket vẫn thuộc các lát Gather.
- **Nhung/Integrator:** giữ game.contract.json và inventory.py theo phân công; manifest ở working tree hiện vẫn 1.0. Fixture 1.1 chỉ nằm trong tests/fixtures và bản sao kiểm chứng, không thay cấu hình chung. Cần ghép fish_initial=8, 6 nguyên liệu/6 món, 2 bếp/4 bàn, day_plan/shop, validation monsters/age_ticks và engine Gather trước khi xác nhận chạy day mặc định.
- Có sửa nhỏ `contract.py` để đọc cả v1.0/v1.1 và kiểm dữ liệu day/shop/burn; `scenario.py` thêm điểm nối `validate_phase_block` và route day, suy nguyên liệu hợp lệ từ dữ liệu menu thay vì khóa 4 loại P1. Đây là phụ thuộc cần thiết để CLI/day chạy được, không thay schema kho hoặc hoàn thành hộ validation Gather v1.1 của Nhung.
- Bằng chứng và các giới hạn: [chur04 Phase 2](proof/phase-2/chur04/README.md). Giữ nhánh cá nhân hiện có `2A202603873_VuVanChu`; không tạo nhánh mới, commit, push hay tag.

## Phase 3 — lát 3 Quán (21/11/2026)

Người dùng xác nhận làm phần Quán: hao độ tươi, giữ chỗ bằng ID, thử giữ lại và giá chốt. Bản ticket được cung cấp chưa nêu công thức giá; người dùng cho phép tự đề xuất phần thiếu. Những giả định dưới đây không được coi là câu trả lời của giảng viên hay luật trích từ PRD.

| Vấn đề | Quyết định / nguồn |
|---|---|
| Giá theo fresh | **Giả định được người dùng cho phép:** floor(giá menu × trung bình cộng fresh của toàn bộ cá thể dùng nấu / initial). initial chuẩn là 100. Tính sau hao tươi của bước nấu, chốt vào payload món; không hao/định giá lại sau khi rời kho thô. Nếu tích hợp có công thức chính thức khác, đổi tại FreshStock.consume và các test giá tương ứng. |
| Chọn nguyên liệu | Lấy đủ công thức từ hàng chưa ươn/chưa giữ, tươi nhất trước, hòa theo id tự nhiên. Mảng reserved xuất theo id; cook_started.items sắp theo kind rồi id. Phần giữ tường minh của fixture được kiểm trước, sau đó cấp phần thiếu theo order_tick rồi id bàn. |
| Khi một phần giữ vừa ươn | Phát hết spoiled theo id trước. Nhả toàn bộ phần giữ của các đơn bị ảnh hưởng, rồi thử cấp đủ công thức lại theo order_tick/id bàn. Thiếu thì unfulfillable, reserved=[], tiếp tục chờ; không giữ một phần, không lấy của đơn chưa bị ảnh hưởng. Đây là cách chốt phần quy trình chưa đầy đủ trong ticket đính kèm. |
| Hàng ươn trong kho | Giữ cá thể trong tồn vật lý/snapshot, vẫn hao về 0, không dùng nấu/giữ/chọn món. Hàng đã ươn lúc nạp không phát spoiled lại; event chỉ phát khi đi từ ≥30 xuống <30. |
| Tính chính xác | Dùng Fraction từ giá trị thập phân đầu vào, hao theo tuning/tick_hz; không cộng/trừ float lặp để quyết định ngưỡng/floor. JSONL không làm tròn fresh về 3 chữ số. Chặn trường hợp đổi sang float làm hàng đã ươn hiển thị lại đúng 30 bằng nextafter. |

### Tác động và thứ tự tích hợp

1. `quan_freshness.validate_stock(items,kinds)` kiểm/copy mảng cá thể; `FreshStock` gắn vào QuanSim khi có tuning.freshness. QuanSim nhận inventory hoặc scenario.stock dạng mảng và giữ nguyên id/fresh khi dựng, không hao ở tick 0. Không có freshness thì chạy nhánh đếm P1/P2 như cũ.
2. Lát schema cần ghép manifest 1.2, đọc/ghi kho cá thể và từ chối kho đếm theo version; lát Gather cấp/giữ id, hao tươi, LIFO và xuất đủ độ chính xác. Lát day/Shop phải chuyển stock sang list, bàn giao cùng tick không hao, giữ IdAllocator xuyên Ngày và cấp id mới cho hold template từ Ngày 2. Các phần này chưa được sửa trong lát Quán.
3. Luồng Quán đã nối: đồng hồ/timer → FreshStock.step (hao tươi, toàn bộ spoiled, giữ lại) → chín/cháy → di chuyển/interact → kết toán/đóng ca → sinh khách thường. Burn dùng lại bộ chọn cá thể; hàng đã nấu không hoàn lại. Pause do Session chặn trước gameplay nên không hao tươi.
4. `scenario.py` nhận stock/reserved dạng list khi có freshness, các liên kết giữ thực tế do QuanSim kiểm trước khi writer mở file. `jsonl.py` chỉ đổi cách xuất trường fresh, tọa độ vẫn 3 chữ số. Không sửa game.contract.json, inventory.py, Gather, day/Shop hay HUD trong thay đổi này.
5. Bằng chứng: [lát 3 Quán](proof/phase-3/chur04/README.md). Chưa bật v1.2 toàn project, chưa xác nhận file/day/HUD hoặc mở rộng đặt trước. Người dùng tự commit; không stage/commit/push/tag tự động.
