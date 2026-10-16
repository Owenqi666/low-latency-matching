# llmatch — M1 matching core

A single-threaded, in-memory C++20 matching core. The public contract is
[docs/semantics.md](docs/semantics.md).
Limit orders, market IOC, owner-checked cancellation and an independent reference
model are implemented and tested. Deterministic replay, differential validation,
failure reduction and versioned text traces are available. Core benchmarks
measure per-command latency and separate batch throughput, including result
generation. They do not measure network latency or concurrent service capacity.

Requires a C++20 compiler, CMake >= 3.24, Ninja, Python >= 3.10, and network access for the first
GoogleTest 1.17.0 download. GoogleTest is a test-only dependency, configured using
the [official CMake integration](https://google.github.io/googletest/quickstart-cmake.html).

```sh
cmake --preset debug
cmake --build --preset debug
ctest --preset debug --output-on-failure --no-tests=error
```

Replace `debug` with `release` or `asan-ubsan` for the other configurations.
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
rejections. There is no networking, concurrency, risk engine or crash recovery.
