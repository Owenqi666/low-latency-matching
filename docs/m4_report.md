# M4 order-storage experiment report

The slot candidate does not meet the frozen core adoption rule. `mixed`
throughput improves by a paired median **5.241%**, with five of five pairs
improving; `cancel_heavy` improves **2.710%**, with four of five pairs improving,
but misses its required 5% minimum. This already prevents adoption under the
[recorded plan](m4_experiment_plan.md). Production files have been restored to
the measured list control; all 92 build/tool/test/input files match that source.
The service experiment is also verified: all 40 formal runs deliver, drain
and meet sample requirements, while some individual and internal tail metrics
regress. Final PR/main CI and M4 publication still require their own receipts.
No threshold or scenario was changed after seeing these results.

## Sources and measurement environment

A is the common list control `97fdc6ee165201b0ab9b3997879f5296fb508d9f`;
B is the fixed-slot candidate `4cf669ff2e932c6f27adeca0a9e143ffd03430b1`.
Both measurements used clean source checkouts. Their build inputs differ only
in `include/llmatch/order_book.hpp` and `src/order_book.cpp`. The M4 common
baseline adds the shared diagnostic, input, pairing and validation tools to
the accepted M3 production path. It is not an untouched M2 baseline, and no
M2/M3 historical throughput is used as the new A measurement. The network
path retains single-frame writes.

Both `bench_core` executables used GCC 13.3.0, C++20 and `-O3 -DNDEBUG`, with
sanitizers off, on Ubuntu 24.04 arm64, Linux `6.8.0-147-generic`, glibc 2.39.
The QEMU/HVF guest has four vCPUs and 4 GiB configured RAM; its host is an
Apple M5 Pro with 18 cores and 48 GiB RAM, running macOS 26.6.2. Guest CPUs
0–3 were available, with no affinity pinning, fixed frequency/turbo or
exclusive physical cores. The host is shared and interactive. Project builds,
tests, compression and profiling were excluded from the formal interval;
these controls do not turn the VM into an isolated performance laboratory.

The core binary SHA-256 values are:

- A: `f165ba00ea9a1e266bd1b27efa1a5116512a1a60ba6aa92b40d87baba1400780`
- B: `99f5ce0744c929d7ffa5eb35ad138df92ec9f77f30264e85ac2bb2146ea8e8fb`

Full compiler flags, source/build file hashes, binary identities and input
hashes are retained in the [verified core JSON](benchmarks/m4_core_pairs.json).
Its original guest paths identify evidence provenance; they are not download
links. The [evidence index](m4_evidence_index.md) maps raw records and permanent
archive members; final publication is governed by the release receipts.

## Core matrix and independent verification

The candidate reserves one fixed vector of C slots at construction. `size_t`
indexes and its maximum-value sentinel cover every constructible vector index;
standard vector construction enforces its storage-size limit. Each level keeps
head/tail links and aggregate quantity. A simple free list reuses released
slots, while the map and OrderId index retain their existing roles. There is
no runtime backend switch, generation handle, allocator framework or growth.

Matching admission still rejects a full-book limit before matching; market IOC
does not reserve a resting slot. Every matching step looks up its maker again
and copies the order before fill can reclaim it. New deterministic regressions
cover C=1/C=2, changed owner/arrival order on reuse, FIFO behind a survivor and
maker reclamation across paused stages. Existing deletion, 64-maker sweep,
tiny queues, routing/fd reuse and shutdown tests remain. The full active/free
slot partition and link scan runs only through explicit invariant validation.

The formal core batch ran on 2026-10-17, from 16:51:21 to 16:52:01 UTC.
It contains all five fixed scenes at C=1,000 and 100,000 commands per input,
with five adjacent pairs in AB/BA/AB/BA/AB order: **25 pairs, 50 invocations
and 100 timing intervals**. Each invocation first compares every command's
complete ordered events with the independent vector Reference, retains the
verification ledger and final snapshot, and performs a separate full-input
verified warmup. Latency and throughput each start a new book and setup.
The pair checker confirms equal input bytes, output work, counts, checksums
and final snapshots across A/B and repeats.

