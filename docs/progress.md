# M1 implementation progress

M1 technical implementation and reproduction acceptance are complete at source
revision `59a29316a8d91b33bcb5572438eb731a8bc0b96f`. Later delivery commits add
reports and evidence. Final publication, merge SHA and main push CI are recorded
in the [M1 release](https://github.com/Owenqi666/low-latency-matching/releases/tag/m1-baseline).
Original planning documents remain unchanged and local.

| Task | State | Evidence |
|---|---|---|
| T00 | Verified | Three presets, pinned GoogleTest, local builds; actual CI failure/recovery in ci_evidence.md |
| T01 | Verified | Value contracts, semantics, full hand-calculated events/snapshots; deliberately wrong oracle fails |
| T02 | Verified | Independent vector model; exact expectations and swap-delete FIFO coverage |
| T03 | Verified | map/list/hash book, explicit invariants, lifetime/index tests under sanitizers |
| T04 | Verified | Bid/ask limit matching, partial fills, multi-price sweeps, output boundaries |
| T05 | Verified | IOC, owner cancel, reject precedence, ID/request reuse, numeric/sequence boundaries |
| T06 | Verified | 40,000-command CI test and 1,000,000-command local check; 2,000-command price mutation reduced to 2 and permanently regressed |
| T07 | Verified | Debug 59 / Release 60 / ASan+UBSan 59 in actual PR CI; downloaded failure artifacts replayed; Release smoke and independent report validation |
| T08 | Verified | Four scenarios, two capacities, 100,000 commands, five rounds per mode; all 4,000,000 latency samples and earlier measurements retained |
| T09 | Verified | Independent fresh checkout, 60 tests, fixture/random replay, repeated short benchmark; README, two ADRs, report, learning guide and evidence index |

See [acceptance mapping](acceptance.md), [M1 report](m1_report.md), and
[evidence index](evidence_index.md). Learning exercises provide auditable
explanations without claiming that the user has already mastered them.

## M2 service implementation

Implementation started on 2026-10-16 from main `b0293a36e4cff5a6ca4634c0df8af956f82ef2d3`
on branch `feat/m2-service`. The local M2 task book defines T00–T10. This table
records implementation separately from observed verification; no M2 acceptance
is claimed before the corresponding evidence exists.

| Task | State | Evidence / next check |
|---|---|---|
| M2-T00 | Local runtime checked; final Linux acceptance pending | Boost 1.89.0 pinned, protocol/default capacities fixed; Linux Clang 18 clean/race TSan probes observed |
| M2-T01 | Local tests passed | Pausable production state machine and synchronous adapter; 8 focused tests plus existing M1 regression suite |
| M2-T02 | Local tests passed | 12 protocol cases, independent golden bytes, fragmented/coalesced frames and business rejection boundaries |
| M2-T03 | Local tests passed | 8 pipeline cases: tiny queues, 64-maker sweeps, double congestion, bounded records, wake/drain/abort |
| M2-T04 | Local integration passed | Real TCP service tests and independently encoded CLI peer tests; Linux/remote checks pending |
| M2-T05 | Local full-event comparison passed | 18 commands across three clients checked against independent Reference events, route lists and final-state BBO |
| M2-T06 | Local lifecycle cases passed | Slow peer closes while healthy peer progresses; timeout is nonzero; abort retains current admission and phase |
| M2-T07 | In progress | Actual-admission replay/digest verifier and corrupted-evidence negative cases; 100,000-command service validation pending |
| M2-T08 | In progress | CI includes independent TSan, real service/CLI/loadgen groups and network smoke; remote failure/recovery and final PR/main checks pending |
| M2-T09 | In progress | Bounded open-loop loadgen and runner implemented; independent summary validation in integration; formal Linux matrix/profiling pending |
| M2-T10 | Pending | Clean Linux reproduction, PR/main verification and M2 release |

Original planning documents remain local. Ordinary implementation decisions do
not expand the scope into persistence, custom queues, allocation optimizations
or additional network backends.
