# Milestone progress and acceptance

Status index updated on 2026-10-17. M4 and M5 have completed T00–T08, including
their final PR/main checks and publication verification. The entries below
identify the delivered revisions and link the evidence that closes the earlier
planning and prepublication records. Original taskbooks, acceptance records,
published assets and their hashes remain unchanged.

| Milestone | Delivered result | Progress and acceptance | Published revision |
|---|---|---|---|
| M4 | Fixed-slot experiment completed; retain list storage | [T00–T08](#m4-order-storage-experiment), [acceptance mapping](m4_acceptance.md), [evidence index](m4_evidence_index.md) | [m4-order-storage](https://github.com/Owenqi666/low-latency-matching/releases/tag/m4-order-storage), `9314cf0` |
| M5 | Offline ITCH decoding and single-security visible-book reconstruction delivered | [T00–T08](#m5-offline-itch-reconstruction), [acceptance mapping](m5_acceptance.md), [evidence index](m5_evidence_index.md) | [m5-itch-reconstruction](https://github.com/Owenqi666/low-latency-matching/releases/tag/m5-itch-reconstruction), `0b83195` |

See [historical pending items and their closure](#historical-pending-items-and-their-closure)
for unchecked boxes, preparation-time gates and receipt-upload states preserved
in older documents. Those states describe the time each record was written;
the later evidence has its own source and verification scope.

## M1 implementation progress

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

## M3 selective performance experiment

M3 execution started on 2026-10-17 from published `m2-service`,
`db9b74f4181a2dc4a50966c20080949c839bf73f`, on `feat/m3-experiments`.
The [experiment plan](m3_experiment_plan.md) separates the baseline, diagnosis,
candidate selection and final acceptance. Historical M2 measurements remain
historical evidence, not the new comparison control.

| Task | State | Evidence / next step |
|---|---|---|
| M3-T00 | Baseline verified | Local main, fetched origin/main and m2-service agree; published release and five asset hashes checked; existing local task-book ignore preserved |
| M3-T01 | Complete | Four diagnosed runs and four warmups verified; 203 copied raw files passed SHA-256 verification; [diagnosis](m3_diagnostics.md), frozen 16-frame/4096-byte plan and adoption rule |
| M3-T02 | Both variants locally verified | Control `7b8fcd3`, candidate `b1ba98c`, one-constant difference; both passed 103 Debug tests, including deterministic and actual TCP batch coverage |
| M3-T03 | Candidate CI and Linux Release passed | Each independent Release build passed 104 tests; candidate CI passed 103/104/103/103, downloaded checks/smoke/new-path evidence verified; formal long validation passed on both frozen paths |
| M3-T04 | Complete | All 70 measured attempts and 14 warmups retained. Guest independent checks passed; 1,618 copied files passed SHA-256 checks. Host full revalidation reproduced all derived files byte-for-byte. Separate A/B profiling and host revalidation passed; original profiler signal exits are retained |
| M3-T05 | Candidate rejected | CPU/request improves 14.68% at 45k/s, but single-client RTT p99 rises 71.30% in paired median, exceeding the frozen 10% limit. Production restored to one frame, identical to measured control |
| M3-T06 | Not applicable | No new core/allocation evidence justifies a second experiment; no extra optimization to force a positive result |
| M3-T07 | Technical reproduction and reporting complete | Fresh public Linux clone and dependency installation; 104/104 Release tests, two CLI clients, core/network smoke and three short 45k/s pairs passed; copied files and independent summaries checked. [Report](m3_report.md) states source identities and limits |
| M3-T08 | Separate final publication authority | [PR #3](https://github.com/Owenqi666/low-latency-matching/pull/3); latest PR, exact-main CI, permanent archives and public release are accepted only through the [release record](https://github.com/Owenqi666/low-latency-matching/releases/download/m3-experiments/acceptance.json) |

## M4 order-storage experiment

M4 T00–T08 are complete at published main
`9314cf077c3968d484c627aa1d7f7e51dfa28463`, merged through
[PR #4](https://github.com/Owenqi666/low-latency-matching/pull/4).
The fixed-slot candidate was rejected under the frozen adoption rule;
production retains the measured list control. Experiment completion does not
imply adoption or a production speedup.

| Task | Final state | Evidence |
|---|---|---|
| M4-T00 | Complete | Accepted M3 baseline `37220e1`; source and retained-evidence identities in the [evidence index](m4_evidence_index.md) |
| M4-T01 | Complete | [Frozen experiment plan](m4_experiment_plan.md) and [bounded diagnosis](m4_diagnostics.md) |
| M4-T02 | Complete | List control `97fdc6e` and slot candidate `4cf669f`; two-file candidate, direct regressions and source comparison in the [acceptance mapping](m4_acceptance.md) |
| M4-T03 | Complete | Both Linux Release sources passed 108 tests; independent Reference checks and four-configuration candidate CI passed; final delivery CI is recorded under T07 |
| M4-T04 | Complete | 25 core pairs / 100 timing intervals, 40 formal service runs / eight warmups, separate resource diagnostics and independent summaries in the [report](m4_report.md) |
| M4-T05 | Complete; candidate rejected | Cancel-heavy gain of 2.710% missed the frozen 5% threshold. [ADR 006](adr/006-fixed-order-storage.md) retains list storage and the original negative results |
| M4-T06 | Complete | Fresh public Linux checkouts and dependencies; 108 selected-path Release tests, two CLI clients, core/seven-scene network smoke and two short representative core pairs; [reproduction evidence](m4_evidence_index.md) |
| M4-T07 | Complete | [Final PR CI 39056679890](https://github.com/Owenqi666/low-latency-matching/actions/runs/39056679890), normal PR #4 merge and [exact-main CI 39057150654](https://github.com/Owenqi666/low-latency-matching/actions/runs/39057150654); both artifact sets downloaded and independently inspected |
| M4-T08 | Complete | [Release](https://github.com/Owenqi666/low-latency-matching/releases/tag/m4-order-storage), frozen archives, public download/replay and uploaded-receipt checks; evidence chain below |

The published [acceptance.json](https://github.com/Owenqi666/low-latency-matching/releases/download/m4-order-storage/acceptance.json)
binds the technical results and final CI identities. It intentionally retains
`prepublication_verified` and `m4_complete: false` from before publication.
[publication-verification.json](https://github.com/Owenqi666/low-latency-matching/releases/download/m4-order-storage/publication-verification.json)
records the actual tag, asset identities, public downloads and archive replay.
[completion-check.json](https://github.com/Owenqi666/low-latency-matching/releases/download/m4-order-storage/completion-check.json)
then closes the technical audit and publication-receipt upload check.
The retained workspace record `build/m4-delivery/release-final-state.json`
verifies the completion-check asset itself and records `m4_complete: true`
with no remaining required work. This local record is not a Release asset.

## M5 offline ITCH reconstruction

M5 T00–T08 are complete at published main
`0b83195b8da3584beedf4172a65a2c8add039203`, merged through
[PR #5](https://github.com/Owenqi666/low-latency-matching/pull/5).
The measured and freshly reproduced source is `7cea5df`; all 29 C++/CMake build
inputs and five measurement/reference tools match the delivered source.
Later changes added reports and post-run inspectors. Original matching and
network production behavior, including the M3/M4 rejection decisions, is retained.

| Task | Final state | Evidence |
|---|---|---|
| M5-T00 | Complete | Accepted M4 baseline `9314cf0`, preserved original production sources and source relationship in the [acceptance mapping](m5_acceptance.md) |
| M5-T01 | Complete | [Plan](m5_plan.md), [message/input scope](itch_scope.md) and [ADR 007](adr/007-independent-itch-reconstruction.md); bounded day-start historical capture and frozen workloads |
| M5-T02 | Complete | Independent decoder, reconstructor and CLI; [hand-maintained golden bytes and lifecycle](../data/itch/README.md) |
| M5-T03 | Complete | Independent raw-byte Python Reference; three streams each compare 800,000 target updates, 80 full checkpoints and final state; final CI passes 120/124/120/120 tests for Debug/Release/ASan-UBSan/TSan |
| M5-T04 | Complete within declared scope | AAPL day-start prefix: 1,042,864 messages, 1,000 target updates, four checkpoints and final state; retained overdraw negative and actual saved-command replay in the [report](m5_report.md) |
| M5-T05 | Complete | Three million-message inputs, decode/rebuild modes, all 30 measurements and six warmups, one real-prefix resource observation; [all rounds](benchmarks/m5_itch_rounds.md) |
| M5-T06 | Complete | [Fresh public Linux checkout and dependencies](m5_reproduction.md), 124 Release tests, two service CLI clients, ITCH golden/real/negative demonstrations and core/seven-scene network/ITCH smoke |
| M5-T07 | Complete | [Final PR CI 39064550936](https://github.com/Owenqi666/low-latency-matching/actions/runs/39064550936), normal PR #5 merge and [exact-main CI 39066718550](https://github.com/Owenqi666/low-latency-matching/actions/runs/39066718550); both artifact sets downloaded and independently inspected |
| M5-T08 | Complete | [Release](https://github.com/Owenqi666/low-latency-matching/releases/tag/m5-itch-reconstruction), frozen source/measurement/validation archives, actual downloads and independent replay; evidence chain below |

The published [acceptance.json](https://github.com/Owenqi666/low-latency-matching/releases/download/m5-itch-reconstruction/acceptance.json)
records T00–T07 and the frozen archives, with T08 still pending at its creation.
[publication-verification.json](https://github.com/Owenqi666/low-latency-matching/releases/download/m5-itch-reconstruction/publication-verification.json)
closes the tag/assets/download/replay checks: 179 source files match the final
commit, 122 measurement files and 44,717 validation files pass inventory checks,
three raw synthetic inputs pass independent Reference replay, and 18 validation
checks pass. The retained workspace `build/m5-delivery/final-state.json`
independently confirms the uploaded publication receipt's actual downloaded
bytes and records `m5_complete: true`, with T00–T08 passed. It is a local final
check, not an additional Release receipt.

M5 covers an offline, day-start, single-security visible book. The real target
prefix covers A/D/E; synthetic cases cover the remaining required types.
No whole-day/gzip-CRC validation, exchange matching or per-message p99 is claimed.
The shared-VM measurements establish a scoped batch-throughput baseline.

## Historical pending items and their closure

This table provides navigation from the original statements to their later
evidence. It does not edit historical checkboxes, receipt fields, original
taskbooks or frozen archives. Each CI result remains tied to its recorded SHA;
this documentation update does not transfer an old green check to a new revision.

| Historical statement | Later evidence that closes it |
|---|---|
| [Initial CI record](ci_evidence.md): unchecked T07 trace download/replay and failure-injection verification | [T07 trace evidence](ci_trace_evidence.md) records the isolated defect, downloaded failure inputs, exact replay, restored source and successful recovery. The initial assertion-only probe remains narrower evidence |
| [CI workflow revision](ci_evidence.md#m1-workflow-revision-awaiting-pr-verification): benchmark smoke pending T08 | [PR evidence](pr_ci_evidence.md) records the Release benchmark smoke and independent downloaded-result validation; the [M1 acceptance mapping](acceptance.md) records the completed automation gate |
| Same CI revision: feature-PR verification, normal merge and new-main checks unchecked | [Final PR CI 38972543169](https://github.com/Owenqi666/low-latency-matching/actions/runs/38972543169), [PR #1](https://github.com/Owenqi666/low-latency-matching/pull/1), [main CI 38972684082](https://github.com/Owenqi666/low-latency-matching/actions/runs/38972684082) and the [M1 release](https://github.com/Owenqi666/low-latency-matching/releases/tag/m1-baseline) bind delivered main `b0293a3` |
| [M4 acceptance](m4_acceptance.md) T07/T08, [evidence index](m4_evidence_index.md) publication checks, and release acceptance's `m4_complete: false` | The [M4 final progress and receipt chain](#m4-order-storage-experiment) records final PR/main inspection, actual publication/download/replay, completion-check upload and the local final check |
| M4 publication receipt says its own upload is pending | Published [completion-check.json](https://github.com/Owenqi666/low-latency-matching/releases/download/m4-order-storage/completion-check.json) closes that upload check; local `build/m4-delivery/release-final-state.json` separately verifies the completion-check asset |
| [M5 plan](m5_plan.md#progress) T07/T08, [report](m5_report.md) and [evidence index](m5_evidence_index.md) preparation-time pending states, and release acceptance's publication-pending T08 | The [M5 final progress and receipt chain](#m5-offline-itch-reconstruction) records the final PR/main evidence, published assets, actual download/replay and the local check of the uploaded publication receipt |
| Original local taskbooks retain “not started” text or unchecked completion lists | Their public acceptance mappings and the revision-specific release evidence above establish delivery. The original planning documents remain unchanged and local |

M3/M4 candidate rejection and M5's explicit scope limits are retained outcomes,
not reopened implementation tasks. Local final checks and authoritative inputs
remain in the workspace; the evidence indexes identify the durable public
archives and permitted data. Missing disposable extraction copies can be
restored using the retained storage instructions without repeating the experiments.
