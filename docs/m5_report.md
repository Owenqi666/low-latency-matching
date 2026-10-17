# M5 offline ITCH reconstruction report

The independent ITCH path passed its byte contracts, synthetic differential
checks and a bounded historical AAPL prefix. The frozen Linux matrix completed
all 30 measurements and six warmups. Rebuild throughput medians were 6.808,
7.383 and 6.018 million input messages/s for mixed, cancel/replace and multilevel
inputs respectively. This establishes a baseline for this new module; it is
not a matching-service optimization result or a comparison against Python.

At report preparation, candidate CI and fresh Linux reproduction had passed.
Final PR checks after report integration, normal merge, exact-main push checks,
permanent Release assets and publication verification were still pending.
Their eventual completion is recorded separately in the revision-specific
acceptance and release receipts; the candidate results below do not certify a
future main commit.

## Implementation and correctness

The module reads uncompressed BinaryFILE frames in file order and reconstructs
one selected security from the session start. It supports S/R context and
A/F/E/C/X/D/U visible-order changes, with an explicit ignore table. It does not
call MatchingEngine, infer hidden orders, auto-match a crossed visible book or
implement live-feed recovery. See [scope](itch_scope.md),
[ADR 007](adr/007-independent-itch-reconstruction.md),
[golden fixture calculations](../data/itch/README.md) and
[reproduction commands](m5_reproduction.md).

The fixed 553-byte golden stream contains 18 messages and nine target updates,
with independent hexadecimal bytes and hand-calculated states. Tests cover
C with Printable=N, original display-price retention, U inheritance, shared
levels, crossed books, boundary quantities, split reads, full/prefix framing,
unknown types before filtering, and invalid updates. The independent Python
model decodes the original bytes and directly aggregates its order dictionary;
C++ exported events are not its sole input.

The retained early local Release long check compared 120,000 target updates
from 150,000 messages, 12 full checkpoints and the final state. Its input,
binary and tool hashes bind that historical run; it predates the later failure
receipt correction and is not represented as a build of the final source.
The measured public commit additionally passed three independent complete
million-message checks: 800,000 target updates and 80 full checkpoints per
input, followed by final orders/depth and saved-output comparisons. Audit
records were streamed rather than retained as millions of JSON lines.

A review found that a failed verifier's suggested replay command could force
prefix mode and lose a capacity limit. The corrected tool preserves the exact
original input and options and invokes the verifier itself. Tests actually
replay completeness, capacity, truncated-prefix, audit-tampering and
CSV-tampering failures. Non-ASCII unknown message diagnostics also remain valid
JSON. The measured candidate's CLI test retained 41 cases in each configuration;
this case count is evidence, not a hard-coded test-discovery threshold.

## Historical prefix: coverage and limits

The source was Nasdaq's [12302019.NASDAQ_ITCH50.gz](https://emi.nasdaq.com/ITCH/Nasdaq%20ITCH/12302019.NASDAQ_ITCH50.gz), trading date 2019-12-30,
selected symbol AAPL (locate 13). Acquisition on 2026-10-17 read 12,386,304
compressed bytes and retained a 30,262,428-byte continuous prefix from the day
start, ending at a complete-message boundary. The source response advertised
3,524,013,057 bytes; only the bounded prefix was consumed. The frozen cutoff
was 1,000 target updates including an add and a subsequent change.

The retained input has 1,042,864 messages, 1,055 target-locate messages and
1,000 applied target updates: 516 A, 470 D and 14 E. The target sequence contains
no F/C/X/U; their semantics are covered by synthetic fixtures and streams,
not claimed as historical coverage. T06 independently compared all 1,000
updates, four full checkpoints and the final state (39 orders across 33 levels).
The last processed frame starts at byte 30,262,390. S/O and S/S are present;
S/C and the BinaryFILE terminator are absent, and `session_complete=false`.

