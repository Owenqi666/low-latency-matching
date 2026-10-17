#!/usr/bin/env python3
"""Verify an M5 evidence tar.gz or its unchanged extracted directory.

M5_MANIFEST.json has schema_version=1, kind=measurements|validation,
files=[{path, bytes, sha256}], required=[file paths], and roles={name: path}.
Measurements roles: formal, real_capture, real_verification, real_observation.
Validation roles: t06, pr_ci, main_ci, source_relation. Roles do not supply code.

Hash/structure check: verify_m5_archive.py ARCHIVE --receipt check.json
Safe extraction: add --extract-to NEW_DIRECTORY.
Independent checks: add --recompute --tools-root TRUSTED_SOURCE --work-dir NEW_DIR.
For an already extracted archive, pass its directory instead of ARCHIVE.
Recomputation uses only the specified trusted Python tools, never archive binaries.
Real raw bytes and real orders/levels CSV are private and cannot be replayed here.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import tarfile

MANIFEST = 'M5_MANIFEST.json'
SCENARIOS = ('mixed', 'cancel_replace', 'multilevel')
PRESETS = ('debug', 'release', 'asan-ubsan', 'tsan')
TOOLS = ('scripts/create_itch_workloads.py', 'scripts/verify_itch.py',
         'reference/itch_reference.py', 'scripts/run_itch_bench.py',
         'scripts/summarize_itch_bench.py')
GROUPS = ('core', 'pausable', 'protocol', 'concurrency', 'service', 'client', 'loadgen', 'itch')
ROLE_NAMES = {'measurements': {'formal', 'real_capture', 'real_verification', 'real_observation'},
              'validation': {'t06', 'pr_ci', 'main_ci', 'source_relation'}}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def permitted(name):
    require(isinstance(name, str) and bool(name), 'empty/non-string member path')
    path = PurePosixPath(name)
    require(path.parts and not path.is_absolute() and str(path) == name and '..' not in path.parts and
            '\\' not in name and all(ord(c) >= 32 and ord(c) != 127 for c in name), f'unsafe member: {name}')
    require(not set(path.parts) & {'.git', '.ssh', '.cache', '_deps', 'CMakeFiles', '__pycache__'} and
            not any(re.fullmatch(r'm\d+-vm', part) for part in path.parts), f'private/cache member: {name}')
    require(not any(token in name for token in ('项目方针', '项目计划', '开发任务', '任务书',
                                               'ssh_config', 'id_ed25519', 'id_rsa')), f'private document/key: {name}')
    require(path.suffix.lower() not in ('.qcow2', '.img', '.iso', '.pem', '.key', '.tar', '.gz', '.tgz', '.zip', '.bz2', '.xz', '.zst', '.7z'),
            f'VM/key/nested archive is outside M5 evidence: {name}')
    # M5's historical-data destinations; legacy loadgen-test-evidence/real is
    # a synthetic live-server fixture and its traces remain public evidence.
    real = path.parts[0] in ('real', 'real-negative') or 'itch-real' in path.parts
    require(not real or path.suffix.lower() not in ('.bin', '.csv', '.trace', '.snapshot'),
            f'private real input/state: {name}')
    return name


def hex_digest(value, length=64):
    return isinstance(value, str) and re.fullmatch('[0-9a-f]{' + str(length) + '}', value) is not None


def digest(stream):
    value = hashlib.sha256()
    for block in iter(lambda: stream.read(1024 * 1024), b''):
        value.update(block)
    return value.hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def manifest_files(manifest):
    require(manifest['schema_version'] == 1 and manifest['kind'] in ROLE_NAMES, 'unknown M5 manifest format')
    require(set(manifest['roles']) == ROLE_NAMES[manifest['kind']], 'missing or unknown M5 evidence role')
    for path in manifest['roles'].values():
        permitted(path)
    files = {}
    for item in manifest['files']:
        name = permitted(item['path'])
        require(name != MANIFEST and name not in files, f'duplicate/self-listed member: {name}')
        require(type(item['bytes']) is int and item['bytes'] >= 0 and hex_digest(item['sha256']), f'invalid identity: {name}')
        files[name] = item
    required = manifest['required']
    require(files and required and len(required) == len(set(required)) and set(required) <= set(files),
            'empty manifest or missing/duplicate required file')
    return files


def check_roles(manifest, files, load):
    """These requirements are fixed here, not supplied by manifest.required."""
    roles = manifest['roles']
    def need(*names):
        for name in names:
            require(name in files, f'missing mandatory evidence: {name}')
    def matrix(base, formal=False):
        need(base + '/matrix-manifest.json', base + '/report.json')
        value, report = load(base + '/matrix-manifest.json'), load(base + '/report.json')
        spec = value['specification']
        rounds, messages = (5, 1_000_000) if formal else (1, 2000)
        require(value['status'] == 'completed' and value['mode'] == ('formal' if formal else 'smoke') and
                tuple(spec['scenarios']) == SCENARIOS and spec['rounds'] == rounds and spec['messages'] == messages and
                spec['warmups'] == spec['traversals'] == 1, f'{base}: incorrect frozen matrix')
        plan = [dict(scenario=scenario, mode=mode, kind='warmup' if number == 0 else 'measurement',
                     round=number, directory=f'runs/{scenario}/{mode}/' + ('warmup' if number == 0 else f'round_{number}'))
                for scenario in SCENARIOS for mode in ('decode', 'rebuild') for number in range(rounds + 1)]
        require(value['execution_plan'] == plan and len(value['executed']) == len(plan), f'{base}: incomplete intervals')
        for expected, actual in zip(plan, value['executed']):
            require(all(actual[key] == item for key, item in expected.items()) and actual['status'] == 'passed' and
                    actual['exit_code'] == 0, f'{base}: failed/changed interval')
            need(*(base + '/' + expected['directory'] + '/' + name for name in ('result.json', 'benchmark.log')))
        for scenario in SCENARIOS:
            need(*(base + '/inputs/' + scenario + '/' + name for name in ('input.bin', 'workload.json')))
            need(base + '/verification/' + scenario + '/verification.json')
            need(*(base + '/verification/' + scenario + '/replay/' + name for name in ('summary.json', 'orders.csv', 'levels.csv')))
        need(*(base + '/tool-evidence/' + name for name in TOOLS))
        need(*(base + '/build-evidence/' + name for name in
               ('bench_itch', 'itch_replay', 'CMakeCache.txt', 'compile_commands.json', 'source.json')))
        require(report['validation'] == 'passed' and report['measured_intervals'] == rounds * 6 and report['warmup_intervals'] == 6,
                f'{base}: matrix report differs')
        return value
    if manifest['kind'] == 'measurements':
        value = matrix(roles['formal'], formal=True)
        require(hex_digest(value['build']['source']['commit'], 40) and not value['build']['source']['dirty'], 'formal source is not fixed/clean')
        need(*(roles[name] for name in ('real_capture', 'real_verification', 'real_observation')))
        capture, verification, observation = (load(roles[name]) for name in ('real_capture', 'real_verification', 'real_observation'))
        require(hex_digest(capture['prefix_sha256']) and capture['retained_bytes'] > 0 and capture['url'] and capture['symbol'], 'missing real provenance')
        require(verification['status'] == 'passed' and verification['exit_code'] == 0 and verification['output_files_verified'] and
                verification['prefix_allowed'] and verification['input']['sha256'] == capture['prefix_sha256'] and
                verification['input']['bytes'] == capture['retained_bytes'] and verification['summary']['symbol'] == capture['symbol'] and
                verification['summary']['updates'] > 0 and
                not verification['summary']['session_complete'], 'real verification is not the captured prefix')
        require(observation['status'] == 'passed' and observation['mode'] == 'rebuild' and observation['prefix_allowed'] and
                observation['symbol'] == capture['symbol'] and observation['bytes'] == capture['retained_bytes'] and
                observation['input_fnv1a64'] == verification['summary']['input_fnv1a64'] and
                observation['target_updates'] == verification['summary']['updates'] and observation['elapsed_ns'] > 0,
                'real resource observation differs from verified input')
        return
    t06 = roles['t06']
    need(*(t06 + '/' + name for name in ('run.json', 'test-discovery.json', 'ctest.xml', 'CMakeCache.txt',
          'compile_commands.json', 'two-clients/summary.json', 'two-clients/commands.json', 'truncated.bin',
          'itch-negative/error.json', 'itch-golden/verification.json', 'itch-real/verification.json', 'real-capture.json',
          'core-smoke/report.json', 'network-smoke/manifest.json', 'network-smoke/source_manifest.json', 'network-smoke/report.json')))
    run = load(t06 + '/run.json')
    require(run['status'] == 'passed' and hex_digest(run['target_sha'], 40) and run['real_input']['acquisition_repeated'] is False,
            'T06 did not complete the recorded fresh-checkout/reused-input path')
    steps = {step['name']: step for step in run['steps']}
    mandatory = ('clone.log', 'checkout.log', 'checkout-sha.log', 'configure.log', 'build.log', 'ctest.log',
                 'test-discovery-check.json', 'test-execution-check.json', 'two-clients.log', 'itch-golden.log',
                 'itch-real.log', 'itch-negative.log', 'core-smoke.log', 'core-summary.log', 'network-smoke.log',
                 'network-summary.log', 'itch-smoke.log', 'itch-summary.log', 'git-status-after.log')
    require(set(mandatory) <= set(steps) and len(steps) == len(run['steps']), 'T06 is missing executed steps')
    for name in mandatory:
        require(steps[name]['exit_code'] == steps[name]['expected_exit'] == (1 if name == 'itch-negative.log' else 0),
                f'T06 failed step: {name}')
        need(t06 + '/' + name)
    smoke = matrix(t06 + '/itch-smoke')
    require(smoke['build']['source']['commit'] == run['target_sha'] and not smoke['build']['source']['dirty'], 'T06 smoke source differs')
    demo = load(t06 + '/two-clients/summary.json')
    require(demo['status'] == 'passed' and demo['commands'] == 7 and len(set(demo['clients'])) == 2 and
            demo['reference_verified'] and demo['bbo_before_complete'], 'T06 two-client demonstration did not pass')
    golden, real = load(t06 + '/itch-golden/verification.json'), load(t06 + '/itch-real/verification.json')
    require(all(item['status'] == 'passed' and item['exit_code'] == 0 and item['output_files_verified'] for item in (golden, real)) and
            real['prefix_allowed'] and real['input']['sha256'] == run['real_input']['sha256'] and
            real['input']['bytes'] == run['real_input']['bytes'], 'T06 ITCH demonstration evidence differs')
    capture = load(t06 + '/real-capture.json')
    require(capture['prefix_sha256'] == real['input']['sha256'] and capture['retained_bytes'] == real['input']['bytes'], 'T06 real source receipt differs')
    negative = load(t06 + '/itch-negative/error.json')
    require(negative['status'] == 'failed' and 'truncated length' in negative['error'], 'T06 negative demonstration is missing')
    relation = load(roles['source_relation'])
    require(relation['status'] == 'passed' and all(hex_digest(relation[name], 40) for name in
            ('baseline_sha', 'measured_sha', 'reproduced_sha', 'final_sha')), 'incomplete source relationship')
    require(relation['measured_build_input_sha256'] and
            relation['measured_build_input_sha256'] == relation['final_build_input_sha256'] and
            all(hex_digest(value) for value in relation['measured_build_input_sha256'].values()), 'measured/final build inputs differ')
    require(relation['reproduced_sha'] == run['target_sha'], 'T06/source relationship differs')
    for role, event in (('pr_ci', 'pull_request'), ('main_ci', 'push')):
        base = roles[role]
        need(base + '/run.json', base + '/inspection.json')
        ci, inspection = load(base + '/run.json'), load(base + '/inspection.json')
        require(ci['status'] == 'completed' and ci['conclusion'] == 'success' and ci['event'] == event and
                inspection['status'] == 'passed' and inspection['run_id'] == ci['databaseId'] and
                inspection['head'] == ci['headSha'] and inspection['event'] == event and
                {job['preset'] for job in inspection['jobs']} == set(PRESETS) and len(inspection['jobs']) == 4,
                f'{role}: incomplete CI inspection')
        if role == 'main_ci':
            require(inspection['head'] == inspection['tested_checkout'] == relation['final_sha'], 'main CI is not final source')
        else:
            need(base + '/tested-checkout-parents.json')
            parents = load(base + '/tested-checkout-parents.json')
            require(parents == inspection['tested_checkout_parents'] and parents['sha'] == inspection['tested_checkout'] and
                    len(parents['parents']) == 2 and parents['parents'][1] == inspection['head'], 'PR checkout relationship differs')
        for preset in PRESETS:
            artifact = f"{base}/ci-evidence-{preset}-{inspection['run_id']}-{inspection['attempt']}"
            need(*(artifact + '/ci-evidence/' + preset + '/' + name for name in
                   ('checkout-sha.log', 'event.log', 'test-discovery.json', 'ctest.xml')))
            cli = artifact + '/' + preset + '/itch-cli'
            need(cli + '/latest.json')
            selected = load(cli + '/latest.json')['run']
            require(PurePosixPath(selected).name == selected and selected.startswith('run-'), 'invalid latest CLI evidence path')
            cli += '/' + selected
            receipt = load(cli + '/test-summary.json')
            require(receipt['status'] == 'passed' and receipt['cases'], 'missing latest CLI cases')
            for case in receipt['cases']:
                if 'evidence' in case:
                    need(cli + '/' + case['evidence'])
                    folder = str(PurePosixPath(cli + '/' + case['evidence']).parent)
                    need(*(folder + '/' + name for name in ('input.bin', 'stdout.jsonl', 'stderr.log', 'replay/error.json')))
                elif 'verification' in case:
                    need(cli + '/' + case['verification'])
                    folder = str(PurePosixPath(cli + '/' + case['verification']).parent)
                    names = ('failure-input.bin', 'mismatch.json', 'stderr.log') if case['expected'] == 'failed' else (
                            'replay/summary.json', 'replay/orders.csv', 'replay/levels.csv')
                    need(*(folder + '/' + name for name in names))
                else:
                    require(case['name'] == 'missing-arguments', 'unknown CLI case')
                    need(cli + '/missing-arguments.stderr')
        artifact = f"{base}/ci-evidence-release-{inspection['run_id']}-{inspection['attempt']}"
        need(artifact + '/benchmark-smoke/report.json', artifact + '/service-smoke/report.json', artifact + '/service-smoke/manifest.json')
        matrix(artifact + '/itch-smoke')


def verify(source):
    archive = None
    if source.is_dir():
        manifest = read(source / MANIFEST)
        paths = list(source.rglob('*'))
        require(all(not path.is_symlink() and (path.is_dir() or path.is_file()) for path in paths), 'non-regular extracted member')
        for path in paths:
            permitted(path.relative_to(source).as_posix())
        members = {path.relative_to(source).as_posix(): path for path in paths if path.is_file()}
        open_member = lambda name: members[name].open('rb')
        size = lambda name: members[name].stat().st_size
    else:
        archive = tarfile.open(source, 'r:gz')
        entries = archive.getmembers()
        require(all(item.isfile() and not item.sparse for item in entries), 'archive must contain selected regular files only')
        members = {item.name: item for item in entries}
        require(len(members) == len(entries), 'duplicate archive member')
        open_member = lambda name: archive.extractfile(members[name])
        size = lambda name: members[name].size
        require(MANIFEST in members, 'missing M5_MANIFEST.json')
        with open_member(MANIFEST) as stream:
            manifest = json.load(stream)
    try:
        files = manifest_files(manifest)
        require(set(members) == set(files) | {MANIFEST}, 'missing or extra archive files')
        if source.is_dir():
            parents = {str(parent) for name in members for parent in PurePosixPath(name).parents}
            require(all(path.relative_to(source).as_posix() in parents for path in paths if path.is_dir()), 'extra extracted directory')
        for name in members:
            permitted(name)
        roles, cache = manifest['roles'], {}
        metadata = set(roles.values())
        for role in ('t06', 'pr_ci', 'main_ci'):
            if role in roles:
                metadata.update(roles[role] + '/' + name for name in ('run.json', 'inspection.json', 'tested-checkout-parents.json',
                                'two-clients/summary.json', 'itch-golden/verification.json', 'itch-real/verification.json',
                                'real-capture.json', 'itch-negative/error.json'))
        for name, wanted in files.items():
            require(size(name) == wanted['bytes'], f'size mismatch: {name}')
            with open_member(name) as stream:
                # Keep only small metadata, avoiding repeated gzip seeks for role checks.
                if name in metadata or name.endswith(('/matrix-manifest.json', '/report.json', '/latest.json', '/test-summary.json')):
                    cache[name] = stream.read()
                    actual = hashlib.sha256(cache[name]).hexdigest()
                else:
                    actual = digest(stream)
                require(actual == wanted['sha256'], f'SHA-256 mismatch: {name}')
        def load(name):
            require(name in files, f'missing mandatory evidence: {name}')
            if name in cache:
                return json.loads(cache[name])
            with open_member(name) as stream:
                return json.load(stream)
        check_roles(manifest, files, load)
        return manifest
    finally:
        if archive:
            archive.close()


def recompute(directory, manifest, tools, work):
    work.mkdir(parents=True, exist_ok=False)
    checks = []
    def invoke(name, script, arguments):
        command = [sys.executable, str(tools / 'scripts' / script), *map(str, arguments)]
        with (work / (name + '.log')).open('w') as log:
            result = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT)
        (work / (name + '.exit')).write_text(str(result.returncode) + '\n')
        require(result.returncode == 0, f'{name}: independent check failed; see {work}')
        checks.append(dict(name=name, exit_code=result.returncode, command=command))
    def groups(base, name, release=True):
        arguments = ['--discovery', base / 'test-discovery.json', '--junit', base / 'ctest.xml']
        for group in GROUPS + (('benchmark',) if release else ()):
            arguments += ['--require', group]
        invoke(name, 'check_test_groups.py', arguments)
    def summary(base, name, script):
        target = work / name
        # Only these derived reports are rewritten by the three trusted summarizers.
        shutil.copytree(base, target, copy_function=os.link,
                        ignore=lambda folder, names: [item for item in names if item in ('report.json', 'report.md')])
        before = read(base / 'report.json')
        invoke(name, script, [target])
        after = read(target / 'report.json')
        if script == 'summarize_bench.py':
            for report in (before, after):
                for row in report['runs']:
                    row.pop('directory')
        require(before == after, f'{name}: recomputed report differs')
    def smoke(base, prefix):
        summary(base / 'core-smoke', prefix + '-core', 'summarize_bench.py')
        summary(base / 'network-smoke', prefix + '-network', 'summarize_service_bench.py')
        summary(base / 'itch-smoke', prefix + '-itch', 'summarize_itch_bench.py')
    roles = manifest['roles']
    if manifest['kind'] == 'measurements':
        formal = directory / roles['formal']
        identities = read(formal / 'matrix-manifest.json')['tools']
        for name in TOOLS:
            with (tools / name).open('rb') as stream:
                require(digest(stream) == identities[name], f'trusted tool differs from measurement: {name}')
        summary(formal, 'formal', 'summarize_itch_bench.py')
        spec = importlib.util.spec_from_file_location('m5_archive_reference', tools / 'reference/itch_reference.py')
        reference = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(reference)
        for scenario in SCENARIOS:
            final = None
            for record in reference.replay(formal / 'inputs' / scenario / 'input.bin', 'TEST'):
                if record['kind'] == 'final':
                    final = record
            verification = read(formal / 'verification' / scenario / 'verification.json')
            require(final is not None and final['summary'] == verification['summary'], f'{scenario}: independent raw replay differs')
            # Compare the complete normalized state, not only the input hash/counts.
            import csv
            for name, numeric in [('orders', {'reference', 'price', 'shares'}), ('levels', {'price', 'shares', 'orders'})]:
                with (formal / 'verification' / scenario / 'replay' / (name + '.csv')).open(newline='') as stream:
                    actual = [{key: int(value) if key in numeric else value for key, value in row.items()} for row in csv.DictReader(stream)]
                require(actual == final[name], f'{scenario}: independent final {name} differ')
            checks.append(dict(name='formal-reference-' + scenario, status='passed', updates=final['summary']['updates']))
    else:
        t06 = directory / roles['t06']
        groups(t06, 't06-tests')
        smoke(t06, 't06')
        for role in ('pr_ci', 'main_ci'):
            base = directory / roles[role]
            inspection = read(base / 'inspection.json')
            for name, wanted in inspection['tool_bindings'].items():
                with (tools / name).open('rb') as stream:
                    require(digest(stream) == wanted, f'{role}: trusted tool/fixture differs: {name}')
            for preset in PRESETS:
                artifact = base / f"ci-evidence-{preset}-{inspection['run_id']}-{inspection['attempt']}"
                groups(artifact / 'ci-evidence' / preset, role + '-' + preset, release=preset == 'release')
                if preset == 'release':
                    for folder, script in [('benchmark-smoke', 'summarize_bench.py'), ('service-smoke', 'summarize_service_bench.py'),
                                           ('itch-smoke', 'summarize_itch_bench.py')]:
                        summary(artifact / folder, role + '-' + folder, script)
    return checks


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('source', type=Path)
    parser.add_argument('--extract-to', type=Path)
    parser.add_argument('--recompute', action='store_true')
    parser.add_argument('--tools-root', type=Path)
    parser.add_argument('--work-dir', type=Path, help='New scratch directory on the extracted evidence filesystem (hardlinks avoid duplicate raw inputs)')
    parser.add_argument('--receipt', type=Path, help='Write outside the checked/extracted directory')
    args = parser.parse_args()
    source = args.source.resolve()
    if args.recompute and (not args.tools_root or not args.work_dir or (not source.is_dir() and not args.extract_to)):
        parser.error('--recompute needs --tools-root, --work-dir and an extracted directory or --extract-to')
    result = dict(status='checking', source=str(source), started_at_utc=datetime.now(timezone.utc).isoformat())
    receipt = None
    try:
        checked_directory = args.extract_to.resolve() if args.extract_to else (source if source.is_dir() else None)
        if args.receipt:
            requested = args.receipt.resolve()
            require(requested != source and (checked_directory is None or not requested.is_relative_to(checked_directory)),
                    '--receipt must be outside the archive/extracted evidence')
            receipt = requested
        if args.recompute:
            require(not args.work_dir.resolve().is_relative_to(checked_directory), '--work-dir must be outside extracted evidence')
        manifest = verify(source)
        directory = source
        if args.extract_to:
            require(not source.is_dir(), '--extract-to requires a tar.gz source')
            directory = args.extract_to.resolve()
            directory.mkdir(parents=True, exist_ok=False)
            with tarfile.open(source, 'r:gz') as archive:
                for member in archive:
                    permitted(member.name)
                    require(member.isfile() and not member.sparse, 'non-regular member during extraction')
                    target = directory / member.name
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with archive.extractfile(member) as stream, target.open('xb') as output:
                        shutil.copyfileobj(stream, output)
        result.update(kind=manifest['kind'], files_verified=len(manifest['files']),
                      uncompressed_bytes=sum(item['bytes'] for item in manifest['files']),
                      roles=manifest['roles'], independent_checks=[])
        if args.recompute:
            result['independent_checks'] = recompute(directory, manifest, args.tools_root.resolve(), args.work_dir.resolve())
        result.update(status='passed', scope='Internal inventory/SHA/size, public-file exclusions, mandatory role structure and source/CI relationships; only listed independent checks were rerun. Real raw input is intentionally excluded.')
    except (OSError, ValueError, KeyError, TypeError, tarfile.TarError, subprocess.SubprocessError) as error:
        result.update(status='failed', error=f'{type(error).__name__}: {error}')
    result['ended_at_utc'] = datetime.now(timezone.utc).isoformat()
    if receipt:
        receipt.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))
    return 0 if result['status'] == 'passed' else 1


if __name__ == '__main__':
    sys.exit(main())
