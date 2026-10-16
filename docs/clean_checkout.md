# Clean checkout reproduction

On 2026-10-16, an independent Codex sub-agent cloned the public repository,
built it from a fresh checkout and followed the README's Release workflow.
This is an agent reproduction, not a claim that a human user completed the
learning exercise or that another machine reproduced these timings.

The exact source revision was
59a29316a8d91b33bcb5572438eb731a8bc0b96f
(fix: reject missing benchmark runs and stale reports).
The checkout was detached at that revision. Git reported no modified or untracked
source files before or after the checks, and both benchmark run manifests record
code_dirty: false. No source edits or local untracked fixtures were copied from
the development workspace. Fixtures came from the public Git commit.

## Fresh checkout and tools

Repository: https://github.com/Owenqi666/low-latency-matching

Local reproduction directory: /private/tmp/llmatch-m1-clean-20261016.
It initially had no build directory or dependency cache. The first sandboxed
clone could not resolve GitHub; the network-enabled retry succeeded. Configure
used network access to download GoogleTest 1.17.0 into this checkout's own build
directory. The downloaded archive SHA-256 was verified as
65fab701d9829d38cb77c14acdc431d2108bfdbf8979e40eb8ae567edf10b27c,
matching the committed dependency pin. No GoogleTest source override was set,
and FetchContent was not in disconnected mode.

Observed tools and platform:

| Item | Observation |
| --- | --- |
| OS | macOS 26.6.2, build 25G83 |
| Architecture | arm64 |
| Compiler | Apple clang 21.0.0, clang-2100.1.1.101 |
| Compiler path | /usr/bin/c++ |
| CMake | 4.4.4 |
| Ninja | 1.13.2 |
| Python | 3.14.8 |
| Build | Release, -O3 -DNDEBUG, C++20 |
| Sanitizers | OFF for this Release reproduction |

The benchmark manifest records 18 logical CPUs. Exact CPU model, physical core
count, memory size and virtualization state were unavailable to the sandboxed
environment probe; they are not inferred here. Frequency, affinity and exclusive
CPU use were not controlled.

## Executed commands and results

All commands below ran from the clean checkout. The README explicitly permits
substituting the release preset and paths for debug.

    git clone https://github.com/Owenqi666/low-latency-matching.git /private/tmp/llmatch-m1-clean-20261016
    git fetch origin feat/m1-baseline
    git checkout --detach 59a29316a8d91b33bcb5572438eb731a8bc0b96f
    cmake --preset release
    cmake --build --preset release
    ctest --preset release --output-on-failure --no-tests=error --output-junit build/evidence/ctest-release.xml
    ./build/release/replay --engine compare --config data/fixtures/basic.config --input data/fixtures/basic.trace --output-dir build/basic-replay
    ./build/release/generate_workload --config data/fixtures/basic.config --seed 817 --count 2000 --output build/random.trace
    ./build/release/replay --engine compare --config data/fixtures/basic.config --input build/random.trace --output-dir build/random-replay
    python3 scripts/run_bench.py --binary build/release/bench_core --manifest data/workloads/smoke.manifest --repeats 1 --output-dir build/results/smoke
    python3 scripts/summarize_bench.py build/results/smoke
    python3 scripts/run_bench.py --binary build/release/bench_core --manifest data/workloads/smoke.manifest --repeats 1 --output-dir build/results/smoke-repeat
    python3 scripts/summarize_bench.py build/results/smoke-repeat

- Configure and build succeeded from the fresh directory.
- CTest passed **60/60** tests in 2.49 seconds, including the CLI contract,
  permanent maker-price regression and benchmark pipeline integrity tests.
- The basic hand fixture replay compared **8 commands** successfully.
- The independently generated trace contained **2,000 commands**, seed 817,
  hash fnv1a64:b361b38b595d93f5; baseline/reference comparison succeeded.
