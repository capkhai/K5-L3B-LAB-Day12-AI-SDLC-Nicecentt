"""Benchmark có render 1280x720 cho cảnh buổi sáng lõi (TICKET-04, Contract v1.3).

Cách chạy chuẩn:
    python3 -m chonoi.bench --seed 42 --duration 30 --out bench.json

Không phụ thuộc thư viện ngoài hay X11/browser: chạy trực tiếp `Session("gather", ...)`
với độ tươi, cá bơi, Cá Sấu Năm Chèo, dòng nước lũ và render đầy đủ framebuffer RGB
1280x720 mỗi khung hình (nền nước theo độ sâu, sóng mặt nước, bến, nút hái, đàn cá,
thủy quái, Út Sen đứng yên ở bến, hiệu ứng bọt nước và thanh HUD).
"""

import argparse
import json
import math
import os
import sys
import tempfile
import time

from .contract import load_contract
from .errors import BadInput
from .inputs import InputState
from .runner import Session

WIDTH = 1280
HEIGHT = 720
ROW_STRIDE = WIDTH * 3
HUD_TOP_H = 66
HUD_BOT_H = 76
WATER_Y0 = HUD_TOP_H
WATER_Y1 = HEIGHT - HUD_BOT_H
WATER_H = WATER_Y1 - WATER_Y0
SIM_DT = 1.0 / 60.0

COLORS = {
    "ca_loc": (124, 168, 80),
    "ca_linh": (144, 202, 249),
    "ca_keo": (217, 160, 102),
    "bong_dien_dien": (246, 196, 49),
    "bong_sung": (240, 98, 146),
    "keo_neo": (143, 207, 107),
    "ca_sau": (186, 104, 200),
    "ran": (239, 83, 80),
    "dock": (184, 134, 75),
    "player": (255, 224, 130),
    "bubble": (210, 240, 255),
    "wave": (130, 205, 240),
    "oxy_bar": (79, 195, 247),
    "hp_bar": (239, 83, 80),
    "hud_bg": (11, 23, 33),
}


