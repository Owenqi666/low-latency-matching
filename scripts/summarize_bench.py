#!/usr/bin/env python3
"""Validate complete benchmark evidence before producing per-round reports."""
import argparse
import csv
import math
from collections import defaultdict
from pathlib import Path
import json

from create_bench_workloads import file_hashes, write_json

LATENCY_COLUMNS = ["index", "command_kind", "result", "reject_reason", "event_count", "trade_count", "ns"]
VERIFICATION_COLUMNS = LATENCY_COLUMNS[:-1] + ["swept_levels", "live_orders"]
KINDS = {0: "limit", 1: "market", 2: "cancel"}
REASONS = {0: "none", 1: "invalid_client", 2: "invalid_request", 3: "invalid_order",
           4: "invalid_side", 5: "invalid_quantity", 6: "invalid_price", 7: "duplicate_order",
           8: "unknown_order", 9: "not_owner", 10: "capacity_exceeded"}
COUNT_FIELDS = ("completed", "accepted", "rejected", "trades", "events")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def quantile(samples, fraction):
    ordered = sorted(samples)
    require(bool(ordered), "cannot calculate a quantile from no samples")
    return ordered[max(0, math.ceil(fraction * len(ordered)) - 1)]


def safe_file(directory, name):
    require(isinstance(name, str) and Path(name).name == name, "artifact must name a local file")
    return directory / name


def read_samples(path, columns):
    rows = []
    with path.open(newline="", encoding="utf-8") as source:
        reader = csv.DictReader(source)
        require(reader.fieldnames == columns, f"{path}: wrong CSV header")
        for index, raw in enumerate(reader):
            require(None not in raw and all(raw[name] is not None for name in columns), f"{path}: incomplete row")
            row = {name: int(raw[name]) for name in columns}
            require(all(value >= 0 for value in row.values()), f"{path}: negative field")
            require(row["index"] == index, f"{path}: missing/duplicate sample index")
            require(row["command_kind"] in KINDS and row["result"] in (1, 2), f"{path}: invalid kind/result")
            require(row["reject_reason"] in REASONS, f"{path}: invalid reject reason")
            require((row["result"] == 1) == (row["reject_reason"] == 0), f"{path}: outcome/reason mismatch")
            require(row["event_count"] >= 2, f"{path}: missing command events")
            if row["result"] == 2:
                require(row["trade_count"] == 0 and row["event_count"] == 2, f"{path}: invalid rejected command")
            rows.append(row)
    return rows


def counts(rows):
    return {"completed": len(rows), "accepted": sum(row["result"] == 1 for row in rows),
            "rejected": sum(row["result"] == 2 for row in rows),
            "trades": sum(row["trade_count"] for row in rows),
            "events": sum(row["event_count"] for row in rows)}


