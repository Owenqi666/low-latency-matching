# M5 offline ITCH reconstruction plan

M5 adds one offline BinaryFILE reader, ITCH decoder, single-security visible-book
reconstructor and CLI. It does not change the matching service or resurrect the
rejected M3/M4 candidates. The accepted baseline is `m4-order-storage`,
`9314cf077c3968d484c627aa1d7f7e51dfa28463`. Work starts on
`codex/m5-itch-reconstruction`; M4 remains complete.

## Fixed scope

Process one session and one selected symbol from the day start, in file order.
Implement S/R/A/F/E/C/X/D/U and an explicit known non-book message ignore table.
Unknown message types fail even for other securities. A bounded prefix is not a
complete session; a truncated frame is an error. Reconstruction uses order IDs
and price aggregates, not MatchingEngine or inferred executions. The independent
Python model decodes the original bytes itself.

The implementation uses no new package dependency, networking backend, allocator
framework or runtime engine selection. File/field/state validation occurs at
the boundary that owns it; invariant scans belong to verification and tests.

## Real source and fixed capture rule

Use `https://emi.nasdaq.com/ITCH/Nasdaq%20ITCH/12302019.NASDAQ_ITCH50.gz`,
trading date 2019-12-30, symbol AAPL. Starting at source byte zero, retain the
continuous uncompressed BinaryFILE prefix through the first complete message
with at least 1,000 target book updates, including at least one add and one
E/C/X/D/U. Stop earlier at the resource limit and record insufficient coverage.
The cumulative first acquisition budget is 1 GiB compressed bytes and 256 MiB
retained uncompressed prefix. No automatic retry or budget expansion.

The capture records response identity, read bytes, framing/cutoff, type counts
and prefix SHA-256. It does not validate the entire source gzip CRC or checksum.
Real source bytes stay local unless redistribution permission is established.
Public CI uses synthetic data only. Capture success is not semantic acceptance:
the original bytes must subsequently pass independent state comparison.

## Verification and timing

Use fixed independent golden bytes and hand-computed results, randomized
lifecycles, at least 100,000 target updates in a long differential run, and the
real prefix. Compare affected state per update and full state at checkpoints
and the end. Stream audit records to the verifier rather than retain millions
of duplicate JSON lines; retain input identity, failures and reproducible tools.

The formal synthetic matrix has mixed updates, cancel/replace, and multiple
levels/best-level removal, each exactly 1,000,000 messages. Freeze seeds,
type/target mix and working-set generation before measurement. The two timing
modes are in-memory framing/decoding and framing/decoding/reconstruction. Each
has one independent warmup and five recorded rounds. A single full traversal
per interval is the initial fixed setting; any bounded preflight adjustment
must be recorded before the formal batch, not selected after its results.
Reference, input I/O, construction, final snapshots and output I/O are outside
the measured loops. Report durations, all round rates, target update rates,
CPU/RSS and clock/environment limitations. There is no speedup requirement or
per-message p99 claim. Measure only after correctness passes, without concurrent
builds, compression or profiling. The real prefix gets one resource observation.

## Frozen synthetic generation

Generator v1 uses a fixed SplitMix64 sequence. The three formal inputs contain
exactly 1,000,000 payload messages each (the zero-length file terminator is not
a message): `mixed` seed `0x495443480501`, `cancel_replace` seed
`0x495443480502`, and `multilevel` seed `0x495443480503`. A separate
`long_verify` stream uses seed `0x495443480504` and 150,000 messages; its recorded
actual target-update count must be at least 100,000.

Each stream starts with S/O and TEST/OTHER directories and ends with S/C plus
the BinaryFILE terminator. Between these, each 100-slot cycle assigns 80 slots
to target updates, 10 to OTHER updates and 10 to known ignored P/Q/B/H messages.
The requested add:execute:cancel:delete:replace weights are respectively
30:20:20:10:20, 15:10:25:15:35 and 35:15:20:10:20; adds split between A/F and
executions between E/C. Legalisation forces an add for an empty population and
turns adds into deletes at capacity. The manifest records actual type counts.

Target/other capacities are 1,000/128 orders, shares range from 1 to 1,000, and
prices use center 1,000,000 with tick 100. Price choices per side are 32, 16
and 256 for the three scenarios. Every 2,000 target updates, multilevel drains
all orders at a selected current best bid or ask using consecutive target
deletes, alternating sides and recording completed best-level disappearances.
Equal timestamps deliberately occur; processing remains in file order. The
manifest binds parameters, actual counts, peak/final activity, generator hash
and input SHA-256. These are synthetic lifecycle inputs, not market data.

## Delivery gates

Extend existing four Linux CI configurations with an ITCH group and small
Release smoke; keep every original group and core/network smoke. Independently
check discovery/JUnit and downloaded evidence. Perform fresh public Linux
checkout/dependency/build reproduction. Then inspect the latest PR checks,
merge normally, inspect exact-main push checks, and publish
`m5-itch-reconstruction` with durable source/evidence archives and verified
downloads. Freeze archive contents before hashing; one publication receipt and
one local final check close delivery without recursive self-certification.

## Progress

| Task | State | Evidence or next step |
| --- | --- | --- |
| T00 | Baseline verified | Current local/remote main equal accepted M4; original documents and storage retained; local start receipt under build/m5-baseline |
| T01 | Scope frozen | Message contract in itch_scope.md; bounded real capture has 1,000 AAPL updates; synthetic parameters fixed above |
| T02 | Implemented; local checks passed | Independent C++ module/CLI, golden bytes and 14 C++ lifecycle tests; Linux CI pending |
| T03 | Local checks passed; remote pending | Independent raw-byte Python model; 120,000 target updates and 12 full checkpoints passed; local Release discovery/JUnit 124/124; four Linux configurations pending |
| T04 | Local semantic checks passed | Continuous real prefix: 1,042,864 messages, 1,000 target updates, 39 final orders/33 levels; four full checkpoints plus final state match; injected overdraw rejected by both implementations |
| T05 | Pending | Correctness-gated finite Linux matrix |
| T06 | Pending | Fresh public-source reproduction and report |
| T07 | Pending | Latest PR, normal merge and exact-main checks |
| T08 | Pending | Durable archives and verified Release |
