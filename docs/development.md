# Development and reproduction guide

Return to the [project overview](../README.md). Run all commands below from the
repository root. Give each demo or experiment a new output directory to preserve
its evidence; formal measurements and profiling should run separately.

## Build configurations

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

## Deterministic replay and differential testing

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

## Deep-book tests

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
[Gateway evidence index](gateway_evidence_index.md).

## Core benchmarks

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
output directory. See [benchmark methodology](benchmark_method.md) and the
[core walkthrough](learning.md). The CI smoke checks evidence integrity
without imposing a latency threshold on shared runners.

[Semantics](semantics.md) specify active-ID reuse, no RequestId deduplication,
owner checks, allowed self-trades and conservative full-book limit rejection.
[Trace format](trace_format.md) separates malformed text from business
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
labels are uncalibrated workload candidates. It validates the measurement path;
it does not establish a service capacity. See the [service measurement method](service_benchmark_method.md)
for timing boundaries and formal paired experiments, and the [Gateway report](gateway_report.md)
for the completed comparison. Always retain failed rounds and all request outcomes.

## Offline ITCH replay

The [ITCH guide](itch_scope.md#cli-and-outputs) provides the golden-fixture replay
and independent Python verification commands, supported messages and resource
limits. The [reproduction guide](m5_reproduction.md) documents the larger checks.

## CI and experiment records

The [CI workflow](../.github/workflows/ci.yml) runs Debug, Release, ASan/UBSan and
separate TSan builds on Ubuntu 24.04. It checks that every discovered test ran
successfully, without skips, through [check_test_groups.py](../scripts/check_test_groups.py).
Release also runs core, network and ITCH smoke checks. Shared CI runners do not
have a latency pass/fail threshold.

Use [project progress](progress.md) to find milestone reports and release records,
and the [Gateway evidence index](gateway_evidence_index.md) for the latest experiment.
The [Gateway closeout](gateway_closeout_2026-10-18.md) is a pre-merge snapshot;
[PR #7](https://github.com/Owenqi666/low-latency-matching/pull/7) records its final delivery.
