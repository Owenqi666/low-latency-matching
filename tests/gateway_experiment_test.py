#!/usr/bin/env python3
"""Gateway decision counterexamples; synthetic records only, no service workloads."""
from copy import deepcopy
import csv
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import evaluate_gateway_experiment as gateway
from run_service_pair import MEASUREMENT_TOOLS


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    gateway.write_json(path, value)


def side(cpu=100, rtt=100, scheduled=200, completed=100000, planned=100000):
    success = completed == planned
    return {gateway.CPU_KEY: cpu, "rtt": gateway.distribution([rtt]),
            "scheduled_to_complete": gateway.distribution([scheduled]),
            "counts": {"planned": planned, "started": planned, "completed": completed},
            "succeeded": success, "server_drained": True, "failure": "" if success else "loss",
            "plan_window_seconds": 10}


def refresh(pair):
    pair["both_succeeded"] = pair["A"]["succeeded"] and pair["B"]["succeeded"]
    pair["metrics"] = gateway.paired_metrics(pair["A"], pair["B"])


def matrix(phase="formal"):
    pairs = []
    for name in gateway.ROWS if phase == "formal" else ("mixed_4", "mixed_1"):
        for number in range(1, 6):
            pair = {"id": f"{name}-round_{number}", "row": name, "round": number,
                    "A": side(), "B": side(cpu=80)}
            refresh(pair)
            pairs.append(pair)
    return pairs


def raw_run(directory, latencies, setup_completions=500, incomplete=0):
    samples = []
    for index, (lag, rtt) in enumerate(latencies):
        scheduled = 10000 + index * 100
        row = dict.fromkeys(gateway.CLIENT_COLUMNS, 0)
        row.update(idx=index, logical=1 + index % 2, actual=1 + index % 2, request=index + 1,
                   scheduled_ns=scheduled, first_attempt_ns=scheduled + lag,
                   write_completed_ns=scheduled + lag, complete_ns=scheduled + lag + rtt,
                   send_lag_ns=lag, rtt_ns=rtt, outcome="completed", failure="", command_seq=index + 1,
                   completion_status=1, offset_ns=index * 100)
        samples.append(row)
    for _ in range(incomplete):
        row = dict.fromkeys(gateway.CLIENT_COLUMNS, 0)
        row.update(idx=len(samples), logical=2, actual=2, request=len(samples) + 1,
                   scheduled_ns=20000, first_attempt_ns=None, write_completed_ns=None,
                   complete_ns=None, send_lag_ns=None, rtt_ns=None, outcome="not_started", failure="drain_timeout")
        samples.append(row)
    csv_path = directory / "client/client_samples.csv"
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=gateway.CLIENT_COLUMNS)
        writer.writeheader()
        writer.writerows(samples)
    server = {**gateway.RUNTIME, "write_batch_max_frames": 1, "user_cpu_us": 900, "system_cpu_us": 100,
              "completed": len(latencies) + setup_completions, "close_reasons": {"peer_closed": 2},
              "uncompleted": 0, "discarded_business_frames": 0, "missing_business_recipients": 0}
    save(directory / "server/server.json", server)
    valid = {"server_counters": server, "counts": {"planned": len(samples), "started": len(latencies),
             "completed": len(latencies), "not_started": incomplete, "failed": 0, "unfinished": 0},
             "succeeded": not incomplete, "server_drained": True, "failure": "loss" if incomplete else "",
             "failure_reasons": {"drain_timeout": incomplete} if incomplete else {},
             "rtt": gateway.distribution([rtt for _, rtt in latencies]),
             "send_lag": gateway.distribution([lag for lag, _ in latencies]),
             "service": gateway.distribution([1] * len(latencies)),
             "gateway_wait": gateway.distribution([1] * len(latencies)), "plan_window_seconds": 10}
    return valid, samples


