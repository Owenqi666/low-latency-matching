#!/usr/bin/env python3
"""Generate finite, deterministic service commands and open-loop schedules."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re

from create_bench_workloads import Sequence


GENERATOR_VERSION = "m2-service-workloads-v1"
SCENARIOS = {"mixed", "cancel_heavy", "sweep", "burst"}


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_manifest(path, rows=None, commands=None, rounds=None, rate=None):
    spec = json.loads(Path(path).read_text(encoding="utf-8"))
    if spec.get("schema_version") != 1 or spec.get("generator_version") != GENERATOR_VERSION:
        raise ValueError("unsupported service manifest/generator version")
    if spec.get("mode") not in {"smoke", "calibration", "formal"}:
        raise ValueError("mode must be smoke, calibration, or formal")
    if spec["mode"] == "formal":
        if any(value is not None for value in (rows, commands, rounds, rate)):
            raise ValueError("formal parameters must be fixed in the manifest, without CLI overrides")
        if not spec.get("rates_locked"):
            raise ValueError("formal rates are not locked; calibrate and save a new fixed manifest first")
        if spec["rounds"] < 5 or spec["commands"] < 100000 or spec["minimum_plan_seconds"] < 10:
            raise ValueError("formal runs require >=5 rounds, >=100000 planned commands, and >=10 seconds")
    if commands is not None:
        spec["commands"] = commands
    if rounds is not None:
        spec["rounds"] = rounds
    for field in ("capacity", "background_depth", "working_depth", "commands", "rounds", "warmup_commands"):
        if type(spec.get(field)) is not int or spec[field] < 1:
            raise ValueError(f"{field} must be a positive integer")
    if type(spec.get("seed")) is not int or spec["seed"] < 0:
        raise ValueError("seed must be a nonnegative integer")
    if type(spec["minimum_plan_seconds"]) is not int or spec["minimum_plan_seconds"] < 0:
        raise ValueError("minimum_plan_seconds must be a nonnegative integer")
    for field in ("max_connections", "max_inflight", "max_send_bytes", "drain_ms", "command_capacity",
                  "event_capacity", "send_limit", "shutdown_ms", "startup_seconds", "setup_budget_seconds", "timeout_slack_seconds"):
        if type(spec["limits"].get(field)) is not int or spec["limits"][field] < 1:
            raise ValueError(f"limits.{field} must be a positive integer")
    if not 0 < spec["background_depth"] < spec["capacity"]:
        raise ValueError("background depth must leave working capacity")
    ids = [row["id"] for row in spec["rows"]]
    if not ids or len(ids) != len(set(ids)) or any(not re.fullmatch(r"[a-z][a-z0-9_]*", name) for name in ids):
        raise ValueError("row ids must be unique lowercase path-safe names")
    if rows and not set(rows) <= set(ids):
        raise ValueError("unknown selected row")
    selected = []
    for index, source in enumerate(spec["rows"]):
        row = dict(source)
        if rows and row["id"] not in rows:
            continue
        if rate is not None:
            row["target_rate_per_sec"] = rate
        if row["scenario"] not in SCENARIOS:
            raise ValueError("unknown service scenario")
        if type(row["connections"]) is not int or not 1 <= row["connections"] <= spec["limits"]["max_connections"]:
            raise ValueError("connections outside server connection limit")
        if type(row.get("target_rate_per_sec")) is not int or row["target_rate_per_sec"] < 1:
            raise ValueError(f"{row['id']}: target rate must be fixed to a positive integer")
        row.update({key: spec[key] for key in ("capacity", "background_depth", "working_depth", "commands", "minimum_plan_seconds")})
        row["seed"] = spec["seed"] + index * 100003
        row["commands"] = max(row["commands"], int(row["target_rate_per_sec"] * row["minimum_plan_seconds"]) + 1)
        if row["scenario"] == "sweep":
            if row["working_depth"] < 64:
                raise ValueError("sweep requires at least 64 makers per group")
            bound = row["connections"] * row["working_depth"]
        elif row["scenario"] == "cancel_heavy":
            bound = 0
        else:
            # At most ten units of outstanding ask volume and one bid per
            # connection; partial fills may leave more than one ask order.
            bound = 11 * row["connections"]
        if row["background_depth"] + bound > row["capacity"]:
            raise ValueError(f"{row['id']}: configured capacity is too small for this workload")
        if row["working_depth"] * 10 > 1000000 or 10015 + (row["working_depth"] - 1) // 8 > 20000:
            raise ValueError("working depth exceeds generated price/quantity domains")
        if row["scenario"] == "burst" and not 0 < row["burst_window_ns"] < row["burst_period_ns"]:
            raise ValueError("burst window must be positive and shorter than its period")
        selected.append(row)
    by_id = {row["id"]: row for row in selected}
    if "mixed_1" in by_id and "mixed_4" in by_id and by_id["mixed_1"]["target_rate_per_sec"] != by_id["mixed_4"]["target_rate_per_sec"]:
        raise ValueError("mixed 1-client and 4-client rows require the same total target rate")
    if spec["mode"] == "formal":
        required = {"mixed_4": ("mixed", 4), "cancel_heavy_4": ("cancel_heavy", 4), "sweep_4": ("sweep", 4),
                    "burst_4": ("burst", 4), "mixed_1": ("mixed", 1), "mixed_4_near": ("mixed", 4), "mixed_4_overload": ("mixed", 4)}
        if any(name not in by_id or (by_id[name]["scenario"], by_id[name]["connections"]) != shape for name, shape in required.items()):
            raise ValueError("formal manifest is missing a required matrix row")
    spec["rows"] = selected
    return spec


def generate(row, directory, commands=None):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=False)
    count = row["commands"] if commands is None else commands
    sequence = Sequence(row["seed"])
    scenario, connections = row["scenario"], row["connections"]
    initial, depth = row["background_depth"], row["working_depth"]
    pool_size = min(initial, depth) if scenario == "cancel_heavy" else 0
    setup, pool = [], []
    for index in range(initial - pool_size):
        owner = 1 + index % connections
        side = 0 if scenario == "sweep" else index % 2
        price = 9000 + index % 16 if side == 0 else 11000 + index % 16
        setup.append(sequence.command("L", owner, sequence.new_id(), side, price, 100))
    for index in range(pool_size):
        owner, order = 1 + index % connections, sequence.new_id()
        pool.append((owner, order))
        setup.append(sequence.command("L", owner, order, 0, 9500 + index % 16, 10))

    lines, deliberate_errors, cycle = [], [], 0
    while len(lines) < count:
        owner = 1 + cycle % connections
        cycle += 1
        if scenario in {"mixed", "burst"}:
            ask, limit, market, bid = [sequence.new_id() for _ in range(4)]
            actions = [
                sequence.command("L", owner, ask, 1, 10000 + sequence.random(32), 10),
                sequence.command("L", owner, limit, 0, 10064, 3),
                sequence.command("M", owner, market, 0, 7),
                sequence.command("L", owner, bid, 0, 9500 + sequence.random(16), 7),
                sequence.command("C", owner, bid),
            ]
        elif scenario == "cancel_heavy":
            slot = sequence.random(pool_size)
            owner, old = pool[slot]
            replacement = sequence.new_id()
            pool[slot] = (owner, replacement)
            actions = [sequence.command("C", owner, old),
                       sequence.command("L", owner, replacement, 0, 9500 + sequence.random(16), 10)]
            if cycle % 20 == 0:
                if len(lines) + len(actions) < count:
                    deliberate_errors.append(len(lines) + len(actions))
                actions.append(sequence.command("C", owner, (1 << 63) + cycle))
        else:
            offset = sequence.random(16)
            actions = [sequence.command("L", owner, sequence.new_id(), 1, 10000 + offset + index // 8, 10)
                       for index in range(depth)]
            actions.append(sequence.command("M", owner, sequence.new_id(), 0, depth * 10))
        lines.extend(actions[:count - len(lines)])

    offsets = []
    for index in range(count):
        uniform = index * 1000000000 // row["target_rate_per_sec"]
        if scenario == "burst":
            period, window = row["burst_period_ns"], row["burst_window_ns"]
            uniform = uniform // period * period + uniform % period * window // period
        offsets.append(uniform)
    paths = {"config": directory / "engine.config", "setup": directory / "setup.trace",
             "input": directory / "input.trace", "schedule": directory / "schedule.txt"}
    paths["config"].write_text(f"LLMATCH_CONFIG 1\n{row['capacity']} 20000 1000000\n")
    paths["setup"].write_text("LLMATCH_TRACE 1\n" + "\n".join(setup) + "\n")
    paths["input"].write_text("LLMATCH_TRACE 1\n" + "\n".join(lines) + "\n")
    paths["schedule"].write_text("\n".join(map(str, offsets)) + "\n")
    kinds = Counter(line.split()[0] for line in lines)
    metadata = {
        "schema_version": 1, "generator_version": GENERATOR_VERSION, "row": row,
        "commands": count, "setup_commands": len(setup), "initial_live_orders": initial,
        "passive_background_orders": initial - pool_size, "initial_working_orders": pool_size,
        "command_counts": dict(kinds), "command_ratios": {kind: value / count for kind, value in kinds.items()},
        "input_limit_price_counts": dict(Counter(line.split()[5] for line in lines if line.startswith("L "))),
        "deliberate_unknown_cancel_indices": deliberate_errors,
        "expected_business_rejections_when_all_commands_arrive": len(deliberate_errors),
        "schedule_last_offset_ns": offsets[-1], "schedule_plan_window_ns": (count * 1000000000 + row["target_rate_per_sec"] - 1) // row["target_rate_per_sec"],
        "arrival_pattern": "periodic compressed send windows" if scenario == "burst" else "uniform offsets",
        "price_domain": [1, 20000], "quantity_domain": [1, 1000000],
        "background_bid_prices": [9000, 9015], "background_ask_prices": None if scenario == "sweep" else [11000, 11015],
        "working_ask_prices": [10000, 10015 + (depth - 1) // 8] if scenario == "sweep" else [10000, 10031],
        "working_bid_prices": [9500, 9515],
        "notes": "Setup is outside measurement. Dependencies stay within each connection's ordered stream. "
                 "Cross-connection maker order may vary; verify each actual admitted trace independently. "
                 "Background depth is fixed and mostly passive, not a full-book stress claim. "
                 "Sweep has 64 or more adds per market sweep; whole-stream throughput is not sweep-only throughput. "
                 "Actual depths and final state must come from server/reference evidence. Request loss may change business outcomes.",
        "files": {name: {"path": path.name, "sha256": sha256(path)} for name, path in paths.items()},
    }
    write_json(directory / "workload.json", metadata)
    return metadata


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--row", action="append")
    parser.add_argument("--commands", type=int)
    parser.add_argument("--rate", type=int)
    args = parser.parse_args()
    spec = load_manifest(args.manifest, args.row, args.commands, rate=args.rate)
    for row in spec["rows"]:
        result = generate(row, args.output_dir / row["id"])
        print(f"{row['id']}: {result['commands']} commands, {result['setup_commands']} setup, {row['connections']} connections")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise SystemExit(f"create_service_workloads: {error}")
