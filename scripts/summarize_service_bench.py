#!/usr/bin/env python3
"""Independently validate every declared service run before reporting its measurements.

Expected overload attempts may contain losses. Their evidence must still balance;
an unsuccessful server drain never becomes a successful performance measurement.
"""
import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import json
import math
from pathlib import Path

CLIENT_COLUMNS = "idx,logical,actual,request,scheduled_ns,first_attempt_ns,write_completed_ns,complete_ns,command_seq,events,trades,checksum,completion_status,outcome,failure,send_lag_ns,rtt_ns,offset_ns".split(",")
SERVICE_COLUMNS = "command_seq,client,request,order_id,admitted_ns,gateway_wait_ns,completed_ns,service_ns,events,trades,checksum,status".split(",")
COUNTS = "planned not_started started completed failed unfinished accepted rejected".split()
NULLABLE = set("scheduled_ns first_attempt_ns write_completed_ns complete_ns send_lag_ns rtt_ns offset_ns".split())


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read_json(path):
    return json.loads(path.read_text())


def file_hash(path):
    value = 14695981039346656037
    for byte in path.read_bytes():
        value = ((value ^ byte) * 1099511628211) & ((1 << 64) - 1)
    return f"fnv1a64:{value:016x}"


def local_file(directory, relative):
    path = (directory / relative).resolve()
    path.relative_to(directory.resolve())
    return path


def read_csv(path, columns):
    rows = []
    with path.open(newline="") as source:
        reader = csv.DictReader(source)
        require(reader.fieldnames == columns, f"{path}: unexpected CSV header")
        for raw in reader:
            require(None not in raw and all(value is not None for value in raw.values()), f"{path}: incomplete row")
            row = {}
            for key, value in raw.items():
                if key in ("outcome", "failure"):
                    row[key] = value
                elif value == "" and key in NULLABLE:
                    row[key] = None
                else:
                    row[key] = int(value)
                    require(row[key] >= 0, f"{path}: negative {key}")
            rows.append(row)
    return rows


def read_trace(path):
    lines = path.read_text().splitlines()
    require(lines and lines[0] == "LLMATCH_TRACE 1", f"{path}: invalid trace header")
    result = []
    for line in lines[1:]:
        fields = line.split()
        if not fields or line.startswith("#"):
            continue
        require(fields[0] in ("L", "M", "C"), f"{path}: unknown command")
        require(len(fields) == {"L": 7, "M": 6, "C": 4}[fields[0]], f"{path}: malformed command")
        result.append((fields[0], *map(int, fields[1:])))
    return result


def distribution(values):
    if not values:
        return {"samples": 0, "p50_ns": None, "p99_ns": None}
    ordered = sorted(values)
    return {"samples": len(values), "p50_ns": ordered[math.ceil(.5 * len(values)) - 1],
            "p99_ns": ordered[math.ceil(.99 * len(values)) - 1], "max_ns": ordered[-1]}


