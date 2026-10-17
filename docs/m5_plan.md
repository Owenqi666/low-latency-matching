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
| T01 | In progress | Capture rule and module scope fixed here; validate source framing and freeze synthetic generator settings |
| T02 | In progress | Independent C++ module and CLI under development |
| T03 | In progress | Independent Python decoding/reference and fixtures under development |
| T04 | Pending | Real prefix capture followed by independent semantic verification |
| T05 | Pending | Correctness-gated finite Linux matrix |
| T06 | Pending | Fresh public-source reproduction and report |
| T07 | Pending | Latest PR, normal merge and exact-main checks |
| T08 | Pending | Durable archives and verified Release |
