# llmatch — C++ matching core and TCP service

A single-threaded, in-memory C++20 matching core. The public contract is
[docs/semantics.md](docs/semantics.md).
Limit orders, market IOC, owner-checked cancellation and an independent reference
model are implemented and tested. Deterministic replay, differential validation,
failure reduction and versioned text traces are available. Core benchmarks
measure per-command latency and separate batch throughput, including result
generation. They do not measure network latency or concurrent service capacity.

M1 is released. M2 service implementation and acceptance are in progress on this
branch: [architecture](docs/service_architecture.md), [wire protocol](docs/protocol.md),
and [task status](docs/progress.md). No formal M2 performance or release claim is
made before Linux, remote CI, measurement and publication evidence is complete.

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
labels are uncalibrated candidates, not measured capacity claims. Formal rates
must first be calibrated and frozen in a Linux Release manifest. Records keep
planned, started, completed, failed and unfinished requests separately. The
independent report rejects missing rounds, inconsistent counts and stale reference
verification. See [service measurement method](docs/service_benchmark_method.md).
