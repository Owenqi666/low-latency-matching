# Service measurement method

The measurement tools and evidence checks passed Linux PR CI at `eb0a109`.
Rates were [frozen from calibration](m2_rate_selection.md) before either complete
seven-row, five-round network matrix. The corrected matrix has 30 successful
measured runs and five overload delivery failures; all 42 warmup/measured attempts
drained and passed Reference verification. The [M2 report](m2_report.md)
distinguishes this matrix from the preserved earlier run with post-start schedule
initialization. The
[Linux synchronous core results](m2_core_measurements.md) and separate
[service profiling](m2_profiling.md) have distinct timing/source boundaries.
M1 results retain their original platform and scope.

## Boundaries

| Metric | Start | End |
|---|---|---|
| Core latency | Preconstructed command enters synchronous `process` | All business events are in its no-wait receiver |
| Service completion | Timestamp immediately before successful command-queue publication | Complete is successfully published to the event queue |
| Client RTT | First actual `async_write` attempt for the request | Read callback receives the complete Complete frame |
| Gateway wait | Read callback receives the final byte of a frame | Successful queue admission |
| Send lag | Planned send time | First actual write attempt |

Service latency includes command queuing, matching, BBO publication and output
backpressure. It excludes Gateway delivery. The queue start timestamp includes
the successful push operation's cost. RTT ends on Complete, not Accepted or local
write completion. A callback-entry timestamp avoids moving RTT's end after digest
calculation. Differences use one process's steady clock; clocks on different hosts
are never subtracted. Core timing has its existing clock probe; loadgen also saves
clock interval and timestamp-recording overhead without subtracting a constant.

Frames coalesced into one read share its readiness timestamp, including frames
waiting behind an earlier pending command. Another read is issued only when the
leading buffered frame is incomplete, so this timestamp also represents the
arrival of a fragmented frame's final bytes.

## Bounded workload and outcomes

The generator saves a finite setup trace, input trace and monotonically ordered
schedule. Setup is sequential and outside measurement. Each formal round restarts
the server; warmup uses a different server instance. Logical connection IDs map
to server-assigned ClientIds and the successful admission trace is preserved.
Different multi-client arrival orders are verified separately.

The first complete `f58ff79` matrix exposed an O(N) scheduled-timestamp fill
after measurement start, delaying initial writes and creating catch-up sends.
The corrected `eb0a109` measurement derives scheduled times from start plus offsets
prepared beforehand, without traversing the complete plan after starting the
clock. It has its own complete network run and source identity; the original
matrix remains available and the frozen rates did not change. The service binary
was unchanged by this loadgen correction.

The load generator sends on planned offsets while independently receiving frames.
Per-connection send bytes, total in-flight requests and preallocated experiment
records are bounded. Hitting a bound records unstarted requests and a reason;
it does not change to response-paced sending. TCP_NODELAY is fixed on service,
CLI and loadgen connections. No alternative transport/waiting strategy is selected.

For measured requests, `planned = not_started + started` and
`started = completed + failed + unfinished`. Completed requests split into
business Accepted/Rejected. Local full-frame writes are a separate observation.
The service checks `admitted = completed + uncompleted`; consumer/write/discard
counters distinguish internal completion from delivery. Peer closure can lose
unsolicited maker/BBO delivery even when a request's Complete has arrived; those
service counters remain visible.

## Reference and independent checks

`verify_service` requires a successful complete drain with enabled records. It
replays every admitted command in the independent vector engine, comparing full
wire-field FNV digests, event/Trade counts, result status and final snapshot.
It binds its report to the input trace, configuration, server report, samples and
snapshot. A digest is not a collision-free proof; small service tests additionally
compare every event field, per-client routing and BBO against reference snapshots.

The independent Python summary checks all expected warmups and rounds against
the effective workload parameters. It validates original input hashes, connection
mapping, every planned outcome, schedule/attempt/Complete times, sample counts,
queue limits, server admission order, client/service digests and the reference
report's file bindings. Missing entire rounds, inconsistent counts and stale
success reports must fail. Failed revalidation removes old derived success reports.

A failed server drain is retained with its completed prefix, current admission,
worker phase, last event sequence and unfinished count. It is not compared to a
complete replay's final state and produces no successful service-latency result.
Lossy overload attempts can still have internally consistent evidence. Reports
state evidence validity and run success separately. A failed attempt is never
silently replaced or filtered out of the matrix.

The corrected matrix illustrates the distinction: `evidence_valid=true` and
`all_runs_succeeded=false`. Thirty of 35 measured runs succeeded; 34 met the
normal sample threshold, including four failed overload attempts. A sufficient
number of completed samples does not undo losses or prove stable service at that
offered rate. The five overload runs are reported with their 2–4 slow-client
closures and request outcomes, even though every server drained admitted work.

## Formal matrix and reporting

Use Linux unsanitized Release. Calibrate with short runs, then freeze rates and
run at least five rounds of: mixed, cancellation-heavy, sweep and temporal burst
with four clients; mixed with one client at the same aggregate ordinary rate;
and four-client mixed near the observed capacity and under explicit overload.
Use C=1,000 and at least 64 makers per sweep pattern. No Cartesian product of
all capacities, connection counts and rates is required.

Normal scenes start with at least 10 seconds and 100,000 completed requests;
report insufficient samples explicitly. Overload has a finite schedule and drain
deadline. Nearest-rank p50/p99 are reported per round from completed samples,
alongside request losses and send lag. A batch mean is not a request percentile.
p99.9 is not reported without enough samples and repeat stability.