def contract_fixture(directory, phase="formal"):
    """Concrete example of the freeze receipt schema, with source-bound artifacts."""
    source = json.loads((ROOT / "data/workloads/service-formal.json").read_text())
    if phase == "repro":
        source.update(mode="calibration", rates_locked=False)
    source_path = directory / "evidence/baseline/source_manifest.json"
    save(source_path, source)
    spec = gateway.load_manifest(source_path, ["mixed_4", "mixed_1"] if phase == "repro" else None)
    headers = {}
    original = ("#pragma once\ninline constexpr std::size_t batch_max_frames = 1;\n"
                "inline constexpr std::size_t batch_descriptor_capacity = 16;\n"
                "inline constexpr std::size_t batch_max_bytes = 4096;\n")
    for key in ("A", "B"):
        header = directory / f"queue-{key}.hpp"
        header.write_text(original if key == "A" else original.replace("batch_max_frames = 1;", "batch_max_frames = 16;"))
        headers[key] = {"path": header.name, "sha256": gateway.sha256(header)}
    environment = {"os": "Linux", "kernel": "test-kernel", "architecture": "aarch64", "logical_cpus": 4,
                   "thread_configuration": "one gateway and one matching", "transport": "loopback_tcp",
                   "host_environment": {"virtualization": "test-fixture", "affinity": "all four vcpus"},
                   "code_dirty": False}
    variants = {}
    for key in ("A", "B"):
        identity = {"commit": key * 40, "server_sha256": key.lower() * 64,
                    "build_input_sha256": {"src/send_queue.hpp": headers[key]["sha256"], "src/server.cpp": "c" * 64},
                    "dirty": False, "git_status": ""}
        binaries = {name: {"build_type": "Release", "sanitized": False, "sha256": (key.lower() if name == "server" else "d") * 64}
                    for name in ("server", "loadgen", "verifier")}
        variants[key] = {"server_source": {"source": identity}, "environment": deepcopy(environment),
                         "binaries": binaries, "source_manifest_sha256": gateway.sha256(source_path),
                         "workload_parameters": deepcopy(spec)}
    tools = {name: gateway.sha256(ROOT / "scripts" / name) for name in MEASUREMENT_TOOLS}
    pair = {"mode": source["mode"], "variants": {"A": {"directory": "baseline"}, "B": {"directory": "candidate"}},
            "measurement_tools": {"sha256": tools}, "started_at_utc": "2026-10-18T01:00:00Z",
            "executed": [{"started_at_utc": "2026-10-18T01:01:00+00:00"}]}
    plan = directory / "plan.md"
    plan.write_text("Fixture plan frozen before all attempts.\n")
    receipt = {"schema_version": 1, "phase": phase, "rules": deepcopy(gateway.RULES),
               "source_manifest_sha256": variants["A"]["source_manifest_sha256"],
               "variants": {key: gateway.source_identity(value) for key, value in variants.items()},
               "binaries": {key: deepcopy(value["binaries"]) for key, value in variants.items()},
               "measurement_tools_sha256": tools, "evaluator_sha256": gateway.sha256(Path(gateway.__file__)),
               "environment": {key: environment[key] for key in gateway.ENVIRONMENT},
               "runtime": deepcopy(gateway.RUNTIME), "queue_sources": headers,
               "plan": {"path": plan.name, "sha256": gateway.sha256(plan)},
               "frozen_at_utc": "2026-10-18T00:00:00Z"}
    receipt_path = directory / "freeze.json"
    save(receipt_path, receipt)
    return directory / "evidence", pair, variants, receipt_path, receipt


