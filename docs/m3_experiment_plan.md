# M3 experiment plan

Status: this plan was frozen before implementing batching on 2026-10-17.
The completed matrix rejects the candidate under the unchanged rule; see the
[report](m3_report.md) and [ADR](adr/005-bounded-send-batching.md). Parameters,
hypotheses and decision criteria below retain their pre-experiment meaning.

## Baseline and scope

The baseline is the published `m2-service` commit
`db9b74f4181a2dc4a50966c20080949c839bf73f`. At M3 start, the local main, fetched
`origin/main` and fetched tag all resolve to that commit. The GitHub release is
published and its five asset hashes match the M2 publication record. The only
pre-existing tracked modification adds the local M3 task book to `.gitignore`;
it is preserved. Work continues on `feat/m3-experiments`.

M3 must complete one evidence-backed experiment, not necessarily achieve a
speedup. A second order-slot experiment is conditional on separate diagnostic
evidence and is not required for delivery. The matching algorithm, two production
threads, Boost SPSC queues, protocol, limits and Reference implementation remain
the baseline contracts.

M2's old results motivate a hypothesis but are not the new A/B control. All five
80,000/s overload attempts reached the per-connection outbound limit while
Matching recorded no output-space waits. The old user-only profile did not
attribute kernel or blocked time and used the earlier loadgen. Neither result
establishes that allocation, locking or socket writes are the dominant cause.

## Targeted diagnosis

Use a clean M2 source and the corrected load generator in the existing Linux
VM. Record the new running kernel and environment after restarting that VM.
Run bounded mixed-four-client diagnostics at 10,000/s twice, 45,000/s once,
and a temporal-burst diagnostic. Preserve actual input, admission replay,
resource observations, profiler commands and exits for every attempt.

Distinguish Gateway, Matching and loadgen CPU/scheduling observations. Examine
write/send calls or call chains, outbound backlog, request send lag and loss.
Unavailable hardware/kernel events remain unavailable rather than zero.
Profiler-assisted timings are excluded from the formal comparison.

The first two 10,000/s diagnostics each completed all 100,001 measured requests
and passed the actual-admission Reference check and independent summary. Gateway
`sendto` counts were 701,795 and 701,793, exactly their respective written-frame
counts, with zero `sendmsg`/`write`/`writev`. Gateway task-clock was 2.653/2.657 s,
versus Matching 0.891/0.910 s over roughly 10.1 s. Loadgen lifetime CPU was
2.284/2.261 s. The new samples include kernel paths and also show futex activity;
they do not establish that socket writes are the only bottleneck.

These observations select bounded gather-write as E1. It changes how many
already queued frames one Asio composed write carries, with no wait-to-fill or
flush timer. Fix the batch at **16 frames and 4,096 bytes**, keeping all M2 queue,
send, socket and request limits. Current v1 output frames are at most 138 bytes,
so 16 such frames total 2,208 bytes; the byte limit is not the active bound for
this protocol. No waiting-strategy change or parameter search is included.

The [diagnostic record](m3_diagnostics.md) indexes all four runs, exact commands
and copied evidence at `build/m3-diagnostics/baseline-run-1/`. All 203 original
files passed host SHA-256 verification, and independent host summaries match
the guest summaries. These are current-source
diagnostics, not formal A/B timings. The rebooted guest runs kernel
`6.8.0-147-generic`; the M2 release measurements ran `6.8.0-142-generic`.

## Isolated implementation and adoption rule

First preserve a one-frame control with the same concrete send-queue extraction
and bounded observational counters used by the candidate. Identify it as
**M2 plus observation and local send-queue extraction**, not an unmodified M2
binary. Then change only the compile-time selected frame bound from 1 to 16.
Both sides retain the same descriptor-array storage and accounting code, and
the original M2 tag and exact diff remain reproducible. The extraction permits
deterministic asynchronous write/cancel tests without a second transport backend.

The frozen control is `7b8fcd3b074ed39ff24a3488253397e1dfb7094e`; candidate
`b1ba98c205de3bd717eb0f118fb9771d1f251a25` changes only the frame limit from
1 to 16 in `src/send_queue.hpp`. Shared loadgen resource collection, observation
fields, tests and tools are already in the control. Both passed the 103-test
local Debug suite; Linux and formal evidence are recorded separately.

The primary adoption metric is server lifetime CPU seconds per client-completed
request in the four-client 45,000/s scene, using only fully delivered paired
runs. Adopt only if its paired median reduction is at least 10%, at least four
of five pairs improve, and the correctness and tradeoff checks below hold. This
is a predeclared engineering decision rule, not a confidence interval or a CI
performance gate. Syscall/write-count reductions support mechanism attribution
but cannot substitute for this outcome.

- Both variants must fully deliver all five ordinary scenes and the high-load
  scene in every measured round; an observed failure is retained and prevents a
  loss-free adoption claim rather than being replaced by a convenient repeat.
- For each of those six scenes, the median paired RTT p99 increase must not
  exceed 10%. Report every pair and compare variation; a noisy or contradictory
  outcome supports retaining the control rather than claiming a small win.
- Compare service latency, send lag, server/loadgen CPU and RSS for all scenes.
  Additional memory must be explainable by the fixed per-connection descriptors,
  without enlarged queues or send budgets. Any new unbounded work/storage,
  lifecycle defect or starvation rejects the candidate.
- Report all overload outcomes and losses at the unchanged 80,000/s schedule.
  Overload need not become successful; better completed-only latency after peers
  close is not an adoption benefit.

If these conditions are not met, reject batching, retain the simple production
path, and preserve candidate source, results and the negative conclusion. Do not
add another optimization merely to cross the decision threshold. E2 remains
unstarted without separate core/allocation evidence.

## Formal comparison

Preserve the seven rows of `data/workloads/service-formal.json`, with five
measured runs per variant per row and separate warmups: 70 measured runs plus
14 warmups. Use the same Linux Release toolchain, inputs, corrected loadgen,
verifier, capacities and recording settings. Start a fresh server each time.
Within each row, use AB for odd rounds and BA for even rounds; warmups are A then
B. Never run A and B concurrently.

Each variant retains a complete manifest, validated by the existing independent
service summary. A thin paired runner reuses the existing per-run executor;
the paired checker additionally binds inputs, versions and execution order.
Record each binary's actual source checkout rather than the runner's checkout.
If observational changes are needed, apply them equally to both variants and
preserve that source difference from the unmodified M2 tag.

Preserve unsuccessful runs and all raw outcomes. Comparison distinguishes
evidence validity, server drain, client delivery and sufficient latency samples.

Both variants share the loadgen addition recording user/system CPU and peak
RSS at process lifetime scope, including input preparation and setup but before
evidence formatting and output. Its monotonic capture timestamp is retained;
these are not request-only resource measurements. Historical M2 evidence without
these fields remains valid but cannot supply the new per-round client resources.

## Completion and publication

Reuse the M2 failure/recovery evidence and existing tests. Add only tests of the
new mechanism and paired-evidence checks. Keep Debug, Release, ASan/UBSan and
independent TSan CI, core/network smoke and artifact inspection. A clean Linux
reproduction, latest PR checks, normal merge, exact-main push checks, durable
archives and verified `m3-experiments` publication remain required even if the
candidate is rejected. Original planning documents and VM/SSH files remain local.
