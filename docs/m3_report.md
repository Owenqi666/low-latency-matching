# M3 bounded-send experiment report

Status: the complete formal matrix is available and the frozen adoption decision
is **reject the 16-frame candidate**. Production has been restored to one frame
per composed write. Separate post-experiment profiling and clean Linux
reproduction are complete. Final PR/main CI inspection and release publication
are recorded separately in the release acceptance record; these technical
results alone do not declare M3 acceptance complete.

The candidate reduced server lifetime CPU per completed measured request at
45,000/s by a paired median **14.68%**, improving in all five pairs. It also
increased one-client mixed RTT p99 by a paired median **71.30%**, exceeding the
predeclared 10% regression limit. The target CPU benefit therefore does not meet
the complete adoption rule. No rate, batch size or decision threshold was changed
after observing these results, and no second optimization was added to rescue E1.

## Sources and experiment scope

| Role | Commit and meaning |
|---|---|
| Published M2 | `db9b74f4181a2dc4a50966c20080949c839bf73f`; preserved historical release |
| A, measured control | `7b8fcd3b074ed39ff24a3488253397e1dfb7094e`; one-frame writes, M2 plus local send-queue extraction, bounded observations and shared measurement-tool changes |
| B, measured candidate | `b1ba98c205de3bd717eb0f118fb9771d1f251a25`; only `batch_max_frames` changes from 1 to 16 relative to A |
| Final production choice | One frame, with the same observations and tests retained; the final commit and its acceptance evidence will be recorded separately |

Both measured source directories were clean, with independent Linux Release
builds. A is explicitly **not an unmodified M2 binary**. The A/B result isolates
the frame bound within the observed send-queue implementation; it does not
measure the extraction/counter overhead relative to the original M2 release.
The current restored production, build, tool and test files match A; final
report/publication changes do not alter the identity of the binaries measured here.

Both variants contain the same fixed 16-entry buffer-descriptor storage and
accounting. The candidate gathers already queued frames, bounded by 16 frames
and 4,096 bytes, with no wait-to-fill and no flush timer. The current protocol's
maximum frame is 138 bytes, so 16 frames occupy at most 2,208 bytes and the frame
bound is active. Matching, the two production threads, Boost SPSC queues,
protocol, routing, BBO frequency and all queue/send/request limits are unchanged.
There is no runtime transport strategy, waiting-strategy change or parameter
search. E2, preallocated order slots, remains unstarted because no separate
core/allocation evidence justified it; it is not a completion prerequisite.

The [frozen plan](m3_experiment_plan.md) records why E1 was selected. Two new
10,000/s baseline diagnostics observed 701,795/701,793 Gateway `sendto` calls,
equal to written frames, and Gateway task-clock 2.653/2.657 s versus Matching
0.891/0.910 s. The [four-run diagnostic record](m3_diagnostics.md) also covers
45,000/s and burst. Those instrumented timings are excluded from formal A/B.
Futex activity was visible as well; neither those samples nor the formal write
counters establish that writes are the only bottleneck.

| Measured binary | SHA-256 |
|---|---|
| A server | `dca59a4cd8027511b03e46da3b96658728ba74856531432597db9bf470a449b9` |
| B server | `56100432a2791e2fda7a21031943d00eab328aa99e9c08e49e5e3cacb256122c` |
| Shared loadgen | `9e9455a4c908c79f43fe7f7596522517999b1fb41a79eb0a322e300db0a18256` |
| Shared verifier | `239ea89ea98faea32152e72f816f30a3b1c9583e4dbfb23d296d4512d7ed29bb` |

Both formal variants use the same candidate-built loadgen and verifier. The manifests
retain actual CMake source directories, compiler/flags, source-file and binary
hashes. This is provenance evidence, not a reproducible-build attestation.

## Formal execution and evidence validity

The unchanged [formal manifest](../data/workloads/service-formal.json) produced
**70 measured attempts, 35 pairs and 14 separate warmups**. Each attempt uses a
fresh server. Within each scene, measured rounds alternate AB/BA/AB/BA/AB after
separate A-then-B warmups; A and B never run concurrently. Identical input hashes,
shared tools and actual order are checked by the independent pair summary.
Different multi-client admission orders remain possible, and each actual trace
is independently replayed by Reference.

