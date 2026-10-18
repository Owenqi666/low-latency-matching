#!/usr/bin/env python3
"""Finite A-only G05 calibration using the existing service runner.

Without --execute, create/verify the frozen plan only. --resume never re-runs an
unfinished attempt: it can validate an already terminal raw archive, otherwise
it stops for recovery. Each attempt/result and each journal revision is new.
The output is proposed rates, never a formal run or an adoption decision.
"""
import argparse
from copy import deepcopy
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import signal
from statistics import median
import subprocess
import sys
import tempfile

from create_service_workloads import load_manifest, sha256
from run_bench import capture
from run_service_bench import binary_record, environment, now
from run_service_pair import MEASUREMENT_TOOLS, source_record
from summarize_service_bench import CLIENT_COLUMNS, distribution, local_file, read_csv, read_json, require


ROWS = ["mixed_4", "cancel_heavy_4", "sweep_4", "burst_4", "mixed_1", "mixed_4_near", "mixed_4_overload"]
ENVIRONMENT = ("os", "kernel", "architecture", "logical_cpus", "thread_configuration", "transport", "host_environment")
LAG_RULES = {"bins": 4, "minimum_started_per_bin": 1, "p50_growth_ns": 1000000,
             "p99_growth_ns": 5000000, "pending_floor": 10, "pending_rate_seconds": .001,
             "span_multiplier": 1.05, "span_slack_ns": 1000000}
POLICY = {"probe_points": 10, "probe_measurements": 20, "confirmation_measurements": 18,
          "burst_measurements": 2, "maximum_plan_seconds": 600, "warmup_commands": 1000,
          "estimated_bytes_per_command": 4096, "disk_reserve_bytes": 1024**3,
          "lag": LAG_RULES,
          "interpretation": "Bounded offered-load stability check; lag growth alone does not identify a loadgen bottleneck."}
HARD_STOPS = {"evidence_invalid", "correctness_fault", "measurement_insufficient", "needs_load_diagnosis"}
FAILURES = {"valid_load_failure", "unstable_offered_load"}
SOURCE_FIELDS = ("commit", "dirty", "git_status", "server_sha256", "build_input_sha256", "cmake_cache_sha256", "compile_commands_sha256")


