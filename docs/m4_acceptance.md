# M4 acceptance record

Status: technical experiment and clean reproduction verified; retain list
storage because the frozen core adoption rule failed. Final
PR/main and publication identities are governed by the release's
`acceptance.json` and `publication-verification.json`.
The accepted starting point is `m3-experiments` at
`37220e16fe0f05110c5f4ea112e4057bc55be122`.

| Task | Required evidence | State |
|---|---|---|
| T00 | Baseline/main/tag/release identity, preserved work and existing evidence | Verified: local/remote main and M3 push CI match the accepted source; prior publication/completion receipts pass. Only the local M4 taskbook ignore entry existed at start; development uses `codex/m4-order-storage` |
| T01 | Bounded allocation diagnosis and frozen hypothesis/inputs/decision rules | Complete: [plan](m4_experiment_plan.md) committed at `6b92335` before candidate implementation; [short macOS diagnosis](m4_diagnostics.md) validates three 2,000-command traces, all 16 artifact hashes and unchanged M3 production sources |
| T02 | One minimal slot candidate and direct regressions, frozen A/B sources | Complete: common list control `97fdc6e`, slot candidate `4cf669f`; only `include/llmatch/order_book.hpp` and `src/order_book.cpp` differ. Both pass all 105 local Debug and 108 local Release tests with discovery/JUnit checks |
| T03 | Independent Reference, long validation, complete tests and four remote CI configurations for candidate | Complete: local suites and [candidate CI](https://github.com/Owenqi666/low-latency-matching/actions/runs/39050889184) passed 105/108/105/105 with downloaded artifacts independently checked. Both fixed Linux Release sources passed 108 tests; 11,059 copied evidence files and source hashes verified. Both paths passed the formal 100,000-command core Reference checks |
| T04 | All core/service pairs, separate resource diagnostics, raw identities and independent revalidation | Complete: 25 core pairs / 100 intervals, 793 copied files verified and host summary equal except relocated directory fields. Six Linux diagnostics / 103 copied files verified. All 40 formal service runs and eight warmups deliver, drain and pass Reference; 941 files verified and all eight derived files reproduce byte-for-byte |
| T05 | Adopt/reject decision, all regressions/costs and selected production/source relation | Complete: reject the candidate for the failed cancel_heavy threshold; [ADR](adr/006-fixed-order-storage.md) and [report](m4_report.md) disclose all core/service effects and resource costs. Restored production and all 92 build/tool/test/input files equal measured control `97fdc6e` |
| T06 | Report, ADR, fresh Linux dependency/build reproduction, CLI/smoke and representative short pair | Complete: fresh public A/B clones and dependencies; selected A passes 108 Release tests, two CLI clients, core/seven-scene network smoke; two 2,000-command representative core pairs pass as smoke. All 5,947 copied files and tracked-source hashes verified; independent host JUnit, build, CLI and summary checks pass in `build/m4-clean-repro/host-revalidation/verification.json` |
| T07 | Latest PR check/artifact inspection, normal merge and exact-main push check/artifact inspection | Required final gate: actual final identities and inspection receipts are recorded in release acceptance.json; candidate CI alone is insufficient |
| T08 | Durable source/raw/validation archives, internal/external hashes, tagged Release and uploaded-asset verification | Required publication gate: archive checks and exact tag/asset checks are recorded in release acceptance.json and the post-upload publication-verification.json |

## Starting environment

The candidate CI tested merge checkout
`6f233a140e6a81619dd3660dc46ae84e1250103a`, whose parents are the accepted M3
main and candidate `4cf669f`. Downloaded artifacts were independently checked
for discovery/JUnit, required groups, pair-fixture failure preservation and
recomputation, one-frame production writes, fd reuse and core/seven-scene
network smoke. See `build/m4-ci/candidate-4cf669f/inspection.json`.
This candidate check does not substitute for final PR or merged-main checks.

The independent Linux Release builds used clean public-source checkouts and
the same GCC settings, reusing retained pinned dependency source trees. Both
passed all 108 tests. `build/m4-linux-validation/host-validation.json` records
copied-file hash verification and independent host JUnit/source checks. This
is not the separate T06 fresh-dependency reproduction.

The existing M2/M3 VM was stopped when M4 began: localhost SSH refused the
connection and no QEMU process existed. It was restarted using its existing
disk/configuration, without replacing prior evidence. The running guest reports
Linux `6.8.0-147-generic` on aarch64, with a 23 GiB filesystem and about 7.5 GiB
free at startup. Formal host/guest capture is retained with the measurements;
T06 uses new project/dependency/build directories on this existing system,
not a new operating-system installation.

## Evidence rules

The frozen core rule is not met: mixed improves 5.241% (5/5 pairs), while
cancel_heavy improves 2.710% (4/5 pairs), below its required 5% median gain.
Sweep, clustered and near_full_reuse improve 6.222%, 3.803% and 1.978%.
These are paired `B/A - 1` medians, not ratios of group medians. All service
formal runs pass delivery/sample/drain checks, and the four RTT p99 paired
medians meet the +10% bound. Sweep service-completion p99 nevertheless rises
26.438%; mixed_4 has a 69.571% individual RTT p99 increase. These outcomes
remain in the report and do not waive the failed core threshold.

The common measurement/test baseline passed all 105 discovered macOS Debug
tests and all 108 discovered Release tests, with JUnit and required-group
checks passing without skips. Release includes the allocation-probe contract,
core-pair corruption/replay tests and the existing benchmark pipeline; the
service-pair tests exercise the four-row M4 manifest as a short smoke.
Logs and discovery/JUnit records are under
`build/m4-validation/control-debug/` and `control-release/`. These are local
common-baseline checks, not candidate, Linux or remote-CI acceptance.

The common baseline preserves the M3 production sources. It adds measurement
tools and directly related regression coverage before the two-file storage
candidate is applied. Actual frozen commits and source hashes are recorded
in validation evidence; formal results and their independent checks are linked
from the [evidence index](m4_evidence_index.md).

Adoption thresholds are not completion thresholds. A correctly rejected
candidate can fulfill M4, but T05-T08 still require actual evidence. Historical
M3 checks do not validate new code. Each result must name actual source,
binary/tool/input identity and scope; smoke is not formal performance evidence.
Actions artifact retention alone is not permanent publication.