The guest's two independent service summaries and paired checker passed.
All **84/84 attempts drained and passed Reference**, while **65/70 measured
attempts delivered the full client plan**: A succeeded in 30/35 and B in 35/35.
All 14 warmups succeeded. Every measured run meets the normal sample threshold,
including A's five failed overload attempts; sample sufficiency does not erase
losses. The paired report correctly has `evidence_valid=true` and
`all_runs_succeeded=false`. The runner's exit 1 records those delivery failures;
its independent summarizer exited successfully.

All 1,618 copied original files (4,612,638,661 bytes) passed SHA-256 verification.
The report tables derive from the preserved guest summaries at
`build/m3-measurement/host-revalidation/guest-derived/`. The host independently
recomputed all raw samples: its summarizer exited 0, and all eight derived files
are byte-identical to the preserved guest results. The check is recorded in
`build/m3-measurement/host-revalidation/verification.json`. Raw attempts,
unsuccessful outcomes and the original archive are retained under
`build/m3-measurement/`. The [evidence index](m3_evidence_index.md) tracks final
archive/publication identities.

| Property | Recorded value |
|---|---|
| Guest | Ubuntu 24.04, aarch64, kernel `6.8.0-147-generic`; 4 vCPUs, 4 GiB assigned RAM |
| Host | Apple M5 Pro, 18 physical cores, 48 GiB RAM; macOS 26.6.2 |
| Virtualization / network | QEMU 11.1.2 with HVF; server and loadgen share guest TCP loopback |
| Build | GCC 13.3.0, C++20, unsanitized Release `-O3 -DNDEBUG` |
| Threads | One Gateway thread, one Matching thread; separate loadgen process |
| Controls | No affinity pinning or exclusive physical cores; frequency/turbo uncontrolled |
| Background | Sequential A/B; no concurrent VM build, test, compression or profiler; host OS and Codex remain shared |
| Run UTC window | 2026-10-17 00:57:41 to 01:16:58; includes setup, output and verification |

The VM disk was expanded from 12 to 24 GiB before the formal run, preserving its
contents; both variants ran after that same restart. M2's historical matrix used
kernel `6.8.0-142-generic` and is not reused as the numerical A/B baseline.
These results describe this shared-host VM and finite synthetic workloads, not
bare-metal, cross-machine or production-market performance. Execution and
evidence collection were performed by Codex agents.

## Fixed workloads and timing

| Scene | Clients | Planned requests/s | Requests per measured run | Schedule |
|---|---:|---:|---:|---|
| mixed_4 | 4 | 10,000 | 100,001 | 10 s |
| cancel_heavy_4 | 4 | 10,000 | 100,001 | 10 s |
| sweep_4 | 4 | 10,000 | 100,001 | 10 s; at least 64 makers per planned sweep |
| burst_4 | 4 | 2,000 average | 100,000 | 100 ms period / 10 ms burst window; final offset 49.909950 s |
| mixed_1 | 1 | 10,000 | 100,001 | Same aggregate target as mixed_4 |
| mixed_4_near | 4 | 45,000 | 450,001 | 10 s |
| mixed_4_overload | 4 | 80,000 | 800,001 | 10 s |

Capacity remains 1,000 live orders, with 500 setup orders and working depth 64.
Command/event queues each have 1,024 effective slots, server/client send budgets
are each 65,536 wire bytes, the loadgen in-flight bound is 16,384, and drain and
shutdown deadlines are five seconds. There is one 1,000-request warmup per
variant per scene. Deliberate cancellation rejections are business outcomes,
not failed delivery. `near` and `overload` are frozen workload labels rather
than assertions about sustainable capacity.

| Metric | Boundary and population |
|---|---|
| Client RTT | First actual async-write attempt through receipt of the complete Complete frame; client-completed measured requests only |
| Service latency | Successful command-queue admission through Complete event publication; internally completed measured admissions, including any not received by the client |
| Send lag | Planned send time through first actual write attempt; started requests, including eventual failures |
| Gateway wait | Final frame byte's read callback through successful command admission |
| Server CPU/request | Server lifetime user + system CPU before evidence output, including setup, divided by client-completed measured requests |
| Loadgen CPU/RSS | Process lifetime before evidence output, including input preparation and setup |

The CPU metric is an amortized process cost, not time spent only inside an
individual request. RTT excludes planned waiting. Latency populations differ,
so subtracting service and RTT percentiles would not recover network latency.
Each interval uses one process's steady clock; clocks across processes are not
subtracted. Each measured clock probe observed a minimum positive interval of
41 ns; timestamp-recording probes ranged from 13.93 to 16.53 ns/iteration.
No clock constant is subtracted. Quantiles use nearest rank per run; no pooled
p99, average-p99-as-request-quantile or p99.9 claim is made. The reported ranges
are observed five-round ranges, not confidence intervals.