The [locked formal manifest](../data/workloads/service-formal.json) selects
10000 planned requests/s for ordinary mixed/cancellation/sweep and one-client
mixed, 2000/s for the temporal burst, 45000/s for the near-capacity candidate,
and 80000/s for overload. Every row has five fresh measured instances and an
independent warmup. The near label comes from short calibration; it does not
guarantee loss-free longer runs. Keep the frozen parameters and every failed
attempt, report completed-only percentiles with their loss counts, and do not
infer a sustainable rate from a short successful probe or a failed run's small
completed subset.

The current summary's rate window runs from measurement start through final
completion/drain; target schedule rate is shown separately. Setup is excluded from
latency samples, while process CPU/RSS includes setup and the full server lifetime
up to shutdown, before evidence formatting. Raw samples permit separate windows.
Record SHA, dirty state, binary/input hashes, compiler and flags, CPU/kernel, thread
placement, frequency controls, virtualization and background load. Unknown or
uncontrolled values remain explicit. Profiling runs separately from formal timing.

CI uses short correctness smoke without absolute latency/throughput gates.
Formal Linux VM loopback data describes that VM and resource sharing; it is not
bare-metal or cross-machine evidence. Long-term delivery archives include inputs,
all raw samples, original/effective manifests, run logs and environment metadata.
The release's `acceptance.json` is authoritative for the measured sources,
separately verified final PR/main revisions, workflows and archive identities.
A later documentation commit does not silently change the source identity of
an earlier measurement.

## Paired M3 comparison

The [M3 plan](m3_experiment_plan.md) fixes the one-frame observed control and
16-frame candidate, their adoption criteria and the unchanged seven-row matrix.
Use separate clean source/build directories. The control includes the same
send-queue extraction and bounded counters as the candidate; it is not the pure
M2 tag. The candidate changes one compile-time frame bound, not a runtime option.

From an existing repository, choose unused paths and build both revisions:

```sh
git fetch origin
git worktree add --detach /tmp/llmatch-m3-control 7b8fcd3b074ed39ff24a3488253397e1dfb7094e
git worktree add --detach /tmp/llmatch-m3-candidate b1ba98c205de3bd717eb0f118fb9771d1f251a25
for comparison_source in /tmp/llmatch-m3-control /tmp/llmatch-m3-candidate; do
  (cd "$comparison_source" && cmake --preset release && cmake --build --preset release --parallel 2)
done
python3 /tmp/llmatch-m3-candidate/scripts/run_service_pair.py \
  --baseline-source /tmp/llmatch-m3-control \
  --baseline-server /tmp/llmatch-m3-control/build/release/matching_server \
  --candidate-source /tmp/llmatch-m3-candidate \
  --candidate-server /tmp/llmatch-m3-candidate/build/release/matching_server \
  --loadgen /tmp/llmatch-m3-candidate/build/release/loadgen \
  --verifier /tmp/llmatch-m3-candidate/build/release/verify_service \
  --manifest /tmp/llmatch-m3-candidate/data/workloads/service-formal.json \
  --output-dir /tmp/llmatch-m3-formal-new
python3 /tmp/llmatch-m3-candidate/scripts/summarize_service_pair.py /tmp/llmatch-m3-formal-new
```

Formal mode requires Linux and unsanitized Release. Supply `--host-environment`
with actual host metadata when running inside a VM. Each scene starts with
separate A/B warmups, then five pairs: AB on odd rounds and BA on even rounds.
All 70 measured attempts and 14 warmups remain in two complete variant manifests.
The original service summary checks each side before the pair checker binds
input hashes, source/build records, shared tools and actual execution order.
There is no formal `--row` or `--rounds` shortcut. For a short functional check,
use `service-smoke.json` and explicit short overrides, and label that result as
smoke rather than a replacement for the full comparison.

For the recorded T07 representative reproduction, unpack `m3-validation.tar.gz`
from the release and use its retained wrapper and `representative-45k.json`.
After building the two worktrees above, run from the archive's extraction root:

```sh
bash validation/clean-repro/run_representative_pair.sh \
  /tmp/llmatch-m3-control /tmp/llmatch-m3-candidate /tmp/llmatch-m3-control \
  /absolute/path/to/current-host-environment.json /tmp/llmatch-m3-short-new
```

Supply a JSON file describing the actual host/VM and controls, not the archived
host's identity. This uses the freshly built control's shared loadgen/verifier,
three pairs of 100,000 requests at 45,000/s and separate 1,000-command warmups.
The approximately 2.222-second windows are smoke, below the formal duration
requirement. The wrapper retains the invocation and both exit statuses; its
independent summary is not a substitute for the full adoption matrix.

The runner exits nonzero when a client-delivery run fails, while the independent
summary can still validate its evidence. Inspect `summarizer_exit`,
`evidence_valid`, `all_runs_succeeded` and the individual outcomes before deciding
whether the tool failed. Failed pairs retain both absolute results; they do not
produce latency/rate/CPU benefit deltas from a completed subset.

New loadgen `resource_usage` records user/system CPU and peak RSS for process
lifetime through the capture point, including input preparation and setup,
before CSV/JSON output. Server resources retain their own lifetime scope.
Dividing lifetime CPU by measured completions is an amortized cost, not CPU
spent only inside each request. Older M2 runs have no client resource snapshot;
their summary explicitly reports null rather than manufacturing a zero.

Server write observations count composed asynchronous operations and submitted
frames/bytes, with fixed histograms and the compiled batch limits. They are not
system-call counts. Error or after-close callback bytes and complete-frame
prefixes remain separate from conservative written/discarded totals; none alone
establish peer receipt. Actual syscall profiling stays outside formal timing.
