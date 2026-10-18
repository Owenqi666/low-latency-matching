#!/usr/bin/env python3
"""Stream-compare C++ ITCH replay under a whole-verification deadline.

Linux/macOS: a supervisor owns a separate process group containing the Python
reference and C++ replay. Blocking hashes, reference code, partial lines, EOF,
process exit and final-file comparisons can all be stopped. No reader threads,
unbounded audit queue or whole-output communicate() are used. Other platforms
fail before spawning: they need an equivalent process-tree containment backend.
"""
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
import math
import mmap
import os
from pathlib import Path
import signal
import struct
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'reference'))
from itch_reference import ItchError, replay  # noqa: E402

# Historical 800,000-update checks took up to 219 s. This configurable default
# leaves substantial room for those long inputs and slower supported hosts.
DEFAULT_TIMEOUT = 1800.0
DEFAULT_CLEANUP_TIMEOUT = 10.0
DEFAULT_EVIDENCE_TIMEOUT = 60.0
STATUS_BYTES = 256 * 1024
PHASES = ('starting', 'input_hash', 'binary_hash', 'tool_hashes', 'cpp_start',
          'reference', 'audit_read', 'tail_eof', 'cpp_exit', 'final_summary',
          'final_orders', 'final_levels', 'output_hashes', 'mismatch_evidence',
          'failure_copy', 'failure_hash', 'finished')


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


class StatusPage:
    """One fixed-size, lock-free status page; never transport the audit here.

    A sequence word guards against reading a partial publication. Readers make
    at most three attempts, retaining their last valid record if interrupted.
    There is no lock a killed worker could leave held and no pipe recv waiting
    for the remainder of a message. Full mismatch objects stay in worker files.
    """
    def __init__(self, path, *, create=False):
        with Path(path).open('w+b' if create else 'r+b') as stream:
            if create:
                stream.truncate(STATUS_BYTES)
            self.memory = mmap.mmap(stream.fileno(), STATUS_BYTES)
        self.last = {}

    def phase(self, name):
        struct.pack_into('=I', self.memory, 8, PHASES.index(name))

    def publish(self, record):
        raw = json.dumps(record, ensure_ascii=True).encode('ascii')
        if len(raw) > STATUS_BYTES - 12:
            raise ValueError('verification metadata exceeds bounded status capacity')
        sequence = struct.unpack_from('=I', self.memory, 0)[0]
        sequence += 1 if sequence % 2 == 0 else 2
        struct.pack_into('=I', self.memory, 0, sequence)
        self.memory[12:12 + len(raw)] = raw
        struct.pack_into('=I', self.memory, 4, len(raw))
        struct.pack_into('=I', self.memory, 0, sequence + 1)

    def read(self):
        for _ in range(3):
            before, size, phase = struct.unpack_from('=III', self.memory, 0)
            if before % 2 or not 0 < size <= STATUS_BYTES - 12:
                continue
            raw = self.memory[12:12 + size]
            after = struct.unpack_from('=I', self.memory, 0)[0]
            if before == after:
                try:
                    self.last = json.loads(raw)
                except (ValueError, UnicodeError):
                    continue
                break
        result = self.last.copy()
        phase = struct.unpack_from('=I', self.memory, 8)[0]
        result['phase'] = PHASES[phase] if phase < len(PHASES) else 'unknown'
        return result

    def close(self):
        self.memory.close()


class StopRequested(Exception):
    pass


def stop_requested(_signal, _frame):
    # Give the worker a chance to reap its direct child before the supervisor's
    # hard kill. Python reference loops and blocking readline are interruptible.
    raise StopRequested('supervisor requested cleanup')


