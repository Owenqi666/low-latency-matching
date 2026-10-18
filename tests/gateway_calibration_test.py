#!/usr/bin/env python3
"""Finite G05 policy and evidence counterexamples; no service processes or load."""
from copy import deepcopy
import json
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import calibrate_gateway as calibration


def base():
    return json.loads((ROOT / "data/workloads/service-formal.json").read_text())


def result(kind, rate, outcome="pass", retry=0):
    return {**calibration.run_step(kind, rate, retry), "outcome": outcome}


def bracket():
    return [result("probe", 10000), result("probe", 15000, "valid_load_failure")]


def pass_until_failure(count=5):
    results = []
    for _ in range(count):
        results.append({**calibration.next_step(results), "outcome": "pass"})
    results.append({**calibration.next_step(results), "outcome": "valid_load_failure"})
    return results


def samples(lags=None, per_bin=100):
    values = []
    for group in range(4):
        for index in range(per_bin):
            scheduled = group * 1000000000 + index * 1000000000 // per_bin
            lag = 10000 if lags is None else lags(group, index)
            values.append({"scheduled_ns": scheduled, "first_attempt_ns": None if lag is None else scheduled + lag,
                           "send_lag_ns": lag})
    return values


def run(name="r1", kind="measurement", success=True):
    return {"id": name, "kind": kind, "succeeded": success, "failure_reasons": {} if success else {"deadline": 1},
            "server_counters": {"worker_aborted": False, "failure": "", "write_batch_max_frames": 1,
                                "write_batch_max_bytes": 4096, "gateway_diagnostics_enabled": False}}


def environment():
    return {**dict.fromkeys(calibration.ENVIRONMENT, "fixed"), "system_memory_bytes": 4 * 1024**3,
            "physical_cpu_cores": 4, "cpu": {"available": True, "output": "Model name: test CPU\nCPU MHz: 999\n"},
            "cpu_controls": {"inherited_affinity_cpus": [0, 1, 2, 3], "observed_governors": None},
            "virtualization": {"available": True, "output": "qemu"}, "code_commit": "tools-commit"}


def fake_plan(root, pending=None):
    calibration.write_once(root / "base-manifest.json", base())
    plan = {"schema_version": 1, "policy": calibration.POLICY, "config": {"g04_pair": None},
            "identity": {}, "snapshots": {"base-manifest.json": calibration.sha256(root / "base-manifest.json")},
            "provenance_scope": "synthetic A binding"}
    calibration.write_once(root / "plan.json", plan)
    calibration.append_state(root, {"status": "prepared", "attempts": [], "pending": pending, "reuse": None})
    return plan