def write_once(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    # Link a completely written file into place; never replace a prior receipt.
    with tempfile.NamedTemporaryFile(mode="w", prefix=".pending-", dir=path.parent, delete=False) as stream:
        temporary = Path(stream.name)
        try:
            json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
            os.link(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)


def tree_digest(root):
    require(root.is_dir(), f"evidence directory is missing: {root}")
    files = {}
    for path in sorted(root.rglob("*")):
        require(not path.is_symlink(), f"evidence symlink is unsupported: {path}")
        if path.is_file():
            files[path.relative_to(root).as_posix()] = {"sha256": sha256(path), "bytes": path.stat().st_size}
    return {"sha256": hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest(),
            "bytes": sum(item["bytes"] for item in files.values()), "files": len(files)}


def source_identity(source):
    return {key: source[key] for key in SOURCE_FIELDS}


def critical_environment(value):
    result = {key: value[key] for key in ENVIRONMENT}
    for key in ("system_memory_bytes", "physical_cpu_cores", "virtualization"):
        result[key] = value.get(key)
    cpu = deepcopy(value.get("cpu"))
    if isinstance(cpu, dict) and isinstance(cpu.get("output"), str):
        cpu["output"] = "\n".join(line for line in cpu["output"].splitlines() if "MHz" not in line and "BogoMIPS" not in line)
    result["cpu_identity"] = cpu
    # Affinity is observable without changing the requested CPU/RAM layout.
    result["inherited_affinity_cpus"] = value.get("cpu_controls", {}).get("inherited_affinity_cpus")
    result["observed_governors"] = value.get("cpu_controls", {}).get("observed_governors")
    return result


def lag_analysis(samples, planned_start_ns, plan_window_ns, rate):
    require(type(plan_window_ns) is int and plan_window_ns > 0 and type(rate) is int and rate > 0,
            "invalid planned lag window/rate")
    groups = [[] for _ in range(4)]
    started = []
    missing_schedule = False
    for sample in samples:
        scheduled, first = sample["scheduled_ns"], sample["first_attempt_ns"]
        if scheduled is None:
            missing_schedule = True
            continue
        require(planned_start_ns <= scheduled < planned_start_ns + plan_window_ns, "sample outside planned lag window")
        index = min(3, (scheduled - planned_start_ns) * 4 // plan_window_ns)
        if first is not None:
            require(first >= scheduled and sample["send_lag_ns"] == first - scheduled, "invalid lag sample")
            groups[index].append(sample["send_lag_ns"])
            started.append(first)
    boundaries = [planned_start_ns + plan_window_ns * n // 4 for n in range(1, 5)]
    pending = [sum(sample["scheduled_ns"] is not None and sample["scheduled_ns"] <= boundary and
                   (sample["first_attempt_ns"] is None or sample["first_attempt_ns"] > boundary) for sample in samples)
               for boundary in boundaries]
    result = {"rules": LAG_RULES, "planned_start_ns": planned_start_ns, "plan_window_ns": plan_window_ns,
              "bins": [{"index": index, "start_ns": planned_start_ns + plan_window_ns * index // 4,
                        "end_ns": boundaries[index], **distribution(values)} for index, values in enumerate(groups)],
              "pending_at_boundaries": pending, "boundary_ns": boundaries,
              "actual_first_attempt_range_ns": [min(started), max(started)] if started else None,
              "planned_samples": len(samples), "started_samples": len(started)}
    if missing_schedule or any(len(values) < LAG_RULES["minimum_started_per_bin"] for values in groups):
        return {**result, "status": "measurement_insufficient", "reason": "four planned-time bins require meaningful started samples"}
    p50 = [item["p50_ns"] for item in result["bins"]]
    p99 = [item["p99_ns"] for item in result["bins"]]
    scheduled = [sample["scheduled_ns"] for sample in samples]
    planned_span, actual_span = max(scheduled) - min(scheduled), max(started) - min(started)
    values = {"p50_growth_ns": median(p50[2:]) - median(p50[:2]),
              "p99_growth_ns": median(p99[2:]) - median(p99[:2]),
              "pending_growth": pending[-1] - pending[0], "pending_growth_limit": max(10, (rate + 999) // 1000),
              "planned_span_ns": planned_span, "actual_first_attempt_span_ns": actual_span}
    gates = {"p50_growth": values["p50_growth_ns"] <= LAG_RULES["p50_growth_ns"],
             "p99_growth": values["p99_growth_ns"] <= LAG_RULES["p99_growth_ns"],
             "pending_growth": values["pending_growth"] <= values["pending_growth_limit"],
             "actual_send_span": actual_span <= LAG_RULES["span_multiplier"] * planned_span + LAG_RULES["span_slack_ns"]}
    return {**result, **values, "gates": gates, "status": "stable" if all(gates.values()) else "unstable_offered_load"}


def run_step(kind, rate, retry=0):
    require(kind in {"probe", "ordinary", "near", "burst"} and type(rate) is int and rate > 0 and
            type(retry) is int and retry in (0, 1) and (kind != "probe" or retry == 0), "invalid calibration step")
    return {"action": "run", "kind": kind, "rate": rate, "retry": retry,
            "rows": ["mixed_4", "mixed_1"] if kind == "ordinary" else ["burst_4" if kind == "burst" else "mixed_4"],
            "commands": 2000 if kind == "probe" else 10000,
            "minimum_plan_seconds": 2 if kind == "probe" else 10,
            "rounds": 2 if kind == "probe" else (1 if kind == "burst" else 3), "warmup_commands": 1000}


def stop(reason, **details):
    return {"action": "stop", "reason": reason, **details}


def next_step(results, reuse=None, g04_available=False):
    """Pure finite policy; retries have their own fixed budget, never probe credit."""
    if reuse is not None:
        require(reuse["outcome"] in HARD_STOPS | {"reused", "not_reused"}, "unknown G04 reuse outcome")
    for index, result in enumerate(results):
        require(result["outcome"] in HARD_STOPS | FAILURES | {"pass"}, "unknown calibration outcome")
        expected = _choose_step(results[:index], reuse, g04_available)
        require(expected["action"] == "run", "attempt follows a terminal decision or unresolved reuse")
        require(all(result[key] == value for key, value in expected.items()), "attempt configuration differs from finite policy")
    return _choose_step(results, reuse, g04_available)


def _choose_step(results, reuse, g04_available):
    for result in results:
        if result["outcome"] in HARD_STOPS:
            return stop(result["outcome"], last_attempt=result["kind"])
    probes = [result for result in results if result["kind"] == "probe"]
    require(len(probes) <= 10 and len({p["rate"] for p in probes}) == len(probes), "probe budget/unique-rate violation")
    require(sum(r["rounds"] * len(r["rows"]) for r in results if r["kind"] in {"ordinary", "near"}) <= 18 and
            sum(r["rounds"] for r in results if r["kind"] == "burst") <= 2, "confirmation budget violation")
    if not probes:
        return run_step("probe", 10000)
    passed = [p["rate"] for p in probes if p["outcome"] == "pass"]
    highest = max(passed) if passed else None
    upper = [p for p in probes if highest is not None and p["rate"] > highest and p["outcome"] in FAILURES]
    if not upper and len(probes) < 10:
        previous = probes[-1]
        if probes[0]["outcome"] == "pass":
            return run_step("probe", (3 * previous["rate"] + 1) // 2)
        if previous["rate"] == 1:
            return stop("failure_at_one_request_per_second")
        return run_step("probe", max(1, previous["rate"] // 2))
    if highest is None:
        return stop("probe_budget_without_a_pass")
    load_failures = [p["rate"] for p in upper if p["outcome"] == "valid_load_failure"]
    if upper and not load_failures:
        return stop("needs_load_diagnosis", highest_pass=highest, upper_rates=[p["rate"] for p in upper],
                    detail="only upper boundary failed offered-load stability; this does not identify the bottleneck")
    rates = {"ordinary": max(1, min(10000, highest // 5)), "near": max(1, highest * 9 // 10),
             "overload": min(load_failures) if load_failures else highest, "overload_observed": bool(load_failures), "highest_pass": highest}
    for kind in ("ordinary", "near", "burst"):
        if kind == "burst":
            rates[kind] = max(1, rates["ordinary"] // 5)
        attempts = [result for result in results if result["kind"] == kind]
        require(len(attempts) <= 2, "confirmation retry budget exceeded")
        if kind == "ordinary" and not attempts and rates[kind] == 10000 and g04_available:
            if reuse is None:
                return {"action": "reuse_g04"}
            if reuse["outcome"] in HARD_STOPS:
                return stop(reuse["outcome"], detail=reuse.get("reason"))
            if reuse["outcome"] == "reused":
                continue
        if not attempts:
            if kind == "near" and rates[kind] <= rates["ordinary"]:
                return stop("ordinary_near_not_distinct", rates=rates)
            return run_step(kind, rates[kind])
        last = attempts[-1]
        if last["outcome"] == "pass":
            rates[kind] = last["rate"]
            if kind == "near" and rates[kind] <= rates["ordinary"]:
                return stop("ordinary_near_not_distinct", rates=rates)
            continue
        if len(attempts) == 2:
            return stop("confirmation_failed_twice", kind=kind, outcome=last["outcome"])
        lower = max(1, last["rate"] // 2)
        if lower == last["rate"] or (kind == "near" and lower <= rates["ordinary"]):
            return stop("ordinary_near_not_distinct" if kind == "near" else "confirmation_cannot_decrease", rates=rates)
        return run_step(kind, lower, 1)
    return {"action": "complete", "rates": rates}


def manifest_for(base, step):
    spec = deepcopy(base)
    spec.update(mode="calibration", rates_locked=False, gateway_diagnostics=False,
                **{key: step[key] for key in ("commands", "minimum_plan_seconds", "rounds", "warmup_commands")})
    spec["rate_selection"] = f"G05 A-only {step['kind']} at {step['rate']}/s; finite policy; never chosen from B outcomes."
    for row in spec["rows"]:
        if row["id"] in step["rows"]:
            row["target_rate_per_sec"] = step["rate"]
    return spec


def estimate(spec, selected):
    rows = []
    for row in spec["rows"]:
        if row["id"] not in selected:
            continue
        rate = row["target_rate_per_sec"]
        count = max(spec["commands"], rate * spec["minimum_plan_seconds"] + 1)
        warmup = min(spec["warmup_commands"], count)
        seconds = count / rate
        require(seconds <= 600 and warmup / rate <= 600, "planned row exceeds 600-second budget")
        rows.append({"row": row["id"], "rate": rate, "measured_commands_per_run": count,
                     "measured_runs": spec["rounds"], "warmup_runs": 1, "warmup_commands": warmup,
                     "setup_commands_per_run": spec["background_depth"], "plan_seconds_per_measurement": seconds,
                     "total_commands_including_setup": count * spec["rounds"] + warmup +
                                                       spec["background_depth"] * (spec["rounds"] + 1)})
    require(len(rows) == len(selected), "estimate contains unknown/duplicate selected rows")
    total = sum(row["total_commands_including_setup"] for row in rows)
    estimated_bytes = total * POLICY["estimated_bytes_per_command"] + 16 * 1024**2
    # The independent validator uses one temporary copy while raw evidence stays intact.
    return {"rows": rows, "total_commands_including_setup": total, "estimated_raw_bytes": estimated_bytes,
            "required_free_bytes": 2 * estimated_bytes + POLICY["disk_reserve_bytes"],
            "bytes_estimate_is_not_measurement": True,
            "planned_measurement_seconds": sum(row["plan_seconds_per_measurement"] * spec["rounds"] for row in rows)}


def proposed_manifest(base, rates):
    spec = deepcopy(base)
    spec.update(mode="formal", rates_locked=True, commands=100000, minimum_plan_seconds=10,
                rounds=5, warmup_commands=1000, gateway_diagnostics=False)
    spec["rate_selection"] = ("Proposed from completed finite A-only G05 calibration. Separate source/host/rules freeze still required. "
                              + ("Observed valid delivery-loss boundary." if rates["overload_observed"] else
                                 "No overload boundary observed within the probe budget; overload row is a high-load probe."))
    for row in spec["rows"]:
        role = "burst" if row["id"] == "burst_4" else "near" if row["id"] == "mixed_4_near" else "overload" if row["id"] == "mixed_4_overload" else "ordinary"
        row["target_rate_per_sec"] = rates[role]
        if role == "overload" and not rates["overload_observed"]:
            row["rate_role"] = "high_load_probe"
    estimate(spec, ROWS)
    return spec


def live_identity(config):
    source = source_record(Path(config["server"]), Path(config["source"]))
    require(source["dirty"] is False and source["git_status"] == "", "A server checkout must be clean")
    header = (Path(config["source"]) / "src/send_queue.hpp").read_text()
    require("inline constexpr std::size_t batch_max_frames = 1;" in header and
            "inline constexpr std::size_t batch_descriptor_capacity = 16;" in header and
            "inline constexpr std::size_t batch_max_bytes = 4096;" in header, "calibration requires the bounded batch1 A")
    host = environment(Path(config["source"]), Path(config["host_environment"]))
    require(host["os"].lower().startswith("linux"), "G05 calibration requires Linux")
    binaries = {name: binary_record(Path(config[name])) for name in ("server", "loadgen", "verifier")}
    require(all(record["build_type"] == "Release" and record["sanitized"] is False for record in binaries.values()),
            "G05 requires unsanitized Release binaries")
    scripts = Path(__file__).resolve().parent
    return {"A_source": source, "A_environment": host, "binaries": binaries,
            "tools_sha256": {name: sha256(scripts / name) for name in (*MEASUREMENT_TOOLS, Path(__file__).name)},
            "tools_repository": {"commit": capture(["git", "rev-parse", "HEAD"], scripts.parent),
                                 "status": capture(["git", "status", "--porcelain"], scripts.parent)},
            "host_file_sha256": sha256(Path(config["host_environment"])),
            "base_manifest_sha256": sha256(Path(config["base_manifest"])), "python": sys.version}


def identity_binding(identity):
    return {"A_source": source_identity(identity["A_source"]),
            "environment": critical_environment(identity["A_environment"]),
            **{name: identity[name] for name in ("binaries", "tools_sha256", "tools_repository", "host_file_sha256", "base_manifest_sha256", "python")}}


def verify_identity(plan):
    current = live_identity(plan["config"])
    require(identity_binding(current) == identity_binding(plan["identity"]), "source, binary, tools, limits, or environment changed since G05 freeze")
    return current


def validate_base(base):
    require([row["id"] for row in base["rows"]] == ROWS, "base manifest must preserve the original seven rows and order")
    shapes = [("mixed", 4), ("cancel_heavy", 4), ("sweep", 4), ("burst", 4), ("mixed", 1), ("mixed", 4), ("mixed", 4)]
    require([(row["scenario"], row["connections"]) for row in base["rows"]] == shapes, "base workload row shapes differ")
    require(all(base["limits"][key] == value for key, value in
                {"command_capacity": 1024, "event_capacity": 1024, "send_limit": 65536}.items()), "base queue or send limits differ")
    require((base["rows"][3]["burst_period_ns"], base["rows"][3]["burst_window_ns"]) == (100000000, 10000000),
            "burst must retain the 100ms period and 10ms window")


def prepare(root, config):
    require(not root.exists(), "calibration output already exists; use --resume or a new directory")
    base = read_json(Path(config["base_manifest"]))
    validate_base(base)
    load_manifest(Path(config["base_manifest"]))
    identity = live_identity(config)
    root.mkdir(parents=True)
    snapshots = {}
    copies = {"base-manifest.json": Path(config["base_manifest"]), "host-environment.json": Path(config["host_environment"]),
              "build-evidence/CMakeCache.txt": Path(config["server"]).parent / "CMakeCache.txt",
              "build-evidence/compile_commands.json": Path(config["server"]).parent / "compile_commands.json",
              "build-evidence/send_queue.hpp": Path(config["source"]) / "src/send_queue.hpp"}
    copies.update({"measurement-tools/" + name: Path(__file__).with_name(name) for name in identity["tools_sha256"]})
    for name, original in copies.items():
        destination = root / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(original, destination)
        snapshots[name] = sha256(destination)
        require(snapshots[name] == sha256(original), f"snapshot changed while copying: {name}")
    expected = {"base-manifest.json": identity["base_manifest_sha256"], "host-environment.json": identity["host_file_sha256"],
                "build-evidence/CMakeCache.txt": identity["A_source"]["cmake_cache_sha256"],
                "build-evidence/compile_commands.json": identity["A_source"]["compile_commands_sha256"],
                "build-evidence/send_queue.hpp": identity["A_source"]["build_input_sha256"]["src/send_queue.hpp"]}
    expected.update({"measurement-tools/" + name: digest for name, digest in identity["tools_sha256"].items()})
    require(all(snapshots[name] == digest for name, digest in expected.items()), "snapshot differs from captured source/tools identity")
    write_once(root / "build-evidence/source.json", identity["A_source"])
    snapshots["build-evidence/source.json"] = sha256(root / "build-evidence/source.json")
    plan = {"schema_version": 1, "frozen_at_utc": now(), "policy": POLICY, "config": config,
            "identity": identity, "snapshots": snapshots,
            "provenance_scope": "A_source/A_environment bind the server. The unchanged runner's environment.code_commit identifies its measurement-tools checkout, never the server source.",
            "lag_definition": "Four equal planned-window bins; p50/p99 use started requests. Pending means scheduled by a boundary but first attempt after it or absent. Span uses last minus first scheduled time."}
    write_once(root / "plan.json", plan)
    append_state(root, {"status": "prepared", "attempts": [], "pending": None, "reuse": None})
    return plan


def append_state(root, state):
    directory = root / "journal"
    directory.mkdir(exist_ok=True)
    previous = sorted(directory.glob("*.json"))
    write_once(directory / f"{len(previous):05d}.json", {"at_utc": now(), "plan_sha256": sha256(root / "plan.json"),
               "previous_sha256": sha256(previous[-1]) if previous else None, "state": state})


def read_state(root):
    previous, state = None, None
    for index, path in enumerate(sorted((root / "journal").glob("*.json"))):
        require(path.name == f"{index:05d}.json", "journal has a missing revision")
        record = read_json(path)
        require(record["previous_sha256"] == previous and record["plan_sha256"] == sha256(root / "plan.json"),
                "journal/plan hash chain differs")
        previous, state = sha256(path), record["state"]
    require(state is not None, "calibration journal is missing")
    return state


def checked_result(root, reference):
    path = local_file(root, reference["path"])
    require(sha256(path) == reference["sha256"], "saved result hash differs")
    result = read_json(path)
    if "raw_identity" in result:
        raw = (local_file(Path(read_json(root / "plan.json")["config"]["g04_pair"]), result["g04_A_directory"])
               if "g04_A_directory" in result else path.parent / "raw")
        require(tree_digest(raw) == result["raw_identity"], "saved raw evidence changed or is missing")
    if "identity_sha256" in result:
        require(sha256(path.parent / "identity.json") == result["identity_sha256"] and
                sha256(path.parent / "configuration.json") == result["configuration_sha256"], "saved attempt inputs changed")
    if "report_sha256" in result:
        validation = local_file(root, result.get("validation_directory", "g04-reuse"))
        require(sha256(validation / "report.json") == result["report_sha256"], "saved independent report changed")
    return result


def reference(root, path):
    return {"path": path.resolve().relative_to(root.resolve()).as_posix(), "sha256": sha256(path)}


def validate_copy(raw, destination):
    """Reuse the real checker on a disposable copy, retaining its result/log."""
    destination.mkdir(parents=True, exist_ok=False)
    before = tree_digest(raw)
    require(shutil.disk_usage(destination).free > before["bytes"] + POLICY["disk_reserve_bytes"], "insufficient disk for independent evidence copy")
    try:
        with tempfile.TemporaryDirectory(prefix="recompute-", dir=destination) as temporary:
            copied = Path(temporary) / "raw"
            shutil.copytree(raw, copied)
            require(tree_digest(copied) == before, "validation copy differs from raw evidence")
            with (destination / "validator.log").open("x") as log:
                status = subprocess.run([sys.executable, str(Path(__file__).with_name("summarize_service_bench.py")), str(copied)],
                                        stdout=log, stderr=subprocess.STDOUT, timeout=600).returncode
            require(status == 0, f"independent validator failed; see {destination / 'validator.log'}")
            for name in ("report.json", "report.md"):
                shutil.copyfile(copied / name, destination / name)
    finally:
        require(tree_digest(raw) == before, "source evidence changed during independent validation")
    return read_json(destination / "report.json"), before


def run_lags(raw, manifest, report):
    entries = {entry["id"]: entry for entry in manifest["expectedRuns"]}
    result = {}
    for run in report["runs"]:
        if run["kind"] != "measurement":
            continue
        directory = local_file(raw, entries[run["id"]]["directory"])
        client = read_json(directory / "client/client.json")
        workload = read_json(directory / "inputs/workload.json")
        result[run["id"]] = lag_analysis(read_csv(directory / "client/client_samples.csv", CLIENT_COLUMNS),
                                        client["measurement_start_ns"], workload["schedule_plan_window_ns"], run["target_per_second"])
    return result


def classify(runs, lags):
    measured = [run for run in runs if run["kind"] == "measurement"]
    require(measured and set(lags) == {run["id"] for run in measured}, "missing measured lag assessment")
    for run in runs:
        server = run["server_counters"]
        reasons = set(run["failure_reasons"])
        if server.get("worker_aborted") or "protocol" in reasons or server.get("failure", "") not in (
                "", "shutdown deadline exhausted", "admitted commands were not completely drained"):
            return "correctness_fault"
        if reasons - {"max_inflight", "send_limit", "deadline", "disconnected", "write_error"}:
            return "needs_load_diagnosis"
    if any(not run["succeeded"] for run in runs if run["kind"] != "measurement"):
        return "needs_load_diagnosis"
    # Independent validation already established a real delivery failure.
    # Early connection closure can leave later lag bins empty; that limits lag
    # interpretation but cannot erase the observed failed load point.
    if any(not run["succeeded"] for run in measured):
        return "valid_load_failure"
    if any(item["status"] == "measurement_insufficient" for item in lags.values()):
        return "measurement_insufficient"
    return "pass" if all(item["status"] == "stable" for item in lags.values()) else "unstable_offered_load"


def analyze_attempt(root, plan, pending):
    directory = local_file(root, pending["directory"])
    raw = directory / "raw"
    validations = sorted(directory.glob("validation-*"))
    output = directory / f"validation-{len(validations):03d}"
    result = {**pending["step"], "recorded_at_utc": now(), "identity_sha256": sha256(directory / "identity.json"),
              "configuration_sha256": sha256(directory / "configuration.json"), "validation_directory": output.relative_to(root).as_posix()}
    try:
        saved_identity = read_json(directory / "identity.json")
        require(identity_binding(saved_identity["live"]) == identity_binding(plan["identity"]) and
                saved_identity["configuration_sha256"] == result["configuration_sha256"] and
                saved_identity["plan_sha256"] == sha256(root / "plan.json"), "attempt identity/configuration differs")
        verify_identity(plan)
        manifest = read_json(raw / "manifest.json")
        require(manifest["source_manifest_sha256"] == result["configuration_sha256"] and
                manifest["workload_parameters"] == load_manifest(directory / "configuration.json", pending["step"]["rows"]),
                "runner changed frozen calibration parameters or seed mapping")
        require(manifest["binaries"] == plan["identity"]["binaries"] and
                critical_environment(manifest["environment"]) == critical_environment(plan["identity"]["A_environment"]),
                "runner binary/environment differs from A binding")
        # A raw reference failure is a correctness stop, even if a complete
        # report cannot subsequently pass the independent evidence validator.
        for entry in manifest["expectedRuns"]:
            run = read_json(local_file(raw, entry["directory"]) / "run.json")
            if run.get("verifier_exit") not in (None, 0):
                return {**result, "outcome": "correctness_fault", "reason": "independent Reference process failed"}
        report, digest = validate_copy(raw, output)
        for run in report["runs"]:
            counters = run["server_counters"]
            require(counters["write_batch_max_frames"] == 1 and counters["write_batch_max_bytes"] == 4096 and
                    counters.get("gateway_diagnostics_enabled", False) is False, "attempt did not use uninstrumented bounded batch1 A")
        lags = run_lags(raw, manifest, report)
        verify_identity(plan)
        return {**result, "outcome": classify(report["runs"], lags), "lag": lags,
                "runs": [{key: run[key] for key in ("id", "kind", "row", "round", "succeeded", "server_drained", "counts", "failure", "failure_reasons")}
                         for run in report["runs"]], "raw_identity": digest,
                "report_sha256": sha256(output / "report.json"),
                "failure_scope": "Valid delivery loss may reflect server or client pressure; it is not a claim identifying the bottleneck."}
    except (OSError, ValueError, KeyError, TypeError, StopIteration, subprocess.TimeoutExpired) as error:
        return {**result, "outcome": "evidence_invalid", "reason": str(error)}


def reuse_g04(root, plan):
    pair_root = Path(plan["config"]["g04_pair"])
    output = root / "g04-reuse"
    try:
        pair = read_json(pair_root / "pair-manifest.json")
        binding = pair["variants"]["A"]  # Never inspect candidate outcomes/rates.
        raw = local_file(pair_root, binding["directory"])
        manifest = read_json(raw / "manifest.json")
        source = read_json(raw / "build-evidence/source.json")
        require(source == binding["source"] and manifest["server_source"] == binding and
                sha256(raw / "build-evidence/source.json") == binding["source_record_sha256"], "G04 A source binding is corrupt")
        require(sha256(raw / "build-evidence/CMakeCache.txt") == source["cmake_cache_sha256"] and
                sha256(raw / "build-evidence/compile_commands.json") == source["compile_commands_sha256"], "G04 A CMake evidence differs")
        if source_identity(source) != source_identity(plan["identity"]["A_source"]) or manifest["binaries"] != plan["identity"]["binaries"] or \
                critical_environment(manifest["environment"]) != critical_environment(plan["identity"]["A_environment"]):
            return {"outcome": "not_reused", "reason": "G04 A source, binaries, or environment differs"}
        spec = load_manifest(raw / "source_manifest.json", ["mixed_4", "mixed_1"])
        base = read_json(root / "base-manifest.json")
        require(spec == manifest["workload_parameters"] and spec["rounds"] == 5 and spec["commands"] == 100000 and
                spec["minimum_plan_seconds"] == 10 and spec["mode"] == "calibration" and not spec["rates_locked"], "G04 A is not the five-round reproduction")
        for row in spec["rows"]:
            original_index = ROWS.index(row["id"])
            require(row["target_rate_per_sec"] == 10000 and row["seed"] == base["seed"] + original_index * 100003 and
                    all(row[key] == base[key] for key in ("capacity", "background_depth", "working_depth")) and
                    (row["scenario"], row["connections"]) == (base["rows"][original_index]["scenario"], base["rows"][original_index]["connections"]),
                    "G04 A workload differs from G05 source workload")
        require(spec["limits"] == base["limits"], "G04 A limits differ")
        report, digest = validate_copy(raw, output)
        measured = [run for run in report["runs"] if run["kind"] == "measurement"]
        require(all(run["server_counters"]["write_batch_max_frames"] == 1 and
                    run["server_counters"]["write_batch_max_bytes"] == 4096 and
                    run["server_counters"].get("gateway_diagnostics_enabled", False) is False for run in report["runs"]),
                "G04 reuse did not use uninstrumented bounded batch1 A")
        require({(run["row"], run["round"]) for run in measured} == {(name, n) for name in ("mixed_4", "mixed_1") for n in range(1, 6)} and
                len(measured) == 10, "G04 A reuse is missing one of five rounds")
        if not all(run["succeeded"] and run["counts"]["completed"] >= 100000 and run["plan_window_seconds"] >= 10 for run in measured):
            return {"outcome": "not_reused", "reason": "G04 A ordinary rows did not all succeed", "raw_identity": digest,
                    "g04_A_directory": binding["directory"]}
        lags = run_lags(raw, manifest, report)
        outcome = classify(report["runs"], lags)
        return {"outcome": "reused" if outcome == "pass" else "needs_load_diagnosis" if outcome == "unstable_offered_load" else outcome,
                "reason": "G04 A identity, both five-round ordinary rows, and frozen G05 lag criterion checked",
                "raw_identity": digest, "g04_A_directory": binding["directory"], "lag": lags, "report_sha256": sha256(output / "report.json")}
    except (OSError, ValueError, KeyError, TypeError, subprocess.TimeoutExpired) as error:
        return {"outcome": "evidence_invalid", "reason": str(error)}


def execute_attempt(root, plan, pending):
    directory = local_file(root, pending["directory"])
    config, step = plan["config"], pending["step"]
    command = [sys.executable, str(Path(__file__).with_name("run_service_bench.py"))]
    for name in ("server", "loadgen", "verifier"):
        command += ["--" + name, config[name]]
    command += ["--manifest", str(directory / "configuration.json"), "--output-dir", str(directory / "raw"),
                "--host-environment", config["host_environment"]]
    for name in step["rows"]:
        command += ["--row", name]
    projection = read_json(directory / "estimate.json")
    # The existing runner has per-process deadlines. This extra ceiling also
    # bounds a wedged runner/checker; all children belong to this new group.
    timeout = math.ceil(projection["planned_measurement_seconds"] + (step["rounds"] + 1) * len(step["rows"]) * 900)
    stopped = None
    with (directory / "runner.log").open("x") as log:
        process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        write_once(directory / "launch.json", {"command": command, "pid": process.pid, "started_at_utc": now(), "timeout_seconds": timeout})
        try:
            code = process.wait(timeout=timeout)
        except (KeyboardInterrupt, subprocess.TimeoutExpired) as error:
            stopped = type(error).__name__
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                code = process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                code = None
            # A terminated leader does not prove that its children have exited.
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            if code is None:
                code = process.wait()
    write_once(directory / "exit.json", {"returncode": code, "stopped": stopped, "ended_at_utc": now()})


def continue_calibration(root, plan, execute):
    require(plan["schema_version"] == 1 and plan["policy"] == POLICY, "calibration policy changed; start a new frozen plan")
    for name, digest in plan["snapshots"].items():
        require(sha256(local_file(root, name)) == digest, f"frozen snapshot changed: {name}")
    state = read_state(root)
    for item in state["attempts"] + ([state["reuse"]] if state["reuse"] else []):
        checked_result(root, item)
    if state["status"] in ("stopped", "proposed"):
        return state
    verify_identity(plan)
    while True:
        if state["pending"] is not None:
            pending = state["pending"]
            directory = local_file(root, pending["directory"])
            result_path = directory / "result.json"
            if not result_path.exists():
                manifest_path = directory / "raw/manifest.json"
                exit_path = directory / "exit.json"
                exited = read_json(exit_path) if exit_path.exists() else {}
                if not manifest_path.exists() or read_json(manifest_path).get("status") not in ("completed", "failed") or \
                        exited.get("stopped", "missing") is not None or exited.get("returncode") not in (0, 1):
                    state.update(status="needs_recovery", reason="attempt lacks an uninterrupted runner exit and terminal archive; retained without automatic rerun")
                    append_state(root, state)
                    return state
                write_once(result_path, analyze_attempt(root, plan, pending))
            state["attempts"].append(reference(root, result_path))
            state.update(pending=None, status="active")
            append_state(root, state)
        results = [checked_result(root, item) for item in state["attempts"]]
        reuse = checked_result(root, state["reuse"]) if state["reuse"] else None
        step = next_step(results, reuse, bool(plan["config"].get("g04_pair")))
        if step["action"] == "stop":
            state.update(status="stopped", decision=step)
            append_state(root, state)
            return state
        if step["action"] == "complete":
            try:
                proposed = proposed_manifest(read_json(root / "base-manifest.json"), step["rates"])
            except ValueError as error:
                state.update(status="stopped", decision=stop("formal_plan_budget", detail=str(error), rates=step["rates"]))
                append_state(root, state)
                return state
            path = root / "proposed-gateway-service-formal.json"
            if path.exists():
                require(read_json(path) == proposed, "existing proposed manifest differs")
            else:
                write_once(path, proposed)
            load_manifest(path)
            state.update(status="proposed", decision=step, manifest=reference(root, path), formal_run=False, adoption_evaluated=False)
            append_state(root, state)
            return state
        if not execute:
            return {**state, "next_step": step, "execution_requested": False}
        if step["action"] == "reuse_g04":
            path = root / "g04-reuse.json"
            if not path.exists():
                write_once(path, reuse_g04(root, plan))
            state["reuse"] = reference(root, path)
            append_state(root, state)
            continue
        current = verify_identity(plan)
        spec = manifest_for(read_json(root / "base-manifest.json"), step)
        try:
            projection = estimate(spec, step["rows"])
            projection["available_disk_bytes"] = shutil.disk_usage(root).free
            require(projection["available_disk_bytes"] >= projection["required_free_bytes"], "insufficient disk for attempt, validation copy, and reserve")
        except ValueError as error:
            state.update(status="stopped", decision=stop("resource_guard", detail=str(error), requested_step=step))
            append_state(root, state)
            return state
        directory = root / "attempts" / f"{len(results) + 1:03d}-{step['kind']}-{step['rate']}"
        directory.mkdir(parents=True, exist_ok=False)
        write_once(directory / "configuration.json", spec)
        derived = load_manifest(directory / "configuration.json", step["rows"])
        require([r["commands"] for r in derived["rows"]] == [r["measured_commands_per_run"] for r in projection["rows"]], "planned raw count estimate differs from generator")
        write_once(directory / "estimate.json", projection)
        write_once(directory / "identity.json", {"live": current, "plan_sha256": sha256(root / "plan.json"),
                   "configuration_sha256": sha256(directory / "configuration.json"), "scope": plan["provenance_scope"]})
        state.update(status="active", pending={"directory": directory.relative_to(root).as_posix(), "step": step})
        append_state(root, state)
        execute_attempt(root, plan, state["pending"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True, type=Path)
    for name in ("server", "source", "loadgen", "verifier", "base-manifest", "host-environment", "g04-pair"):
        parser.add_argument("--" + name, type=Path)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--execute", action="store_true", help="run the finite calibration; default only prepares/verifies the frozen plan")
    args = parser.parse_args()
    root = args.output_dir.resolve()
    fields = ("server", "source", "loadgen", "verifier", "base_manifest", "host_environment", "g04_pair")
    if args.resume:
        plan = read_json(root / "plan.json")
        for name in fields:
            value = getattr(args, name)
            require(value is None or str(value.resolve()) == plan["config"].get(name), f"resume overrides frozen {name}")
    else:
        require(all(getattr(args, name) is not None for name in fields[:-1]), "new calibration requires server/source/loadgen/verifier/base-manifest/host-environment")
        config = {name: str(getattr(args, name).resolve()) if getattr(args, name) else None for name in fields}
        plan = prepare(root, config)
    with (root / ".lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        state = continue_calibration(root, plan, args.execute)
    print(json.dumps(state, indent=2, sort_keys=True))
    return 2 if state["status"] in ("stopped", "needs_recovery") else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, KeyError, TypeError, StopIteration) as error:
        print(f"calibrate_gateway: {error}", file=sys.stderr)
        sys.exit(2)
