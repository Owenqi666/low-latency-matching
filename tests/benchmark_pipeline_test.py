"""Exercise public benchmark generation/reporting CLIs with real Release binaries.

Usage: python3 benchmark_pipeline_test.py /path/to/bench_core /path/to/clock_probe
This is a short functional test; its timings are not performance evidence.
"""
import csv
from collections import Counter
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


def invoke(command, *, success=True, diagnostic=None):
    result = subprocess.run([str(part) for part in command], capture_output=True, text=True)
    if success:
        assert result.returncode == 0, (command, result.returncode, result.stdout, result.stderr)
    else:
        assert result.returncode != 0, (command, result.stdout, result.stderr)
        assert diagnostic in result.stderr, (diagnostic, result.stderr)
    return result


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path, value):
    path.write_text(json.dumps(value) + "\n", encoding="utf-8")


def check_workload(directory, scenario):
    metadata = read_json(directory / "workload.json")
    summary = read_json(directory / "summary.json")
    records = [line.split() for line in (directory / "input.trace").read_text().splitlines()
               if line and not line.startswith("#")][1:]
    kinds = Counter(record[0] for record in records)
    assert len(records) == metadata["commands"] == 130
    assert dict(kinds) == metadata["command_counts"]
    assert metadata["capacity"] == 128
    assert metadata["expected_accepted"] + metadata["expected_rejected"] == 130
    assert metadata["expected_accepted"] >= 117, "normal matching workload is dominated by rejections"
    assert {item["mode"] for item in summary["rounds"]} == {"latency", "throughput"}
    for item in summary["rounds"]:
        assert item["completed"] == 130
        assert item["accepted"] == metadata["expected_accepted"]
        assert item["rejected"] == metadata["expected_rejected"]
        assert item["p99_sample_threshold_met"] is False
    with (directory / "verification.csv").open(newline="", encoding="utf-8") as source:
        rows = [{key: int(value) for key, value in row.items()} for row in csv.DictReader(source)]
    rejected = [row for row in rows if row["result"] == 2]
    assert [row["index"] for row in rejected] == metadata["expected_rejection_indices"]
    assert all(row["command_kind"] == 2 and row["reject_reason"] == 8 for row in rejected)
    if scenario == "cancel_heavy":
        assert kinds["C"] >= kinds["L"] > 0 and kinds["M"] == 0
        assert 0 < len(rejected) < 13, "deliberate cancel errors must remain a separate minority"
        assert any(row["command_kind"] == 2 and row["result"] == 1 for row in rows)
    else:
        assert not rejected
        if scenario == "sweep":
            assert kinds["L"] > 0 and kinds["M"] > 0 and kinds["C"] == 0
            assert any(row["trade_count"] > 1 and row["swept_levels"] > 1 for row in rows)
        else:
            assert set(kinds) == {"L", "M", "C"}
    return metadata


def main():
    if len(sys.argv) != 3:
        raise SystemExit(__doc__.splitlines()[2])
    bench, clock = (Path(argument).resolve() for argument in sys.argv[1:])
    repository = Path(__file__).resolve().parents[1]
    scripts = repository / "scripts"
    scenarios = ("mixed", "cancel_heavy", "sweep", "clustered")
    with tempfile.TemporaryDirectory(prefix="llmatch-benchmark-pipeline-") as temporary:
        work = Path(temporary)
        invoke([clock, "--output", work / "clock.json"])
        probe = read_json(work / "clock.json")
        assert probe["is_steady"] is True and probe["samples"] > 0
        assert probe["nominal_period_num"] > 0 and probe["nominal_period_den"] > 0
        assert 0 <= probe["zero_intervals"] <= probe["samples"]
        assert probe["pair_and_duration_record_batch_ns"] > 0
        assert probe["clock_and_timestamp_record_batch_ns"] > 0

        output = work / "valid"
        for scenario in scenarios:
            manifest = repository / "data/workloads" / f"{scenario}.manifest"
            invoke([sys.executable, scripts / "run_bench.py", "--binary", bench,
                    "--manifest", manifest, "--commands", 130, "--capacity", 128,
                    "--repeats", 1, "--output-dir", output])
            directory = output / scenario / "capacity_128"
            check_workload(directory, scenario)
            invoke([sys.executable, scripts / "create_bench_workloads.py", "--manifest", manifest,
                    "--commands", 130, "--capacity", 128, "--output-dir", work / "regenerated"])
            regenerated = work / "regenerated" / scenario / "capacity_128"
            for filename in ("config.txt", "setup.trace", "input.trace", "workload.json"):
                assert (directory / filename).read_bytes() == (regenerated / filename).read_bytes(), (scenario, filename)

        report = read_json(output / "report.json")
        assert report["validation"] == "passed" and len(report["runs"]) == 4
        assert report["quantile_algorithm"] == "nearest-rank"
        for run in report["runs"]:
            assert run["minimum_five_rounds_met"] is False
            latency = next(item for item in run["rounds"] if item["mode"] == "latency")
            assert latency["p99_sample_threshold_met"] is False
            assert sum(group["samples"] for group in latency["groups"]) == 130
            if run["scenario"] == "cancel_heavy":
                accepted = [group for group in latency["groups"]
                            if group["command"] == "cancel" and group["outcome"] == "accepted"]
                rejected = [group for group in latency["groups"]
                            if group["command"] == "cancel" and group["outcome"] == "rejected"]
                assert accepted and rejected
                assert all(group["reason"] == "unknown_order" for group in rejected)
                assert sum(group["samples"] for group in rejected) == latency["rejected"]

        original = output / "mixed" / "capacity_128"
        for corruption in ("truncated_samples", "input_hash", "input_bytes", "missing_round", "snapshot"):
            damaged = work / corruption
            shutil.copytree(original, damaged)
            summary_path = damaged / "summary.json"
            summary = read_json(summary_path)
            if corruption == "truncated_samples":
                samples = damaged / next(item["samples_file"] for item in summary["rounds"] if item["mode"] == "latency")
                lines = samples.read_text().splitlines(keepends=True)
                samples.write_text("".join(lines[:-1]))
                diagnostic = "incomplete samples"
            elif corruption == "input_hash":
                summary["input_hash"] = "fnv1a64:0000000000000000"
                write_json(summary_path, summary)
                diagnostic = "benchmark input hash mismatch"
            elif corruption == "input_bytes":
                with (damaged / "input.trace").open("a", encoding="utf-8") as changed:
                    changed.write("# bytes changed after measurement\n")
                diagnostic = "workload input hash mismatch"
            elif corruption == "missing_round":
                summary["rounds"] = [item for item in summary["rounds"] if item["mode"] != "throughput"]
                write_json(summary_path, summary)
                diagnostic = "missing or duplicate measurement round"
            else:
                (damaged / "latency_1.snapshot").write_text("BOOK 1\n", encoding="utf-8")
                diagnostic = "final snapshot mismatch"
            invoke([sys.executable, scripts / "summarize_bench.py", damaged], success=False, diagnostic=diagnostic)
            assert not (damaged / "report.json").exists(), "invalid evidence produced a success report"

    print("Benchmark pipeline: four deterministic scenarios, real Release smoke, separated outcomes and five corrupted-evidence failures passed")


if __name__ == "__main__":
    main()
