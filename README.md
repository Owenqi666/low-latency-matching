# llmatch — C++ matching core and TCP service

A C++20 in-memory price-time matching engine with a bounded TCP Gateway,
independent reference validation, deterministic replay and an offline ITCH reader.
TCP clients communicate with one Gateway I/O thread; bounded command/event queues
connect it to one Matching thread that exclusively owns the order book.

## Build and run

Requires a C++20 compiler, CMake >= 3.24, Ninja and Python >= 3.10. The first build
downloads pinned GoogleTest 1.17.0 and Boost 1.89.0 sources; hashes are in
`cmake/Dependencies.cmake`.

```sh
cmake --preset release
cmake --build --preset release
ctest --preset release
python3 scripts/demo_service_clients.py . build/gateway-demo --stage Gateway
```

The demo starts a server and two real CLI clients, checks matching Trade events,
request-ID reuse and BBO/Complete ordering, and verifies the recorded commands
against the independent reference model. Use a new output directory to retain
each demonstration. [Architecture](docs/service_architecture.md),
[protocol](docs/protocol.md) and [semantics](docs/semantics.md) describe the contract.

## Current evidence and limits

Production writes remain **batch1** after the Gateway experiment's valid rejection
of batch16. The seven-row Linux VM matrix retained all 35 pairs and 14 warmups:

- At the frozen near rate of 22,781 commands/s, batch16 reduced server lifetime
  CPU per measured completion by a paired median **6.40%**, below the 10% gate.
- In that same row, RTT p99 and scheduled-to-completion p99 increased by paired
  medians **13.72%** and **10.09%**, exceeding their 10% limits.
- A delivered all requests in 28/35 measured runs and B in 35/35. A's burst,
  single-client and overload failures remain in the record; all runs drained.