class PolicyTests(unittest.TestCase):
    def test_exact_configurations(self):
        for kind, rows, commands, seconds, rounds in (
                ("probe", ["mixed_4"], 2000, 2, 2), ("ordinary", ["mixed_4", "mixed_1"], 10000, 10, 3),
                ("near", ["mixed_4"], 10000, 10, 3), ("burst", ["burst_4"], 10000, 10, 1)):
            step = calibration.run_step(kind, 12345)
            self.assertEqual((step["rows"], step["commands"], step["minimum_plan_seconds"], step["rounds"], step["warmup_commands"]),
                             (rows, commands, seconds, rounds, 1000))
        for arguments in (("other", 1), ("probe", 0), ("probe", True), ("probe", 1, 1), ("ordinary", 1, 2)):
            with self.assertRaises(ValueError):
                calibration.run_step(*arguments)

    def test_growing_probe_stops_at_first_upper_failure(self):
        history = []
        expected = [10000, 15000, 22500, 33750, 50625, 75938]
        for rate in expected:
            step = calibration.next_step(history)
            self.assertEqual((step["kind"], step["rate"]), ("probe", rate))
            history.append({**step, "outcome": "pass" if rate != expected[-1] else "valid_load_failure"})
        self.assertEqual(calibration.next_step(history), calibration.run_step("ordinary", 10000))

    def test_initial_failure_halves_without_bisection(self):
        history = [result("probe", 10000, "valid_load_failure"), result("probe", 5000, "valid_load_failure")]
        self.assertEqual(calibration.next_step(history), calibration.run_step("probe", 2500))
        history.append(result("probe", 2500))
        self.assertEqual(calibration.next_step(history), calibration.run_step("ordinary", 500))
        history += [result("ordinary", 500), result("near", 2250), result("burst", 100)]
        final = calibration.next_step(history)
        self.assertEqual(final["rates"]["overload"], 5000)

    def test_ten_successes_keep_high_load_label_without_extra_probe(self):
        history = []
        for _ in range(10):
            history.append({**calibration.next_step(history), "outcome": "pass"})
        highest = history[-1]["rate"]
        self.assertEqual(calibration.next_step(history)["kind"], "ordinary")
        while calibration.next_step(history)["action"] == "run":
            history.append({**calibration.next_step(history), "outcome": "pass"})
        decision = calibration.next_step(history)
        self.assertFalse(decision["rates"]["overload_observed"])
        self.assertEqual(decision["rates"]["overload"], highest)
        proposed = calibration.proposed_manifest(base(), decision["rates"])
        self.assertEqual(proposed["rows"][-1]["rate_role"], "high_load_probe")
        self.assertEqual(sum(item["rounds"] for item in history if item["kind"] == "probe"), 20)

    def test_ten_failures_stop_and_cannot_borrow_confirmation_budget(self):
        history = []
        for _ in range(10):
            history.append({**calibration.next_step(history), "outcome": "valid_load_failure"})
        self.assertEqual(calibration.next_step(history)["reason"], "probe_budget_without_a_pass")
        with self.assertRaises(ValueError):
            calibration.next_step(history + [result("probe", 9)])

    def test_lag_only_upper_is_not_overload_or_environment_noise(self):
        history = [result("probe", 10000), result("probe", 15000, "unstable_offered_load")]
        self.assertEqual(calibration.next_step(history)["reason"], "needs_load_diagnosis")
        history = [result("probe", 10000, "unstable_offered_load"), result("probe", 5000)]
        self.assertEqual(calibration.next_step(history)["reason"], "needs_load_diagnosis")

    def test_confirmations_have_independent_single_halving_budgets(self):
        history = bracket()
        for kind, first, lower in (("ordinary", 2000, 1000), ("near", 9000, 4500), ("burst", 200, 100)):
            self.assertEqual(calibration.next_step(history), calibration.run_step(kind, first))
            history.append(result(kind, first, "valid_load_failure"))
            self.assertEqual(calibration.next_step(history), calibration.run_step(kind, lower, 1))
            history.append(result(kind, lower, retry=1))
        self.assertEqual(calibration.next_step(history)["action"], "complete")
        self.assertEqual(sum(item["rounds"] * len(item["rows"]) for item in history if item["kind"] in {"ordinary", "near"}), 18)
        self.assertEqual(sum(item["rounds"] for item in history if item["kind"] == "burst"), 2)

    def test_second_confirmation_failure_stops(self):
        history = bracket() + [result("ordinary", 2000, "valid_load_failure"), result("ordinary", 1000, "valid_load_failure", 1)]
        self.assertEqual(calibration.next_step(history)["reason"], "confirmation_failed_twice")
        with self.assertRaises(ValueError):
            calibration.next_step(history + [result("ordinary", 500, retry=1)])

    def test_invalid_sequence_rate_retry_or_extra_attempt_rejected(self):
        counterexamples = [[result("probe", 10001)], [result("probe", 10000), result("probe", 20000)],
                           bracket() + [result("ordinary", 2000, retry=1)],
                           bracket() + [result("near", 9000)],
                           [result("probe", 10000, "measurement_insufficient"), result("probe", 5000)]]
        for history in counterexamples:
            with self.subTest(history=history), self.assertRaises(ValueError):
                calibration.next_step(history)

    def test_g04_reuse_only_at_ordinary_ten_thousand(self):
        history = pass_until_failure()
        self.assertEqual(calibration.next_step(history, g04_available=True), {"action": "reuse_g04"})
        self.assertEqual(calibration.next_step(history, {"outcome": "reused"}, True), calibration.run_step("near", 45562))
        self.assertEqual(calibration.next_step(history, {"outcome": "not_reused"}, True), calibration.run_step("ordinary", 10000))
        self.assertEqual(calibration.next_step(bracket(), g04_available=True), calibration.run_step("ordinary", 2000))

    def test_hard_stop_never_becomes_failed_upper_boundary(self):
        for outcome in calibration.HARD_STOPS:
            history = [result("probe", 10000), result("probe", 15000, outcome)]
            self.assertEqual(calibration.next_step(history)["reason"], outcome)