All 50 latency intervals contain 100,000 samples; the separate 50 throughput
intervals each complete the same 100,000 commands. Every per-invocation
`repeats=1` record remains labeled below the five-round requirement on its
own. Only the enclosing checked matrix establishes five pairs per scene.
The copied batch contains 793 hash-checked recorded files. Independent host
recomputation reproduces the report, except for five directory fields that
necessarily change when evidence is relocated. The receipt is
`build/m4-measurement/core-host-revalidation.json`; the original raw batch is
`build/m4-measurement/core-run-1`. These are local evidence paths until final
archiving, not a claim of permanent availability.

### Throughput and the frozen decision

The A/B columns below are medians and ranges of the five absolute rates,
in million completed commands/s. The change column is the median and range
of the five **paired** `B/A - 1` values. A ratio of the two independent
medians is a different calculation and is not the adoption metric.

| Scene | A M commands/s, median [range] | B M commands/s, median [range] | Paired change, median [range] | Improved pairs | Frozen core rule |
| --- | --- | --- | --- | --- | --- |
| mixed | 12.764 [11.731, 13.003] | 13.433 [12.899, 13.578] | +5.241% [+2.065%, +13.682%] | 5/5 | pass |
| cancel_heavy | 13.078 [12.927, 13.168] | 13.281 [12.893, 13.521] | +2.710% [-2.092%, +3.197%] | 4/5 | **fail** |
| sweep | 8.295 [8.090, 8.351] | 8.787 [8.683, 8.811] | +6.222% [+5.294%, +7.703%] | 5/5 | pass |
| clustered | 10.694 [10.441, 10.879] | 11.096 [9.638, 11.239] | +3.803% [-11.406%, +6.270%] | 4/5 | pass |
| near_full_reuse | 12.786 [7.433, 13.216] | 11.218 [5.660, 13.603] | +1.978% [-23.848%, +24.712%] | 3/5 | pass |

`mixed` and `cancel_heavy` each require at least +5% and four improving
pairs; the other three scenes permit a paired median regression of at most
5%. All three secondary numerical rules pass, but this does not erase their
individual regressions. `clustered` pair 4 is −11.406%. `near_full_reuse`
pairs 3 and 5 are −12.265% and −23.848%; pair 4 is +24.712%. In that last
scene the independent absolute medians are 12.786M/s for A and 11.218M/s for
B, while the paired median is +1.978%. All observations remain in the report;
no round is discarded and no favorable interpretation resolves the broad
range into a stable advantage.

All 25 individual pair rows and absolute durations are in the
[paired table](benchmarks/m4_core_pairs.md). Command/result counts and
median accepted, rejected and trade rates are shown separately below;
rates are million/s and counts exclude setup.

| Scene | Accepted / rejected / trades per interval | Accepted rate A / B | Rejected rate A / B | Trade rate A / B |
| --- | --- | --- | --- | --- |
| mixed | 100,000 / 0 / 33,334 | 12.764 / 13.433 | 0.000 / 0.000 | 4.255 / 4.478 |
| cancel_heavy | 97,561 / 2,439 / 0 | 12.759 / 12.957 | 0.319 / 0.324 | 0.000 / 0.000 |
| sweep | 100,000 / 0 / 98,432 | 8.295 / 8.787 | 0.000 / 0.000 | 8.165 / 8.649 |
| clustered | 100,000 / 0 / 32,992 | 10.694 / 11.096 | 0.000 / 0.000 | 3.528 / 3.661 |
| near_full_reuse | 97,142 / 2,858 / 2,857 | 12.421 / 10.897 | 0.365 / 0.321 | 0.365 / 0.320 |

