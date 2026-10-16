# M2 implementation and acceptance record

Status snapshot: 2026-10-17. M2 implementation and verification are in progress.
This record maps the service requirements to actual code and executable checks;
it does not mark M2 delivered. [M1 acceptance](acceptance.md) retains its original
scope. See the [service walkthrough](service_walkthrough.md) for demonstrations
and [measurement method](service_benchmark_method.md) for experiment boundaries.

## Observed verification and its limits

| Evidence | Observed state | Scope / limitation |
|---|---|---|
| Local macOS development suite | 93/93 CTest entries passed | `build/debug/ctest-m2-pre-pr.log` and `.xml`; this is a development checkout, not Linux or final-main acceptance |
| Frozen dirty Linux development snapshot | Debug 92/92; Release 93/93 passed | Ubuntu 24.04 arm64 QEMU/HVF guest, 4 virtual CPUs / 4 GiB; snapshot has a file-hash manifest, not a clean Git checkout |
| Linux ASan/UBSan and TSan on that snapshot | ASan/UBSan 92/92; TSan 92/92 passed, including real service groups | Actual project tests executed; this does not transfer sanitizer acceptance to a later source revision |
| Initial implementation revision / [PR #2](https://github.com/Owenqi666/low-latency-matching/pull/2) | `ce9e94f134f6d9894f67922586004c7650a32467` is the revision used for the long test and clean reproduction below | Latest PR/main checkout and artifacts still require final acceptance; a PR merge-test SHA can differ from the head |
| Two completed PR CI runs | All four jobs passed in [38980042883](https://github.com/Owenqi666/low-latency-matching/actions/runs/38980042883) and [38980514661](https://github.com/Owenqi666/low-latency-matching/actions/runs/38980514661): Debug/ASan/TSan 93 each; Release 94 | Downloaded actual checkout SHAs are `09f7f5a8401ca655f26ccd7b87263e8509a510b1` and `e89db5f5a217953e967cb4d3ca2b37281bb76d66`; follow-up tests still require a new CI run |
| Service long validation | 120,000 measured requests completed and reference-verified across three 40,000-command runs | Clean `ce9e94f`, macOS loopback, calibration mode; this is service correctness evidence, not formal Linux performance |
| Clean Linux reproduction | Interim `ce9e94f`: Release 94/94; fresh dependency downloads; two real CLI clients; seven-row network smoke | Clean checkout before/after; performed by an independent Codex subagent in the Linux VM, not a human or bare-metal host |
| Follow-up lifecycle coverage | Local pipeline 9/9, server lifecycle 2/2 and TCP service 10/10 passed; Linux reconnect/restart 2/2 passed | Linux observed old/new socket fd 9 while ClientId changed 1→2. Latest-source CI remains pending |
| Formal measurements and release | Not yet accepted | No formal performance conclusion or `m2-service` release claim follows from the checks above |

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
an interim implementation revision; new test-only changes still need their own
validation before final delivery.

Follow-up test evidence is in `build/agent-protocol/pipeline-followup.xml`,
`server-lifecycle-followup.xml` and `service-followup/`, plus
`build/m2-vm/evidence/followup-identity-restart-85de7f3/`. The Linux follow-up used
the existing `85de7f3` Release server and a separately hashed copy of the new test
script; it preserved the earlier clean-checkout record. Its `fd-reuse.json`
records the observed descriptor and identity transition. macOS runs retain the
same ownership/routing checks but explicitly record descriptor observation as
unavailable.

## T00–T10 mapping

| Task | Implemented artifacts and checks | Current acceptance state |
|---|---|---|
| T00: contracts and Linux toolchain | [Protocol field/length table](protocol.md), [architecture/default bounds](service_architecture.md), ADR [003](adr/003-pausable-service-output.md)/[004](adr/004-connection-identity-and-delivery.md), [pinned Boost 1.89.0 and GoogleTest](../cmake/Dependencies.cmake), separate `tsan` preset | Four Linux development configurations passed; fresh dependency installation and clean Release reproduction passed at `ce9e94f`. Final-source validation remains a release gate. |
| T01: pausable production engine | [MatchingEngine](../src/matching_engine.cpp), [pausable tests](../tests/pausable_engine_test.cpp), existing core/contract/differential tests; independent [ReferenceEngine](../reference/reference_engine.cpp) | Local tests passed: per-event pauses, both-side 64-maker sweeps, Busy/output/sequence boundaries and reference snapshots. Final Linux/remote gate remains open. |
| T02: codec and framing | [protocol.cpp](../src/protocol.cpp), 12 [protocol tests](../tests/protocol_test.cpp), TCP fragmentation/error cases in [service tests](../tests/service_test.py) | Local and frozen Linux development tests passed; golden bytes, exact lengths, all prefixes/chunk sizes, malformed headers and business-rejection precedence covered. |
| T03: SPSC pipeline and wake-up | [pipeline.cpp](../src/pipeline.cpp), 9 [pipeline tests](../tests/pipeline_test.cpp), [server lifecycle tests](../tests/server_lifecycle_test.cpp) | Local tests passed: event capacity 1/2/4, 64 makers, both queues full, notification-before-wait, drain/abort and record limit. Linux snapshot passed real project TSan; later tests need latest-source Linux execution. |
| T04: TCP Gateway and CLI | [server.cpp](../src/server.cpp), [CLI](../apps/client_main.cpp), `service_integration`, `client_cli` | Real sockets, multiple clients, independent wire peers, repeated RequestIds, idle maker reads and finite client drain exercised. See walkthrough for a runnable two-client sequence. |
| T05: routing and BBO | `MatchingServer::route`, final BBO in pipeline, `service_evidence` full-event test | 18 commands/three clients compare every routed event and BBO with independent reference prefix snapshots. Self-trade, owner checks, OrderId reuse and reconnect identity are exercised. Linux `/proc` evidence confirms actual fd reuse without identity reuse. |
| T06: backpressure and shutdown | `service_integration`, `PipelineTest.*`, `ServerLifecycle.*`; counters in [server_main.cpp](../apps/server_main.cpp) | Local tests passed for slow peer/healthy progress, prefix drain, full-output abort and write deadline. Added tests passed locally for first-Trade abort with partial-book evidence, Gateway callback exception with abort/join, and a restarted process with an empty book. |
| T07: service differential and reproduction | [verify_service](../tools/service_verify.cpp), [service evidence tests](../tests/service_evidence_test.py), [actual-admission runner](../scripts/run_service_bench.py), M1 replay/shrinker | Small complete-stream comparison and negative evidence tests passed; 120,000 measured requests plus setup were verified against actual admission order at `ce9e94f`. This correctness run does not satisfy formal performance requirements. |
| T08: CI gates and failure reproduction | [workflow](../.github/workflows/ci.yml), [test-group checker](../scripts/check_test_groups.py), four presets, independent network summary | Two PR runs passed all four jobs. Controlled failure/artifact replay and restored replay are retained in `build/m2-ci-failure-evidence/`; latest-test CI, final main checks and permanent evidence indexing remain. |
| T09: bounded open-loop measurement | [loadgen](../apps/loadgen_main.cpp), [contract tests](../tests/loadgen_test.py), generator/runner/[summary](../scripts/summarize_service_bench.py), [summary negative tests](../tests/service_benchmark_test.py) | Short integration and consistency checks exist. Linux rate calibration, frozen seven-row formal matrix, five rounds each, sufficient normal samples, profiling and report remain pending. |
| T10: reproduction and delivery | [README](../README.md), this mapping, walkthrough, [clean reproduction](m2_clean_checkout.md) and evidence formats | Interim clean Linux checkout, initial downloads, tests, real CLI demo and short benchmark passed at `ce9e94f`. Latest-main validation, final evidence archive and M2 release remain pending. |

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

## Final delivery checklist

| Requirement | Evidence available now | Remaining gate |
|---|---|---|
| M1 semantic preservation | Existing suite plus synchronous/pausable/reference comparisons | Required latest PR and main suites must pass |
| Protocol correctness | Golden bytes, segmentation/coalescing, malformed/EOF and business-error cases | Latest Linux sanitizer/remote execution |
| Identity/routing and BBO | Cross-client/self-trade/reuse/owner tests, full-event BBO comparison and Linux observed fd reuse | Latest remote execution of the added boundary |
| Bounded pause and progress | Tiny-queue sweeps, controlled wake boundary, slow peer with healthy progress; Linux snapshot sanitizer suites | Latest-source sanitizer/remote validation |
| Lifecycle and delivery loss | Prefix drain, first-Trade abort, consumer exception, restart and write deadline checks with separate loss counters | Latest-source Linux/remote execution of follow-up cases |
| Failure localization | Retained remote fault artifacts, downloaded-trace reproduction, restored replay; verifier/summary negative tests | Permanent evidence index/archive and final successful latest-source CI |
| Service correctness at scale | 120,000 measured requests with actual-order reference checks; setup/warmups separate | Retain raw checks in permanent evidence package |
| Credible measurement | Bounded open-loop samples, loss conservation, three timing boundaries | Frozen Linux formal matrix, all rounds/raw results, profiling and report |
| Fresh-environment reproduction | Independent clean Linux checkout at `ce9e94f`, fresh dependencies, 94 Release tests, real CLI and smoke | Preserve interim-source scope; validate later changes and final main |
| Verifiable version | PR #2 implementation branch | Latest required PR checks, merge, exact-main push checks/artifacts, permanent archive, then release |

Publication remains ordered: pass the latest PR checks and inspect their actual
checkout/artifacts; merge; verify the new main push at that exact SHA; save the
required evidence beyond the CI artifact retention period; only then publish
`m2-service`. Queued/running/cancelled jobs and M1 green checks do not satisfy
these gates. Later report-only commits must follow the same PR/main process and
state their relationship to the measured source revision.
