"""Phase 1, lát 3 (nhungvo631-stack): lịch sinh khách, chọn món đủ kho khả dụng, giữ chỗ và no_dish.

Gọi ở cuối QuanSim.step() khi còn giờ (không sinh ở bước đóng ca).
Timer và xử lý khách rời bàn/thanh toán do quan_service đảm nhận một nơi duy nhất.
"""

from ..ids import sort_by_id


def available_stock(sim) -> dict:
    """Tồn khả dụng = tồn vật lý trừ tổng phần giữ chỗ của các đơn reserved."""
    if sim.fresh_stock is not None:
        return sim.fresh_stock.available_counts()
    available = dict(sim.stock)
    for customer in sim.customers:
        if customer.get("order_status") == "reserved":
            for kind, count in customer.get("reserved", {}).items():
                available[kind] = available.get(kind, 0) - count
    return available


def cookable_dishes(sim) -> list:
    """Danh sách id món đủ kho khả dụng, sắp theo thứ tự Unicode."""
    available = available_stock(sim)
    return [
        dish_id
        for dish_id in sorted(sim.menu)
        if all(available.get(kind, 0) >= count for kind, count in sim.menu[dish_id]["recipe"].items())
    ]


class CustomerSpawner:
    """Sinh khách định kỳ theo first_customer_tick và customer_interval_s."""

    def __init__(self, sim, scenario):
        self.sim = sim
        t = sim.t
        self.random_customers = scenario.get("random_customers", True)
        self.first_customer_tick = int(t["first_customer_tick"])
        self.interval_ticks = int(round(t["customer_interval_s"] * sim.tick_hz))
        self.next_customer_tick = self.first_customer_tick

    def step(self, events: list):
        if not self.random_customers:
            return
        if self.sim.phase_tick < self.next_customer_tick:
            return
        while self.next_customer_tick <= self.sim.phase_tick:
            self.next_customer_tick += self.interval_ticks
        self._try_spawn(events)

    def _try_spawn(self, events: list):
        sim = self.sim
        occupied = {c["table_id"] for c in sim.customers}
        free_tables = [tb["id"] for tb in sort_by_id(sim.tables) if tb["id"] not in occupied]
        if not free_tables:
            # PRD-0: không có bàn trống thì bỏ lượt, không phát no_dish.
            return
        cookable = cookable_dishes(sim)
        if not cookable:
            events.append(("no_dish", {}))
            return
        dish_id = sim.rng.get("customer_dish").choice(cookable)
        table_id = free_tables[0]
        customer_id = sim.ids.new("C")
        recipe = dict(sim.menu[dish_id]["recipe"])
        customer = {
            "id": customer_id,
            "table_id": table_id,
            "dish_id": dish_id,
            "order_tick": sim.phase_tick,
            "order_status": "reserved",
            "state": "waiting",
            "patience_ticks_left": sim.patience_max_ticks,
            "eat_ticks_left": 0,
            "reserved": sim.fresh_stock.select(recipe) if sim.fresh_stock is not None else recipe,
        }
        sim.customers.append(customer)
        events.append(("customer_arrived", {
            "order_id": customer_id,
            "table_id": table_id,
            "dish_id": dish_id,
        }))
