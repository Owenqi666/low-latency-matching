#!/usr/bin/env python3
"""Run finite service experiments, retaining every planned run and failure."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import selectors
import shlex
import shutil
import signal
import subprocess
import sys
import time

from create_service_workloads import GENERATOR_VERSION, generate, load_manifest, sha256, write_json
from run_bench import capture


def now():
    return datetime.now(timezone.utc).isoformat()


def binary_record(path):
    path = path.resolve()
    if not path.is_file():
        raise ValueError(f"binary does not exist: {path}")
    cache_path = path.parent / "CMakeCache.txt"
    cache = {}
    if cache_path.exists():
        for line in cache_path.read_text().splitlines():
            if line and not line.startswith(("#", "//")) and "=" in line:
                key, value = line.split("=", 1)
                cache[key.split(":", 1)[0]] = value
    flags = {}
    commands = path.parent / "compile_commands.json"
    if commands.exists():
        for item in json.loads(commands.read_text()):
            name = Path(item["file"]).name
            if name in {"matching_engine.cpp", "order_book.cpp", "pipeline.cpp", "server.cpp", "protocol.cpp",
                        "server_main.cpp", "loadgen_main.cpp", "service_verify.cpp"}:
                args = item.get("arguments") or shlex.split(item["command"])
                flags[name] = [arg for arg in args if arg.startswith(("-O", "-g", "-D", "-std=", "-march=", "-mcpu=", "-mtune=", "-flto", "-fsanitize", "-fno-omit", "-pthread"))]
    sanitized = any(cache.get(key) == "ON" for key in ("LLMATCH_SANITIZERS", "LLMATCH_TSAN")) or any(
        "sanitize" in flag for values in flags.values() for flag in values)
    compiler = cache.get("CMAKE_CXX_COMPILER")
    return {"path": str(path), "sha256": sha256(path), "build_type": cache.get("CMAKE_BUILD_TYPE"),
            "sanitized": sanitized, "compiler": capture([compiler, "--version"]) if compiler else {"available": False},
            "cmake_cache_sha256": sha256(cache_path) if cache_path.exists() else None,
            "build_flags": {key: cache.get(key) for key in ("CMAKE_CXX_FLAGS", "CMAKE_CXX_FLAGS_RELEASE", "CMAKE_EXE_LINKER_FLAGS")},
            "target_compile_flags": flags}


def environment(repository, host_environment):
    commit = capture(["git", "rev-parse", "HEAD"], repository)
    status = capture(["git", "status", "--porcelain"], repository)
    result = {"recorded_at_utc": now(), "os": platform.platform(), "kernel": platform.release(),
              "architecture": platform.machine(), "logical_cpus": os.cpu_count(), "python": platform.python_version(),
              "code_commit": commit.get("output") if commit["available"] else None,
              "code_dirty": bool(status["output"]) if status["available"] else None,
              "thread_configuration": "one Gateway io_context thread and one Matching thread; loadgen is a separate process",
              "transport": "TCP loopback on the same host", "physical_cpu_cores": None, "system_memory_bytes": None,
              "cpu_controls": {"affinity": "not changed by this runner", "frequency": "not controlled", "turbo": "not controlled",
                               "exclusive_core": False, "background_load": list(os.getloadavg()) if hasattr(os, "getloadavg") else None},
              "virtualization": {"available": False, "reason": "unknown"},
              "host_environment": json.loads(host_environment.read_text()) if host_environment else None}
    if sys.platform == "darwin":
        result["cpu"] = capture(["sysctl", "-n", "machdep.cpu.brand_string"])
        for key, variable in (("physical_cpu_cores", "hw.physicalcpu"), ("system_memory_bytes", "hw.memsize")):
            value = capture(["sysctl", "-n", variable])
            result[key] = int(value["output"]) if value["available"] else None
        result["virtualization"] = capture(["sysctl", "-n", "kern.hv_vmm_present"])
    elif sys.platform.startswith("linux"):
        result["cpu"] = capture(["lscpu"])
        result["virtualization"] = capture(["systemd-detect-virt"])
        memory = Path("/proc/meminfo").read_text()
        result["system_memory_bytes"] = int(next(line.split()[1] for line in memory.splitlines() if line.startswith("MemTotal:"))) * 1024
        topology = capture(["lscpu", "-p=SOCKET,CORE"])
        if topology["available"]:
            result["physical_cpu_cores"] = len({line for line in topology["output"].splitlines() if line and not line.startswith("#")})
            result["physical_core_scope"] = "guest-visible topology when virtualized; host physical cores require host_environment"
        if hasattr(os, "sched_getaffinity"):
            result["cpu_controls"]["inherited_affinity_cpus"] = sorted(os.sched_getaffinity(0))
        governors = sorted({path.read_text().strip() for path in Path("/sys/devices/system/cpu").glob("cpu*/cpufreq/scaling_governor")})
        result["cpu_controls"]["observed_governors"] = governors or None
    return result


def wait_ready(process, logfile, timeout):
    deadline = time.monotonic() + timeout
    pending = b""
    with selectors.DefaultSelector() as selector:
        selector.register(process.stdout, selectors.EVENT_READ)
        while time.monotonic() < deadline:
            if not selector.select(max(0, deadline - time.monotonic())):
                break
            data = os.read(process.stdout.fileno(), 4096)
            if not data:
                raise RuntimeError("server exited before READY; see server logs")
            logfile.write(data)
            logfile.flush()
            pending += data
            while b"\n" in pending:
                line, pending = pending.split(b"\n", 1)
                if line.startswith(b"READY "):
                    port = int(line.split()[1])
                    if not 1 <= port <= 65535:
                        raise ValueError("server reported an invalid READY port")
                    return port
    raise RuntimeError("server READY deadline exceeded")


def stop_server(process, stdout, timeout):
    if process.poll() is None:
        process.send_signal(signal.SIGTERM)
    try:
        remaining, _ = process.communicate(timeout=timeout)
        timed_out = False
    except subprocess.TimeoutExpired:
        process.kill()
        remaining, _ = process.communicate()
        timed_out = True
    stdout.write(remaining or b"")
    stdout.flush()
    return process.returncode, timed_out


def run_one(root, entry, row, spec, binaries):
    directory = root / entry["directory"]
    directory.mkdir(parents=True, exist_ok=False)
    (directory / "logs").mkdir()
    state = {**entry, "schema_version": 1, "status": "running", "started_at_utc": now(),
             "config": row, "invocations": {}, "server_exit": None, "loadgen_exit": None,
             "verifier_exit": None, "reference_verification": "not_run", "error": None}
    write_json(directory / "run.json", state)
    errors = []
    try:
        count = min(spec["warmup_commands"], row["commands"]) if entry["kind"] == "warmup" else row["commands"]
        workload = generate(row, directory / "inputs", count)
        state["config"] = {**row, "commands": count}
        state["setup_commands"] = workload["setup_commands"]
        state["inputs"] = {name: {**record, "path": "inputs/" + record["path"]} for name, record in workload["files"].items()}
        limits = spec["limits"]
        server_command = [binaries["server"]["path"], "--address", "127.0.0.1", "--port", "0", "--capacity", str(row["capacity"]),
                          "--max-price", "20000", "--max-qty", "1000000", "--record-limit", str(count + workload["setup_commands"]),
                          "--output-dir", str(directory / "server")]
        for option, key in (("--command-capacity", "command_capacity"), ("--event-capacity", "event_capacity"),
                            ("--max-connections", "max_connections"), ("--send-limit", "send_limit"), ("--shutdown-ms", "shutdown_ms")):
            server_command.extend((option, str(limits[key])))
        state["invocations"]["server"] = server_command
        with (directory / "logs/server.stdout.log").open("wb") as stdout, (directory / "logs/server.stderr.log").open("wb") as stderr:
            process = subprocess.Popen(server_command, stdout=subprocess.PIPE, stderr=stderr)
            state["server_pid"] = process.pid
            try:
                port = wait_ready(process, stdout, limits["startup_seconds"])
                state["server_port"] = port
                client_command = [binaries["loadgen"]["path"], "--host", "127.0.0.1", "--port", str(port),
                                  "--connections", str(row["connections"]), "--setup", str(directory / "inputs/setup.trace"),
                                  "--input", str(directory / "inputs/input.trace"), "--schedule", str(directory / "inputs/schedule.txt"),
                                  "--max-inflight", str(limits["max_inflight"]), "--max-send-bytes", str(limits["max_send_bytes"]),
                                  "--drain-ms", str(limits["drain_ms"]), "--output-dir", str(directory / "client")]
                state["invocations"]["loadgen"] = client_command
                write_json(directory / "run.json", state)
                timeout = limits["setup_budget_seconds"] + workload["schedule_last_offset_ns"] / 1e9 + limits["drain_ms"] / 1000 + limits["timeout_slack_seconds"]
                with (directory / "logs/loadgen.log").open("wb") as log:
                    state["loadgen_exit"] = subprocess.run(client_command, stdout=log, stderr=subprocess.STDOUT, timeout=timeout).returncode
                if state["loadgen_exit"]:
                    errors.append(f"loadgen exited {state['loadgen_exit']}; request failures retained")
            finally:
                state["server_exit"], state["server_killed_after_deadline"] = stop_server(
                    process, stdout, limits["shutdown_ms"] / 1000 + limits["timeout_slack_seconds"])
        if state["server_exit"]:
            errors.append(f"server exited {state['server_exit']}")
        server = json.loads((directory / "server/server.json").read_text())
        drained = state["server_exit"] == 0 and server["uncompleted"] == 0 and server["admitted"] == server["completed"]
        state["server_fully_drained"] = drained
        if drained:
            verify_command = [binaries["verifier"]["path"], "--directory", str(directory / "server")]
            state["invocations"]["verifier"] = verify_command
            with (directory / "logs/verification.log").open("wb") as log:
                state["verifier_exit"] = subprocess.run(verify_command, stdout=log, stderr=subprocess.STDOUT, timeout=120).returncode
            state["reference_verification"] = "passed" if state["verifier_exit"] == 0 else "failed"
            if state["verifier_exit"]:
                errors.append("independent service/reference verification failed")
        else:
            state["reference_verification"] = "not_run_incomplete_drain"
            errors.append("server did not fully drain; partial state is retained, not compared to a complete replay")
        for record in state["inputs"].values():
            if sha256(directory / record["path"]) != record["sha256"]:
                errors.append(f"input changed during the run: {record['path']}")
        for name, record in binaries.items():
            if sha256(record["path"]) != record["sha256"]:
                errors.append(f"{name} binary changed during the run")
    except (OSError, ValueError, KeyError, RuntimeError, subprocess.TimeoutExpired) as error:
        errors.append(str(error))
    except KeyboardInterrupt:
        state["status"] = "interrupted"
        state["error"] = "interrupted by user"
        write_json(directory / "run.json", state)
        raise
    state["status"] = "failed" if errors else "completed"
    state["error"] = "; ".join(errors) if errors else None
    state["ended_at_utc"] = now()
    write_json(directory / "run.json", state)
    return state


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--server", required=True, type=Path)
    parser.add_argument("--loadgen", required=True, type=Path)
    parser.add_argument("--verifier", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--row", action="append")
    parser.add_argument("--commands", type=int)
    parser.add_argument("--rounds", type=int)
    parser.add_argument("--rate", type=int)
    parser.add_argument("--host-environment", type=Path)
    parser.add_argument("--summarizer", type=Path, default=Path(__file__).with_name("summarize_service_bench.py"),
                        help="independent Python checker, invoked as SCRIPT OUTPUT_DIR (defaults to sibling script)")
    args = parser.parse_args()
    spec = load_manifest(args.manifest, args.row, args.commands, args.rounds, args.rate)
    binaries = {name: binary_record(getattr(args, name)) for name in ("server", "loadgen", "verifier")}
    if spec["mode"] == "formal":
        if not sys.platform.startswith("linux") or any(binaries[name]["build_type"] != "Release" or binaries[name]["sanitized"] for name in ("server", "loadgen")):
            raise ValueError("formal measurements require Linux and unsanitized Release server/loadgen builds")
    root = args.output_dir.resolve()
    root.mkdir(parents=True, exist_ok=False)
    shutil.copyfile(args.manifest, root / "source_manifest.json")
    expected = []
    for row in spec["rows"]:
        for repeat in range(spec["rounds"] + 1):
            suffix = "warmup" if repeat == 0 else f"round_{repeat}"
            expected.append({"id": f"{row['id']}-{suffix}", "row": row["id"], "round": repeat,
                             "kind": "warmup" if repeat == 0 else "measurement",
                             "directory": f"runs/{row['id']}/{suffix}", "status": "planned"})
    manifest = {"schema_version": 1, "generator_version": GENERATOR_VERSION, "mode": spec["mode"],
                "source_manifest_sha256": sha256(root / "source_manifest.json"), "workload_parameters": spec,
                "environment": environment(Path(__file__).resolve().parents[1], args.host_environment),
                "binaries": binaries, "expectedRuns": expected, "status": "running", "started_at_utc": now()}
    write_json(root / "manifest.json", manifest)
    rows = {row["id"]: row for row in spec["rows"]}
    try:
        for entry in expected:
            entry["status"] = "running"
            write_json(root / "manifest.json", manifest)
            print(f"{entry['id']}: starting", flush=True)
            state = run_one(root, entry, rows[entry["row"]], spec, binaries)
            entry["status"] = state["status"]
            print(f"{entry['id']}: {state['status']}" + (f" ({state['error']})" if state["error"] else ""), flush=True)
            write_json(root / "manifest.json", manifest)
    except KeyboardInterrupt:
        entry["status"] = "interrupted"
        manifest["status"] = "interrupted"
        write_json(root / "manifest.json", manifest)
        raise
    manifest["status"] = "completed" if all(entry["status"] == "completed" for entry in expected) else "failed"
    manifest["ended_at_utc"] = now()
    write_json(root / "manifest.json", manifest)
    with (root / "summary-check.log").open("wb") as log:
        manifest["summarizer_exit"] = subprocess.run([sys.executable, str(args.summarizer.resolve()), str(root)], stdout=log, stderr=subprocess.STDOUT).returncode
    if manifest["summarizer_exit"]:
        manifest["status"] = "failed"
    write_json(root / "manifest.json", manifest)
    return 0 if manifest["status"] == "completed" else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise SystemExit(f"run_service_bench: {error}")