The prefix SHA-256 is
`90bb246d6f9902c498765ed98a68784db45f5e21e4ae9a07c5513d7f1c364ad4`.
The capture receipt preserves the URL, response metadata, consumption and
cutoff. No whole-file gzip CRC, official full-file checksum, whole session or
whole trading day was verified. T06 reused this input and records
`acquisition_repeated=false`; it did not repeat data acquisition. Raw historical
bytes and detailed real order/depth CSVs remain local while redistribution
permission is unconfirmed. This report publishes coverage and identity only.

The real negative case changes the first target E quantity from 22 to
4,294,967,295 in a separate day-start prefix. At offset 10,286,348, message
359,236, reference 194645, both Python and C++ rejected the overdraw after
139 preceding target updates had compared successfully. The mutation receipt
and original errors are retained. A subsequent check with the current macOS
Release binary and corrected verifier repeated that same negative input, then
actually executed the saved verifier replay command. Both runs exited 1 with
the same input identity, offset and reference; `expected-failure-check.json`
records the expected-failure check as passed. This verifies the corrected
failure-replay contract without overwriting the historical attempt. Its raw
bytes are also excluded from public data.

One additional Linux rebuild observation of the verified real prefix took
83.512019 ms in the loop, with 83.514 ms user CPU and zero recorded system CPU.
It decoded 12.488 million total messages/s but applied only about 11,974 target
updates/s: most messages concern other securities or context. This is one
resource observation, not a real-market throughput matrix. Input reading took
7.520157 ms, construction 1,417 ns, finish 167 ns, final snapshot 9,083 ns and
output writing 95,541 ns, all outside the loop. Process RSS high-water was
31.875 MiB after input and 32.500 MiB after timing/snapshot; the input itself
occupied 30,262,428 bytes. These values do not isolate the book's allocation.

## Frozen synthetic matrix

Measurements used clean public commit
`7cea5df6d25c69a99831ed6b00a1babbbf151052` in the fresh Linux checkout used for
T06. The VM ran Ubuntu 24.04, kernel 6.8.0-147 on aarch64 with four logical CPUs,
GCC 13.3.0, CMake 3.28.3 and Python 3.12.3. Release flags were
`-O3 -DNDEBUG -std=c++20`; sanitizers were off. The benchmark/replay binary SHA-256 values are
recorded in the [evidence index](m5_evidence_index.md). Source/build/tool identities
were checked before and after the matrix.

Each input has exactly 1,000,000 payload messages, including 800,000 target
updates. The zero-length terminator is not a message. Between the initial
context and final S/C, each 100-slot cycle assigns 80 target updates, 10
non-target updates and 10 known ignored messages. Empty/capacity legalisation
changes requested type proportions; actual counts remain in each workload
manifest. The target capacity is 1,000 and the non-target capacity is 128.

| Scenario | Seed | Input bytes | Peak / final target orders | Available price choices/side | Forced best-level disappearances |
| --- | --- | ---: | ---: | ---: | ---: |
| mixed | `0x495443480501` | 32,865,084 | 1000 / 997 | 32 | 0 |
| cancel_replace | `0x495443480502` | 32,580,697 | 18 / 4 | 16 | 0 |
| multilevel | `0x495443480503` | 32,519,585 | 1000 / 1000 | 256 | 399 |

The cancel/replace input's observed peak is only 18 orders, despite the common
capacity of 1,000. Its working set differs materially from the other two
scenarios. Multilevel completed 399 deterministic removals of an entire current
best level; final depth contained 435 occupied levels. These artificial inputs
exercise defined lifecycles and may contain crossed visible books. They are
not calibrated market distributions.

All three independent reference checks completed before the first timed
process. Their separately recorded wall durations were 153.237 s (mixed),
7.015 s (cancel/replace) and 218.714 s (multilevel); none is included in the C++
throughput figures. Each scenario/mode then received one independent warmup
and five measured processes, each with one complete traversal and a new empty
book for rebuild. The entire matrix ran sequentially on the same checkout.
No later round was added or selected to improve a result.