def validate_gateway_diagnostics(directory, server):
    """Check optional bounded Gateway records without changing legacy summaries."""
    path = directory / "gateway_diagnostics.json"
    filenames = ("gateway_diagnostics.json", "gateway_closes.csv", "gateway_windows.csv", "gateway_connections.csv")
    if not server.get("gateway_diagnostics_enabled", False):
        require(not any((directory / name).exists() for name in filenames),
                "disabled Gateway diagnostics left stale detailed artifacts")
        return None
    report = read_json(path)
    require(report["schema_version"] == 1 and report["clock"] == "server_steady_clock_ns",
            "unsupported Gateway diagnostics schema/clock")
    require(report["sample_period_ns"] == 10_000_000, "unexpected Gateway sample period")
    require(report["storage_bytes"] > 0, "missing bounded diagnostic storage size")
    tables = {}
    outbound = ("client,bytes,frames,in_flight_bytes,in_flight_frames,max_bytes,max_frames,"
                "max_in_flight_bytes,max_in_flight_frames,write_operations,write_callbacks,"
                "write_error_callbacks,last_write_started_ns,last_callback_ns")
    headers = {"close": "closed_ns,reason," + outbound,
               "connection_window": "observed_ns," + outbound,
               "window": "planned_ns,observed_ns,command_depth,event_depth,connections,admitted,events_consumed,"
                         "bbo_consumed,write_operations,write_callbacks,bytes_transferred,write_operations_delta,"
                         "write_callbacks_delta,bytes_transferred_delta"}
    for name, filename, capacity in (("close", "gateway_closes.csv", 128),
                                     ("window", "gateway_windows.csv", 4096),
                                     ("connection_window", "gateway_connections.csv", 16384)):
        require(report[name + "_capacity"] == capacity and
                0 <= report[name + "_count"] <= capacity and report[name + "_overflow"] >= 0,
                "invalid Gateway diagnostic record bound")
        require(not report[name + "_overflow"] or report[name + "_count"] == capacity,
                "Gateway overflow without full retained storage")
        with (directory / filename).open(newline="") as source:
            reader = csv.DictReader(source)
            require(reader.fieldnames == headers[name].split(","), "Gateway diagnostic CSV header mismatch")
            rows = list(reader)
        require(len(rows) == report[name + "_count"], "Gateway diagnostic CSV count mismatch")
        for row in rows:
            require(None not in row and all(value is not None for value in row.values()),
                    "incomplete Gateway diagnostic CSV row")
            for key in row:
                if key != "reason":
                    row[key] = int(row[key])
                    require(row[key] >= 0, "negative Gateway diagnostic field")
        tables[name] = rows
    for name in ("whole_write_completion", "callback_interval", "loop_lateness"):
        histogram = report[name]
        require(len(histogram["buckets"]) == 64 and all(v >= 0 for v in histogram["buckets"])
                and sum(histogram["buckets"]) == histogram["count"], "invalid Gateway histogram counts")
        maximum = histogram["maximum_ns"]
        require(0 <= maximum < 2**64 and (histogram["count"] > 0 or maximum == 0), "invalid Gateway histogram maximum")
        if histogram["count"]:
            require(max(i for i, n in enumerate(histogram["buckets"]) if n) == max(0, maximum.bit_length() - 1),
                    "Gateway maximum differs from highest populated bucket")
    require(report["whole_write_completion"]["count"] == server["write_callbacks"],
            "Gateway composed callback count mismatch")
    require(report["callback_interval"]["count"] <= server["write_callbacks"], "too many callback intervals")
    require(report["loop_lateness"]["count"] == report["window_count"] + report["window_overflow"],
            "Gateway timer sample count mismatch")
    require(report["close_count"] + report["close_overflow"] == sum(server["close_reasons"].values()),
            "Gateway close snapshot count mismatch")
    reasons = Counter(row["reason"] for row in tables["close"])
    require(all(reasons[name] <= count for name, count in server["close_reasons"].items()),
            "Gateway close reason count mismatch")
    require(len({row["client"] for row in tables["close"]}) == len(tables["close"]),
            "duplicate Gateway close snapshot")
    previous = {}
    for row in tables["window"]:
        require(row["observed_ns"] >= row["planned_ns"] and
                row["observed_ns"] >= previous.get("observed_ns", 0), "Gateway sample time order mismatch")
        require(row["command_depth"] <= server["command_capacity"] and
                row["event_depth"] <= server["event_capacity"] and row["connections"] <= server["max_connections"],
                "Gateway queue/connection depth exceeds capacity")
        require(row["admitted"] <= server["admitted"] and row["events_consumed"] <= server["events_consumed"] and
                row["bbo_consumed"] <= server["bbo_consumed"], "Gateway window exceeds final counters")
        for name, total in (("write_operations", "write_operations"), ("write_callbacks", "write_callbacks"),
                            ("bytes_transferred", "write_bytes_transferred")):
            require(row[name] <= server[total] and
                    row[name + "_delta"] == row[name] - previous.get(name, 0), "Gateway window delta mismatch")
        previous = row
    if tables["window"]:
        require(report["first_window_ns"] == tables["window"][0]["observed_ns"] and
                report["last_retained_window_ns"] == tables["window"][-1]["observed_ns"] and
                report["last_observed_window_ns"] >= report["last_retained_window_ns"],
                "Gateway retained time coverage mismatch")
    else:
        require(report["first_window_ns"] == report["last_retained_window_ns"] == report["last_observed_window_ns"] == 0
                and not tables["connection_window"], "unexpected empty Gateway window coverage")
    connection_times = [row["observed_ns"] for row in tables["connection_window"]]
    require(connection_times == sorted(connection_times) and
            all(t <= report["last_observed_window_ns"] for t in connection_times),
            "Gateway connection time order mismatch")
    for name, field, first_key, last_key in (
            ("connection_window", "observed_ns", "first_connection_window_ns", "last_retained_connection_window_ns"),
            ("close", "closed_ns", "first_retained_close_ns", "last_retained_close_ns")):
        times = [row[field] for row in tables[name]]
        require(times == sorted(times) and report[first_key] == (times[0] if times else 0) and
                report[last_key] == (times[-1] if times else 0), "Gateway table time coverage mismatch")
    per_tick = defaultdict(set)
    for row in tables["connection_window"]:
        ids = per_tick[row["observed_ns"]]
        require(row["client"] not in ids, "duplicate connection in Gateway window")
        ids.add(row["client"])
    for row in tables["window"]:
        if not report["connection_window_overflow"] or (connection_times and row["observed_ns"] < connection_times[-1]):
            require(len(per_tick[row["observed_ns"]]) == row["connections"], "Gateway connection/window association mismatch")
    for row in tables["close"] + tables["connection_window"]:
        time_ns = row.get("closed_ns", row.get("observed_ns"))
        require(0 < row["client"] <= server["connections"] and row["bytes"] <= row["max_bytes"] <= server["send_limit"]
                and row["max_frames"] <= row["max_bytes"], "invalid connection identity/allowance")
        for unit in ("bytes", "frames"):
            require(row["in_flight_" + unit] <= row[unit] <= row["max_" + unit] and
                    row["in_flight_" + unit] <= row["max_in_flight_" + unit], "Gateway in-flight/high-water mismatch")
        require(row["in_flight_frames"] <= server["write_batch_max_frames"] and
                row["in_flight_bytes"] <= server["write_batch_max_bytes"] and
                row["max_in_flight_frames"] <= min(row["max_frames"], server["write_batch_max_frames"]) and
                row["max_in_flight_bytes"] <= min(row["max_bytes"], server["write_batch_max_bytes"]),
                "Gateway batch bound exceeded")
        require(row["write_error_callbacks"] <= row["write_callbacks"] <= row["write_operations"] and
                max(row["last_write_started_ns"], row["last_callback_ns"]) <= time_ns,
                "Gateway connection callback count/time mismatch")
        require(all(row[name] <= server[name] for name in
                    ("write_operations", "write_callbacks", "write_error_callbacks")),
                "Gateway connection write counts exceed global totals")
        require(bool(row["in_flight_frames"]) == bool(row["in_flight_bytes"]) and
                row["write_operations"] - row["write_callbacks"] == int(row["in_flight_frames"] > 0),
                "Gateway outstanding write differs from in-flight state")
        if "reason" in row:
            require(row["reason"] in server["close_reasons"], "unknown Gateway close reason")
    return report


