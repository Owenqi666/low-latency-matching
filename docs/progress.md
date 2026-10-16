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
explanations without claiming that the user has already mastered them. No M2
networking, concurrency, queues or persistence work has been started.