There are 2,439 deliberate UnknownOrder cancels in `cancel_heavy`, and 2,858
CapacityExceeded limits in `near_full_reuse`; the other scenes have no
rejections. The new scene reaches 999–1,000 active orders and repeatedly
reuses terminated OrderIds and slots with changed ownership. The old scenes
retain their seeds and working depth of 64: `mixed` reaches 500–501 active
orders, `cancel_heavy` 499–500, and `sweep`/`clustered` 500–564. Sweep commands
reach 64 makers over eight price levels. Whole-stream throughput includes
all the adds and cancels in these patterns; it is not sweep-only speed.

### Latency, duration and timer limits

Values below are medians [minimum, maximum] of the five rounds. Throughput
duration is its independent timed batch, not the sum of individual latency
samples. The complete JSON retains every round's latency sample count,
command/outcome groups, elapsed time and CPU/RSS observations.

| Scene | Variant | Process p50 ns | Process p99 ns | Throughput batch ms |
| --- | --- | --- | --- | --- |
| mixed | A | 42 [42, 42] | 84 [84, 84] | 7.834 [7.690, 8.524] |
| mixed | B | 42 [42, 42] | 84 [84, 84] | 7.444 [7.365, 7.753] |
| cancel_heavy | A | 42 [42, 83] | 84 [84, 125] | 7.647 [7.594, 7.736] |
| cancel_heavy | B | 42 [42, 42] | 84 [84, 84] | 7.530 [7.396, 7.756] |
| sweep | A | 42 [42, 83] | 1125 [1125, 1375] | 12.055 [11.974, 12.361] |
| sweep | B | 42 [42, 83] | 1000 [1000, 1333] | 11.381 [11.349, 11.517] |
| clustered | A | 42 [42, 42] | 583 [542, 583] | 9.351 [9.192, 9.577] |
| clustered | B | 42 [42, 42] | 500 [500, 583] | 9.012 [8.897, 10.375] |
| near_full_reuse | A | 83 [42, 83] | 84 [84, 250] | 7.821 [7.566, 13.453] |
| near_full_reuse | B | 42 [42, 84] | 84 [84, 250] | 8.914 [7.352, 17.666] |

The throughput batches last only 7.352–17.666 ms overall. Completing 100,000
commands does not lengthen these into stable wall-clock experiments. The
latency clock encloses `process` and result generation; its separate batch
also includes the clocks, checks, output consumption and sample recording.
The throughput loop has no per-command clock but still consumes every
output field and checks status. Setup, Reference, parsing, sample output and
final validation remain outside both timing intervals.

All 50 clock probes observe a 41 ns minimum positive interval and a 42 ns
back-to-back p99, despite the nominal 1 ns period. The back-to-back p50 ranges
from 0 to 42 ns, with 24,934–67,151 zero intervals out of 100,000 probes.
Recording a clock pair and duration averages 28.428–67.389 ns per observation
across probes. A commonly observed 42 ns process p50 is therefore strongly
quantized; it is not evidence for a precise few-nanosecond improvement.
No clock constant is subtracted. Overall p99 meets the 100,000-sample
reporting threshold, while command/outcome groups have their own smaller
sample counts; neither establishes tail stability, and no p99.9 is claimed.

CPU deltas cover the respective loop and harness. Benchmark RSS is the
process high-water mark, including parsed inputs, Reference, snapshots,
warmup, samples and previous activity in that process. The recorded range
is 35,008,512–89,976,832 bytes; it is not a measurement of order slots or
allocator-resident order memory. A small or equal RSS value cannot cancel
the explicitly observed reserved-memory cost below.

## Allocation, initialization and memory cost

The separate Linux diagnostic uses the same frozen A/B sources and its own
instrumented executable. It measures 2,000-command traces for `mixed`,
`cancel_heavy` and `near_full_reuse`; it is not part of formal timing.
Independent inspection checked 103 copied files and all six source/binary/
input bindings, Reference outcomes and allocation lifetime balances. The
[diagnostic account](m4_diagnostics.md) retains the earlier macOS control
observations separately and gives the full Linux A/B result and scope.

