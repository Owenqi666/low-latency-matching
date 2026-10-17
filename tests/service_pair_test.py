"""Exercise real AB/BA runs, loss retention, and corrupted comparison evidence."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

SERVER, LOADGEN, VERIFIER = [Path(value).resolve() for value in sys.argv[1:4]]
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from create_service_workloads import load_manifest
from run_service_pair import execution_plan

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


m4_source = ROOT / "data/workloads/m4-service-formal.json"
m4_spec = load_manifest(m4_source)
m4_plan = execution_plan(m4_spec)
assert len(m4_plan) == 48 and sum(item["kind"] == "measurement" for item in m4_plan) == 40
assert {row["id"] for row in load_manifest(ROOT / "data/workloads/service-formal.json")["rows"]} == {
    "mixed_4", "cancel_heavy_4", "sweep_4", "burst_4", "mixed_1", "mixed_4_near", "mixed_4_overload"}
for name, mutation in (("m4-missing-row", lambda value: value["rows"].pop()),
                       ("m4-wrong-mode", lambda value: value.update(mode="formal")),
                       ("m4-short-rounds", lambda value: value.update(rounds=1)),
                       ("m4-changed-rate", lambda value: value["rows"][0].update(target_rate_per_sec=9999))):
    changed = directory / f"{name}.json"
    shutil.copyfile(m4_source, changed)
    edit(changed, mutation)
    try:
        load_manifest(changed)
    except ValueError as error:
        (directory / f"{name}.log").write_text(str(error) + "\n")
    else:
        raise AssertionError(("invalid formal contract accepted", name, directory))

result = execute(command(valid), directory / "runner.log")
assert result.returncode == 0, (directory, result.stdout, result.stderr)
report = json.loads((valid / "pair-report.json").read_text())
manifest = json.loads((valid / "pair-manifest.json").read_text())
assert report["evidence_valid"] and report["all_runs_succeeded"] and report["measured_attempts"] == 4
assert [item["variant"] for item in manifest["executed"]] == ["A", "B", "A", "B", "B", "A"]
assert [item["round"] for item in report["pairs"]] == [1, 2]
assert all(item["both_succeeded"] for item in report["pairs"])
assert all(item["resources"][key]["loadgen_peak_rss_bytes"] > 0 for item in report["pairs"] for key in ("A", "B"))
assert not report["m4_formal_contract_met"] and not report["all_measured_sample_targets_met"]
assert len(report["measurement_tools"]["sha256"]) == 7


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


def wrong_mode(path):
    edit(path / "pair-manifest.json", lambda value: value.update(mode="m4-formal"))


def wrong_tool_source(path):
    target = path / "measurement-tools/create_service_workloads.py"
    target.write_text(target.read_text() + "\n# changed after measurement\n")


for name, mutation in (("missing-side", missing_side), ("missing-round", missing_round), ("wrong-inputs", wrong_inputs),
                       ("wrong-source", wrong_source), ("wrong-counts", wrong_counts), ("different-tool", different_tool),
                       ("different-compile-flags", different_compile_flags), ("missing-client-resources", missing_client_resources), ("wrong-order", wrong_order),
                       ("shortened-plan", shortened_plan), ("wrong-build-source", wrong_build_source),
                       ("wrong-mode", wrong_mode), ("wrong-tool-source", wrong_tool_source)):
    changed = directory / name
    shutil.copytree(valid, changed)
    mutation(changed)
    result = execute([sys.executable, str(checker), str(changed)], directory / f"{name}.log")
    assert result.returncode != 0, ("corruption accepted", name, directory)
    assert not (changed / "pair-report.json").exists() and not (changed / "pair-report.md").exists(), "stale pair success remains"

# Retain a restored copy as well as the original, changed inputs and failure logs.
restored = directory / "restored"
shutil.copytree(valid, restored)
result = execute([sys.executable, str(restored / "measurement-tools/summarize_service_pair.py"), str(restored)],
                 directory / "restored.log")
assert result.returncode == 0, (directory, result.stdout, result.stderr)

# The new four-row route runs real services but remains explicitly a short smoke.
m4_smoke = directory / "m4-smoke-manifest.json"
shutil.copyfile(m4_source, m4_smoke)
edit(m4_smoke, lambda value: value.update(mode="smoke", minimum_plan_seconds=0, warmup_commands=130))
m4_short = directory / "m4-short"
short_command = command(m4_short, m4_smoke)
selection = short_command.index("--row")
del short_command[selection:selection + 2]
short_command[short_command.index("--commands") + 1] = "260"
result = execute(short_command, directory / "m4-short-runner.log")
assert result.returncode == 0, (directory, result.stdout, result.stderr)
short_report = json.loads((m4_short / "pair-report.json").read_text())
assert short_report["mode"] == "smoke" and not short_report["m4_formal_contract_met"]
assert short_report["measured_attempts"] == 16 and short_report["warmup_attempts"] == 8
assert short_report["all_runs_succeeded"] and len(short_report["per_row"]) == 4

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
print(f"Real paired runs, thirteen corruption failures, M4 contract checks and four-row smoke, restored check and lossy evidence passed; evidence: {directory}")
