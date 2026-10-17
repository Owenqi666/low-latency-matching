"""Exercise real AB/BA runs, loss retention, and corrupted comparison evidence."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

SERVER, LOADGEN, VERIFIER = [Path(value).resolve() for value in sys.argv[1:4]]
ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = SERVER.parent / "service-pair-evidence"
EVIDENCE.mkdir(exist_ok=True)
directory = Path(tempfile.mkdtemp(prefix="pair-check-", dir=EVIDENCE))
runner = ROOT / "scripts/run_service_pair.py"
checker = ROOT / "scripts/summarize_service_pair.py"
valid = directory / "valid"


def execute(command, log):
    result = subprocess.run(command, capture_output=True, text=True, timeout=120)
    log.write_text(result.stdout + result.stderr)
    return result


def command(output, manifest=ROOT / "data/workloads/service-smoke.json", rounds="2", rate="1000"):
    return [sys.executable, str(runner), "--baseline-server", str(SERVER), "--baseline-source", str(ROOT),
            "--candidate-server", str(SERVER), "--candidate-source", str(ROOT),
            "--loadgen", str(LOADGEN), "--verifier", str(VERIFIER), "--manifest", str(manifest),
            "--row", "mixed_4", "--commands", "40", "--rounds", rounds, "--rate", rate,
            "--output-dir", str(output)]


def edit(path, mutation):
    value = json.loads(path.read_text())
    mutation(value)
    path.write_text(json.dumps(value) + "\n")


result = execute(command(valid), directory / "runner.log")
assert result.returncode == 0, (directory, result.stdout, result.stderr)
report = json.loads((valid / "pair-report.json").read_text())
manifest = json.loads((valid / "pair-manifest.json").read_text())
assert report["evidence_valid"] and report["all_runs_succeeded"] and report["measured_attempts"] == 4
assert [item["variant"] for item in manifest["executed"]] == ["A", "B", "A", "B", "B", "A"]
assert [item["round"] for item in report["pairs"]] == [1, 2]
assert all(item["both_succeeded"] for item in report["pairs"])
assert all(item["resources"][key]["loadgen_peak_rss_bytes"] > 0 for item in report["pairs"] for key in ("A", "B"))


def missing_side(path):
    shutil.rmtree(path / "candidate")


def missing_round(path):
    shutil.rmtree(path / "candidate/runs/mixed_4/round_2")


def wrong_inputs(path):
    target = path / "candidate/runs/mixed_4/round_1/inputs/schedule.txt"
    target.write_text(target.read_text() + "0\n")


def wrong_source(path):
    edit(path / "candidate/manifest.json", lambda value: value["environment"].update(code_commit="0" * 40))


def wrong_counts(path):
    edit(path / "candidate/runs/mixed_4/round_1/client/client.json",
         lambda value: value.update(completed=value["completed"] - 1))


def different_tool(path):
    edit(path / "candidate/manifest.json", lambda value: value["binaries"]["loadgen"].update(sha256="0" * 64))


def different_compile_flags(path):
    edit(path / "candidate/manifest.json", lambda value: value["binaries"]["server"]["target_compile_flags"]["server.cpp"].append("-O0"))


def missing_client_resources(path):
    edit(path / "candidate/runs/mixed_4/round_1/client/client.json", lambda value: value.pop("resource_usage"))


def wrong_order(path):
    edit(path / "pair-manifest.json", lambda value: value["executed"].reverse())


def shortened_plan(path):
    edit(path / "pair-manifest.json", lambda value: (value["execution_plan"].pop(), value["executed"].pop()))


def wrong_build_source(path):
    target = path / "candidate/build-evidence/CMakeCache.txt"
    target.write_text(target.read_text().replace("CMAKE_HOME_DIRECTORY:INTERNAL=", "CMAKE_HOME_DIRECTORY:INTERNAL=/wrong/"))


for name, mutation in (("missing-side", missing_side), ("missing-round", missing_round), ("wrong-inputs", wrong_inputs),
                       ("wrong-source", wrong_source), ("wrong-counts", wrong_counts), ("different-tool", different_tool),
                       ("different-compile-flags", different_compile_flags), ("missing-client-resources", missing_client_resources), ("wrong-order", wrong_order),
                       ("shortened-plan", shortened_plan), ("wrong-build-source", wrong_build_source)):
    changed = directory / name
    shutil.copytree(valid, changed)
    mutation(changed)
    result = execute([sys.executable, str(checker), str(changed)], directory / f"{name}.log")
    assert result.returncode != 0, ("corruption accepted", name, directory)
    assert not (changed / "pair-report.json").exists() and not (changed / "pair-report.md").exists(), "stale pair success remains"

# Retain a restored copy as well as the original, changed inputs and failure logs.
restored = directory / "restored"
shutil.copytree(valid, restored)
result = execute([sys.executable, str(checker), str(restored)], directory / "restored.log")
assert result.returncode == 0, (directory, result.stdout, result.stderr)

# A bounded overload has valid evidence even when its client cannot start every request.
loss_manifest = directory / "loss-manifest.json"
shutil.copyfile(ROOT / "data/workloads/service-smoke.json", loss_manifest)
edit(loss_manifest, lambda value: value["limits"].update(max_inflight=1))
lossy = directory / "lossy"
result = execute(command(lossy, loss_manifest, rounds="1", rate="1000000000"), directory / "lossy-runner.log")
assert result.returncode == 1, (directory, result.stdout, result.stderr)
report = json.loads((lossy / "pair-report.json").read_text())
assert report["evidence_valid"] and not report["all_runs_succeeded"] and report["measured_attempts"] == 2
assert all(not item["both_succeeded"] and all(value is None for value in item["B_minus_A"].values()) for item in report["pairs"])
assert all(item[key]["counts"]["not_started"] > 0 for item in report["pairs"] for key in ("A", "B"))

wrong = command(directory / "wrong-declared-source")
wrong[wrong.index("--candidate-source") + 1] = str(ROOT.parent)
result = execute(wrong, directory / "wrong-declared-source.log")
assert result.returncode != 0 and "differs from declared source" in result.stderr
print(f"Real paired runs, eleven corruption failures, restored check and lossy evidence passed; evidence: {directory}")