def validate_run(directory):
    directory = Path(directory)
    manifest = read_json(directory / "run_manifest.json")
    workload = read_json(directory / "workload.json")
    summary = read_json(directory / "summary.json")
    require(manifest["schema_version"] == 1 and summary["schema_version"] == 1, "unsupported result schema")
    require(summary["hash_algorithm"] == "fnv1a64", "unsupported benchmark hash algorithm")
    clock_record = manifest["clock_probe"]
    clock_file = safe_file(directory, clock_record["path"])
    require(all(clock_record[key] == value for key, value in file_hashes(clock_file).items()), "clock probe hash mismatch")
    clock = read_json(clock_file)
    require(clock["schema_version"] == 1 and clock["is_steady"] is True and clock["samples"] > 0,
            "invalid clock probe")
    require(clock["nominal_period_den"] > 0 and 0 <= clock["back_to_back_p50_ns"] <= clock["back_to_back_p99_ns"] and
            clock["pair_and_duration_record_batch_ns"] > 0 and clock["clock_and_timestamp_record_batch_ns"] > 0,
            "invalid clock measurements")
    for name in ("config", "setup", "input"):
        expected = workload["files"][name]
        actual = file_hashes(safe_file(directory, expected["path"]))
        require(actual == {k: expected[k] for k in actual}, f"{name}: workload input hash mismatch")
        require(actual == {k: manifest["inputs"][name][k] for k in actual}, f"{name}: recorded input hash mismatch")
        require(summary[f"{name}_hash"] == actual["fnv1a64"], f"{name}: benchmark input hash mismatch")

    verification = summary["verification"]
    require(verification["passed"] is True, "reference verification did not pass")
    verified_file = directory / "verified_final.snapshot"
    verified_hash = file_hashes(verified_file)["fnv1a64"]
    require(verified_hash == verification["final_snapshot_hash"], "verified snapshot hash mismatch")
    verified_bytes = verified_file.read_bytes()
    require(verified_bytes.startswith(b"BOOK 1\n"), "invalid final snapshot format")
    reference_rows = read_samples(safe_file(directory, verification["characteristics_file"]), VERIFICATION_COLUMNS)
    expected_counts = counts(reference_rows)
    require(expected_counts["completed"] == workload["commands"], "verification sample count mismatch")
    require(expected_counts["accepted"] == workload["expected_accepted"] and
            expected_counts["rejected"] == workload["expected_rejected"], "generated workload outcomes differ")
    require([row["index"] for row in reference_rows if row["result"] == 2] == workload["expected_rejection_indices"],
            "unexpected rejection positions")
    require(all(row["reject_reason"] == 8 for row in reference_rows if row["result"] == 2),
            "deliberate unknown-order cancellations returned a different rejection")
    for key in COUNT_FIELDS:
        require(verification[key] == expected_counts[key], f"verification {key} mismatch")
    require(verification["setup_live_orders"] == workload["initial_live_orders"], "setup depth mismatch")
    require(verification["end_live_orders"] == workload["planned_end_live_orders"], "ending depth mismatch")
    require(reference_rows[-1]["live_orders"] == verification["end_live_orders"], "last sample depth mismatch")
    for row in reference_rows:
        require(row["live_orders"] <= workload["capacity"] and row["swept_levels"] <= row["trade_count"],
                "invalid live-order/sweep characteristics")
    input_kinds = [line.split()[0] for line in (directory / "input.trace").read_text().splitlines()
                   if line and not line.startswith("#")][1:]
    require([KINDS[row["command_kind"]][0].upper() for row in reference_rows] == input_kinds,
            "verification command sequence differs from input")

    repeats = manifest["repeats"]
    require(type(repeats) is int and repeats > 0, "invalid repeat count")
    require(summary["repeats"] == repeats and summary["max_live_orders"] == workload["capacity"], "measurement configuration mismatch")
    require(summary["quantile_method"] == "nearest-rank", "unsupported quantile method")
    require(summary["sink_capacity"] == workload["capacity"] + 4 and summary["event_bytes"] > 0 and
            summary["sink_bytes"] == summary["sink_capacity"] * summary["event_bytes"], "invalid output sink dimensions")
    expected_rounds = {(mode, number) for mode in ("latency", "throughput") for number in range(1, repeats + 1)}
    actual_rounds = [(item["mode"], item["round"]) for item in summary["rounds"]]
    require(len(actual_rounds) == len(expected_rounds) and set(actual_rounds) == expected_rounds,
            "missing or duplicate measurement round")
    report_rounds = []
    for item in summary["rounds"]:
        mode, number = item["mode"], item["round"]
        require(item["verified"] is True, f"{mode} {number}: verification failed")
        for key in COUNT_FIELDS:
            require(item[key] == expected_counts[key], f"{mode} {number}: {key} mismatch")
        require(item["checksum"] == verification["checksum"], f"{mode} {number}: event checksum mismatch")
        snapshot = directory / f"{mode}_{number}.snapshot"
        require(item["final_snapshot_hash"] == verified_hash and snapshot.read_bytes() == verified_bytes,
                f"{mode} {number}: final snapshot mismatch")
        require(type(item["elapsed_ns"]) is int and item["elapsed_ns"] > 0, "invalid elapsed time")
        result = {key: item[key] for key in ("mode", "round", "elapsed_ns", *COUNT_FIELDS)}
        for key in ("batch_elapsed_ns", "max_rss_bytes", "cpu_user_us", "cpu_system_us"):
            result[key] = item[key]
        if mode == "latency":
            rows = read_samples(safe_file(directory, item["samples_file"]), LATENCY_COLUMNS)
            require(len(rows) == len(reference_rows), f"latency {number}: incomplete samples")
            for sample, reference in zip(rows, reference_rows):
                require(all(sample[key] == reference[key] for key in LATENCY_COLUMNS[:-1]),
                        f"latency {number}: sample result differs from verification")
            samples = [row["ns"] for row in rows]
            require(sum(samples) == item["elapsed_ns"], f"latency {number}: sample timing sum mismatch")
            require(quantile(samples, .5) == item["p50_ns"] and quantile(samples, .99) == item["p99_ns"],
                    f"latency {number}: reported quantile mismatch")
            result.update(p50_ns=quantile(samples, .5), p99_ns=quantile(samples, .99),
                          p99_sample_threshold_met=len(samples) >= 100000, groups=[])
            groups = defaultdict(list)
            for row in rows:
                groups[(row["command_kind"], row["result"], row["reject_reason"])].append(row["ns"])
            for (kind, outcome, reason), values in sorted(groups.items()):
                result["groups"].append({"command": KINDS[kind], "outcome": "accepted" if outcome == 1 else "rejected",
                                         "reason": REASONS[reason], "samples": len(values),
                                         "p50_ns": quantile(values, .5), "p99_ns": quantile(values, .99),
                                         "p99_sample_threshold_met": len(values) >= 100000})
        else:
            require(item["samples_file"] is None, "throughput must not claim latency samples")
            seconds = item["elapsed_ns"] / 1e9
            result.update(completed_per_second=item["completed"] / seconds,
                          accepted_per_second=item["accepted"] / seconds,
                          trades_per_second=item["trades"] / seconds)
        report_rounds.append(result)
    live = [row["live_orders"] for row in reference_rows]
    return {"directory": str(directory.resolve()), "scenario": workload["scenario"], "capacity": workload["capacity"],
            "commands": workload["commands"], "repeats": repeats, "initial_live_orders": workload["initial_live_orders"],
            "seed": workload["seed"], "working_depth_parameter": workload["working_depth"],
            "command_counts": workload["command_counts"], "workload_notes": workload["notes"], "pattern": workload["pattern"],
            "minimum_five_rounds_met": repeats >= 5,
            "end_live_orders": verification["end_live_orders"],
            "live_orders_after_commands": {"min": min(live), "max": max(live), "mean": sum(live) / len(live),
                                            "p50": quantile(live, .5), "p99": quantile(live, .99)},
            "max_trades_per_command": max(row["trade_count"] for row in reference_rows),
            "max_swept_levels": max(row["swept_levels"] for row in reference_rows),
            "max_events_per_command": max(row["event_count"] for row in reference_rows),
            "rejection_fraction": expected_counts["rejected"] / expected_counts["completed"],
            "resource_scope": summary["resource_scope"], "rounds": report_rounds,
            "timing_scope": summary["timing_scope"], "clock_probe": clock,
            "output_sink": {key: summary[key] for key in ("sink_capacity", "sink_bytes", "event_bytes")},
            "inputs": manifest["inputs"], "environment": manifest["environment"]}