class ManifestTests(unittest.TestCase):
    def test_seed_indices_preserved_and_only_selected_rates_change(self):
        original = base()
        spec = calibration.manifest_for(original, calibration.run_step("ordinary", 2000))
        self.assertEqual([row["id"] for row in spec["rows"]], calibration.ROWS)
        self.assertEqual(spec["rows"][1:4], original["rows"][1:4])
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "manifest.json"
            calibration.write_once(path, spec)
            rows = calibration.load_manifest(path, ["mixed_4", "mixed_1"])["rows"]
        self.assertEqual([row["seed"] for row in rows], [original["seed"], original["seed"] + 4 * 100003])
        self.assertEqual([row["commands"] for row in rows], [20001, 20001])
        self.assertFalse(spec["gateway_diagnostics"])

    def test_exact_raw_count_includes_separate_warmups_and_setup(self):
        step = calibration.run_step("probe", 10000)
        estimate = calibration.estimate(calibration.manifest_for(base(), step), step["rows"])
        self.assertEqual(estimate["rows"][0]["measured_commands_per_run"], 20001)
        self.assertEqual(estimate["total_commands_including_setup"], 42502)
        self.assertEqual(estimate["required_free_bytes"], 2 * estimate["estimated_raw_bytes"] + 1024**3)
        step = calibration.run_step("ordinary", 10000)
        estimate = calibration.estimate(calibration.manifest_for(base(), step), step["rows"])
        self.assertEqual(estimate["total_commands_including_setup"], 606006)

    def test_600_second_guard_never_lowers_formal_sample_count(self):
        rates = {"ordinary": 1000, "near": 4500, "overload": 10000, "burst": 166, "overload_observed": True}
        with self.assertRaisesRegex(ValueError, "600"):
            calibration.proposed_manifest(base(), rates)
        rates["burst"] = 167
        spec = calibration.proposed_manifest(base(), rates)
        self.assertEqual((spec["commands"], spec["minimum_plan_seconds"], spec["rounds"]), (100000, 10, 5))
        self.assertEqual(spec["rows"][3]["burst_period_ns"], 100000000)
        self.assertEqual(spec["rows"][3]["burst_window_ns"], 10000000)

    def test_base_contract_rejects_shape_order_and_limits_drift(self):
        calibration.validate_base(base())
        for category in ("shape", "order", "burst", "command_capacity", "event_capacity", "send_limit"):
            spec = base()
            if category == "shape":
                spec["rows"][0]["connections"] = 1
            elif category == "order":
                spec["rows"][0], spec["rows"][1] = spec["rows"][1], spec["rows"][0]
            elif category == "burst":
                spec["rows"][3]["burst_window_ns"] = 1000000
            else:
                spec["limits"][category] += 1
            with self.subTest(category=category), self.assertRaises(ValueError):
                calibration.validate_base(spec)


class LagTests(unittest.TestCase):
    def analyze(self, values):
        return calibration.lag_analysis(values, 0, 4000000000, 10000)

    def test_stable_lag_uses_four_planned_bins_and_actual_span(self):
        report = self.analyze(samples())
        self.assertEqual(report["status"], "stable")
        self.assertEqual([item["samples"] for item in report["bins"]], [100] * 4)
        self.assertEqual(report["p50_growth_ns"], 0)
        self.assertEqual(report["actual_first_attempt_span_ns"], report["planned_span_ns"])

    def test_median_drift_and_tail_drift_are_separate_failures(self):
        p50 = self.analyze(samples(lambda group, index: 2000000 if group >= 2 else 0))
        self.assertFalse(p50["gates"]["p50_growth"])
        p99 = self.analyze(samples(lambda group, index: 10000000 if group >= 2 and index >= 98 else 0))
        self.assertTrue(p99["gates"]["p50_growth"])
        self.assertFalse(p99["gates"]["p99_growth"])

    def test_pending_and_send_span_catch_backlog_hidden_by_percentiles(self):
        pending = self.analyze(samples(lambda group, index: 10000000000 if group == 3 and index >= 80 else 0))
        self.assertFalse(pending["gates"]["pending_growth"])
        span = self.analyze(samples(lambda group, index: 300000000 if group == 3 and index == 99 else 0))
        self.assertTrue(span["gates"]["p50_growth"])
        self.assertTrue(span["gates"]["p99_growth"])
        self.assertFalse(span["gates"]["actual_send_span"])

    def test_empty_bins_and_missing_schedule_are_insufficient(self):
        for values in ([], samples(lambda group, index: None if group == 3 else 0),
                       samples() + [{"scheduled_ns": None, "first_attempt_ns": None, "send_lag_ns": None}]):
            self.assertEqual(self.analyze(values)["status"], "measurement_insufficient")

    def test_lag_identity_and_planned_window_are_checked(self):
        for field, value in (("send_lag_ns", -1), ("scheduled_ns", -1), ("first_attempt_ns", -1)):
            values = samples()
            values[0][field] = value
            with self.assertRaises(ValueError):
                self.analyze(values)


