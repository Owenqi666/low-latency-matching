# Gateway optimization report

Status: investigation in progress. Production remains **batch1**. G00–G04 have
verified evidence. G05 run-01's original stop is retained; after a disclosed
post-observation classification correction, run-02 completed A-only calibration
with a rate proposal. G05 is now complete: ordinary 10,000/s, near 22,781/s,
burst 2,000/s and overload 75,938/s were formally frozen at 16:19:55.525998Z.
**G06 is running**, launched at 16:21:25.121295Z; no formal conclusion is available.
The formal adoption matrix, final ADR and G09 delivery verification are not yet complete.
This report must not be read as a release or adoption receipt.

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
The external report's 10k/s delivery failure was not reproduced here.

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

## Diagnostic interpretation and next decision

The [diagnostic report](gateway_diagnostics.md) separates observations, supported
explanations and remaining alternatives. In the observed windows, named sendmsg
rates fell about 28.8% for mixed_4 and 50.0% for mixed_1. Gateway thread CPU fell
while Matching thread CPU changed little. Retained stacks support both network
delivery and synchronization costs; they do not establish matching-core
saturation. Diagnostic tail co-occurrence does not prove causation.

G04 supports entering the bounded A-only calibration: CPU/completion improved in
all five pairs of both rows, application writes and observed syscalls decreased,
and neither clean row had a persistent median latency regression. This is not an
adoption decision. G05 must validate offered-load stability and freeze all seven
formal rows before G06 can apply the predeclared benefit, latency, delivery,
resource and isolation gates. No evidence currently triggers a G07 policy change.

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
There is no G06 result or batch16 adoption yet. The subsequent formal freeze and
active-run recovery entry are recorded below; completed calibration is not restarted.

## G06 freeze and active run

`formal/freeze-01/freeze.json` was recorded at 2026-10-18T16:19:55.525998Z with
SHA-256 `37646da98a7f6eda9fd287e22937c31869b5fe841d96bc931cd93bf82897f332`.
The guarded run launched at 2026-10-18T16:21:25.121295Z using the frozen manifest
and identities. The current driver log
shows mixed_4 in progress; it does not establish a completed comparison.

Recovery starts with the [execution plan's current checkpoint](gateway_optimization_plan.md#current-recovery-checkpoint).
Check Linux guard PID 10805 against its command/start identity and
`/home/m2/gateway-formal-01-launch.json`; output is
`/home/m2/gateway-formal-01/pairs` and the parent holds `guard-report.json`.
The host driver log is `formal/run-01-driver.log`; launch-time local SSH PID
46491 and root exec session 49493 locate the existing driver and require a live
check. Monitor the existing run, without restart, directory clearing, duplicate
launches, builds, tests or large evidence revalidation during measurement.
Terminal results and all retained outcomes must be examined before any decision.

## Acceptance and remaining work

The [execution plan](gateway_optimization_plan.md) contains the task-by-task
status and recovery point; the [evidence index](gateway_evidence_index.md) locates
raw commands, source/binary identities and validation logs. G01 includes bounded
whole-process ITCH verification; G02 includes full per-command deep-book coverage;
G03 includes optional bounded diagnostics and lifecycle/accounting checks.

Still required: finish and independently evaluate the running G06 matrix, then
decide production configuration; record G07 as triggered or not triggered; finalize this report
and a new ADR; finish the clean
Linux build/smoke/demo/short A/B and archive-copy recomputation required by G09.
The current passing sanitizer results do not by themselves complete G09.

Historical [M3 rejection](m3_report.md) and [M4 rejection](m4_report.md) are
unchanged. No personal-contribution or CV claim follows from this investigation.
