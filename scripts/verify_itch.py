#!/usr/bin/env python3
"""Compare C++ audit stdout with independent raw-BinaryFILE Python replay."""
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'reference'))
from itch_reference import ItchError, replay  # noqa: E402


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def read_csv(path, numeric):
    with path.open(newline='') as stream:
        return [{key: int(value) if key in numeric else value for key, value in row.items()}
                for row in csv.DictReader(stream)]


def verify(binary, source, symbol, output_dir, *, prefix=False, max_orders=1_000_000,
           checkpoint_every=10_000, read_chunk_size=65536):
    binary, source, output_dir = Path(binary).resolve(), Path(source).resolve(), Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=False)
    replay_dir = output_dir / 'replay'
    command = [str(binary), '--input', str(source), '--symbol', symbol,
               '--output-dir', str(replay_dir), '--audit-stdout', '--max-orders', str(max_orders),
               '--checkpoint-every', str(checkpoint_every), '--read-chunk-size', str(read_chunk_size)]
    if prefix:
        command.append('--prefix')
    record = dict(schema_version=1, status='running', started_at_utc=datetime.now(timezone.utc).isoformat(),
                  input=dict(path=str(source), bytes=source.stat().st_size, sha256=sha256(source)),
                  command=command, binary_sha256=sha256(binary),
                  tool_hashes={str(path.relative_to(ROOT)): sha256(path) for path in
                               [Path(__file__).resolve(), ROOT / 'reference/itch_reference.py']},
                  compared_updates=0, checkpoints=0, prefix_allowed=prefix,
                  audit_retained=False, comparison='Every target update: affected orders/levels/BBO/count; full checkpoints and final state.')
    process = None
    expected = actual = None
    final = None
    try:
        with (output_dir / 'stderr.log').open('w') as errors:
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=errors, text=True)
            for expected in replay(source, symbol, prefix, max_orders, checkpoint_every):
                line = process.stdout.readline()
                if not line:
                    raise ValueError('C++ audit ended before the independent reference')
                actual = json.loads(line)
                if actual != expected:
                    raise ValueError(f'audit mismatch at {expected["kind"]} update {expected.get("update_index")}')
                if expected['kind'] == 'update':
                    record['compared_updates'] += 1
                elif expected['kind'] == 'checkpoint':
                    record['checkpoints'] += 1
                else:
                    final = expected
            if process.stdout.readline():
                raise ValueError('extra C++ audit records after final state')
            record['exit_code'] = process.wait(timeout=30)
        if record['exit_code'] != 0:
            raise ValueError(f'C++ replay exited {record["exit_code"]}')
        if final is None:
            raise ValueError('missing final audit')
        summary = json.loads((replay_dir / 'summary.json').read_text())
        if summary != final['summary']:
            raise ValueError('summary file differs from independently verified final audit')
        if read_csv(replay_dir / 'orders.csv', {'reference', 'price', 'shares'}) != final['orders']:
            raise ValueError('orders.csv differs from independent final state')
        if read_csv(replay_dir / 'levels.csv', {'price', 'shares', 'orders'}) != final['levels']:
            raise ValueError('levels.csv differs from independent final state')
        record.update(status='passed', summary=summary, final_orders=len(final['orders']),
                      final_levels=len(final['levels']), output_files_verified=True,
                      outputs={name: sha256(replay_dir / name) for name in ('summary.json', 'orders.csv', 'levels.csv')})
    except (OSError, ValueError, subprocess.TimeoutExpired) as error:
        record.update(status='failed', error=f'{type(error).__name__}: {error}')
        if isinstance(error, ItchError):
            record['reference_error'] = error.details
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        record['exit_code'] = process.returncode if process else None
        (output_dir / 'mismatch.json').write_text(json.dumps(dict(expected=expected, actual=actual), indent=2) + '\n')
        # Keep EOF semantics and the exact bytes: shortening an input or enabling
        # prefix mode can turn a completeness or capacity failure into a success.
        failed = output_dir / 'failure-input.bin'
        with source.open('rb') as src, failed.open('xb') as dst:
            for block in iter(lambda: src.read(1024 * 1024), b''):
                dst.write(block)
        replay_command = [sys.executable, str(Path(__file__).resolve()), '--binary', str(binary),
                          '--input', str(failed), '--symbol', symbol,
                          '--output-dir', str(output_dir / 'failure-replay'),
                          '--max-orders', str(max_orders), '--checkpoint-every', str(checkpoint_every),
                          '--read-chunk-size', str(read_chunk_size)]
        if prefix:
            replay_command.append('--prefix')
        record['failure_replay'] = dict(path=failed.name, bytes=failed.stat().st_size, sha256=sha256(failed),
                                      command=replay_command,
                                      note='Exact original bytes and validation options; reruns the independent verifier, including audit/output comparison. Use the recorded binary and tool identities. A failure caused only by an external I/O condition also requires that condition.')
    finally:
        if process is not None and process.stdout:
            process.stdout.close()
        record['ended_at_utc'] = datetime.now(timezone.utc).isoformat()
        (output_dir / 'verification.json').write_text(json.dumps(record, indent=2) + '\n')
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary', type=Path, required=True)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--symbol', required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--prefix', action='store_true')
    parser.add_argument('--max-orders', type=int, default=1_000_000)
    parser.add_argument('--checkpoint-every', type=int, default=10_000)
    parser.add_argument('--read-chunk-size', type=int, default=65536)
    args = parser.parse_args()
    if min(args.max_orders, args.checkpoint_every, args.read_chunk_size) <= 0:
        parser.error('capacities, checkpoint interval and chunk size must be positive')
    result = verify(args.binary, args.input, args.symbol, args.output_dir, prefix=args.prefix,
                    max_orders=args.max_orders, checkpoint_every=args.checkpoint_every,
                    read_chunk_size=args.read_chunk_size)
    print(json.dumps(result, indent=2))
    return 0 if result['status'] == 'passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