- Two separate benchmark invocations each generated and verified the same
  1,000-command mixed input at C=1,000 and ran one latency/throughput pair.
  Each invocation was followed by the standalone summary validator.
- The benchmark inputs, verification rows and final snapshot were additionally
  compared byte-for-byte across the two invocations. All matched.

CTest resolves the relative JUnit destination under its preset build directory.
The resulting XML is therefore at
build/release/build/evidence/ctest-release.xml; it records 60 tests, zero
failures and zero skipped tests.

## Independent repeat identity and semantics

The two runner calls regenerated the fixed input from the same committed
manifest. Byte comparison proves they measured identical config, setup and
input files, not merely the same seed or intended workload.

| File | SHA-256 in both invocations |
| --- | --- |
| config.txt | de5c70a3299f040eef14b4358073a99763fd39c292d5ab8462fe505d52ffc215 |
| setup.trace | 96d73cc0d1e45c9b3061faa0460fd7e7f32fb2c059d6d576e23ab3db427e9d41 |
| input.trace | f4ac450406f1143d412002d4291054c8778654b0a2538053908520343c8dba10 |
| verified_final.snapshot | 6ac39d0109cd9a99acea90e8fd63f84627f26c02e95cedb867a7f36a40376328 |
| verification.csv | 903ff6f6a3740cf6fcd05ff5b05ccf9aa05e7921665f2c921e309a87ec08e3bf |

Both benchmark summaries also report the same raw-byte identifiers:

| Input | FNV-1a64 |
| --- | --- |
| Config | fnv1a64:60ea05670d075bca |
| Setup | fnv1a64:83dea5a018515ffd |
| Measured input | fnv1a64:f3d6a15c3dfe9e1a |
| Final snapshot | fnv1a64:9becb45ea450f1ed |

Both invocations completed 1,000 accepted commands, zero rejected commands,
334 trades and 3,000 events. The full-event rolling checksum was
54a60cae25b9ba0a in both modes and both invocations. Setup and final depth were
500 orders; observed depth was 500–501. The complete verification JSON objects
were equal, and each round's snapshot and counters matched the reference replay.

## Timing variation and limits

These are functional smoke observations, not the formal five-round performance
result. Each run had only 1,000 samples, below the 100,000-sample reporting
threshold; no statistical stability is asserted.

| Invocation | Latency p50 / p99 | Throughput batch duration |
| --- | --- | --- |
| First | 41 ns / 42 ns | 76,250 ns |
| Independent repeat | 41 ns / 42 ns | 83,125 ns |

The throughput duration differed by 6,875 ns despite identical business results.
The clock probes observed a minimum positive clock interval of 41 ns and many
zero back-to-back intervals. This directly shows that these tiny call timings
are strongly quantized. Short batch length, scheduling, cache state and
uncontrolled background activity can also affect repeat timing; the runs did
not isolate their individual causal contributions. The reproduction requirement
is identical semantics and auditable methodology, not identical nanoseconds.

The probe's nominal 1 ns representation period is not the observed resolution.
Both generated reports explicitly label this as a one-round smoke and mark p99
below the sample threshold. Neither result replaces the formal baseline report.

## Local evidence index

All paths below are relative to the clean checkout directory:

- build/evidence/configure.log
- build/evidence/build.log
- build/evidence/ctest-release.log
- build/release/build/evidence/ctest-release.xml
- build/evidence/benchmark-smoke.log
- build/evidence/benchmark-repeat.log
- build/evidence/reproduction-check.json
- build/basic-replay/
- build/random.trace and build/random.trace.meta
- build/random-replay/
- build/results/smoke/report.md and report.json
- build/results/smoke-repeat/report.md and report.json
- Both result trees' mixed/capacity_1000/ directories retain input files,
  run manifests, raw samples, clock probes, snapshots and verification CSVs.

All clean-checkout build and measurement processes had completed before the
main agent began the final formal measurement run.
