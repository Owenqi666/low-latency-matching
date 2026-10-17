# M3 acceptance record

Status: implementation in progress. A task is accepted only when the evidence
below identifies its actual source, environment and result. M2's published
release remains the baseline, not evidence that new M3 code has passed.

| Task | Required evidence | Current state |
|---|---|---|
| T00 | Baseline tag/release/source identity and preservation of existing work | Verified at `db9b74f4181a2dc4a50966c20080949c839bf73f`; baseline/plan recorded in `0526ed6` |
| T01 | Corrected-loadgen targeted Linux diagnosis; frozen hypothesis, parameters and adoption criteria | Complete: four diagnosed runs and four warmups passed delivery, drain and Reference; 203 copied files verified by SHA-256; [diagnosis](m3_diagnostics.md) and frozen plan select E1 |
| T02 | Minimal candidate and deterministic checks of its changed mechanism | One-frame control and seven deterministic send-queue tests pass local Debug; batch candidate will have a separate revision |
| T03 | Independent reference, full event/routing checks, finite long validation, four CI configurations and new evidence-checker negative cases | Control: 103 local Debug tests passed, including real TCP histogram checks, paired runs, eleven corrupt evidence cases and restoration. Candidate, Linux CI and long validation remain pending |
| T04 | All 70 measured A/B attempts and 14 warmups, individual reference/evidence checks, provenance, resource data and separate profiling | Not started |
| T05 | Complete round comparison, regressions, adoption/rejection and reproducible candidate source | Not started |
| T06 | Optional second experiment, only with independent diagnostic justification | Not started; not a completion prerequisite |
| T07 | Report, ADR, clean Linux reproduction, CLI/smoke and a representative paired reproduction | Not started |
| T08 | Latest PR and exact-main CI artifact inspection, normal merge, durable hashes and published `m3-experiments` | Not started |

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

The existing Linux VM disk was expanded from 12 to 24 GiB while shut down,
preserving its contents. On restart its root filesystem grew to 23 GiB with
about 14 GiB available. It still has four vCPUs, 4 GiB RAM and kernel
`6.8.0-147-generic`. Both formal variants will run after this same restart.

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