def process_group_exists(pgid):
    try:
        os.killpg(pgid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        # An uninspectable group is not evidence of successful cleanup.
        return True
    return True


def stop_group(process, budget):
    """Bounded TERM/KILL/reap, including descendants after the leader exits."""
    started = time.monotonic()
    deadline = started + budget
    result = {'worker_pid': process.pid, 'term_sent': False, 'kill_sent': False}
    for sig, field in ((signal.SIGTERM, 'term_sent'), (signal.SIGKILL, 'kill_sent')):
        try:
            os.killpg(process.pid, sig)
            result[field] = True
        except ProcessLookupError:
            pass
        wait_until = min(deadline, started + budget * .6) if sig == signal.SIGTERM else deadline
        try:
            process.wait(timeout=max(0, wait_until - time.monotonic()))
        except subprocess.TimeoutExpired:
            pass
    # killpg is asynchronous and wait() only reaps the leader. In particular a
    # crashed/hard-killed worker may leave its replay in the group. Do not call
    # that complete until the whole group disappears (including orphan zombies
    # awaiting the OS reaper). A broken host reaper is reported, never hidden.
    while process_group_exists(process.pid) and time.monotonic() < deadline:
        time.sleep(min(.005, max(0, deadline - time.monotonic())))
    worker_reaped = process.poll() is not None
    group_gone = not process_group_exists(process.pid)
    result.update(worker_exit_code=process.poll(), worker_reaped=worker_reaped,
                  process_group_gone=group_gone, complete=worker_reaped and group_gone,
                  elapsed_seconds=time.monotonic() - started)
    return result


def verification_worker(config, state):
    record = config['record']
    source, binary = Path(config['source']), Path(config['binary'])
    output_dir = Path(config['output_dir'])
    replay_dir = output_dir / 'replay'
    process = expected = actual = final = None
    last_publish = time.monotonic()
    try:
        state.phase('input_hash')
        record['input']['bytes'] = source.stat().st_size
        state.publish(record)
        record['input']['sha256'] = sha256(source)
        state.publish(record)
        state.phase('binary_hash')
        record['binary_sha256'] = sha256(binary)
        state.publish(record)
        state.phase('tool_hashes')
        record['tool_hashes'] = {str(path.relative_to(ROOT)): sha256(path) for path in
                                 [Path(__file__).resolve(), ROOT / 'reference/itch_reference.py']}
        state.publish(record)
        state.phase('cpp_start')
        with (output_dir / 'stderr.log').open('w') as errors:
            process = subprocess.Popen(record['command'], stdout=subprocess.PIPE, stderr=errors,
                                       text=True, encoding='utf-8')
            record['replay_pid'] = process.pid
            state.publish(record)
            state.phase('reference')
            reference = iter(replay(source, config['symbol'], config['prefix'],
                                    config['max_orders'], config['checkpoint_every']))
            # Full checkpoint/final records grow with configured order capacity,
            # not input duration. Also bound a malformed unterminated JSON line.
            line_limit = 1024 * 1024 + 512 * config['max_orders']
            while True:
                state.phase('reference')
                try:
                    expected = next(reference)
                except StopIteration:
                    break
                state.phase('audit_read')
                line = process.stdout.readline(line_limit + 1)
                if len(line) > line_limit:
                    raise ValueError('C++ audit record exceeds capacity-derived line limit')
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
                if time.monotonic() - last_publish >= .25:
                    state.publish(record)
                    last_publish = time.monotonic()
            state.phase('tail_eof')
            # One byte suffices to reject extra output; still require actual EOF.
            if process.stdout.read(1):
                raise ValueError('extra C++ audit records after final state')
            state.phase('cpp_exit')
            record['exit_code'] = process.wait()
        if record['exit_code'] != 0:
            raise ValueError(f'C++ replay exited {record["exit_code"]}')
        if final is None:
            raise ValueError('missing final audit')
        state.phase('final_summary')
        summary = json.loads((replay_dir / 'summary.json').read_text())
        if summary != final['summary']:
            raise ValueError('summary file differs from independently verified final audit')
        state.phase('final_orders')
        if read_csv(replay_dir / 'orders.csv', {'reference', 'price', 'shares'}) != final['orders']:
            raise ValueError('orders.csv differs from independent final state')
        state.phase('final_levels')
        if read_csv(replay_dir / 'levels.csv', {'price', 'shares', 'orders'}) != final['levels']:
            raise ValueError('levels.csv differs from independent final state')
        state.phase('output_hashes')
        outputs = {name: sha256(replay_dir / name) for name in ('summary.json', 'orders.csv', 'levels.csv')}
        record.update(status='passed', summary=summary, final_orders=len(final['orders']),
                      final_levels=len(final['levels']), output_files_verified=True, outputs=outputs)
    except Exception as error:
        record.update(status='failed', failure_kind='validation', error=f'{type(error).__name__}: {error}')
        if isinstance(error, ItchError):
            record['reference_error'] = error.details
        state.publish(record)
        if not isinstance(error, StopRequested):
            state.phase('mismatch_evidence')
            (output_dir / 'mismatch.json').write_text(json.dumps(dict(expected=expected, actual=actual), indent=2) + '\n')
    finally:
        # This grace is contained inside the supervisor's total/cleanup budgets;
        # the supervisor always owns the final hard-kill and group cleanup.
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        if process is not None:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=min(.1, config['cleanup_timeout_seconds'] / 8))
                except subprocess.TimeoutExpired:
                    process.kill()
                    try:
                        process.wait(timeout=min(.1, config['cleanup_timeout_seconds'] / 8))
                    except subprocess.TimeoutExpired:
                        pass
            record['exit_code'] = process.poll()
            if process.stdout:
                process.stdout.close()
        state.publish(record)
        state.phase('finished')


