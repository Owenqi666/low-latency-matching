#!/usr/bin/env python3
"""Retained CLI/reference contract cases; no real-data or network dependency."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'reference'))
sys.path.insert(0, str(ROOT / 'scripts'))
from itch_reference import ItchError, decode, replay  # noqa: E402
from create_itch_workloads import create  # noqa: E402
from verify_itch import verify  # noqa: E402


def frames(raw):
    result, offset = [], 0
    while offset < len(raw):
        size = int.from_bytes(raw[offset:offset + 2], 'big')
        result.append(raw[offset:offset + size + 2])
        offset += size + 2
    return result


def change(frame, start, value):
    """Mutate a field at its wire-payload offset, independently of the generator."""
    result = bytearray(frame)
    result[start + 2:start + 2 + len(value)] = value
    return bytes(result)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    binary = args.binary.resolve()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    directory = Path(tempfile.mkdtemp(prefix='run-', dir=args.output_dir)).resolve()
    receipt = dict(status='running', binary=str(binary), evidence_directory=str(directory), cases=[])
    (args.output_dir / 'latest.json').write_text(json.dumps({'run': directory.name}) + '\n')
    (directory / 'test-summary.json').write_text(json.dumps(receipt, indent=2) + '\n')
    golden = (ROOT / 'data/itch/golden.bin').read_bytes()
    assert golden == bytes.fromhex((ROOT / 'data/itch/golden.hex').read_text())
    expected = json.loads((ROOT / 'data/itch/golden_expected.json').read_text())
    records = list(replay(ROOT / 'data/itch/golden.bin', 'TEST', checkpoint_every=1))
    updates = [x for x in records if x['kind'] == 'update']
    final = records[-1]
    for key in ('messages', 'updates', 'system_events', 'target_messages', 'filtered_messages', 'ignored_by_type'):
        assert final['summary'][key] == expected[key], key
    assert final['orders'] == expected['final_orders']
    assert final['levels'] == expected['final_levels']
    assert updates[3]['orders'][0]['state'] == expected['after_c']['order']
    assert updates[3]['bbo']['bid'] == expected['after_c']['bid']
    replacement = updates[6]
    assert replacement['orders'] == [dict(reference=10, state=None), dict(reference=12, state=expected['after_u']['order'])]
    assert replacement['levels'] == expected['after_u']['levels']
    assert replacement['bbo'] == expected['after_u']['bbo']
    chunks = frames(golden)
    assert decode(chunks[3][2:])['timestamp'] == expected['timestamp_ns']

    def positive(name, raw, **kwargs):
        source = directory / (name + '.bin')
        source.write_bytes(raw)
        result = verify(binary, source, 'TEST', directory / name, **kwargs)
        assert result['status'] == 'passed', result
        receipt['cases'].append(dict(name=name, expected='passed', verification=f'{name}/verification.json'))
        return result

    def negative(name, raw, *, prefix=False, max_orders=1_000_000):
        case = directory / name
        case.mkdir()
        source = case / 'input.bin'
        source.write_bytes(raw)
        try:
            list(replay(source, 'TEST', prefix=prefix, max_orders=max_orders))
        except ItchError as error:
            reference_error = error.details
        else:
            raise AssertionError(f'reference accepted invalid case {name}')
        command = [str(binary), '--input', str(source), '--symbol', 'TEST', '--output-dir', str(case / 'replay'),
                   '--audit-stdout', '--max-orders', str(max_orders)]
        if prefix:
            command.append('--prefix')
        result = subprocess.run(command, capture_output=True, timeout=30)
        stdout = result.stdout.decode('utf-8')
        (case / 'stdout.jsonl').write_text(stdout)
        (case / 'stderr.log').write_text(result.stderr.decode('utf-8', errors='backslashreplace'))
        assert result.returncode != 0, name
        error = json.loads((case / 'replay/error.json').read_text())
        assert error['status'] == 'failed', name
        assert not (case / 'replay/summary.json').exists(), name
        assert all(json.loads(line)['kind'] != 'final' for line in stdout.splitlines()), name
        evidence = dict(name=name, expected='failed', exit_code=result.returncode, command=command,
                        input_sha256=hashlib.sha256(raw).hexdigest(), reference_error=reference_error, error=error)
        (case / 'case.json').write_text(json.dumps(evidence, indent=2) + '\n')
        receipt['cases'].append(dict(name=name, expected='failed', evidence=f'{name}/case.json'))

    def replay_failure(result, case):
        assert result['status'] == 'failed'
        failure = result['failure_replay']
        assert failure['sha256'] == result['input']['sha256']
        assert failure['bytes'] == result['input']['bytes']
        assert ('--prefix' in failure['command']) == result['prefix_allowed']
        rerun = subprocess.run(failure['command'], capture_output=True, text=True, timeout=30)
        (case / 'failure-replay-invocation.json').write_text(json.dumps(dict(
            command=failure['command'], exit_code=rerun.returncode, stderr=rerun.stderr), indent=2) + '\n')
        assert rerun.returncode == 1, rerun.stdout
        repeated = json.loads((case / 'failure-replay/verification.json').read_text())
        assert repeated['status'] == 'failed' and repeated['error'] == result['error']
        assert repeated.get('reference_error') == result.get('reference_error')

    try:
        positive('golden-byte-chunks', golden, checkpoint_every=1, read_chunk_size=1)
        positive('golden-split-chunks', golden, checkpoint_every=3, read_chunk_size=17)
        prefix = b''.join(chunks[:17])
        result = positive('aligned-prefix-after-S-E', prefix, prefix=True)
        assert not result['summary']['session_complete'] and result['summary']['updates'] == 9
        positive('full-session-prefix-option', golden, prefix=True)
        complete_reductions = chunks[:6] + [change(chunks[6], 19, (100).to_bytes(4, 'big')),
                                           change(chunks[7], 19, (80).to_bytes(4, 'big')),
                                           chunks[10]] + chunks[-2:]
        result = positive('complete-E-C-empty-book', b''.join(complete_reductions))
        assert result['summary']['active_orders'] == 0
        positive('replacement-same-price', b''.join(chunks[:9]) + change(chunks[9], 31, (10000).to_bytes(4, 'big')) + b''.join(chunks[10:]))
        # Legal u32 quantities aggregate past u32, and legal zero/maximum Price4.
        boundary = chunks[:3] + [change(change(chunks[3], 20, b'\xff' * 4), 32, (2_000_000_000).to_bytes(4, 'big')),
                               change(change(chunks[4], 20, b'\xff' * 4), 32, (2_000_000_000).to_bytes(4, 'big')),
                               change(chunks[5], 32, bytes(4))] + chunks[-2:]
        result = positive('integer-boundaries-crossed', b''.join(boundary))
        assert result['summary']['bbo']['bid']['shares'] == 2 * (2**32 - 1)
        # The non-target path checks framing/header, not another book's semantics.
        filtered = chunks[:3] + [change(change(chunks[4], 1, b'\0\2'), 24, b'OTHER   ')] + chunks[3:]
        filtered[3] = change(change(filtered[3], 19, b'?'), 20, bytes(4))
        positive('other-security-filter', b''.join(filtered))
        for name, raw, options in [
            ('empty', b'', {}),
            ('missing-start', b''.join(chunks[1:]), {}),
            ('duplicate-start', chunks[0] + golden, {}),
            ('missing-binary-end', golden[:-2], {}),
            ('missing-itch-end', b''.join(chunks[:-2]) + b'\0\0', {'prefix': True}),
            ('half-length', golden[:-1], {'prefix': True}),
            ('half-payload', b''.join(chunks[:6]) + chunks[6][:-1], {'prefix': True}),
            ('trailing-byte', golden + b'X', {}),
            ('payload-after-itch-end', golden[:-2] + chunks[14] + b'\0\0', {}),
            ('unknown-nontarget', b''.join(chunks[:14]) + change(chunks[14], 0, b'?') + b''.join(chunks[15:]), {}),
            ('unknown-non-ascii', b''.join(chunks[:14]) + change(chunks[14], 0, b'\xff') + b''.join(chunks[15:]), {}),
            ('wrong-known-length', b''.join(chunks[:3]) + b'\0\x27' + chunks[3][2:-1] + b''.join(chunks[4:]), {}),
            ('invalid-timestamp', b''.join(chunks[:3]) + change(chunks[3], 5, (86_400_000_000_000).to_bytes(6, 'big')) + b''.join(chunks[4:]), {}),
            ('invalid-side', b''.join(chunks[:3]) + change(chunks[3], 19, b'?') + b''.join(chunks[4:]), {}),
            ('zero-shares', b''.join(chunks[:3]) + change(chunks[3], 20, bytes(4)) + b''.join(chunks[4:]), {}),
            ('price-overflow', b''.join(chunks[:3]) + change(chunks[3], 32, (2_000_000_001).to_bytes(4, 'big')) + b''.join(chunks[4:]), {}),
            ('duplicate-reference', b''.join(chunks[:4]) + chunks[3] + b''.join(chunks[4:]), {}),
            ('missing-reference', b''.join(chunks[:6]) + change(chunks[6], 11, (999).to_bytes(8, 'big')) + b''.join(chunks[7:]), {}),
            ('over-reduction', b''.join(chunks[:6]) + change(chunks[6], 19, (101).to_bytes(4, 'big')) + b''.join(chunks[7:]), {}),
            ('replacement-conflict', b''.join(chunks[:9]) + change(chunks[9], 19, (11).to_bytes(8, 'big')) + b''.join(chunks[10:]), {}),
            ('resource-limit', golden, {'max_orders': 2}),
            ('no-target-updates', b''.join(chunks[:3] + chunks[-2:]), {}),
            ('missing-directory', chunks[0] + b''.join(chunks[2:]), {}),
            ('directory-locate-conflict', chunks[0] + change(chunks[2], 1, b'\0\1') + b''.join(chunks[1:]), {}),
        ]:
            negative(name, raw, **options)
        for name, raw, options in [
            ('replay-completeness', golden[:-2], {}),
            ('replay-capacity', golden, {'max_orders': 2}),
            ('replay-truncated-prefix', b''.join(chunks[:6]) + chunks[6][:-1], {'prefix': True}),
        ]:
            source = directory / (name + '.bin')
            source.write_bytes(raw)
            case = directory / name
            result = verify(binary, source, 'TEST', case, checkpoint_every=3, read_chunk_size=17, **options)
            replay_failure(result, case)
            receipt['cases'].append(dict(name=name, expected='failed', verification=f'{name}/verification.json',
                                        repeated_verification=f'{name}/failure-replay/verification.json'))
        # Failures of the verifier itself must retain the original failure input.
        for tamper in ('audit', 'csv'):
            wrapper = directory / f'tamper-{tamper}.py'
            wrapper.write_text('#!/usr/bin/env python3\nimport json,pathlib,subprocess,sys\n'
                               f'p=subprocess.run([{str(binary)!r}]+sys.argv[1:],capture_output=True,text=True)\n'
                               'lines=p.stdout.splitlines()\n' +
                               ('value=json.loads(lines[0]);value["active_orders"]+=1;lines[0]=json.dumps(value)\n'
                                if tamper == 'audit' else
                                'd=pathlib.Path(sys.argv[sys.argv.index("--output-dir")+1]);(d/"orders.csv").write_text("reference,side,price,shares,attribution\\n")\n') +
                               'print("\\n".join(lines));sys.stderr.write(p.stderr);sys.exit(p.returncode)\n')
            wrapper.chmod(0o755)
            result = verify(wrapper, ROOT / 'data/itch/golden.bin', 'TEST', directory / f'tamper-{tamper}')
            replay_failure(result, directory / f'tamper-{tamper}')
            receipt['cases'].append(dict(name=f'tamper-{tamper}', expected='failed', verification=f'tamper-{tamper}/verification.json'))
        for scenario in ('mixed', 'cancel_replace', 'multilevel'):
            workload = directory / f'workload-{scenario}'
            manifest = create(scenario, 3000, workload)
            result = verify(binary, workload / 'input.bin', 'TEST', directory / f'generated-{scenario}')
            assert result['status'] == 'passed', result
            assert result['summary']['updates'] == manifest['target_updates']
            if scenario == 'multilevel':
                assert manifest['deterministic_best_level_disappearances'] > 0
            receipt['cases'].append(dict(name=f'generated-{scenario}', expected='passed', verification=f'generated-{scenario}/verification.json'))
        missing = subprocess.run([str(binary)], capture_output=True, text=True, timeout=10)
        assert missing.returncode != 0
        (directory / 'missing-arguments.stderr').write_text(missing.stderr)
        receipt['cases'].append(dict(name='missing-arguments', expected='failed', exit_code=missing.returncode))
        receipt['status'] = 'passed'
    finally:
        (directory / 'test-summary.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(dict(status='passed', cases=len(receipt['cases']), evidence_directory=str(directory))))


if __name__ == '__main__':
    main()