| Diagnostic scene | Successful resting additions | C++ allocation requests A → B | C++ frees A → B | Requested bytes during input A → B |
| --- | --- | --- | --- | --- |
| mixed | 667 | 2,001 → 1,334 | 1,998 → 1,332 | 112,056 → 69,368 |
| cancel_heavy | 976 | 1,969 → 993 | 1,970 → 994 | 94,920 → 40,128 |
| near_full_reuse | 971 | 1,942 → 971 | 1,942 → 971 | 93,216 → 38,840 |

The reduction is one allocation request per resting addition, consistent
with removing separately allocated list nodes. The remaining requests
include OrderId hash nodes and, when created, price-map nodes. B is not a
zero-allocation core or service. Its price-level payload also changes with
the new links, so requested-byte differences do not all represent slot
allocation alone. Allocation and locality change together; there is no
isolated cache or allocator causality measurement.

Each candidate slot is 56 bytes, aligned to eight bytes: C=1,000 reserves
**56,000 bytes** for slots. Empty engine tracked requested heap bytes rise
from 11,048 to 67,048. After the half-full mixed setup they are 60,200 for A
and 88,072 for B; after the full 1,000-order setup they are 108,200 and
108,072. The 128-byte difference at full occupancy is not a general memory
saving. These counters exclude allocator metadata, padding and diagnostic
headers; process RSS and total allocator occupancy are different quantities.

Each scenario records 100 fresh OrderBook constructor observations. The
instrumented medians are 83–84 ns for A and 916–958 ns for B; the first
observations are also retained. This interval includes hash bucket reserve
and slot construction, not parsing or Reference; destruction occurs outside
it. Counters are disabled, but the diagnostic replacement allocator still
adds its header/alignment overhead. These are diagnostic constructor
observations, not production startup latency or isolated slot initialization
measurements. No startup speedup or exact production startup cost is inferred.

## Service regression experiment

The four-scene `m4-formal` subset contains 20 adjacent pairs and eight separate
warmups. All **48 attempts fully deliver, drain and pass actual-admission
Reference replay**; all 40 formal runs meet their sample/plan-window contract.
They complete **4,000,030 of 4,000,030 planned measured requests**, with no
rejections, failed, unstarted or unfinished requests. Each non-burst formal
run completes 100,001 requests; burst completes 100,000. Setup adds 500
admissions per attempt. Every server retains single-frame writes, zero
discarded frames, zero missing business recipients and zero unconfirmed bytes.

All 941 collected files (1,132,867,731 bytes) pass SHA-256 checks. Independent
host parsing/recomputation using the archived tools reproduces all eight
derived files byte-for-byte. Originals remain unchanged. See
`build/m4-measurement/service-host-revalidation.json`, the complete
[pair table](benchmarks/m4_service_pairs.md) and
[machine-readable report](benchmarks/m4_service_pairs.json).

RTT values below are five-round absolute medians in microseconds. Percentage
changes are medians [range] of the five paired values, not a ratio of the
absolute medians or a pooled percentile.

| Scene | RTT p99 A / B, us | Paired RTT p99 change [range] | Paired service p99 change [range] | RTT rule |
| --- | --- | --- | --- | --- |
| mixed_1 | 95.499 / 100.790 | +1.600% [-38.399%, +23.044%] | -3.327% [-38.235%, +7.369%] | pass |
| mixed_4 | 105.876 / 99.918 | -0.704% [-21.984%, +69.571%] | +0.706% [-9.412%, +39.474%] | pass |
| sweep_4 | 222.335 / 226.543 | +1.893% [+0.528%, +5.418%] | +26.438% [-1.030%, +65.511%] | pass |
| burst_4 | 4093.027 / 4006.404 | +0.209% [-11.376%, +1.339%] | -13.771% [-54.145%, +30.110%] | pass |

