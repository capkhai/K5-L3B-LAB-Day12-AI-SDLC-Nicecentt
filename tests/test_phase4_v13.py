"""Kiểm thử Phase 4 (Contract v1.3 — Phát hành v1.0.0): bench_cmd, soak_cmd (10 ngày tất định), 3 cảnh báo + tương phản cao, đóng gói."""

import json
import pathlib
import subprocess
import sys
import unittest

from chonoi.contract import load_contract
from helpers import Workdir

ROOT = pathlib.Path(__file__).resolve().parents[1]


class Phase4ContractAndReleaseTest(unittest.TestCase):
    def test_contract_v13_declares_bench_and_soak_cmds(self):
        contract = load_contract()
        self.assertEqual(contract["contract_version"], "1.3")
        self.assertEqual(contract["bench_cmd"], "python3 -m chonoi.bench")
        self.assertEqual(contract["soak_cmd"], "python3 -m chonoi.soak")
        self.assertTrue((ROOT / "LICENSE").is_file())
        self.assertTrue((ROOT / "CREDITS.md").is_file())
        self.assertTrue((ROOT / "CHANGELOG.md").is_file())

    def test_bench_cli_produces_valid_five_field_json_and_rejects_bad_args(self):
        with Workdir() as w:
            out = w.path("bench.json")
            res = subprocess.run(
                [sys.executable, "-m", "chonoi.bench", "--seed", "42", "--duration", "0.5", "--warmup", "0.1", "--out", out],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )
            self.assertEqual(res.returncode, 0, res.stderr)
            data = json.loads(pathlib.Path(out).read_text(encoding="utf-8"))
            self.assertEqual(set(data.keys()), {"avg_fps", "p1_low_fps", "frames", "measured_s", "load_ms"})
            self.assertGreater(data["frames"], 0)
            self.assertGreater(data["measured_s"], 0)
            self.assertGreater(data["avg_fps"], 0)
            self.assertGreater(data["p1_low_fps"], 0)
            self.assertGreaterEqual(data["avg_fps"], data["p1_low_fps"] - 0.1)
            self.assertGreaterEqual(data["load_ms"], 0)

            bad = subprocess.run(
                [sys.executable, "-m", "chonoi.bench", "--seed", "42", "--duration", "0", "--out", w.path("bad.json")],
                cwd=ROOT,
                capture_output=True,
            )
            self.assertEqual(bad.returncode, 2)

    def test_soak_10_days_cycles_plan_zero_crashes_and_deterministic_gameplay(self):
        with Workdir() as w:
            o1, o2 = w.path("soak1.json"), w.path("soak2.json")
            for out in (o1, o2):
                res = subprocess.run(
                    [sys.executable, "-m", "chonoi.soak", "--seed", "7", "--days", "10", "--out", out],
                    cwd=ROOT,
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(res.returncode, 0, res.stderr)

            d1 = json.loads(pathlib.Path(o1).read_text(encoding="utf-8"))
            d2 = json.loads(pathlib.Path(o2).read_text(encoding="utf-8"))
            self.assertEqual(set(d1.keys()), {"days", "days_completed", "crashes", "results", "duration_s"})
            self.assertEqual(d1["days"], 10)
            self.assertEqual(d1["days_completed"], 10)
            self.assertEqual(d1["crashes"], 0)
            self.assertEqual(len(d1["results"]), 10)
            self.assertEqual([r["day"] for r in d1["results"]], list(range(1, 11)))
            for r in d1["results"]:
                self.assertEqual(set(r.keys()), {"day", "earned", "reputation", "score"})
            # So tính lặp ở mọi trường gameplay (bỏ duration_s)
            self.assertEqual(d1["results"], d2["results"])
            self.assertEqual(d1["days_completed"], d2["days_completed"])
            self.assertEqual(d1["crashes"], d2["crashes"])
            # Xác nhận bot chơi thật (kiếm được tiền qua 10 ngày)
            self.assertGreater(d1["results"][-1]["earned"], 0)


if __name__ == "__main__":
    unittest.main()
