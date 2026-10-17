#!/usr/bin/env python3
"""Independently validate M4 core pairs, then report absolute and paired metrics."""
import argparse
from datetime import datetime
from pathlib import Path
from statistics import median

from create_bench_workloads import file_hashes, write_json
from summarize_bench import read_json, require, validate_run

SCENARIOS = ("mixed", "cancel_heavy", "sweep", "clustered", "near_full_reuse")
WORKLOAD_FILES = ["mixed.manifest", "cancel_heavy.manifest", "sweep.manifest",
                  "clustered.manifest", "near-full-reuse.manifest"]


def execution_plan(spec):
    return [{"variant": variant, "scenario": scenario, "pair": number,
             "directory": f"{'baseline' if variant == 'A' else 'candidate'}/{scenario}/pair_{number}"}
            for scenario in spec["scenarios"] for number in range(1, spec["rounds"] + 1)
            for variant in ("AB" if number % 2 else "BA")]


def sha256(path):
    return file_hashes(path)["sha256"]


def distribution(values):
    return {"median": median(values), "min": min(values), "max": max(values), "values": values}


def summarize(root):
    root = Path(root)
    for name in ("pair-summary.json", "pair-report.md"):
        (root / name).unlink(missing_ok=True)
    pair = read_json(root / "pair-manifest.json")
    require(pair["schema_version"] == 1, "unsupported core pair schema")
    require(pair["status"] == "completed", "core pair experiment did not complete")
    spec = pair["specification"]
    require(spec["mode"] in ("formal", "smoke"), "unknown core pair mode")
    require(type(spec["rounds"]) is int and spec["rounds"] > 0 and spec["commands"] > 0,
            "invalid core pair dimensions")
    require(len(spec["scenarios"]) == len(set(spec["scenarios"])) and
            set(spec["scenarios"]) <= set(SCENARIOS), "unknown/duplicate core scenario")
    if spec["mode"] == "formal":
        require(tuple(spec["scenarios"]) == SCENARIOS and spec["capacity"] == 1000 and
                spec["commands"] == 100000 and spec["rounds"] == 5, "incomplete formal core matrix")
    plan = execution_plan(spec)
    require(pair["execution_plan"] == plan, "core pair execution plan differs from fixed AB/BA order")
    require(len(pair["executed"]) == len(plan), "missing or duplicate core pair run")
    require(set(pair["workloads"]) == set(spec["scenarios"]), "missing/extra workload identity")
    require(set(pair["variants"]) == {"A", "B"}, "missing/extra variant identity")
    expected_directories = {item["directory"] for item in plan}
    actual_directories = {str(path.parent.relative_to(root)) for path in root.rglob("run_manifest.json")}
    require(actual_directories == expected_directories, "missing or orphan core run evidence")
    require(sha256(root / "source-manifest.json") == pair["source_manifest_sha256"], "source manifest hash mismatch")
    source_spec = read_json(root / "source-manifest.json")
    require(source_spec == {"schema_version": 1, "mode": "formal", "capacity": 1000,
                            "commands": 100000, "rounds": 5, "workloads": WORKLOAD_FILES},
            "frozen core source manifest contract differs")
    if spec["mode"] == "formal":
        require(spec == {**source_spec, "scenarios": list(SCENARIOS)}, "formal specification differs from source manifest")
    else:
        require(set(spec) == set(source_spec) | {"scenarios"} and
                all(spec[key] == source_spec[key] for key in ("schema_version", "capacity", "workloads")),
                "smoke specification changes a fixed source manifest field")
    if "host_environment_sha256" in pair:
        require(sha256(root / "host-environment.json") == pair["host_environment_sha256"], "host environment hash mismatch")
    for name, digest in pair["shared_tools"].items():
        require(Path(name).name == name and sha256(root / "tool-evidence" / name) == digest, "shared tool hash mismatch")
    require(set(pair["shared_tools"]) == {"create_bench_workloads.py", "run_bench.py", "summarize_bench.py",
                                           "run_core_pair.py", "summarize_core_pair.py"}, "missing shared tool identity")
    for variant, binding in pair["variants"].items():
        directory = root / ("baseline" if variant == "A" else "candidate") / "build-evidence"
        source = binding["source"]
        require(sha256(directory / "source.json") == binding["source_record_sha256"] and
                read_json(directory / "source.json") == source, "source record mismatch")
        require(sha256(directory / "CMakeCache.txt") == source["cmake_cache_sha256"] and
                sha256(directory / "compile_commands.json") == source["compile_commands_sha256"], "build evidence hash mismatch")
        cache = (directory / "CMakeCache.txt").read_text()
        require(f"CMAKE_HOME_DIRECTORY:INTERNAL={source['cmake_home_directory']}\n" in cache and
                source["cmake_home_directory"] == source["directory"], "build source binding mismatch")
        env = binding["environment"]
        require(env["code_commit"] == source["commit"] and env["binary_sha256"] == source["binary_sha256"] and
                env["cmake_cache_sha256"] == source["cmake_cache_sha256"], "source/environment identity mismatch")
        require(env["build_type"] == "Release" and env["sanitizers"] == "OFF", "invalid timing build")
        if spec["mode"] == "formal":
            require(source["dirty"] is False and env["code_dirty"] is False and env["os"].startswith("Linux"),
                    "formal source must be clean and run on Linux")
    for field in ("compiler", "build_type", "sanitizers", "build_flags", "target_compile_flags"):
        require(pair["variants"]["A"]["environment"][field] == pair["variants"]["B"]["environment"][field],
                f"A/B {field} differs")
    for scenario, workload in pair["workloads"].items():
        directory = root / "inputs" / scenario
        require(sha256(directory / "source.manifest") == workload["source_manifest_sha256"] and
                sha256(directory / "workload.json") == workload["metadata_sha256"], "workload metadata hash mismatch")
        parameters = read_json(directory / "source.manifest")
        parameters.update(commands=spec["commands"], capacities=[spec["capacity"]])
        require(parameters == workload["parameters"], "workload source parameters differ")
        for name, record in workload["files"].items():
            require(Path(record["path"]).name == record["path"], "input path must be local")
            require(file_hashes(directory / record["path"]) == {key: record[key] for key in ("sha256", "fnv1a64")},
                    "shared workload input hash mismatch")
    runs, previous_end = {}, None
    for planned, executed in zip(plan, pair["executed"]):
        require(all(executed[key] == value for key, value in planned.items()), "executed core pair order differs")
        require(executed["status"] == "passed", "failed core run cannot count as passed")
        start, end = (datetime.fromisoformat(executed[key]) for key in ("started_at_utc", "ended_at_utc"))
        require(start <= end and (previous_end is None or start >= previous_end), "core runs overlap or have invalid time order")
        previous_end = end
        directory = root / planned["directory"]
        manifest, raw = read_json(directory / "run_manifest.json"), read_json(directory / "summary.json")
        workload = pair["workloads"][planned["scenario"]]
        require(manifest["inputs"] == workload["files"], "paired input identity differs")
        require(manifest["workload_parameters"] == workload["parameters"] and
                manifest["source_manifest_sha256"] == workload["source_manifest_sha256"], "paired workload parameters differ")
        require(manifest["environment"] == pair["variants"][planned["variant"]]["environment"], "run source/binary identity differs")
        require(sha256(directory / "workload.json") == workload["metadata_sha256"], "run workload metadata differs")
        report = validate_run(directory)
        require(report["commands"] == spec["commands"] and report["capacity"] == spec["capacity"] and
                report["scenario"] == planned["scenario"] and report["repeats"] == 1, "core run dimensions differ")
        # Each invocation has its own Reference pass and separate full-input
        # warmup. A single invocation is not itself a five-round formal result.
        require(manifest["formal_repetition_count"] is False, "single run claimed formal repetition count")
        for item in report["rounds"]:
            if item["mode"] == "throughput":
                item["rejected_per_second"] = item["rejected"] * 1e9 / item["elapsed_ns"]
        runs[(planned["scenario"], planned["pair"], planned["variant"])] = {"report": report, "raw": raw,
                "verification_sha256": sha256(directory / "verification.csv"),
                "snapshot_sha256": sha256(directory / "verified_final.snapshot")}
    scenarios = []
    for scenario in spec["scenarios"]:
        values = []
        reference_identity = None
        for number in range(1, spec["rounds"] + 1):
            variants = {key: runs[(scenario, number, key)] for key in ("A", "B")}
            for run in variants.values():
                identity = (run["verification_sha256"], run["snapshot_sha256"], run["raw"]["verification"]["checksum"])
                if reference_identity is None:
                    reference_identity = identity
                require(identity == reference_identity, "A/B output or Reference work differs")
            metrics = {}
            for key, run in variants.items():
                metrics[key] = {item["mode"]: item for item in run["report"]["rounds"]}
            change = metrics["B"]["throughput"]["completed_per_second"] / metrics["A"]["throughput"]["completed_per_second"] - 1
            values.append({"pair": number, "throughput_relative_change": change, "variants": metrics})
        changes = [item["throughput_relative_change"] for item in values]
        primary = scenario in ("mixed", "cancel_heavy")
        passed = median(changes) >= (0.05 if primary else -0.05) and (not primary or sum(value > 0 for value in changes) >= 4)
        scenarios.append({"scenario": scenario, "pairs": values, "throughput_relative_change": distribution(changes),
                          "improved_pairs": sum(value > 0 for value in changes),
                          "core_adoption_numeric_rule_met": passed if spec["mode"] == "formal" else None,
                          "workload": runs[(scenario, 1, "A")]["report"]})
    a = pair["variants"]["A"]["source"]["build_input_sha256"]
    b = pair["variants"]["B"]["source"]["build_input_sha256"]
    report = {"schema_version": 1, "validation": "passed", "mode": spec["mode"],
              "formal_matrix_complete": spec["mode"] == "formal", "pair_count": len(plan) // 2,
              "timing_intervals": len(plan) * 2, "scenarios": scenarios, "variants": pair["variants"],
              "source_diff_paths": sorted(name for name in a.keys() | b.keys() if a.get(name) != b.get(name)),
              "core_numeric_rules_met": all(row["core_adoption_numeric_rule_met"] for row in scenarios) if spec["mode"] == "formal" else None,
              "decision_scope": "Core numerical rules only. Adoption also requires service delivery/tails, correctness, startup, memory and complexity assessment.",
              "timing_note": "Each pair has independent single-run Reference/warmup and latency/throughput intervals. Short batch durations and 100000 samples do not remove noise or prove tail stability."}
    lines = ["# M4 paired core report", "", f"Mode: {spec['mode']}; validated {report['pair_count']} pairs / {report['timing_intervals']} timing intervals.",
             "", report["decision_scope"], "", report["timing_note"], "",
             "| Scenario | Pair | A completed/s | B completed/s | B/A − 1 | A batch ms | B batch ms | A p99 ns | B p99 ns |",
             "| --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    for row in scenarios:
        for value in row["pairs"]:
            av, bv = value["variants"]["A"], value["variants"]["B"]
            lines.append(f"| {row['scenario']} | {value['pair']} | {av['throughput']['completed_per_second']:.1f} | "
                         f"{bv['throughput']['completed_per_second']:.1f} | {value['throughput_relative_change']:+.2%} | "
                         f"{av['throughput']['elapsed_ns']/1e6:.3f} | {bv['throughput']['elapsed_ns']/1e6:.3f} | "
                         f"{av['latency']['p99_ns']} | {bv['latency']['p99_ns']} |")
    lines += ["", "Full accepted/rejected/trades rates, counts, latency groups, CPU/RSS, clocks, input and source identities are retained in pair-summary.json and each raw run.", ""]
    write_json(root / "pair-summary.json", report)
    (root / "pair-report.md").write_text("\n".join(lines), encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    report = summarize(args.directory)
    print(f"validated {report['pair_count']} core pairs / {report['timing_intervals']} intervals ({report['mode']})")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise SystemExit(f"summarize_core_pair: {error}")
