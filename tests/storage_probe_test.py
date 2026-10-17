#!/usr/bin/env python3
"""Check diagnostic counter scope using full/partial fills and order-id reuse."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PROBE = Path(sys.argv.pop(1)).resolve()


class StorageProbeTest(unittest.TestCase):
    def test_allocation_lifetime_and_semantics(self):
        with tempfile.TemporaryDirectory(prefix="storage-probe-") as temporary:
            root = Path(temporary)
            (root / "config").write_text("LLMATCH_CONFIG 1\n2 200 10\n")
            (root / "setup").write_text("LLMATCH_TRACE 1\nL 1 1 1 0 90 5\nL 1 2 2 1 110 5\n")
            (root / "input").write_text(
                "LLMATCH_TRACE 1\n"
                "L 2 3 3 0 110 1\n"  # Full before crossing: rejection allocates nothing.
                "M 2 4 3 0 2\n"  # Partial fill retains the maker.
                "C 1 5 1\n"
                "M 2 6 4 0 3\n"  # Full fill releases remaining maker and level.
                "L 2 7 2 1 110 4\n"  # Reuse completed id with a different owner.
                "C 1 8 2\n"  # Old owner cannot cancel reused id.
                "C 2 9 2\n"
                "M 2 10 5 1 2\n"  # Empty-book IOC.
            )
            command = [str(PROBE), "--config", str(root / "config"), "--setup", str(root / "setup"),
                       "--input", str(root / "input"), "--construction-repeats", "3"]
            output = root / "all.json"
            subprocess.run(command + ["--output", str(output)], check=True, capture_output=True, text=True)
            data = json.loads(output.read_text())
            self.assertTrue(data["diagnostic_only"])
            self.assertTrue(data["reference_passed"])
            self.assertEqual(data["input_commands"], 8)
            self.assertEqual(data["measured_prefix_commands"], 8)
            self.assertEqual(len(data["order_book_construction_ns"]), 3)
            self.assertGreater(data["construction"]["allocations"], 0)
            self.assertGreater(data["empty"]["engine_live_requested_bytes"], 0)
            self.assertEqual(data["after_setup"]["live_orders"], 2)
            self.assertEqual(data["measured_min_live_orders"], 0)
            self.assertEqual(data["measured_max_live_orders"], 2)
            self.assertEqual(data["final"]["live_orders"], 0)
            self.assertEqual(data["final"]["engine_live_requested_bytes"], data["empty"]["engine_live_requested_bytes"])
            self.assertEqual(data["engine_live_requested_bytes_after_destruction"], 0)
            self.assertEqual(data["engine_live_allocations_after_destruction"], 0)
            limit, market, cancel = [data["measured"][kind] for kind in ("limit", "market", "cancel")]
            self.assertEqual((limit["commands"], limit["accepted"], limit["rejected"], limit["rested"]), (2, 1, 1, 1))
            self.assertEqual((market["commands"], market["trades"], market["ioc_remainders"]), (3, 2, 1))
            self.assertEqual((cancel["commands"], cancel["rejected"], cancel["user_cancels"]), (3, 1, 2))
            self.assertEqual(market["allocations"], 0)
            self.assertEqual(cancel["allocations"], 0)
            self.assertGreater(market["frees"], 0)
            self.assertGreater(cancel["frees"], 0)
            # Reference, invariant scans and snapshot allocations must be excluded:
            # the empty-book live bytes equal constructor bytes and all are freed.
            phases = [data["construction"], data["destruction"], *data["setup"].values(), *data["measured"].values()]
            self.assertEqual(sum(p["allocations"] for p in phases), sum(p["frees"] for p in phases))
            self.assertEqual(sum(p["allocated_requested_bytes"] for p in phases), sum(p["freed_requested_bytes"] for p in phases))
            self.assertEqual(data["empty"]["engine_live_requested_bytes"], data["construction"]["allocated_requested_bytes"])
            # Prefix isolates a full-book rejection and a partial fill. Neither
            # changes storage lifetime, even though full event/state validation runs.
            prefix = root / "prefix.json"
            subprocess.run(command + ["--output", str(prefix), "--max-commands", "2"], check=True, capture_output=True, text=True)
            short = json.loads(prefix.read_text())
            for group in short["measured"].values():
                self.assertEqual(group["allocations"], 0)
                self.assertEqual(group["frees"], 0)
            self.assertEqual(short["input_hash"], data["input_hash"])
            self.assertEqual(short["measured_prefix_commands"], 2)
            self.assertEqual(short["final"]["live_orders"], 2)
            self.assertEqual(short["after_setup"]["engine_live_requested_bytes"], short["final"]["engine_live_requested_bytes"])
            # Evidence must survive a rejected attempt to reuse its output path.
            preserved = output.read_bytes()
            failed = subprocess.run(command + ["--output", str(output)], capture_output=True, text=True)
            self.assertNotEqual(failed.returncode, 0)
            self.assertIn("refusing to overwrite", failed.stderr)
            self.assertEqual(output.read_bytes(), preserved)


if __name__ == "__main__":
    unittest.main()
