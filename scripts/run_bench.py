#!/usr/bin/env python3
"""Generate inputs, record build/environment evidence, then run each benchmark once."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import shlex
import subprocess
import sys

from create_bench_workloads import file_hashes, generate, load_manifest, write_json
from summarize_bench import summarize, validate_run


def capture(command, cwd=None):
    try:
        result = subprocess.run(command, cwd=cwd, capture_output=True, text=True, check=False)
    except FileNotFoundError:
        return {"available": False, "reason": "command unavailable"}
    return {"available": result.returncode == 0, "exit_code": result.returncode,
            "output": result.stdout.strip() if result.returncode == 0 else result.stderr.strip()}


def environment(binary, repository):
    cache_path = binary.parent / "CMakeCache.txt"
    cache = {}
    for line in cache_path.read_text(encoding="utf-8").splitlines():
        if line and not line.startswith(("#", "//")) and "=" in line:
            name, value = line.split("=", 1)
            cache[name.split(":", 1)[0]] = value
    if cache.get("CMAKE_BUILD_TYPE") != "Release" or cache.get("LLMATCH_SANITIZERS") != "OFF":
        raise ValueError("benchmark requires a Release CMake build with LLMATCH_SANITIZERS=OFF")
    compiler = cache["CMAKE_CXX_COMPILER"]
    compile_path = binary.parent / "compile_commands.json"
    flags = {}
    if compile_path.exists():
        for item in json.loads(compile_path.read_text(encoding="utf-8")):
            name = Path(item["file"]).name
            if name in {"matching_engine.cpp", "order_book.cpp", "core_bench.cpp"}:
                arguments = item.get("arguments") or shlex.split(item["command"])
                flags[name] = [arg for arg in arguments if arg.startswith(("-O", "-g", "-D", "-std=", "-march=", "-mcpu=", "-mtune=", "-flto", "-fsanitize", "-fno-omit"))]
    if any("sanitize" in flag for values in flags.values() for flag in values):
        raise ValueError("compile commands contain sanitizer flags")
    status = capture(["git", "status", "--porcelain"], repository)
    commit = capture(["git", "rev-parse", "HEAD"], repository)
    cpu = platform.processor() or "unavailable"
    physical_cores = None
    memory_bytes = None
    controls = {"affinity": "not controlled by this runner", "frequency": "not controlled",
                "turbo": "not controlled", "exclusive_core": False,
                "background_load": list(os.getloadavg()) if hasattr(os, "getloadavg") else "unavailable"}
    virtualization = {"available": False, "reason": "not detected on this platform"}
    if sys.platform == "darwin":
        identity = capture(["sysctl", "-n", "machdep.cpu.brand_string"])
        cpu = identity["output"] if identity["available"] else cpu
        virtualization = capture(["sysctl", "-n", "kern.hv_vmm_present"])
        physical = capture(["sysctl", "-n", "hw.physicalcpu"])
        memory = capture(["sysctl", "-n", "hw.memsize"])
        physical_cores = int(physical["output"]) if physical["available"] else None
        memory_bytes = int(memory["output"]) if memory["available"] else None
    elif sys.platform.startswith("linux"):
        info = Path("/proc/cpuinfo")
        if info.exists():
            models = [line.split(":", 1)[1].strip() for line in info.read_text().splitlines() if line.startswith("model name")]
            if models:
                cpu = models[0]
        memory = Path("/proc/meminfo")
        if memory.exists():
            totals = [line.split()[1] for line in memory.read_text().splitlines() if line.startswith("MemTotal:")]
            memory_bytes = int(totals[0]) * 1024 if totals else None
        if hasattr(os, "sched_getaffinity"):
            controls["inherited_affinity_cpus"] = sorted(os.sched_getaffinity(0))
        governors = sorted({path.read_text().strip() for path in Path("/sys/devices/system/cpu").glob("cpu*/cpufreq/scaling_governor")})
        controls["observed_governors"] = governors or "unavailable"
        virtualization = capture(["systemd-detect-virt"])
        if virtualization.get("exit_code") == 1:
            virtualization = {"available": True, "output": "none reported by systemd-detect-virt"}
    return {
        "recorded_at_utc": datetime.now(timezone.utc).isoformat(), "os": platform.platform(),
        "architecture": platform.machine(), "cpu": cpu, "logical_cpus": os.cpu_count(),
        "physical_cpu_cores": physical_cores, "system_memory_bytes": memory_bytes,
        "python": platform.python_version(), "compiler": capture([compiler, "--version"]),
        "cmake": capture([cache.get("CMAKE_COMMAND", "cmake"), "--version"]),
        "build_type": cache["CMAKE_BUILD_TYPE"], "sanitizers": cache["LLMATCH_SANITIZERS"],
        "build_flags": {name: cache.get(name, "") for name in ("CMAKE_CXX_FLAGS", "CMAKE_CXX_FLAGS_RELEASE", "CMAKE_EXE_LINKER_FLAGS")},
        "target_compile_flags": flags, "cmake_cache_sha256": hashlib.sha256(cache_path.read_bytes()).hexdigest(),
        "code_commit": commit["output"] if commit["available"] else None,
        "code_dirty": bool(status["output"]) if status["available"] else None,
        "binary_sha256": hashlib.sha256(binary.read_bytes()).hexdigest(),
        "binary_name": binary.name, "thread_configuration": "single-threaded matching core; independent latency/throughput rounds",
        "cpu_controls": controls, "virtualization": virtualization,
        "environment_policy": "Selected measurements only; no full environment-variable dump.",
    }


def execute(command, logfile):
    with logfile.open("w", encoding="utf-8") as output:
        result = subprocess.run(command, stdout=output, stderr=subprocess.STDOUT, check=False)
    if result.returncode != 0:
        raise RuntimeError(f"{Path(command[0]).name} exited {result.returncode}; see {logfile}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--commands", type=int)
    parser.add_argument("--capacity", type=int, action="append")
    args = parser.parse_args()
    if args.repeats < 1:
        raise ValueError("repeats must be positive")
    binary = args.binary.resolve()
    if not binary.is_file():
        raise ValueError(f"benchmark binary does not exist: {binary}")
    spec = load_manifest(args.manifest, args.commands, args.capacity)
    repository = Path(__file__).resolve().parents[1]
    recorded_environment = environment(binary, repository)
    directories = [args.output_dir.resolve() / spec["scenario"] / f"capacity_{capacity}" for capacity in spec["capacities"]]
    if any((directory / "summary.json").exists() or (directory / "run_manifest.json").exists() for directory in directories):
        raise ValueError("output already contains a run; choose a new output directory to preserve all rounds")
    for capacity, directory in zip(spec["capacities"], directories):
        workload = generate(spec, capacity, directory)
        command = [str(binary), "--config", str(directory / "config.txt"), "--setup", str(directory / "setup.trace"),
                   "--input", str(directory / "input.trace"), "--repeats", str(args.repeats), "--output-dir", str(directory)]
        manifest = {"schema_version": 1, "repeats": args.repeats, "workload_parameters": spec,
                    "source_manifest_sha256": hashlib.sha256(args.manifest.read_bytes()).hexdigest(),
                    "inputs": workload["files"], "environment": recorded_environment,
                    "invocation": command, "formal_repetition_count": args.repeats >= 5}
        write_json(directory / "run_manifest.json", manifest)
        clock = binary.with_name("clock_probe")
        if not clock.is_file():
            raise ValueError(f"required clock probe does not exist: {clock}")
        execute([str(clock), "--output", str(directory / "clock_probe.json")], directory / "clock_probe.log")
        manifest["clock_probe"] = {"path": "clock_probe.json", **file_hashes(directory / "clock_probe.json")}
        write_json(directory / "run_manifest.json", manifest)
        print(f"Running {spec['scenario']} capacity={capacity}, commands={spec['commands']}, repeats={args.repeats}", flush=True)
        execute(command, directory / "benchmark.log")
        for name, record in workload["files"].items():
            actual = file_hashes(directory / record["path"])
            if any(actual[key] != record[key] for key in actual):
                raise ValueError(f"{name} changed during measurement")
        if hashlib.sha256(binary.read_bytes()).hexdigest() != recorded_environment["binary_sha256"]:
            raise ValueError("benchmark binary changed during measurement")
        validate_run(directory)
    report = summarize(args.output_dir)
    print(f"Validated {len(report['runs'])} workload/capacity runs; report: {args.output_dir / 'report.md'}")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError, TypeError, RuntimeError) as error:
        raise SystemExit(f"run_bench: {error}")
