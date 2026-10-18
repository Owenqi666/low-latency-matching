# Gateway optimization report

Decision: **reject batch16 under the frozen rules; retain A, batch1**. The complete
G06 comparison is valid and independently recomputed. Near-load CPU/completion
improves by 6.403%, below the required 10%; near-load RTT p99 and scheduled-to-complete
p99 regress by 13.717% and 10.095%, respectively, exceeding their 10% limits.
B fully delivers all 35 measurements, including every overload run. A loses
delivery in two ordinary scenarios and all five overload runs. These are A's
failures, not failures caused by B; B's benefits do not waive the frozen gates.

G00–G06 have completed evidence. G07 is **not triggered** because the observations
do not isolate a mechanism for an additional policy change. The
[decision ADR](adr/008-retain-single-frame-gateway.md) and
[all 35 pairs](benchmarks/gateway_service_pairs.md) preserve the result.
**G09 final delivery verification remains pending**; this is a measured production
decision, not a release or final-verification receipt.

## Scope and source identity

The first comparison changes only `batch_max_frames` from 1 to 16. Both variants
retain 16 descriptors, a 4,096-byte batch limit, 65,536-byte per-connection send
allowance including in-flight data, and 1,024-slot command/event queues. There is
no wait-to-fill timer, new admission policy or changed matching semantics.

| Role | Source |
|---|---|
| Original baseline | `4abdccc57037c69ded2247ac9a88894a03a1543b` |
| Common implementation / experiment A | `7d9d7dc0a6ab386d2d381f401ce644e621e33d33` |
| Experiment B, frame constant only | `56d5c71e7daec7631272dbc7b10a0f430f3381e0` |
| Frozen G04 measurement tools | `6f3ef0878668e428fb5fa69277226d0b19dcd6de` |
| Frozen G06 measurement and evaluation tools | `f6765b5c0e096428115980c047f56e2a9190146f` |

A/B binaries were rebuilt from clean Linux checkouts and their build inputs
were compared. Both use the same A-built loadgen and independent verifier.
Later analysis-tool changes are identified separately and do not alter the
frozen measurement tools or raw data.

## Environment and measurement boundary

Measurements ran on Ubuntu 24.04 aarch64, kernel 6.8.0-147-generic, in the existing
QEMU/HVF VM with four vCPUs and 4 GiB RAM. Server and loadgen share the VM and use
TCP loopback. The host is an Apple M5 Pro, 18 CPU cores and 48 GiB RAM, running
macOS 26.6.2 on AC power. Cores are not exclusive and frequency is not controlled.
Hardware-cycle/instruction perf events were unavailable; diagnostic software
sampling and the named syscall tracepoints were available.

Clean A/B runs were serial, unsanitized Release, with detailed Gateway diagnostics
off and no competing project builds, tests or profiler runs. Profiling is a
separate dataset. Results characterize this layout and workload only.

## G04 fixed reproduction

Each of mixed_4 and mixed_1 used a total offered rate of 10,000/s, five alternating
AB/BA pairs and separate A/B warmups. All seven manifest rows and their original
indices were retained; selection used the runner's row arguments. Every measured
input contained 100,001 commands with a ten-second planned interval. All 20
measurements and four warmups fully delivered, drained and passed Reference.
The external report's 10k/s delivery failure was not reproduced in these G04
runs. The later formal A mixed_1 failure below prevents extending that statement
to every local 10k/s run; it does not establish the external failure's mechanism.

| Row | CPU/completion reduction, paired median [min, max] | RTT p99 change, paired median [min, max] | Scheduled-to-completion p99 change, paired median [min, max] |
|---|---|---|---|
| mixed_4 | 8.615% [7.566%, 11.935%] | -4.996% [-14.369%, 39.378%] | 0.054% [-6.824%, 35.435%] |
| mixed_1 | 8.132% [5.250%, 9.645%] | 0.638% [-13.916%, 2.947%] | -1.846% [-4.736%, 5.032%] |

Positive CPU reduction means lower B cost; positive latency change means B is
slower. CPU is server lifetime user+system CPU divided by measured client
completions, including setup/lifetime overhead in the numerator. Quantiles are
computed separately in each run before pairing; scheduled-to-completion is
computed per sample as `complete_ns - scheduled_ns`, not a sum of p99s.

