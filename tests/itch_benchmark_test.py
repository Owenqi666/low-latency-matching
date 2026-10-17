"""Real-binary ITCH smoke and a few independently replayable evidence failures.

Usage: python3 itch_benchmark_test.py /path/to/bench_itch /path/to/itch_replay
Evidence remains under the build's itch-benchmark-evidence directory.
"""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from summarize_itch_bench import read, sha256, write  # noqa: E402


def invoke(command, log, expected=None):
    result = subprocess.run([str(part) for part in command], capture_output=True, text=True)
    log.write_text(result.stdout + result.stderr)
    log.with_suffix('.exit').write_text(str(result.returncode) + '\n')
    if expected is None:
        assert result.returncode == 0, (command, result.returncode, result.stdout, result.stderr)
    else:
        assert result.returncode != 0 and expected in result.stderr, (expected, result.returncode, result.stderr)
    return result


def main():
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    binary, replay = (Path(value).resolve() for value in sys.argv[1:])
    parent = binary.parent / 'itch-benchmark-evidence'
    parent.mkdir(exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix='benchmark-check-', dir=parent))
    valid = work / 'valid'
    invoke([sys.executable, ROOT / 'scripts/run_itch_bench.py', '--binary', binary, '--replay', replay,
            '--source', ROOT, '--messages', 2000, '--rounds', 1, '--output-dir', valid], work / 'run.log')
    report = read(valid / 'report.json')
    assert report['validation'] == 'passed' and report['mode'] == 'smoke'
    assert report['measured_intervals'] == report['warmup_intervals'] == 6
    assert len(report['rows']) == 6
    for row in report['rows']:
        sample = row['rounds'][0]
        assert sample['messages'] == 2000 and 0 < sample['target_updates'] < sample['messages']
        assert sample['traversals'] == 1 and sample['elapsed_ns'] > 0
        assert sample['input_read_ns'] > 0 and sample['output_write_ns'] > 0
        assert sample['peak_rss_after_timing_bytes'] > 0
        assert 'p99' not in sample
    # A relocated copy and its archived standalone checker must remain usable.
    restored = work / 'restored'
    shutil.copytree(valid, restored)
    invoke([sys.executable, restored / 'tool-evidence/scripts/summarize_itch_bench.py', restored], work / 'restored.log')
    assert read(restored / 'report.json') == report

    for name, expected in [('missing-round', 'missing or changed execution plan'),
                           ('changed-input', 'input identity mismatch'),
                           ('wrong-counts', 'benchmark/reference counts or bytes mismatch'),
                           ('fake-formal', 'formal matrix must retain')]:
        damaged = work / name
        shutil.copytree(valid, damaged)
        manifest = read(damaged / 'matrix-manifest.json')
        if name == 'missing-round':
            manifest['executed'].pop()
        elif name == 'changed-input':
            with (damaged / 'inputs/mixed/input.bin').open('ab') as stream:
                stream.write(b'\0')
        elif name == 'wrong-counts':
            entry = manifest['executed'][1]
            path = damaged / entry['directory'] / 'result.json'
            sample = read(path)
            sample['target_updates'] += 1
            write(path, sample)
            entry['result_sha256'] = sha256(path)
        else:
            manifest['mode'] = 'formal'
        write(damaged / 'matrix-manifest.json', manifest)
        invoke([sys.executable, ROOT / 'scripts/summarize_itch_bench.py', damaged], work / (name + '.log'), expected)
        assert not (damaged / 'report.json').exists() and not (damaged / 'report.md').exists()
        assert (damaged / 'inputs/mixed/input.bin').is_file()

    # A real framing failure retains its original bytes, stderr and exit code.
    truncated = work / 'truncated.bin'
    truncated.write_bytes((valid / 'inputs/mixed/input.bin').read_bytes()[:-3])
    invoke([binary, '--input', truncated, '--symbol', 'TEST', '--mode', 'rebuild',
            '--output', work / 'truncated-result.json'], work / 'truncated.log', 'truncated')
    assert not (work / 'truncated-result.json').exists()
    # Decode-only still enforces session boundaries while permitting an explicit prefix.
    raw = (valid / 'inputs/mixed/input.bin').read_bytes()
    prefix = work / 'prefix.bin'
    prefix.write_bytes(raw[:-16])  # Remove the final 14-byte S/C frame and zero marker.
    invoke([binary, '--input', prefix, '--symbol', 'TEST', '--mode', 'decode',
            '--output', work / 'prefix-rejected.json'], work / 'prefix-rejected.log', 'incomplete session')
    invoke([binary, '--input', prefix, '--symbol', 'TEST', '--mode', 'decode', '--prefix',
            '--output', work / 'prefix-result.json'], work / 'prefix.log')
    assert read(work / 'prefix-result.json')['messages'] == 1999
    after_end = work / 'after-end.bin'
    after_end.write_bytes(raw[:-2] + raw[:14] + b'\0\0')
    invoke([binary, '--input', after_end, '--symbol', 'TEST', '--mode', 'decode',
            '--output', work / 'after-end-result.json'], work / 'after-end.log', 'payload after ITCH End')
    write(work / 'test-result.json', dict(status='passed', smoke_intervals=6, independent_warmups=6,
                                        relocated_replay=True, evidence_failures=['missing-round', 'changed-input', 'wrong-counts', 'fake-formal'],
                                        real_framing_failure_retained=True, decode_prefix_session_checks=True))
    print(json.dumps(dict(status='passed', evidence=str(work))))


if __name__ == '__main__':
    main()
