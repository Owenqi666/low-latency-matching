#!/usr/bin/env python3
"""Validate complete A/B evidence and report paired, per-round differences."""
import argparse
from datetime import datetime
from pathlib import Path
from statistics import median
import subprocess
import sys

from create_service_workloads import sha256, write_json
from summarize_service_bench import local_file, read_json, require


def summarize(directory):
    root = Path(directory).resolve()
    for name in ("pair-report.json", "pair-report.md"):
        (root / name).unlink(missing_ok=True)
    pair = read_json(root / "pair-manifest.json")
    require(pair["schema_version"] == 1 and pair["status"] in ("completed", "failed"), "pair manifest is not terminal")
    require(set(pair["variants"]) == {"A", "B"}, "pair must contain exactly A and B")
    variants, reports, locations = {}, {}, {}
    for key in ("A", "B"):
        binding = pair["variants"][key]
        variant_root = local_file(root, binding["directory"])
        locations[key] = variant_root
        manifest = read_json(variant_root / "manifest.json")
        variants[key] = manifest
        evidence = variant_root / "build-evidence"
        source = read_json(evidence / "source.json")
        require(source == binding["source"] and manifest["server_source"] == binding and
                sha256(evidence / "source.json") == binding["source_record_sha256"], f"{key}: source binding differs")
        cache = (evidence / "CMakeCache.txt").read_text()
        cache_home = next(line.split("=", 1)[1] for line in cache.splitlines() if line.startswith("CMAKE_HOME_DIRECTORY:INTERNAL="))
        require(cache_home == source["directory"] == source["cmake_home_directory"], f"{key}: wrong source for CMake build")
        require(source["commit"] == manifest["environment"]["code_commit"] and
                source["dirty"] == manifest["environment"]["code_dirty"], f"{key}: source/environment identity differs")
        require(source["server_sha256"] == manifest["binaries"]["server"]["sha256"], f"{key}: source bound to a different server")
        require(sha256(evidence / "CMakeCache.txt") == source["cmake_cache_sha256"] == manifest["binaries"]["server"]["cmake_cache_sha256"] and
                sha256(evidence / "compile_commands.json") == source["compile_commands_sha256"], f"{key}: build evidence hash differs")
        with (root / f"independent-summary-{key}.log").open("wb") as log:
            result = subprocess.run([sys.executable, str(Path(__file__).with_name("summarize_service_bench.py")), str(variant_root)],
                                    stdout=log, stderr=subprocess.STDOUT)
        require(result.returncode == 0, f"{key}: independent service summary failed; see independent-summary-{key}.log")
        reports[key] = read_json(variant_root / "report.json")
        require(all(run["client_resources"] is not None for run in reports[key]["runs"]),
                f"{key}: paired runs require loadgen resource snapshots")
    require(locations["A"] != locations["B"], "A and B cannot point to the same evidence directory")
    a, b = variants["A"], variants["B"]
    require(a["mode"] == b["mode"] == pair["mode"] and a["workload_parameters"] == b["workload_parameters"] and
            a["source_manifest_sha256"] == b["source_manifest_sha256"], "A/B workloads differ")
    for tool in ("loadgen", "verifier"):
        require(a["binaries"][tool] == b["binaries"][tool], f"A/B {tool} differs")
    for field in ("build_type", "compiler", "build_flags", "target_compile_flags", "sanitized"):
        require(a["binaries"]["server"][field] == b["binaries"]["server"][field], f"A/B server {field} differs")
    for field in ("os", "kernel", "architecture", "logical_cpus", "thread_configuration", "transport", "host_environment"):
        require(a["environment"][field] == b["environment"][field], f"A/B environment {field} differs")
    spec = a["workload_parameters"]
    expected = []
    for row in spec["rows"]:
        for repeat in range(spec["rounds"] + 1):
            kind = "warmup" if repeat == 0 else "measurement"
            suffix = "warmup" if repeat == 0 else f"round_{repeat}"
            order = ("B", "A") if repeat > 0 and repeat % 2 == 0 else ("A", "B")
            expected.extend({"variant": key, "id": f"{row['id']}-{suffix}", "row": row["id"], "round": repeat, "kind": kind}
                            for key in order)
    require(pair["execution_plan"] == expected and len(pair["executed"]) == len(expected), "pair plan is incomplete or does not alternate AB/BA")
    entries = {key: {item["id"]: item for item in manifest["expectedRuns"]} for key, manifest in variants.items()}
    runs = {key: {item["id"]: item for item in report["runs"]} for key, report in reports.items()}
    previous_end = None
    for planned, actual in zip(expected, pair["executed"]):
        require(all(actual[name] == value for name, value in planned.items()), "executed order differs from frozen plan")
        key = planned["variant"]
        run = read_json(local_file(locations[key], entries[key][planned["id"]]["directory"]) / "run.json")
        require(all(run[name] == actual[name] for name in ("status", "started_at_utc", "ended_at_utc")), "pair execution record differs from actual run")
        start, end = (datetime.fromisoformat(run[name]) for name in ("started_at_utc", "ended_at_utc"))
        require(end >= start and (previous_end is None or start >= previous_end), "A/B executions overlap or run out of order")
        previous_end = end
    comparisons = []
    for entry in a["expectedRuns"]:
        name = entry["id"]
        identities = []
        for key in ("A", "B"):
            run = read_json(local_file(locations[key], entries[key][name]["directory"]) / "run.json")
            identities.append({field: item["sha256"] for field, item in run["inputs"].items()})
        require(identities[0] == identities[1], f"{name}: paired inputs differ")
        if entry["kind"] == "warmup":
            continue
        left, right = runs["A"][name], runs["B"][name]
        complete = left["succeeded"] and right["succeeded"]
        deltas = {}
        for metric in ("rtt", "service", "gateway_wait", "send_lag"):
            for quantile in ("p50_ns", "p99_ns"):
                av = left[metric][quantile] if left[metric] else None
                bv = right[metric][quantile] if right[metric] else None
                deltas[f"{metric}_{quantile}"] = bv - av if complete and av is not None and bv is not None else None
                if metric == "rtt":
                    deltas[f"{metric}_{quantile}_percent"] = 100 * (bv - av) / av if complete and av and bv is not None else None
        deltas["completed_per_second"] = right["completed_per_second"] - left["completed_per_second"] if complete else None
        resources = {}
        for key, value in (("A", left), ("B", right)):
            counters = value["server_counters"]
            cpu = counters["user_cpu_us"] + counters["system_cpu_us"]
            client = value["client_resources"]
            completed = value["counts"]["completed"]
            resources[key] = {"server_lifetime_cpu_us": cpu,
                              "server_lifetime_cpu_us_per_completed_measured_request": cpu / completed if completed else None,
                              "loadgen_lifetime_cpu_us": client["user_cpu_us"] + client["system_cpu_us"],
                              "loadgen_peak_rss_bytes": client["peak_rss_bytes"]}
        cpu_key = "server_lifetime_cpu_us_per_completed_measured_request"
        deltas[cpu_key] = resources["B"][cpu_key] - resources["A"][cpu_key] if complete else None
        comparisons.append({"id": name, "row": entry["row"], "round": entry["round"],
                            "both_succeeded": complete, "input_sha256": identities[0],
                            "A": left, "B": right, "resources": resources, "B_minus_A": deltas})
    by_row = []
    for row in spec["rows"]:
        items = [item for item in comparisons if item["row"] == row["id"]]
        summary = {}
        for metric in items[0]["B_minus_A"]:
            values = [item["B_minus_A"][metric] for item in items if item["B_minus_A"][metric] is not None]
            summary[metric] = {"paired_successes": len(values), "median": median(values) if values else None,
                               "min": min(values) if values else None, "max": max(values) if values else None}
        by_row.append({"row": row["id"], "pairs": len(items), "complete_pairs": sum(item["both_succeeded"] for item in items), "B_minus_A": summary})
    succeeded = all(report["all_runs_succeeded"] for report in reports.values())
    require((pair["status"] == "completed") == succeeded, "pair status contradicts observed outcomes")
    report = {"schema_version": 1, "evidence_valid": True, "all_runs_succeeded": succeeded, "mode": pair["mode"],
              "variants": pair["variants"], "shared_tools": {name: a["binaries"][name] for name in ("loadgen", "verifier")},
              "warmup_attempts": 2 * len(spec["rows"]),
              "measured_attempts": 2 * len(comparisons), "pairs": comparisons, "per_row": by_row,
              "notes": "B minus A describes per-round differences, not a pooled percentile. Failed pairs retain both outcomes; "
                       "latency/rate deltas exclude them and are never evidence of overload speedup. "
                       "Server/loadgen CPU and RSS cover process lifetime before evidence output, including setup; "
                       "loadgen also includes input preparation. Dividing server CPU by measured completions is an amortized cost, not a request-only CPU window. "
                       "Server source binding records CMake provenance and source hashes, not reproducible-build attestation. "
                       "Shared loadgen/verifier are separately bound by their own binary hashes and build records."}
    write_json(root / "pair-report.json", report)
    lines = ["# Service A/B comparison", "", f"Mode: {pair['mode']}. All {2 * len(comparisons)} measured attempts retained.", "",
             "| Pair | A complete/planned | B complete/planned | RTT p99 A/B (ns) | Paired difference (ns) | Both succeeded |",
             "|---|---:|---:|---:|---:|---|"]
    for item in comparisons:
        left, right = item["A"], item["B"]
        lines.append(f"| {item['id']} | {left['counts']['completed']}/{left['counts']['planned']} | "
                     f"{right['counts']['completed']}/{right['counts']['planned']} | {left['rtt']['p99_ns']}/{right['rtt']['p99_ns']} | "
                     f"{item['B_minus_A']['rtt_p99_ns']} | {item['both_succeeded']} |")
    lines.extend(["", report["notes"], "", "Per-pair counts, resources, other latency metrics and median/range summaries are in pair-report.json.", ""])
    (root / "pair-report.md").write_text("\n".join(lines))
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    try:
        result = summarize(args.directory)
        print(f"Validated {result['measured_attempts']} measured attempts; all succeeded: {result['all_runs_succeeded']}")
    except (OSError, ValueError, KeyError, TypeError, IndexError, StopIteration) as error:
        raise SystemExit(f"summarize_service_pair: {error}")
