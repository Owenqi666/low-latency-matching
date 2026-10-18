#!/usr/bin/env python3
"""Recompute Gateway metrics on a temporary evidence copy; never alter the input.

Repro is descriptive only. Formal decisions require a pre-run freeze receipt and
all numeric gates. Adoption also requires a source-bound correctness receipt;
its referenced artifacts are hash checked, not inferred from performance data.
Exit 0 means valid evidence (including a rejection); exit 2 means invalid evidence.
"""
import argparse
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path
import shutil
from statistics import median
import sys
import tempfile

from create_service_workloads import load_manifest, sha256
from summarize_service_bench import CLIENT_COLUMNS, distribution, local_file, read_csv, read_json, require
from summarize_service_pair import summarize as summarize_pair


ROWS = ["mixed_4", "cancel_heavy_4", "sweep_4", "burst_4", "mixed_1", "mixed_4_near", "mixed_4_overload"]
ENVIRONMENT = ("os", "kernel", "architecture", "logical_cpus", "thread_configuration", "transport", "host_environment")
RUNTIME = {"command_capacity": 1024, "event_capacity": 1024, "send_limit": 65536,
           "write_batch_max_bytes": 4096, "max_connections": 64,
           "socket_send_buffer": 0, "gateway_diagnostics_enabled": False}
RULES = {"cpu_median_reduction_percent": 10, "cpu_min_improving_pairs": 4,
         "p99_max_regression_percent": 10, "overload_worse_pairs": 4}
CORRECTNESS_CHECKS = {"event_state_consistency", "asan_ubsan", "tsan", "bounded_resources", "healthy_client_isolation"}
CPU_KEY = "server_lifetime_cpu_us_per_completed_measured_request"


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")


