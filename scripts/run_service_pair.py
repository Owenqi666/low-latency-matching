#!/usr/bin/env python3
"""Run two complete service experiments in a fixed, alternating A/B order."""
import argparse
from pathlib import Path
import shutil
import subprocess
import sys

from create_service_workloads import load_manifest, sha256, write_json
from run_bench import capture
from run_service_bench import binary_record, finish_experiment, now, prepare_experiment, run_one

VARIANTS = {"A": "baseline", "B": "candidate"}


def source_record(server, source):
    """Bind the declared checkout to the binary's actual CMake build directory."""
    source = source.resolve()
    cache_path = server.resolve().parent / "CMakeCache.txt"
    cache = dict(line.split("=", 1) for line in cache_path.read_text().splitlines()
                 if line.startswith("CMAKE_HOME_DIRECTORY:INTERNAL="))
    home = Path(cache["CMAKE_HOME_DIRECTORY:INTERNAL"]).resolve()
    if home != source:
        raise ValueError(f"server build source {home} differs from declared source {source}")
    commit = capture(["git", "rev-parse", "HEAD"], source)
    status = capture(["git", "status", "--porcelain"], source)
    if not commit["available"] or not status["available"]:
        raise ValueError(f"cannot identify source checkout: {source}")
    files = [source / name for name in ("CMakeLists.txt", "CMakePresets.json")]
    for directory in ("src", "include", "apps", "cmake"):
        files.extend(path for path in (source / directory).rglob("*") if path.is_file())
    hashes = {str(path.relative_to(source)): sha256(path) for path in sorted(files) if path.is_file()}
    return {"directory": str(source), "cmake_home_directory": str(home), "commit": commit["output"],
            "dirty": bool(status["output"]), "git_status": status["output"], "build_input_sha256": hashes,
            "server_sha256": sha256(server), "cmake_cache_sha256": sha256(cache_path),
            "compile_commands_sha256": sha256(server.parent / "compile_commands.json")}


