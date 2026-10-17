#!/usr/bin/env python3
"""Run the fixed M4 core matrix sequentially, alternating adjacent A/B pairs."""
import argparse
from datetime import datetime, timezone
from pathlib import Path
import shutil
import sys

from create_bench_workloads import file_hashes, generate, load_manifest, write_json
from run_bench import capture, environment, execute
from summarize_bench import read_json, require, validate_run
from summarize_core_pair import SCENARIOS, WORKLOAD_FILES, execution_plan, summarize

VARIANTS = {"A": "baseline", "B": "candidate"}
TOOLS = ("create_bench_workloads.py", "run_bench.py", "summarize_bench.py",
         "run_core_pair.py", "summarize_core_pair.py")


def now():
    return datetime.now(timezone.utc).isoformat()


def sha256(path):
    return file_hashes(path)["sha256"]


def source_record(binary, source):
    cache = binary.parent / "CMakeCache.txt"
    home = next(line.split("=", 1)[1] for line in cache.read_text().splitlines()
                if line.startswith("CMAKE_HOME_DIRECTORY:INTERNAL="))
    require(Path(home).resolve() == source, "benchmark build source differs from declared source")
    commit, status = capture(["git", "rev-parse", "HEAD"], source), capture(["git", "status", "--porcelain"], source)
    require(commit["available"] and status["available"], "cannot identify source checkout")
    files = [source / name for name in ("CMakeLists.txt", "CMakePresets.json")]
    for directory in ("src", "include", "apps", "bench", "reference", "tools", "cmake"):
        files.extend(path for path in (source / directory).rglob("*") if path.is_file())
    return {"directory": str(source), "cmake_home_directory": home,
            "commit": commit["output"], "dirty": bool(status["output"]), "git_status": status["output"],
            "build_input_sha256": {str(path.relative_to(source)): sha256(path) for path in sorted(files)},
            "binary_sha256": sha256(binary), "clock_sha256": sha256(binary.with_name("clock_probe")),
            "cmake_cache_sha256": sha256(cache),
            "compile_commands_sha256": sha256(binary.parent / "compile_commands.json")}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for variant in VARIANTS.values():
        parser.add_argument(f"--{variant}-binary", required=True, type=Path)
        parser.add_argument(f"--{variant}-source", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--host-environment", type=Path)
    parser.add_argument("--commands", type=int, help="override for a functional smoke only")
    parser.add_argument("--rounds", type=int, help="override for a functional smoke only")
    parser.add_argument("--scenario", action="append", help="subset for a functional smoke only")
    args = parser.parse_args()
    spec = read_json(args.manifest)
    require(spec["schema_version"] == 1 and spec["mode"] == "formal", "unsupported M4 core manifest")
    require(spec["capacity"] == 1000 and spec["commands"] == 100000 and spec["rounds"] == 5,
            "M4 core formal dimensions must remain fixed")
    require(spec["workloads"] == WORKLOAD_FILES, "M4 core workload list must remain fixed")
    if args.commands is not None or args.rounds is not None or args.scenario:
        spec["mode"] = "smoke"
        spec["commands"] = args.commands if args.commands is not None else spec["commands"]
        spec["rounds"] = args.rounds if args.rounds is not None else spec["rounds"]
    require(spec["commands"] > 0 and spec["rounds"] > 0, "commands and rounds must be positive")
    workloads = {}
    for name in spec["workloads"]:
        path = args.manifest.parent / name
        workload = load_manifest(path, spec["commands"], [spec["capacity"]])
        if not args.scenario or workload["scenario"] in args.scenario:
            workloads[workload["scenario"]] = (path, workload)
    require(workloads and (not args.scenario or set(args.scenario) == set(workloads)), "unknown/empty scenario subset")
    spec["scenarios"] = list(workloads)
    if spec["mode"] == "formal":
        require(tuple(spec["scenarios"]) == SCENARIOS, "incomplete formal core matrix")
    binaries = {key: getattr(args, f"{name}_binary").resolve() for key, name in VARIANTS.items()}
    sources = {key: source_record(binaries[key], getattr(args, f"{name}_source").resolve())
               for key, name in VARIANTS.items()}
    environments = {key: environment(binary, Path(sources[key]["directory"])) for key, binary in binaries.items()}
    for field in ("compiler", "build_type", "sanitizers", "build_flags", "target_compile_flags"):
        require(environments["A"][field] == environments["B"][field], f"A/B {field} differs")
    if spec["mode"] == "formal":
        require(sys.platform.startswith("linux"), "formal core pairs require Linux")
        require(not any(source["dirty"] for source in sources.values()), "formal source checkouts must be clean")
    root = args.output_dir.resolve()
    root.mkdir(parents=True, exist_ok=False)
    pair = {"schema_version": 1, "status": "running", "started_at_utc": now(), "specification": spec,
            "execution_plan": execution_plan(spec), "executed": [], "variants": {}, "workloads": {}, "shared_tools": {}}
    evidence = root / "tool-evidence"
    evidence.mkdir()
    for name in TOOLS:
        shutil.copyfile(Path(__file__).with_name(name), evidence / name)
        pair["shared_tools"][name] = sha256(evidence / name)
    shutil.copyfile(args.manifest, root / "source-manifest.json")
    pair["source_manifest_sha256"] = sha256(root / "source-manifest.json")
    if args.host_environment:
        shutil.copyfile(args.host_environment, root / "host-environment.json")
        pair["host_environment_sha256"] = sha256(root / "host-environment.json")
    for key, source in sources.items():
        destination = root / VARIANTS[key] / "build-evidence"
        destination.mkdir(parents=True)
        for name in ("CMakeCache.txt", "compile_commands.json"):
            shutil.copyfile(binaries[key].parent / name, destination / name)
        write_json(destination / "source.json", source)
        pair["variants"][key] = {"directory": VARIANTS[key], "source": source,
                                  "source_record_sha256": sha256(destination / "source.json"),
                                  "environment": environments[key]}
    for scenario, (path, workload) in workloads.items():
        directory = root / "inputs" / scenario
        metadata = generate(workload, spec["capacity"], directory)
        shutil.copyfile(path, directory / "source.manifest")
        pair["workloads"][scenario] = {"parameters": workload, "files": metadata["files"],
                                       "source_manifest_sha256": sha256(path),
                                       "metadata_sha256": sha256(directory / "workload.json")}
    write_json(root / "pair-manifest.json", pair)
    try:
        for planned in pair["execution_plan"]:
            key, scenario = planned["variant"], planned["scenario"]
            directory = root / planned["directory"]
            shutil.copytree(root / "inputs" / scenario, directory)
            entry = {**planned, "status": "running", "started_at_utc": now()}
            pair["executed"].append(entry)
            write_json(root / "pair-manifest.json", pair)
            binary = binaries[key]
            command = [str(binary), "--config", str(directory / "config.txt"), "--setup", str(directory / "setup.trace"),
                       "--input", str(directory / "input.trace"), "--repeats", "1", "--output-dir", str(directory)]
            manifest = {"schema_version": 1, "repeats": 1, "formal_repetition_count": False,
                        "workload_parameters": workloads[scenario][1], "environment": environments[key],
                        "source_manifest_sha256": pair["workloads"][scenario]["source_manifest_sha256"],
                        "inputs": pair["workloads"][scenario]["files"], "invocation": command,
                        "warmup_policy": "bench_core performs full-event Reference verification and one separate verified warmup before its latency and throughput intervals"}
            write_json(directory / "run_manifest.json", manifest)
            print(f"{key} {scenario} pair {planned['pair']}: starting", flush=True)
            execute([str(binary.with_name("clock_probe")), "--output", str(directory / "clock_probe.json")], directory / "clock_probe.log")
            manifest["clock_probe"] = {"path": "clock_probe.json", **file_hashes(directory / "clock_probe.json")}
            write_json(directory / "run_manifest.json", manifest)
            execute(command, directory / "benchmark.log")
            validate_run(directory)
            entry.update(status="passed", ended_at_utc=now())
            write_json(root / "pair-manifest.json", pair)
        for key, before in sources.items():
            after = source_record(binaries[key], Path(before["directory"]))
            require(all(after[field] == before[field] for field in ("commit", "build_input_sha256", "binary_sha256",
                    "clock_sha256", "cmake_cache_sha256", "compile_commands_sha256")),
                    f"{key}: source/build identity changed during measurement")
        require(all(sha256(Path(__file__).with_name(name)) == value for name, value in pair["shared_tools"].items()),
                "shared tools changed during measurement")
        pair.update(status="completed", ended_at_utc=now())
        write_json(root / "pair-manifest.json", pair)
        report = summarize(root)
        print(f"Validated {report['pair_count']} pairs / {report['timing_intervals']} timing intervals ({spec['mode']})")
    except (OSError, ValueError, KeyError, TypeError, RuntimeError, KeyboardInterrupt) as error:
        pair.update(status="failed", ended_at_utc=now(), failure=str(error))
        if pair["executed"] and pair["executed"][-1]["status"] == "running":
            pair["executed"][-1].update(status="failed", ended_at_utc=now(), failure=str(error))
        write_json(root / "pair-manifest.json", pair)
        raise


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError, TypeError, RuntimeError) as error:
        raise SystemExit(f"run_core_pair: {error}")
