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
is claimed before the corresponding evidence exists. Technical implementation,
verification, formal measurement and reporting are complete on the revisions
below; final source/CI/publication identities are governed by release `acceptance.json`.

| Task | State | Evidence / next check |
|---|---|---|
| M2-T00 | Verified on recorded revisions | Pinned dependencies; four Linux configurations; [clean first installation](m2_clean_checkout.md) |
| M2-T01 | Linux/remote tests passed | Pausable state machine and synchronous adapter; independent Reference and M1 regression suite |
| M2-T02 | Linux/remote tests passed | 12 protocol cases, independent golden bytes, fragmented/coalesced frames and rejection boundaries |
| M2-T03 | Linux/remote tests passed | Tiny queues, 64-maker sweeps, double congestion, wake/drain/abort and first-Trade partial-abort regression passed in follow-up PR CI |
| M2-T04 | Verified on recorded revisions | Real TCP service, independently encoded CLI peer tests and two-client clean Linux demonstration |
| M2-T05 | Verified on recorded revisions | Full routed-event/BBO comparison; Linux observed fd 9 reuse with ClientId 1 to 2 |
| M2-T06 | Follow-up Linux/remote tests passed | Slow-peer isolation, finite drain, callback exception, partial sweep and actual process restart; all four follow-up CI jobs observed fd reuse with new ClientId |
| M2-T07 | Verified | [120,000 measured service commands](m2_long_validation.md), actual-admission Reference replay and negative evidence checks |
| M2-T08 | Verified | [Downloaded remote failure, exact replay and four-job recovery](m2_ci_evidence.md); corrected eb0a109 PR run 38983432078 passed Debug 95 / Release 96 / ASan 95 / TSan 95; publication gates recorded separately |
| M2-T09 | Verified with measured overload failures retained | [Locked rates](m2_rate_selection.md); corrected 35-round [report](m2_report.md): 30 successful runs, five failed overload runs, 34 sample-threshold passes. All attempts, earlier matrix, [core rounds](m2_core_measurements.md) and [profiling](m2_profiling.md) retained |
| M2-T10 | Technical reproduction and reporting complete | [Fresh public Linux checkout](m2_clean_checkout.md), walkthrough and [evidence index](m2_evidence_index.md); release `acceptance.json` binds final PR/main and archive/publication identities |

The detailed [acceptance mapping](m2_acceptance.md) distinguishes the revisions
and environments covered by each result. The corrected loadgen PR head is
`eb0a109b026c8ac9cf48d987163fad8751980047`; downloaded CI artifacts identify actual
tested merge checkout `a4bcf6612769b95c17961e1313c49c33bed5a598`. Required groups
executed without failures/skips; all 14 downloaded network smoke attempts and
core smoke passed independent validation. The corrected formal matrix's 42
attempts all drained and passed Reference checks, while five measured overload
runs failed delivery. Four of those failures still met the sample threshold:
sample sufficiency, run success and evidence validity are distinct. Final report
commits and main follow their own release checks; previous green results are not
transferred to a new SHA.

Original planning documents remain local. Ordinary implementation decisions do
not expand the scope into persistence, custom queues, allocation optimizations
or additional network backends.
