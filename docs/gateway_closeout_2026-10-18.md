# Gateway acceptance closeout — 2026-10-18

Status: **historical experiment and archive verified; local registration repair
and default/extended/switch-off acceptance passed; current-source CI and remote
delivery pending**.
This is the pre-merge documentation snapshot for [PR #7](https://github.com/Owenqi666/low-latency-matching/pull/7).
Only the results recorded below are complete. The PR delivery record will bind
the final head, actual CI checkout, merge/main CI and final local synchronization
after those checks finish. No merge, release or new performance improvement is claimed here.

## Baseline and scope

The acceptance baseline is branch `codex/gateway-optimization`, commit
`e94d9f9592534a4058486ebf506576c54d4e0eaf`. The closeout separately records the actual tested revision and worktree diff.
Evidence is local-only under `build/gateway-closeout-r04wqppx/`; these raw files
are intentionally not committed. CI logs/artifacts and delivery identities are
also linked from PR #7. These `build/` paths are
local-only evidence references, not files published in the Git repository.
Its `baseline/record.json`
records tool versions, the taskbook hash and five copied prior-review files; all
five copied SHA-256 values match. Those durable baseline copies replace any
dependency on the original temporary review path.

Two issues prompted this work:

1. Two `DISABLED_Extended*` deep-book cases remained in default CTest discovery.
   CTest could exit successfully while `scripts/check_test_groups.py` rejected
   disabled entries and the discovery/JUnit contract. The historical Linux
   result of 136 passes plus two disabled registrations therefore did not prove
   that the existing default CI entry passed.
2. The report simultaneously said G09 pending and complete. Historical local
   experiment/archive verification, revised-source acceptance and remote
   delivery must have distinct states.

Commit `2aa0826fe2de843800ad2426f7c4b1a6841a1620` limits the code diff to
`CMakeLists.txt` and
`tests/deep_book_test.cpp`: add `LLMATCH_EXTENDED_TESTS` default `OFF`, define
its private macro only for the enabled deep-book target, and conditionally
compile the two normally named `Extended*` cases. Preserve all five routine
tests, the four C10k seeds, full comparison logic, discovery labels/timeouts and
the unchanged strict checker. README, the Gateway report/plan/index/ADR and this
record explain the new entry; `docs/progress.md` only gains navigation.
The code commit changes two files, with nine insertions and two deletions;
`baseline/fix.patch` retains the change. No production code, strict checker or
CI workflow changes are included. All three R02 phases passed at
2026-10-18T17:46:05.070322Z; `local-result.json` records `status=passed` and
identical source-before/source-after maps.

## Acceptance ledger

| Item | Required evidence | Current result |
|---|---|---|
| R00 baseline | New evidence root; branch/HEAD/status/diff; relevant untracked hashes; retained review logs | Recorded in `baseline/`; five prior failure files hash-verified, taskbook copy/hash retained |
| R01 minimal registration repair | Exact diff and repaired-source identity; checker/workflow/production behavior unchanged | Verified at 2aa0826; exact two-file diff reviewed and all R02 phases passed |
| R02-A default full Release | Fresh cache confirms default OFF; discovery and JUnit checks exit 0 / valid=true; all discovered tests execute, with no disabled/skipped/missing/extra entries; routine C1k cases remain | Passed: 136 discovered/executed, both checks valid=true, five routine deep-book cases and no disabled/skipped entries |
| R02-B explicit extended entry | Separate build, option ON; seven deep-book discoveries and exactly two selected Extended tests; both status=run; four C10k inputs/configs/metadata/coverage/comparisons complete and passed | Passed: seven discovered, two selected/executed normally, all four C10k cases retain six hashed files and successful comparisons |
| R02-C ON→OFF | Same extended build reconfigured OFF and rebuilt; discovery returns five routine cases, no Extended/disabled entries | Passed: exactly five routine cases, zero Extended and zero disabled |
| R03 documentation | Current README CTest entry; consistent historical/new acceptance states; old data/thresholds/decisions preserved | Updated with actual local results; current CI and remote states explicitly pending at this documentation snapshot |
| R04 PR CI | PR URL and head SHA; Actions run URL, actual checkout SHA, Debug/Release/ASan-UBSan/separate TSan results and required Release smoke | PR #7 created after the remote refresh; final documentation-head CI pending |
| R04 main delivery | Actual merge/main SHA and its CI checkout/result; final local branch/status/synchronization | Pending remote verification |
| R05 closeout | Final tested source/diff, evidence index, result fields and delivery boundary reconciled | Local record and index complete; final remote delivery evidence pending R04 |

The default run used repaired source `2aa0826fe2de843800ad2426f7c4b1a6841a1620`,
CMake 4.4.4, Ninja 1.13.2, Apple Clang 21 and Python 3.14.8. Explicit dependency
source overrides reused pinned Boost 1.89.0 and GoogleTest 1.17.0 under
`build/debug/_deps`. `default/discovery-check.json` and
`default/execution-check.json` both report `valid=true`, with 136 discovered and
136 passed. These are macOS results, not Linux CI. The initial evidence driver
then incorrectly expected `metadata.json` instead of the actual `metadata.txt`;
its original script and `local-initial-result.json` are retained.
The local `build/gateway-closeout-r04wqppx/driver-note.md` records how
`resume_local.py` validates existing outputs and continues only the unstarted
extended/switch-off phases, without rerunning default tests. That continuation
completed successfully. Extended discovery contains seven deep-book tests and
two selected normal `Extended*` tests, both executed; four C10k cases each retain
`input.trace`, `input.trace.meta`, `config.txt`, `metadata.txt`, `coverage.csv` and
`comparison.txt` with SHA-256 records. ON→OFF discovery returns exactly the five
routine cases, with no Extended or disabled registrations.

No fixed total test count replaces discovery/execution equality. The extended
two-test subset is not paired with an unrelated full-suite discovery to claim
all groups passed. ON→OFF checks registration refresh and does not itself
require another full-suite run. Corresponding valid remote four-configuration
evidence need not be duplicated by another local sanitizer matrix.

The [README](../README.md) uses default OFF for the routine build and a separate
`build/gateway-extended` with ON for the normal CTest `Extended*` entry. Old
`--gtest_also_run_disabled_tests` invocations in original raw receipts are
historical commands, not the current operating instructions.

## Revision and delivery binding

| Identity / result | Recorded value |
|---|---|
| Acceptance baseline | `e94d9f9592534a4058486ebf506576c54d4e0eaf` |
| New evidence directory | `build/gateway-closeout-r04wqppx/` |
| Repaired/tested source | `2aa0826fe2de843800ad2426f7c4b1a6841a1620`; `baseline/fix.patch` and `baseline/tested-working-diff.patch` preserve the recorded source/worktree scope |
| Default receipts | `default/discovery-check.json`, `default/execution-check.json`, `default/ctest.xml`: passed |
| Extended / switch-off receipts | `extended/deep-book-discovery.json`, `extended/selected-discovery.json`, `extended/ctest.xml`, `extended/deep-book/`; `switch-off/deep-book-discovery.json`: passed |
| Combined local receipt | `local-result.json`, status=passed, finished 2026-10-18T17:46:05.070322Z, source-before/source-after equal |
| PR URL and head SHA | [PR #7](https://github.com/Owenqi666/low-latency-matching/pull/7); final documentation-head SHA is recorded in its delivery record after commit |
| PR Actions URL and actual checkout SHA | Pending current-version CI; a merge-preview checkout may differ from PR head |
| Merge/main SHA and main Actions checkout/result | Pending post-merge verification |
| Final local branch, HEAD, worktree and synchronization | Pending final inspection |

The coordinator refreshed remote state at 2026-10-18T17:44:07.287145Z:
`baseline/remote-before.json` records main at
`4abdccc57037c69ded2247ac9a88894a03a1543b` and no existing PR for this branch.
Successful run `39072618339` covers that old main only. PR #7 delivers the full Gateway branch difference, with its current head and actual
checkout recorded separately. Local Release success cannot replace the four
current Linux CI configurations. PR and main results remain distinct. This document intentionally records the
pre-merge snapshot; the final main CI evidence can be added to the PR delivery record and delivery message
without making a commit merely to write its own SHA into this file. Any actual
subsequent source/document commit still needs its corresponding delivery/CI check.

## Preserved performance and archive boundary

The performance data remain bound to frozen A
`7d9d7dc0a6ab386d2d381f401ce644e621e33d33`, B
`56d5c71e7daec7631272dbc7b10a0f430f3381e0` and G06 tools
`f6765b5c0e096428115980c047f56e2a9190146f`. The complete 35 pairs and 14 warmups
produce valid **reject batch16; retain batch1**: near CPU/completed improves
6.402527%, below 10%; RTT p99 and scheduled-to-complete p99 regress 13.717391%
and 10.094805%, above their 10% limits. B delivers 35/35 and A 28/35; retaining
A does not imply superior A delivery. G07 remains not triggered.

The [report](gateway_report.md), [ADR 008](adr/008-retain-single-frame-gateway.md)
and [evidence index](gateway_evidence_index.md) retain all failed outcomes and
the old source boundaries. This closeout adds build-registration/test-enablement
and documentation evidence for the repaired source; it does not transfer old
G09 results into current-version CI or make a new performance claim. If the
actual diff changes a production path, workload, sampling rule or frozen
parameter, reassess only the affected evidence before continuing.

The original archive `build/gateway-final-archive-01/gateway-raw.tar`, SHA-256
`997b2edac92038b7aed1c4e2353cd67b56ad4eef1284756271313f0c88e6b2b2`, and its
verification receipt remain unchanged. A fresh read-only checksum in
`build/gateway-closeout-r04wqppx/archive-preservation.json` confirms that same
SHA and 5,675,490,816-byte size, without regenerating the archive.
New closeout evidence is indexed
separately; the large archive is not regenerated to include these documents.

One shared local VM, unexplained near-tail regressions and A pressure-delivery
failures remain experimental limitations. This registration repair does not
claim to solve them. No new release/tag, admission policy, waiting policy,
personal-contribution claim or CV revision is part of this closeout.
