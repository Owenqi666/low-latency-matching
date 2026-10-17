#!/usr/bin/env python3
"""Independently check retained ITCH matrix evidence and summarize every round."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import statistics

SCENARIOS = ('mixed', 'cancel_replace', 'multilevel')
MODES = ('decode', 'rebuild')
SEEDS = {name: 0x495443480501 + index for index, name in enumerate(SCENARIOS)}
TOOLS = ('scripts/create_itch_workloads.py', 'scripts/verify_itch.py',
         'reference/itch_reference.py', 'scripts/run_itch_bench.py',
         'scripts/summarize_itch_bench.py')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read(path):
    return json.loads(Path(path).read_text())


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2) + '\n')


def sha256(path):
    result = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            result.update(block)
    return result.hexdigest()


def execution_plan(spec):
    return [dict(scenario=scenario, mode=mode, kind='warmup' if round_number == 0 else 'measurement',
                 round=round_number, directory=f'runs/{scenario}/{mode}/' +
                 ('warmup' if round_number == 0 else f'round_{round_number}'))
            for scenario in spec['scenarios'] for mode in MODES
            for round_number in range(spec['rounds'] + 1)]


def final_state_checksum(directory):
    """Mirror only the benchmark's documented consumption, using verified CSV state."""
    value = 14695981039346656037
    def mix(number):
        nonlocal value
        value = ((value ^ number) * 1099511628211) & ((1 << 64) - 1)
    with (directory / 'orders.csv').open(newline='') as stream:
        orders = list(csv.DictReader(stream))
    with (directory / 'levels.csv').open(newline='') as stream:
        levels = list(csv.DictReader(stream))
    mix(len(orders))
    for order in orders:
        for number in (int(order['reference']), ord(order['side']), int(order['price']), int(order['shares'])):
            mix(number)
        for byte in order['attribution'].encode('ascii'):
            mix(byte)
        mix(0)
    mix(len(levels))
    for level in levels:
        for number in (ord(level['side']), int(level['price']), int(level['shares']), int(level['orders'])):
            mix(number)
    return f'{value:016x}'