def copy_failure_input(source, partial):
    with source.open('rb') as src, partial.open('xb') as dst:
        for block in iter(lambda: src.read(1024 * 1024), b''):
            dst.write(block)


def evidence_worker(config, state):
    record = config['record']
    source, directory = Path(config['source']), Path(config['output_dir'])
    partial, failed = directory / 'failure-input.bin.partial', directory / 'failure-input.bin'
    state.phase('failure_copy')
    copy_failure_input(source, partial)
    state.phase('failure_hash')
    digest, size = sha256(partial), partial.stat().st_size
    identity = record['input']
    if identity.get('sha256') is not None and (digest != identity['sha256'] or size != identity['bytes']):
        raise ValueError('failure input changed since verification identity was recorded')
    partial.rename(failed)
    command = [sys.executable, str(Path(__file__).resolve()), '--binary', config['binary'],
               '--input', str(failed), '--symbol', config['symbol'],
               '--output-dir', str(directory / 'failure-replay')]
    for key in ('max_orders', 'checkpoint_every', 'read_chunk_size', 'timeout_seconds',
                'cleanup_timeout_seconds', 'evidence_timeout_seconds'):
        command.extend(['--' + key.replace('_', '-'), str(config[key])])
    if config['prefix']:
        command.append('--prefix')
    result = dict(evidence_incomplete=False, failure_replay=dict(
        path=failed.name, bytes=size, sha256=digest, command=command,
        original_identity_verified=identity.get('sha256') is not None,
        note='Complete input snapshot and original validation options. Use the recorded binary and tool identities. '
             'External I/O conditions require separate reproduction; an interrupted original hash cannot prove the original input identity.'))
    state.publish(result)
    state.phase('finished')


def worker_main(mode, config_path):
    config = json.loads(Path(config_path).read_text())
    state = StatusPage(config['status_path'])
    signal.signal(signal.SIGTERM, stop_requested)
    try:
        (verification_worker if mode == '--_verification-worker' else evidence_worker)(config, state)
        return 0
    except Exception as error:
        record = state.read()
        record.update(status='failed', evidence_incomplete=True,
                      worker_error=f'{type(error).__name__}: {error}')
        state.publish(record)
        return 1
    finally:
        state.close()