These are finite results on one local VM, not general capacity guarantees.
The [Gateway report](docs/gateway_report.md) records all outcomes and gates.
The [diagnostic report](docs/gateway_diagnostics.md),
[execution plan](docs/gateway_optimization_plan.md) and
[evidence index](docs/gateway_evidence_index.md) retain source identities and all
outcomes. A clean reproduction is not a general throughput or production claim.
The [historical local verification](docs/gateway_report.md#g09-clean-delivery-verification)
records the clean Linux rebuild, 136 passing Release tests plus two disabled
registrations, both-variant network checks, smoke/demo, short replay and
independent archive-copy recomputation. A later acceptance review found that
those disabled registrations fail the existing strict CI checker. The
[Gateway closeout record](docs/gateway_closeout_2026-10-18.md) tracks the explicit
extended-test option, passing default/extended/ON→OFF local checks, and pending
current-source CI and remote delivery. Historical experiment and archive verification do not
establish that the revised source has passed those checks.


Delivery status below is a pre-merge snapshot; the final head, PR/main checkout
SHAs and CI results are recorded in [PR #7](https://github.com/Owenqi666/low-latency-matching/pull/7).

The service is in-memory, single-host and single-Matching-thread; it has no WAL,
replication or durability guarantee. A connection exceeding its bounded send
allowance is isolated and its undelivered results are counted. Core benchmark
timings exclude networking. The ITCH reader reconstructs an explicitly limited
single-security visible book; historical feed events bypass the matching engine.

## Milestone history

For M4/M5 completion status and the evidence behind older pending items, see the
[milestone progress and acceptance index](docs/progress.md).

A single-threaded, in-memory C++20 matching core. The public contract is
[docs/semantics.md](docs/semantics.md).
Limit orders, market IOC, owner-checked cancellation and an independent reference
model are implemented and tested. Deterministic replay, differential validation,
failure reduction and versioned text traces are available. Core benchmarks
measure per-command latency and separate batch throughput, including result
generation. They do not measure network latency or concurrent service capacity.

M1 is released. M2 technical implementation, Linux verification, formal
measurement and reporting are complete. The release's `acceptance.json` is the
authority for final PR/main checks, durable archives and publication. See
[architecture](docs/service_architecture.md), [wire protocol](docs/protocol.md),
[task status](docs/progress.md) and the revision-specific
[acceptance record](docs/m2_acceptance.md). The corrected
[network report](docs/m2_report.md) records 30 successful measured rounds and
five overload delivery failures; all 42 warmup/measured attempts drained and
passed Reference checks. The earlier matrix is retained with its loadgen timing
limitation. Recorded Linux
[core measurements](docs/m2_core_measurements.md) and separate
[service profiling](docs/m2_profiling.md) have their own timing and source boundaries.
The [evidence index](docs/m2_evidence_index.md) maps those records to release assets.

M3 evaluated bounded output batching and retained one-frame production writes.
Across 35 Linux VM pairs, the candidate reduced CPU/request at 45k/s by a median
14.68%, but increased single-client RTT p99 by 71.30%, failing the frozen
regression limit. The [report](docs/m3_report.md), [all-pair results](docs/benchmarks/m3_service_pairs.md),
[acceptance record](docs/m3_acceptance.md) and
[reproduction method](docs/service_benchmark_method.md#paired-m3-comparison)
preserve the rejected candidate, complete outcomes and source-specific evidence.

M4 evaluated fixed-capacity order slots and retained list storage. Across five
core scenes, mixed throughput improved by a paired median 5.241%, while
cancel-heavy improved 2.710%, below its required 5% threshold. All 40 formal
service runs delivered and drained, but internal tail regressions remain in
the [report](docs/m4_report.md). See the [evidence index](docs/m4_evidence_index.md),
[acceptance record](docs/m4_acceptance.md) and
[A/B reproduction](docs/benchmark_method.md#paired-m4-order-storage-comparison).
M4 T00–T08 are complete. [Final progress and acceptance links](docs/progress.md#m4-order-storage-experiment)
connect the [m4-order-storage release](https://github.com/Owenqi666/low-latency-matching/releases/tag/m4-order-storage)
to its final CI, archive and publication receipts.

M5 adds an independent offline ITCH 5.0 decoder and single-security visible-book
reconstructor. Golden bytes, an independent raw-byte Python model, three synthetic
million-message streams and a bounded AAPL historical prefix validate its scope.
See the [supported messages and CLI](docs/itch_scope.md), [report](docs/m5_report.md),
[fresh Linux reproduction](docs/m5_reproduction.md), [acceptance record](docs/m5_acceptance.md)
and [evidence index](docs/m5_evidence_index.md). Historical feed events are applied
directly and do not pass through the matching engine. M5 T00–T08 are complete.
[Final progress and acceptance links](docs/progress.md#m5-offline-itch-reconstruction)
connect the [m5-itch-reconstruction release](https://github.com/Owenqi666/low-latency-matching/releases/tag/m5-itch-reconstruction)
to its final CI, downloaded-archive replay and publication-receipt checks.

Requires a C++20 compiler, CMake >= 3.24, Ninja, Python >= 3.10, and network access for the first
GoogleTest 1.17.0 and Boost 1.89.0 downloads (versions and SHA-256 are pinned in
`cmake/Dependencies.cmake`). GoogleTest is a test-only dependency, configured using
the [official CMake integration](https://google.github.io/googletest/quickstart-cmake.html).

```sh
cmake --preset debug
cmake --build --preset debug
ctest --preset debug --output-on-failure --no-tests=error
```

Replace `debug` with `release` or `asan-ubsan` for the other configurations.
Linux concurrency validation uses a separate `tsan` preset; for example configure
with `cmake --preset tsan -DCMAKE_CXX_COMPILER=clang++-18`, then build/test that preset.
The sanitizer flags apply to project code, not just the test entry point.

M1 implementation and reproduction acceptance are complete. See the
[baseline report](docs/m1_report.md), [evidence index](docs/evidence_index.md),
and [task mapping](docs/progress.md). The [M1 release](https://github.com/Owenqi666/low-latency-matching/releases/tag/m1-baseline)
records publication and final main CI separately from the measured source commit.

```sh
./build/debug/replay --engine compare --config data/fixtures/basic.config \
  --input data/fixtures/basic.trace --output-dir build/basic-replay
./build/debug/generate_workload --config data/fixtures/basic.config \
  --seed 817 --count 2000 --output build/random.trace
./build/debug/replay --engine compare --config data/fixtures/basic.config \
  --input build/random.trace --output-dir build/random-replay
LLMATCH_LONG_DIFFERENTIAL=1 ./build/debug/llmatch_tests \
  --gtest_filter=DifferentialTest.FixedSeedsCompareEveryEventAndSnapshot
```

The normal suite compares 20 seeds × 2,000 commands; the long entry point runs
100 × 10,000. Capacities rotate through 1, 2, 16 and 128. Mismatches retain the
actual input, configuration and both outputs under the test working directory's
`failures/`. `shrink_failure --config FILE --input FILE --output FILE` requires
an input that still fails on the current binaries; a correctly fixed input will
report that there is no failure to shrink.

The separate deep-book suite covers long FIFO queues and sparse, wide price
levels. Its routine cases use capacity 1,000, 850 prefill commands and 500 tail
commands, with one fixed seed per distribution. They run in the normal CTest
suite; to select just this suite and retain its inputs and coverage records:

```sh
cmake --preset release
cmake --build --preset release --target deep_book_tests replay --parallel 2
LLMATCH_DEEP_BOOK_OUTPUT="$PWD/build/deep-book-routine-01" \
  ctest --preset release -L deep_book --output-on-failure --no-tests=error
```

`LLMATCH_EXTENDED_TESTS` defaults to `OFF`: the normal build registers five
routine deep-book tests, without disabled extended entries. To opt into the two
normal `Extended*` CTest cases, use the independent `build/gateway-extended`
directory. Each case covers two fixed seeds at capacity 10,000, with 8,500
prefill commands and 1,000 tail commands per seed:

```sh
cmake -S . -B build/gateway-extended -G Ninja \
  -DCMAKE_BUILD_TYPE=Release -DLLMATCH_EXTENDED_TESTS=ON
cmake --build build/gateway-extended --target deep_book_tests --parallel 2
ctest --test-dir build/gateway-extended \
  -R '^DeepBookTest[.]Extended(LongFifo|SparseWide)$' --show-only=json-v1
LLMATCH_DEEP_BOOK_OUTPUT="$PWD/build/deep-book-extended-01" \
  ctest --test-dir build/gateway-extended \
  -R '^DeepBookTest[.]Extended(LongFifo|SparseWide)$' \
  --output-on-failure --no-tests=error \
  --output-junit "$PWD/build/deep-book-extended-01.xml"
```

This runs the two extended tests through CTest; it is not a full-suite CI result.
Choose new evidence paths for each run. Each trace includes any additional
boundary and replenishment commands; every command compares full events,
normalized snapshots and invariants. `LLMATCH_DEEP_BOOK_OUTPUT` retains the trace,
configuration, metadata, coverage CSV and comparison result. These cases provide
deep-book coverage separately from the small-capacity `LLMATCH_LONG_DIFFERENTIAL`
entry above. Recorded runs and independent replays are in the
[Gateway evidence index](docs/gateway_evidence_index.md).

Build `release`, then run a short benchmark and independently check its report:

```sh
python3 scripts/run_bench.py --binary build/release/bench_core \
  --manifest data/workloads/smoke.manifest --repeats 1 \
  --output-dir build/results/smoke
python3 scripts/summarize_bench.py build/results/smoke
```

For the full baseline, run all four manifests, retaining five rounds of each
mode at capacities 1,000 and 10,000. Choose a new output directory for each run;
the runner preserves existing evidence instead of overwriting it.

```sh
for scenario in mixed cancel_heavy sweep clustered; do
  python3 scripts/run_bench.py --binary build/release/bench_core \
    --manifest "data/workloads/$scenario.manifest" --repeats 5 \
    --output-dir build/results/baseline
done
python3 scripts/summarize_bench.py build/results/baseline
```

Every formal input has 100,000 commands. Inputs are generated before timing;
the independent reference checks full events, and each measured round must
match verified counts, event checksum and final snapshot. Raw samples, all
rounds, hashes, build/environment metadata and clock probes remain under the
output directory. See [benchmark methodology](docs/benchmark_method.md) and the
[core walkthrough](docs/learning.md). The CI smoke checks evidence integrity
without imposing a latency threshold on shared runners.

[Semantics](docs/semantics.md) specify active-ID reuse, no RequestId deduplication,
owner checks, allowed self-trades and conservative full-book limit rejection.
[Trace format](docs/trace_format.md) separates malformed text from business
rejections. The M1 release is the synchronous core baseline; M2 adds the service
described below. Risk management and crash recovery remain outside its scope.

## Service development and short experiments

The default listener is loopback. Start the server and run two CLI instances in
separate terminals. Stop the server with SIGINT/SIGTERM to drain admitted work.

```sh
./build/debug/matching_server --port 19999 --record-limit 10000 --output-dir build/manual-service
./build/debug/matching_client --port 19999
```

CLI lines are `limit REQUEST ORDER buy|sell PRICE QTY`,
`market REQUEST ORDER buy|sell QTY`, `cancel REQUEST ORDER`, and `quit`.
For example, one client enters `limit 1 101 sell 100 5`; another enters
`market 1 201 buy 2`; the first can then enter `cancel 2 101`. Both clients
continuously print business events and BBO, including maker trades while idle.
Complete ends that request's immediate processing, not the lifetime of a resting
order. Reconnecting creates a new identity and does not recover prior ownership.

After the server exits, validate its recorded run:

```sh
./build/debug/verify_service --directory build/manual-service
```

Use a new output directory for each bounded network experiment:

```sh
python3 scripts/run_service_bench.py --server build/release/matching_server \
  --loadgen build/release/loadgen --verifier build/release/verify_service \
  --manifest data/workloads/service-smoke.json --output-dir build/service-smoke
python3 scripts/summarize_service_bench.py build/service-smoke
```

The smoke manifest checks seven workload paths at small scale. Its near/overload
labels are uncalibrated candidates, not measured capacity claims. The separate
[formal manifest](data/workloads/service-formal.json) has rates frozen from
[Linux calibration](docs/m2_rate_selection.md). The corrected network run kept
those rates: all ordinary and 45000/s near rounds succeeded, while every 80000/s
overload round failed delivery. Both complete matrices remain in the
[report](docs/m2_report.md). These finite VM observations do not establish a
platform-independent sustainable rate. Records keep
planned, started, completed, failed and unfinished requests separately. The
independent report rejects missing rounds, inconsistent counts and stale reference
verification. See [service measurement method](docs/service_benchmark_method.md).