def summarize(directory):
    directory = Path(directory)
    # A failed recheck must not leave an old success report beside damaged evidence.
    for name in ('report.json', 'report.md'):
        (directory / name).unlink(missing_ok=True)
    manifest = read(directory / 'matrix-manifest.json')
    require(manifest['schema_version'] == 1 and manifest['status'] == 'completed', 'matrix did not complete')
    spec = manifest['specification']
    require(manifest['mode'] in ('formal', 'smoke'), 'unknown matrix mode')
    require(spec['messages'] >= 10 and spec['rounds'] > 0 and spec['traversals'] == 1 and spec['warmups'] == 1,
            'invalid matrix dimensions')
    require(spec['symbol'] == 'TEST' and spec['max_orders'] == 1_000_000, 'changed target/capacity contract')
    require(spec['scenarios'] and len(set(spec['scenarios'])) == len(spec['scenarios']) and
            set(spec['scenarios']) <= set(SCENARIOS), 'unknown or duplicate scenario')
    if manifest['mode'] == 'formal':
        require(spec['messages'] == 1_000_000 and spec['rounds'] == 5 and tuple(spec['scenarios']) == SCENARIOS,
                'formal matrix must retain three million-message inputs and five rounds')
        require(manifest['environment']['system'] == 'Linux' and not manifest['build']['source']['dirty'],
                'formal measurement requires clean Linux source')
    plan = execution_plan(spec)
    require(manifest['execution_plan'] == plan and len(manifest['executed']) == len(plan), 'missing or changed execution plan')
    require(set(manifest['tools']) == set(TOOLS), 'missing tool identity')
    for name, wanted in manifest['tools'].items():
        require(sha256(directory / 'tool-evidence' / name) == wanted, f'tool identity mismatch: {name}')
    build = manifest['build']
    require(build['source']['directory'] == build['source']['cmake_home_directory'], 'build source differs from declared source')
    for name, wanted in build['artifacts'].items():
        require(sha256(directory / 'build-evidence' / name) == wanted, f'build identity mismatch: {name}')
    require(read(directory / 'build-evidence/source.json') == build['source'], 'source record mismatch')
    cache = {line.split(':', 1)[0]: line.split('=', 1)[1]
             for line in (directory / 'build-evidence/CMakeCache.txt').read_text().splitlines()
             if line and not line.startswith(('#', '//')) and '=' in line}
    require(cache['CMAKE_BUILD_TYPE'] == 'Release' and cache['LLMATCH_SANITIZERS'] == 'OFF',
            'timings require an unsanitized Release build')

    verified = {}
    require(set(manifest['inputs']) == set(manifest['verification']) == set(spec['scenarios']), 'missing input or reference verification')
    for scenario in spec['scenarios']:
        files = directory / 'inputs' / scenario
        identity = manifest['inputs'][scenario]
        require(sha256(files / 'input.bin') == identity['sha256'] and (files / 'input.bin').stat().st_size == identity['bytes'],
                f'input identity mismatch: {scenario}')
        require(sha256(files / 'workload.json') == identity['metadata_sha256'], 'workload metadata identity mismatch')
        metadata = read(files / 'workload.json')
        require(metadata['scenario'] == scenario and metadata['messages'] == spec['messages'] and metadata['seed'] == SEEDS[scenario],
                'workload parameters differ from frozen specification')
        require(metadata['generator_sha256'] == manifest['tools']['scripts/create_itch_workloads.py'], 'generator identity mismatch')
        folder = directory / 'verification' / scenario
        require(sha256(folder / 'verification.json') == manifest['verification'][scenario]['sha256'], 'reference receipt identity mismatch')
        receipt = read(folder / 'verification.json')
        require(receipt['status'] == 'passed' and receipt['exit_code'] == 0 and receipt['output_files_verified'], 'reference verification failed')
        require(receipt['input']['sha256'] == identity['sha256'] and receipt['input']['bytes'] == identity['bytes'], 'reference checked different input')
        require(receipt['binary_sha256'] == build['artifacts']['itch_replay'], 'reference replay binary mismatch')
        require(all(receipt['tool_hashes'][name] == manifest['tools'][name] for name in
                    ('scripts/verify_itch.py', 'reference/itch_reference.py')), 'reference tool identity mismatch')
        for name, wanted in receipt['outputs'].items():
            require(sha256(folder / 'replay' / name) == wanted, 'verified state output identity mismatch')
        summary = receipt['summary']
        require(read(folder / 'replay/summary.json') == summary, 'verified replay summary mismatch')
        require(summary['messages'] == metadata['messages'] and summary['updates'] == metadata['target_updates'] == receipt['compared_updates'],
                'generator/reference counts differ')
        require(summary['counts_by_type'] == metadata['counts_by_type'] and summary['active_orders'] == metadata['final_target_orders'],
                'generator/reference state differs')
        require(summary['session_complete'] and not receipt['prefix_allowed'], 'synthetic matrix needs complete sessions')
        verified[scenario] = dict(summary=summary, state_checksum=final_state_checksum(folder / 'replay'),
                                  levels=receipt['final_levels'])

    runs, checksums = [], {}
    for planned, entry in zip(plan, manifest['executed']):
        require(all(entry[key] == value for key, value in planned.items()) and entry['status'] == 'passed' and entry['exit_code'] == 0,
                'missing or failed benchmark round')
        folder = directory / planned['directory']
        require(sha256(folder / 'result.json') == entry['result_sha256'], 'benchmark result identity mismatch')
        require(sha256(folder / 'benchmark.log') == entry['log_sha256'], 'benchmark log identity mismatch')
        sample, log = read(folder / 'result.json'), read(folder / 'benchmark.log')
        reference = verified[planned['scenario']]
        summary = reference['summary']
        require(sample['status'] == log['status'] == 'passed' and sample['mode'] == planned['mode'], 'benchmark mode/result mismatch')
        require(sample['traversals'] == 1 and not sample['prefix_allowed'] and sample['symbol'] == spec['symbol'], 'changed benchmark interval')
        require(all(sample[left] == summary[right] for left, right in
                    [('bytes', 'bytes'), ('messages', 'messages'), ('target_messages', 'target_messages'),
                     ('target_updates', 'updates'), ('input_fnv1a64', 'input_fnv1a64')]), 'benchmark/reference counts or bytes mismatch')
        require(sample['elapsed_ns'] > 0 and sample['clock']['steady'], 'invalid timing clock/interval')
        require(all(sample[key] >= 0 for key in ('cpu_user_us', 'cpu_system_us', 'input_read_ns', 'construction_ns', 'finish_ns', 'final_snapshot_ns'))
                and log['output_write_ns'] >= 0, 'negative resource or excluded duration')
        require(sample['input_storage_bytes'] >= sample['bytes'] and sample['peak_rss_after_timing_bytes'] > 0, 'invalid memory observation')
        previous = checksums.setdefault(planned['scenario'], sample['decoded_checksum'])
        require(sample['decoded_checksum'] == previous, 'decoded consumption differs across intervals')
        if planned['mode'] == 'rebuild':
            require(sample['active_orders'] == summary['active_orders'] and sample['levels'] == reference['levels'] and
                    sample['state_checksum'] == reference['state_checksum'], 'final reconstructed state differs from reference')
        else:
            require(sample['active_orders'] is None and sample['levels'] is None and sample['state_checksum'] is None, 'decode mode must not claim rebuilt state')
        runs.append({**planned, **sample, 'output_write_ns': log['output_write_ns'],
                     'messages_per_second': sample['messages'] * 1e9 / sample['elapsed_ns'],
                     'target_updates_per_second': sample['target_updates'] * 1e9 / sample['elapsed_ns'],
                     'bytes_per_second': sample['bytes'] * 1e9 / sample['elapsed_ns']})
    rows = []
    for scenario in spec['scenarios']:
        for mode in MODES:
            rounds = [run for run in runs if run['scenario'] == scenario and run['mode'] == mode and run['kind'] == 'measurement']
            row = dict(scenario=scenario, mode=mode, rounds=rounds)
            for key in ('elapsed_ns', 'messages_per_second', 'target_updates_per_second', 'bytes_per_second'):
                values = [run[key] for run in rounds]
                row[key] = dict(median=statistics.median(values), minimum=min(values), maximum=max(values))
            rows.append(row)
    report = dict(schema_version=1, validation='passed', mode=manifest['mode'],
                  measured_intervals=len(spec['scenarios']) * 2 * spec['rounds'], warmup_intervals=len(spec['scenarios']) * 2,
                  traversals_per_interval=1, source=build['source'], environment=manifest['environment'], rows=rows,
                  warmups=[run for run in runs if run['kind'] == 'warmup'],
                  scope='Whole in-memory BinaryFILE framing/decoding includes reader byte FNV and decoded-field consumption. Rebuild adds filtering and state updates. Reference, input I/O, construction, final snapshot, EOF validation and output I/O are excluded and separately recorded. Decode target update rate counts input messages, not applied updates. CPU deltas cover the loop; RSS is whole-process high-water including input/book/harness, not isolated book bytes. No per-message p99 or speedup claim; subtracting modes does not isolate reconstruction cost.')
    write(directory / 'report.json', report)
    lines = ['# ITCH benchmark', '', f"Mode: {manifest['mode']}; {report['measured_intervals']} measured intervals, {report['warmup_intervals']} independent warmups; one traversal per interval.", '',
             '| Scenario | Mode | messages/s median [min, max] | target updates/s median | bytes/s median |',
             '| --- | --- | --- | --- | --- |']
    for row in rows:
        rate = row['messages_per_second']
        lines.append(f"| {row['scenario']} | {row['mode']} | {rate['median']:.2f} [{rate['minimum']:.2f}, {rate['maximum']:.2f}] | {row['target_updates_per_second']['median']:.2f} | {row['bytes_per_second']['median']:.2f} |")
    lines += ['', report['scope'], '', 'Every round, excluded duration, clock observation and CPU/RSS value is retained in report.json and its original result.json. Shared host load/frequency/affinity are not controlled by this runner.', '']
    (directory / 'report.md').write_text('\n'.join(lines))
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    args = parser.parse_args()
    try:
        result = summarize(args.directory)
        print(json.dumps({key: result[key] for key in ('validation', 'mode', 'measured_intervals', 'warmup_intervals')}))
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise SystemExit(f'summarize_itch_bench: {error}')