| Scenario | Mode | M messages/s median [min, max] | M target update messages/s median | MB/s median | Wall ms median | CPU ms median |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| mixed | decode | 14.019 [13.768, 14.050] | 11.215 | 460.727 | 71.333 | 71.336 |
| mixed | rebuild | 6.808 [6.686, 6.843] | 5.447 | 223.760 | 146.877 | 146.863 |
| cancel_replace | decode | 14.193 [14.091, 14.269] | 11.354 | 462.416 | 70.458 | 70.461 |
| cancel_replace | rebuild | 7.383 [7.284, 7.428] | 5.906 | 240.543 | 135.447 | 135.444 |
| multilevel | decode | 14.016 [13.627, 14.105] | 11.213 | 455.797 | 71.347 | 71.339 |
| multilevel | rebuild | 6.018 [5.919, 6.080] | 4.814 | 195.700 | 166.171 | 166.163 |

All 36 intervals and their actual wall time, user/system CPU, RSS, excluded
work and clock observations are listed in [the interval tables](benchmarks/m5_itch_rounds.md).
No failure or slower interval was discarded. The copied matrix passed a
separate local invocation of the same published summarizer, which checks the
raw results, input/tool/binary bindings and complete execution plan.

The timed loop includes in-memory framing, decoding, common/context work,
a whole-input byte FNV-1a pass and consumption of decoded fields into another
checksum. Rebuild additionally applies target updates. Decode mode's target
update rate counts decoded update messages without applying them to a book;
it is not a reconstruction rate. The checksum work is part of these measured
costs, not subtracted as estimated overhead. Subtracting mode durations does
not strictly isolate reconstruction cost.

Reference, input reading, construction, final EOF/context validation, final
snapshot/checksum and output writing are outside the interval. Across the 30
measurements, input reading took 6.508450–7.138991 ms; construction 542–1,708 ns;
finish 42–334 ns; snapshot 0–111,084 ns; output writing 79,583–122,959 ns.
Whole-process timed RSS high-water ranged from 34.000 to 34.375 MiB, rising
as high as 34.500 MiB after snapshot. The approximately 32.5–32.9 MB input
buffers dominate this accounting; process high-water cannot be subtracted to
claim exact standalone book memory.

The nominal steady-clock period is 1 ns, but each measured interval's preflight
observed a 41 ns minimum positive step and 6,083–7,215 zero pairs out of 10,000.
The actual loops lasted roughly 70–169 ms. No per-message p99 or nanosecond
latency distribution is inferred. The VM shares its host; core exclusivity,
CPU affinity and frequency were not controlled. There is no absolute speed or
speedup acceptance gate, and these results do not establish bare-metal or
production-market performance.

## Fresh reproduction and CI evidence

T06 cloned the public repository at the measured commit into a new Linux
checkout and downloaded dependencies into a new Release build, reusing only
the existing VM/system toolchain. It finished with clean Git status. Dynamic
CTest discovery and JUnit agreed on 124 executed/passed tests in nine Release
groups: the original seven, ITCH and benchmark. Two actual service CLI
processes completed seven commands, observed the same two trades and passed
the independent service verifier. Golden and historical ITCH replay, a
truncated-frame negative demonstration, core smoke, seven network scenes and
small ITCH smoke all completed with their expected exit codes.

Candidate [Actions run 39063078708](https://github.com/Owenqi666/low-latency-matching/actions/runs/39063078708)
was downloaded and independently inspected. Debug/Release/ASan-UBSan/Clang-TSan
executed 120/124/120/120 tests respectively. The PR head was `7cea5df6d25c69a99831ed6b00a1babbbf151052`;
the tested merge checkout was `53dbc147e772f25815d4412577e122829f6ce86e`, with
parents `9314cf077c3968d484c627aa1d7f7e51dfa28463` and that head. Discovery/JUnit,
required groups, retained CLI negatives and independently recomputed smoke
summaries passed inspection. Missing-round, changed-input, wrong-count and
smoke-mislabeled-as-formal benchmark evidence was rejected as intended.

These counts describe that run only. Report integration requires its own
latest-head checks, followed by normal PR merge and exact-main push inspection.
The [evidence index](m5_evidence_index.md) separates measured, reproduced,
candidate-tested and subsequently published identities. M3/M4 rejected
optimizations remain rejected; M5 does not change their conclusions.