def summarize(directory):
    directory = Path(directory)
    files = sorted(directory.rglob("summary.json"))
    require(bool(files), f"{directory}: no benchmark summary.json files")
    runs = [validate_run(path.parent) for path in files]
    report = {"schema_version": 1, "validation": "passed", "quantile_algorithm": "nearest-rank",
              "p99_note": "The 100000-sample reporting threshold does not establish statistical stability.",
              "runs": runs}
    text = ["# M1 core benchmark report", "", "All listed raw inputs, samples, counts and final snapshots passed validation.",
            "Latency includes synchronous result generation. Throughput uses separately timed batches. No network/queue latency is measured.",
            "p99 is marked when below the 100,000-sample reporting threshold. Meeting this threshold does not establish statistical stability.", ""]
    for run in runs:
        text += [f"## {run['scenario']} / capacity {run['capacity']}", "",
                 run["pattern"], "", run["workload_notes"], "",
                 f"Commands: {run['commands']}; rounds per mode: {run['repeats']}; live orders setup → end: "
                 f"{run['initial_live_orders']} → {run['end_live_orders']}; rejection fraction: {run['rejection_fraction']:.4%}.", "",
                 "| Mode | Round | p50 ns | p99 ns | Completed/s | Accepted/s | Trade/s | Rejections |",
                 "| --- | --- | --- | --- | --- | --- | --- | --- |"]
        if not run["minimum_five_rounds_met"]:
            text.insert(len(text) - 2, "Short functional smoke only: fewer than five rounds per mode; not final performance evidence.\n")
        for item in run["rounds"]:
            if item["mode"] == "latency":
                label = "" if item["p99_sample_threshold_met"] else " (below sample threshold)"
                text.append(f"| latency | {item['round']} | {item['p50_ns']} | {item['p99_ns']}{label} | — | — | — | {item['rejected']} |")
            else:
                text.append(f"| throughput | {item['round']} | — | — | {item['completed_per_second']:.1f} | "
                            f"{item['accepted_per_second']:.1f} | {item['trades_per_second']:.1f} | {item['rejected']} |")
        text += ["", "### Latency by command and outcome", "",
                 "| Round | Command / outcome / reason | Samples | p50 ns | p99 ns |",
                 "| --- | --- | --- | --- | --- |"]
        for item in run["rounds"]:
            for group in item.get("groups", []):
                label = "" if group["p99_sample_threshold_met"] else " (below sample threshold)"
                text.append(f"| {item['round']} | {group['command']} / {group['outcome']} / {group['reason']} | "
                            f"{group['samples']} | {group['p50_ns']} | {group['p99_ns']}{label} |")
        text += ["", f"Resource scope: {run['resource_scope']}", "",
                 "Environment, build identity, actual depth distribution and input hashes are retained in report.json and run_manifest.json.", ""]
    write_json(directory / "report.json", report)
    (directory / "report.md").write_text("\n".join(text), encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    report = summarize(args.directory)
    print(f"validated {len(report['runs'])} workload/capacity runs; wrote {args.directory / 'report.md'}")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise SystemExit(f"summarize_bench: {error}")