## Decision against the frozen rule

The table reports the median of five individual paired percentage changes,
`100 × (B/A − 1)`, with their observed range. It is not the percentage change
between separately computed medians. Lower is better for these two metrics.

| Scene | Fully delivered pairs | CPU/request paired change, median [min, max] | CPU improvements | RTT p99 paired change, median [min, max] |
|---|---:|---:|---:|---:|
| mixed_4 | 5/5 | -8.14% [-15.69%, -4.23%] | 5/5 | -5.09% [-45.64%, +23.21%] |
| cancel_heavy_4 | 5/5 | -3.59% [-4.73%, +2.12%] | 4/5 | -4.96% [-27.40%, +5.32%] |
| sweep_4 | 5/5 | -6.71% [-8.89%, -5.78%] | 5/5 | -54.71% [-58.42%, -22.11%] |
| burst_4 | 5/5 | -34.37% [-45.83%, -23.83%] | 5/5 | -81.92% [-85.19%, -71.97%] |
| mixed_1 | 5/5 | -5.60% [-8.09%, -4.38%] | 5/5 | +71.30% [-5.47%, +101.38%] |
| mixed_4_near | 5/5 | -14.68% [-14.83%, -14.49%] | 5/5 | -30.93% [-36.14%, -14.06%] |
| mixed_4_overload | 0/5; A 0/5, B 5/5 | — | — | — |

The primary 45,000/s criterion passes: a 14.68% median CPU/request reduction,
with all five pairs improving by 14.49–14.83%. All six required non-overload
scenes also fully deliver on both sides. However, the one-client mixed scene
fails the RTT p99 constraint: A ranges 81.293–90.377 us and B 80.711–182.004 us;
four pairs regress, with paired changes from −5.47% to +101.38% and median
+71.30%. Its paired service p99 median increases by 16.708 us, send-lag p99 by
25.590 us and Gateway p99 by 0.125 us. These simultaneous observations do not
isolate the cause of the tail regression. The separate profiling below covers
four-client 45,000/s and cannot establish the cause of this one-client regression.
The successful CPU outcome cannot override this predeclared rejection condition.

Sweep and burst show large RTT p99 reductions, but burst still has send-lag p99
of 9.498–9.990 ms for A and 9.610–9.970 ms for B. The actual attempts therefore
do not precisely track all planned burst offsets. Its whole-window completion
rate is about 2,003.4–2,003.6/s because observation ends after the last burst near
49.91 s, without the unused remainder of a 50 s period. Burst improvement does
not demonstrate removal of schedule lag. At ordinary mixed load, one paired
RTT p99 change is +23.21% although the five-pair median is −5.09%; this variation
is preserved, not replaced with a more favorable repeat.

## Delivery failures and resource observations

At the frozen 80,000/s workload, B delivers all 800,001 requests in each of five
runs, while A fails all five through slow-client closures. A's completed counts
range from 200,963 to 600,318; totals are 1,603,931 completed, 2,394,834 not started,
1,240 failed after starting and zero unfinished out of 4,000,005 planned.
There are 1–3 slow-client closures per A run, 8,496 discarded frames in total,
and eight missing business recipients. Every server still drains its admitted
work, so internal completion is not equivalent to client delivery.

This finite delivery difference is recorded, but the five incomplete A/B pairs
produce **no comparative latency, rate or CPU benefit deltas**. Their completed-only
RTT and CPU/request values remain in the absolute tables with loss counts.
Neither the candidate's five successful ten-second runs nor the control's smaller
completed subsets establish a universal sustainable rate. The overload outcome
does not reverse the independent one-client rejection.

The [35-pair tables](benchmarks/m3_service_pairs.md) retain absolute CPU/request
and RTT p99 for every pair, plus service/lag/resource ranges and every overload
loss count. The [machine-readable report](benchmarks/m3_service_pairs.json)
retains full per-run p50/p99/max, rates, client outcomes, server observations,
clock probes, hashes and paired deltas.

