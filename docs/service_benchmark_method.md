# M2 service measurement method

Status: tools and acceptance are in development. Formal results will be linked
from the M2 report after their environment, complete run set and reference checks
have been verified. M1 results retain their original platform and scope.

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