The fifth mixed_4 pair regressed in RTT p99 from 84.544 to 117.836 microseconds
(+39.378%). It is retained and unexplained. Profiling a different run cannot
retrospectively establish its cause. The complete per-pair values and raw data
remain in `build/gateway-optimization/repro/pairs-01/`; independent recomputation
is in `repro/evaluation-02/` under that evidence root, including raw per-request
scheduled-to-completion quantiles and before/after input-tree hashes.

## Diagnostic interpretation and continuation decision

The [diagnostic report](gateway_diagnostics.md) separates observations, supported
explanations and remaining alternatives. In the observed windows, named sendmsg
rates fell about 28.8% for mixed_4 and 50.0% for mixed_1. Gateway thread CPU fell
while Matching thread CPU changed little. Retained stacks support both network
delivery and synchronization costs; they do not establish matching-core
saturation. Diagnostic tail co-occurrence does not prove causation.

G04 supported entering the bounded A-only calibration: CPU/completion improved in
all five pairs of both rows, application writes and observed syscalls decreased,
and neither clean row had a persistent median latency regression. This is not an
adoption decision. G05 subsequently checked offered-load stability and froze all
seven rows; G06 applied the predeclared gates below. The profiling evidence is not
transferred to the unprofiled formal failures as an explanation of their cause.

## G05 first probes and retained stop

The first A-only sequence used clean tools revision
`98377de69681644d824ffd751cae2589e6ee568e` and the unchanged A server/source.
Its calibration plan was recorded before probing at 2026-10-18T16:00:14.325060Z;
that plan is not a G06 formal freeze. The driver ran from 16:00:50.719385Z to
16:01:51.234337Z and returned exit 2. Each mixed_4 point used two measurements
and one independent 1,000-command warmup. All six warmups passed.

| Offered rate /s | Planned commands per measurement | Completed commands, rounds 1 / 2 | Original point outcome |
|---|---:|---:|---|
| 10,000 | 20,001 | 20,001 / 20,001 | pass |
| 15,000 | 30,001 | 30,001 / 30,001 | pass |
| 22,500 | 45,001 | 45,001 / 45,001 | pass |
| 33,750 | 67,501 | 67,501 / 67,501 | pass |
| 50,625 | 101,251 | 101,251 / 101,251 | pass |
| 75,938 | 151,877 | 38,951 / 1,244 | measurement_insufficient |

At the first five points, both measurements fully delivered, drained and passed
the fixed lag checks. At 75,938/s, both measurements lost client delivery through
disconnects; the server drained its admitted prefix and Reference passed. The
server recorded three and four slow-client closures respectively. Round 1 had
growing pending requests; round 2 had started samples only in its first planned
bin. Thus the original classifier stopped on missing lag coverage. The immutable
result and terminal journal retain `measurement_insufficient`, not a successful
point. These short probes do not establish sustained service capacity or identify
whether server, client or scheduling pressure caused the delivery loss.

After seeing these A results, classification priority was corrected so that an
independently validated delivery failure is retained as `valid_load_failure`
even when early disconnects leave later lag bins empty. This is explicitly a
post-observation correction. The four-bin definition, one-started-sample minimum,
1 ms p50-growth limit, 5 ms p99-growth limit, pending-growth bound and send-span
bound are unchanged. Missing bins remain insufficient for lag interpretation;
a fully delivered run with missing bins still stops, and invalid evidence or
correctness faults still stop for correction. No original result is rewritten,
and no failed measurement is promoted to a pass.

`build/gateway-optimization/calibration/run-01/` and its collection verification
retain all 462 hash-checked files and the original stop. The separate continuation
below does not rewrite that history or restart its budgets.

## G05 continuation and proposed rates

`calibration/continuation-01/` records preparation of clean tools revision
`f6765b5c0e096428115980c047f56e2a9190146f` and the continuation driver. Run-02's
`carry-forward-audit.json` binds the original six attempts, their unchanged raw
and lag data, and the unchanged original evidence-tree SHA. It derives a
`valid_load_failure` for 75,938/s under the corrected precedence while preserving
the original `measurement_insufficient` result. The driver ran from
16:11:59.727231Z to 16:15:15.434562Z and exited 0.

| Confirmation | Planned commands per measurement | Completed commands by round | Result |
|---|---:|---|---|
| Ordinary 10,000/s | 100,001 | Existing five A rounds each for mixed_4 and mixed_1 | G04 `reused`; all ten lag assessments stable; no new ordinary measurement |
| Near 45,562/s | 455,621 | 455,621 / 178,708 / 455,621 | `valid_load_failure`; round 2 disconnected |
| Near 22,781/s, retry 1 | 227,811 | 227,811 / 227,811 / 227,811 | All three passed delivery, drain, Reference and lag gates |
| Burst 2,000/s mean | 20,001 | 20,001 | Passed delivery, drain, Reference and lag gates |