class ClassificationTests(unittest.TestCase):
    def test_correctness_insufficient_pressure_and_lag_only_remain_distinct(self):
        stable = {"r1": {"status": "stable"}}
        self.assertEqual(calibration.classify([run()], stable), "pass")
        self.assertEqual(calibration.classify([run(success=False)], stable), "valid_load_failure")
        unstable = {"r1": {"status": "unstable_offered_load"}}
        self.assertEqual(calibration.classify([run()], unstable), "unstable_offered_load")
        self.assertEqual(calibration.classify([run(success=False)], unstable), "valid_load_failure")
        self.assertEqual(calibration.classify([run(success=False)], {"r1": {"status": "measurement_insufficient"}}), "measurement_insufficient")
        for failure in ("protocol", "startup"):
            item = run(success=False)
            item["failure_reasons"] = {failure: 1}
            self.assertEqual(calibration.classify([item], stable), "correctness_fault" if failure == "protocol" else "needs_load_diagnosis")
        item = run()
        item["server_counters"]["worker_aborted"] = True
        self.assertEqual(calibration.classify([item], stable), "correctness_fault")

    def test_failed_warmup_is_not_hidden_by_successful_measurements(self):
        self.assertEqual(calibration.classify([run("w", "warmup", False), run()], {"r1": {"status": "stable"}}), "needs_load_diagnosis")
        with self.assertRaises(ValueError):
            calibration.classify([run("w", "warmup")], {})

    def test_environment_binding_checks_live_ram_cpu_and_not_tools_commit(self):
        original = environment()
        altered = deepcopy(original)
        altered["code_commit"] = "A-source-commit"
        altered["cpu"]["output"] = "Model name: test CPU\nCPU MHz: 1500\n"
        self.assertEqual(calibration.critical_environment(original), calibration.critical_environment(altered))
        for field, value in (("system_memory_bytes", 8 * 1024**3), ("physical_cpu_cores", 8),
                             ("cpu", {"available": True, "output": "Model name: other CPU"})):
            altered = deepcopy(original)
            altered[field] = value
            self.assertNotEqual(calibration.critical_environment(original), calibration.critical_environment(altered))


