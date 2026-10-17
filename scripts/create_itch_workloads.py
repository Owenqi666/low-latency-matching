#!/usr/bin/env python3
"""Create deterministic, legal synthetic ITCH BinaryFILE inputs (not market data)."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

VERSION = 1
MASK64 = (1 << 64) - 1
SCENARIOS = {
    'mixed': (0x495443480501, (30, 20, 20, 10, 20), 32),
    'cancel_replace': (0x495443480502, (15, 10, 25, 15, 35), 16),
    'multilevel': (0x495443480503, (35, 15, 20, 10, 20), 256),
    'long_verify': (0x495443480504, (30, 20, 20, 10, 20), 32),
}


class Random:
    def __init__(self, seed):
        self.state = seed & MASK64

    def pick(self, bound):
        self.state = (self.state + 0x9E3779B97F4A7C15) & MASK64
        value = self.state
        value = ((value ^ (value >> 30)) * 0xBF58476D1CE4E5B9) & MASK64
        value = ((value ^ (value >> 27)) * 0x94D049BB133111EB) & MASK64
        return (value ^ (value >> 31)) % bound


def u(value, size):
    return value.to_bytes(size, 'big')


def header(kind, locate, index):
    # Repeated timestamps deliberately exercise file-order rather than time sorting.
    return kind.encode() + u(locate, 2) + u(index % 65536, 2) + u(index // 3, 6)


def directory(symbol, locate, index):
    # Stock, market category, financial status, round lot, round-lots-only,
    # issue classification/subtype, authenticity, SSR, IPO, LULD, ETP, factor, inverse.
    return header('R', locate, index) + symbol.encode().ljust(8, b' ') + b'QN' + u(100, 4) + b'NC  PNN1N' + u(0, 4) + b'N'


class Population:
    def __init__(self, symbol, locate, cap, levels):
        self.symbol, self.locate, self.cap, self.levels = symbol, locate, cap, levels
        self.orders, self.refs, self.positions = {}, [], {}
        self.next_ref = locate << 48
        self.peak = 0

    def remove(self, ref):
        position = self.positions.pop(ref)
        last = self.refs.pop()
        if position < len(self.refs):
            self.refs[position] = last
            self.positions[last] = position
        del self.orders[ref]

    def insert(self, ref, order):
        self.positions[ref] = len(self.refs)
        self.refs.append(ref)
        self.orders[ref] = order
        self.peak = max(self.peak, len(self.refs))

    def fresh_ref(self):
        self.next_ref += 1
        return self.next_ref

    def update(self, choice, rng, index, forced_ref=None):
        if not self.refs:
            choice = 'A'
        elif choice in 'AF' and len(self.refs) == self.cap:
            choice = 'D'
        if forced_ref is not None:
            ref, choice = forced_ref, 'D'
        elif self.refs:
            ref = self.refs[rng.pick(len(self.refs))]
        else:
            ref = None
        price = 1_000_000 + (rng.pick(self.levels) - self.levels // 2) * 100
        shares = 1 + rng.pick(1000)
        if choice in 'AF':
            ref = self.fresh_ref()
            side = 'BS'[rng.pick(2)]
            body = u(ref, 8) + side.encode() + u(shares, 4) + self.symbol.encode().ljust(8, b' ') + u(price, 4)
            if choice == 'F':
                body += b'SYN1'
            self.insert(ref, dict(side=side, price=price, shares=shares))
        elif choice == 'U':
            old, new = self.orders[ref], self.fresh_ref()
            body = u(ref, 8) + u(new, 8) + u(shares, 4) + u(price, 4)
            replacement = dict(old, price=price, shares=shares)
            self.remove(ref)
            self.insert(new, replacement)
        elif choice == 'D':
            body = u(ref, 8)
            self.remove(ref)
        else:
            order = self.orders[ref]
            amount = order['shares'] if rng.pick(4) == 0 else 1 + rng.pick(order['shares'])
            body = u(ref, 8) + u(amount, 4)
            if choice in 'EC':
                body += u(index, 8)
            if choice == 'C':
                body += (b'Y' if rng.pick(2) == 0 else b'N') + u(price, 4)
            order['shares'] -= amount
            if not order['shares']:
                self.remove(ref)
        return header(choice, self.locate, index) + body


def create(scenario, messages, output_dir, seed=None):
    default_seed, weights, levels = SCENARIOS[scenario]
    seed = default_seed if seed is None else seed
    if messages < 10:
        raise ValueError('at least 10 messages are required')
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=False)
    rng = Random(seed)
    target = Population('TEST', 1, 1000, levels)
    other = Population('OTHER', 2, 128, levels)
    counts, target_counts = Counter(), Counter()
    digest = hashlib.sha256()
    best_deletions = 0
    pending_best = []
    target_updates = 0
    cumulative = []
    total = 0
    for weight in weights:
        total += weight
        cumulative.append(total)
    raw = output_dir / 'input.bin'
    with raw.open('xb') as stream:
        def emit(payload):
            frame = u(len(payload), 2) + payload
            stream.write(frame)
            digest.update(frame)
            kind = chr(payload[0])
            counts[kind] += 1
            if int.from_bytes(payload[1:3], 'big') == 1:
                target_counts[kind] += 1
        emit(header('S', 0, 1) + b'O')
        emit(directory('TEST', 1, 2))
        emit(directory('OTHER', 2, 3))
        for index in range(4, messages):
            slot = (index - 4) % 100
            if slot >= 90:
                kind, length = [('P', 44), ('Q', 40), ('B', 19), ('H', 25)][(index - 4) // 100 % 4]
                emit(header(kind, 1, index) + bytes(length - 11))
                continue
            population = target if slot < 80 else other
            draw = rng.pick(100)
            category = next(i for i, upper in enumerate(cumulative) if draw < upper)
            kind = ['AF'[rng.pick(2)], 'EC'[rng.pick(2)], 'X', 'D', 'U'][category]
            forced = None
            if population is target:
                if scenario == 'multilevel' and target_updates and target_updates % 2000 == 0 and not pending_best:
                    side = 'BS'[(target_updates // 2000) % 2]
                    orders = [(r, o) for r, o in target.orders.items() if o['side'] == side]
                    if orders:
                        best = (max if side == 'B' else min)(o['price'] for _, o in orders)
                        pending_best = sorted(r for r, o in orders if o['price'] == best)
                if pending_best:
                    forced = pending_best.pop(0)
                    if not pending_best:
                        best_deletions += 1
                target_updates += 1
            emit(population.update(kind, rng, index, forced))
        emit(header('S', 0, messages) + b'C')
        stream.write(b'\0\0')
        digest.update(b'\0\0')
    manifest = dict(schema_version=1, generator_version=VERSION, scenario=scenario, seed=seed,
                    synthetic=True, symbol='TEST', other_symbol='OTHER', messages=messages,
                    requested_lifecycle_weights=dict(zip(('add', 'execute', 'cancel', 'delete', 'replace'), weights)),
                    schedule='After S/O and two directories: each 100 slots has 80 target, 10 non-target, 10 known ignored; final S/C plus zero marker.',
                    target_capacity=1000, other_capacity=128, price_levels_per_side=levels,
                    price_center=1_000_000, price_tick=100, shares_min=1, shares_max=1000,
                    counts_by_type=dict(counts), target_counts_by_type=dict(target_counts),
                    target_updates=target_updates, peak_target_orders=target.peak,
                    final_target_orders=len(target.orders), peak_other_orders=other.peak,
                    deterministic_best_level_disappearances=best_deletions,
                    legalisation='Empty book forces add; full capacity converts add to delete; multilevel drains one entire current best level every 2000 target updates.',
                    input=dict(path='input.bin', bytes=raw.stat().st_size, sha256=digest.hexdigest()),
                    generator_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    (output_dir / 'workload.json').write_text(json.dumps(manifest, indent=2) + '\n')
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scenario', choices=SCENARIOS, required=True)
    parser.add_argument('--messages', type=int, default=1_000_000)
    parser.add_argument('--seed', type=lambda value: int(value, 0))
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(create(args.scenario, args.messages, args.output_dir, args.seed), indent=2))


if __name__ == '__main__':
    main()