At 45,562/s round 2, 179,257 requests started: 178,708 completed and 549 failed.
Another 276,364 never started. Its four lag-bin sample counts were
113,906 / 65,351 / 0 / 0.
Lag coverage therefore remains `measurement_insufficient`; the validated delivery
loss determines the negative confirmation outcome. The server drained its
admitted prefix and Reference passed. Rounds 1 and 3 fully delivered with stable
lag, but do not erase round 2. The allowed halving rule then selected 22,781/s.

At 22,781/s, all three rounds populated every bin. The largest p50 growth was
358.5 ns, largest p99 growth 14,761.5 ns, and pending growth was zero in every
round (limit 23); actual send spans were about 10.00001 seconds and passed the
unchanged span bound. Burst used the existing 100 ms period / 10 ms window. Its
lag p99s were about 9.42–9.74 ms, while p99 growth was -12,255 ns and p50 growth
187,748.5 ns; pending growth was -2 and its 10.010063-second send span passed.
This is a pass of the fixed growth checks, not a claim that burst lag is small.
All three new 1,000-command warmups passed.

Cumulative use is six probe points / 12 probe measurements / six warmups, plus
six near-confirmation measurements / two warmups and one burst measurement /
one warmup: 19 calibration measurements and nine warmups across both runs.
The ordinary G04 reuse adds zero new runs. Measured budgets used are 12/20 probe,
6/18 ordinary/near and 1/2 burst; the new directory and tools did not reset them.

The verified local collection is `calibration/run-02/`: its collection receipt
reports all 705 file hashes matching, totaling 746,338,997 bytes. Terminal
`journal/00009.json` records `status=proposed`, decision `complete`, no pending
attempt, `formal_run=false` and `adoption_evaluated=false`. The proposed rates
are ordinary 10,000/s, near 22,781/s, burst 2,000/s and overload 75,938/s; the
highest successful short probe remains 50,625/s. The proposal's formal-mode and
locked-rate fields do not substitute for the separate source/host/rules freeze.
At that proposal checkpoint there was no G06 result. The subsequent freeze and
complete comparison are recorded below; completed calibration was not restarted.

## G06 freeze, complete execution and independent validation

`formal/freeze-01/freeze.json` was recorded at 2026-10-18T16:19:55.525998Z with
SHA-256 `37646da98a7f6eda9fd287e22937c31869b5fe841d96bc931cd93bf82897f332`.
The guarded run launched at 2026-10-18T16:21:25.121295Z and reached its terminal
receipt at 16:47:47 UTC. Every row used AB/BA/AB/BA/AB plus independent A/B warmups:
35 pairs, 70 measurements and 14 warmups. All 84 attempts are retained. The guard
checked each completed attempt without stopping; the independent summarizer
exited 0. The runner exited 1 because valid delivery failures remain in the
matrix, not because the evidence is invalid. All 14 warmups fully delivered;
all 70 measurements drained admitted work and passed Reference. A delivered
28/35 measurements and B 35/35.

Frozen total offered rates are ordinary 10,000/s, near 22,781/s, burst 2,000/s
mean and overload 75,938/s. Ordinary inputs have 100,001 planned commands,
near 227,811 and overload 759,381, each with about ten planned seconds. Burst
has 100,000 commands and a 50-second planned interval, with the existing
100 ms period / 10 ms window; its instantaneous pressure is different from
constant-rate 2,000/s. Each attempt starts a new server with the same input and
initial state for its pair. Detailed diagnostics and profiling remain off.

The independent evaluator exited 0 with `evidence_valid=true`, `decision=reject`,
`selected_variant=A`, all source-bound correctness categories passed and no
correctness-receipt error. It recomputed from a temporary evidence copy and
verified that the original source tree was unchanged, digest
`818b47ebb46c8524b1c7c04f740cc64aa5abb126604b14bc35aa96010ba63905`.
The local collection `build/gateway-optimization/formal/run-01/` contains
1,632 hash-verified files totaling 3,736,738,350 bytes. The decision JSON is
`independent-evaluation/gateway-evaluation.json`; the independently validated
full run summaries are in `independent-evaluation/validation/pair-report.json`.
The [evidence index](gateway_evidence_index.md) binds the collection and later
delivery artifacts separately.

