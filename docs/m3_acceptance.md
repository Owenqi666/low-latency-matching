# M3 acceptance record

Status: the primary candidate was rejected under the frozen tradeoff rule; technical validation and clean reproduction are complete on the recorded sources. Final publication is governed by the release acceptance record. A task is accepted only when the evidence
below identifies its actual source, environment and result. M2's published
release remains the baseline, not evidence that new M3 code has passed.

| Task | Required evidence | Current state |
|---|---|---|
| T00 | Baseline tag/release/source identity and preservation of existing work | Verified at `db9b74f4181a2dc4a50966c20080949c839bf73f`; baseline/plan recorded in `0526ed6` |
| T01 | Corrected-loadgen targeted Linux diagnosis; frozen hypothesis, parameters and adoption criteria | Complete: four diagnosed runs and four warmups passed delivery, drain and Reference; 203 copied files verified by SHA-256; [diagnosis](m3_diagnostics.md) and frozen plan select E1 |
| T02 | Minimal candidate and deterministic checks of its changed mechanism | Control `7b8fcd3`, candidate `b1ba98c`; only the frame limit differs. Both passed all 103 local Debug tests, including deterministic short-write/cancel and actual TCP multi-frame observations |
| T03 | Independent reference, full event/routing checks, finite long validation, four CI configurations and new evidence-checker negative cases | Both local Debug suites and both Linux Release suites passed. Candidate [CI 38988332237](https://github.com/Owenqi666/low-latency-matching/actions/runs/38988332237) passed 103/104/103/103 with downloaded evidence independently checked; formal long validation passed on both frozen paths (450,501 admissions in the first high-load round, including 500 setup commands) |
| T04 | All 70 measured A/B attempts and 14 warmups, individual reference/evidence checks, provenance, resource data and separate profiling | All 70 measurements and 14 warmups retained; guest summaries and pair check passed, all 84 drained and passed Reference. Host copied-file hashes passed for 1,618 files (4,612,638,661 bytes); full host revalidation reproduced all derived files byte-for-byte. Separate A/B profiling completed; 114 copied files verified and both host summaries reproduced byte-for-byte |
| T05 | Complete round comparison, regressions, adoption/rejection and reproducible candidate source | Reject batching: primary CPU/request median improves 14.68%, but single-client RTT p99 median increases 71.30%, violating the frozen 10% limit. Working-tree production frame limit restored to 1, identical to the measured control |
| T06 | Optional second experiment, only with independent diagnostic justification | Not applicable: no new core/allocation evidence justifies a second experiment; the complete negative E1 result satisfies experiment scope |
| T07 | Report, ADR, clean Linux reproduction, CLI/smoke and a representative paired reproduction | Fresh public Linux clone at control `7b8fcd3`, fresh dependencies, 104/104 Release tests, two real CLI clients, core and seven-row network smoke passed. Three short 45k/s pairs completed; 3,269 copied files and independent host checks passed. [Report](m3_report.md) records the short-run limits and equality of the restored production source to this control |
| T08 | Latest PR and exact-main CI artifact inspection, normal merge, durable hashes and published `m3-experiments` | [PR #3](https://github.com/Owenqi666/low-latency-matching/pull/3); final source, check, archive and publication identities belong to the [release acceptance record](https://github.com/Owenqi666/low-latency-matching/releases/download/m3-experiments/acceptance.json), not intermediate candidate green checks |

## Development observations

The initial one-frame observation/control snapshot passed all 103 discovered
macOS Debug tests, with required groups and JUnit checked. Logs are under
`build/m3-validation/control-local/`. This is a dirty development snapshot,
not acceptance of a later commit or the 16-frame candidate. Review then added
explicit production batch-limit evidence and shared loadgen resource records;
those changes need their own validation before freezing the control.

The completed control then passed all 103 tests again after those additions.
`build/m3-validation/control-final-local/` retains source-file SHA-256 values,
build and execution logs, discovery, JUnit and group validation. The only edits
after that test were acceptance/progress documentation. The new tests check
real production batch use as well as deterministic partial-write/close behavior;
the control uses only single-frame operations. Paired tests cover actual short
A/A scheduling, eleven corrupt evidence variants, restoration and retained
client-delivery failure, without claiming performance from smoke runs.

The candidate changes only `batch_max_frames` from 1 to 16 and also passed all
103 local Debug tests. `build/m3-validation/candidate-local/` retains its logs;
`source-binding.json` in the parent directory verifies the control's recorded
file hashes against commit `7b8fcd3` (only two post-test documentation changes)
and binds the candidate build to `b1ba98c`. In the actual slow-peer TCP test,
the control recorded only single-frame writes; the candidate recorded 998
three-frame writes and three two-frame writes. These functional observations
establish production-path coverage, not a formal performance result.

Both frozen commits were built in separate clean Linux worktrees with identical
Release settings and shared existing pinned dependency sources. Each passed
104/104 tests with all eight required groups. All 2,739 files per validation
bundle passed copied-file SHA-256 checks and host-side JUnit/group revalidation;
see `build/m3-linux-validation/host-validation.json`. This is not fresh dependency
installation evidence. The formal comparison explicitly shares the candidate's
loadgen and verifier binaries across both server builds.

Candidate PR [run 38988332237](https://github.com/Owenqi666/low-latency-matching/actions/runs/38988332237)
tested merge checkout `3fec7a70c07958f1706f8eec219948740bf8fbc9`, with parents
`db9b74f` and `b1ba98c`. Downloaded Debug/Release/ASan-UBSan/TSan artifacts passed
discovery/JUnit checks for 103/104/103/103 tests, without failures or skips. Each
included all seven send-queue tests and the real paired-evidence test. Independent
checks confirmed core smoke, all 14 network-smoke attempts, multi-frame production
writes and the paired corruption/restoration evidence. The complete inspection
is at `build/m3-ci/candidate-b1ba98c/inspection.json`; it does not substitute for
the later final-PR or merged-main checks.

The existing Linux VM disk was expanded from 12 to 24 GiB while shut down,
preserving its contents. On restart its root filesystem grew to 23 GiB with
about 14 GiB available. It still has four vCPUs, 4 GiB RAM and kernel
`6.8.0-147-generic`. Both formal variants ran after this same restart.

## Preserved contracts

The existing semantic, protocol, pausable matching, tiny-queue, slow-peer,
identity/routing and shutdown tests remain mandatory. A send-queue extraction
must preserve the conservative M2 written/discarded accounting, including a
callback that arrives after close. Complete still means a command's immediate
processing, not that a resting order's lifetime ended or a peer received data.

Each drained experiment must pass the independent actual-admission Reference
check. Small tests additionally compare complete event fields and routing.
Successful service long verification may reuse a formal run with at least
100,000 accepted-into-service commands; it does not require a duplicate run.

## Final evidence requirements

Before acceptance, inspect actual CTest discovery and JUnit execution, the
downloaded core/network smoke results and tested checkout for all four CI jobs.
The final PR's head and base must match its tested checkout; merged main needs
its own push run and artifact inspection. No previous green run transfers to
a different production/build revision.

The release record will distinguish measured source, final source, observational
baseline changes and any rejected candidate. Original plans and VM/SSH material
are excluded from public source and archives. All failed measurement attempts
remain evidence, even if a corrected run is necessary. Sample sufficiency,
server drain, client success and valid evidence are separate findings.
