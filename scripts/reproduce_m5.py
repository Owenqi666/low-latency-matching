#!/usr/bin/env python3
"""M5 Linux reproduction from a fresh public checkout and fresh CMake dependencies."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sha', required=True, help='Exact public commit to reproduce')
    parser.add_argument('--checkout', type=Path, required=True)
    parser.add_argument('--evidence', type=Path, required=True)
    parser.add_argument('--real-input', type=Path, required=True, help='Previously captured day-start prefix, reused without downloading')
    parser.add_argument('--capture', type=Path, required=True, help='Its original capture.json provenance receipt')
    args = parser.parse_args()
    if platform.system() != 'Linux':
        parser.error('run this reproduction on Linux')
    if len(args.sha) != 40 or any(c not in '0123456789abcdef' for c in args.sha):
        parser.error('--sha must be an exact lowercase commit SHA')
    checkout, evidence = args.checkout.resolve(), args.evidence.resolve()
    real_input = args.real_input.resolve(strict=True)
    capture = json.loads(args.capture.read_text())
    real_sha = hashlib.sha256(real_input.read_bytes()).hexdigest()
    if real_sha != capture['prefix_sha256'] or real_input.stat().st_size != capture['retained_bytes']:
        parser.error('real prefix differs from the acquisition receipt')
    if checkout.exists() or evidence.exists():
        parser.error('checkout and evidence directories must both be new')
    evidence.mkdir(parents=True)
    now = lambda: datetime.now(timezone.utc).isoformat()
    record = dict(status='running', target_sha=args.sha, started_at_utc=now(), steps=[],
                  repository='https://github.com/Owenqi666/low-latency-matching.git',
                  checkout=str(checkout), evidence=str(evidence),
                  executor='Codex automated M5 T06',
                  real_input=dict(path=str(real_input), sha256=real_sha, bytes=real_input.stat().st_size,
                                  symbol=capture['symbol'], source=capture['url'], acquisition_repeated=False),
                  dependency_mode='New public checkout, dependency downloads and Release build; existing Linux VM and system toolchain.',
                  environment=dict(platform=platform.platform(), python=platform.python_version(),
                                   build_variables={k: os.environ[k] for k in ('CC', 'CXX', 'CMAKE_PREFIX_PATH', 'CMAKE_TOOLCHAIN_FILE') if k in os.environ}))

    def save():
        (evidence / 'run.json').write_text(json.dumps(record, indent=2) + '\n')

    def run(name, command, *, cwd=checkout, expected=0):
        step = dict(name=name, argv=list(map(str, command)), cwd=str(cwd), started_at_utc=now(), expected_exit=expected)
        with (evidence / name).open('w') as log:
            done = subprocess.run(step['argv'], cwd=cwd, stdout=log, stderr=subprocess.STDOUT)
        step.update(exit_code=done.returncode, ended_at_utc=now())
        record['steps'].append(step)
        save()
        print(name, done.returncode, flush=True)
        if done.returncode != expected:
            raise RuntimeError(f'{name}: expected exit {expected}, got {done.returncode}')

    save()
    shutil.copyfile(args.capture, evidence / 'real-capture.json')
    try:
        run('clone.log', ['git', 'clone', record['repository'], checkout], cwd=checkout.parent)
        run('checkout.log', ['git', 'checkout', '--detach', args.sha])
        run('checkout-sha.log', ['git', 'rev-parse', 'HEAD'])
        if (evidence / 'checkout-sha.log').read_text().strip() != args.sha:
            raise RuntimeError('checkout differs from requested commit')
        for name, command in [('os-release.log', ['cat', '/etc/os-release']),
                              ('cpu.log', ['lscpu']), ('memory.log', ['cat', '/proc/meminfo']),
                              ('uname.log', ['uname', '-a']), ('compiler.log', ['g++', '--version']),
                              ('cmake.log', ['cmake', '--version']), ('ninja.log', ['ninja', '--version']),
                              ('python.log', [sys.executable, '--version'])]:
            run(name, command)
        run('configure.log', ['cmake', '--preset', 'release', '-DCMAKE_CXX_COMPILER=g++'])
        run('build.log', ['cmake', '--build', '--preset', 'release', '--parallel', '2'])
        for name in ('CMakeCache.txt', 'compile_commands.json'):
            shutil.copyfile(checkout / 'build/release' / name, evidence / name)
        run('test-discovery.json', ['ctest', '--preset', 'release', '--show-only=json-v1'])
        check = [sys.executable, 'scripts/check_test_groups.py', '--discovery', evidence / 'test-discovery.json']
        for group in ('core', 'pausable', 'protocol', 'concurrency', 'service', 'client', 'loadgen', 'itch', 'benchmark'):
            check += ['--require', group]
        run('test-discovery-check.json', check)
        run('ctest.log', ['ctest', '--preset', 'release', '--output-on-failure', '--no-tests=error',
                          '--output-junit', evidence / 'ctest.xml'])
        run('test-execution-check.json', check + ['--junit', evidence / 'ctest.xml'])
        run('two-clients.log', [sys.executable, 'scripts/demo_service_clients.py', checkout,
                                evidence / 'two-clients', record['executor']])
        run('itch-golden.log', [sys.executable, 'scripts/verify_itch.py', '--binary', 'build/release/itch_replay',
                               '--input', 'data/itch/golden.bin', '--symbol', 'TEST', '--output-dir', evidence / 'itch-golden'])
        run('itch-real.log', [sys.executable, 'scripts/verify_itch.py', '--binary', 'build/release/itch_replay',
                             '--input', real_input, '--symbol', capture['symbol'], '--prefix',
                             '--checkpoint-every', '250', '--output-dir', evidence / 'itch-real'])
        bad = evidence / 'truncated.bin'
        bad.write_bytes((checkout / 'data/itch/golden.bin').read_bytes()[:-1])
        run('itch-negative.log', ['build/release/itch_replay', '--input', bad, '--symbol', 'TEST',
                                  '--output-dir', evidence / 'itch-negative'], expected=1)
        if 'truncated length' not in json.loads((evidence / 'itch-negative/error.json').read_text())['error']:
            raise RuntimeError('negative demonstration did not diagnose the injected half length')
        run('core-smoke.log', [sys.executable, 'scripts/run_bench.py', '--binary', 'build/release/bench_core',
                               '--manifest', 'data/workloads/smoke.manifest', '--repeats', '1', '--output-dir', evidence / 'core-smoke'])
        run('core-summary.log', [sys.executable, 'scripts/summarize_bench.py', evidence / 'core-smoke'])
        run('network-smoke.log', [sys.executable, 'scripts/run_service_bench.py', '--server', 'build/release/matching_server',
                                  '--loadgen', 'build/release/loadgen', '--verifier', 'build/release/verify_service',
                                  '--manifest', 'data/workloads/service-smoke.json', '--output-dir', evidence / 'network-smoke'])
        run('network-summary.log', [sys.executable, 'scripts/summarize_service_bench.py', evidence / 'network-smoke'])
        run('itch-smoke.log', [sys.executable, 'scripts/run_itch_bench.py', '--binary', 'build/release/bench_itch',
                               '--replay', 'build/release/itch_replay', '--source', checkout, '--messages', '2000',
                               '--rounds', '1', '--output-dir', evidence / 'itch-smoke'])
        run('itch-summary.log', [sys.executable, 'scripts/summarize_itch_bench.py', evidence / 'itch-smoke'])
        run('git-status-after.log', ['git', 'status', '--porcelain'])
        if (evidence / 'git-status-after.log').read_text().strip():
            raise RuntimeError('checkout changed during reproduction')
        record['status'] = 'passed'
    except (OSError, ValueError, RuntimeError) as error:
        record.update(status='failed', error=str(error))
        raise
    finally:
        record['binaries'] = {}
        for name in ('itch_replay', 'bench_itch', 'matching_server', 'matching_client', 'loadgen', 'verify_service', 'bench_core'):
            path = checkout / 'build/release' / name
            if path.exists():
                record['binaries'][name] = dict(bytes=path.stat().st_size, sha256=hashlib.sha256(path.read_bytes()).hexdigest())
        record['ended_at_utc'] = now()
        save()


if __name__ == '__main__':
    main()