def supervise(config, mode, scratch, deadline, cleanup_budget, worker_script):
    status_path = scratch / (mode + '.status')
    config_path = scratch / (mode + '.json')
    state = StatusPage(status_path, create=True)
    state.publish(config['record'] if mode == 'verification' else {})
    config_path.write_text(json.dumps(dict(config, status_path=str(status_path))))
    process = None
    timed_out = False
    try:
        with (Path(config['output_dir']) / (mode + '-worker.stderr.log')).open('w') as errors:
            process = subprocess.Popen([sys.executable, str(worker_script), '--_' + mode + '-worker', str(config_path)],
                                       stdout=subprocess.DEVNULL, stderr=errors, start_new_session=True)
            try:
                process.wait(timeout=max(0, deadline - time.monotonic()))
            except subprocess.TimeoutExpired:
                timed_out = True
            result = state.read()
            timeout_phase = result['phase']
            cleanup = stop_group(process, cleanup_budget)
            # Cleanup may have reaped the replay and published its final exit.
            after = state.read()
            if not timed_out:
                result = after
            elif 'exit_code' in after:
                result['exit_code'] = after['exit_code']
            result['supervision'] = dict(timed_out=timed_out, timeout_phase=timeout_phase if timed_out else None,
                                         cleanup=cleanup)
            if process.returncode != 0 and not timed_out:
                result.setdefault('worker_error', f'verifier worker exited {process.returncode}')
            return result
    finally:
        # Popen failure has no child to reap. Unexpected supervisor errors still
        # use the same bounded cleanup, never an unbounded wait in a destructor.
        if process is not None and process.poll() is None:
            stop_group(process, 0)
        state.close()


def verify(binary, source, symbol, output_dir, *, prefix=False, max_orders=1_000_000,
           checkpoint_every=10_000, read_chunk_size=65536, timeout_seconds=DEFAULT_TIMEOUT,
           cleanup_timeout_seconds=DEFAULT_CLEANUP_TIMEOUT,
           evidence_timeout_seconds=DEFAULT_EVIDENCE_TIMEOUT, _worker_script=None):
    started = time.monotonic()
    if os.name != 'posix':
        raise ValueError('bounded ITCH verification supports Linux/macOS POSIX process groups; this platform is unsupported')
    if any(not math.isfinite(value) or value <= 0 for value in
           (timeout_seconds, cleanup_timeout_seconds, evidence_timeout_seconds)):
        raise ValueError('verification, cleanup and evidence budgets must be finite and positive')
    if min(max_orders, checkpoint_every, read_chunk_size) <= 0:
        raise ValueError('capacities, checkpoint interval and chunk size must be positive')
    binary, source, output_dir = Path(binary).resolve(), Path(source).resolve(), Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=False)
    command = [str(binary), '--input', str(source), '--symbol', symbol,
               '--output-dir', str(output_dir / 'replay'), '--audit-stdout', '--max-orders', str(max_orders),
               '--checkpoint-every', str(checkpoint_every), '--read-chunk-size', str(read_chunk_size)]
    if prefix:
        command.append('--prefix')
    record = dict(schema_version=1, status='running', started_at_utc=datetime.now(timezone.utc).isoformat(),
                  input=dict(path=str(source), bytes=None, sha256=None), command=command,
                  binary_sha256=None, tool_hashes={}, compared_updates=0, checkpoints=0,
                  prefix_allowed=prefix, audit_retained=False,
                  comparison='Every target update: affected orders/levels/BBO/count; full checkpoints and final state.',
                  budgets_seconds=dict(verification=timeout_seconds, cleanup=cleanup_timeout_seconds,
                                       evidence=evidence_timeout_seconds),
                  supervisor_backend='POSIX process group; fixed metadata page; no reader thread')
    config = dict(binary=str(binary), source=str(source), output_dir=str(output_dir), symbol=symbol,
                  prefix=prefix, max_orders=max_orders, checkpoint_every=checkpoint_every,
                  read_chunk_size=read_chunk_size, timeout_seconds=timeout_seconds,
                  cleanup_timeout_seconds=cleanup_timeout_seconds, evidence_timeout_seconds=evidence_timeout_seconds,
                  record=record)
    # This private entrypoint permits deterministic fault injection in tests; it
    # is not a public CLI option or part of a saved production replay command.
    worker_script = Path(_worker_script) if _worker_script else Path(__file__).resolve()
    with tempfile.TemporaryDirectory(prefix='.supervisor-', dir=output_dir) as scratch:
        try:
            outcome = supervise(config, 'verification', Path(scratch), started + timeout_seconds,
                                cleanup_timeout_seconds / 2, worker_script)
            record.update(outcome)
            supervision = record.pop('supervision')
            record['verification_supervision'] = supervision
            if supervision['timed_out']:
                record.update(status='failed', failure_kind='timeout',
                              timeout_phase=supervision['timeout_phase'],
                              error=f'TimeoutError: verification exceeded {timeout_seconds:g} seconds')
            elif record.get('worker_error') or record['status'] == 'running':
                record.update(status='failed', failure_kind='worker',
                              error=record.get('worker_error', 'worker exited without a final result'))
            if not supervision['cleanup']['complete']:
                record.update(status='failed', failure_kind='cleanup', error='verification process group did not disappear within cleanup budget')
        except (OSError, ValueError) as error:
            record.update(status='failed', failure_kind='supervisor', error=f'{type(error).__name__}: {error}')
        if record['status'] != 'passed':
            record['evidence_incomplete'] = True
            config['record'] = record
            try:
                evidence = supervise(config, 'evidence', Path(scratch), time.monotonic() + evidence_timeout_seconds,
                                     cleanup_timeout_seconds / 2, worker_script)
                supervision = evidence.pop('supervision')
                record['evidence_supervision'] = supervision
                if supervision['timed_out']:
                    record['evidence_error'] = f'TimeoutError: failure evidence exceeded {evidence_timeout_seconds:g} seconds'
                elif evidence.get('worker_error'):
                    record['evidence_error'] = evidence['worker_error']
                else:
                    record.update({key: value for key, value in evidence.items() if key != 'phase'})
                if not supervision['cleanup']['complete']:
                    record.update(evidence_incomplete=True, evidence_error='evidence process group did not disappear within cleanup budget')
            except (OSError, ValueError) as error:
                record['evidence_error'] = f'{type(error).__name__}: {error}'
            if record['evidence_incomplete']:
                record['failure_input_source'] = record['input'].copy()
                record['partial_input_path'] = 'failure-input.bin.partial'
                record.pop('failure_replay', None)
    record['elapsed_seconds'] = time.monotonic() - started
    record['ended_at_utc'] = datetime.now(timezone.utc).isoformat()
    (output_dir / 'verification.json').write_text(json.dumps(record, indent=2) + '\n')
    return record


