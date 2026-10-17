#!/usr/bin/env python3
"""Verify three synthetic streams, then run one warmup and fixed ITCH intervals."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import shlex
import shutil
import subprocess
import sys
import time

from summarize_itch_bench import SCENARIOS, TOOLS, execution_plan, read, require, sha256, summarize, write


def now():
    return datetime.now(timezone.utc).isoformat()


def source_record(source, binary, replay):
    cache = {}
    for line in (binary.parent / 'CMakeCache.txt').read_text().splitlines():
        if line and not line.startswith(('#', '//')) and '=' in line:
            key, value = line.split('=', 1)
            cache[key.split(':', 1)[0]] = value
    require(Path(cache['CMAKE_HOME_DIRECTORY']).resolve() == source, 'build source differs from declared source')
    require(cache['CMAKE_BUILD_TYPE'] == 'Release' and cache['LLMATCH_SANITIZERS'] == 'OFF', 'requires unsanitized Release build')
    require(binary.parent == replay.parent, 'benchmark and replay must share the declared build')
    commands = read(binary.parent / 'compile_commands.json')
    flags = {}
    for command in commands:
        file = Path(command['file'])
        if file.name in ('itch.cpp', 'itch_main.cpp', 'itch_bench.cpp'):
            require(file.resolve().is_relative_to(source), 'ITCH compile input is outside the declared source')
            arguments = command.get('arguments') or shlex.split(command['command'])
            flags[file.name] = [arg for arg in arguments if arg.startswith(('-O', '-D', '-g', '-std=', '-march=', '-mcpu=', '-mtune=', '-flto', '-fsanitize'))]
    require(set(flags) == {'itch.cpp', 'itch_main.cpp', 'itch_bench.cpp'}, 'missing ITCH compile commands')
    require(not any('sanitize' in flag for values in flags.values() for flag in values), 'sanitizer flags in benchmark build')
    files = [source / 'CMakeLists.txt', source / 'CMakePresets.json']
    for folder in ('src', 'include', 'apps', 'bench', 'cmake'):
        files.extend(path for path in (source / folder).rglob('*') if path.is_file())
    git = lambda *args: subprocess.check_output(['git', *args], cwd=source, text=True).strip()
    status = git('status', '--porcelain')
    record = dict(directory=str(source), cmake_home_directory=str(Path(cache['CMAKE_HOME_DIRECTORY']).resolve()),
                  commit=git('rev-parse', 'HEAD'), dirty=bool(status), git_status=status,
                  build_input_sha256={str(path.relative_to(source)): sha256(path) for path in sorted(files)},
                  binary_sha256=sha256(binary), replay_sha256=sha256(replay),
                  cmake_cache_sha256=sha256(binary.parent / 'CMakeCache.txt'),
                  compile_commands_sha256=sha256(binary.parent / 'compile_commands.json'))
    return record, cache, flags


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary', type=Path, required=True)
    parser.add_argument('--replay', type=Path, required=True)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--messages', type=int, help='Override labels the run smoke')
    parser.add_argument('--rounds', type=int, help='Override labels the run smoke')
    parser.add_argument('--scenario', choices=SCENARIOS, action='append', help='Subset labels the run smoke')
    args = parser.parse_args()
    source, binary, replay = args.source.resolve(), args.binary.resolve(), args.replay.resolve()
    repository = Path(__file__).resolve().parents[1]
    spec = dict(messages=args.messages if args.messages is not None else 1_000_000,
                rounds=args.rounds if args.rounds is not None else 5,
                scenarios=args.scenario or list(SCENARIOS), symbol='TEST', max_orders=1_000_000,
                warmups=1, traversals=1)
    require(spec['messages'] >= 10 and spec['rounds'] > 0 and len(set(spec['scenarios'])) == len(spec['scenarios']), 'invalid smoke dimensions')
    mode = 'smoke' if args.messages is not None or args.rounds is not None or args.scenario else 'formal'
    identity, cache, flags = source_record(source, binary, replay)
    if mode == 'formal':
        require(platform.system() == 'Linux' and not identity['dirty'], 'formal ITCH measurements require clean Linux source')
    require(all(sha256(repository / name) == sha256(source / name) for name in TOOLS), 'measurement tools differ from declared source')
    environment = dict(system=platform.system(), platform=platform.platform(), architecture=platform.machine(),
                       cpu=platform.processor(), logical_cpus=os.cpu_count(), python=platform.python_version(),
                       compiler=subprocess.check_output([cache['CMAKE_CXX_COMPILER'], '--version'], text=True).strip(),
                       build_type=cache['CMAKE_BUILD_TYPE'], sanitizers=cache['LLMATCH_SANITIZERS'],
                       flags=flags, cmake_version=subprocess.check_output([cache.get('CMAKE_COMMAND', 'cmake'), '--version'], text=True).strip(),
                       cpu_controls=dict(exclusive_core=False, affinity='not controlled', frequency='not controlled',
                           inherited_affinity=sorted(os.sched_getaffinity(0)) if hasattr(os, 'sched_getaffinity') else None,
                           load_average=list(os.getloadavg()) if hasattr(os, 'getloadavg') else None))
    root = args.output_dir.resolve()
    root.mkdir(parents=True, exist_ok=False)
    manifest = dict(schema_version=1, status='running', mode=mode, started_at_utc=now(), specification=spec,
                    environment=environment, build=dict(source=identity, artifacts={}), tools={}, inputs={},
                    verification={}, execution_plan=execution_plan(spec), executed=[])
    save = lambda: write(root / 'matrix-manifest.json', manifest)
    save()

    def execute(command, log):
        started = time.perf_counter_ns()
        with log.open('w') as stream:
            result = subprocess.run([str(arg) for arg in command], stdout=stream, stderr=subprocess.STDOUT)
        duration = time.perf_counter_ns() - started
        require(result.returncode == 0, f'{Path(str(command[0])).name} exited {result.returncode}; see {log}')
        return duration

    try:
        for name in TOOLS:
            target = root / 'tool-evidence' / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(repository / name, target)
            manifest['tools'][name] = sha256(target)
        build = root / 'build-evidence'
        build.mkdir()
        for name, path in [('bench_itch', binary), ('itch_replay', replay),
                           ('CMakeCache.txt', binary.parent / 'CMakeCache.txt'),
                           ('compile_commands.json', binary.parent / 'compile_commands.json')]:
            shutil.copyfile(path, build / name)
        write(build / 'source.json', identity)
        manifest['build']['artifacts'] = {path.name: sha256(path) for path in sorted(build.iterdir())}
        save()
        for scenario in spec['scenarios']:
            execute([sys.executable, repository / 'scripts/create_itch_workloads.py', '--scenario', scenario,
                     '--messages', spec['messages'], '--output-dir', root / 'inputs' / scenario], root / f'generate-{scenario}.log')
            folder = root / 'inputs' / scenario
            manifest['inputs'][scenario] = dict(bytes=(folder / 'input.bin').stat().st_size,
                                                sha256=sha256(folder / 'input.bin'), metadata_sha256=sha256(folder / 'workload.json'))
            save()
        # Complete all original-byte reference comparisons before the first timing process.
        for scenario in spec['scenarios']:
            print(f'Verifying {scenario} original bytes before measurement', flush=True)
            duration = execute([sys.executable, repository / 'scripts/verify_itch.py', '--binary', replay,
                                '--input', root / 'inputs' / scenario / 'input.bin', '--symbol', spec['symbol'],
                                '--max-orders', spec['max_orders'], '--output-dir', root / 'verification' / scenario],
                               root / f'verify-{scenario}.log')
            receipt = root / 'verification' / scenario / 'verification.json'
            require(read(receipt)['status'] == 'passed', 'independent verification did not pass')
            manifest['verification'][scenario] = dict(sha256=sha256(receipt), wall_elapsed_ns=duration)
            save()
        for planned in manifest['execution_plan']:
            folder = root / planned['directory']
            folder.mkdir(parents=True)
            command = [str(binary), '--input', str(root / 'inputs' / planned['scenario'] / 'input.bin'),
                       '--symbol', spec['symbol'], '--mode', planned['mode'], '--max-orders', str(spec['max_orders']),
                       '--output', str(folder / 'result.json')]
            entry = {**planned, 'status': 'running', 'started_at_utc': now(), 'command': command}
            manifest['executed'].append(entry)
            save()
            print(f"{planned['scenario']} {planned['mode']} {planned['kind']} {planned['round']}", flush=True)
            entry['process_elapsed_ns'] = execute(command, folder / 'benchmark.log')
            entry.update(status='passed', exit_code=0, ended_at_utc=now(),
                         result_sha256=sha256(folder / 'result.json'), log_sha256=sha256(folder / 'benchmark.log'))
            save()
        after, _, _ = source_record(source, binary, replay)
        require(after == identity, 'source/build identity changed during measurement')
        require(all(sha256(repository / name) == wanted for name, wanted in manifest['tools'].items()), 'measurement tool changed during matrix')
        manifest.update(status='completed', ended_at_utc=now())
        save()
        report = summarize(root)
        print(json.dumps({key: report[key] for key in ('validation', 'mode', 'measured_intervals', 'warmup_intervals')}))
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError, KeyboardInterrupt) as error:
        manifest.update(status='failed', ended_at_utc=now(), failure=str(error))
        if manifest['executed'] and manifest['executed'][-1]['status'] == 'running':
            manifest['executed'][-1].update(status='failed', ended_at_utc=now(), failure=str(error))
        save()
        raise


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as error:
        raise SystemExit(f'run_itch_bench: {error}')
