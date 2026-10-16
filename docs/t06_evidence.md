# T06 local differential and failure-reduction evidence

Observed on 2026-10-16 using Apple Clang 21.0.0
(`clang-2100.1.1.101`), Darwin 25.6.0, arm64. These are correctness checks,
not performance measurements or a claim of complete state-space coverage.

## Source provenance

At evidence capture, HEAD was
`6592670c1c27bc22bd168a96490f7e81d4305218` (engines and strict trace IO).
The differential runner, random generator, CLIs and differential tests were
additional **uncommitted working-tree files**. Therefore that commit alone does
not identify the tested T06 implementation. The next integration commit must
record its own test and CI results.

The local builds linked `src/order_book.cpp`, `src/matching_engine.cpp`,
`reference/reference_engine.cpp`, `tools/trace_io.cpp`,
`tools/differential.cpp`, and (for random tests) `tools/random_commands.cpp`.
They used the contracts in `include/llmatch`, tool/reference headers, and
GoogleTest v1.17.0 from `build/debug/_deps/googletest-src`.

Source SHA-256 values captured with this record:

| File | SHA-256 |
| --- | --- |
| `src/matching_engine.cpp` | `d5e5b3b29f244b95ed982c79dfb7909a4c3decf8fb01b3aaab515619b29a5c1d` |
| `src/order_book.cpp` | `818d0f7eaea068d5cc108a41117e135fa85d591df60c7027c56725d89590edab` |
| `reference/reference_engine.cpp` | `b18df31e1d86aa6919a34700fb1a62b684e16531226003b428b7e8f2d864e628` |
| `tools/trace_io.cpp` | `2f0396ea94e0a052f2f959000c179b928fec612859d2e8212097364877e025e0` |
| `tools/differential.cpp` | `708ca9cbb847db3472876c582eed4adbfb9765cc9246679a941a349dfc420bbc` |
| `tools/random_commands.cpp` | `1b15d6beb81f6f8e3dafd10b953e9bc43503f87fb46ac309734eac8523bb7404` |
| `tests/differential_test.cpp` | `a5a701af5d3945eeb06801768dcd4e02fa4394114a4c6a2b6997309be7e834cd` |

The initial ordinary/long test binary preceded two minor cleanup edits: explicit
closing of failure output streams and zero-initialized synthetic test records to
remove compiler warnings. The later sanitizer build included those edits.
The hashes above describe the source snapshot at documentation time; they are
not claimed to reconstruct the earlier ordinary binary byte for byte.

## Fixed seeds and long local run

Actual standalone build and run commands, from the repository root:

```sh
clang++ -std=c++20 -O1 -g -Wall -Wextra -Wpedantic -Wconversion -Wshadow \
  -Iinclude -Itools -Ireference \
  -isystem build/debug/_deps/googletest-src/googletest/include \
  tests/differential_test.cpp tools/differential.cpp tools/random_commands.cpp \
  tools/trace_io.cpp src/order_book.cpp src/matching_engine.cpp \
  reference/reference_engine.cpp build/debug/lib/libgtest.a \
  build/debug/lib/libgtest_main.a -pthread -o build/differential_tests
./build/differential_tests --gtest_output=xml:build/differential-small.xml
LLMATCH_LONG_DIFFERENTIAL=1 ./build/differential_tests \
  --gtest_filter=DifferentialTest.FixedSeedsCompareEveryEventAndSnapshot \
  --gtest_output=xml:build/differential-long.xml
```

Ordinary run: all five tests passed, including 20 seeds × 2,000 commands =
40,000 commands. Long run: 100 seeds × 10,000 commands = **1,000,000 commands**
passed. Capacities rotate through 1, 2, 16 and 128; each long-run capacity received
25 seeds. Seeds start at `0x4D310000`; generator version is
`mt19937_64-modulo-v1`. Every command compares process status, complete ordered
event records and canonical snapshots; both engines also check their invariants.
The XML records the actual seed count, commands per seed, total and capacities.

The later sanitizer build used the same source list and includes, with
`-fsanitize=address,undefined -fno-sanitize-recover=all -fno-omit-frame-pointer`
added to compilation/linking, output `build/differential_tests_san`, then:

```sh
./build/differential_tests_san --gtest_output=xml:build/differential-san.xml
```

All five tests, including the 40,000-command run, passed without diagnostics.
Core, reference, trace and differential sources were instrumented in that build;
its reused GoogleTest static libraries were ordinary Debug libraries. Full
CMake sanitizer/CI integration has separate evidence.

## Temporary wrong-price probe and reduction

