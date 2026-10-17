"""Real short core A/A pairs, retained failure evidence, and comparison corruption checks."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

BINARY = Path(sys.argv[1]).resolve()
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from summarize_core_pair import execution_plan

EVIDENCE = BINARY.parent / "core-pair-evidence"
EVIDENCE.mkdir(exist_ok=True)
directory = Path(tempfile.mkdtemp(prefix="pair-check-", dir=EVIDENCE))
runner = ROOT / "scripts/run_core_pair.py"
checker = ROOT / "scripts/summarize_core_pair.py"
valid = directory / "valid"


def execute(command, name):
    result = subprocess.run([str(value) for value in command], capture_output=True, text=True, timeout=120)
    (directory / f"{name}.log").write_text(result.stdout + result.stderr)
    return result


def edit(path, mutation):
    value = json.loads(path.read_text())
    mutation(value)
    path.write_text(json.dumps(value) + "\n")


def command(output):
    return [sys.executable, runner, "--baseline-binary", BINARY, "--baseline-source", ROOT,
            "--candidate-binary", BINARY, "--candidate-source", ROOT,
            "--manifest", ROOT / "data/workloads/m4-core-formal.json", "--commands", "130", "--rounds", "2",
            "--scenario", "mixed", "--scenario", "near_full_reuse", "--output-dir", output]


formal = json.loads((ROOT / "data/workloads/m4-core-formal.json").read_text())
formal["scenarios"] = ["mixed", "cancel_heavy", "sweep", "clustered", "near_full_reuse"]
assert len(execution_plan(formal)) == 50  # two timing intervals for each invocation
result = execute(command(valid), "runner")
assert result.returncode == 0, (directory, result.stdout, result.stderr)
report = json.loads((valid / "pair-summary.json").read_text())
manifest = json.loads((valid / "pair-manifest.json").read_text())
assert report["validation"] == "passed" and report["mode"] == "smoke"
assert report["pair_count"] == 4 and report["timing_intervals"] == 16
assert not report["formal_matrix_complete"] and report["core_numeric_rules_met"] is None
assert [entry["variant"] for entry in manifest["executed"]] == list("ABBAABBA")
assert all(row["core_adoption_numeric_rule_met"] is None for row in report["scenarios"])
assert report["source_diff_paths"] == []
for scenario in report["scenarios"]:
    for pair in scenario["pairs"]:
        for variant in pair["variants"].values():
            assert variant["throughput"]["completed"] == 130
            assert variant["throughput"]["rejected_per_second"] >= 0
            assert not variant["latency"]["p99_sample_threshold_met"]


def remove_run(path):
    shutil.rmtree(path / "candidate/mixed/pair_2")


def wrong_inputs(path):
    file = path / "candidate/mixed/pair_1/input.trace"
    file.write_text(file.read_text() + "# changed input bytes\n")


def wrong_identity(path):
    edit(path / "candidate/mixed/pair_1/run_manifest.json", lambda value: value["environment"].update(binary_sha256="0" * 64))


def failed_summary(path):
    edit(path / "candidate/mixed/pair_1/summary.json", lambda value: value["verification"].update(passed=False))


def failed_run(path):
    edit(path / "pair-manifest.json", lambda value: value["executed"][0].update(status="failed"))


def shortened_plan(path):
    edit(path / "pair-manifest.json", lambda value: (value["execution_plan"].pop(), value["executed"].pop()))


def wrong_order(path):
    edit(path / "pair-manifest.json", lambda value: value["executed"].reverse())


def wrong_build_source(path):
    file = path / "candidate/build-evidence/CMakeCache.txt"
    file.write_text(file.read_text().replace("CMAKE_HOME_DIRECTORY:INTERNAL=", "CMAKE_HOME_DIRECTORY:INTERNAL=/wrong/"))


def wrong_tool(path):
    file = path / "tool-evidence/create_bench_workloads.py"
    file.write_text(file.read_text() + "\n# modified\n")


def wrong_formal_label(path):
    edit(path / "pair-manifest.json", lambda value: value["specification"].update(mode="formal"))


def wrong_source_contract(path):
    file = path / "source-manifest.json"
    edit(file, lambda value: value.update(commands=99999))
    digest = hashlib.sha256(file.read_bytes()).hexdigest()
    edit(path / "pair-manifest.json", lambda value: value.update(source_manifest_sha256=digest))


for name, mutation in (("missing-run", remove_run), ("input-bytes", wrong_inputs), ("binary-identity", wrong_identity),
                       ("failed-verification", failed_summary), ("failed-run", failed_run), ("shortened-plan", shortened_plan),
                       ("wrong-order", wrong_order), ("wrong-build-source", wrong_build_source),
                       ("wrong-tool", wrong_tool), ("fake-formal", wrong_formal_label), ("source-contract", wrong_source_contract)):
    changed = directory / name
    shutil.copytree(valid, changed)
    mutation(changed)
    result = execute([sys.executable, checker, changed], name)
    assert result.returncode != 0, ("corruption accepted", name, directory)
    assert not (changed / "pair-summary.json").exists() and not (changed / "pair-report.md").exists(), "stale success remains"

restored = directory / "restored"
shutil.copytree(valid, restored)
result = execute([sys.executable, restored / "tool-evidence/summarize_core_pair.py", restored], "restored")
assert result.returncode == 0, (directory, result.stdout, result.stderr)
wrong = command(directory / "wrong-declared-source")
wrong[wrong.index("--candidate-source") + 1] = ROOT.parent
result = execute(wrong, "wrong-declared-source")
assert result.returncode != 0 and "differs from declared source" in result.stderr
# An actual failed process must leave its declared attempt and log intact. This
# fixture is an explicit failure stub, never a timing/performance result.
failing = directory / "failing-build"
failing.mkdir()
for name in ("CMakeCache.txt", "compile_commands.json", "clock_probe"):
    shutil.copy2(BINARY.parent / name, failing / name)
stub = failing / "bench_core"
stub.write_text("#!/bin/sh\nprintf 'intentional core pair failure fixture\\n'\nexit 23\n")
stub.chmod(0o755)
failed_output = directory / "failed-invocation"
failed_command = command(failed_output)
for flag in ("--baseline-binary", "--candidate-binary"):
    failed_command[failed_command.index(flag) + 1] = stub
result = execute(failed_command, "failed-invocation")
assert result.returncode != 0 and "exited 23" in result.stderr
failed_manifest = json.loads((failed_output / "pair-manifest.json").read_text())
assert failed_manifest["status"] == "failed" and failed_manifest["executed"][0]["status"] == "failed"
assert len(failed_manifest["executed"]) == 1 and len(failed_manifest["execution_plan"]) == 8
assert "intentional core pair failure fixture" in (failed_output / "baseline/mixed/pair_1/benchmark.log").read_text()
assert not (failed_output / "pair-summary.json").exists()
result = execute([sys.executable, checker, failed_output], "failed-invocation-check")
assert result.returncode != 0 and "did not complete" in result.stderr
print(f"Real core AB/BA smoke, eleven corruption failures, archived checker replay and actual failed invocation retention passed; evidence: {directory}")
