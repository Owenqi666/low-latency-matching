# M2 service measurement report

<!-- RESULTS:BEGIN -->
The corrected Linux VM matrix contains all **35 measured rounds and seven
independent warmups**. Independent evidence validation passed; **30/35 measured
rounds delivered all planned requests**, and 34/35 met the normal sample
threshold. Client completions total 5,754,789 of
8,750,030 planned requests. There were 2,993,691
not-started, 1,550 failed-started and 0
unfinished requests. These outcomes remain separate from the 35/35 server
drains. The detailed rows below retain failed attempts and their actual sample
counts; evidence validity does not mean every request succeeded.
<!-- RESULTS:END -->

## Source and environment

The corrected network measurement source is
`eb0a109b026c8ac9cf48d987163fad8751980047`. It changes loadgen to combine the
prebuilt relative offset with the clock anchor only when scheduling or exporting
a request. Server and verifier binaries remain identical to the earlier matrix;
there is no change to the matching algorithm, network service or frozen rates.

| Binary | SHA-256 |
|---|---|
| matching_server | `2348899014ba8415c1b4f6212541fb9ef61c6c5644af8631ae1a56a2812c4c23` |
| loadgen | `411cd79c93f94bcd2ffde56594d32c6299280b4c63c6526e24cba5a14c1048ee` |
| verify_service | `bdc3b6b9449e9bb42665a889ac0c98b3966835ccfe962babf3d7d141e0bec1ac` |

The source transition and binary hashes are retained in
`build/m2-measurement/loadgen-fix-transition.txt`. Execution was performed by
Codex agents, not a claimed human benchmark or personal learning assessment.

<!-- ENVIRONMENT:BEGIN -->
| Property | Recorded value |
| --- | --- |
| Source state | `eb0a109b026c8ac9cf48d987163fad8751980047`; code_dirty=false |
| Guest | Linux-6.8.0-142-generic-aarch64-with-glibc2.39; 4 vCPUs; 4096 MiB assigned RAM |
| Physical host | macOS 26.6.2 (25G83); Apple M5 Pro; 18 cores; 48 GiB RAM |
| Virtualization / transport | QEMU 11.1.2 HVF; server and loadgen share guest TCP loopback |
| Build | GCC 13.3.0; C++20; Release `-O3 -DNDEBUG`; sanitized=false |
| Thread placement | Gateway and Matching threads; independent loadgen process; not changed by this runner; exclusive_core=false |
| Frequency / turbo | not controlled / not controlled |
| Background | Codex and host OS active; no concurrent VM builds or tests during measurement |
| Run UTC window | 2026-10-16T23:50:38.937219+00:00 → 2026-10-17T00:00:14.092227+00:00 |

The UTC window includes input generation, setup, file output and verification; it
is not a latency interval. Guest topology is not exclusive physical-core ownership.
These are shared-host VM loopback observations, not bare-metal, cross-machine or
production-market results.
<!-- ENVIRONMENT:END -->

## What is timed

| Metric | Interval and sample population |
|---|---|
| Client RTT | First actual `async_write` attempt to receipt of the complete CommandComplete frame; only requests completed at the client. It excludes time waiting before that first attempt. |
| Service completion | Immediately before successful command-queue push to successful Complete publication into the event queue; all internally completed measured admissions, including results a disconnected client never receives. Includes queueing, matching, BBO and output backpressure, but excludes Gateway delivery. |
| Send lag | Planned absolute send time to first actual write attempt; every started measured request, including eventual failures. Unstarted requests have no latency sample and remain in the loss counts. |
| Gateway wait | Read callback receiving a frame's final byte to successful admission. Coalesced complete frames retain the same readiness timestamp while waiting behind earlier admissions. |
| Synchronous core | One `process` call to all business events in its no-wait receiver; separately measured and linked below. It has neither service queues nor TCP/BBO delivery. |

RTT uses the receive callback's entry time, before digest processing. Each duration
uses one process's steady clock; no server/client clock subtraction is performed.
Service push timing includes the successful queue operation. Percentiles use
nearest rank within each round, without subtracting a clock constant. Distinct
sample populations mean service and RTT percentiles cannot be subtracted to
estimate a network-only delay.