def main():
    if len(sys.argv) == 3 and sys.argv[1] in ('--_verification-worker', '--_evidence-worker'):
        return worker_main(sys.argv[1], sys.argv[2])
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary', type=Path, required=True)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--symbol', required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--prefix', action='store_true')
    parser.add_argument('--max-orders', type=int, default=1_000_000)
    parser.add_argument('--checkpoint-every', type=int, default=10_000)
    parser.add_argument('--read-chunk-size', type=int, default=65536)
    parser.add_argument('--timeout-seconds', type=float, default=DEFAULT_TIMEOUT)
    parser.add_argument('--cleanup-timeout-seconds', type=float, default=DEFAULT_CLEANUP_TIMEOUT)
    parser.add_argument('--evidence-timeout-seconds', type=float, default=DEFAULT_EVIDENCE_TIMEOUT)
    args = parser.parse_args()
    if min(args.max_orders, args.checkpoint_every, args.read_chunk_size) <= 0:
        parser.error('capacities, checkpoint interval and chunk size must be positive')
    if any(not math.isfinite(value) or value <= 0 for value in
           (args.timeout_seconds, args.cleanup_timeout_seconds, args.evidence_timeout_seconds)):
        parser.error('verification, cleanup and evidence budgets must be finite and positive')
    result = verify(args.binary, args.input, args.symbol, args.output_dir, prefix=args.prefix,
                    max_orders=args.max_orders, checkpoint_every=args.checkpoint_every,
                    read_chunk_size=args.read_chunk_size, timeout_seconds=args.timeout_seconds,
                    cleanup_timeout_seconds=args.cleanup_timeout_seconds,
                    evidence_timeout_seconds=args.evidence_timeout_seconds)
    print(json.dumps(result, indent=2))
    return 0 if result['status'] == 'passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