## Formal results and frozen gates

Percentages below are per-pair changes summarized by median [minimum, maximum].
CPU reduction is positive when B costs less; latency change is positive when B
is slower. Only fully delivered same-input pairs enter these performance
comparisons. Burst and mixed_1 have four such pairs, so their descriptive medians
cannot satisfy a five-pair acceptance condition. Failed pairs remain in the
[complete tables](benchmarks/gateway_service_pairs.md), with both absolute
outcomes and no paired performance delta. No samples are pooled across runs.

| Row | Full pairs | CPU/completion reduction % | RTT p99 change % | Scheduled-to-complete p99 change % |
|---|---:|---:|---:|---:|
| mixed_4 | 5/5 | 8.638 [5.509, 10.849] | -5.926 [-30.747, 2.513] | -2.688 [-24.262, 7.683] |
| cancel_heavy_4 | 5/5 | 3.029 [2.125, 6.882] | -1.354 [-8.242, 13.548] | 1.103 [-9.437, 7.803] |
| sweep_4 | 5/5 | 7.461 [5.898, 8.380] | -58.185 [-60.065, -56.556] | -50.229 [-51.995, -49.202] |
| burst_4 | 4/5 | 23.601 [21.371, 43.778] | -81.174 [-85.745, -79.247] | -15.868 [-18.725, -7.598] |
| mixed_1 | 4/5 | 8.419 [7.174, 10.859] | -6.678 [-17.390, -2.344] | -6.811 [-19.525, -3.122] |
| mixed_4_near | 5/5 | 6.403 [5.738, 6.490] | 13.717 [-54.916, 39.139] | 10.095 [-48.166, 50.910] |
| mixed_4_overload | 0/5 | N/A | N/A | N/A |

| Frozen condition | Observed result | Decision |
|---|---|---|
| Source-bound correctness, bounded resources and healthy-client isolation | All five prerequisite categories passed; formal admission/drain/Reference checks passed; no guard correctness stop | Passed within the recorded test/platform scope |
| Both variants deliver every first-six-row measurement | A burst round 2 and A mixed_1 round 4 fail delivery; B delivers every run | Not met; these are control failures, not candidate-caused regressions |
| At least 100,000 completed samples in each first-six-row run | Those two A runs complete 1,553 and 91,325 requests | Not met |
| Near CPU/completion median reduction ≥10%, at least 4/5 improving pairs | All five pairs improve, median 6.402527% | Magnitude not met |
| Every first-six-row RTT p99 paired median regression ≤10% | Near median +13.717391%; burst/mixed_1 additionally lack five fully delivered pairs | Not met; near is a measured breach, incomplete rows are not proof of a latency regression |
| Every first-six-row scheduled-to-complete p99 paired median regression ≤10% | Near median +10.094805%; burst/mixed_1 additionally lack five fully delivered pairs | Not met; near is a measured breach |
| Reject if overload B completed/planned is worse in ≥4/5 pairs and its median difference is negative | B is better in all five pairs; median difference +74.866766 percentage points | Overload non-regression condition passed |

This is a valid negative decision under the frozen contract, not `inconclusive`.
The near CPU and both near latency constraints independently prevent adoption,
even apart from A's ordinary delivery failures. No worst pair is removed, no
extra rounds are added, and the small scheduled-to-complete breach is not rounded
down to a pass. Retaining A is the specified outcome of a failed adoption
comparison; it does not certify that A is more reliable than B or that the
selected offered rates are universally sustainable.

## Retained failures, overload and healthy-client evidence

Every failure below is a client-delivery failure with admitted-prefix drain and
Reference agreement. No failure is reclassified as environment noise. Started
requests satisfy `started = completed + failed + unfinished`; all these runs
have zero unfinished requests. Planned requests additionally include not-started
rows. Failure-reason totals can include not-started rows and therefore are not
interchangeable with the started-request `failed` column.