class GatewayMetricsTest(unittest.TestCase):
    def test_scheduled_quantile_is_per_sample_not_sum_of_quantiles(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            valid, _ = raw_run(directory, [(1000, 1)] * 50 + [(1, 1000)] * 50)
            result = gateway.run_metrics(directory, valid, 1, gateway.RUNTIME)
            self.assertEqual(result["scheduled_to_complete"], {"samples": 100, "p50_ns": 1001, "p99_ns": 1001, "max_ns": 1001})
            self.assertEqual(result["rtt"]["p99_ns"] + result["send_lag"]["p99_ns"], 2000)
            self.assertEqual(result[gateway.CPU_KEY], 10)
            self.assertEqual(result["cpu_denominator_count"], 100)
            self.assertNotEqual(result[gateway.CPU_KEY], 1000 / valid["server_counters"]["completed"])

    def test_loss_keeps_subset_samples_and_connection_outcomes(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            valid, _ = raw_run(directory, [(1, 2)] * 10, incomplete=3)
            result = gateway.run_metrics(directory, valid, 1, gateway.RUNTIME)
            self.assertEqual(result["latency_scope"], "completed_subset_only")
            self.assertEqual(result[gateway.CPU_KEY], 100)
            self.assertEqual(result["scheduled_to_complete"]["samples"], 10)
            self.assertEqual(result["connections"][1]["not_started"], 3)
            self.assertEqual(sum(row["completed"] for row in result["connections"]), 10)

    def test_runtime_denominator_and_timing_corruptions_rejected(self):
        for corruption in ("wrong-denominator", "pooled-rtt", "batch", "send-bound", "bool", "missing-setting", "timestamp"):
            with self.subTest(corruption=corruption), tempfile.TemporaryDirectory() as temporary:
                directory = Path(temporary)
                valid, samples = raw_run(directory, [(1, 2)] * 10)
                if corruption == "wrong-denominator":
                    valid["counts"]["completed"] += 500
                elif corruption == "pooled-rtt":
                    valid["rtt"]["p99_ns"] = 500
                elif corruption == "timestamp":
                    samples[0]["complete_ns"] += 1
                    with (directory / "client/client_samples.csv").open("w", newline="") as stream:
                        writer = csv.DictWriter(stream, fieldnames=gateway.CLIENT_COLUMNS)
                        writer.writeheader()
                        writer.writerows(samples)
                else:
                    server = valid["server_counters"]
                    if corruption == "batch":
                        server["write_batch_max_frames"] = 16
                    elif corruption == "send-bound":
                        server["send_limit"] *= 2
                    elif corruption == "bool":
                        server["gateway_diagnostics_enabled"] = 0
                    else:
                        del server["gateway_diagnostics_enabled"]
                    save(directory / "server/server.json", server)
                with self.assertRaises(ValueError):
                    gateway.run_metrics(directory, valid, 1, gateway.RUNTIME)

    def test_pair_report_cannot_use_setup_in_cpu_denominator(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            variants, pair_report = {}, {"pairs": []}
            item = {"id": "mixed_4-round_1", "resources": {}}
            for key, name in (("A", "baseline"), ("B", "candidate")):
                variants[key] = {"directory": name}
                entry = {"id": item["id"], "kind": "measurement", "directory": "run"}
                save(directory / name / "manifest.json", {"expectedRuns": [entry]})
                valid, _ = raw_run(directory / name / "run", [(1, 2)] * 10)
                item[key] = valid
                item["resources"][key] = {gateway.CPU_KEY: 1000 / valid["server_counters"]["completed"]}
            pair_report["pairs"].append(item)
            save(directory / "pair-manifest.json", {"variants": variants})
            with patch.object(gateway, "summarize_pair", return_value=pair_report), \
                    patch.object(gateway, "validate_contract", return_value=(gateway.RUNTIME, None)):
                with self.assertRaisesRegex(ValueError, "CPU denominator"):
                    gateway.analyze_copy(directory, "repro", None, None)


class GatewayDecisionTest(unittest.TestCase):
    def test_adoption_requires_correctness_receipt(self):
        for correctness, expected in ((None, "inconclusive"), ({"all_passed": False}, "reject"), ({"all_passed": True}, "adopt")):
            result = gateway.numeric_decision(matrix(), "formal")
            self.assertEqual(result["decision"], "numerically_eligible")
            gateway.apply_correctness(result, "formal", correctness)
            self.assertEqual(result["decision"], expected)
            self.assertEqual(result["selected_variant"], "B" if expected == "adopt" else "A")
        repro = gateway.numeric_decision(matrix("repro"), "repro")
        gateway.apply_correctness(repro, "repro", {"all_passed": True})
        self.assertEqual((repro["decision"], repro["selected_variant"]), ("not_evaluated", "A"))

    def test_pair_percentages_are_not_pooled_or_ratio_of_medians(self):
        pairs = matrix()
        for pair, a, b in zip([p for p in pairs if p["row"] == "mixed_1"], [10, 20, 30, 100, 200], [1, 400, 30, 110, 220]):
            pair["A"]["rtt"] = gateway.distribution([a])
            pair["B"]["rtt"] = gateway.distribution([b])
            refresh(pair)
        result = gateway.numeric_decision(pairs, "formal")
        row = next(row for row in result["per_row"] if row["row"] == "mixed_1")
        # Pair changes: -90%, 1900%, 0%, 10%, 10%; median is 10%.
        # Ratio of medians is 266.7%, and a pooled p99 gives 100%.
        self.assertEqual(row["metrics"]["rtt_p99_change_percent"], {"pairs": 5, "median": 10, "min": -90, "max": 1900})
        self.assertTrue(result["gates"]["rtt_p99"])

    def test_near_requires_four_improving_pairs_as_well_as_median(self):
        pairs = matrix()
        near = [pair for pair in pairs if pair["row"] == "mixed_4_near"]
        for pair, candidate in zip(near, (80, 80, 80, 100, 100)):
            pair["B"][gateway.CPU_KEY] = candidate
            refresh(pair)
        result = gateway.numeric_decision(pairs, "formal")
        self.assertEqual(result["decision"], "reject")
        self.assertFalse(result["gates"]["near_cpu"])
        near[-1]["B"][gateway.CPU_KEY] = 99
        refresh(near[-1])
        self.assertTrue(gateway.numeric_decision(pairs, "formal")["gates"]["near_cpu"])

    def test_every_ordinary_and_near_row_has_latency_gate(self):
        for row in gateway.ROWS[:-1]:
            for metric, gate in (("rtt", "rtt_p99"), ("scheduled_to_complete", "scheduled_to_complete_p99")):
                with self.subTest(row=row, metric=metric):
                    pairs = matrix()
                    for pair in pairs:
                        if pair["row"] == row:
                            pair["B"][metric] = gateway.distribution([pair["A"][metric]["p99_ns"] * 1.11])
                            refresh(pair)
                    result = gateway.numeric_decision(pairs, "formal")
                    self.assertEqual(result["decision"], "reject")
                    self.assertFalse(result["gates"][gate])

    def test_exact_latency_and_cpu_thresholds_pass(self):
        pairs = matrix()
        for pair in pairs:
            pair["B"] = side(cpu=90, rtt=110, scheduled=220)
            refresh(pair)
        self.assertEqual(gateway.numeric_decision(pairs, "formal")["decision"], "numerically_eligible")

    def test_valid_service_loss_is_rejection_and_not_inconclusive(self):
        pairs = matrix()
        pairs[0]["B"] = side(cpu=1, completed=99999)
        refresh(pairs[0])
        result = gateway.numeric_decision(pairs, "formal")
        gateway.apply_correctness(result, "formal", None)
        self.assertEqual(result["decision"], "reject")
        self.assertFalse(result["gates"]["ordinary_and_near_delivery"])
        self.assertIsNone(pairs[0]["metrics"]["cpu_reduction_percent"])

    def test_overload_delivery_gate_cannot_be_offset_by_cpu(self):
        for count in (3, 4):
            pairs = matrix()
            overload = [pair for pair in pairs if pair["row"] == "mixed_4_overload"]
            for pair in overload[:count]:
                pair["A"] = side(completed=90000)
                pair["B"] = side(cpu=1, completed=80000)
                refresh(pair)
            result = gateway.numeric_decision(pairs, "formal")
            self.assertEqual(result["gates"]["overload_delivery"], count < 4)
            self.assertEqual(result["decision"], "numerically_eligible" if count == 3 else "reject")

    def test_missing_duplicate_fake_success_and_precomputed_metrics_rejected(self):
        for corruption in ("missing", "duplicate", "fake-pair", "fake-run", "fake-drain", "fake-metric"):
            with self.subTest(corruption=corruption):
                pairs = matrix()
                if corruption == "missing":
                    pairs.pop()
                elif corruption == "duplicate":
                    pairs[-1] = deepcopy(pairs[-2])
                elif corruption == "fake-pair":
                    pairs[0]["B"]["succeeded"] = False
                elif corruption == "fake-run":
                    pairs[0]["B"]["counts"]["completed"] -= 1
                elif corruption == "fake-drain":
                    pairs[0]["B"]["server_drained"] = False
                else:
                    pairs[0]["metrics"]["cpu_reduction_percent"] = 90
                with self.assertRaises(ValueError):
                    gateway.numeric_decision(pairs, "formal")


class GatewayFreezeTest(unittest.TestCase):
    def test_contract_and_original_seed_mapping(self):
        with tempfile.TemporaryDirectory() as temporary:
            root, pair, variants, path, _ = contract_fixture(Path(temporary), "repro")
            runtime, receipt = gateway.validate_contract(root, pair, variants, "repro", path)
            self.assertEqual(runtime, gateway.RUNTIME)
            self.assertIsNotNone(receipt)
            rows = variants["A"]["workload_parameters"]["rows"]
            self.assertEqual(rows[1]["seed"], rows[0]["seed"] + 4 * 100003)
        with tempfile.TemporaryDirectory() as temporary:
            root, pair, variants, path, _ = contract_fixture(Path(temporary))
            self.assertIsNotNone(gateway.validate_contract(root, pair, variants, "formal", path)[1])
            with self.assertRaisesRegex(ValueError, "freeze receipt"):
                gateway.validate_contract(root, pair, variants, "formal")

    def test_repro_row_names_cannot_hide_wrong_workload_or_client_count(self):
        for name in ("mixed_4", "mixed_1"):
            for field, value in (("scenario", "cancel_heavy"), ("connections", 2)):
                with self.subTest(row=name, field=field), tempfile.TemporaryDirectory() as temporary:
                    root, pair, variants, _, _ = contract_fixture(Path(temporary), "repro")
                    source_path = root / "baseline/source_manifest.json"
                    source = json.loads(source_path.read_text())
                    next(row for row in source["rows"] if row["id"] == name)[field] = value
                    save(source_path, source)
                    for variant in variants.values():
                        variant["workload_parameters"] = gateway.load_manifest(source_path, ["mixed_4", "mixed_1"])
                    with self.assertRaisesRegex(ValueError, "mixed workload with four and one clients"):
                        gateway.validate_contract(root, pair, variants, "repro")

    def test_stale_or_weakened_freezes_rejected(self):
        for corruption in ("late", "attempt-before-freeze", "rule", "source", "shared-binary", "tool", "evaluator", "environment", "runtime", "plan", "absolute", "escape"):
            with self.subTest(corruption=corruption), tempfile.TemporaryDirectory() as temporary:
                directory = Path(temporary)
                root, pair, variants, path, receipt = contract_fixture(directory)
                if corruption == "late":
                    receipt["frozen_at_utc"] = pair["started_at_utc"]
                elif corruption == "attempt-before-freeze":
                    pair["executed"][0]["started_at_utc"] = "2026-10-17T00:00:00Z"
                elif corruption == "rule":
                    receipt["rules"]["p99_max_regression_percent"] = 100
                elif corruption == "source":
                    receipt["variants"]["B"]["server_sha256"] = "e" * 64
                elif corruption == "shared-binary":
                    receipt["binaries"]["B"]["loadgen"]["sha256"] = "e" * 64
                elif corruption == "tool":
                    receipt["measurement_tools_sha256"]["summarize_service_pair.py"] = "e" * 64
                elif corruption == "evaluator":
                    receipt["evaluator_sha256"] = "e" * 64
                elif corruption == "environment":
                    receipt["environment"]["logical_cpus"] = 8
                elif corruption == "runtime":
                    receipt["runtime"]["send_limit"] *= 2
                elif corruption == "plan":
                    (directory / "plan.md").write_text("changed after freeze")
                elif corruption == "absolute":
                    receipt["plan"]["path"] = str(directory / "plan.md")
                else:
                    receipt["plan"]["path"] = "../outside.md"
                save(path, receipt)
                with self.assertRaises((ValueError, OSError)):
                    gateway.validate_contract(root, pair, variants, "formal", path)

    def test_clean_release_identity_and_only_constant_change(self):
        for corruption in ("dirty", "git-status", "sanitizer", "debug", "other-file", "additional-change", "descriptor", "reorder", "same-near-rate"):
            with self.subTest(corruption=corruption), tempfile.TemporaryDirectory() as temporary:
                directory = Path(temporary)
                root, pair, variants, path, receipt = contract_fixture(directory)
                if corruption == "dirty":
                    variants["A"]["server_source"]["source"]["dirty"] = True
                elif corruption == "git-status":
                    variants["A"]["server_source"]["source"]["git_status"] = " M src/server.cpp"
                elif corruption == "sanitizer":
                    variants["B"]["binaries"]["verifier"]["sanitized"] = True
                elif corruption == "debug":
                    variants["A"]["binaries"]["server"]["build_type"] = "Debug"
                elif corruption == "other-file":
                    variants["B"]["server_source"]["source"]["build_input_sha256"]["src/server.cpp"] = "e" * 64
                elif corruption in ("additional-change", "descriptor"):
                    header = directory / "queue-B.hpp"
                    value = header.read_text()
                    header.write_text(value + "// extra edit\n" if corruption == "additional-change" else value.replace("capacity = 16;", "capacity = 32;"))
                    digest = gateway.sha256(header)
                    variants["B"]["server_source"]["source"]["build_input_sha256"]["src/send_queue.hpp"] = digest
                    receipt["queue_sources"]["B"]["sha256"] = digest
                    receipt["variants"]["B"] = gateway.source_identity(variants["B"])
                    save(path, receipt)
                else:
                    source_path = root / "baseline/source_manifest.json"
                    source = json.loads(source_path.read_text())
                    if corruption == "reorder":
                        source["rows"].reverse()
                    else:
                        source["rows"][-2]["target_rate_per_sec"] = source["rows"][0]["target_rate_per_sec"]
                    save(source_path, source)
                    variants["A"]["workload_parameters"] = gateway.load_manifest(source_path)
                with self.assertRaises(ValueError):
                    gateway.validate_contract(root, pair, variants, "formal", path)

    def test_correctness_receipt_hashes_and_identity_are_required(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            _, _, variants, _, _ = contract_fixture(directory)
            evidence = directory / "correctness.log"
            evidence.write_text("Fixture checks passed for both source identities.\n")
            base = {"schema_version": 1, "variants": {key: gateway.source_identity(value) for key, value in variants.items()},
                    "checks": {name: {"status": "passed", "artifacts": [{"path": evidence.name, "sha256": gateway.sha256(evidence)}]}
                               for name in gateway.CORRECTNESS_CHECKS}}
            path = directory / "correctness.json"
            save(path, base)
            self.assertTrue(gateway.correctness_receipt(path, variants)["all_passed"])
            failed = deepcopy(base)
            failed["checks"]["tsan"]["status"] = "failed"
            save(path, failed)
            self.assertFalse(gateway.correctness_receipt(path, variants)["all_passed"])
            for corruption in ("identity", "missing-check", "no-artifact", "stale-artifact"):
                with self.subTest(corruption=corruption):
                    value = deepcopy(base)
                    if corruption == "identity":
                        value["variants"]["A"]["commit"] = "e" * 40
                    elif corruption == "missing-check":
                        value["checks"].pop("tsan")
                    elif corruption == "no-artifact":
                        value["checks"]["tsan"]["artifacts"] = []
                    else:
                        value["checks"]["tsan"]["artifacts"][0]["sha256"] = "e" * 64
                    save(path, value)
                    with self.assertRaises(ValueError):
                        gateway.correctness_receipt(path, variants)


class GatewayArchiveTest(unittest.TestCase):
    def test_non_string_freeze_times_produce_structured_invalid_evidence(self):
        for location in ("freeze", "experiment", "attempt"):
            for value in (None, 0, {}, []):
                with self.subTest(location=location, value=value), tempfile.TemporaryDirectory() as temporary:
                    directory = Path(temporary)
                    evidence, pair, variants, freeze, receipt = contract_fixture(directory)
                    if location == "freeze":
                        receipt["frozen_at_utc"] = value
                    elif location == "experiment":
                        pair["started_at_utc"] = value
                    else:
                        pair["executed"][0]["started_at_utc"] = value
                    save(freeze, receipt)
                    save(evidence / "pair-manifest.json", pair)
                    for key, variant in variants.items():
                        save(evidence / pair["variants"][key]["directory"] / "manifest.json", variant)
                    before = gateway.tree_identity(evidence)
                    with patch.object(gateway, "summarize_pair", return_value={"pairs": []}):
                        result = gateway.evaluate(evidence, "formal", directory / "output", freeze)
                    self.assertFalse(result["evidence_valid"])
                    self.assertEqual((result["decision"], result["selected_variant"]), ("inconclusive", "A"))
                    self.assertIn("ISO 8601 string", result["error"])
                    self.assertEqual(json.loads((directory / "output/gateway-evaluation.json").read_text()), result)
                    self.assertEqual(before, gateway.tree_identity(evidence))

    def test_bad_correctness_receipt_preserves_valid_rejection_and_blocks_adoption(self):
        for rejected in (False, True):
            for corruption in ("missing", "malformed", "stale-artifact"):
                with self.subTest(rejected=rejected, corruption=corruption), tempfile.TemporaryDirectory() as temporary:
                    directory = Path(temporary)
                    evidence, pair, variants, freeze, _ = contract_fixture(directory)
                    pairs = matrix()
                    if rejected:
                        pairs[0]["B"] = side(completed=99999)
                        refresh(pairs[0])
                    for item in pairs:
                        item["input_sha256"] = {}
                        item["resources"] = {key: {gateway.CPU_KEY: item[key][gateway.CPU_KEY]} for key in ("A", "B")}
                    save(evidence / "pair-manifest.json", pair)
                    for key, variant in variants.items():
                        variant["expectedRuns"] = [{"id": item["id"], "directory": item["id"], "kind": "measurement"} for item in pairs]
                        save(evidence / pair["variants"][key]["directory"] / "manifest.json", variant)
                    correctness = directory / "correctness.json"
                    if corruption == "malformed":
                        correctness.write_text("{invalid JSON")
                    elif corruption == "stale-artifact":
                        artifact = directory / "correctness.log"
                        artifact.write_text("original check log\n")
                        save(correctness, {"schema_version": 1,
                             "variants": {key: gateway.source_identity(value) for key, value in variants.items()},
                             "checks": {name: {"status": "passed", "artifacts": [{"path": artifact.name, "sha256": "e" * 64}]}
                                        for name in gateway.CORRECTNESS_CHECKS}})
                    runs = {item["id"]: item for item in pairs}

                    def metrics(run_dir, validated, frames, runtime):
                        return runs[run_dir.name]["A" if frames == 1 else "B"]

                    before = gateway.tree_identity(evidence)
                    with patch.object(gateway, "summarize_pair", return_value={"pairs": pairs}), \
                            patch.object(gateway, "run_metrics", side_effect=metrics):
                        result = gateway.evaluate(evidence, "formal", directory / "output", freeze, correctness)
                    self.assertTrue(result["evidence_valid"])
                    self.assertEqual((result["decision"], result["selected_variant"]), ("reject" if rejected else "inconclusive", "A"))
                    self.assertEqual(result["gates"]["ordinary_and_near_delivery"], not rejected)
                    self.assertTrue(result["correctness_error"])
                    self.assertIsNone(result["correctness"])
                    self.assertIn("Correctness receipt error:", (directory / "output/gateway-evaluation.md").read_text())
                    self.assertEqual(before, gateway.tree_identity(evidence))

    def test_recompute_mutates_only_temporary_copy_and_preserves_logs(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            evidence, output = directory / "evidence", directory / "output"
            save(evidence / "pair-report.json", {"old": True})
            (evidence / "raw.csv").write_text("frozen raw evidence\n")
            before = gateway.tree_identity(evidence)

            def recompute(copied, *_):
                self.assertNotEqual(copied, evidence)
                (copied / "raw.csv").write_text("validator may write only here\n")
                save(copied / "pair-report.json", {"recomputed": True})
                (copied / "independent-summary-A.log").write_text("validated\n")
                return {"evidence_valid": True, "phase": "repro", "decision": "not_evaluated", "selected_variant": "A"}

            with patch.object(gateway, "analyze_copy", side_effect=recompute):
                result = gateway.evaluate(evidence, "repro", output)
            self.assertEqual(before, gateway.tree_identity(evidence))
            self.assertEqual(result["source_identity_before"], result["source_identity_after"])
            self.assertEqual(json.loads((output / "validation/pair-report.json").read_text()), {"recomputed": True})
            self.assertFalse(list(output.glob("recompute-*")))

    def test_validator_corruption_errors_are_fail_closed(self):
        for error in ("missing round", "paired inputs differ", "run status contradicts exit evidence", "CPU denominator differs"):
            with self.subTest(error=error), tempfile.TemporaryDirectory() as temporary:
                directory = Path(temporary)
                evidence, output = directory / "evidence", directory / "output"
                save(evidence / "pair-manifest.json", {"stale_decision": "adopt"})
                before = gateway.tree_identity(evidence)
                with patch.object(gateway, "summarize_pair", side_effect=ValueError(error)) as validator:
                    result = gateway.evaluate(evidence, "formal", output)
                validator.assert_called_once()
                self.assertFalse(result["evidence_valid"])
                self.assertEqual((result["decision"], result["selected_variant"]), ("inconclusive", "A"))
                self.assertIn(error, result["error"])
                self.assertEqual(before, gateway.tree_identity(evidence))

    def test_real_validator_rejects_incomplete_archive_without_modifying_it(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            evidence, output = directory / "evidence", directory / "output"
            save(evidence / "pair-manifest.json", {"schema_version": 1, "status": "running"})
            save(evidence / "pair-report.json", {"decision": "adopt", "stale": True})
            before = gateway.tree_identity(evidence)
            process = subprocess.run([sys.executable, str(ROOT / "scripts/evaluate_gateway_experiment.py"), str(evidence),
                                      "--phase", "formal", "--output-dir", str(output)], capture_output=True, text=True, timeout=20)
            self.assertEqual(process.returncode, 2, process.stdout + process.stderr)
            result = json.loads((output / "gateway-evaluation.json").read_text())
            self.assertFalse(result["evidence_valid"])
            self.assertEqual(result["decision"], "inconclusive")
            self.assertIn("not terminal", result["error"])
            self.assertEqual(before, gateway.tree_identity(evidence))

    def test_no_nested_output_existing_output_or_symlink_inputs(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            evidence = directory / "evidence"
            save(evidence / "raw.json", {})
            for output in (evidence / "new-output", directory, evidence):
                with self.assertRaises(ValueError):
                    gateway.evaluate(evidence, "repro", output)
            output = directory / "existing"
            output.mkdir()
            with self.assertRaises(ValueError):
                gateway.evaluate(evidence, "repro", output)
            (evidence / "symlink.json").symlink_to(evidence / "raw.json")
            with self.assertRaisesRegex(ValueError, "symlink"):
                gateway.evaluate(evidence, "repro", directory / "new-output")


if __name__ == "__main__":
    unittest.main(verbosity=2)