class ReuseTests(unittest.TestCase):
    def fixture(self, root):
        raw = root / "pair/A"
        calibration.write_once(raw / "build-evidence/CMakeCache.txt", {"release": True})
        calibration.write_once(raw / "build-evidence/compile_commands.json", [])
        source = dict.fromkeys(calibration.SOURCE_FIELDS, "A-source")
        source.update(dirty=False, git_status="", build_input_sha256={"src/send_queue.hpp": "a" * 64},
                      cmake_cache_sha256=calibration.sha256(raw / "build-evidence/CMakeCache.txt"),
                      compile_commands_sha256=calibration.sha256(raw / "build-evidence/compile_commands.json"))
        calibration.write_once(raw / "build-evidence/source.json", source)
        binding = {"directory": "A", "source": source, "source_record_sha256": calibration.sha256(raw / "build-evidence/source.json")}
        calibration.write_once(root / "pair/pair-manifest.json", {"variants": {"A": binding, "B": {"directory": "B-does-not-exist"}}})
        original = base()
        spec = deepcopy(original)
        spec.update(mode="calibration", rates_locked=False)
        calibration.write_once(raw / "source_manifest.json", spec)
        binaries = {name: {"sha256": name} for name in ("server", "loadgen", "verifier")}
        host = environment()
        calibration.write_once(raw / "manifest.json", {"server_source": binding, "binaries": binaries, "environment": host,
                               "workload_parameters": calibration.load_manifest(raw / "source_manifest.json", ["mixed_4", "mixed_1"])})
        calibration.write_once(root / "base-manifest.json", original)
        plan = {"config": {"g04_pair": str(root / "pair")},
                "identity": {"A_source": source, "A_environment": host, "binaries": binaries}}
        runs = [run("warmup-" + name, "warmup") for name in ("mixed_4", "mixed_1")]
        for name in ("mixed_4", "mixed_1"):
            for number in range(1, 6):
                runs.append({**run(f"{name}-{number}"), "row": name, "round": number,
                             "counts": {"completed": 100001}, "plan_window_seconds": 10.0001})
        return plan, {"runs": runs}

    def evaluate(self, root, plan, report):
        def validate(raw, destination):
            calibration.write_once(destination / "report.json", report)
            return report, calibration.tree_digest(raw)
        lags = {item["id"]: {"status": "stable"} for item in report["runs"] if item["kind"] == "measurement"}
        with patch.object(calibration, "validate_copy", side_effect=validate), patch.object(calibration, "run_lags", return_value=lags):
            return calibration.reuse_g04(root, plan)

    def test_reuse_binds_A_source_not_tools_commit_and_never_reads_B(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            plan, report = self.fixture(root)
            self.assertNotEqual(plan["identity"]["A_source"]["commit"], plan["identity"]["A_environment"]["code_commit"])
            self.assertEqual(self.evaluate(root, plan, report)["outcome"], "reused")

    def test_different_source_or_live_environment_skips_reuse(self):
        for category in ("source", "memory"):
            with self.subTest(category=category), tempfile.TemporaryDirectory() as folder:
                root = Path(folder).resolve()
                plan, _ = self.fixture(root)
                if category == "source":
                    plan["identity"]["A_source"]["commit"] = "other-A"
                else:
                    plan["identity"]["A_environment"]["system_memory_bytes"] *= 2
                with patch.object(calibration, "validate_copy") as validate:
                    self.assertEqual(calibration.reuse_g04(root, plan)["outcome"], "not_reused")
                    validate.assert_not_called()

    def test_reuse_requires_all_five_successes_uninstrumented_A_and_successful_warmups(self):
        for category, expected in (("loss", "not_reused"), ("missing_round", "evidence_invalid"),
                                   ("instrumented", "evidence_invalid"), ("batch16", "evidence_invalid"),
                                   ("warmup", "needs_load_diagnosis")):
            with self.subTest(category=category), tempfile.TemporaryDirectory() as folder:
                root = Path(folder).resolve()
                plan, report = self.fixture(root)
                if category == "loss":
                    report["runs"][-1]["succeeded"] = False
                elif category == "missing_round":
                    report["runs"].pop()
                elif category == "instrumented":
                    report["runs"][-1]["server_counters"]["gateway_diagnostics_enabled"] = True
                elif category == "batch16":
                    report["runs"][-1]["server_counters"]["write_batch_max_frames"] = 16
                else:
                    report["runs"][0]["succeeded"] = False
                    report["runs"][0]["failure_reasons"] = {"deadline": 1}
                self.assertEqual(self.evaluate(root, plan, report)["outcome"], expected)


class EvidenceTests(unittest.TestCase):
    def test_immutable_files_and_journal_detect_missing_or_changed_revision(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            fake_plan(root)
            with self.assertRaises(FileExistsError):
                calibration.write_once(root / "plan.json", {})
            calibration.append_state(root, {"status": "active"})
            self.assertEqual(calibration.read_state(root)["status"], "active")
            first = root / "journal/00000.json"
            first.write_text(first.read_text() + "\n")
            with self.assertRaisesRegex(ValueError, "hash chain"):
                calibration.read_state(root)
            first.unlink()
            with self.assertRaisesRegex(ValueError, "missing revision"):
                calibration.read_state(root)

    def test_saved_receipt_requires_unchanged_original_raw_evidence(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            raw = root / "attempt/raw"
            raw.mkdir(parents=True)
            (raw / "sample.csv").write_text("original\n")
            path = root / "attempt/result.json"
            calibration.write_once(path, {"outcome": "pass", "raw_identity": calibration.tree_digest(raw)})
            receipt = calibration.reference(root, path)
            self.assertEqual(calibration.checked_result(root, receipt)["outcome"], "pass")
            (raw / "sample.csv").write_text("modified\n")
            with self.assertRaisesRegex(ValueError, "raw evidence changed"):
                calibration.checked_result(root, receipt)
            path.write_text("{}")
            with self.assertRaisesRegex(ValueError, "result hash differs"):
                calibration.checked_result(root, receipt)

    def test_partial_or_terminal_manifest_without_normal_exit_never_reruns(self):
        for status, exit_record in (("running", None), ("completed", None),
                                    ("completed", {"returncode": 0, "stopped": "TimeoutExpired"}),
                                    ("failed", {"returncode": 2, "stopped": None})):
            with self.subTest(status=status, exit=exit_record), tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                pending = {"directory": "attempts/001-probe-10000", "step": calibration.run_step("probe", 10000)}
                plan = fake_plan(root, pending)
                directory = root / pending["directory"]
                calibration.write_once(directory / "raw/manifest.json", {"status": status})
                if exit_record is not None:
                    calibration.write_once(directory / "exit.json", exit_record)
                with patch.object(calibration, "verify_identity", return_value={}), patch.object(calibration, "execute_attempt") as execute, \
                        patch.object(calibration, "analyze_attempt") as analyze:
                    state = calibration.continue_calibration(root, plan, True)
                self.assertEqual(state["status"], "needs_recovery")
                execute.assert_not_called()
                analyze.assert_not_called()

    def test_full_orchestration_uses_new_attempts_and_only_proposes_formal(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            plan = fake_plan(root)
            invocations = []

            def fake_execute(root, plan, pending):
                directory = root / pending["directory"]
                invocations.append(pending["step"])
                calibration.write_once(directory / "raw/manifest.json", {"status": "completed"})
                calibration.write_once(directory / "exit.json", {"returncode": 0, "stopped": None})

            def fake_analyze(root, plan, pending):
                outcome = "valid_load_failure" if pending["step"]["kind"] == "probe" and pending["step"]["rate"] == 15000 else "pass"
                return {**pending["step"], "outcome": outcome}

            with patch.object(calibration, "verify_identity", return_value={}), \
                    patch.object(calibration, "execute_attempt", side_effect=fake_execute), \
                    patch.object(calibration, "analyze_attempt", side_effect=fake_analyze), \
                    patch.object(calibration.shutil, "disk_usage", return_value=Mock(free=10**15)):
                state = calibration.continue_calibration(root, plan, True)
                self.assertEqual(state["status"], "proposed")
                self.assertEqual([(step["kind"], step["rate"]) for step in invocations],
                                 [("probe", 10000), ("probe", 15000), ("ordinary", 2000), ("near", 9000), ("burst", 400)])
                snapshot = calibration.tree_digest(root)
                self.assertEqual(calibration.continue_calibration(root, plan, True), state)
                self.assertEqual(calibration.tree_digest(root), snapshot)
            self.assertEqual(len(state["attempts"]), 5)
            self.assertFalse(state["formal_run"])
            self.assertFalse(state["adoption_evaluated"])
            spec = calibration.load_manifest(root / state["manifest"]["path"])
            self.assertEqual(len(spec["rows"]), 7)
            self.assertEqual(spec["mode"], "formal")

    def test_default_does_not_launch_and_low_disk_stops_before_attempt(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            plan = fake_plan(root)
            with patch.object(calibration, "verify_identity", return_value={}), patch.object(calibration, "execute_attempt") as execute, \
                    patch.object(calibration.shutil, "disk_usage", return_value=Mock(free=1)):
                state = calibration.continue_calibration(root, plan, False)
                self.assertFalse(state["execution_requested"])
                state = calibration.continue_calibration(root, plan, True)
            self.assertEqual(state["decision"]["reason"], "resource_guard")
            self.assertFalse((root / "attempts").exists())
            execute.assert_not_called()

    def test_timeout_kills_own_group_even_if_runner_leader_exits_first(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            directory = root / "attempt"
            calibration.write_once(directory / "estimate.json", {"planned_measurement_seconds": 4})
            process = Mock(pid=12345)
            process.wait.side_effect = [subprocess.TimeoutExpired("runner", 10), -15]
            context = {"config": dict.fromkeys(("server", "loadgen", "verifier", "host_environment"), "/synthetic")}
            with patch.object(calibration.subprocess, "Popen", return_value=process), patch.object(calibration.os, "killpg") as kill:
                calibration.execute_attempt(root, context, {"directory": "attempt", "step": calibration.run_step("probe", 10000)})
            self.assertEqual([call.args for call in kill.call_args_list], [(12345, signal.SIGTERM), (12345, signal.SIGKILL)])
            self.assertEqual(calibration.read_json(directory / "exit.json")["stopped"], "TimeoutExpired")


if __name__ == "__main__":
    unittest.main()
