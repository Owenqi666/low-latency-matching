# Gateway diagnostics: observations and attribution limits

G03 observation collection and G04 reproduction/diagnostic analysis are complete.
They supported proceeding to G05 and the separately frozen G06 comparison.
The complete [formal report](gateway_report.md#formal-results-and-frozen-gates)
now rejects batch16 under the frozen rules and retains batch1; G09 delivery
verification is still pending. The measurements below remain the independent
G04 diagnostic dataset, not profiles of the later formal failures or regressions.
Historical M3 rejection remains unchanged.

## Questions to resolve

| Hypothesis | Required observation | What that observation cannot establish alone |
|---|---|---|
| Existing queued-frame batching reduces application write overhead | write operations/admitted, submitted frames/operation, batch distribution, whole-callback duration; separate syscall profile | One async_write is a composed operation, not one syscall |
| Single-client tail regression involves output completion or Gateway scheduling | Same-process window samples, output/in-flight state, callback intervals and loop timer lateness, alongside service and client samples | Lifetime high-water/histograms alone do not establish ordering or causality |
| SlowClient reflects Gateway or peer/output congestion | Connection close snapshot, outstanding frames/bytes, last callback, queue states and delivered/missing recipients | The close reason does not prove the peer stopped reading |
| Load generation constrains delivered offered load | Scheduled-to-start lag over planned-time windows, actual sending interval and pending sends | Eventual completion does not prove stability at the advertised offered rate |

## Thread and lifetime boundaries

Connection, SendQueue and Gateway diagnostic state are owned by the Gateway
thread. The worker's non-atomic PipelineStats and completion vectors are read
only after join. Live queue depth must use the producer-side command queue and
consumer-side event queue availability APIs, not the worker's mutable counters.
schedule_pump can run on both threads and must not write an unsynchronized timing
field. A Gateway timer measures its own scheduled-versus-actual callback time.

Closing snapshots are taken before SendQueue discards queued/in-flight frames.
Late callbacks must still count as unconfirmed under the existing semantics and
must not produce duplicate close records. Successful socket writes do not imply
application-level peer receipt. Existing basic server.json field meanings remain
unchanged; detailed records are an optional, separately versioned artifact.

## Implemented observation bounds

Enable detailed collection with `--gateway-diagnostics 1` and use `--output-dir`
to retain its artifacts after shutdown. The default is off: no detailed collector,
timer or detailed clock collection is created on that path. Optional collection
uses 128 close records, 4,096 global windows, 16,384 connection windows and three
64-bucket histograms. The collector occupies 2,442,960 bytes on the current arm64
build; per-connection SendQueue observation fields are additionally bounded by
the existing maximum connection count. No background thread or hot-path file
writes are introduced.

The existing single-version and paired runners also accept the optional boolean
`gateway_diagnostics: true` in a separate smoke/calibration manifest. The setting
is recorded with the workload and checked against each server report. Formal
manifests reject detailed diagnostics; performance runs retain the default off.

The nominal sample period is 10ms, scheduled after each actual callback, without
catch-up bursts. At 64 persistent connections, connection records may cover only
about 2.56 seconds even while global windows cover about 40.96 seconds; callbacks
delayed by load stretch those times. These are capacity examples, not measured
coverage guarantees. JSON and CSV files report actual timestamps, retained first
and last times, and separate overflow counts. Only observed windows support claims.

`gateway_diagnostics.json` describes schema, clock, bounds, coverage and duration
histograms. `gateway_windows.csv` holds global counters/deltas and safe queue
occupancy snapshots. `gateway_connections.csv` holds per-connection outbound
state at those times. `gateway_closes.csv` records each retained pre-discard close
state and reason. Total bytes/frames already include in-flight storage; queued-only
state is their difference. An in-flight operation retains its entire batch until
the composed callback, even after an underlying partial socket write.

The optional checker in `summarize_service_bench.py` validates headers, record
bounds, overflow accounting, histogram extrema, callback/close totals, ClientId
ranges, per-connection totals and outstanding-write/in-flight consistency,
batch/allowance high-water bounds, window deltas and time association.
Legacy reports without the new switch remain readable. Disabled runs reject
stale detailed artifacts. Tests mutate real artifacts to check rejection rather
than merely checking that serialization reproduces its own values.

Local checks include actual Asio timer delivery and cancellation at shutdown,
real TCP traffic with ten live windows in the observed test, controlled storage
overflow, and existing short-write/cancel/late-callback/duplicate-close cases.
The selected 17-test Gateway/network group passed. Cross-platform integration,
sanitizer checks and experiment-source identities are recorded in the
[evidence index](gateway_evidence_index.md); that index distinguishes each
executed check from remaining delivery work.

Profile only representative mixed_1/mixed_4 runs outside performance timing.
Record per-thread CPU, scheduling/context switches and available syscall/call-stack
data. Tool/permission limitations remain explicit. Cross-process association must
state host clock/alignment; clocks from different machines are not subtracted.

## Evidence identity and offline reproduction

The two source identities are A `7d9d7dc0a6ab386d2d381f401ce644e621e33d33`
(batch1) and B `56d5c71e7daec7631272dbc7b10a0f430f3381e0` (batch16).
The recorded build inputs differ only in the frame-limit constant; both retain
16 descriptors, a 4,096-byte batch limit, a 65,536-byte connection allowance and
1,024-slot command/event queues. There is no wait-to-fill timer. The shared
measurement tools are `6f3ef0878668e428fb5fa69277226d0b19dcd6de`; A supplies the
shared loadgen and verifier. Source records and binary hashes are retained in
each pair report. These observations came from one aarch64 Linux 6.8 host with
GCC 13.3 and same-host server/loadgen, not the external review's x86 VM.

Paths below are relative to the repository root. Raw evidence under `build/` is
local and not tracked; it must accompany this report for independent recomputation.

| Evidence | Path | Scope |
|---|---|---|
| Clean G04 pairs | `build/gateway-optimization/repro/pairs-01/pair-report.json` and sibling run directories | Five pairs per row; all 20 measured attempts and four warmups retained |
| Diagnostic invocation and host-clock record | `build/gateway-optimization/diagnostics/run-01/{plan,driver,clock,preflight}.json` | One independent pair for each row, plus one warmup per version/row; profilers attach only to measurements |
| Raw diagnostic observations | `diagnostics/run-01/proc-samples.jsonl`, target directories with `perf.data`, `perf-script.txt`, `*-stat.log` under the same `build/gateway-optimization/` root | Eight observed server/loadgen processes; 24 observer exits and runner exit all zero |
| Service/client evidence | `diagnostics/run-01/pair/{baseline,candidate}/runs/{mixed_4,mixed_1}/round_1/` under that root | Diagnostics JSON/CSVs, service/client samples, run metadata and exact inputs |
| Recomputed analysis | `build/gateway-optimization/diagnostics/analysis-01/` | `analyze.py`, `analysis.json`, `analysis.md`, four `*-timeline.csv` files |

The collected diagnostic bundle contains 276 hash-verified files. The offline
analysis rechecks its 74 consumed files listed in collection manifests and
compares input/setup/schedule/config SHA-256 against every corresponding clean
attempt. Both sets use 100,001 measured commands and 500 setup commands per run;
row order and seeds are preserved. The diagnostic manifest enables detailed
collection and reduces rounds to one; profiling is additional interference.
Its results are kept separate from clean G04 measurements.

Recompute existing data without starting a service or profiler:

```sh
python3 build/gateway-optimization/diagnostics/analysis-01/analyze.py
```

The script accepts `--diagnostics`, `--clean` and `--output` for relocated copies.
It records consumed-file SHA-256 values and per-thread coverage in `analysis.json`.
The original raw files are unchanged.

## Clean G04 reproduction result

These are paired medians from the two-row reproduction, not adoption thresholds
applied to a complete formal matrix. Lifetime CPU is amortized over completed
measured requests and includes setup. Application write/admitted includes setup
in both numerator and denominator; it counts composed operations, not syscalls.

| Row | CPU per measured completion, B/A change | RTT p99, B/A change | Median application writes/admitted, A → B |
|---|---:|---:|---:|
| mixed_4 | −8.615% | −4.996% | 6.983 → 4.984 |
| mixed_1 | −8.132% | +0.638% | 3.996 → 1.999 |

All measured attempts passed Reference, delivery, drain and sample-count checks.
The old persistent single-client median RTT regression was not reproduced here.
That does not mean every pair improved: mixed_4 round 5 RTT p99 rose from 84,544
to 117,836 ns (**+39.378%**). Its send-lag p99 rose from 28,533 to 46,047 ns and
service p99 from 21,334 to 25,292 ns. The row remains in every calculation and
its cause remains unexplained. A later profiled run cannot explain it retroactively.

## Diagnostic CPU, syscalls and retained stacks

The following CPU values are differences of the same live `/proc` thread's
cumulative ticks, using only samples entirely inside the client measurement
interval. The main server TID is Gateway; its sole other thread is identified as
the inferred Matching worker. Loadgen values below refer to its main thread.
No standalone core-benchmark result is subtracted from service CPU.

| Diagnostic run | Observed span s | Gateway CPU s (system) | Matching CPU s (system) | Loadgen CPU s (system) |
|---|---:|---:|---:|---:|
| A mixed_4 | 9.881 | 3.15 (2.74) | 1.32 (1.03) | 2.22 (1.64) |
| B mixed_4 | 9.890 | 2.83 (2.46) | 1.32 (1.01) | 2.13 (1.55) |
| A mixed_1 | 9.873 | 2.57 (2.02) | 1.24 (0.93) | 1.73 (1.54) |
| B mixed_1 | 9.897 | 2.19 (1.81) | 1.21 (0.78) | 1.61 (1.08) |

The analysis retains voluntary/involuntary context-switch differences separately
for every TID and span. In these measurement subsets Gateway has about 197–198k
voluntary switches, Matching 198–228k and loadgen 189–193k; involuntary counts
are 1–7 per main/worker thread. These counts neither measure wait duration nor
exclude scheduling stalls outside the observed subset. Tick resolution is 10 ms;
reads of different threads are not atomic.

Actual `sys_enter_sendmsg` counts come from tracepoints. The roughly 11.011 s
reported stat spans include attach/startup and process-tail evidence output.
Interior rates omit the first and final incremental interval, leaving about
nine reported seconds; they are observation rates, not exact request-only rates.

| Gateway diagnostic run | Observed sendmsg count | Interior sendmsg/s | Lifetime application writes |
|---|---:|---:|---:|
| A mixed_4 | 700,471 | 69,992.1 | 701,795 |
| B mixed_4 | 499,431 | 49,805.3 | 499,431 |
| A mixed_1 | 401,576 | 40,000.0 | 401,576 |
| B mixed_1 | 200,982 | 19,998.7 | 200,982 |

The real syscall direction agrees with fewer application writes. The mixed_4 A
count mismatch also demonstrates why their scopes cannot be interchanged.
Matching threads recorded zero across the five observed send/write events;
this is not a count of all syscalls. Loadgen main-thread `sendto` totals are
100,133 for A mixed_4 and 100,501 for the other runs, with the same attachment
limits. The collected `write`/`writev` counts include any file descriptor,
including evidence files; they are not labelled network writes.

Retained task-clock stacks inside the measurement interval also show network and
synchronization paths. Counts below are raw samples with inclusive, overlapping
categories, not exact CPU shares or time spent blocked.

| Gateway diagnostic run | Samples | Kernel leaf samples | TCP/socket stack samples | Futex/mutex/condition stack samples |
|---|---:|---:|---:|---:|
| A mixed_4 | 266 | 215 | 144 | 70 |
| B mixed_4 | 233 | 179 | 100 | 83 |
| A mixed_1 | 208 | 167 | 96 | 64 |
| B mixed_1 | 169 | 134 | 77 | 51 |

Gateway's most frequent sampled leaf is `try_to_wake_up`; Matching has 67–73
measured samples per run, with kernel `mutex_unlock` its most frequent leaf.
The full symbol lists and category regexes remain in `analysis.json` and the
raw stack exports. Profiles report zero lost samples, but low sample counts and
4,096-byte DWARF stack capture still limit interpretation. There are no off-CPU
stacks. Hardware cycles/instructions were unavailable; these are software
`task-clock` profiles collected with noninteractive sudo, not hardware profiles.

## Diagnostic queues, callbacks and time windows

All four diagnostic measurements completed and drained 100,001 requests.
Lifetime counters include setup; sampled peaks and lifetime peaks are distinct.
No run recorded output waits, missing recipients, discarded business frames,
unconfirmed writes, write-error closes or SlowClient closes. All retained close
snapshots had empty outbound queues. mixed_4 closes were one `peer_eof` and
three `read_error`; mixed_1 had one `peer_eof`. These reasons at successful run
shutdown do not establish a delivery failure or a non-reading client.

| Diagnostic run | RTT p99 µs | Send-lag p99 µs | Gateway wait p99 µs | Service p99 µs | Lifetime command/event peak | Lifetime connection-byte peak / limit |
|---|---:|---:|---:|---:|---:|---:|
| A mixed_4 | 96.336 | 31.355 | 0.209 | 24.792 | 2 / 8 | 944 / 65,536 |
| B mixed_4 | 111.461 | 42.277 | 0.250 | 26.876 | 79 / 200 | 15,456 / 65,536 |
| A mixed_1 | 89.460 | 31.450 | 0.209 | 24.501 | 5 / 20 | 2,360 / 65,536 |
| B mixed_1 | 86.086 | 31.292 | 0.209 | 24.459 | 4 / 16 | 1,888 / 65,536 |

| Diagnostic run | Whole composed-write p99 bucket ns | Exact whole-write max ns | Callback-interval p99 bucket ns | Measured timer-lateness max ms |
|---|---:|---:|---:|---:|
| A mixed_4 | 16,384–32,767 | 626,390 | 65,536–131,071 | 2.357 |
| B mixed_4 | 16,384–32,767 | 12,336,879 | 65,536–131,071 | 8.507 |
| A mixed_1 | 8,192–16,383 | 92,835 | 65,536–131,071 | 0.864 |
| B mixed_1 | 4,096–8,191 | 54,710 | 65,536–131,071 | 3.136 |

Histogram quantiles are bucket intervals across the server lifetime, including
setup and final callbacks, not exact per-request quantiles. Timer maxima in the
last column are recomputed only from windows inside the measurement interval.
Callback interval is neither request latency nor continuous underlying write
progress; timer lateness is not kernel wake-up latency.

| Diagnostic run | Global windows, measured / retained | Connection windows, measured / retained | Closes |
|---|---:|---:|---:|
| A mixed_4 | 997 / 1,010 | 3,988 / 3,996 | 4 |
| B mixed_4 | 995 / 1,006 | 3,980 / 3,988 | 4 |
| A mixed_1 | 998 / 1,011 | 998 / 1,000 | 1 |
| B mixed_1 | 997 / 1,007 | 997 / 999 | 1 |

There was no diagnostic retention overflow. The nominal 10 ms timer is sampled
only when its callback runs, so short-lived peaks can be missed. At 100 ms bin
resolution, B mixed_4's 8.5–8.6 s interval has send-lag max 12.166 ms, timer
lateness max 8.507 ms, service p99 2.376 ms and RTT p99 15.886 ms. Its sampled
command depth peaks at 37, event depth at zero and outbound bytes at 2,824;
these are not the lifetime peaks 79/200/15,456 above. The zero sampled event
depth therefore does not prove an empty event queue throughout the interval.

In 100 populated bins, B mixed_4's send-lag p99 versus timer-max Pearson value
is 0.959, while the other runs range from −0.102 to 0.077. This is a descriptive
association dominated by an exceptional bin, not a causal estimate. Per-request
end-to-end latency is computed as `complete_ns - scheduled_ns`; send-lag p99 and
RTT p99 are never added.

## Clock alignment and missing coverage

The `/proc` observer uses Python `CLOCK_MONOTONIC` and perf explicitly requests
`CLOCK_MONOTONIC`; perf headers confirm that clock. Client/server timestamps use
C++ `steady_clock`. Same-host alignment assumes the Linux/libstdc++ monotonic
mapping and agrees numerically with the recorded spans; no independent offset
calibration was performed. Analysis bins are anchored to each client's own
measurement start: client rows by scheduled time, service rows by admission
time and Gateway snapshots by observation time. Timestamps are never subtracted
across runs or machines. Exact begin/end values are retained in the analysis.

Perf-stat timestamps are relative to event enable, whose precise monotonic start
was not captured. Observer launch time is only a lower bound, so stat intervals
are not joined as precise same-clock events. Profilers attach after PID discovery;
actual first/last CPU samples, observed process identity and `/proc` spans are
retained, not represented as continuous or full-lifetime coverage.

Five tracepoints were available: `write`, `writev`, `sendto`, `sendmsg`, and
`sendmmsg`; numeric stat rows reported 100% running. A mixed_4 loadgen auxiliary
TID 5680 has 50 `<not counted>` event intervals, retained as missing rather than
zero. Auxiliary loadgen TIDs 5794, 5747 and 5831 were seen in `/proc` but absent
from the corresponding stat attachment. No syscall assertion covers those
threads. A final counted zero or a zero CPU tick difference does not recover
missing intervals. Read-side, futex and scheduling syscall totals were not
collected. Detailed timers, tracepoints and profiler activity may alter tails;
this single diagnostic pair per row provides no unbiased performance effect size.

## Observation → supported explanation → not excluded

| Direct observation | Supported explanation | Still not excluded / scope |
|---|---|---|
| Clean application writes/admitted fall; observed sendmsg rates fall in the same direction; Gateway CPU is predominantly system CPU and exceeds Matching CPU | Network delivery and per-write work are material costs; these observations justified carrying existing queued-frame batching into finite G05/G06 | Sparse task-clock samples do not quantify an exact component share or prove matching-core saturation; the later formal rejection is separate from these observations |
| Clean mixed_1 median RTT changes by +0.638%, while its median CPU falls 8.132%; all runs deliver and drain | The old persistent single-client regression is not reproduced in this fixed environment | Other rates, scenarios and hosts may regress; the full formal constraints still apply |
| Diagnostic B mixed_4 has a transient shared send-lag/timer/service/RTT excursion with bounded queues and later full drain | A scheduling or output-progress interruption is consistent with these observations | Loadgen scheduling, Gateway scheduling, host scheduling and profiler interference cannot be separated; neither a non-reading peer nor pump starvation is established |
| Clean mixed_4 round 5 has +39.378% RTT p99 alongside higher send-lag and service p99 | The regression affects multiple reported stages and must remain visible | Its cause is unexplained; the later diagnostic excursion cannot be used as its causal trace |
| No G04 clean or diagnostic 10k/s run reproduces the external delivery failure | This environment completes those selected G04 workloads under their actual configuration | Later formal A mixed_1 round 4 loses delivery at 10k/s; the external x86 VM/workload/scheduler equivalence and failure mechanism remain unresolved, so no universal reliability claim follows |

These results do not isolate a mechanism for a separate scheduling/input-throttle
change. G04 preserves useful candidate benefit and unresolved tails; the separate
G06 decision determines whether production should change.

## What the completed G06 comparison adds

The independent G06 evaluator validates all 35 pairs and selects A under the
unchanged adoption rules. All five near pairs improve CPU/completion, but their
6.402527% median reduction is below 10%. Near RTT p99 and scheduled-to-complete
p99 regress by 13.717391% and 10.094805%, above their respective 10% ceilings.
Those are actual full-pair numeric breaches. The [full report](gateway_report.md)
and [all-pair tables](benchmarks/gateway_service_pairs.md) retain the ranges,
absolute values, incomplete ordinary pairs and every failed outcome.

| Formal observation | Supported explanation | Not established |
|---|---|---|
| B completes all 35 measurements, including all five overload runs; A loses delivery in five overload runs | B improves delivered overload work in this fixed matrix; completed/planned increases by a paired median 74.866766 percentage points | Universal sustainable capacity, cross-host improvement, or enough benefit to waive the failed near gates |
| A burst round 2 completes 1,553/100,000, records four SlowClient closes, send high-water 65,536 bytes and one output wait; A mixed_1 round 4 completes 91,325/100,001 with one SlowClient close and send high-water 65,470 | The control experiences bounded output-pressure delivery failures in these formal runs; admitted work still drains and Reference passes | B caused those failures; an environmental fault; the peer stopped reading; input throttling would solve the mechanism |
| Near application writes/admitted fall from median 6.992 to 4.892, while both near tail medians breach their limits | Fewer composed writes coexist with a CPU benefit and an unacceptable latency tradeoff under the frozen contract | Syscall counts during these unprofiled runs, or the temporal cause of the near regressions |

Detailed diagnostics and profilers were off for G06. Its cumulative counters
cannot establish event ordering or causality. G04's profiled B mixed_4 excursion
and its separate clean +39.378% outlier remain exactly those earlier observations;
neither is relabelled as an explanation of a formal failure. Unknown causes stay
unknown and are not automatically called environment noise.

**G07 is not triggered.** The evidence does not isolate a reproducible
input-admission mechanism or establish pump starvation. Generic overload,
SlowClient reasons and high-water marks do not independently meet that trigger.
No throttling, work-budget or waiting-policy change is added to the batch
experiment. [ADR 008](adr/008-retain-single-frame-gateway.md) records the decision
and the evidence needed before any separate follow-up comparison.
