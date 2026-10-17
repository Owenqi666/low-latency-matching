#!/usr/bin/env python3
"""Capture one bounded, day-start BinaryFILE prefix from an official gzip URL.

The output is private research input, not automatically redistributable. This
tool checks framing and selection only; independent replay verifies semantics.
It deliberately does not claim whole-file gzip CRC or source checksum validation.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import urllib.request
import zlib


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', required=True)
    parser.add_argument('--symbol', required=True)
    parser.add_argument('--date', required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--target-updates', type=int, default=1000)
    args = parser.parse_args()
    if not args.url.startswith('https://emi.nasdaq.com/ITCH/'):
        parser.error('use the official Nasdaq ITCH archive')
    if not 1 <= len(args.symbol) <= 8 or args.target_updates < 2:
        parser.error('symbol length must be 1..8 and target-updates >= 2')
    args.output_dir.mkdir(parents=True, exist_ok=False)
    raw = args.output_dir / 'prefix.bin'
    receipt = args.output_dir / 'capture.json'
    record = dict(status='running', url=args.url, symbol=args.symbol, trading_date=args.date,
                  started_at_utc=datetime.now(timezone.utc).isoformat(),
                  compressed_budget=1024**3, raw_budget=256*1024**2,
                  compressed_bytes_read=0, retained_bytes=0, messages=0,
                  target_updates_requested=args.target_updates, session_complete=False,
                  source_gzip_crc_verified=False, source_whole_file_checksum_verified=False,
                  redistribution='Not established; keep raw prefix local.',
                  script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    types, target_types = Counter(), Counter()
    digest = hashlib.sha256()
    pending = bytearray()
    locate = None
    decoder = zlib.decompressobj(16 + zlib.MAX_WBITS)
    tail = b''
    stop = False
    try:
        request = urllib.request.Request(args.url, headers={'Accept-Encoding': 'identity'})
        with urllib.request.urlopen(request, timeout=30) as response, raw.open('xb') as output:
            record['response'] = {k:response.headers.get(k) for k in
                                  ('Content-Length','Last-Modified','ETag','Content-Type')}
            record['resolved_url'] = response.url
            while not stop:
                if not tail:
                    remaining = record['compressed_budget'] - record['compressed_bytes_read']
                    if not remaining:
                        record['end_reason'] = 'compressed_budget'
                        break
                    tail = response.read(min(65536, remaining))
                    record['compressed_bytes_read'] += len(tail)
                    if not tail:
                        record['end_reason'] = 'upstream_eof'
                        break
                pending.extend(decoder.decompress(tail, 262144))
                tail = decoder.unconsumed_tail
                consumed = 0
                while len(pending) - consumed >= 2:
                    size = int.from_bytes(pending[consumed:consumed+2], 'big')
                    if len(pending) - consumed < size + 2:
                        break
                    frame = bytes(pending[consumed:consumed+size+2])
                    if record['retained_bytes'] + len(frame) > record['raw_budget']:
                        record['end_reason'] = 'raw_budget'
                        stop = True
                        break
                    if not size:
                        record['end_reason'] = 'source_session_terminator'
                        stop = True
                        break  # Preserve a prefix, never append a fabricated terminator.
                    payload = frame[2:]
                    if record['messages'] == 0 and not (size == 12 and payload[0] == ord('S') and payload[11] == ord('O')):
                        raise ValueError('source does not start with an ITCH Start of Messages event')
                    if size < 11:
                        raise ValueError('payload is shorter than the common ITCH header')
                    kind = chr(payload[0])
                    types[kind] += 1
                    if kind == 'R' and size == 39 and payload[11:19].decode('ascii').rstrip() == args.symbol:
                        locate = int.from_bytes(payload[1:3], 'big')
                    if locate is not None and int.from_bytes(payload[1:3], 'big') == locate:
                        target_types[kind] += 1
                    output.write(frame)
                    digest.update(frame)
                    consumed += len(frame)
                    record['retained_bytes'] += len(frame)
                    record['messages'] += 1
                    record['last_timestamp_ns'] = int.from_bytes(payload[5:11], 'big')
                    changes = sum(target_types[k] for k in 'ECXDU')
                    updates = changes + sum(target_types[k] for k in 'AF')
                    if updates >= args.target_updates and changes and any(target_types[k] for k in 'AF'):
                        record['end_reason'] = 'frozen_target_lifecycle_cutoff'
                        record['status'] = 'captured_pending_semantic_verification'
                        stop = True
                        break
                del pending[:consumed]
        if record['status'] == 'running':
            record['status'] = 'insufficient_target_lifecycle'
    except Exception as error:
        record.update(status='failed', error=f'{type(error).__name__}: {error}')
    record.update(ended_at_utc=datetime.now(timezone.utc).isoformat(), types=dict(types),
                  target_types=dict(target_types), target_locate=locate,
                  prefix_sha256=digest.hexdigest(), prefix_path=raw.name,
                  complete_message_boundary=True,
                  upstream_decompressed_unretained_bytes=len(pending),
                  cutoff='First complete message with >= requested target updates, >=1 add and >=1 E/C/X/D/U; otherwise stop at the byte budget.')
    receipt.write_text(json.dumps(record, indent=2)+'\n')
    print(json.dumps(record, indent=2))
    return 0 if record['status'] == 'captured_pending_semantic_verification' else 1


if __name__ == '__main__':
    raise SystemExit(main())
