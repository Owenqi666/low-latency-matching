# M4 acceptance record

Status: in progress. No candidate, performance or delivery result is claimed.
The accepted starting point is `m3-experiments` at
`37220e16fe0f05110c5f4ea112e4057bc55be122`.

| Task | Required evidence | State |
|---|---|---|
| T00 | Baseline/main/tag/release identity, preserved work and existing evidence | Verified: local/remote main and M3 push CI match the accepted source; prior publication/completion receipts pass. Only the local M4 taskbook ignore entry existed at start; development uses `codex/m4-order-storage` |
| T01 | Bounded allocation diagnosis and frozen hypothesis/inputs/decision rules | In progress: [plan](m4_experiment_plan.md) records scope, fixed matrix and thresholds before candidate implementation; diagnosis pending |
| T02 | One minimal slot candidate and direct regressions, frozen A/B sources | Pending |
| T03 | Independent Reference, long validation, complete tests and four remote CI configurations for candidate | Pending |
| T04 | All core/service pairs, separate resource diagnostics, raw identities and independent revalidation | Pending |
| T05 | Adopt/reject decision, all regressions/costs and selected production/source relation | Pending |
| T06 | Report, ADR, fresh Linux dependency/build reproduction, CLI/smoke and representative short pair | Pending |
| T07 | Latest PR check/artifact inspection, normal merge and exact-main push check/artifact inspection | Pending |
| T08 | Durable source/raw/validation archives, internal/external hashes, tagged Release and uploaded-asset verification | Pending |

## Starting environment

The existing M2/M3 VM was stopped when M4 began: localhost SSH refused the
connection and no QEMU process existed. It was restarted using its existing
disk/configuration, without replacing prior evidence. The running guest reports
Linux `6.8.0-147-generic` on aarch64, with a 23 GiB filesystem and about 7.5 GiB
free at startup. Formal environment capture and fresh-install evidence are
still pending; this restart is not a new clean installation.

## Evidence rules

Adoption thresholds are not completion thresholds. A correctly rejected
candidate can fulfill M4, but T05-T08 still require actual evidence. Historical
M3 checks do not validate new code. Each result must name actual source,
binary/tool/input identity and scope; smoke is not formal performance evidence.
Actions artifact retention alone is not permanent publication.
