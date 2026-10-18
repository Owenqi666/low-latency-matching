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
assert all(run["client_resources"]["scope"] == "process_lifetime_before_evidence" for run in report["runs"])


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


def negative_client_cpu(path):
    edit_json(path / "runs/mixed_4/round_1/client/client.json",
              lambda value: value["resource_usage"].update(user_cpu_us=-1))


def client_resource_before_completion(path):
    edit_json(path / "runs/mixed_4/round_1/client/client.json",
              lambda value: value["resource_usage"].update(captured_ns=value["measurement_end_ns"] - 1))


for name, mutation in (("missing-round", remove_round), ("missing-declaration", remove_declared_round),
                       ("wrong-count", change_count), ("truncated-samples", truncate_samples),
                       ("stale-reference", stale_reference), ("wrong-input", wrong_schedule),
                       ("shortened-window", shortened_window), ("wrong-configuration", wrong_configuration),
                       ("smoke-as-formal", smoke_as_formal), ("negative-client-cpu", negative_client_cpu),
                       ("client-resource-before-completion", client_resource_before_completion)):
    changed = directory / name
    shutil.copytree(valid, changed)
    mutation(changed)
    result = execute([sys.executable, str(checker), str(changed)], directory / f"{name}.log")
    assert result.returncode != 0, f"corruption was accepted: {name} ({directory})"
    assert not (changed / "report.json").exists() and not (changed / "report.md").exists(), "stale success report remains"
# Historical M2 evidence had no client resource snapshot; do not invent one.
legacy = directory / "legacy-client-resources"
shutil.copytree(valid, legacy)
for path in legacy.glob("runs/*/*/client/client.json"):
    edit_json(path, lambda value: value.pop("resource_usage"))
result = execute([sys.executable, str(checker), str(legacy)], directory / "legacy-client-resources.log")
assert result.returncode == 0, (directory, result.stdout, result.stderr)
legacy_report = json.loads((legacy / "report.json").read_text())
assert all(run["client_resources"] is None for run in legacy_report["runs"])
print(f"Real open-loop run, eleven corruption checks and explicit legacy resource absence passed: {directory}")

# Detailed diagnostics use the same runner on a separately identified manifest.
# They cannot be silently introduced into formal performance measurements.
diagnostic_spec = json.loads((ROOT / "data/workloads/service-smoke.json").read_text())
diagnostic_spec["gateway_diagnostics"] = True
diagnostic_manifest = directory / "diagnostic-manifest.json"
diagnostic_manifest.write_text(json.dumps(diagnostic_spec) + "\n")
diagnostic_command = command.copy()
diagnostic_command[diagnostic_command.index("--manifest") + 1] = str(diagnostic_manifest)
diagnostic_output = directory / "diagnostic-run"
diagnostic_command[diagnostic_command.index("--output-dir") + 1] = str(diagnostic_output)
result = execute(diagnostic_command, directory / "diagnostic-run.log")
assert result.returncode == 0, (directory, result.stdout, result.stderr)
assert all(json.loads(path.read_text())["gateway_diagnostics_enabled"] for path in
           diagnostic_output.glob("runs/*/*/server/server.json"))
edit_json(diagnostic_output / "manifest.json", lambda value:
          value["workload_parameters"].update(gateway_diagnostics=False))
result = execute([sys.executable, str(checker), str(diagnostic_output)], directory / "diagnostic-setting-mismatch.log")
assert result.returncode != 0, "diagnostic setting mismatch was accepted"
sys.path.insert(0, str(ROOT / "scripts"))
from create_service_workloads import load_manifest
for mutation in ({"gateway_diagnostics": 1}, {"mode": "formal", "gateway_diagnostics": True}):
    diagnostic_manifest.write_text(json.dumps({**diagnostic_spec, **mutation}) + "\n")
    try:
        load_manifest(diagnostic_manifest)
    except ValueError:
        pass
    else:
        raise AssertionError(f"invalid diagnostic manifest accepted: {mutation}")
print("Optional Gateway diagnostics and formal exclusion passed")