Only `build/t06-probe/matching_engine_mutant.cpp` was mutated. The production
`src/matching_engine.cpp` was not changed. The copied source changed exactly:

```cpp
trade.price = maker.price;
// to:
trade.price = maker.price + 1; // TEMPORARY PROBE: wrong maker price
```

Mutant source SHA-256:
`e58a10a51effd3977def47af0baa9e3551bebdf29e459a69bd6cc8befcfd6042`.
Replacing that single mutated line with the original was checked to reproduce
the production file exactly. The mutant and temporary binaries remain ignored
build artifacts; the mutation is not a production configuration or feature.

Actual build commands:

```sh
clang++ -std=c++20 -O1 -g -Iinclude -Itools -Ireference \
  apps/replay_main.cpp tools/differential.cpp tools/trace_io.cpp \
  src/order_book.cpp build/t06-probe/matching_engine_mutant.cpp \
  reference/reference_engine.cpp -o build/t06-probe/replay_mutant
clang++ -std=c++20 -O1 -g -Iinclude -Itools -Ireference \
  tools/shrink_failure.cpp tools/differential.cpp tools/trace_io.cpp \
  src/order_book.cpp build/t06-probe/matching_engine_mutant.cpp \
  reference/reference_engine.cpp -o build/t06-probe/shrink_mutant
clang++ -std=c++20 -O1 -g -Iinclude -Itools -Ireference \
  tools/workload_generator.cpp tools/random_commands.cpp tools/trace_io.cpp \
  reference/reference_engine.cpp -o build/generate_standalone
```

The ordinary `build/replay_standalone` and `build/shrink_standalone` were built
with the corresponding command above, substituting `src/matching_engine.cpp`
for the mutant and using the ordinary output path. Probe configuration was
`LLMATCH_CONFIG 1` followed by `16 1000 1000`.

```sh
./build/generate_standalone --config build/t06-probe/config.txt \
  --seed 817 --count 2000 --output build/t06-probe/input.trace
./build/replay_standalone --engine compare --config build/t06-probe/config.txt \
  --input build/t06-probe/input.trace --output-dir build/t06-probe/correct
./build/t06-probe/replay_mutant --engine compare --config build/t06-probe/config.txt \
  --input build/t06-probe/input.trace --output-dir build/t06-probe/failure
./build/t06-probe/shrink_mutant --config build/t06-probe/config.txt \
  --input build/t06-probe/input.trace --output build/t06-probe/minimized.trace
./build/replay_standalone --engine compare --config build/t06-probe/config.txt \
  --input build/t06-probe/minimized.trace --output-dir build/t06-probe/regression-correct
```

Observed results:

- Original generated input: 2,000 commands, `fnv1a64:108d67ddbc326976`;
  config: `fnv1a64:d154bc023a250f19`.
- Correct comparison: exit 0. Mutant comparison: exit 2, first mismatch at
  command 10, class `event_value_kind_2` (Trade).
- Failure directory contains `config.txt`, `input.trace`, `difference.txt`,
  `metadata.txt` and copied `source.metadata.txt`. The copied source metadata
  records generator version and seed 817; generic replay metadata labels these
  unknown because replay did not itself generate the input.
- Shrinker: exit 0, **2,000 → 2 commands**, 20 candidate replays, same Trade
  difference class. Each candidate starts from fresh empty engines.
- Minimized input: `fnv1a64:71dc9a9ac64d66ed`. Correct comparison of that input:
  exit 0. Detailed local report: `build/t06-probe/minimized.trace.report.txt`.

The two-command regression is:

```text
LLMATCH_TRACE 1
L 1 1994 1994 0 101 11
L 3 1996 1996 1 100 13
```

It trades 11 at the resting buy maker's price 101 and rests the sell remainder
2 at 100. The mutant emits price 102, while its final snapshot is still equal:
this probe establishes why complete event comparison matters. Permanent
regression integration is recorded separately from this local probe.

## CLI exit-boundary checks

Actual results are captured in `build/t06-probe/cli-boundaries.json`:

- Trace line 2 containing quantity `18446744073709551616`: replay exit 1,
  error explicitly reports `malformed.trace:2` and the out-of-range integer.
- A trace consisting of unknown cancellation and invalid-client rejection:
  compare exit 0, two commands processed consistently.
- Correct implementation asked to shrink the minimized trace: exit 1 with
  `input has no differential failure to shrink`.

The local `build/` evidence is intentionally not committed. This document
preserves the commands, observed outcomes and identifying hashes. T07 remote
runner execution, downloadable failure artifacts and final-version validation
must be established independently; this record does not claim them.