def client_samples(rows, commands, summary, mapping, schedule=None, start=0):
    require(len(rows) == len(commands), "client samples do not cover every planned request")
    counts = Counter({key: 0 for key in COUNTS})
    counts["planned"] = len(rows)
    for index, (sample, command) in enumerate(zip(rows, commands)):
        require(sample["idx"] == index and sample["logical"] == command[1] and
                sample["actual"] == mapping[command[1]] and sample["request"] == command[2],
                "client sample identity/order differs from input")
        outcome = sample["outcome"]
        require(outcome in ("completed", "failed", "unfinished", "not_started"), "invalid request outcome")
        attempted, completed = sample["first_attempt_ns"], sample["complete_ns"]
        counts["started" if attempted is not None else "not_started"] += 1
        require((attempted is None) == (outcome == "not_started"), "request outcome/attempt mismatch")
        if schedule is not None:
            require(sample["offset_ns"] == schedule[index], "sample offset differs from fixed schedule")
            require(sample["scheduled_ns"] == (start + schedule[index] if start else None), "scheduled time mismatch")
            if attempted is not None:
                require(sample["scheduled_ns"] is not None and attempted >= sample["scheduled_ns"] and
                        sample["send_lag_ns"] == attempted - sample["scheduled_ns"], "send lag mismatch")
        else:
            require(sample["offset_ns"] is None and sample["scheduled_ns"] is None, "setup included in input schedule")
        if sample["write_completed_ns"] is not None:
            require(attempted is not None and sample["write_completed_ns"] >= attempted, "write timestamp mismatch")
        if outcome == "completed":
            require(completed is not None and completed >= attempted and sample["rtt_ns"] == completed - attempted,
                    "completed request has invalid RTT")
            require(not sample["failure"] and sample["completion_status"] in (1, 2) and sample["command_seq"] > 0,
                    "completed request has no valid terminal response")
            counts["completed"] += 1
            counts["accepted" if sample["completion_status"] == 1 else "rejected"] += 1
        else:
            require(completed is None and sample["rtt_ns"] is None and sample["failure"], "failed/unstarted request has no reason or invented RTT")
            if outcome != "not_started":
                counts[outcome] += 1
    require(all(summary[key] == counts[key] for key in COUNTS), "client JSON/CSV counts differ")
    require(counts["planned"] == counts["not_started"] + counts["started"] and
            counts["started"] == counts["completed"] + counts["failed"] + counts["unfinished"], "request count conservation failed")
    return dict(counts)


