#!/usr/bin/env python3
"""Inspect downloaded M5 CI artifacts without changing their original files.

Uses local Git objects to bind the selected tools to --head. Runs only Python
evidence checks/reference replay, never downloaded binaries, builds or network.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET


def read(path):
    return json.loads(Path(path).read_text())


def sha256(path):
    result = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            result.update(block)
    return result.hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    parser.add_argument('--run-id', type=int, required=True)
    parser.add_argument('--head', required=True)
    parser.add_argument('--checkout', required=True)
    parser.add_argument('--base')
    parser.add_argument('--attempt', type=int, default=1)
    parser.add_argument('--tools-root', type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    root, repo = args.directory.resolve(), args.tools_root.resolve()
    scratch = root / 'independent-revalidation'
    require(not scratch.exists() and not (root / 'inspection.json').exists(), 'Use a fresh inspection directory')
    scratch.mkdir()
    result = dict(schema_version=1, status='checking', run_id=args.run_id, attempt=args.attempt,
                  head=args.head, tested_checkout=args.checkout, started_at_utc=datetime.now(timezone.utc).isoformat(),
                  jobs=[], tool_bindings={}, raw_artifacts_preserved=True,
                  scope='Dynamic discovery/JUnit, retained ITCH failures and Python-only independent smoke/reference replay. Existing core/service fault paths are not rerun; their unchanged checks remain covered by full CTest.')

    def command_check(name, command, expected_error=None):
        done = subprocess.run([str(part) for part in command], capture_output=True, text=True)
        log = scratch / (name + '.log')
        log.write_text(done.stdout + done.stderr)
        log.with_suffix('.exit').write_text(str(done.returncode) + '\n')
        if expected_error is None:
            require(done.returncode == 0, f'{name} exited {done.returncode}; see {log}')
        else:
            require(done.returncode != 0 and expected_error in done.stderr, f'{name}: expected evidence rejection was not observed')
        return done.stdout

    def mirror(source, destination, hardlinks=False):
        # Summarizers unlink/rewrite only these derived reports. Never link them.
        shutil.copytree(source, destination, copy_function=os.link if hardlinks else shutil.copy2,
                        ignore=lambda directory, names: [name for name in names if name in ('report.json', 'report.md')])

    def recompute(source, name, script, hardlinks=False):
        target = scratch / name
        original = read(source / 'report.json')
        mirror(source, target, hardlinks)
        command_check(name, [sys.executable, repo / 'scripts' / script, target])
        checked = read(target / 'report.json')
        relocated = []
        if script == 'summarize_bench.py':
            require(len(original['runs']) == len(checked['runs']), 'core smoke run count changed')
            for before, after in zip(original['runs'], checked['runs']):
                old, new = before.pop('directory'), after.pop('directory')
                require(Path(new).is_relative_to(target), 'core smoke report has an unexpected output directory')
                relocated.append(dict(original=old, recomputed=new))
        require(original == checked, f'{name}: original and recomputed reports differ')
        return read(target / 'report.json'), dict(status='passed', directory=str(target.relative_to(root)),
                                                  equal_except_directory=bool(relocated), directory_relocations=relocated)

    try:
        run = read(root / 'run.json')
        require(run['databaseId'] == args.run_id and run['headSha'] == args.head, 'wrong CI run/head')
        require(run['status'] == 'completed' and run['conclusion'] == 'success', 'CI run did not succeed')
        expected_jobs = {'debug / Ubuntu 24.04', 'release / Ubuntu 24.04', 'asan-ubsan / Ubuntu 24.04',
                         'tsan / Ubuntu 24.04 / Clang 18'}
        require(len(run['jobs']) == 4 and {job['name'] for job in run['jobs']} == expected_jobs and
                all(job['status'] == 'completed' and job['conclusion'] == 'success' for job in run['jobs']), 'four required CI jobs did not succeed')
        if 'attempt' in run:
            require(run['attempt'] == args.attempt, 'CI attempt differs')
        if run['event'] == 'pull_request':
            require(args.base, '--base is required for a PR')
            parents = read(root / 'tested-checkout-parents.json')
            require(parents == dict(sha=args.checkout, parents=[args.base, args.head]), 'wrong PR merge checkout/parents')
        else:
            require(run['event'] == 'push' and args.checkout == args.head, 'expected exact-main push or PR run')
            parents = None
        result.update(event=run['event'], run_url=run['url'], tested_checkout_parents=parents)

        # These local files are the tools/fixtures actually used below, not an assumed checkout.
        result['inspection_tool'] = dict(path=str(Path(__file__).resolve()), sha256=sha256(Path(__file__)),
                                        scope='Local post-CI inspector; not claimed to have run in the inspected CI checkout.')
        names = ('scripts/check_test_groups.py', 'scripts/summarize_bench.py',
                 'scripts/create_bench_workloads.py', 'scripts/summarize_service_bench.py', 'scripts/create_service_workloads.py',
                 'scripts/summarize_itch_bench.py', 'scripts/run_itch_bench.py', 'scripts/create_itch_workloads.py',
                 'scripts/verify_itch.py', 'reference/itch_reference.py', 'tests/itch_cli_test.py', 'tests/itch_benchmark_test.py',
                 'data/itch/golden.bin', 'data/itch/golden_expected.json', 'data/workloads/smoke.manifest',
                 'data/workloads/service-smoke.json')
        for name in names:
            committed = subprocess.check_output(['git', 'show', f'{args.head}:{name}'], cwd=repo)
            actual = sha256(repo / name)
            require(hashlib.sha256(committed).hexdigest() == actual, f'local inspection input differs from CI head: {name}')
            result['tool_bindings'][name] = actual
        module_spec = importlib.util.spec_from_file_location('m5_inspection_reference', repo / 'reference/itch_reference.py')
        reference = importlib.util.module_from_spec(module_spec)
        module_spec.loader.exec_module(reference)

        def tool_binding(receipt):
            for name, wanted in receipt['tool_hashes'].items():
                require(name in result['tool_bindings'] and result['tool_bindings'][name] == wanted, f'CI reference tool differs: {name}')

        def replay_failure(source, options, expected, label):
            observed = None
            try:
                for _ in reference.replay(source, 'TEST', prefix=options.get('prefix', False), max_orders=options.get('max_orders', 1_000_000)):
                    pass
            except reference.ItchError as error:
                observed = error.details
            require(observed == expected, f'{label}: independent original-byte failure differs')
            return dict(case=label, input_sha256=sha256(source), reference_error=observed)

        def inspect_cli(artifact, preset, junit_case):
            directory = artifact / preset / 'itch-cli'
            selected = read(directory / 'latest.json')['run']
            require(Path(selected).name == selected and selected.startswith('run-'), 'invalid latest ITCH run')
            folder = directory / selected
            receipt = read(folder / 'test-summary.json')
            require(receipt['status'] == 'passed' and receipt['cases'], 'latest ITCH CLI run did not pass')
            require(selected in junit_case.findtext('system-out', ''), 'latest ITCH evidence is not the executed JUnit run')
            original_folder = Path(receipt['evidence_directory'])
            failures, replayed, positive = [], [], []
            representative = {'unknown-nontarget', 'over-reduction', 'half-payload', 'resource-limit'}
            for item in receipt['cases']:
                name = item['name']
                if 'evidence' in item:
                    case = read(folder / item['evidence'])
                    case_folder = (folder / item['evidence']).parent
                    raw = case_folder / 'input.bin'
                    require(case['exit_code'] != 0 and case['expected'] == 'failed', f'{name}: missing failed exit')
                    require(sha256(raw) == case['input_sha256'], f'{name}: failure input changed')
                    error = read(case_folder / 'replay/error.json')
                    require(error == case['error'] and error['status'] == 'failed', f'{name}: missing actual C++ error')
                    require(not (case_folder / 'replay/summary.json').exists() and (case_folder / 'stderr.log').read_text().strip(), f'{name}: incomplete failure evidence')
                    with (case_folder / 'stdout.jsonl').open() as stream:
                        require(all(json.loads(line)['kind'] != 'final' for line in stream), f'{name}: failed replay emitted final state')
                    failures.append(name)
                    if name in representative:
                        command = case['command']
                        options = dict(prefix='--prefix' in command, max_orders=int(command[command.index('--max-orders') + 1]))
                        replayed.append(replay_failure(raw, options, case['reference_error'], name))
                elif 'verification' in item:
                    path = folder / item['verification']
                    verification = read(path)
                    tool_binding(verification)
                    require(verification['status'] == item['expected'], f'{name}: verification outcome differs')
                    if item['expected'] == 'failed':
                        reproduction = verification['failure_replay']
                        raw = path.parent / reproduction['path']
                        require(sha256(raw) == reproduction['sha256'] == verification['input']['sha256'] and
                                raw.stat().st_size == reproduction['bytes'] == verification['input']['bytes'], f'{name}: failure reproduction bytes differ')
                        read(path.parent / 'mismatch.json')
                        require(verification['error'] and (path.parent / 'stderr.log').exists(), f'{name}: missing failure diagnostic')
                        failures.append(name)
                    else:
                        require(verification['exit_code'] == 0 and verification['output_files_verified'], f'{name}: replay did not succeed')
                        raw = folder / Path(verification['input']['path']).relative_to(original_folder)
                        require(sha256(raw) == verification['input']['sha256'], f'{name}: positive input identity differs')
                        for output, wanted in verification['outputs'].items():
                            require(sha256(path.parent / 'replay' / output) == wanted, f'{name}: verified output changed')
                        if name in ('golden-byte-chunks', 'aligned-prefix-after-S-E', 'generated-mixed'):
                            final = None
                            for record in reference.replay(raw, 'TEST', prefix=verification['prefix_allowed']):
                                if record['kind'] == 'final':
                                    final = record
                            require(final is not None and final['summary'] == verification['summary'], f'{name}: independent replay differs')
                            positive.append(name)
                else:
                    require(name == 'missing-arguments' and item['exit_code'] != 0 and (folder / 'missing-arguments.stderr').read_text().strip(), 'unrecognized CLI failure evidence')
            require(representative <= set(failures) and len(replayed) == len(representative), 'missing representative ITCH failures')
            require(set(positive) == {'golden-byte-chunks', 'aligned-prefix-after-S-E', 'generated-mixed'}, 'missing representative successful ITCH inputs')
            checked = dict(status='passed', run=selected, cases=len(receipt['cases']), retained_failures=failures,
                           independently_replayed_failures=replayed, independently_replayed_successes=positive)
            (scratch / f'{preset}-itch-cli.json').write_text(json.dumps(checked, indent=2) + '\n')
            return checked

        for preset in ('debug', 'release', 'asan-ubsan', 'tsan'):
            artifact = root / f'ci-evidence-{preset}-{args.run_id}-{args.attempt}'
            logs = artifact / 'ci-evidence' / preset
            require((logs / 'checkout-sha.log').read_text().strip() == args.checkout, f'{preset}: wrong actual checkout')
            event = dict(line.split('=', 1) for line in (logs / 'event.log').read_text().splitlines())
            require(event['event'] == run['event'] and event['event_sha'] == args.checkout, 'artifact event differs')
            require(event['ref'] == 'refs/heads/main' if run['event'] == 'push' else
                    event['ref'].startswith('refs/pull/') and event['ref'].endswith('/merge'), 'artifact ref differs')
            groups = ('core', 'pausable', 'protocol', 'concurrency', 'service', 'client', 'loadgen', 'itch') + (('benchmark',) if preset == 'release' else ())
            command = [sys.executable, repo / 'scripts/check_test_groups.py', '--discovery', logs / 'test-discovery.json', '--junit', logs / 'ctest.xml']
            for group in groups:
                command += ['--require', group]
            discovery_check = json.loads(command_check(preset + '-groups', command))
            cases = {case.attrib['name']: case for case in ET.parse(logs / 'ctest.xml').getroot().iter('testcase')}
            discovery = {test['name']: test for test in read(logs / 'test-discovery.json')['tests']}
            require('itch_cli' in cases and any(Path(arg).name == 'itch_cli_test.py' for arg in discovery['itch_cli']['command']), 'ITCH CLI test did not execute')
            cli = inspect_cli(artifact, preset, cases['itch_cli'])
            result['jobs'].append(dict(preset=preset, checkout=args.checkout, tests=len(cases), group_check=discovery_check, itch_cli=cli))

        artifact = root / f'ci-evidence-release-{args.run_id}-{args.attempt}'
        itch_manifest = read(artifact / 'itch-smoke/matrix-manifest.json')
        source = itch_manifest['build']['source']
        require(source['commit'] == args.checkout and not source['dirty'], 'ITCH smoke came from a different/dirty checkout')
        for name, wanted in source['build_input_sha256'].items():
            require(sha256(repo / name) == wanted, f'current build source differs from tested CI: {name}')
        for name, wanted in itch_manifest['tools'].items():
            require(result['tool_bindings'][name] == wanted, f'ITCH smoke tool differs from tested source: {name}')
        core, core_comparison = recompute(artifact / 'benchmark-smoke', 'core-smoke', 'summarize_bench.py')
        require(core['validation'] == 'passed' and core['runs'] and all(row['environment']['code_commit'] == args.checkout and
                row['environment']['code_dirty'] is False for row in core['runs']), 'core smoke source/validation differs')
        require(all(read(path)['source_manifest_sha256'] == result['tool_bindings']['data/workloads/smoke.manifest']
                    for path in (artifact / 'benchmark-smoke').rglob('run_manifest.json')), 'core smoke used a different source manifest')
        network, network_comparison = recompute(artifact / 'service-smoke', 'network-smoke', 'summarize_service_bench.py')
        network_manifest = read(artifact / 'service-smoke/manifest.json')
        expected_rows = {row['id'] for row in read(repo / 'data/workloads/service-smoke.json')['rows']}
        require(network['evidence_valid'] and network['all_runs_succeeded'] and network['mode'] == 'smoke', 'network smoke did not pass')
        require(len(expected_rows) == 7 and {row['row'] for row in network['runs']} == expected_rows, 'seven network scenes are incomplete')
        require(sha256(artifact / 'service-smoke/source_manifest.json') == result['tool_bindings']['data/workloads/service-smoke.json'],
                'network smoke used a different source manifest')
        require(network_manifest['environment']['code_commit'] == args.checkout and network_manifest['environment']['code_dirty'] is False, 'network smoke source differs')
        itch, itch_comparison = recompute(artifact / 'itch-smoke', 'itch-smoke', 'summarize_itch_bench.py', hardlinks=True)
        require(itch['validation'] == 'passed' and itch['mode'] == 'smoke' and
                itch_manifest['specification']['messages'] == 2000 and itch_manifest['specification']['rounds'] == 1 and
                itch['measured_intervals'] == 6 and itch['warmup_intervals'] == 6, 'ITCH smoke matrix differs from CI contract')
        result['smoke'] = dict(core=core_comparison, network=network_comparison, itch=itch_comparison)

        # Replay new benchmark-evidence failures without rerunning the measured workloads.
        benchmark_runs = list((artifact / 'release/itch-benchmark-evidence').glob('benchmark-check-*'))
        require(len(benchmark_runs) == 1, 'expected one fresh ITCH benchmark CTest run')
        benchmark = benchmark_runs[0]
        require(read(benchmark / 'test-result.json')['status'] == 'passed', 'ITCH benchmark test did not finish')
        release_cases = {case.attrib['name']: case for case in ET.parse(artifact / 'ci-evidence/release/ctest.xml').getroot().iter('testcase')}
        require('itch_benchmark' in release_cases and benchmark.name in release_cases['itch_benchmark'].findtext('system-out', ''),
                'ITCH benchmark evidence is not the executed Release JUnit run')
        rejected = {}
        for name, error in [('missing-round', 'missing or changed execution plan'), ('changed-input', 'input identity mismatch'),
                            ('wrong-counts', 'benchmark/reference counts or bytes mismatch'), ('fake-formal', 'formal matrix must retain')]:
            require(int((benchmark / (name + '.exit')).read_text()) != 0 and error in (benchmark / (name + '.log')).read_text(),
                    f'{name}: original CI rejection log/exit is missing')
            require(not (benchmark / name / 'report.json').exists() and not (benchmark / name / 'report.md').exists(),
                    f'{name}: original failure retained a stale success report')
            destination = scratch / ('itch-negative-' + name)
            mirror(benchmark / name, destination, hardlinks=True)
            command_check('itch-negative-' + name, [sys.executable, repo / 'scripts/summarize_itch_bench.py', destination], error)
            require(not (destination / 'report.json').exists() and not (destination / 'report.md').exists(), 'failed evidence left a success report')
            rejected[name] = dict(status='rejected', expected_error=error)
        result['itch_benchmark_failures'] = rejected
        result.update(status='passed', ended_at_utc=datetime.now(timezone.utc).isoformat())
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError, ET.ParseError) as error:
        result.update(status='failed', failure=f'{type(error).__name__}: {error}', ended_at_utc=datetime.now(timezone.utc).isoformat())
        (scratch / 'failure.log').write_text(result['failure'] + '\n')
        (root / 'inspection.json').write_text(json.dumps(result, indent=2) + '\n')
        raise
    (root / 'inspection.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(dict(status='passed', run_id=args.run_id, checkout=args.checkout,
                          tests={job['preset']: job['tests'] for job in result['jobs']}), indent=2))


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError, ET.ParseError) as error:
        raise SystemExit(f'inspect_m5_ci: {error}')