| A run | Planned | Started | Completed | Failed | Not started | SlowClient closes | Send high-water bytes |
|---|---:|---:|---:|---:|---:|---:|---:|
| burst_4 round 2 | 100,000 | 2,000 | 1,553 | 447 | 98,000 | 4 | 65,536 |
| mixed_1 round 4 | 100,001 | 91,497 | 91,325 | 172 | 8,504 | 1 | 65,470 |
| mixed_4_overload round 1 | 759,381 | 191,315 | 191,006 | 309 | 568,066 | 3 | 65,486 |
| mixed_4_overload round 2 | 759,381 | 191,165 | 190,857 | 308 | 568,216 | 3 | 65,486 |
| mixed_4_overload round 3 | 759,381 | 191,345 | 191,032 | 313 | 568,036 | 3 | 65,530 |
| mixed_4_overload round 4 | 759,381 | 1,565 | 1,145 | 420 | 757,816 | 4 | 65,522 |
| mixed_4_overload round 5 | 759,381 | 1,765 | 1,353 | 412 | 757,616 | 4 | 65,486 |

A burst round 2 reaches the 1,024-event queue limit and records one output wait;
its command high-water is 462. A mixed_1 round 4 has command/event high-water
138/480 and no output wait. These counters locate bounded output pressure but do
not identify why it developed. Neither a non-reading peer nor a specific
Gateway starvation mechanism is established by a SlowClient reason alone.

