#!/usr/bin/env python3
"""Bounded ITCH supervision faults, real golden replay and larger input checks."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from create_itch_workloads import create  # noqa: E402
from verify_itch import process_group_exists, verify  # noqa: E402


def executable(path, source):
    path.write_text('#!' + sys.executable + '\n' + source)
    path.chmod(0o755)
    return path


def absent(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return True
    return False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    binary = args.binary.resolve()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    directory = Path(tempfile.mkdtemp(prefix='run-', dir=args.output_dir)).resolve()
    (args.output_dir / 'latest.json').write_text(json.dumps({'run': directory.name}) + '\n')
    receipt = dict(status='running', evidence_directory=str(directory), cases=[])
    initial_threads = set(threading.enumerate())
    source = ROOT / 'data/itch/golden.bin'
    wrapper_prefix = ('import pathlib, sys, time\n'
                      f'sys.path.insert(0, {str(ROOT / "scripts")!r})\n'
                      'import verify_itch as verifier\n')
    hang = '\nwhile True: time.sleep(10)\n'

    def run(name, target=binary, *, expect='failed', failure_kind=None, phase=None,
            worker=None, timeout=1.0, evidence_timeout=2.0, input_path=source):
        cleanup = 1.0
        started = time.monotonic()
        result = verify(target, input_path, 'TEST', directory / name,
                        timeout_seconds=timeout, cleanup_timeout_seconds=cleanup,
                        evidence_timeout_seconds=evidence_timeout, _worker_script=worker)
        duration = time.monotonic() - started
        assert duration <= timeout + cleanup + evidence_timeout + 1.0, (name, duration, result)
        assert result['status'] == expect, (name, result)
        if failure_kind:
            assert result['failure_kind'] == failure_kind, (name, result)
        if phase:
            assert result['timeout_phase'] == phase, (name, result)
        assert set(threading.enumerate()) == initial_threads, name
        for key in ('verification_supervision', 'evidence_supervision'):
            if key in result:
                cleanup_result = result[key]['cleanup']
                assert cleanup_result['complete'], (name, cleanup_result)
                assert cleanup_result['worker_reaped'] and cleanup_result['process_group_gone'], (name, cleanup_result)
                assert absent(cleanup_result['worker_pid']), (name, cleanup_result)
                assert not process_group_exists(cleanup_result['worker_pid']), (name, cleanup_result)
        if result.get('replay_pid'):
            assert absent(result['replay_pid']), (name, result)
        receipt['cases'].append(dict(name=name, expected=expect, elapsed_seconds=duration,
                                    verification=f'{name}/verification.json'))
        (directory / 'test-summary.json').write_text(json.dumps(receipt, indent=2) + '\n')
        return result

    try:
        run('golden', expect='passed', timeout=15)
        workload = directory / 'larger-workload'
        manifest = create('long_verify', 20000, workload)
        large = run('larger-input', expect='passed', timeout=30, input_path=workload / 'input.bin')
        assert large['compared_updates'] == manifest['target_updates']

        no_output = executable(directory / 'no-output.py', 'import time\n' + hang)
        result = run('no-output', no_output, failure_kind='timeout', phase='audit_read')
        assert not result['evidence_incomplete']
        assert result['failure_replay']['sha256'] == result['input']['sha256']
        partial = executable(directory / 'partial-line.py',
                             'import sys,time\nsys.stdout.write("{\\\"kind\\\":");sys.stdout.flush()\n' + hang)
        run('partial-json-line', partial, failure_kind='timeout', phase='audit_read')

        # A real replay produces all expected output, then the wrapper keeps
        # stdout open. A second case closes stdout but does not exit.
        for name, close_stdout, phase in [('final-record-no-eof', False, 'tail_eof'),
                                          ('eof-without-exit', True, 'cpp_exit')]:
            fake = executable(directory / (name + '.py'),
                              'import os,subprocess,sys,time\n'
                              f'p=subprocess.run([{str(binary)!r}]+sys.argv[1:])\n'
                              'assert p.returncode == 0\n' +
                              ('os.close(1)\n' if close_stdout else '') + hang)
            run(name, fake, failure_kind='timeout', phase=phase)

        # Faults are injected in a separate worker script, not production CLI
        # flags. They exercise the real parent supervisor and process cleanup.
        reference = executable(directory / 'reference-hang.py', wrapper_prefix +
                               'def stalled(*args, **kwargs):\n'
                               '    while True: time.sleep(10)\n'
                               'verifier.replay = stalled\n'
                               'raise SystemExit(verifier.main())\n')
        run('python-reference-hang', worker=reference, failure_kind='timeout', phase='reference')
        hashing = executable(directory / 'hash-hang.py', wrapper_prefix +
                             'original = verifier.sha256\n'
                             'def stalled(path):\n'
                             f'    if pathlib.Path(path) == pathlib.Path({str(source)!r}):\n'
                             '        while True: time.sleep(10)\n'
                             '    return original(path)\n'
                             'verifier.sha256 = stalled\n'
                             'raise SystemExit(verifier.main())\n')
        result = run('input-hash-hang', worker=hashing, failure_kind='timeout', phase='input_hash')
        assert result['input']['sha256'] is None
        assert result['input']['bytes'] == source.stat().st_size
        assert not result['failure_replay']['original_identity_verified']
        final_csv = executable(directory / 'final-csv-hang.py', wrapper_prefix +
                               'def stalled(*args, **kwargs):\n'
                               '    while True: time.sleep(10)\n'
                               'verifier.read_csv = stalled\n'
                               'raise SystemExit(verifier.main())\n')
        run('final-artifact-hang', worker=final_csv, failure_kind='timeout', phase='final_orders')

        tamper = executable(directory / 'tamper.py',
                            'import json,subprocess,sys\n'
                            f'p=subprocess.run([{str(binary)!r}]+sys.argv[1:],capture_output=True,text=True)\n'
                            'lines=p.stdout.splitlines()\n'
                            'value=json.loads(lines[0]);value["active_orders"]+=1\n'
                            'lines[0]=json.dumps(value)\n'
                            'print("\\n".join(lines));sys.stderr.write(p.stderr);sys.exit(p.returncode)\n')
        result = run('content-mismatch', tamper, failure_kind='validation', timeout=15)
        assert result['error'].startswith('ValueError: audit mismatch')
        mismatch = json.loads((directory / 'content-mismatch/mismatch.json').read_text())
        assert mismatch['actual'] != mismatch['expected']
        # The saved production command must really repeat the semantic failure.
        rerun = subprocess.run(result['failure_replay']['command'], capture_output=True, text=True, timeout=20)
        assert rerun.returncode == 1, rerun.stdout
        repeated = json.loads((directory / 'content-mismatch/failure-replay/verification.json').read_text())
        assert repeated['error'] == result['error']

        evidence = executable(directory / 'copy-hang.py', wrapper_prefix +
                              'def stalled(source, partial):\n'
                              '    partial.write_bytes(b"incomplete")\n'
                              '    while True: time.sleep(10)\n'
                              'verifier.copy_failure_input = stalled\n'
                              'raise SystemExit(verifier.main())\n')
        result = run('failure-evidence-timeout', tamper, worker=evidence,
                     failure_kind='validation', timeout=15, evidence_timeout=.5)
        assert result['evidence_incomplete'] and 'failure_replay' not in result
        assert result['evidence_supervision']['timed_out']
        assert result['evidence_supervision']['timeout_phase'] == 'failure_copy'
        assert (directory / 'failure-evidence-timeout/failure-input.bin.partial').exists()
        assert not (directory / 'failure-evidence-timeout/failure-input.bin').exists()
        assert result['failure_input_source']['sha256'] == result['input']['sha256']

        # Ignore graceful termination: the parent's group KILL must finish it.
        stubborn = executable(directory / 'stubborn.py',
                              'import signal,time\nsignal.signal(signal.SIGTERM, signal.SIG_IGN)\n' + hang)
        run('ignores-terminate', stubborn, failure_kind='timeout', phase='audit_read')
        # Also force cleanup without the worker's finally/reap path: a leader
        # can exit first, or both leader and replay can ignore graceful TERM.
        orphan_prefix = (wrapper_prefix + 'import json,os,signal\n'
                         'original = verifier.subprocess.Popen\n'
                         'def launch(command, **kwargs):\n'
                         '    child = original(command, **kwargs)\n'
                         '    config = json.loads(pathlib.Path(sys.argv[2]).read_text())\n'
                         '    (pathlib.Path(config["output_dir"])/"abandoned-child.pid").write_text(str(child.pid))\n'
                         '    time.sleep(.1)\n')
        early_exit = executable(directory / 'leader-exits.py', orphan_prefix +
                                '    os._exit(23)\n'
                                'verifier.subprocess.Popen = launch\n'
                                'raise SystemExit(verifier.main())\n')
        run('leader-exits-before-child', stubborn, worker=early_exit, failure_kind='worker')
        stuck_worker = executable(directory / 'worker-ignores-terminate.py', orphan_prefix +
                                  '    signal.signal(signal.SIGTERM, signal.SIG_IGN)\n'
                                  '    while True: time.sleep(10)\n'
                                  'verifier.subprocess.Popen = launch\n'
                                  'raise SystemExit(verifier.main())\n')
        result = run('worker-and-child-ignore-terminate', stubborn, worker=stuck_worker,
                     failure_kind='timeout', phase='cpp_start')
        assert result['verification_supervision']['cleanup']['kill_sent']
        for name in ('leader-exits-before-child', 'worker-and-child-ignore-terminate'):
            assert absent(int((directory / name / 'abandoned-child.pid').read_text())), name
        cli = subprocess.run([sys.executable, str(ROOT / 'scripts/verify_itch.py'),
                              '--binary', str(no_output), '--input', str(source), '--symbol', 'TEST',
                              '--output-dir', str(directory / 'cli-timeout'), '--timeout-seconds', '1',
                              '--cleanup-timeout-seconds', '1', '--evidence-timeout-seconds', '2'],
                             capture_output=True, text=True, timeout=6)
        assert cli.returncode == 1, cli.stdout
        assert json.loads(cli.stdout)['failure_kind'] == 'timeout'
        receipt['cases'].append(dict(name='cli-timeout', expected='nonzero', exit_code=cli.returncode,
                                    verification='cli-timeout/verification.json'))
        receipt['status'] = 'passed'
    except BaseException as error:
        receipt.update(status='failed', error=f'{type(error).__name__}: {error}')
        raise
    finally:
        (directory / 'test-summary.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt, indent=2))


if __name__ == '__main__':
    main()