Reported attempted and completed rates divide by the client's measurement start
through final completion or bounded drain/termination. They are whole-window
rates, not the frozen target rate or a steady interval selected after losses.
For a failed run that loses its connections early, the remaining finite schedule
still contributes to this window. Local full-frame writes are reported separately
and do not prove peer receipt. Setup is outside latency samples; server CPU and
peak RSS cover its lifetime through shutdown, before evidence formatting, and
include setup. CPU totals are not percentages of a matching-only core.

## Fixed workloads and limits

Rates and input-generation rules were frozen in the
[formal manifest](../data/workloads/service-formal.json) before the first matrix;
the corrected repeat retains them unchanged. The
[calibration record](m2_rate_selection.md) retains both short calibration batches
and their later-discovered loadgen limitation. Each of seven rows has one
independent 1,000-request warmup and five fresh measured server instances.

<!-- WORKLOADS:BEGIN -->
| Row | Clients | Target/s | Planned/round | Last offset s | Limit/market/cancel | Seed | Final live orders |
| --- | --- | --- | --- | --- | --- | --- | --- |
| mixed_4 | 4 | 10000 | 100001 | 10.000000 | 60001/20000/20000 | 20261016 | 501 |
| cancel_heavy_4 | 4 | 10000 | 100001 | 10.000000 | 48781/0/51220 | 20361019 | 500 |
| sweep_4 | 4 | 10000 | 100001 | 10.000000 | 98463/1538/0 | 20461022 | 531 |
| burst_4 | 4 | 2000 | 100000 | 49.909950 | 60000/20000/20000 | 20561025 | 500 |
| mixed_1 | 1 | 10000 | 100001 | 10.000000 | 60001/20000/20000 | 20661028 | 501 |
| mixed_4_near | 4 | 45000 | 450001 | 10.000000 | 270001/90000/90000 | 20761031 | 501 |
| mixed_4_overload | 4 | 80000 | 800001 | 10.000000 | 480001/160000/160000 | 20861034 | 500–502 |

Setup begins with 500 live orders. Input metadata preserves the working and
background price distributions, exact command ratios and per-run file hashes.
Final live-order counts come from Reference-checked snapshots; no unrecorded
peak live-depth estimate is claimed. Deliberate UnknownOrder cancellations in
`cancel_heavy_4` are business rejections, not transport failures.
<!-- WORKLOADS:END -->