def execution_plan(spec):
    plan = []
    for row in spec["rows"]:
        for repeat in range(spec["rounds"] + 1):
            suffix = "warmup" if repeat == 0 else f"round_{repeat}"
            order = "AB" if repeat == 0 or repeat % 2 else "BA"
            for variant in order:
                plan.append({"variant": variant, "id": f"{row['id']}-{suffix}",
                             "row": row["id"], "round": repeat,
                             "kind": "warmup" if repeat == 0 else "measurement"})
    return plan


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for variant in VARIANTS.values():
        parser.add_argument(f"--{variant}-server", required=True, type=Path)
        parser.add_argument(f"--{variant}-source", required=True, type=Path)
    for name in ("loadgen", "verifier", "manifest", "output-dir"):
        parser.add_argument(f"--{name}", required=True, type=Path)
    parser.add_argument("--host-environment", type=Path)
    parser.add_argument("--row", action="append")
    parser.add_argument("--commands", type=int)
    parser.add_argument("--rounds", type=int)
    parser.add_argument("--rate", type=int)
    args = parser.parse_args()
    spec = load_manifest(args.manifest, args.row, args.commands, args.rounds, args.rate)
    shared = {name: binary_record(getattr(args, name)) for name in ("loadgen", "verifier")}
    servers = {key: getattr(args, f"{name}_server").resolve() for key, name in VARIANTS.items()}
    sources = {key: source_record(servers[key], getattr(args, f"{name}_source")) for key, name in VARIANTS.items()}
    binaries = {key: {"server": binary_record(server), **shared} for key, server in servers.items()}
    if spec["mode"] == "formal" and (not sys.platform.startswith("linux") or any(
            record[name]["build_type"] != "Release" or record[name]["sanitized"]
            for record in binaries.values() for name in ("server", "loadgen"))):
        raise ValueError("formal measurements require Linux and unsanitized Release server/loadgen builds")
    for field in ("build_type", "compiler", "build_flags", "target_compile_flags", "sanitized"):
        if binaries["A"]["server"][field] != binaries["B"]["server"][field]:
            raise ValueError(f"server {field} differs between variants")
    root = args.output_dir.resolve()
    root.mkdir(parents=True, exist_ok=False)
    manifests = {}
    pair = {"schema_version": 1, "status": "running", "mode": spec["mode"], "started_at_utc": now(),
            "order": "warmup AB; odd measurement rounds AB; even measurement rounds BA",
            "variants": {}, "execution_plan": execution_plan(spec), "executed": []}
    for key, directory in VARIANTS.items():
        variant_root = root / directory
        manifest = prepare_experiment(variant_root, args.manifest, spec, binaries[key],
                                      Path(sources[key]["directory"]), args.host_environment)
        evidence = variant_root / "build-evidence"
        evidence.mkdir()
        for name in ("CMakeCache.txt", "compile_commands.json"):
            shutil.copyfile(servers[key].parent / name, evidence / name)
        write_json(evidence / "source.json", sources[key])
        binding = {"directory": directory, "source": sources[key],
                   "source_record_sha256": sha256(evidence / "source.json")}
        pair["variants"][key] = binding
        manifest["server_source"] = binding
        write_json(variant_root / "manifest.json", manifest)
        manifests[key] = manifest
    write_json(root / "pair-manifest.json", pair)
    rows = {row["id"]: row for row in spec["rows"]}
    entries = {key: {entry["id"]: entry for entry in manifest["expectedRuns"]} for key, manifest in manifests.items()}
    try:
        for planned in pair["execution_plan"]:
            key = planned["variant"]
            manifest, variant_root = manifests[key], root / VARIANTS[key]
            entry = entries[key][planned["id"]]
            entry["status"] = "running"
            write_json(variant_root / "manifest.json", manifest)
            print(f"{key} {entry['id']}: starting", flush=True)
            state = run_one(variant_root, entry, rows[entry["row"]], spec, binaries[key])
            entry["status"] = state["status"]
            pair["executed"].append({**planned, "status": state["status"],
                                     "started_at_utc": state["started_at_utc"], "ended_at_utc": state["ended_at_utc"]})
            write_json(variant_root / "manifest.json", manifest)
            write_json(root / "pair-manifest.json", pair)
            print(f"{key} {entry['id']}: {state['status']}", flush=True)
    except KeyboardInterrupt:
        entry["status"] = manifest["status"] = pair["status"] = "interrupted"
        write_json(variant_root / "manifest.json", manifest)
        write_json(root / "pair-manifest.json", pair)
        raise
    for key, name in VARIANTS.items():
        after = source_record(servers[key], Path(sources[key]["directory"]))
        if any(after[field] != sources[key][field] for field in (
                "commit", "build_input_sha256", "server_sha256", "cmake_cache_sha256", "compile_commands_sha256")):
            raise ValueError(f"{key} source/build identity changed during the experiment")
        finish_experiment(root / name, manifests[key])
    for name, record in shared.items():
        if sha256(Path(record["path"])) != record["sha256"]:
            raise ValueError(f"shared {name} binary changed during the experiment")
    pair["status"] = "completed" if all(manifest["status"] == "completed" for manifest in manifests.values()) else "failed"
    pair["ended_at_utc"] = now()
    write_json(root / "pair-manifest.json", pair)
    with (root / "pair-summary-check.log").open("wb") as log:
        result = subprocess.run([sys.executable, str(Path(__file__).with_name("summarize_service_pair.py")), str(root)],
                                stdout=log, stderr=subprocess.STDOUT)
    pair["summarizer_exit"] = result.returncode
    write_json(root / "pair-manifest.json", pair)
    if result.returncode:
        return result.returncode
    return 0 if pair["status"] == "completed" else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise SystemExit(f"run_service_pair: {error}")