Both variants use identical descriptor storage and record capacities. Server
RSS ranges from 36.305 to 38.270 MiB for A's ordinary scenes and 36.348 to
38.270 MiB for B's; at 45,000/s it is 108.238–108.766 versus
108.680–108.781 MiB. Both overload variants report 177.738 MiB. These process
peaks include evidence storage and allocator behavior, not just send queues.
The data does not justify attributing tiny RSS differences to the batch or
claiming a memory reduction. Loadgen CPU and RSS are separately retained;
for 45,000/s, lifetime CPU ranges 6.828–6.913 s for A and 5.916–5.953 s for B,
with about 227.637 MiB RSS for both.

All formal attempts record zero Matching output-space waits. Ordinary and near
runs record no discarded frames, missing business recipients or slow-client
closures. Candidate overload also records none. Observed queue high-water marks
remain within the original limits; no extra queue capacity was supplied to B.

## Write observations and accounting

The observed write counts are **Asio composed asynchronous operations**, not
syscalls. A composed `async_write` may invoke several underlying sends. At
45,000/s, A starts 3,151,705–3,151,776 operations per run, B starts
1,817,437–1,844,672, while written frame totals are each about 3.152 million.
In one-client mixed, B roughly halves composed writes yet regresses RTT p99;
operation reduction alone is insufficient evidence for adoption. Cross-client
admission order can change business events/BBO broadcasts and hence frame totals;
each trace has its own independent Reference result.

The conservative M2 accounting is retained. Closing a connection discards all
unsettled queued frames once, including any active write. A later callback does
not reclassify those frames as written. Callback byte progress and the number
of complete frames in its transferred prefix are separate observations;
partial frames are never counted as complete, and none of these observations
proves peer receipt. A's overload runs contain 12 after-close/unconfirmed callbacks
and 12 complete-frame prefixes (1,336 transferred bytes), with zero write-error
callbacks. These remain part of the discarded/unconfirmed outcomes. B records
zero unconfirmed callbacks throughout the matrix.

## Separate post-experiment profiling

One independent 45,000/s four-client diagnostic and one separate 1,000-request
warmup were completed for each measured source, sequentially A then B. Each
diagnostic delivered all 450,001 measured requests, with 500 setup commands.
Both warmups and diagnostics drained and passed Reference; each saved source-side
independent service summary exited 0 with valid evidence and successful delivery.
Source directories stayed clean and source/binary identities were unchanged.
All 114 copied original files (383,944,643 bytes) passed host SHA-256 checks.
The assessment is retained at `build/m3-profiling/profile-assessment.json`, with
raw evidence under `build/m3-profiling/control-7b8fcd3/mixed_45k/` and
`build/m3-profiling/candidate-b1ba98c/mixed_45k/`. Separate host recomputation
of both diagnostics' raw client/service evidence also passed: each independent
summarizer exited 0, and both `report.json`/`report.md` pairs are byte-identical
to their source reports. The four derived-file comparisons are recorded in
`build/m3-profiling/host-revalidation/verification.json`; they are additional to
the copied-file hash check and the read-only profiling assessment.

These runs use the same server binaries as formal A/B and the same shared
candidate-built loadgen. Each diagnostic uses its own source's verifier after
execution: A verifier SHA-256
`370c725c22c3c89dd3c57554e43c430639ace5d7a1288af5c000b631f3513a8d`,
and B the verifier hash in the formal identity table. Input, setup and schedule
hashes match between A and B.

| Diagnostic observation | A: one frame | B: up to 16 frames |
|---|---:|---:|
| Gateway `sendmsg` tracepoint count | 3,151,754 | 1,784,429 |
| Composed write operations | 3,151,754 | 1,784,429 |
| Written frames | 3,151,754 | 3,151,714 |
| Submitted/transferred bytes | 290,925,548 | 290,921,948 |
| Frames per composed operation | 1.000 | 1.766 |
| Gateway perf task-clock, s | 8.46008 | 6.32783 |
| Matching perf task-clock, s | 1.88109 | 2.08723 |
| Loadgen CPU before evidence output, s | 7.040461 | 5.993798 |
| Captured `cpu-clock` samples | 7,968 | 6,445 |
| Lost samples | 0 | 0 |

Actual Gateway `sendmsg` calls decrease by 43.38% in this diagnostic pair and
happen to equal composed-write counts on each side. Both sides record zero
Gateway `sendto`, `write` and `writev` calls. This supports amortizing sends over
multiple frames at 45,000/s. Formal-round application counters remain composed
operations; the syscall equality observed here is not assumed for every other
run. Small frame/event-count differences are compatible with allowed admission
interleaving and each trace's independent Reference check.