def tree_identity(root):
    """Bind names and bytes, including old derived reports; reject symlink inputs."""
    files = {}
    for path in sorted(root.rglob("*")):
        require(not path.is_symlink(), f"evidence symlink is unsupported: {path}")
        if path.is_file():
            files[path.relative_to(root).as_posix()] = {"sha256": sha256(path), "bytes": path.stat().st_size}
    digest = hashlib.sha256(json.dumps(files, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return {"sha256": digest, "file_count": len(files), "bytes": sum(v["bytes"] for v in files.values())}


def source_identity(manifest):
    source = manifest["server_source"]["source"]
    return {key: source[key] for key in ("commit", "server_sha256", "build_input_sha256")}


def checked_time(value):
    require(isinstance(value, str), "timestamp must be an ISO 8601 string")
    instant = datetime.fromisoformat(value.replace("Z", "+00:00"))
    require(instant.tzinfo is not None, "timestamp must include a UTC offset")
    return instant


def checked_artifact(base, item):
    require(isinstance(item["path"], str) and not Path(item["path"]).is_absolute(),
            "receipt artifact paths must be relative")
    path = local_file(base, item["path"])
    require(path.is_file() and sha256(path) == item["sha256"], f"artifact hash mismatch: {item['path']}")
    return path


def checked_queue_sources(base, records, variants):
    require(set(records) == {"A", "B"}, "freeze must bind both queue source snapshots")
    contents = {}
    for key in ("A", "B"):
        require(records[key]["sha256"] == source_identity(variants[key])["build_input_sha256"]["src/send_queue.hpp"],
                "queue snapshot differs from build input")
        contents[key] = checked_artifact(base, records[key]).read_bytes()
    original = b"inline constexpr std::size_t batch_max_frames = 1;"
    require(contents["A"].count(original) == 1 and
            contents["A"].replace(original, original.replace(b"1;", b"16;")) == contents["B"] and
            b"inline constexpr std::size_t batch_descriptor_capacity = 16;" in contents["A"] and
            b"inline constexpr std::size_t batch_max_bytes = 4096;" in contents["A"],
            "queue source difference is not exactly batch_max_frames 1 to 16 with fixed bounds")


def runtime_matches(server, frames, runtime):
    return (type(server.get("write_batch_max_frames")) is int and server["write_batch_max_frames"] == frames and
            all(type(server.get(name)) is type(value) and server[name] == value for name, value in runtime.items()))


def validate_contract(root, pair, variants, phase, freeze_path=None):
    require(phase in ("repro", "formal"), "unknown Gateway phase")
    source = read_json(root / pair["variants"]["A"]["directory"] / "source_manifest.json")
    require([r["id"] for r in source["rows"]] == ROWS, "Gateway source manifest must retain all seven rows in order")
    row_names = ["mixed_4", "mixed_1"] if phase == "repro" else ROWS
    spec = variants["A"]["workload_parameters"]
    require([r["id"] for r in spec["rows"]] == row_names and spec["rounds"] == 5,
            "Gateway requires the exact phase rows and five pairs per row")
    require(spec["commands"] >= 100000 and spec["minimum_plan_seconds"] >= 10,
            "Gateway planned sample count/duration is insufficient")
    manifest_path = root / pair["variants"]["A"]["directory"] / "source_manifest.json"
    derived = load_manifest(manifest_path, row_names if phase == "repro" else None)
    require(spec == derived, "Gateway workload parameters differ from the original row/seed mapping")
    if phase == "repro":
        require(pair["mode"] == "calibration" and source["rates_locked"] is False,
                "G04 must remain an unlocked calibration experiment")
        require([(r["id"], r["scenario"], r["connections"]) for r in spec["rows"]] ==
                [("mixed_4", "mixed", 4), ("mixed_1", "mixed", 1)],
                "G04 requires the mixed workload with four and one clients")
        require(spec["commands"] == 100000 and spec["minimum_plan_seconds"] == 10 and
                all(r["target_rate_per_sec"] == 10000 for r in spec["rows"]), "G04 requires fixed 10k/s reproduction")
    else:
        require(pair["mode"] == "formal" and source["rates_locked"] is True, "G06 requires a locked formal manifest")
        by_id = {row["id"]: row for row in spec["rows"]}
        ordinary = by_id["mixed_4"]["target_rate_per_sec"]
        require(all(by_id[name]["target_rate_per_sec"] == ordinary for name in ("cancel_heavy_4", "sweep_4", "mixed_1")) and
                ordinary < by_id["mixed_4_near"]["target_rate_per_sec"] <= by_id["mixed_4_overload"]["target_rate_per_sec"],
                "formal ordinary/near/high-load rate roles differ")
        require((by_id["burst_4"]["burst_period_ns"], by_id["burst_4"]["burst_window_ns"]) == (100000000, 10000000) and
                spec["warmup_commands"] == 1000 and
                all(row["commands"] / row["target_rate_per_sec"] <= 600 for row in spec["rows"]),
                "formal burst, warmup, or finite plan-duration contract differs")
    for key, manifest in variants.items():
        source_binding = manifest["server_source"]["source"]
        require(source_binding["dirty"] is False and source_binding["git_status"] == "" and
                manifest["environment"]["code_dirty"] is False, f"{key}: Gateway source must be clean")
        require(manifest["environment"]["os"].lower().startswith("linux"), "Gateway experiment must run on Linux")
        for name in ("server", "loadgen", "verifier"):
            record = manifest["binaries"][name]
            require(record["build_type"] == "Release" and record["sanitized"] is False,
                    f"{key}: Gateway requires unsanitized Release {name}")
    a, b = (source_identity(variants[k])["build_input_sha256"] for k in ("A", "B"))
    require(set(a) == set(b) and {name for name in a if a[name] != b[name]} == {"src/send_queue.hpp"},
            "batch A/B build inputs must differ only in src/send_queue.hpp")
    require(pair.get("measurement_tools") is not None, "Gateway requires a shared measurement-tool snapshot")
    runtime = dict(RUNTIME)
    receipt = None
    require(phase != "formal" or freeze_path is not None, "formal evaluation requires a freeze receipt")
    if freeze_path is not None:
        receipt = read_json(freeze_path)
        require(receipt["schema_version"] == 1 and receipt["phase"] == phase, "invalid phase freeze receipt")
        require(receipt["rules"] == RULES, "freeze rules differ from the Gateway adoption contract")
        require(receipt["source_manifest_sha256"] == variants["A"]["source_manifest_sha256"], "frozen manifest hash differs")
        require(receipt["variants"] == {k: source_identity(v) for k, v in variants.items()}, "frozen source/binary identity differs")
        require(receipt["binaries"] == {k: v["binaries"] for k, v in variants.items()}, "frozen binaries/build records differ")
        require(receipt["measurement_tools_sha256"] == pair["measurement_tools"]["sha256"], "frozen measurement tools differ")
        require(all(sha256(Path(__file__).with_name(name)) == digest for name, digest in receipt["measurement_tools_sha256"].items()),
                "current validator/tool code differs from frozen measurement code")
        require(receipt["evaluator_sha256"] == sha256(Path(__file__)), "evaluator differs from frozen analysis code")
        require(receipt["environment"] == {key: variants["A"]["environment"][key] for key in ENVIRONMENT},
                "frozen environment differs")
        runtime = receipt["runtime"]
        require(set(runtime) == set(RUNTIME) and all(type(runtime[k]) is type(v) and runtime[k] == v
                for k, v in RUNTIME.items() if k != "socket_send_buffer")
                and type(runtime["socket_send_buffer"]) is int and runtime["socket_send_buffer"] >= 0,
                "frozen runtime bounds/settings differ")
        checked_queue_sources(freeze_path.parent, receipt["queue_sources"], variants)
        checked_artifact(freeze_path.parent, receipt["plan"])
        frozen = checked_time(receipt["frozen_at_utc"])
        require(frozen < checked_time(pair["started_at_utc"]) and
                all(frozen < checked_time(item["started_at_utc"]) for item in pair["executed"]),
                "freeze must predate the experiment and all attempts")
    return runtime, receipt


def run_metrics(run_directory, validated, expected_frames, runtime):
    samples = read_csv(run_directory / "client/client_samples.csv", CLIENT_COLUMNS)
    completed = [row for row in samples if row["outcome"] == "completed"]
    require(len(samples) == validated["counts"]["planned"] and len(completed) == validated["counts"]["completed"],
            "Gateway measured sample denominator differs from validated counts")
    server = read_json(run_directory / "server/server.json")
    require(server == validated["server_counters"], "Gateway server counters differ from validated evidence")
    require(runtime_matches(server, expected_frames, runtime), "Gateway runtime or batch limit differs")
    values = []
    for row in completed:
        require(row["scheduled_ns"] is not None and row["complete_ns"] is not None and
                row["complete_ns"] >= row["scheduled_ns"], "missing or invalid scheduled-to-completion timestamps")
        elapsed = row["complete_ns"] - row["scheduled_ns"]
        require(elapsed == row["send_lag_ns"] + row["rtt_ns"], "scheduled-to-completion sample identity differs")
        values.append(elapsed)
    rtt = distribution([row["rtt_ns"] for row in completed])
    require(rtt == validated["rtt"], "RTT distribution is not the per-run nearest-rank result")
    require(all(type(server[k]) is int and server[k] >= 0 for k in ("user_cpu_us", "system_cpu_us")),
            "invalid server lifetime CPU counters")
    cpu = server["user_cpu_us"] + server["system_cpu_us"]
    connections = []
    for logical in sorted({row["logical"] for row in samples}):
        group = [row for row in samples if row["logical"] == logical]
        connections.append({"logical": logical, "planned": len(group),
                            "started": sum(row["first_attempt_ns"] is not None for row in group),
                            "completed": sum(row["outcome"] == "completed" for row in group),
                            "failed": sum(row["outcome"] == "failed" for row in group),
                            "unfinished": sum(row["outcome"] == "unfinished" for row in group),
                            "not_started": sum(row["first_attempt_ns"] is None for row in group)})
    return {"counts": validated["counts"], "succeeded": validated["succeeded"],
            "server_drained": validated["server_drained"], "failure": validated["failure"],
            "failure_reasons": validated["failure_reasons"], "server_close_reasons": server["close_reasons"],
            "uncompleted": server["uncompleted"], "discarded_business_frames": server["discarded_business_frames"],
            "missing_business_recipients": server["missing_business_recipients"],
            "scheduled_to_complete": distribution(values), "rtt": rtt, "send_lag": validated["send_lag"],
            "service": validated["service"], "gateway_wait": validated["gateway_wait"],
            "latency_scope": "fully_delivered" if validated["succeeded"] else "completed_subset_only",
            "server_lifetime_cpu_us": cpu, CPU_KEY: cpu / len(completed) if completed else None,
            "cpu_denominator": "measured_client_completed", "cpu_denominator_count": len(completed),
            "connections": connections,
            "client_samples_sha256": sha256(run_directory / "client/client_samples.csv"),
            "server_json_sha256": sha256(run_directory / "server/server.json"),
            "plan_window_seconds": validated["plan_window_seconds"]}


def percentage(a, b):
    return 100 * (b - a) / a if a is not None and a > 0 and b is not None else None


def summarize_values(values):
    values = [value for value in values if value is not None]
    return {"pairs": len(values), "median": median(values) if values else None,
            "min": min(values) if values else None, "max": max(values) if values else None}


def paired_metrics(a, b):
    both = a["succeeded"] and b["succeeded"]
    cpu = percentage(a[CPU_KEY], b[CPU_KEY]) if both else None
    return {"cpu_reduction_percent": -cpu if cpu is not None else None,
            "rtt_p99_change_percent": percentage(a["rtt"]["p99_ns"], b["rtt"]["p99_ns"]) if both else None,
            "scheduled_to_complete_p99_change_percent": percentage(a["scheduled_to_complete"]["p99_ns"], b["scheduled_to_complete"]["p99_ns"]) if both else None,
            "completed_fraction_difference": b["counts"]["completed"] / b["counts"]["planned"] -
                                             a["counts"]["completed"] / a["counts"]["planned"]}


def numeric_decision(pairs, phase):
    require(phase in ("repro", "formal"), "unknown Gateway phase")
    names = ["mixed_4", "mixed_1"] if phase == "repro" else ROWS
    require(len(pairs) == 5 * len(names) and {(p["row"], p["round"]) for p in pairs} ==
            {(name, n) for name in names for n in range(1, 6)}, "missing or duplicate Gateway pair")
    for pair in pairs:
        require(pair["both_succeeded"] == (pair["A"]["succeeded"] and pair["B"]["succeeded"]),
                "pair success differs from run outcomes")
        for side in (pair["A"], pair["B"]):
            require(not side["succeeded"] or (side["server_drained"] and not side["failure"] and
                    side["counts"]["completed"] == side["counts"]["planned"]),
                    "successful run has loss, failure, or incomplete drain")
        require(pair["metrics"] == paired_metrics(pair["A"], pair["B"]), "paired metrics differ from per-run values")
    per_row = []
    for name in names:
        items = [p for p in pairs if p["row"] == name]
        per_row.append({"row": name, "complete_pairs": sum(p["both_succeeded"] for p in items),
                        "metrics": {key: summarize_values(p["metrics"][key] for p in items) for key in items[0]["metrics"]}})
    if phase == "repro":
        return {"decision": "not_evaluated", "selected_variant": "A", "reason": "G04 is diagnostic reproduction; no adoption decision", "per_row": per_row}
    ordinary = [p for p in pairs if p["row"] != ROWS[-1]]
    near = next(r for r in per_row if r["row"] == "mixed_4_near")
    cpu = near["metrics"]["cpu_reduction_percent"]
    overloaded = [p["metrics"]["completed_fraction_difference"] for p in pairs if p["row"] == ROWS[-1]]
    gates = {
        "ordinary_and_near_delivery": all(p["both_succeeded"] for p in ordinary),
        "ordinary_and_near_samples": all(v["counts"]["completed"] >= 100000 and v["plan_window_seconds"] >= 10
                                         for p in ordinary for v in (p["A"], p["B"])),
        "near_cpu": cpu["pairs"] == 5 and cpu["median"] >= RULES["cpu_median_reduction_percent"] and
                    sum(p["metrics"]["cpu_reduction_percent"] is not None and p["metrics"]["cpu_reduction_percent"] > 0
                        for p in pairs if p["row"] == "mixed_4_near") >= RULES["cpu_min_improving_pairs"],
        "rtt_p99": all(r["metrics"]["rtt_p99_change_percent"]["pairs"] == 5 and
                       r["metrics"]["rtt_p99_change_percent"]["median"] <= RULES["p99_max_regression_percent"] for r in per_row[:-1]),
        "scheduled_to_complete_p99": all(r["metrics"]["scheduled_to_complete_p99_change_percent"]["pairs"] == 5 and
                                         r["metrics"]["scheduled_to_complete_p99_change_percent"]["median"] <= RULES["p99_max_regression_percent"] for r in per_row[:-1]),
        "overload_delivery": not (sum(v < 0 for v in overloaded) >= RULES["overload_worse_pairs"] and median(overloaded) < 0),
    }
    return {"decision": "numerically_eligible" if all(gates.values()) else "reject", "selected_variant": "A",
            "reason": "numeric gates passed; correctness evidence still required" if all(gates.values()) else "valid experiment failed one or more frozen numeric gates",
            "gates": gates, "per_row": per_row}


def correctness_receipt(path, variants):
    if path is None:
        return None
    receipt = read_json(path)
    require(receipt["schema_version"] == 1 and receipt["variants"] == {k: source_identity(v) for k, v in variants.items()},
            "correctness receipt source/binary identity differs")
    require(set(receipt["checks"]) == CORRECTNESS_CHECKS, "correctness receipt is incomplete")
    for name, check in receipt["checks"].items():
        require(check["status"] in ("passed", "failed") and check["artifacts"], f"missing correctness evidence: {name}")
        for artifact in check["artifacts"]:
            checked_artifact(path.parent, artifact)
    return {"sha256": sha256(path), "all_passed": all(c["status"] == "passed" for c in receipt["checks"].values()),
            "checks": receipt["checks"], "scope": "source-bound acceptance statements and artifact hashes; not inferred from benchmark metrics"}


def apply_correctness(decision, phase, correctness):
    if phase == "formal" and decision["decision"] == "numerically_eligible":
        if correctness is None:
            decision.update(decision="inconclusive", reason="numeric gates passed, but source-bound correctness/isolation evidence is missing")
        elif not correctness["all_passed"]:
            decision.update(decision="reject", reason="source-bound correctness/isolation checks failed")
        else:
            decision.update(decision="adopt", selected_variant="B", reason="all frozen numeric gates passed; the source-bound correctness receipt records all checks passed")


def analyze_copy(root, phase, freeze_path, correctness_path):
    validated = summarize_pair(root)
    pair = read_json(root / "pair-manifest.json")
    variants = {key: read_json(local_file(root, binding["directory"]) / "manifest.json") for key, binding in pair["variants"].items()}
    runtime, freeze = validate_contract(root, pair, variants, phase, freeze_path)
    entries = {key: {r["id"]: r for r in manifest["expectedRuns"]} for key, manifest in variants.items()}
    # Warmup observations must use the same batch/runtime settings, too.
    warmups = []
    for key, manifest in variants.items():
        side = local_file(root, pair["variants"][key]["directory"])
        for entry in manifest["expectedRuns"]:
            if entry["kind"] == "warmup":
                server = read_json(local_file(side, entry["directory"]) / "server/server.json")
                require(runtime_matches(server, 1 if key == "A" else 16, runtime),
                        "warmup Gateway runtime or batch limit differs")
                run = next(row for row in read_json(side / "report.json")["runs"] if row["id"] == entry["id"])
                warmups.append({"variant": key, "id": entry["id"],
                                **{name: run[name] for name in ("succeeded", "server_drained", "counts", "failure", "failure_reasons")}})
    pairs = []
    for item in validated["pairs"]:
        sides = {}
        for key in ("A", "B"):
            side = local_file(root, pair["variants"][key]["directory"])
            run_dir = local_file(side, entries[key][item["id"]]["directory"])
            sides[key] = run_metrics(run_dir, item[key], 1 if key == "A" else 16, runtime)
            claimed = item["resources"][key][CPU_KEY]
            actual = sides[key][CPU_KEY]
            require((actual is None and claimed is None) or
                    (actual is not None and claimed is not None and math.isclose(actual, claimed, rel_tol=1e-12)),
                    "paired CPU denominator differs from measured client completions")
        pairs.append({"id": item["id"], "row": item["row"], "round": item["round"],
                      "both_succeeded": item["both_succeeded"], "input_sha256": item["input_sha256"],
                      **sides, "metrics": paired_metrics(sides["A"], sides["B"])})
    decision = numeric_decision(pairs, phase)
    correctness, correctness_error = None, None
    try:
        correctness = correctness_receipt(correctness_path, variants)
    except (OSError, ValueError, KeyError, TypeError, IndexError, AttributeError) as error:
        # This additional acceptance evidence cannot erase a valid benchmark rejection.
        correctness_error = str(error)
    apply_correctness(decision, phase, correctness)
    if correctness_error is not None and decision["decision"] == "inconclusive":
        decision["reason"] = "numeric gates passed, but source-bound correctness/isolation evidence is invalid"
    return {"schema_version": 1, "evidence_valid": True, "phase": phase, **decision, "pairs": pairs, "warmups": warmups,
            "runtime": runtime, "rules": RULES, "correctness": correctness, "correctness_error": correctness_error,
            "freeze_sha256": sha256(freeze_path) if freeze else None,
            "exact_queue_source_difference_verified": freeze is not None,
            "analysis_tools_sha256": {name: sha256(Path(__file__).with_name(name)) for name in pair["measurement_tools"]["sha256"]},
            "notes": "Per-run nearest-rank quantiles of completed measured requests. Failed subsets are descriptive only. "
                     "Percent changes are per pair, then medians; never pooled percentiles or sums of p99. "
                     "CPU includes setup and process-lifetime overhead, divided by measured client completions."}


def evaluate(directory, phase, output, freeze=None, correctness=None):
    root, output = Path(directory).resolve(), Path(output).resolve()
    require(root.is_dir(), "evidence directory does not exist")
    require(not output.is_relative_to(root) and not root.is_relative_to(output), "output must be outside the source evidence tree")
    require(not output.exists(), "output directory already exists; preserve prior attempts")
    before = tree_identity(root)
    output.mkdir(parents=True)
    result = None
    try:
        with tempfile.TemporaryDirectory(prefix="recompute-", dir=output) as temporary:
            copied = Path(temporary) / "evidence"
            shutil.copytree(root, copied)
            require(tree_identity(copied) == before, "temporary evidence copy differs")
            try:
                result = analyze_copy(copied, phase, Path(freeze).resolve() if freeze else None,
                                      Path(correctness).resolve() if correctness else None)
            finally:
                logs = output / "validation"
                logs.mkdir()
                for name in ("independent-summary-A.log", "independent-summary-B.log", "pair-report.json", "pair-report.md"):
                    if (copied / name).is_file():
                        shutil.copyfile(copied / name, logs / name)
    except (OSError, ValueError, KeyError, TypeError, IndexError, StopIteration) as error:
        result = {"schema_version": 1, "evidence_valid": False, "phase": phase,
                  "decision": "inconclusive", "selected_variant": "A", "error": str(error)}
    after = tree_identity(root)
    require(before == after, "source evidence changed during evaluation")
    result.update(source_evidence=str(root), source_identity_before=before, source_identity_after=after,
                  source_unchanged=True, evaluator_sha256=sha256(Path(__file__)))
    write_json(output / "gateway-evaluation.json", result)
    lines = ["# Gateway evaluation", "", f"Decision: {result['decision']}; selected variant: {result['selected_variant']}.", "",
             result.get("reason", result.get("error", "")), "", "Source evidence was not modified."]
    if result.get("correctness_error"):
        lines += ["", f"Correctness receipt error: {result['correctness_error']}"]
    if result.get("per_row"):
        lines += ["", "| Row | Complete pairs | CPU reduction median % | RTT p99 change median % | Scheduled-to-complete p99 change median % |",
                  "|---|---:|---:|---:|---:|"]
        for row in result["per_row"]:
            m = row["metrics"]
            lines.append(f"| {row['row']} | {row['complete_pairs']}/5 | {m['cpu_reduction_percent']['median']} | {m['rtt_p99_change_percent']['median']} | {m['scheduled_to_complete_p99_change_percent']['median']} |")
    (output / "gateway-evaluation.md").write_text("\n".join(lines) + "\n")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--phase", choices=("repro", "formal"), required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--freeze", type=Path)
    parser.add_argument("--correctness", type=Path)
    args = parser.parse_args()
    try:
        report = evaluate(args.directory, args.phase, args.output_dir, args.freeze, args.correctness)
        print(f"Gateway {report['decision']}; evidence valid: {report['evidence_valid']}; report: {args.output_dir}")
        raise SystemExit(0 if report["evidence_valid"] else 2)
    except (OSError, ValueError, KeyError, TypeError, IndexError) as error:
        print(f"evaluate_gateway_experiment: {error}", file=sys.stderr)
        raise SystemExit(2)
