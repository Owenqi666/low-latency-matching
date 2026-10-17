# Offline ITCH visible-book reconstruction

`itch_replay` reads one uncompressed Nasdaq BinaryFILE session from its start
and maintains the visible orders for one explicitly selected symbol. It is
independent of the matching service. It does not infer hidden orders, exchange
matching decisions, executions, priority or trading strategy.

The format sources are the [ITCH 5.0 specification](https://nasdaqtrader.com/content/technicalsupport/specifications/dataproducts/NQTVITCHSpecification.pdf)
and [BinaryFILE specification](https://nasdaqtrader.com/content/technicalSupport/specifications/dataproducts/binaryfile.pdf).
The two-byte big-endian frame length excludes the length field. Zero length is
the BinaryFILE terminator, not an ITCH payload. Numeric fields are big endian;
timestamps are six-byte nanoseconds since midnight, prices are integer units
of $0.0001, order quantities are u32 and aggregate quantities are u64.

## Supported messages

| Type | Payload bytes | Treatment |
| --- | ---: | --- |
| S | 12 | Session context; first payload must be O, no payload after C |
| R | 39 | Current-session symbol to stock-locate mapping |
| A / F | 36 / 40 | Add visible order; F retains attribution |
| E / C | 31 / 36 | Reduce shares, remove at zero; C reduces even if Printable=N and keeps the resting display price |
| X / D | 23 / 19 | Partial cancel / delete all remaining shares |
| U | 35 | Replace old reference with new total shares and price; inherit side and attribution |

Known non-book messages are counted and ignored after type, length and common
header validation: H25, Y20, L26, V35, W12, K28, J35, h21, P44, Q40, B19, I50,
N20 and O48. Their message-specific business fields are not interpreted or
claimed as a complete market-statistics ledger. P/Q/B do not add visible orders
or reverse visible-book changes. Unknown types fail before symbol filtering.

Only target-security order semantics are applied. Known other-security messages
are filtered after framing and common-header checks. Target additions require
the directory mapping. Invalid sides, duplicate active references, missing
references, overdraws, replacement conflicts, out-of-range prices and resource
limits fail with context. A locked or crossed visible book is not automatically
matched or rejected. No timestamp sorting is performed.

## CLI and outputs

```sh
cmake --preset release
cmake --build --preset release --parallel 2
build/release/itch_replay --input data/itch/golden.bin --symbol TEST \
  --output-dir build/itch-demo
python3 scripts/verify_itch.py --binary build/release/itch_replay \
  --input data/itch/golden.bin --symbol TEST --output-dir build/itch-golden-check
```

Use a new output directory for each run. Successful replay writes `summary.json`,
`orders.csv` and `levels.csv`. Orders sort by reference, bids by descending price
and asks by ascending price. Summary includes all/target/filtered message counts,
applied updates, ignored types, final BBO and explicit completion markers.
Errors exit nonzero and save `error.json` when the output directory is available.

Complete mode requires both S/C and the BinaryFILE terminator. `--prefix` permits
record-aligned EOF, still requires the initial S/O and target context, and never
accepts a partial length or payload. S/E is not the end of messages. Prefix mode
does not establish provenance by itself: retain the day-start acquisition record.
No target directory or no target updates is an error in either mode.

`--max-orders N` defaults to 1,000,000 active target orders. The CLI reads bounded
chunks (`--read-chunk-size`, default 65,536). `--audit-stdout` emits affected
orders/levels/BBO for each target update, full checkpoints (`--checkpoint-every`,
default 10,000 updates), and a mandatory final state. The Python verifier decodes
the raw input independently, compares this stream and the saved output files,
and records input SHA-256. The CLI's FNV-1a hash is a lightweight identity, not
a cryptographic checksum or proof of correctness.

## Boundaries and evidence

Golden bytes and hand-computed expectations are in `data/itch/`. Synthetic
workloads and the independent Python model are public. The planned long and
historical checks, finite Linux measurements and delivery status are tracked in
[the M5 plan](m5_plan.md); a runnable example is not final M5 acceptance.

The historical input is a continuous day-start prefix, not a whole trading day.
Raw historical bytes remain local while redistribution permission is unconfirmed.
CI uses only public synthetic fixtures. No realtime feed, network-session
recovery, mid-file empty-book reconstruction, multi-security service or
compression dependency is included.