All four RTT paired medians are below the frozen +10% ceiling. That is not
evidence of no service regression: sweep's internal completion p99 rises by
a paired median 26.438%, and mixed_4 pair 3 has a 69.571% RTT increase. Sweep's
absolute service p99 medians are 28.250 us for A and 39.375 us for B. The
finite shared-VM experiment does not isolate causes for these tail changes.
The service pass cannot override the mandatory core cancel-heavy failure.

| Scene | Server CPU us/completed measured request A / B | Paired CPU change | Server peak RSS A / B, bytes | Send-lag p99 A / B, us |
| --- | --- | --- | --- | --- |
| mixed_1 | 34.161 / 34.179 | -0.318% | 38,289,408 / 38,289,408 | 37.935 / 38.191 |
| mixed_4 | 42.941 / 41.978 | -1.406% | 38,289,408 / 38,289,408 | 36.559 / 35.777 |
| sweep_4 | 36.175 / 36.832 | +0.313% | 39,014,400 / 39,014,400 | 37.404 / 65.680 |
| burst_4 | 40.947 / 40.366 | -3.628% | 39,989,248 / 40,030,208 | 4990.324 / 4996.144 |

Absolute entries are five-round medians. Server/loadgen CPU covers process
lifetime before evidence output, including setup; loadgen also includes input
preparation. Dividing server CPU by measured completions is an amortized
observation, not a request-only CPU interval. RSS is a whole-process high-water
mark. Every loadgen's CPU/RSS, full ranges, counts and queue high-water values
remain in the pair JSON/table. No memory saving is inferred from equal RSS.

The three continuous scenes run about 10.0001 seconds at 10k requests/s.
Burst uses a 50-second plan at 2k/s average; the last scheduled burst ends
before the final idle part of that window, so measured elapsed durations are
49.9101–49.9119 seconds. Burst send lag is about 5 ms at p99 and RTT about
4 ms; RTT begins at actual sending, while send lag separately measures delay
relative to the schedule. Throughput at these fixed rates is not a new service
capacity measurement. Formal high-water maxima are 142 commands, 565 events
and 30,880 send bytes; there are no output waits. Existing
1,024-slot queues, 65,536-byte send limits and other M3 bounds remain fixed.

## Reproduction and final delivery

The selected production path is the measured list control, recorded in
[ADR 006](adr/006-fixed-order-storage.md). A new public Linux clone of A and
new dependency/build directories passed all 108 Release tests, two actual
CLI clients, core smoke and the seven-scene network smoke. A separate new B
clone/dependency/build supplied two near_full_reuse core pairs, 2,000 commands
per invocation and eight timing intervals. This is a functional smoke, not
a new performance result or a revision of the frozen decision. The Linux
system toolchain and VM were reused, with fresh project/dependency builds.
The 5,947 selected copied files (56,766,037 bytes) and both tracked-source
hash maps match the recorded A/B commits. Independent host checks confirm the
fresh source/build bindings, eight required JUnit groups, raw CLI/Reference
results and all three independently recomputed summaries. Only core output
directory fields relocate; original raw files remain unchanged. See the
[acceptance record](m4_acceptance.md).

Reproduction commands are in the [core method](benchmark_method.md#paired-m4-order-storage-comparison)
and [service method](service_benchmark_method.md#m4-service-regression-subset).
The final PR/exact-main CI inspections, permanent archives and uploaded-asset
checks are recorded in the `m4-order-storage` release's `acceptance.json` and
`publication-verification.json`; intermediate checks cannot replace them.
Developed by [Owenqi666](https://github.com/Owenqi666) with assistance from OpenAI
Codex. The measurements and automated evidence review described here were
executed by Codex agents; see the [development workflow](development.md#development-workflow).