B completes all 759,381 requests in every overload measurement, versus A's
1,145–191,032. B−A completed/planned improves by a median 74.866766 percentage
points, range 74.843721–99.849219. In A rounds 1–3, logical client 4 completes its
full 189,845-request share while the other clients lose delivery; rounds 4–5
have partial completion on every client. B completes every client's share in
all five rounds. The [per-client table](benchmarks/gateway_service_pairs.md#overload-each-logical-clients-outcome)
retains planned/started/completed/failed/unfinished/not-started totals. Totals
show each client's completed work, not uninterrupted temporal progress; the
source-bound non-reading-client tests provide separate isolation evidence.
No paired overload CPU or latency speedup is claimed because A never fully
delivers that row.

## Metric and resource scope

Successful ordinary constant-rate runs complete about 10,000 requests/s and
near runs 22,780.879–22,780.984/s over their measured client windows. Successful
burst runs complete 2,003.449–2,003.604/s over about 49.91 seconds, reflecting
the schedule's first/last burst positions rather than a different frozen mean.
B overload completes 75,937.452–75,937.630/s. These finite run observations do
not establish long-term capacity; losses and actual spans remain beside rates
in the full tables.

Server CPU uses user+system process lifetime divided by measured client
completions, including setup and lifetime overhead. It is a benefit comparison
only for fully delivered pairs. Server/loadgen user and system CPU, RSS,
server span and client measurement duration are retained separately for every
run. Server RSS spans 37.012–167.750 MiB and loadgen RSS 53.258–381.137 MiB
across the matrix; both include evidence/input storage, and loadgen includes
input preparation. These are whole-process peaks, not queue-memory measurements.
Near server RSS is 63.715 MiB for both variants. Detailed diagnostics are off;
the optional approximately 2.44 MB collector is not part of formal timing.

At near load, median lifetime application writes/admitted fall from 6.992 to
4.892 and written frames/operation rise from 1.000 to 1.429. Welcome/BBO/setup
remain in the write numerator, and setup is in admitted. These are composed
application operations, not syscall counts or client acknowledgements. The
formal base counters retain callbacks, bytes, frame/byte batch distributions,
unconfirmed writes, close reasons, discarded business frames and missing
recipients; the separate diagnostic profiles supply observed syscall evidence.
Queue capacities remain 1,024/1,024 and send allowance 65,536 bytes including
in-flight frames. No new admission, waiting or memory policy was introduced.

All five latency families retain per-run nearest-rank p50/p99 and sample counts
in the [detail tables](benchmarks/gateway_service_pairs.md#per-run-latency-distributions).
Client RTT, send lag and scheduled-to-complete use the client `steady_clock`;
service completion and Gateway wait use the server's own `steady_clock`.
No cross-process timestamp subtraction is used for those latencies. Client
clock probes record a 41 ns minimum positive interval; no clock cost is
subtracted. Failed completed subsets and admitted server samples have different
denominators and remain labelled. No p99.9 gate or post-hoc metric is added.

## G07 disposition and remaining explanations

G07 is **not triggered**. Fewer writes, lower Gateway CPU in separate profiling,
and improved formal overload delivery support a useful batching effect in this
environment. The formal near-tail regressions and A delivery failures remain
unexplained at mechanism level. Existing diagnostic co-occurrence does not
separate loadgen, Gateway, host scheduling and profiler interference, and cannot
explain another run retrospectively. Generic overload/SlowClient failure does
not establish that input throttling or a pump budget would solve the problem.
No additional policy is implemented to seek a passing result. A future candidate
requires a distinct hypothesis, mechanism evidence, ADR and frozen comparison.

## G09 clean delivery verification

The selected clean Linux checkout is commit
`4cb1cc5781d3d1bfa6c55128f8440ad83e282332`, batch1. Its 122 executable/fixture
files match the reviewed common code identity
`5f8791bab89885c7bfb2c676770e5aa1bca227f3ceebc6fca3e77c4d04233b47`.
All 54 C++/header inputs match the earlier A Debug, ASan/UBSan and separate TSan
matrices (130 executed passes each, two extended registrations disabled by
default). Their compiler/flags/source identities are retained in
`final/source-bridge-01/`; this reuses unchanged C++ coverage, not old results
for newly changed Python tools. The C=10,000 extended tests ran separately under
G02. The final fresh Linux suite covers the combined current tool registrations.

The fresh comparison B is `b6ee3a9980073f774de6656d65a0b13a4b42bdcd`, derived
from that same final commit with only `src/send_queue.hpp`'s frame bound changed
to 16. This is a delivery check; the formal A/B source identities above remain
unchanged. No extra formal matrix or adoption decision was substituted.

| Final check | Recorded outcome |
|---|---|
| Clean GNU 13.3.0 Linux Release A | 136 passed, zero failed/skipped; two documented default-disabled deep-book registrations |
| Clean Release B SendQueue/lifecycle/diagnostics/network subset | 15 passed, zero failed/disabled/skipped |
| Core smoke | Passed; independent copy-backed report matched |
| Seven-row network smoke | All seven measurements and seven warmups delivered, drained and passed Reference; copy-backed report matched |
| Two real CLI clients, stage Gateway G09 | Seven commands, two matching cross-client Trades, request-ID reuse and Reference verification passed |
| Short mixed_4 / burst_4 / mixed_1 replay | One invocation, six pairs: all 12 measurements and six warmups passed; independent copied report matched |

The short replay retains the seven-row manifest and seed positions, with two
alternating pairs per selected row, commands=2,000 and minimum plan=2 seconds;
actual mixed inputs contain 20,001 commands and burst inputs 4,001. Its rates
are fixed at the formal ordinary/burst values. It checks reproducibility and
delivery only, not capacity or the five-pair adoption contract. Both sources,
binaries and tools remained unchanged during these checks.

`final/linux-01/` contains the final results, exact commands, JUnit, compile
commands, dependency/binary/source identities, smoke/demo and short evidence.
All 8,302 collected files / 185,874,848 bytes match the VM hashes. This includes
6,865 retained raw test outputs; temporary fixtures deliberately deleted by
their tests have JUnit/LastTest evidence, not a claim of archived raw fixtures.

The single raw archive is `build/gateway-final-archive-01/gateway-raw.tar`,
5,675,490,816 bytes, SHA-256
`997b2edac92038b7aed1c4e2353cd67b56ad4eef1284756271313f0c88e6b2b2`.
It excludes only the preserved old VM disk backup. Creation, member listing,
extraction and **independent formal recomputation all passed**. Every evaluation
JSON value matches the first independent result except the relocated source
path: source identities, all pairs, gates and valid reject/A decision agree.
The archive SHA was rechecked unchanged. `archive.json` beside the tar records
`status=verified`; recomputed results are under `recomputed/`. This verification
receipt and the final documentation closure follow archive creation; the raw
archive is not replaced to include its own later verification record.

## Acceptance and remaining work

The [execution plan](gateway_optimization_plan.md) contains the task-by-task
status and recovery point; the [evidence index](gateway_evidence_index.md) locates
raw commands, source/binary identities and validation logs. G01 includes bounded
whole-process ITCH verification; G02 includes full per-command deep-book coverage;
G03 includes optional bounded diagnostics and lifecycle/accounting checks.

G00–G06, G08 and G09 are complete; production remains batch1 and G07 is not triggered.
This report, the complete tables and [ADR 008](adr/008-retain-single-frame-gateway.md)
record the decision. G09 has passed the source-bound matrix checks, clean Linux
build/tests/smoke/demo/short replay and archive-copy formal recomputation above.
The remaining limits are explanatory and operational: one shared local VM,
unexplained near-tail regressions and A pressure failures, and no universal
capacity or cross-environment improvement claim. They do not conceal an
unfinished required verification or an unresolved observed correctness defect.

Historical [M3 rejection](m3_report.md) and [M4 rejection](m4_report.md) are
unchanged. No personal-contribution or CV claim follows from this investigation.