The observed A control already uses a buffer sequence, even with one frame,
and therefore uses `sendmsg`. The earlier pure-M2 T01 diagnostic used `sendto`.
The extraction is a real implementation difference from M2, not merely a counter
addition. No percentage comparison between the historical `sendto` and current
`sendmsg` counts is used to claim an optimization or zero extraction overhead.
A/B isolates the 1-to-16 frame bound within the common extracted path.

Gateway remains the larger CPU consumer in both perf and sampled `/proc`
observations. Its perf task-clock falls by 25.20%, while Matching task-clock
increases by 10.96%; this does not show a uniform CPU benefit across threads.
Sampled self-cost symbols include wake-up and clock/syscall paths, with
`MatchingPipeline::run` visible. Symbol shares are compositional and filtered
at 0.5%; changing shares are not isolated function speedups. The diagnostic
supports the send-amortization mechanism but does not establish the cause of
`mixed_1` tail degradation, alter the formal decision or justify a second
optimization.

`perf stat` software counters and syscall tracepoints report 100% event running
time. `perf record` uses software `cpu-clock` at 499 Hz with `dwarf,8192`
call graphs. Both `perf report` and build-ID decoding exit 0; zero lost samples
supports availability of these observations, not zero profiler overhead or
complete stack coverage. All four raw profiler exits remain **−2**: the saved
lifecycle records show an explicit successful SIGINT request after loadgen exit,
followed by captured data and successful decoding. These are documented requested
shutdowns, not silently normalized profiler successes. Service, loadgen and
source-side summarizer exits are separately 0. No hardware cycles, IPC or cache
claims are supported.

Profiling windows differ: perf stat attaches after server readiness through
loadgen exit, including setup and client evidence output; perf record attaches
after loadgen spawn. Server observations include setup, loadgen's resource
snapshot stops before output, and child resource usage includes output. `/proc`
uses 100 Hz CPU ticks sampled every 50 ms, so it is not precise request-only
attribution and need not equal perf task-clock. Instrumentation, fixed A-then-B
order, one pair and the shared VM limit inference; these CPU/timing observations
never replace the unprofiled five-pair formal results.

Both diagnostics record zero slow-client closures, discarded business frames,
missing business recipients, write errors and unconfirmed callbacks. B records
three read-error closes despite complete delivery; the aggregate records do not
establish those callbacks' exact order, so no additional lifecycle cause is
inferred from them.

## Correctness and remaining acceptance

The matching and protocol contracts remain covered by existing independent
Reference, full-event/routing, tiny-queue, slow-peer, identity and shutdown tests.
New tests exercise deterministic short writes, cancellation/close lifetime,
conservative accounting and actual production multi-frame use. Pair-evidence
tests exercise corruption, retained failures and restoration. Both frozen
revisions passed 103 local Debug tests across seven required groups and 104 Linux
Release tests across eight required groups, with dynamic discovery and JUnit
validation. Release adds the benchmark group to the seven shared groups. The
Linux builds reused pinned dependency source directories, so they are not
fresh-install evidence.
Formal successful scenes also supply finite long Reference checks with at least
100,000 admitted measured commands, without rerunning an identical long test.