class GatherFramebufferRenderer:
    """Renderer 2D framebuffer RGB 1280x720 thuần Python (slice copy tốc độ C)."""

    def __init__(self, tuning: dict):
        g = tuning["gather"]
        self.x_max = float(g["bounds"]["x"][1])
        self.d_max = float(g["bounds"]["d"][1])
        self.dock_pos = g["dock_pos"]
        self.bg = self._bake_background()
        self.buf = bytearray(self.bg)
        self._color_rows = {
            name: bytes(rgb) * 96 for name, rgb in COLORS.items()
        }
        self._hud_bar_row = bytes(COLORS["oxy_bar"]) * 240
        self._hp_bar_row = bytes(COLORS["hp_bar"]) * 120
        self._wave_row = bytes(COLORS["wave"]) * 40
        self._bubbles = [(int((i * 197) % WIDTH), float(WATER_Y0 + 30 + (i * 53) % (WATER_H - 50)), 25.0 + (i % 4) * 12.0)
                         for i in range(28)]

    def _bake_background(self) -> bytes:
        rows = []
        hud_row = bytes(COLORS["hud_bg"]) * WIDTH
        for y in range(HEIGHT):
            if y < WATER_Y0 or y >= WATER_Y1:
                rows.append(hud_row)
            else:
                frac = (y - WATER_Y0) / max(1, WATER_H - 1)
                # Gradient nước sông từ mặt nước sáng xuống đáy sâu
                r = int(28 * (1.0 - frac) + 7 * frac)
                g = int(112 * (1.0 - frac) + 26 * frac)
                b = int(156 * (1.0 - frac) + 46 * frac)
                rows.append(bytes((r, g, b)) * WIDTH)
        return b"".join(rows)

    def _to_px(self, x: float, d: float):
        px = int(round((x / self.x_max) * (WIDTH - 24))) + 12
        py = WATER_Y0 + 18 + int(round((d / self.d_max) * (WATER_H - 36)))
        return px, py

    def _fill_rect(self, x0: int, y0: int, w: int, h: int, color_bytes: bytes):
        if x0 < 0:
            w += x0
            x0 = 0
        if y0 < 0:
            h += y0
            y0 = 0
        if x0 + w > WIDTH:
            w = WIDTH - x0
        if y0 + h > HEIGHT:
            h = HEIGHT - y0
        if w <= 0 or h <= 0:
            return
        span = w * 3
        row = color_bytes[:span] if len(color_bytes) >= span else (color_bytes[:3] * w)
        buf = self.buf
        off = y0 * ROW_STRIDE + x0 * 3
        for _ in range(h):
            buf[off:off + span] = row
            off += ROW_STRIDE

    def render(self, snap: dict, elapsed_s: float):
        # 1. Nền nước + dải HUD trên/dưới
        self.buf[:] = self.bg

        # 2. Hiệu ứng sóng mặt nước
        wave_shift = int(elapsed_s * 60) % 64
        for wx in range(-wave_shift, WIDTH, 64):
            wy = WATER_Y0 + 14 + int(3 * math.sin((wx + elapsed_s * 90) * 0.04))
            self._fill_rect(wx, wy, 36, 3, self._wave_row)

        # 3. Hiệu ứng bọt nước nổi lên
        bubble_bytes = self._color_rows["bubble"]
        for bx, by0, spd in self._bubbles:
            by = WATER_Y0 + 20 + int((by0 - WATER_Y0 - elapsed_s * spd) % (WATER_H - 30))
            self._fill_rect(bx, by, 4, 4, bubble_bytes)

        # 4. Bến ghe
        dx, dy = self._to_px(self.dock_pos[0], self.dock_pos[1])
        self._fill_rect(dx - 24, dy - 10, 48, 16, self._color_rows["dock"])

        # 5. Nút hái trên mặt nước
        for n in snap.get("nodes", []):
            nx, ny = self._to_px(n["pos"][0], n["pos"][1])
            c = self._color_rows.get(n["kind"], self._color_rows["bong_sung"])
            sz = 14 if n.get("ready", True) else 6
            self._fill_rect(nx - sz // 2, ny - sz // 2, sz, sz, c)

        # 6. Đàn cá bơi
        for f in snap.get("fish", []):
            fx, fy = self._to_px(f["pos"][0], f["pos"][1])
            c = self._color_rows.get(f["kind"], self._color_rows["ca_linh"])
            self._fill_rect(fx - 12, fy - 6, 24, 12, c)

        # 7. Thủy quái (Cá Sấu Năm Chèo / Rắn Hổ Mây)
        for m in snap.get("monsters", []):
            mx, my = self._to_px(m["pos"][0], m["pos"][1])
            c = self._color_rows.get(m["kind"], self._color_rows["ca_sau"])
            self._fill_rect(mx - 22, my - 10, 44, 20, c)

        # 8. Út Sen đứng yên ở bến
        p = snap.get("player", {})
        pos = p.get("pos", [2, 0])
        px, py = self._to_px(pos[0], pos[1])
        self._fill_rect(px - 10, py - 14, 20, 28, self._color_rows["player"])

        # 9. Thanh HUD (oxy, máu, thời gian)
        oxy_max = max(1, p.get("oxygen_max_ticks", 1800))
        oxy_w = max(0, min(220, int(220 * (p.get("oxygen_ticks", 0) / oxy_max))))
        self._fill_rect(24, 24, oxy_w, 16, self._hud_bar_row)
        hp_max = max(1, p.get("hp_max", 3))
        hp_w = max(0, min(110, int(110 * (p.get("hp", 0) / hp_max))))
        self._fill_rect(270, 24, hp_w, 16, self._hp_bar_row)

    def save_ppm(self, path: str):
        with open(path, "wb") as f:
            f.write(f"P6\n{WIDTH} {HEIGHT}\n255\n".encode("ascii"))
            f.write(self.buf)


def run_benchmark(seed: int, duration_s: float, warmup_s: float = 3.0, save_frame: str = None) -> dict:
    t_start = time.perf_counter()
    contract = load_contract()
    tuning = contract["tuning"]
    sess = Session("gather", tuning, {}, seed)
    renderer = GatherFramebufferRenderer(tuning)
    idle = InputState((0.0, 0.0), {"interact": False, "catch": False}, set())

    # Khung hình đầu tiên của cảnh đo -> chốt load_ms
    snap = sess.snapshot()
    renderer.render(snap, 0.0)
    t_first_frame = time.perf_counter()
    load_ms = (t_first_frame - t_start) * 1000.0

    # Làm nóng (mặc định 3s)
    sim_accum = 0.0
    elapsed_total = 0.0
    prev = t_first_frame
    warmup_end = t_first_frame + warmup_s
    while prev < warmup_end:
        now = time.perf_counter()
        dt = now - prev
        prev = now
        elapsed_total += dt
        sim_accum += dt
        while sim_accum >= SIM_DT:
            sim_accum -= SIM_DT
            if sess.done:
                sess = Session("gather", tuning, {}, seed)
            sess.step(idle)
        renderer.render(sess.snapshot(), elapsed_total)

    # Khoảng đo thực tế
    measure_start = time.perf_counter()
    measure_end = measure_start + duration_s
    frame_dts = []
    prev = measure_start
    while True:
        now = time.perf_counter()
        if now >= measure_end and frame_dts:
            break
        dt = now - prev
        prev = now
        elapsed_total += dt
        sim_accum += dt
        while sim_accum >= SIM_DT:
            sim_accum -= SIM_DT
            if sess.done:
                sess = Session("gather", tuning, {}, seed)
            sess.step(idle)
        renderer.render(sess.snapshot(), elapsed_total)
        after = time.perf_counter()
        frame_dts.append(max(1e-9, after - now))
        prev = after
        if after >= measure_end:
            break

    measured_s = max(1e-9, time.perf_counter() - measure_start)
    frames = len(frame_dts)
    avg_fps = frames / measured_s
    k = max(1, math.ceil(0.01 * frames))
    slowest = sorted(frame_dts, reverse=True)[:k]
    p1_low_fps = 1.0 / (sum(slowest) / len(slowest))

    if save_frame:
        renderer.save_ppm(save_frame)

    return {
        "avg_fps": round(avg_fps, 2),
        "p1_low_fps": round(p1_low_fps, 2),
        "frames": frames,
        "measured_s": round(measured_s, 3),
        "load_ms": round(load_ms, 2),
    }


def _write_json_atomic(path: str, payload: dict):
    parent = os.path.dirname(os.path.abspath(path))
    os.makedirs(parent, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".bench-", suffix=".tmp", dir=parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))
            f.write("\n")
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="chonoi.bench", description="Benchmark có render 1280x720 (Contract v1.3).")
    p.add_argument("--seed", required=True, type=int)
    p.add_argument("--duration", required=True, type=float)
    p.add_argument("--out", required=True)
    p.add_argument("--warmup", type=float, default=3.0)
    p.add_argument("--save-frame", dest="save_frame", default=None)
    a = p.parse_args(argv)
    try:
        if a.duration <= 0:
            raise BadInput("--duration phải > 0")
        if a.warmup < 0:
            raise BadInput("--warmup phải >= 0")
        result = run_benchmark(a.seed, a.duration, warmup_s=a.warmup, save_frame=a.save_frame)
        _write_json_atomic(a.out, result)
    except BadInput as e:
        sys.stderr.write(f"đầu vào sai: {e}\n")
        return 2
    except OSError as e:
        sys.stderr.write(f"lỗi ghi: {e}\n")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
