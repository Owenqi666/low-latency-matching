"""Run real open-loop evidence, then prove missing rounds and corrupt counts fail."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

SERVER, LOADGEN, VERIFIER = [Path(value).resolve() for value in sys.argv[1:4]]
ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = SERVER.parent / "service-benchmark-evidence"
EVIDENCE.mkdir(exist_ok=True)
directory = Path(tempfile.mkdtemp(prefix="round-check-", dir=EVIDENCE))
valid = directory / "valid"
checker = ROOT / "scripts/summarize_service_bench.py"


def execute(command, logfile):
    result = subprocess.run(command, capture_output=True, text=True, timeout=90)
    logfile.write_text(result.stdout + result.stderr)
    return result


def edit_json(path, edit):
    value = json.loads(path.read_text())
    edit(value)
    path.write_text(json.dumps(value) + "\n")


command = [sys.executable, str(ROOT / "scripts/run_service_bench.py"), "--server", str(SERVER),
           "--loadgen", str(LOADGEN), "--verifier", str(VERIFIER), "--manifest", str(ROOT / "data/workloads/service-smoke.json"),
           "--row", "mixed_4", "--commands", "100", "--rounds", "1", "--output-dir", str(valid)]
result = execute(command, directory / "runner.log")
assert result.returncode == 0, (directory, result.stdout, result.stderr)
result = execute([sys.executable, str(checker), str(valid)], directory / "checker.log")
assert result.returncode == 0, (directory, result.stdout, result.stderr)
report = json.loads((valid / "report.json").read_text())
assert report["evidence_valid"] and report["all_runs_succeeded"] and len(report["runs"]) == 2


def remove_round(path):
    shutil.rmtree(path / "runs/mixed_4/round_1")


def remove_declared_round(path):
    remove_round(path)
    edit_json(path / "manifest.json", lambda value: value["expectedRuns"].pop())


def change_count(path):
    edit_json(path / "runs/mixed_4/round_1/client/client.json", lambda value: value.update(completed=value["completed"] - 1))


def truncate_samples(path):
    samples = path / "runs/mixed_4/round_1/client/client_samples.csv"
    samples.write_text("\n".join(samples.read_text().splitlines()[:-1]) + "\n")


def stale_reference(path):
    edit_json(path / "runs/mixed_4/round_1/server/server.json", lambda value: value.update(output_waits=value["output_waits"] + 1))


def wrong_schedule(path):
    schedule = path / "runs/mixed_4/round_1/inputs/schedule.txt"
    schedule.write_text(schedule.read_text() + "0\n")


def shortened_window(path):
    edit_json(path / "runs/mixed_4/round_1/client/client.json", lambda value: value.update(measurement_end_ns=value["measurement_start_ns"] + 1))


def wrong_configuration(path):
    edit_json(path / "runs/mixed_4/round_1/run.json", lambda value: value["config"].update(target_rate_per_sec=123456789, scenario="sweep", capacity=1))


def smoke_as_formal(path):
    edit_json(path / "manifest.json", lambda value: value.update(mode="formal"))


for name, mutation in (("missing-round", remove_round), ("missing-declaration", remove_declared_round),
                       ("wrong-count", change_count), ("truncated-samples", truncate_samples),
                       ("stale-reference", stale_reference), ("wrong-input", wrong_schedule),
                       ("shortened-window", shortened_window), ("wrong-configuration", wrong_configuration),
                       ("smoke-as-formal", smoke_as_formal)):
    changed = directory / name
    shutil.copytree(valid, changed)
    mutation(changed)
    result = execute([sys.executable, str(checker), str(changed)], directory / f"{name}.log")
    assert result.returncode != 0, f"corruption was accepted: {name} ({directory})"
    assert not (changed / "report.json").exists() and not (changed / "report.md").exists(), "stale success report remains"
print(f"Real open-loop run and nine evidence-corruption checks passed: {directory}")