Candidate [CI 38988332237](https://github.com/Owenqi666/low-latency-matching/actions/runs/38988332237)
tested merge `3fec7a70c07958f1706f8eec219948740bf8fbc9`. Its downloaded
Debug/Release/ASan-UBSan/TSan artifacts passed 103/104/103/103 tests. Debug,
ASan-UBSan and TSan each passed seven required groups; Release passed eight.
The downloaded evidence also passed core smoke and 14 network-smoke attempts.
That candidate CI is development evidence; it does not substitute for the final
PR or merged-main checks.

## Clean Linux reproduction and short paired check

T07 cloned the public repository into the new `/home/m2/m3-clean-repro` directory
and detached at control `7b8fcd3b074ed39ff24a3488253397e1dfb7094e`. It used the
existing Linux system toolchain, fresh CMake dependency/build directories and
`cmake --preset release`, without `FETCHCONTENT_SOURCE_DIR` overrides. All
recorded commands exited 0 and the checkout stayed clean before and after.
The restored production/build/tool/test/workflow files match that control;
final report and publication commits will receive their own PR/main checks.

Dynamic CTest discovery and JUnit independently confirm **104/104 passed, with
no skips**, covering all eight required groups: core 59, pausable 8, protocol 12,
concurrency 9, service 13, client 1, loadgen 1 and benchmark 1. The two real CLI
processes completed seven commands using distinct ClientIds and reused RequestId
7. Host inspection of captured output checked all seven Completes, two identical
cross-client Trade records, NotOwner rejection, BBO-before-Complete ordering,
empty pending counts and Reference artifact hashes. The server drained all seven
commands. No service binary or test was rerun during host evidence inspection.

The independent core smoke validates one 1,000-command workload in both latency
and throughput modes, with Reference verification; it is not a formal tail-latency
result. The seven-row network smoke retains all 14 warmup/measured attempts,
all fully delivered and drained. Host revalidation reran the existing Python
summaries on an independent copy. Of 12 derived comparison files, 11 are
byte-identical to the source reports; core `report.json` differs only in its
explicit output-directory field after relocation from guest to host, and is
otherwise identical. All **3,269 original files (204,077,752 bytes)** passed
SHA-256 checks before and after revalidation. Original collected evidence is
unchanged; checks and derived reports are in
`build/m3-clean-repro/host-revalidation/verification.json` and its `derived/`
directory. The temporary `build/m3-clean-repro-recheck/` duplicate is excluded
from delivery archives.

The representative reproduction uses the fresh control server as A, preserved
candidate `b1ba98c` as B, and the same fresh control-built loadgen/verifier for
both. Its binary identities differ from the original formal A/shared tools and
are recorded explicitly; no bit-identical rebuild is claimed.

| Short-reproduction binary | SHA-256 |
|---|---|
| Fresh A server | `6cc9d3d2a47375983b3079fea429794b72530ef11e58d1652546b2a54b1abd8b` |
| Preserved B server | `56100432a2791e2fda7a21031943d00eab328aa99e9c08e49e5e3cacb256122c` |
| Shared fresh loadgen | `000288fcccf517066c0d6c6020384ba83582abebb0c457c75d88bcd0a776b745` |
| Shared fresh verifier | `5996eb33d8d75d04bd9a807e19cde9081fb125ace71784a0a33fdd672dc6acc8` |

Three pairs run in AB/BA/AB order after separate warmups, retaining the frozen
45,000/s target, effective seed and capacities. All six measured attempts
complete exactly **100,000 requests and RTT samples each**, with zero losses;
both 1,000-request warmups also succeed. All drains, Reference checks and host
independent paired summaries pass. Each measured plan is 2.222222223 seconds,
and observed windows are 2.222263–2.222319 seconds. The report correctly records
`mode=smoke` and `normal_sample_target_met=false` for every measured attempt:
the count threshold is met, but the formal ten-second duration is not.

| Pair | A CPU/request us | B CPU/request us | Paired CPU change | A RTT p99 us | B RTT p99 us | Paired RTT p99 change |
|---|---:|---:|---:|---:|---:|---:|
| 1 (AB) | 24.244 | 21.134 | −12.83% | 222.877 | 93.376 | −58.10% |
| 2 (BA) | 24.603 | 21.183 | −13.90% | 140.960 | 94.584 | −32.90% |
| 3 (AB) | 24.437 | 20.933 | −14.34% | 137.876 | 91.793 | −33.42% |

Both metrics improve in all three short pairs: median paired CPU/request change
is −13.90% and RTT p99 change is −33.42%. These directions agree with the formal
45,000/s observations, but the shorter process lifetime gives setup a different
weight, and three pairs do not supply the frozen five-pair evidence. This check
covers one scene only, does not reproduce or explain `mixed_1`, cannot replace
the seven-scene matrix and cannot reverse its rejection decision. The raw short
comparison and invocation are retained under
`build/m3-clean-repro/collected/m3-clean-repro-evidence/representative-pair/`
and `representative-pair-invocation/`; the host record binds every source, input,
shared tool, outcome and derived comparison.

The publication gates following this report are final PR CI and downloaded artifact inspection,
normal merge, exact merged-main push CI and its artifact inspection, followed
by durable hashes and verified `m3-experiments` release assets including the
rejected candidate source.

The [acceptance record](m3_acceptance.md) and [evidence index](m3_evidence_index.md)
track these gates. The release's
[acceptance.json](https://github.com/Owenqi666/low-latency-matching/releases/download/m3-experiments/acceptance.json)
is authoritative for the final source, tested PR/main checkouts and run IDs,
and archive hashes. These identities are assigned only after the actual checks;
no future IDs or passing results are assigned here. Original project/task
documents, VM disks and SSH material remain local.
