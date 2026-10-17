# ADR 005: test bounded batches of already queued output

Status: experiment completed; reject the 16-frame candidate and retain one-frame writes.

M2 writes one encoded frame per Asio composed write. Two new, fully delivered
and Reference-verified mixed diagnostics each show about 701,794 `sendto` calls
for 100,001 measured requests plus setup, matching written-frame counts. Gateway
CPU exceeds Matching CPU in these runs. Kernel/scheduling paths and loadgen still
matter; this does not establish a single end-to-end bottleneck.

Test a maximum of 16 existing queued frames and 4,096 bytes per composed write.
Start immediately when idle and never wait for additional frames. Keep the
socket, protocol, BBO output, two threads, capacities and slow-peer policy. Current
output frames are at most 138 bytes, so the frame bound limits these batches
before the byte bound. Do not change waiting coordination at the same time.

Extract only the concrete send-queue state needed to share real selection,
completion and close behavior with deterministic asynchronous-stream tests.
Preserve a one-frame control with the same extraction and observation fields;
the candidate changes the selected frame constant. Git revisions and independent
builds retain both, without a runtime strategy selector.

Close conservatively counts all unsettled frames, including in-flight ones, as
discarded. Later callbacks cannot count them again as written. Raw callback bytes
and full-frame prefixes are separate diagnostics, not peer-receipt claims. Retain
frame memory until the callback, including when a different callback closes the
connection or adds output during a write.

The [experiment plan](../m3_experiment_plan.md) fixes the comparison and adoption
rule. Potential benefits are fewer writes/callbacks and lower CPU per completed
request. Costs include fixed descriptor storage, callback accounting and possible
tail-latency/fairness changes. Reject the candidate if full correctness and the
predeclared tradeoffs do not hold. A rejected experiment is a valid result; its
source and all measurements remain reproducible.

The complete 35-pair comparison rejects the candidate under the unchanged rule.
At 45,000/s, server lifetime CPU per completed measured request falls by a paired
median 14.68%, with all five pairs improving. However, single-client mixed RTT
p99 rises by a paired median 71.30%, exceeding the predeclared 10% limit. All
six non-overload scenes fully deliver; the candidate also completes all five
80,000/s attempts where the control loses delivery. Those benefits do not override
the tail-latency condition. No additional parameter search or E2 experiment is
started to obtain a positive outcome.

Restore only the frame bound from 16 to 1, preserving the measured control's
concrete SendQueue, lifecycle tests and bounded observations. Production/build/
test/tool source therefore matches control `7b8fcd3`; the rejected `b1ba98c`
candidate and its one-line patch remain rebuildable. The control's buffer
sequence uses `sendmsg`, unlike original M2's `sendto`; extraction overhead
against pure M2 was not measured. Keep that distinction explicit rather than
making another unmeasured storage or transport change during delivery.

Separate 45k/s profiling observes fewer actual sendmsg calls, but does not
explain the single-client tail regression or supersede the formal decision.
The [report](../m3_report.md) and [per-pair data](../benchmarks/m3_service_pairs.md)
record the benefits, losses, uncertainty and resource tradeoffs.
