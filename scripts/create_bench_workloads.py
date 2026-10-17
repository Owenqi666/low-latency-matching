#!/usr/bin/env python3
"""Materialize versioned, deterministic M1 benchmark inputs using only stdlib."""
import argparse
import hashlib
import json
from collections import Counter, deque
from pathlib import Path

GENERATOR_VERSION = "m1-workloads-v1"
SCENARIOS = {"mixed", "cancel_heavy", "sweep", "clustered", "near_full_reuse"}
MASK64 = (1 << 64) - 1


def file_hashes(path):
    data = Path(path).read_bytes()
    value = 14695981039346656037
    for byte in data:
        value = ((value ^ byte) * 1099511628211) & MASK64
    return {"sha256": hashlib.sha256(data).hexdigest(), "fnv1a64": f"fnv1a64:{value:016x}"}


def write_json(path, data):
    Path(path).write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_manifest(path, commands=None, capacities=None):
    spec = json.loads(Path(path).read_text(encoding="utf-8"))
    if spec.get("schema_version") != 1 or spec.get("generator_version") != GENERATOR_VERSION:
        raise ValueError("unsupported workload manifest/generator version")
    if spec.get("scenario") not in SCENARIOS:
        raise ValueError("unknown workload scenario")
    if commands is not None:
        spec["commands"] = commands
    if capacities:
        spec["capacities"] = capacities
    for field in ("commands", "seed", "working_depth"):
        if type(spec.get(field)) is not int or spec[field] < (0 if field == "seed" else 1):
            raise ValueError(f"{field} must be a {'nonnegative' if field == 'seed' else 'positive'} integer")
    if not spec.get("capacities") or any(type(c) is not int or c < 4 for c in spec["capacities"]):
        raise ValueError("capacities must contain integers >= 4")
    if len(set(spec["capacities"])) != len(spec["capacities"]):
        raise ValueError("duplicate capacities")
    if spec["scenario"] == "near_full_reuse" and spec["working_depth"] != 16:
        raise ValueError("near_full_reuse uses exactly 16 cancel/reinsert pairs per cycle")
    if spec["scenario"] != "near_full_reuse" and any(spec["working_depth"] > c - c // 2 for c in spec["capacities"]):
        raise ValueError("working_depth exceeds capacity remaining after setup")
    if spec["scenario"] == "clustered" and spec["working_depth"] < 2:
        raise ValueError("clustered needs at least two working orders to sweep half")
    if spec["working_depth"] * 10 > 1000000 or 10015 + (spec["working_depth"] - 1) // 8 > 20000:
        raise ValueError("working_depth exceeds generated price/quantity bounds")
    return spec


class Sequence:
    """Specified integer generator; independent of Python's random implementation."""
    def __init__(self, seed):
        self.state = seed & MASK64
        self.order = 0
        self.request = 0

    def random(self, bound):
        self.state = (self.state + 0x9E3779B97F4A7C15) & MASK64
        value = self.state
        value = ((value ^ (value >> 30)) * 0xBF58476D1CE4E5B9) & MASK64
        value = ((value ^ (value >> 27)) * 0x94D049BB133111EB) & MASK64
        return (value ^ (value >> 31)) % bound

    def new_id(self):
        self.order += 1
        return self.order

    def command(self, kind, owner, order, *fields):
        self.request += 1
        return " ".join(map(str, (kind, owner, self.request, order, *fields)))


def generate(spec, capacity, directory):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    paths = {name: directory / filename for name, filename in
             (("config", "config.txt"), ("setup", "setup.trace"), ("input", "input.trace"))}
    if any(path.exists() for path in paths.values()):
        raise ValueError(f"refusing to replace existing workload files in {directory}")
    if spec["scenario"] == "near_full_reuse":
        return generate_near_full_reuse(spec, capacity, paths, directory)
    seq = Sequence(spec["seed"])
    scenario, depth = spec["scenario"], spec["working_depth"]
    initial = capacity // 2
    pool_size = min(depth, initial) if scenario == "cancel_heavy" else 0
    pool = []
    setup = []
    for index in range(initial - pool_size):
        # Sweep/clustered consume asks; their background is entirely bids.
        side = 0 if scenario in {"sweep", "clustered"} else index % 2
        price = 9000 + index % 16 if side == 0 else 11000 + index % 16
        setup.append(seq.command("L", 99, seq.new_id(), side, price, 100))
    for index in range(pool_size):
        order = seq.new_id()
        pool.append(order)
        setup.append(seq.command("L", 1, order, 0, 10000 + index % 16, 10))

    lines, count, rejected, live, cycle = [], 0, 0, initial, 0
    kinds, errors = Counter(), []
    minimum = maximum = initial
    while count < spec["commands"]:
        cycle += 1
        actions = []
        if scenario == "mixed":
            price = 10000 + seq.random(32)
            ask, limit, market, bid = [seq.new_id() for _ in range(4)]
            actions = [
                (seq.command("L", 1, ask, 1, price, 10), 1, False),
                (seq.command("L", 2, limit, 0, price, 3), 0, False),
                (seq.command("M", 2, market, 0, 2), 0, False),
                (seq.command("C", 1, ask), -1, False),
                (seq.command("L", 1, bid, 0, price, 7), 1, False),
                (seq.command("C", 1, bid), -1, False),
            ]
        elif scenario == "cancel_heavy":
            slot = seq.random(pool_size)
            replacement = seq.new_id()
            actions = [(seq.command("C", 1, pool[slot]), -1, False),
                       (seq.command("L", 1, replacement, 0, 10000 + seq.random(16), 10), 1, False)]
            pool[slot] = replacement
            if cycle % 20 == 0:
                actions.append((seq.command("C", 1, (1 << 63) + cycle), 0, True))
        else:
            orders = [seq.new_id() for _ in range(depth)]
            offset = seq.random(16)
            # Eight adjacent orders share each price, making FIFO visible.
            actions = [(seq.command("L", 1, order, 1, 10000 + offset + index // 8, 10), 1, False)
                       for index, order in enumerate(orders)]
            consumed = depth if scenario == "sweep" else depth // 2
            actions.append((seq.command("M", 2, seq.new_id(), 0, consumed * 10), -consumed, False))
            if scenario == "clustered":
                actions.extend((seq.command("C", 1, order), -1, False) for order in orders[consumed:])
        for line, delta, error in actions:
            if count == spec["commands"]:
                break
            if error:
                lines.append("# expected_rejection UnknownOrder; deliberate cancel-error subscenario")
                errors.append(count)
                rejected += 1
            lines.append(line)
            kinds[line[0]] += 1
            live += delta
            minimum, maximum = min(minimum, live), max(maximum, live)
            count += 1

    paths["config"].write_text(f"LLMATCH_CONFIG 1\n{capacity} 20000 1000000\n", encoding="utf-8")
    paths["setup"].write_text("LLMATCH_TRACE 1\n" + "\n".join(setup) + "\n", encoding="utf-8")
    paths["input"].write_text("LLMATCH_TRACE 1\n" + "\n".join(lines) + "\n", encoding="utf-8")
    metadata = {
        "schema_version": 1, "generator_version": GENERATOR_VERSION,
        "scenario": scenario, "seed": spec["seed"], "capacity": capacity,
        "commands": count, "working_depth": depth, "initial_live_orders": initial,
        "passive_background_orders": initial - pool_size, "initial_working_orders": pool_size,
        "planned_end_live_orders": live, "planned_min_live_orders": minimum,
        "planned_max_live_orders": maximum, "command_counts": dict(kinds),
        "expected_accepted": count - rejected, "expected_rejected": rejected,
        "expected_rejection_indices": errors,
        "price_range": [1, 20000], "background_bid_prices": [9000, 9015],
        "background_ask_prices": None if scenario in {"sweep", "clustered"} else [11000, 11015],
        "notes": "Synchronous core command pattern; no network arrival-rate, queuing or open-loop model. "
                 "Setup background orders remain passive; this is not a full-capacity pressure test. "
                 "The trace may stop partway through its final cycle; actual ending depth is reported.",
        "pattern": {
            "mixed": "One working order at a time: sell10, buy limit3, buy market2, cancel5, then bid7/cancel.",
            "cancel_heavy": "Cancel/replace within a working pool; every twentieth cycle adds an explicit UnknownOrder cancellation.",
            "sweep": "Buy markets sweep a working ask ladder. Each cycle has working_depth adds and one sweep; whole-stream throughput is not sweep-only throughput.",
            "clustered": "Insert an ask ladder, buy-market half its orders, then cancel the remainder. These are synchronous phases, not network bursts.",
        }[scenario],
        "files": {name: {"path": path.name, **file_hashes(path)} for name, path in paths.items()},
    }
    write_json(directory / "workload.json", metadata)
    return metadata


def generate_near_full_reuse(spec, capacity, paths, directory):
    """35-command cycles; only one deliberate full-book rejection per cycle."""
    seq = Sequence(spec["seed"])
    prices = {order: 8000 + ((order - 1) % 16) * 64 for order in range(1, capacity + 1)}
    owners = {order: 1 for order in prices}
    levels = {price: deque() for price in prices.values()}
    setup = []
    for order, price in prices.items():
        seq.new_id()
        setup.append(seq.command("L", 1, order, 0, price, 10))
        levels[price].append(order)
    lines, errors = [], []
    kinds = Counter()
    live = capacity
    minimum = capacity
    count = 0

    def emit(line, delta=0, rejected=False):
        nonlocal count, live, minimum
        if count == spec["commands"]:
            return False
        if rejected:
            lines.append("# expected_rejection CapacityExceeded; one full-book rejection per 35-command cycle")
            errors.append(count)
        lines.append(line)
        kinds[line[0]] += 1
        live += delta
        minimum = min(minimum, live)
        count += 1
        return True

    while count < spec["commands"]:
        emit(seq.command("L", 1, seq.new_id(), 0, 8000, 10), rejected=True)
        for _ in range(16):
            order = 1 + seq.random(capacity)
            if not emit(seq.command("C", owners[order], order), -1):
                break
            levels[prices[order]].remove(order)
            owners[order] = 3 - owners[order]
            if not emit(seq.command("L", owners[order], order, 0, prices[order], 10), 1):
                break
            levels[prices[order]].append(order)
        if count == spec["commands"]:
            break
        # All resting orders are bids; sell 10 consumes exactly the oldest order
        # at the best bid. Market/rejected IDs are fresh and always exceed C.
        order = levels[max(levels)].popleft()
        emit(seq.command("M", 3, seq.new_id(), 1, 10), -1)
        owners[order] = 3 - owners[order]
        if emit(seq.command("L", owners[order], order, 0, prices[order], 10), 1):
            levels[prices[order]].append(order)

    paths["config"].write_text(f"LLMATCH_CONFIG 1\n{capacity} 20000 1000000\n", encoding="utf-8")
    paths["setup"].write_text("LLMATCH_TRACE 1\n" + "\n".join(setup) + "\n", encoding="utf-8")
    paths["input"].write_text("LLMATCH_TRACE 1\n" + "\n".join(lines) + "\n", encoding="utf-8")
    metadata = {
        "schema_version": 1, "generator_version": GENERATOR_VERSION,
        "scenario": "near_full_reuse", "seed": spec["seed"], "capacity": capacity,
        "commands": count, "working_depth": spec["working_depth"], "initial_live_orders": capacity,
        "passive_background_orders": 0, "initial_working_orders": capacity,
        "planned_end_live_orders": live, "planned_min_live_orders": minimum,
        "planned_max_live_orders": capacity, "command_counts": dict(kinds),
        "expected_accepted": count - len(errors), "expected_rejected": len(errors),
        "expected_rejection_indices": errors, "expected_rejection_reason": 10,
        "price_range": [1, 20000], "background_bid_prices": None, "background_ask_prices": None,
        "notes": "Synchronous core commands; setup fills C orders. Active depth is C-1..C. "
                 "Trace stops after exactly commands, including a possible partial final cycle. "
                 "All successful reinsertions reuse a terminated OrderId and alternate its owner 1/2.",
        "pattern": "35-command cycle: one CapacityExceeded limit; 16 seeded cancel/reinsert pairs; "
                   "one sell-market/reinsert pair. Every order has quantity 10 and fixed bid price "
                   "8000 + ((OrderId-1) % 16) * 64. Market/rejected IDs increase from C+1. "
                   "Market quantity 10 consumes the FIFO head at the best bid; client 3 submits markets.",
        "files": {name: {"path": path.name, **file_hashes(path)} for name, path in paths.items()},
    }
    write_json(directory / "workload.json", metadata)
    return metadata


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--commands", type=int)
    parser.add_argument("--capacity", action="append", type=int)
    args = parser.parse_args()
    spec = load_manifest(args.manifest, args.commands, args.capacity)
    for capacity in spec["capacities"]:
        directory = args.output_dir / spec["scenario"] / f"capacity_{capacity}"
        metadata = generate(spec, capacity, directory)
        print(f"{directory}: {metadata['commands']} commands; setup depth {metadata['initial_live_orders']}")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError) as error:
        raise SystemExit(f"create_bench_workloads: {error}")
