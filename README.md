# llmatch — M1 matching core

A single-threaded, in-memory C++20 matching core under development. The original
planning documents remain local; public contracts will live in `docs/semantics.md`.
Limit orders, market IOC, owner-checked cancellation and an independent reference
model are implemented and tested. Deterministic replay, differential validation,
failure reduction and versioned text traces are available. Benchmark delivery
is in progress; no performance claims are published yet.

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

Implementation and acceptance progress: [docs/progress.md](docs/progress.md).

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

[Semantics](docs/semantics.md) specify active-ID reuse, no RequestId deduplication,
owner checks, allowed self-trades and conservative full-book limit rejection.
[Trace format](docs/trace_format.md) separates malformed text from business
rejections. There is no networking, concurrency, risk engine or crash recovery.