Capacity is 1,000 orders with 500 mostly passive setup orders. Both SPSC queues
have 1,024 effective slots; server and client send limits are 65,536 wire bytes;
loadgen permits at most 16,384 in-flight requests. Client drain and server shutdown
deadlines are five seconds. Per-run record capacity is setup plus planned requests.
Actual admission order, command/event sequences and final snapshots are retained.
See the [capacity budget](service_architecture.md#capacity-budget) for the distinction
between wire-byte limits, container storage and process RSS.

Sweep inputs replenish at least 64 orders per planned market sweep; whole-stream
throughput includes those limit orders. Cross-client interleaving can change the
actual makers and final state, so each actual admission trace is independently
verified. Temporal burst packs each 100 ms period's arrivals into 10 ms; it uses
2,000/s average planned rate and is not merely a concentration of price levels.
The one-client mixed case uses the same 10,000/s aggregate target as four-client
mixed. Names `near` and `overload` are frozen experimental labels, not conclusions
about sustainable capacity.

## Five-round observations

<!-- TABLES:BEGIN -->
| Row | Success | Sample target | Completed/round | RTT p99 us | Service p99 us | Lag p99 us | Gateway p99 us | Complete/s |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| mixed_4 | 5/5 | 5/5 | 100001 | 90.292–93.543 | 22.292–25.000 | 27.390–30.423 | 0.208–0.209 | 10000.0 |
| cancel_heavy_4 | 5/5 | 5/5 | 100001 | 81.250–120.668 | 22.542–27.375 | 26.995–41.045 | 0.209–0.250 | 10000.0 |
| sweep_4 | 5/5 | 5/5 | 100001 | 203.917–223.959 | 26.334–36.625 | 27.488–63.614 | 0.208–0.417 | 10000.0 |
| burst_4 | 5/5 | 5/5 | 100000 | 4104.753–5100.250 | 177.875–475.625 | 5055.123–9515.913 | 18.375–28.125 | 2003.5–2003.6 |
| mixed_1 | 5/5 | 5/5 | 100001 | 80.875–93.291 | 21.958–23.209 | 27.095–30.366 | 0.208–0.250 | 10000.0 |
| mixed_4_near | 5/5 | 5/5 | 450001 | 136.124–207.916 | 20.458–24.166 | 34.609–40.454 | 3.709–4.000 | 44999.7–44999.9 |
| mixed_4_overload | 0/5 | 4/5 | 1281–400599 | 111.999–4890.449 | 16.917–33.292 | 31.086–211.837 | 3.792–4.708 | 128.1–40059.7 |

The next table separates resource ranges and actual admissions per round from
loss totals across all five rounds. Resource counters include setup.

| Row | User CPU s | System CPU s | RSS MiB | Measured admissions/round | Slow closes/round | Not started total | Failed total | Unfinished total |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| mixed_4 | 0.749–0.912 | 3.101–3.443 | 36.613–37.465 | 100001 | 0 | 0 | 0 | 0 |
| cancel_heavy_4 | 0.385–0.901 | 2.345–2.932 | 37.465–37.488 | 100001 | 0 | 0 | 0 | 0 |
| sweep_4 | 0.364–0.810 | 2.713–3.197 | 38.219–39.004 | 100001 | 0 | 0 | 0 | 0 |
| burst_4 | 0.895–1.118 | 2.795–3.232 | 39.129 | 100000 | 0 | 0 | 0 | 0 |
| mixed_1 | 0.700–0.962 | 2.383–2.647 | 39.129 | 100001 | 0 | 0 | 0 | 0 |
| mixed_4_near | 2.048–2.552 | 8.284–8.887 | 106.863–107.039 | 450001 | 0 | 0 | 0 | 0 |
| mixed_4_overload | 0.007–1.517 | 0.037–5.605 | 176.109–176.160 | 1694–400805 | 2–4 | 2993691 | 1550 | 0 |

All rates below use the same client measurement window. Actual admissions count
the measured requests observed by the server in that experiment; they are not a
separately selected steady-state server window.

| Row | Target/s | Attempts/s | Full writes/s | Admissions/s | Client Complete/s | Window s |
| --- | --- | --- | --- | --- | --- | --- |
| mixed_4 | 10000 | 10000.0 | 10000.0 | 10000.0 | 10000.0 | 10.000073–10.000087 |
| cancel_heavy_4 | 10000 | 10000.0 | 10000.0 | 10000.0 | 10000.0 | 10.000070–10.000124 |
| sweep_4 | 10000 | 10000.0 | 10000.0 | 10000.0 | 10000.0 | 10.000076–10.000082 |
| burst_4 | 2000 | 2003.5–2003.6 | 2003.5–2003.6 | 2003.5–2003.6 | 2003.5–2003.6 | 49.910141–49.911826 |
| mixed_1 | 10000 | 10000.0 | 10000.0 | 10000.0 | 10000.0 | 10.000072–10.000078 |
| mixed_4_near | 45000 | 44999.7–44999.9 | 44999.7–44999.9 | 44999.7–44999.9 | 44999.7–44999.9 | 10.000048–10.000090 |
| mixed_4_overload | 80000 | 169.7–40080.3 | 169.6–40080.3 | 169.4–40080.3 | 128.1–40059.7 | 10.000001–10.000090 |

Across the 35 measured loadgen processes, minimum positive clock intervals were 41 ns. Each 10000-sample one-read-plus-timestamp-store probe averaged 13.93–15.44 ns per iteration. These are observed probe costs, not corrections subtracted from request samples.
<!-- TABLES:END -->

The 25 ordinary rounds completed all 2,500,020 requests. Near at 45,000/s also
completed all 2,250,005 requests across five ten-second rounds. That is a finite
observation for this workload and shared VM, not a measurement of a universal
maximum sustainable rate. Burst's 4.105–5.100 ms RTT p99 and 5.055–9.516 ms
send-lag p99 show why the planned schedule and actual attempts must be reported
separately. Its roughly 2,003.5–2,003.6 completions/s exceeds the 2,000/s target
slightly because the observation ends after the final burst near 49.91 seconds,
without adding the unused remainder of a nominal 50-second schedule period.

All five 80,000/s overload rounds failed to deliver the full plan, despite four
having enough completed samples for the threshold. They completed 1,281–400,599
of 800,001 planned requests per round, with **2–4 slow-client closures** each.
Round 2 lost all four connections and is below the sample threshold; rounds 1,
3 and 5 retained one connection, and round 4 retained two. The saved final CSV
rows show a surviving client still receiving Completes for requests scheduled
near ten seconds in those four rounds. Remaining healthy connections therefore
continued to make progress, while the overall experiments still failed.

The observed overload bound was the per-connection outbound backlog: wire-byte
high-water marks were 65,464–65,516 against the 65,536-byte limit. Command/event
high-water marks were only 6–50 / 28–134 out of 1,024, and all five reported zero
Matching output waits. This does not identify an isolated matching-core capacity
limit. After peers close, the surviving workload has a lower aggregate arrival
rate, so a small completed-only RTT p99 cannot be advertised as successful
80,000/s latency. All five loss totals and every round remain in the tables.

RSS is the reported `getrusage` process high-water mark, not an isolated book,
queue or measured-phase allocation. For example, overload round 2 still reports
about 176 MiB despite only 1,694 measured admissions. These records do not
attribute that peak to particular containers or prove all reserved record pages
were resident. Use the capacity formulas and raw resource observations separately.

The [complete round tables](benchmarks/m2_service_rounds.md) and
[machine-readable record](benchmarks/m2_service_rounds.json) retain every round,
including unsuccessful and sample-insufficient results. Minimum–maximum ranges
across five rounds are observations, not confidence intervals. Reaching 100,000
completed samples and ten seconds is a sample threshold, not proof of p99
stability. Smaller command-kind/outcome groups retain their own sample counts in
the JSON. No p99.9 result is claimed.

## Correctness and delivery boundaries

<!-- CORRECTNESS:BEGIN -->
All 42 declared attempts are present: 30/35 measured and
7/7 warmup client runs succeeded.
42/42 servers drained; 42/42 full
Reference replays passed. Across measured runs, the server actually admitted
5,756,332 requests excluding setup. Across all 42 runs including their
setup, it admitted 5,784,332 commands. The saved Reference results bind
continuous command sequences, full per-command event counts/digests and final books.

Measured client accounting is:
`8750030 = 2993691 + 5756339` and
`5756339 = 5754789 + 1550 + 0`.
Business outcomes among client completions were 5,742,594 Accepted
and 12,195 Rejected. Request loss is kept separate from these
business rejections. The appendix lists every server's internal drain, missing or
discarded business recipients, output high-water marks and client failure reasons.
<!-- CORRECTNESS:END -->

The independent checker binds planned input bytes and timestamps, logical-to-real
client IDs, actual admitted commands, continuous command sequences, complete
per-command event/Trade counts, wire-field digests and canonical final snapshots.
ReferenceEngine replays the entire admitted sequence of a successfully drained
server. It does not promise that a disconnected requester received those results.
FNV digests are not collision-free proof; the small full-event, routing, framing,
BBO and lifecycle tests remain separate mandatory evidence. Failed server drains
retain their completed prefix and current admission/phase and cannot acquire a
successful full-replay final-state or service-latency conclusion.

## Retained first matrix and correction

The first matrix at `f58ff79d49fd08c2bcb399ad989eb47ed0830a40` is retained in
full: seven warmups and 35 measured attempts. Its evidence was internally
consistent, but loadgen filled every absolute scheduled timestamp after reading
the measurement clock anchor. This plan-sized loop delayed the first request by
13.997–14.366 ms for the 450,001-request near row and 24.409–25.188 ms for the
800,001-request overload row. The open-loop catch-up consequently introduced an
unintended initial burst; these outcomes cannot locate sustained service capacity.

The old 25 ordinary measured attempts completed all 2,500,020 requests. All ten
near/overload attempts lost requests: near completed only 44 of 2,250,005 planned
requests across five rounds, and overload completed 88 of 4,000,005. Each closed
all four peers for bounded outbound backlog, while the server still drained and
passed Reference. Across all 35 old measured attempts, 6,244,674 requests never
started and 5,204 started requests failed; none remained unfinished at termination.
Their original timestamps, low completed-only percentiles and successful internal
drains are preserved, not presented as good overload performance.

Revision `eb0a109` removes that timed initialization without changing frozen
rates, limits, input schedules or service binaries. The complete matrix is repeated,
not just its failed rows. The earlier batch remains a disclosed harness-defect
attempt in the raw archive and is excluded from the corrected result ranges.
Short calibration also used the old harness; its labels remain hypotheses, not a
capacity estimate retroactively validated by the new run.

<!-- STARTUP:BEGIN -->
| Row | Old request 0 send lag, us | Corrected request 0 send lag, us |
| --- | --- | --- |
| mixed_4_near | 13996.852–14365.955 | 0.750–1.250 |
| mixed_4_overload | 24408.643–25188.433 | 0.708–1.250 |

These ranges read only the first planned request (CSV idx 0) from each of the
five old and five corrected rounds. They show startup send lag after the
correction; they do not isolate every source of later latency or establish that
all differences between the two VM runs have a single cause.
<!-- STARTUP:END -->

## Separate core and profiling evidence

The [Linux synchronous core measurements](m2_core_measurements.md) cover four
workloads and 40 timing rounds at source `f58ff79`, using unchanged core binaries.
The observed 42 ns p50 is close to the clock's 41 ns minimum positive step;
back-to-back reads had p50 0 ns and p99 42 ns. It is not precise instruction-cost
evidence, and no constant clock cost was subtracted. These results do not support
a cross-platform speedup claim against M1 or a substitution for service latency.

The [independent profiling run](m2_profiling.md) used source `85de7f3` and the same
server binary. It supplies 683 user-mode CPU samples, software counters and
Reference-verified service work; hardware counters were unavailable. Both
profiling attempts are retained. The usable data followed a requested perf SIGINT
with raw record exit `-2`; its original wrapper exit `1` is explicitly assessed,
not rewritten as zero. Profiling attached over a different window and adds
overhead. It also used the old loadgen harness, so its latency/throughput outputs
are excluded from formal timing. Only the documented coarse sampled paths are
used, with no precise kernel/blocked-time or optimization attribution.

## Reproduction and retained evidence

On the recorded permitted Linux environment, with a fresh output directory:

```sh
git checkout --detach eb0a109b026c8ac9cf48d987163fad8751980047
cmake --preset release
cmake --build --preset release --parallel 2
python3 scripts/run_service_bench.py \
  --server build/release/matching_server --loadgen build/release/loadgen \
  --verifier build/release/verify_service \
  --manifest data/workloads/service-formal.json \
  --host-environment build/m2-measurement/host-environment.json \
  --output-dir build/m2-measurement/m2-formal-new
python3 scripts/summarize_service_bench.py build/m2-measurement/m2-formal-new
```

The host-environment file must describe the actual execution host; do not copy a
different machine's metadata as a measurement claim. A failed-request experiment
may return nonzero while retaining a valid evidence report. Preserve the raw
outcome and use another directory for any repeat.

The corrected local root is `build/m2-measurement/m2-formal-eb0a109/`; the first
matrix is `build/m2-measurement/m2-formal-f58ff79/`. Each contains the original and
effective manifests, generated inputs, every raw client/service sample, server
admission trace, final book, verifier result, logs and environment/binary bindings.
Original guest reports remain beside independent host revalidation. The
[evidence index](m2_evidence_index.md) maps these roots into permanent archives;
the release acceptance record separately identifies final PR and main validation.
Measurement completion does not itself establish release or CI acceptance.