def validate_run(directory, expected, parameters):
    run = read_json(directory / "run.json")
    require(all(run[key] == expected[key] for key in ("id", "row", "round", "kind")), "run identity differs from manifest")
    require(run["status"] == expected["status"] and run["status"] in ("completed", "failed"), "run was not finished or status differs")
    fixed_row = next(row for row in parameters["rows"] if row["id"] == expected["row"])
    planned_count = min(parameters["warmup_commands"], fixed_row["commands"]) if expected["kind"] == "warmup" else fixed_row["commands"]
    require(run["config"] == {**fixed_row, "commands": planned_count}, "run configuration differs from fixed manifest")
    inputs = {}
    for name in ("config", "setup", "input", "schedule"):
        record = run["inputs"][name]
        path = local_file(directory, record["path"])
        require(hashlib.sha256(path.read_bytes()).hexdigest() == record["sha256"], f"{name}: input SHA256 mismatch")
        inputs[name] = path
    workload = read_json(directory / "inputs/workload.json")
    require(workload["row"] == fixed_row and workload["commands"] == planned_count, "workload differs from fixed manifest")
    setup, commands = read_trace(inputs["setup"]), read_trace(inputs["input"])
    schedule = [int(line) for line in inputs["schedule"].read_text().splitlines()]
    require(len(schedule) == len(commands) == workload["commands"] and len(setup) == workload["setup_commands"], "planned input counts differ")
    require(schedule and schedule[0] >= 0 and schedule == sorted(schedule), "invalid schedule")
    offsets = [index * 1000000000 // fixed_row["target_rate_per_sec"] for index in range(len(commands))]
    if fixed_row["scenario"] == "burst":
        period, window = fixed_row["burst_period_ns"], fixed_row["burst_window_ns"]
        offsets = [offset // period * period + offset % period * window // period for offset in offsets]
    require(schedule == offsets and workload["schedule_plan_window_ns"] ==
            (len(commands) * 1000000000 + fixed_row["target_rate_per_sec"] - 1) // fixed_row["target_rate_per_sec"],
            "schedule or plan window differs from configured arrival rate")
    for name, path in inputs.items():
        require(workload["files"][name]["sha256"] == run["inputs"][name]["sha256"], f"{name}: workload/run identity mismatch")

    client = read_json(directory / "client/client.json")
    server = read_json(directory / "server/server.json")
    require(server.get("gateway_diagnostics_enabled", False) == parameters.get("gateway_diagnostics", False),
            "Gateway diagnostic setting differs from experiment parameters")
    validate_gateway_diagnostics(directory / "server", server)
    require(client["schema_version"] == server["schema_version"] == 1, "unsupported evidence schema")
    require(client["exit_status"] == run["loadgen_exit"] and server["exit_status"] == run["server_exit"], "process/report exit mismatch")
    require(all(server[key] == parameters["limits"][key] for key in ("command_capacity", "event_capacity", "max_connections", "send_limit", "shutdown_ms")) and
            all(client[key] == parameters["limits"][key] for key in ("max_inflight", "max_send_bytes", "drain_ms")), "runtime limits differ from fixed manifest")
    for name in ("setup", "input", "schedule"):
        require(client[name + "_hash"] == file_hash(inputs[name]), f"client used a different {name}")
    require((directory / "server/engine.config").read_bytes() == inputs["config"].read_bytes(), "server used different engine config")
    mapping = {item["logical"]: item["actual"] for item in client["logical_to_actual"]}
    require(len(mapping) == run["config"]["connections"] and set(mapping) == set(range(1, len(mapping) + 1)), "logical client mapping incomplete")
    actual_ids = [value for value in mapping.values() if value]
    require(len(actual_ids) == len(set(actual_ids)), "duplicate server ClientId")
    require(client["inflight_high_water"] <= client["max_inflight"] and all(
        item["send_high_water"] <= client["max_send_bytes"] for item in client["logical_to_actual"]), "client capacity exceeded")
    samples = read_csv(directory / "client/client_samples.csv", CLIENT_COLUMNS)
    setup_samples = read_csv(directory / "client/setup_samples.csv", CLIENT_COLUMNS)
    counts = client_samples(samples, commands, client, mapping, schedule, client["measurement_start_ns"])
    client_samples(setup_samples, setup, client["setup"], mapping)
    all_client = setup_samples + samples
    all_commands = setup + commands
    start, end = client["measurement_start_ns"], client["measurement_end_ns"]
    require(end >= start, "invalid client measurement interval")
    resources = client.get("resource_usage")
    if resources is not None:
        require(resources["scope"] == "process_lifetime_before_evidence", "invalid client resource scope")
        require(all(type(resources[key]) is int and resources[key] >= 0
                    for key in ("user_cpu_us", "system_cpu_us", "peak_rss_bytes", "captured_ns")), "invalid client resource values")
        require(resources["peak_rss_bytes"] > 0 and resources["captured_ns"] >= end,
                "client resource snapshot predates completion or has no RSS")
    for sample in all_client:
        for key in ("first_attempt_ns", "write_completed_ns", "complete_ns"):
            require(sample[key] is None or sample[key] <= end, "client timestamp lies beyond the measurement end")
    for sample in samples:
        require(all(sample[key] is None or start <= sample[key] for key in ("first_attempt_ns", "write_completed_ns", "complete_ns")), "measured request predates measurement start")
    if start:
        require(all(sample["complete_ns"] is not None and sample["complete_ns"] <= start for sample in setup_samples), "setup completion overlaps measurement")
    by_identity = {}
    for command, sample in zip(all_commands, all_client):
        key = (sample["actual"], command[2])
        require(key not in by_identity, "duplicate client request identity in experiment")
        by_identity[key] = ((command[0], sample["actual"], *command[2:]), sample)

    admitted = read_trace(directory / "server/admitted.trace")
    service = read_csv(directory / "server/service_samples.csv", SERVICE_COLUMNS)
    require(server["record_limit"] > 0 and server["record_limit"] >= len(admitted), "server experiment recording disabled/truncated")
    require(server["admitted"] == len(admitted) and server["completed"] == len(service) and
            server["admitted"] == server["completed"] + server["uncompleted"], "server counts do not conserve admitted work")
    require(len(service) <= len(admitted) and server["events_consumed"] <= server["events_published"] and
            server["bbo_consumed"] <= server["bbo_published"], "invalid event consumption counts")
    require(server["command_high_water"] <= server["command_capacity"] and
            server["event_high_water"] <= server["event_capacity"] and server["send_high_water"] <= server["send_limit"], "server capacity exceeded")
    seen = set()
    by_sequence = {}
    measured_service = []
    setup_keys = {(sample["actual"], sample["request"]) for sample in setup_samples}
    previous_admitted = previous_complete = 0
    for index, command in enumerate(admitted):
        key = command[1:3]
        require(key in by_identity and key not in seen, "admitted request missing from plan or duplicated")
        planned, sample = by_identity[key]
        require(planned == command and sample["first_attempt_ns"] is not None, "admitted command differs from attempted plan")
        seen.add(key)
        if index >= len(service):
            continue
        value = service[index]
        require(value["command_seq"] == index + 1 and value["client"] == command[1] and
                value["request"] == command[2] and value["order_id"] == command[3], "service sample identity/order mismatch")
        require(value["completed_ns"] >= value["admitted_ns"] >= previous_admitted and value["completed_ns"] >= previous_complete and
                server["started_ns"] <= value["admitted_ns"] and value["completed_ns"] <= server["ended_ns"] and
                value["service_ns"] == value["completed_ns"] - value["admitted_ns"], "service timestamps inconsistent")
        previous_admitted, previous_complete = value["admitted_ns"], value["completed_ns"]
        by_sequence[index + 1] = value
        if key not in setup_keys:
            measured_service.append(value)
    for sample in all_client:
        if sample["outcome"] == "completed":
            value = by_sequence.get(sample["command_seq"])
            require(value is not None and value["client"] == sample["actual"] and value["request"] == sample["request"], "client Complete absent from server completion records")
            require(all(sample[key] == value[key] for key in ("events", "trades", "checksum")) and
                    sample["completion_status"] == value["status"], "client business stream differs from canonical service stream")

    drained = server["exit_status"] == 0
    if drained:
        require(not server["failure"] and not server["worker_aborted"] and server["current_admission"] == 0 and
                server["worker_phase"] == "idle" and server["uncompleted"] == 0, "successful exit contradicts worker state")
        require(server["events_published"] == server["events_consumed"] == sum(row["events"] for row in service) and
                server["bbo_published"] == server["bbo_consumed"], "successful drain has missing events")
        verification = read_json(directory / "server/verification.json")
        require(run["verifier_exit"] == 0 and verification["result"] == "passed", "reference verifier did not pass")
        for key, name in (("admitted_trace_hash", "admitted.trace"), ("snapshot_hash", "final.snapshot"),
                          ("samples_hash", "service_samples.csv"), ("server_report_hash", "server.json"), ("config_hash", "engine.config")):
            require(verification[key] == file_hash(directory / "server" / name), f"stale reference verification: {name}")
        expected_counts = {"commands": len(service), "events": sum(row["events"] for row in service),
                           "trades": sum(row["trades"] for row in service), "accepted": sum(row["status"] == 1 for row in service),
                           "rejected": sum(row["status"] == 2 for row in service)}
        require(all(verification[key] == value for key, value in expected_counts.items()), "reference verification counts differ")
        require(verification["business_recipients"] == server["written_business_frames"] + server["discarded_business_frames"] +
                server["missing_business_recipients"], "business recipient counters do not conserve delivery attempts")
    else:
        require(server["failure"] and not (directory / "server/verification.json").exists(), "failed drain has no failure or a stale success report")
        require(server["current_admission"] == 0 or server["completed"] < server["current_admission"] <= server["admitted"], "invalid interrupted command position")

    succeeded = drained and client["exit_status"] == 0
    require((run["status"] == "completed") == succeeded, "run status contradicts exit evidence")
    if client["exit_status"] == 0:
        require(not client["failure"] and counts["completed"] == counts["planned"] and
                client["setup"]["completed"] == len(setup), "successful client exit has incomplete requests")
    elapsed = (end - start) / 1e9 if start else 0
    window = workload["schedule_plan_window_ns"] / 1e9
    completed = [row for row in samples if row["outcome"] == "completed"]
    groups = defaultdict(list)
    for command, sample in zip(commands, samples):
        if sample["outcome"] == "completed":
            groups[(command[0], sample["completion_status"])].append(sample["rtt_ns"])
    return {"id": expected["id"], "row": expected["row"], "round": expected["round"], "kind": expected["kind"],
            "succeeded": succeeded, "server_drained": drained, "client_exit": client["exit_status"], "server_exit": server["exit_status"],
            "failure": client["failure"] or server["failure"], "counts": counts,
            "failure_reasons": dict(Counter(row["failure"] for row in samples if row["failure"])),
            "written_complete_frames": sum(row["write_completed_ns"] is not None for row in samples),
            "plan_window_seconds": window, "measurement_seconds": elapsed,
            "target_per_second": run["config"]["target_rate_per_sec"],
            "attempted_per_second": counts["started"] / elapsed if elapsed else 0,
            "completed_per_second": counts["completed"] / elapsed if elapsed else 0,
            "unfinished_fraction": (counts["planned"] - counts["completed"]) / counts["planned"],
            "rtt": distribution([row["rtt_ns"] for row in completed]),
            "send_lag": distribution([row["send_lag_ns"] for row in samples if row["send_lag_ns"] is not None]),
            "service": distribution([row["service_ns"] for row in measured_service]) if drained else None,
            "gateway_wait": distribution([row["gateway_wait_ns"] for row in measured_service]) if drained else None,
            "rtt_groups": [{"command": key[0], "completion_status": key[1], **distribution(values)} for key, values in sorted(groups.items())],
            "normal_sample_target_met": len(completed) >= 100000 and elapsed >= 10,
            "server_counters": server, "client_resources": resources, "clock_probe": client["clock_probe"]}


def summarize(directory):
    directory = Path(directory).resolve()
    for name in ("report.json", "report.md"):
        (directory / name).unlink(missing_ok=True)
    manifest = read_json(directory / "manifest.json")
    require(manifest["schema_version"] == 1 and manifest["expectedRuns"], "invalid or empty run manifest")
    require(manifest["status"] in ("completed", "failed"), "experiment manifest is not terminal")
    require(hashlib.sha256((directory / "source_manifest.json").read_bytes()).hexdigest() == manifest["source_manifest_sha256"], "source manifest hash mismatch")
    source = read_json(directory / "source_manifest.json")
    expected = manifest["expectedRuns"]
    parameters = manifest["workload_parameters"]
    require(source["mode"] == parameters["mode"] == manifest["mode"], "experiment mode differs from source manifest")
    require(manifest["mode"] in {"smoke", "calibration", "formal", "m4-formal"}, "unknown service experiment mode")
    planned = {(row["id"], number, "warmup" if number == 0 else "measurement")
               for row in parameters["rows"] for number in range(parameters["rounds"] + 1)}
    require(len(planned) == len(expected) and planned == {(row["row"], row["round"], row["kind"]) for row in expected},
            "expectedRuns omits or duplicates a configured row/round")
    if manifest["mode"] in {"formal", "m4-formal"}:
        require(all(parameters[key] == value for key, value in source.items() if key != "rows"), "formal global parameters differ from locked source")
        require(len(parameters["rows"]) == len(source["rows"]), "formal rows differ from locked source")
        for index, (fixed, original) in enumerate(zip(parameters["rows"], source["rows"])):
            derived = {**original, **{key: source[key] for key in ("capacity", "background_depth", "working_depth", "commands", "minimum_plan_seconds")},
                       "seed": source["seed"] + index * 100003}
            derived["commands"] = max(derived["commands"], int(derived["target_rate_per_sec"] * derived["minimum_plan_seconds"]) + 1)
            require(fixed == derived, "formal row differs from locked source")
        require(parameters["rates_locked"] and parameters["rounds"] >= 5 and parameters["commands"] >= 100000 and
                parameters["minimum_plan_seconds"] >= 10, "formal parameters are incomplete")
        if manifest["mode"] == "formal":
            require({row["id"] for row in parameters["rows"]} == {"mixed_4", "cancel_heavy_4", "sweep_4", "burst_4", "mixed_1", "mixed_4_near", "mixed_4_overload"},
                    "formal matrix is incomplete")
        else:
            fixed = {"capacity": 1000, "background_depth": 500, "working_depth": 64, "commands": 100000,
                     "rounds": 5, "minimum_plan_seconds": 10, "warmup_commands": 1000, "seed": 20261016}
            limits = {"max_connections": 64, "max_inflight": 16384, "max_send_bytes": 65536, "drain_ms": 5000,
                      "command_capacity": 1024, "event_capacity": 1024, "send_limit": 65536, "shutdown_ms": 5000,
                      "startup_seconds": 15, "setup_budget_seconds": 60, "timeout_slack_seconds": 10}
            require(all(parameters[key] == value for key, value in fixed.items()) and parameters["limits"] == limits,
                    "m4-formal parameters differ from the fixed M4 contract")
            require([(row["id"], row["scenario"], row["connections"], row["target_rate_per_sec"]) for row in parameters["rows"]] ==
                    [("mixed_1", "mixed", 1, 10000), ("mixed_4", "mixed", 4, 10000),
                     ("sweep_4", "sweep", 4, 10000), ("burst_4", "burst", 4, 2000)],
                    "m4-formal requires exactly the four fixed M4 rows and rates")
            burst = parameters["rows"][-1]
            require((burst["burst_period_ns"], burst["burst_window_ns"]) == (100000000, 10000000),
                    "m4-formal burst requires a 100 ms period and 10 ms window")
        require(manifest["environment"]["os"].lower().startswith("linux") and
                all(manifest["binaries"][key]["build_type"] == "Release" and not manifest["binaries"][key]["sanitized"] for key in ("server", "loadgen")),
                "formal evidence is not from Linux unsanitized Release")
    require(len({item["id"] for item in expected}) == len(expected), "duplicate run identity")
    declared = {local_file(directory, item["directory"]) for item in expected}
    require(len(declared) == len(expected), "duplicate run directory")
    present = {path.parent.resolve() for path in (directory / "runs").rglob("run.json")}
    require(present == declared, f"missing or orphaned run directories: missing={declared - present}, extra={present - declared}")
    results = [validate_run(local_file(directory, item["directory"]), item, parameters) for item in expected]
    sample_targets_met = all(row["normal_sample_target_met"] for row in results if row["kind"] == "measurement")
    report = {"schema_version": 1, "evidence_valid": True, "mode": manifest["mode"],
              "all_runs_succeeded": all(row["succeeded"] for row in results), "environment": manifest["environment"],
              "all_measured_sample_targets_met": sample_targets_met,
              "quantile_method": "nearest-rank, per run; completed samples only; no fixed clock-cost subtraction",
              "notes": "Service samples exclude setup. Failed drains have no successful service latency conclusion. "
                       "Per-command FNV digests cover requester business events; small full-event/routing tests provide separate coverage. "
                       "Written frames do not prove peer receipt. Shared CI smoke is not a formal performance result. "
                       "Client resources cover process lifetime including input preparation and setup, before evidence output; "
                       "null means an older loadgen did not record them.",
              "runs": results}
    (directory / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    lines = ["# Service measurements", "", f"Mode: {manifest['mode']}. All declared attempts are included.", "",
             "Nearest-rank p50/p99 in ns, one row per measured attempt. RTT includes only completed requests; losses remain visible.", "",
             "| Run | Complete / planned | Loss % | RTT p50 | RTT p99 | Service p99 | Send lag p99 | Complete/s | Status |",
             "|---|---:|---:|---:|---:|---:|---:|---:|---|"]
    for row in results:
        if row["kind"] != "measurement":
            continue
        service = row["service"]["p99_ns"] if row["service"] else "unverified drain"
        lines.append(f"| {row['id']} | {row['counts']['completed']} / {row['counts']['planned']} | "
                     f"{100 * row['unfinished_fraction']:.3f} | {row['rtt']['p50_ns']} | {row['rtt']['p99_ns']} | "
                     f"{service} | {row['send_lag']['p99_ns']} | {row['completed_per_second']:.1f} | "
                     f"{'completed' if row['succeeded'] else 'failed attempt'} |")
    lines.extend(["", report["notes"], "", "Full counts, resource measurements, clock probe, per-command-type distributions and environment are in report.json.", ""])
    (directory / "report.md").write_text("\n".join(lines))
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    try:
        report = summarize(args.directory)
        print(f"Validated {len(report['runs'])} declared attempts; all succeeded: {report['all_runs_succeeded']}")
    except (OSError, ValueError, KeyError, TypeError, IndexError) as error:
        raise SystemExit(f"summarize_service_bench: {error}")
