# M2 implementation and acceptance record

Technical acceptance snapshot: 2026-10-17. M2 implementation, Linux verification,
corrected formal measurement, profiling and clean-environment reproduction are
complete on the revisions recorded below. Delivery failures under overload are
measured outcomes, not omitted rounds. Final PR/main identities, archive hashes
and publication status are governed by the release's `acceptance.json`.
This record maps the service requirements to actual code and executable checks;
it does not substitute for that publication record. [M1 acceptance](acceptance.md) retains its original
scope. See the [service walkthrough](service_walkthrough.md) for demonstrations
and [measurement method](service_benchmark_method.md) for experiment boundaries.

## Observed verification and its limits

| Evidence | Observed state | Scope / limitation |
|---|---|---|
| Local macOS development suite | 93/93 CTest entries passed | `build/debug/ctest-m2-pre-pr.log` and `.xml`; this is a development checkout, not Linux or final-main acceptance |
| Frozen dirty Linux development snapshot | Debug 92/92; Release 93/93 passed | Ubuntu 24.04 arm64 QEMU/HVF guest, 4 virtual CPUs / 4 GiB; snapshot has a file-hash manifest, not a clean Git checkout |
| Linux ASan/UBSan and TSan on that snapshot | ASan/UBSan 92/92; TSan 92/92 passed, including real service groups | Actual project tests executed; this does not transfer sanitizer acceptance to a later source revision |
| Initial implementation revision / [PR #2](https://github.com/Owenqi666/low-latency-matching/pull/2) | `ce9e94f134f6d9894f67922586004c7650a32467` is the revision used for the long test and clean reproduction below | A PR merge-test SHA can differ from its head; final publication identities are recorded separately |
| Earlier PR CI runs | All four jobs passed in [38980042883](https://github.com/Owenqi666/low-latency-matching/actions/runs/38980042883) and [38980514661](https://github.com/Owenqi666/low-latency-matching/actions/runs/38980514661): Debug/ASan/TSan 93 each; Release 94 | Downloaded actual checkout SHAs are `09f7f5a8401ca655f26ccd7b87263e8509a510b1` and `e89db5f5a217953e967cb4d3ca2b37281bb76d66`; retained as earlier revision evidence |
| Follow-up PR CI at head `f58ff79` | All four jobs passed in [38981810190](https://github.com/Owenqi666/low-latency-matching/actions/runs/38981810190): Debug 95, Release 96, ASan/UBSan 95, TSan 95; no failures or skips | Actual tested merge checkout `f370b4e63a366556ba00cba116fc254e6ce296a1`; all required groups executed. Downloaded network smoke independently validated all 14 attempts |
| Corrected loadgen PR CI at head `eb0a109` | All four jobs passed in [38983432078](https://github.com/Owenqi666/low-latency-matching/actions/runs/38983432078): Debug 95, Release 96, ASan/UBSan 95, TSan 95; no failures or skips | Actual tested merge checkout `a4bcf6612769b95c17961e1313c49c33bed5a598`; downloaded network smoke (14 attempts) and core smoke independently passed. All four jobs observed fd 9→9 with ClientId 1→2 |
| Service long validation | 120,000 measured requests completed and reference-verified across three 40,000-command runs | Clean `ce9e94f`, macOS loopback, calibration mode; this is service correctness evidence, not formal Linux performance |
| Clean Linux reproduction | Interim `ce9e94f`: Release 94/94; fresh dependency downloads; two real CLI clients; seven-row network smoke | Clean checkout before/after; performed by an independent Codex subagent in the Linux VM, not a human or bare-metal host |
| Follow-up lifecycle coverage | Local pipeline 9/9, server lifecycle 2/2 and TCP service 10/10 passed; Linux reconnect/restart 2/2 passed; affected clean `f58ff79` Release groups passed 14/14 | All four follow-up CI jobs observed socket fd 9→9 while ClientId changed 1→2; partial-Trade abort, callback exception and process restart tests are included |
| Linux core measurement | Four workloads at C=1000, 100000 commands, five rounds per mode; all 40 rounds and independent summaries passed at clean `f58ff79` | [Core report](m2_core_measurements.md); synchronous core timing, separate from network/service latency and the earlier M1 platform |
| Linux profiling | Separate mixed workload completed and reference-verified at clean `85de7f3`; decoded user CPU samples and software counters retained | [Profiling record](m2_profiling.md); both attempts retained, no hardware-counter or formal timing claim |
| Earlier complete network matrix | Clean `f58ff79`: seven warmups plus 35 measured attempts; all 42 internally drained and reference-verified; guest and downloaded summaries agree | All 25 ordinary rounds met the normal sample target; all ten near/overload rounds failed delivery. Post-start schedule initialization disturbed arrivals; the entire earlier matrix is retained separately from corrected results |
| Corrected formal network matrix | Clean `eb0a109`: seven warmups plus 35 measured attempts; all 42 drained and reference-verified; guest and downloaded reports agree, `evidence_valid=true`, `all_runs_succeeded=false` | All 25 ordinary and five 45000/s near rounds succeeded. All five 80000/s overload rounds failed delivery. 34 rounds met the sample threshold, including four failed overload rounds: sample sufficiency is not success |
| Final publication | Separate release authority | Final PR/main checks, exact source identities, durable archive hashes and `m2-service` publication are bound by release `acceptance.json`; see the [evidence index](m2_evidence_index.md) |

The Linux development evidence is retained locally under
`build/m2-vm/evidence/dirty-validation-20261016T230725Z/`: `source-manifest.json`,
`source-sha256.txt`, `source-verification.log`, `environment.json`, and each preset's
configure/build/CTest logs and results. Its source base is M1 main
`b0293a36e4cff5a6ca4634c0df8af956f82ef2d3` plus the recorded dirty files. Local
93 and Linux 92/93 refer to different frozen source states/configurations; their
counts must not be relabeled as results for an untested later commit. These local
paths are evidence inventory, not published downloadable artifacts.

Long-validation raw inputs, samples, original/effective manifests and reference
results are under `build/m2-long-service/run-1/`. All three measured runs have
40,000 completed requests, no not-started/failed/unfinished requests, and a
successful service drain; 975 commands in cancellation-heavy are business
rejections. Setup and independent warmups are separate. The report's
`evidence_valid` and `all_runs_succeeded` are both true. The
[long-validation record](m2_long_validation.md) describes that scope.

The [clean-checkout record](m2_clean_checkout.md) indexes
`build/m2-vm/evidence/clean-ce9e94f/`. Its `summary.json` records verified fresh
dependency downloads without source overrides, 94 discovered/passed Release
tests with no skips, 14 warmup/measurement smoke attempts, a seven-command
two-client CLI demonstration, and slow-peer evidence. This is reproduction of
an interim implementation revision; the follow-up validation below covers the
later test changes without relabeling the original first-install evidence.

The follow-up PR artifact inspection is retained in
`build/m2-ci-f58ff79/inspection.json`, alongside all four downloaded job bundles.
The PR head is `f58ff79d49fd08c2bcb399ad989eb47ed0830a40`; each bundle's
`checkout-sha.log` identifies the tested merge checkout
`f370b4e63a366556ba00cba116fc254e6ce296a1`. Discovery/JUnit group validation found
no missing, failed or skipped tests. Each job's `fd-reuse.json` reports actual
Linux descriptor reuse with a new ClientId. The downloaded Release network
evidence was independently summarized again: all 14 declared warmup/measurement
attempts succeeded. These observations close the earlier follow-up-test CI gap;
later source/report commits and the final merged main follow the publication gates.

The corrected load-generator revision
`eb0a109b026c8ac9cf48d987163fad8751980047` has a separate complete inspection at
`build/m2-ci-eb0a109/inspection.json`. All four downloaded jobs identify tested
checkout `a4bcf6612769b95c17961e1313c49c33bed5a598`, pass required discovery/JUnit
groups without failures/skips, and record fd 9 reuse with ClientId 1→2. Independent
checks of the downloaded Release network and core smoke evidence passed. Only
loadgen and its test assertion changed; the service binary SHA-256 remained
`2348899014ba8415c1b4f6212541fb9ef61c6c5644af8631ae1a56a2812c4c23`.

Follow-up test evidence is in `build/agent-protocol/pipeline-followup.xml`,
`server-lifecycle-followup.xml` and `service-followup/`, plus
`build/m2-vm/evidence/followup-identity-restart-85de7f3/`. The Linux follow-up used
the existing `85de7f3` Release server and a separately hashed copy of the new test
script; it preserved the earlier clean-checkout record. Its `fd-reuse.json`
records the observed descriptor and identity transition. macOS runs retain the
same ownership/routing checks but explicitly record descriptor observation as
unavailable.

The first complete network matrix is retained under
`build/m2-measurement/m2-formal-f58ff79/`. Its frozen matrix has five rounds of
each of seven rows plus one separate warmup per row. Mixed, cancellation-heavy,
sweep, temporal burst and one-client mixed all completed their planned requests
in every round and met `normal_sample_target_met` (25/25). The 45000/s near
candidate completed only 8–11 of 450001 planned requests per round; the 80000/s
overload completed 12–20 of 800001. Those ten attempts failed delivery and did
not meet the sample target. All servers still drained admitted work successfully
and passed independent Reference verification. Evidence consistency and successful
delivery are separate outcomes; neither those tiny completed subsets nor the
short calibration establishes a sustainable 45000/s service rate. Every original
attempt remains available. Full results and limitations belong to the
[M2 report](m2_report.md), with the [rate-selection record](m2_rate_selection.md)
preserving the premeasurement decision.

Inspection after the run found that `loadgen` filled all scheduled timestamps
after setting measurement start. That O(N) initialization delayed the first
write by about 14 ms for the near row and 25 ms for overload, followed by
catch-up sends. Internal evidence remains valid, but this plan-size-dependent
arrival disturbance confounds capacity and tail-latency interpretation. The
correction in `eb0a109` computes schedule times from start plus prebuilt offsets
when needed, keeping the fixed rates and bounds unchanged. The full matrix was
then repeated; both revisions and every old attempt remain available. Core/server
measurements, profiling and long correctness retain their recorded source
identities and are not relabeled as runs of the later revision.

The corrected formal evidence is under
`build/m2-measurement/m2-formal-eb0a109/`. Independent summarization validated all
42 declared attempts, returned zero, and reproduced the guest report exactly.
Among the 35 measured attempts, the five ordinary rows and 45000/s near row
succeeded in every round (30/35). All five overload rounds failed delivery,
with 2–4 slow-client closures each; surviving connections continued to progress
in rounds with peers still open. All 42 servers drained admitted work and passed
Reference verification. The completed-sample threshold was met by 34 measured
rounds, including four failed overload attempts; it does not convert those
failures into successful runs or establish stable overload latency.

Across measured rounds, 8750030 requests were planned: 2993691 were not started
and 5756339 started. Of those started, 5754789 completed, 1550 failed and none
remained unfinished. Completed requests include 12195 business rejections.
The [M2 report](m2_report.md) gives per-round timing and losses, the earlier
matrix, VM limits and the separation between evidence validity and run success.

## T00–T10 mapping

| Task | Implemented artifacts and checks | Current acceptance state |
|---|---|---|
| T00: contracts and Linux toolchain | [Protocol field/length table](protocol.md), [architecture/default bounds](service_architecture.md), ADR [003](adr/003-pausable-service-output.md)/[004](adr/004-connection-identity-and-delivery.md), [pinned Boost 1.89.0 and GoogleTest](../cmake/Dependencies.cmake), separate `tsan` preset | Four Linux development configurations and four-job follow-up PR CI passed; fresh dependency installation and clean Release reproduction passed at `ce9e94f`. Final merged-source validation remains a release gate. |
| T01: pausable production engine | [MatchingEngine](../src/matching_engine.cpp), [pausable tests](../tests/pausable_engine_test.cpp), existing core/contract/differential tests; independent [ReferenceEngine](../reference/reference_engine.cpp) | Local and follow-up PR CI passed: per-event pauses, both-side 64-maker sweeps, Busy/output/sequence boundaries and reference snapshots. |
| T02: codec and framing | [protocol.cpp](../src/protocol.cpp), 12 [protocol tests](../tests/protocol_test.cpp), TCP fragmentation/error cases in [service tests](../tests/service_test.py) | Follow-up PR CI passed; golden bytes, exact lengths, all prefixes/chunk sizes, malformed headers and business-rejection precedence covered. |
| T03: SPSC pipeline and wake-up | [pipeline.cpp](../src/pipeline.cpp), 9 [pipeline tests](../tests/pipeline_test.cpp), [server lifecycle tests](../tests/server_lifecycle_test.cpp) | Follow-up PR CI passed including TSan: event capacity 1/2/4, 64 makers, both queues full, notification-before-wait, drain/abort and record limit. Clean `f58ff79` affected Release groups also passed. |
| T04: TCP Gateway and CLI | [server.cpp](../src/server.cpp), [CLI](../apps/client_main.cpp), `service_integration`, `client_cli` | Real sockets, multiple clients, independent wire peers, repeated RequestIds, idle maker reads and finite client drain exercised. See walkthrough for a runnable two-client sequence. |
| T05: routing and BBO | `MatchingServer::route`, final BBO in pipeline, `service_evidence` full-event test | 18 commands/three clients compare every routed event and BBO with independent reference prefix snapshots. Self-trade, owner checks, OrderId reuse and reconnect identity are exercised. Linux `/proc` evidence confirms actual fd reuse without identity reuse. |
| T06: backpressure and shutdown | `service_integration`, `PipelineTest.*`, `ServerLifecycle.*`; counters in [server_main.cpp](../apps/server_main.cpp) | Follow-up PR CI passed for slow peer/healthy progress, prefix drain, full-output abort and write deadline; also first-Trade abort with partial-book evidence, Gateway callback exception with abort/join, and a restarted process with an empty book. |
| T07: service differential and reproduction | [verify_service](../tools/service_verify.cpp), [service evidence tests](../tests/service_evidence_test.py), [actual-admission runner](../scripts/run_service_bench.py), M1 replay/shrinker | Small complete-stream comparison and negative evidence tests passed; 120,000 measured requests plus setup were verified against actual admission order at `ce9e94f`. This correctness run does not satisfy formal performance requirements. |
| T08: CI gates and failure reproduction | [workflow](../.github/workflows/ci.yml), [test-group checker](../scripts/check_test_groups.py), four presets, independent network summary | Recorded feature-PR runs passed all four jobs, including the corrected loadgen. [Controlled failure, downloaded-input replay and recovery](m2_ci_evidence.md) are retained. Final PR/main and archive identities belong to release `acceptance.json`. |
| T09: bounded open-loop measurement | [loadgen](../apps/loadgen_main.cpp), [contract tests](../tests/loadgen_test.py), generator/runner/[summary](../scripts/summarize_service_bench.py), [summary negative tests](../tests/service_benchmark_test.py) | Complete: [locked rates](m2_rate_selection.md), all 35 corrected formal rounds, [core measurement](m2_core_measurements.md), separate [profiling](m2_profiling.md) and [report](m2_report.md). All five overload failures and the earlier matrix are retained. |
| T10: reproduction and delivery | [README](../README.md), this mapping, walkthrough, [clean reproduction](m2_clean_checkout.md) and [evidence index](m2_evidence_index.md) | Clean Linux first installation, tests, real CLI demo and smoke passed at `ce9e94f`; later source changes passed recorded CI. Technical reproduction/reporting is complete; publication is governed by the release record. |

## One local and CI test entry point

The [workflow](../.github/workflows/ci.yml) uses the same presets as local runs.
On Linux, select `debug`, `release`, `asan-ubsan`, or separately `tsan`; TSan uses
Clang 18 in CI. Run each in its own build directory:

```sh
cmake --preset debug
cmake --build --preset debug --parallel 2
ctest --preset debug --show-only=json-v1 > build/debug/test-discovery.json
python3 scripts/check_test_groups.py --discovery build/debug/test-discovery.json \
  --require core --require pausable --require protocol --require concurrency \
  --require service --require client --require loadgen
ctest --preset debug --output-on-failure --no-tests=error \
  --output-junit "$PWD/build/debug/ctest.xml"
python3 scripts/check_test_groups.py --discovery build/debug/test-discovery.json \
  --junit build/debug/ctest.xml --require core --require pausable \
  --require protocol --require concurrency --require service --require client --require loadgen
```

For Release, add `--require benchmark` to both group checks; for TSan configure
with `-DCMAKE_CXX_COMPILER=clang++-18`. Discovery alone is insufficient: the final
check requires each discovered test to appear in JUnit without a skip/failure.
The workflow runs this check even after a test step fails and uploads logs and
reproduction files with `if: always()`. No sanitizer `continue-on-error` gate is
used. The Python suites contain several scenarios within one CTest entry, so
CTest totals are not counts of every individual assertion or wire scenario.

`service_integration` covers actual TCP behavior; `service_evidence` adds
independent replay and corruption checks; `client_cli` and `loadgen_contract`
exercise client completion/failure rules. `service_benchmark` verifies the runner
and rejects missing rounds, inconsistent counts, stale verification, altered
measurement windows/configuration and incorrect formal declarations. CI Release
also runs core smoke and seven-row network smoke with an independent summary.
It has no absolute latency or throughput gate.

The service harness uses port 0, a READY line, bounded deadlines and precise
child-process cleanup. Failures keep inputs, received frames, reports and stderr.
`--record-limit` bounds server admission/completion storage; exceeding it ends
that experiment explicitly. Actual admitted trace order is the reference input,
so cross-connection scheduling variation is not mistaken for a matching error.
Partially drained failures retain the completed prefix/current phase and never
receive a successful full-trace reference report.

## Technical acceptance and publication gates

| Requirement | Technical evidence | Publication gate |
|---|---|---|
| M1 semantic preservation | Existing suite plus synchronous/pausable/reference comparisons | Required latest PR and main suites must pass |
| Protocol correctness | Golden bytes, segmentation/coalescing, malformed/EOF and business-error cases; follow-up Linux PR CI passed | Final report-commit/main suites |
| Identity/routing and BBO | Cross-client/self-trade/reuse/owner tests, full-event BBO comparison; observed Linux fd reuse in all four follow-up CI jobs | Final report-commit/main suites |
| Bounded pause and progress | Tiny-queue sweeps, controlled wake boundary, slow peer with healthy progress; follow-up PR sanitizer suites passed | Final report-commit/main suites |
| Lifecycle and delivery loss | Prefix drain, first-Trade abort, consumer exception, restart and write deadline checks with separate loss counters; follow-up PR CI passed | Final report-commit/main suites |
| Failure localization | Retained remote fault artifacts, downloaded-trace reproduction, restored replay; verifier/summary negative tests and follow-up CI passed | Permanent evidence index/archive and final report-commit/main CI |
| Service correctness at scale | 120,000 measured requests with actual-order reference checks; setup/warmups separate | Retain raw checks in permanent evidence package |
| Credible measurement | Locked rates; corrected 35-round matrix with 30 successes and five overload failures; separate sample-threshold status; earlier matrix, core rounds and profiling retained | Archive all attempts and the report under their exact source identities |
| Fresh-environment reproduction | Independent clean Linux checkout at `ce9e94f`, fresh dependencies, 94 Release tests, real CLI and smoke | Preserve interim-source scope; validate later changes and final main |
| Verifiable version | PR #2 implementation branch | Latest required PR checks, merge, exact-main push checks/artifacts, permanent archive, then release |

Publication remains ordered: pass the latest PR checks and inspect their actual
checkout/artifacts; merge; verify the new main push at that exact SHA; save the
required evidence beyond the CI artifact retention period; only then publish
`m2-service`. Queued/running/cancelled jobs and M1 green checks do not satisfy
these gates. Later report-only commits must follow the same PR/main process and
state their relationship to the measured source revision.

The corrected implementation passed the `eb0a109` PR run; final report changes
and merged main are checked separately. The release evidence's `acceptance.json`
is authoritative for the exact final PR head, tested PR checkout, merged main
commit, workflow results and durable archive identities. Technical completion
here is not a claim that an unrecorded later commit passed. The
[release evidence index](m2_evidence_index.md) describes those publication records
without inventing this tracked document's own future commit SHA.
